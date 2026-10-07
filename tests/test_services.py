from decimal import Decimal
from pathlib import Path
import pytest
from inventory_app.exceptions import InsufficientStockError
from inventory_app.models.product import PRODUCT_CSV_FIELDS, Product
from inventory_app.models.transaction import (
    TRANSACTION_CSV_FIELDS,
    Transaction,
    TransactionType,
)
from inventory_app.repositories.csv_repo import CSVRepository
from inventory_app.services.inventory_service import InventoryService
from inventory_app.services.sales_service import SalesService


def test_inventory_and_sales_lifecycle(tmp_path: Path) -> None:
    """Verify atomic CSV storage, stock adjustments, low-stock alerts, and sales math."""
    prod_repo = CSVRepository[Product](
        file_path=tmp_path / "products.csv",
        fieldnames=PRODUCT_CSV_FIELDS,
        serializer=lambda p: p.to_csv_row(),
        deserializer=Product.from_csv_row,
    )
    tx_repo = CSVRepository[Transaction](
        file_path=tmp_path / "transactions.csv",
        fieldnames=TRANSACTION_CSV_FIELDS,
        serializer=lambda t: t.to_csv_row(),
        deserializer=Transaction.from_csv_row,
    )

    inv_service = InventoryService(product_repo=prod_repo, transaction_repo=tx_repo)
    sales_service = SalesService(inventory_service=inv_service)

    # 1. Register product
    sensor = Product(
        product_id="PRD-500",
        name="Ultrasonic Distance Sensor",
        category="Sensors",
        supplier_id="SUP-01",
        quantity=10,
        cost_price=Decimal("5.00"),
        selling_price=Decimal("12.00"),
        min_stock_level=4,
    )
    inv_service.add_product(sensor)

    # 2. Record a sale of 7 units -> remaining stock should be 3 (triggers low stock!)
    updated_product = sales_service.record_sale("PRD-500", quantity=7, notes="Lab order")
    assert updated_product.quantity == 3
    assert updated_product.is_low_stock is True
    assert len(inv_service.get_low_stock_products()) == 1

    # 3. Verify InsufficientStockError when attempting to sell 5 more units (only 3 left)
    with pytest.raises(InsufficientStockError):
        sales_service.record_sale("PRD-500", quantity=5)

    # 4. Verify financial summary math (7 units * $12 = $84 revenue; 7 * $5 = $35 COGS; $49 profit)
    summary = sales_service.get_financial_summary()
    assert summary.total_units_sold == 7
    assert summary.total_revenue == Decimal("84.00")
    assert summary.total_cogs == Decimal("35.00")
    assert summary.estimated_profit == Decimal("49.00")