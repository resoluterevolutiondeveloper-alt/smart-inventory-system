from dataclasses import dataclass, field
from typing import Dict, Sequence, Set
from inventory_app.exceptions import ValidationError

SUPPLIER_CSV_FIELDS: Sequence[str] = (
    "supplier_id",
    "name",
    "contact_info",
    "supplied_products",
)


@dataclass
class Supplier:
    """Encapsulates supplier contact metadata and a unique set of supplied product IDs."""

    supplier_id: str
    name: str
    contact_info: str
    supplied_products: Set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        """Normalize strings and validate supplier invariants."""
        self.supplier_id = self.supplier_id.strip().upper()
        self.name = self.name.strip()
        self.contact_info = self.contact_info.strip()
        self.supplied_products = {
            pid.strip().upper() for pid in self.supplied_products if pid.strip()
        }

        if not self.supplier_id or not self.name or not self.contact_info:
            raise ValidationError(
                "supplier_id, name, and contact_info cannot be empty strings."
            )

    def register_supplied_product(self, product_id: str) -> None:
        """Associate a product ID with this supplier using O(1) set insertion."""
        cleaned_id = product_id.strip().upper()
        if not cleaned_id:
            raise ValidationError("Cannot associate an empty product_id with a supplier.")
        self.supplied_products.add(cleaned_id)

    def to_csv_row(self) -> Dict[str, str]:
        """Serialize Supplier to a flat dictionary for CSV file persistence.

        Note: Join `sorted(self.supplied_products)` with a pipe delimiter (`|`)
        so the set of product IDs is stored deterministically in a single CSV column.
        """
        # TODO: Return a dictionary with keys matching SUPPLIER_CSV_FIELDS:
        # "supplier_id", "name", "contact_info", and "supplied_products" (joined by "|").
        return {
            "supplier_id": self.supplier_id,
            "name": self.name,
            "contact_info": self.contact_info,
            "supplied_products": "|".join(sorted(self.supplied_products)),
        }

    @classmethod
    def from_csv_row(cls, row: Dict[str, str]) -> "Supplier":
        """Deserialize a CSV row dictionary into a validated Supplier instance.

        Raises:
            ValidationError: If required columns are missing or invalid.
        """
        try:
            raw_products = row.get("supplied_products", "").strip()
            product_set: Set[str] = (
                {pid.strip().upper() for pid in raw_products.split("|") if pid.strip()}
                if raw_products
                else set()
            )
            return cls(
                supplier_id=row["supplier_id"].strip(),
                name=row["name"].strip(),
                contact_info=row["contact_info"].strip(),
                supplied_products=product_set,
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValidationError(f"Malformed supplier CSV row {row}: {exc}") from exc