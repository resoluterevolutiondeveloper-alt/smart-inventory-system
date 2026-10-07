from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Tuple
from inventory_app.exceptions import ValidationError
from inventory_app.models.product import Product
from inventory_app.models.transaction import Transaction, TransactionType
from inventory_app.services.inventory_service import InventoryService


@dataclass(frozen=True)
class FinancialSummary:

    total_units_sold: int
    total_revenue: Decimal
    total_cogs: Decimal
    estimated_profit: Decimal


class SalesService:

    def __init__(self, inventory_service: InventoryService) -> None:
        self._inventory = inventory_service

    def record_sale(
        self, product_id: str, quantity: int, notes: str = ""
    ) -> Product:
        """Record a sale transaction and update inventory stock.

        Raises:
            ValidationError: If quantity <= 0.
            KeyError: If product_id does not exist.
            InsufficientStockError: If available stock is less than quantity.
        """
        if quantity <= 0:
            raise ValidationError("Sale quantity must be a positive integer.")
        return self._inventory.adjust_stock(
            product_id=product_id,
            quantity_delta=-quantity,
            tx_type=TransactionType.SALE,
            notes=notes,
        )

    def get_financial_summary(self) -> FinancialSummary:
        """Calculate total units sold, revenue, COGS, and estimated profit across all sales."""
        sale_txs: List[Transaction] = [
            tx
            for tx in self._inventory.transactions
            if tx.transaction_type == TransactionType.SALE
        ]
        total_units = sum(abs(tx.quantity_delta) for tx in sale_txs)
        revenue = sum((tx.total_revenue for tx in sale_txs), Decimal("0.00"))
        cogs = sum((tx.total_cogs for tx in sale_txs), Decimal("0.00"))
        return FinancialSummary(
            total_units_sold=total_units,
            total_revenue=revenue,
            total_cogs=cogs,
            estimated_profit=revenue - cogs
        )

    def get_best_selling_products(
        self, top_n: int = 5
    ) -> List[Tuple[str, int, Decimal]]:
        """Rank products by total units sold descending.

        Returns:
            List of tuples: (product_id, total_units_sold, total_revenue)
        """
        units_by_product: Dict[str, int] = {}
        revenue_by_product: Dict[str, Decimal] = {}

        for tx in self._inventory.transactions:
            if tx.transaction_type == TransactionType.SALE:
                pid = tx.product_id
                units_by_product[pid] = units_by_product.get(pid, 0) + abs(
                    tx.quantity_delta
                )
                revenue_by_product[pid] = (
                    revenue_by_product.get(pid, Decimal("0.00")) + tx.total_revenue
                )
        ranked_products: List[Tuple[str, int, Decimal]] = [
            (pid, units_by_product[pid], revenue_by_product[pid])
            for pid in units_by_product
        ]
        ranked_products.sort(key=lambda x: x[1], reverse=True)
        return ranked_products[:top_n]

    def get_declining_products(
        self, reference_time: datetime | None = None, window_days: int = 30
    ) -> List[Tuple[str, int, int]]:
        """Identify products where sales in the current window dropped vs the previous window.

        Returns:
            List of tuples: (product_id, previous_period_units, current_period_units)
        """
        now = reference_time or datetime.now()
        current_start = now - timedelta(days=window_days)
        previous_start = current_start - timedelta(days=window_days)

        prev_units: Dict[str, int] = {}
        curr_units: Dict[str, int] = {}

        for tx in self._inventory.transactions:
            if tx.transaction_type != TransactionType.SALE:
                continue
            pid = tx.product_id
            units = abs(tx.quantity_delta)
            if previous_start <= tx.timestamp < current_start:
                prev_units[pid] = prev_units.get(pid, 0) + units
            elif current_start <= tx.timestamp <= now:
                curr_units[pid] = curr_units.get(pid, 0) + units

        declining: List[Tuple[str, int, int]] = []
        for pid, prev_count in prev_units.items():
            curr_count = curr_units.get(pid, 0)
            if curr_count < prev_count:
                declining.append((pid, prev_count, curr_count))

        return sorted(declining, key=lambda item: item[2] - item[1])