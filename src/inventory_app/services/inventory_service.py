from datetime import datetime
from typing import Dict, List, Set
import uuid
from inventory_app.exceptions import (
    DuplicateProductError,
    InsufficientStockError,
    ValidationError,
)
from inventory_app.models.product import Product
from inventory_app.models.transaction import Transaction, TransactionType
from inventory_app.repositories.csv_repo import CSVRepository


class InventoryService:
    """Centralizes product CRUD, stock movements, low-stock alerts, and search."""

    def __init__(
        self,
        product_repo: CSVRepository[Product],
        transaction_repo: CSVRepository[Transaction],
    ) -> None:
        self._product_repo: CSVRepository[Product] = product_repo
        self._tx_repo: CSVRepository[Transaction] = transaction_repo
        self._products: Dict[str, Product] = {
            prod.product_id: prod for prod in self._product_repo.load_all()
        }
        self._transactions: List[Transaction] = self._tx_repo.load_all()

    @property
    def products(self) -> List[Product]:
        """Return a list of all products sorted by product_id."""
        return sorted(self._products.values(), key=lambda p: p.product_id)

    @property
    def transactions(self) -> List[Transaction]:
        """Return a defensive copy of the transaction history for reporting."""
        return list(self._transactions)

    @property
    def categories(self) -> Set[str]:
        """Return a set of all unique categories across registered products."""
        return {prod.category for prod in self._products.values()}

    def get_product(self, product_id: str) -> Product:
        """Retrieve a single product by ID in O(1) time.

        Raises:
            KeyError: If product_id does not exist.
        """
        normalized_id = product_id.strip().upper()
        if normalized_id not in self._products:
            raise KeyError(f"Product ID '{normalized_id}' not found in inventory.")
        return self._products[normalized_id]

    def add_product(self, product: Product) -> None:
        """Register a new product and persist atomically to CSV.

        Raises:
            DuplicateProductError: If product.product_id is already registered.
        """
        if product.product_id in self._products:
            raise DuplicateProductError(
                f"Product ID '{product.product_id}' already exists."
            )
        self._products[product.product_id] = product
        self._product_repo.save_all(self.products)

    def update_product(self, updated_product: Product) -> None:
        """Update an existing product's details and persist to CSV.

        Raises:
            KeyError: If updated_product.product_id does not exist.
        """
        if updated_product.product_id not in self._products:
            raise KeyError(f"Product ID '{updated_product.product_id}' not found.")
        self._products[updated_product.product_id] = updated_product
        self._product_repo.save_all(self.products)

    def delete_product(self, product_id: str) -> None:
        """Delete a product from inventory and persist to CSV.

        Raises:
            KeyError: If product_id does not exist.
        """
        normalized_id = product_id.strip().upper()
        if normalized_id not in self._products:
            raise KeyError(f"Product ID '{normalized_id}' not found.")
        del self._products[normalized_id]
        self._product_repo.save_all(self.products)

    def adjust_stock(
        self,
        product_id: str,
        quantity_delta: int,
        tx_type: TransactionType,
        notes: str = "",
    ) -> Product:
        """Execute a stock-in (+), stock-out (-), sale (-), or adjustment (+/-).

        Automatically updates quantity, logs a Transaction, and saves both CSVs.

        Raises:
            KeyError: If product_id is not found.
            ValidationError: If quantity_delta == 0.
            InsufficientStockError: If resulting stock would be < 0.
        """
        product = self.get_product(product_id)
        if quantity_delta == 0:
            raise ValidationError("Stock quantity_delta cannot be zero.")

        new_quantity: int = product.quantity + quantity_delta

        if new_quantity < 0:
            raise InsufficientStockError(
                f"Insufficient stock for {product.product_id}: available={product.quantity}, requested={abs(quantity_delta)}"
            )
        product.quantity = new_quantity
        tx = Transaction(
            transaction_id=f"TX-{uuid.uuid4().hex[:8].upper()}",
            timestamp=datetime.now(),
            product_id=product.product_id,
            transaction_type=tx_type,
            quantity_delta=quantity_delta,
            unit_cost_price=product.cost_price,
            unit_selling_price=product.selling_price,
            notes=notes,
        )
        self._transactions.append(tx)
        self._product_repo.save_all(self.products)
        self._tx_repo.save_all(self._transactions)
        return product

    def get_low_stock_products(self) -> List[Product]:
        """Return all products whose current quantity is at or below min_stock_level."""
        return [product for product in self.products if product.is_low_stock]

    def search_products(
        self, query: str = "", category: str | None = None
    ) -> List[Product]:
        """Filter products by case-insensitive ID/name substring and optional category."""
        normalized_query = query.strip().lower()
        normalized_category = category.strip().title() if category else None

        filtered_products = [
            prod for prod in self.products
            if (normalized_category is None or prod.category == normalized_category) and
               (not normalized_query or normalized_query in prod.product_id.lower() or normalized_query in prod.name.lower())
        ]
        return filtered_products