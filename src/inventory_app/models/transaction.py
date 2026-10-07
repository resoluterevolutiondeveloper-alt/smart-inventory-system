from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Dict, Sequence, Tuple
from inventory_app.exceptions import ValidationError

TRANSACTION_CSV_FIELDS: Sequence[str] = (
    "transaction_id",
    "timestamp",
    "product_id",
    "transaction_type",
    "quantity_delta",
    "unit_cost_price",
    "unit_selling_price",
    "notes",
)


class TransactionType(str, Enum):
    STOCK_IN = "STOCK_IN"
    STOCK_OUT = "STOCK_OUT"
    SALE = "SALE"
    ADJUSTMENT = "ADJUSTMENT"


@dataclass(frozen=True)
class Transaction:

    transaction_id: str
    timestamp: datetime
    product_id: str
    transaction_type: TransactionType
    quantity_delta: int
    unit_cost_price: Decimal
    unit_selling_price: Decimal
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.transaction_id.strip() or not self.product_id.strip():
            raise ValidationError("transaction_id and product_id cannot be empty.")
        if self.quantity_delta == 0:
            raise ValidationError("quantity_delta cannot be zero.")
        if self.unit_cost_price < Decimal("0.00") or self.unit_selling_price < Decimal("0.00"):
            raise ValidationError("Transaction unit prices cannot be negative.")

    @property
    def audit_tuple(self) -> Tuple[str, str, str, int]:
        return (
            self.transaction_id,
            self.timestamp.isoformat(),
            self.product_id,
            self.quantity_delta,
        )

    @property
    def total_revenue(self) -> Decimal:
        if self.transaction_type == TransactionType.SALE:
            return Decimal(abs(self.quantity_delta)) * self.unit_selling_price.quantize(Decimal("0.01"))
        else:
            return Decimal("0.00")

    @property
    def total_cogs(self) -> Decimal:
        if self.transaction_type == TransactionType.SALE:
            return Decimal(abs(self.quantity_delta)) * self.unit_cost_price.quantize(Decimal("0.01"))
        else:
            return Decimal("0.00")

    @property
    def estimated_profit(self) -> Decimal:
        """Calculate estimated net profit for this transaction."""
        return self.total_revenue - self.total_cogs

    def to_csv_row(self) -> Dict[str, str]:
        """Serialize Transaction to a CSV dictionary."""
        return {
            "transaction_id": self.transaction_id,
            "timestamp": self.timestamp.isoformat(),
            "product_id": self.product_id,
            "transaction_type": self.transaction_type.value,
            "quantity_delta": str(self.quantity_delta),
            "unit_cost_price": str(self.unit_cost_price.quantize(Decimal("0.01"))),
            "unit_selling_price": str(self.unit_selling_price.quantize(Decimal("0.01"))),
            "notes": self.notes,
        }

    @classmethod
    def from_csv_row(cls, row: Dict[str, str]) -> "Transaction":
        """Deserialize a CSV row dictionary into a validated Transaction instance."""
        try:
            return cls(
                transaction_id=row["transaction_id"].strip(),
                timestamp=datetime.fromisoformat(row["timestamp"].strip()),
                product_id=row["product_id"].strip().upper(),
                transaction_type=TransactionType(row["transaction_type"].strip()),
                quantity_delta=int(row["quantity_delta"]),
                unit_cost_price=Decimal(row["unit_cost_price"]),
                unit_selling_price=Decimal(row["unit_selling_price"]),
                notes=row.get("notes", "").strip(),
            )
        except (KeyError, ValueError, InvalidOperation, TypeError) as exc:
            raise ValidationError(f"Malformed transaction CSV row {row}: {exc}") from exc