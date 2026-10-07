from datetime import datetime
from decimal import Decimal
import pytest
from inventory_app.exceptions import ValidationError
from inventory_app.models.product import Product
from inventory_app.models.transaction import Transaction, TransactionType


def test_product_invariants_and_low_stock_detection() -> None:
    item = Product(
        product_id="  prd-100 ",
        name="  Arduino Mega 2560 ",
        category="microcontrollers",
        supplier_id=" sup-01 ",
        quantity=4,
        cost_price=Decimal("22.5"),
        selling_price=Decimal("35.00"),
        min_stock_level=5,
    )
    assert item.product_id == "PRD-100"
    assert item.name == "Arduino Mega 2560"
    assert item.category == "Microcontrollers"
    assert item.supplier_id == "SUP-01"
    assert item.cost_price == Decimal("22.50")
    assert item.is_low_stock is True


def test_product_csv_serialization_roundtrip() -> None:
    original = Product(
        product_id="PRD-200",
        name="Industrial Barcode Scanner",
        category="Peripherals",
        supplier_id="SUP-02",
        quantity=15,
        cost_price=Decimal("40.00"),
        selling_price=Decimal("65.00"),
        min_stock_level=5,
    )
    csv_dict: dict[str, str] = original.to_csv_row()
    restored: Product = Product.from_csv_row(csv_dict)
    assert restored == original


def test_product_from_csv_row_rejects_corrupt_types() -> None:
    bad_row: dict[str, str] = {
        "product_id": "PRD-300",
        "name": "Stepper Motor",
        "category": "Actuators",
        "supplier_id": "SUP-01",
        "quantity": "invalid_int",
        "cost_price": "12.00",
        "selling_price": "20.00",
        "min_stock_level": "3",
    }
    with pytest.raises(ValidationError):
        Product.from_csv_row(bad_row)


def test_sale_transaction_financial_calculations() -> None:
    sale_tx = Transaction(
        transaction_id="TX-0001",
        timestamp=datetime(2026, 10, 6, 12, 0, 0),
        product_id="PRD-200",
        transaction_type=TransactionType.SALE,
        quantity_delta=-3,
        unit_cost_price=Decimal("40.00"),
        unit_selling_price=Decimal("65.00"),
        notes="Walk-in customer purchase",
    )
    assert sale_tx.total_revenue == Decimal("195.00")
    assert sale_tx.total_cogs == Decimal("120.00")
    assert sale_tx.estimated_profit == Decimal("75.00")