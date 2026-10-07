from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Dict, Sequence
from inventory_app.exceptions import ValidationError

PRODUCT_CSV_FIELDS: Sequence[str] = (
    "product_id",
    "name",
    "category",
    "supplier_id",
    "quantity",
    "cost_price",
    "selling_price",
    "min_stock_level",
)


@dataclass
class Product:

    product_id: str
    name: str
    category: str
    supplier_id: str
    quantity: int
    cost_price: Decimal
    selling_price: Decimal
    min_stock_level: int

    def __post_init__(self) -> None:
        """Sanitize strings and enforce domain invariants."""
        self.product_id = self.product_id.strip().upper()
        self.name = self.name.strip()
        self.category = self.category.strip().title()
        self.supplier_id = self.supplier_id.strip().upper()

        if not all([self.product_id, self.name, self.category, self.supplier_id]):
            raise ValidationError("String identifiers and names cannot be empty.")
        if self.quantity < 0 or self.min_stock_level < 0:
            raise ValidationError("Quantity and min_stock_level must be >= 0.")
        if self.cost_price < Decimal("0.00") or self.selling_price < Decimal("0.00"):
            raise ValidationError("Prices cannot be negative.")

        self.cost_price = self.cost_price.quantize(Decimal("0.01"))
        self.selling_price = self.selling_price.quantize(Decimal("0.01"))

    @property
    def is_low_stock(self) -> bool:
        return self.quantity <= self.min_stock_level

    def to_csv_row(self) -> Dict[str, str]:
        return {
            "product_id": str(self.product_id),
            "name":str(self.name),
            "category": str(self.category),
            "supplier_id": str(self.supplier_id),
            "quantity": str(self.quantity),
            "cost_price": str(self.cost_price),
            "selling_price": str(self.selling_price),
            "min_stock_level": str(self.min_stock_level)
        }

    @classmethod
    def from_csv_row(cls, row: Dict[str, str]) -> "Product":
        try:
            return cls(
                product_id=row["product_id"],
                name=row["name"],
                category=row["category"],
                supplier_id=row["supplier_id"],
                quantity=int(row["quantity"]),
                cost_price=Decimal(row["cost_price"]),
                selling_price=Decimal(row["selling_price"]),
                min_stock_level=int(row["min_stock_level"]),
            )
        except (KeyError, ValueError, InvalidOperation, TypeError) as exc:
            raise ValidationError(f"Malformed product CSV row {row}: {exc}") from exc