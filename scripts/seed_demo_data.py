"""Deterministic database seeder for live project defense and UI verification."""

import sys
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List

from inventory_app.config import AppConfig, ensure_src_on_sys_path
from inventory_app.exceptions import InventoryAppError
from inventory_app.models.product import PRODUCT_CSV_FIELDS, Product
from inventory_app.models.supplier import SUPPLIER_CSV_FIELDS, Supplier
from inventory_app.models.transaction import (
    TRANSACTION_CSV_FIELDS,
    Transaction,
    TransactionType,
)
from inventory_app.repositories.csv_repo import CSVRepository


def seed_database() -> None:
    """Populate CSV repositories with realistic products, suppliers, and 60-day sales history.

    Raises:
        InventoryAppError: If atomic CSV persistence fails.
    """
    ensure_src_on_sys_path()
    config = AppConfig.load()

    supplier_repo = CSVRepository[Supplier](
        file_path=config.suppliers_csv,
        fieldnames=SUPPLIER_CSV_FIELDS,
        serializer=lambda s: s.to_csv_row(),
        deserializer=Supplier.from_csv_row,
    )
    product_repo = CSVRepository[Product](
        file_path=config.products_csv,
        fieldnames=PRODUCT_CSV_FIELDS,
        serializer=lambda p: p.to_csv_row(),
        deserializer=Product.from_csv_row,
    )
    tx_repo = CSVRepository[Transaction](
        file_path=config.transactions_csv,
        fieldnames=TRANSACTION_CSV_FIELDS,
        serializer=lambda t: t.to_csv_row(),
        deserializer=Transaction.from_csv_row,
    )

    suppliers: List[Supplier] = [
        Supplier(
            supplier_id="SUP-01",
            name="Mechatronics Global Components Ltd",
            contact_info="orders@mechglobal.com | +234-800-555-0101",
            supplied_products={"PRD-101", "PRD-102"},
        ),
        Supplier(
            supplier_id="SUP-02",
            name="Embedded Vision Systems Inc",
            contact_info="supply@embeddedvision.io | +234-800-555-0202",
            supplied_products={"PRD-103", "PRD-104"},
        ),
    ]

    products: List[Product] = [
        Product(
            product_id="PRD-101",
            name="ESP32-S3 AI Camera Module",
            category="Microcontrollers",
            supplier_id="SUP-01",
            quantity=3,  # LOW STOCK (<= 10) -> Triggers Low-Stock Alert & Red Bar!
            cost_price=Decimal("12.50"),
            selling_price=Decimal("22.00"),
            min_stock_level=10,
        ),
        Product(
            product_id="PRD-102",
            name="MG996R High-Torque Servo",
            category="Actuators",
            supplier_id="SUP-01",
            quantity=45,  # HEALTHY STOCK
            cost_price=Decimal("4.00"),
            selling_price=Decimal("8.50"),
            min_stock_level=15,
        ),
        Product(
            product_id="PRD-103",
            name="RPLiDAR A1M8 360 Laser Scanner",
            category="Sensors",
            supplier_id="SUP-02",
            quantity=2,  # LOW STOCK (<= 5) -> Triggers Restock Recommendation!
            cost_price=Decimal("75.00"),
            selling_price=Decimal("115.00"),
            min_stock_level=5,
        ),
        Product(
            product_id="PRD-104",
            name="Raspberry Pi 5 (8GB RAM)",
            category="Embedded Computers",
            supplier_id="SUP-02",
            quantity=28,  # HEALTHY STOCK
            cost_price=Decimal("68.00"),
            selling_price=Decimal("95.00"),
            min_stock_level=8,
        ),
    ]

    now = datetime.now()
    transactions: List[Transaction] = [
        # Previous 30-60 day window: High sales for PRD-102 (25 units sold 45 days ago)
        Transaction(
            transaction_id="TX-HIST01",
            timestamp=now - timedelta(days=45),
            product_id="PRD-102",
            transaction_type=TransactionType.SALE,
            quantity_delta=-25,
            unit_cost_price=Decimal("4.00"),
            unit_selling_price=Decimal("8.50"),
            notes="Previous month robotics workshop order",
        ),
        # Current 0-30 day window: Lower sales for PRD-102 (only 5 units sold 10 days ago -> DECLINING!)
        Transaction(
            transaction_id="TX-CURR01",
            timestamp=now - timedelta(days=10),
            product_id="PRD-102",
            transaction_type=TransactionType.SALE,
            quantity_delta=-5,
            unit_cost_price=Decimal("4.00"),
            unit_selling_price=Decimal("8.50"),
            notes="Recent walk-in sale",
        ),
        # Current 0-30 day window: Massive sales for PRD-101 (40 units sold 3 days ago -> BEST SELLER!)
        Transaction(
            transaction_id="TX-CURR02",
            timestamp=now - timedelta(days=3),
            product_id="PRD-101",
            transaction_type=TransactionType.SALE,
            quantity_delta=-40,
            unit_cost_price=Decimal("12.50"),
            unit_selling_price=Decimal("22.00"),
            notes="University AI lab bulk purchase",
        ),
    ]

    supplier_repo.save_all(suppliers)
    product_repo.save_all(products)
    tx_repo.save_all(transactions)

if __name__ == "__main__":
    try:
        seed_database()
        print("[SEED OK] Populated suppliers.csv, products.csv, and transactions.csv.", flush=True)
    except InventoryAppError as err:
        print(f"[SEED ERROR] {err}", file=sys.stderr, flush=True)
        sys.exit(1)