"""Unit tests for External API Integration and the AI Inventory Assistant."""

from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch
from inventory_app.models.product import PRODUCT_CSV_FIELDS, Product
from inventory_app.models.transaction import TRANSACTION_CSV_FIELDS, Transaction
from inventory_app.repositories.csv_repo import CSVRepository
from inventory_app.services.ai_assistant import InventoryAssistant
from inventory_app.services.api_service import ExchangeRateAPIService
from inventory_app.services.inventory_service import InventoryService
from inventory_app.services.sales_service import SalesService


@patch("inventory_app.services.api_service.requests.get")
def test_exchange_rate_api_conversion(mock_get: MagicMock) -> None:
    """Verify live currency conversion math using a mocked REST API response."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "result": "success",
        "rates": {"USD": 1.0, "NGN": 1550.50, "EUR": 0.92},
    }
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    api = ExchangeRateAPIService(timeout_seconds=3.0)
    converted = api.convert_price(
        amount=Decimal("10.00"), from_currency="USD", to_currency="NGN"
    )
    assert converted == Decimal("15505.00")


def test_ai_inventory_assistant_queries(tmp_path: Path) -> None:
    """Verify AI Assistant answers restock, best-seller, and summary questions."""
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

    inv_service.add_product(
        Product(
            product_id="PRD-900",
            name="ESP32 Wi-Fi Microcontroller",
            category="Embedded",
            supplier_id="SUP-01",
            quantity=8,
            cost_price=Decimal("4.00"),
            selling_price=Decimal("9.00"),
            min_stock_level=5,
        )
    )
    sales_service.record_sale("PRD-900", quantity=6, notes="Student society bulk buy")

    assistant = InventoryAssistant(
        inventory_service=inv_service, sales_service=sales_service, api_key=""
    )

    restock_answer = assistant.ask("Which products need to be restocked?")
    best_seller_answer = assistant.ask("What were my best-selling products?")
    summary_answer = assistant.ask("Give me a summary of this month's sales.")

    assert "PRD-900" in restock_answer
    assert "PRD-900" in best_seller_answer
    assert "54.00" in summary_answer  # 6 units * $9.00 = $54.00 revenue

def test_zero_unimplemented_stubs_remain_in_production_code() -> None:
    """Scan all source files in src/inventory_app to ensure no NotImplementedError stubs remain."""
    src_root = Path(__file__).resolve().parent.parent / "src" / "inventory_app"
    offending_files: list[str] = []

    for py_file in src_root.rglob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        if "NotImplementedError" in content:
            offending_files.append(str(py_file.relative_to(src_root)))

    assert not offending_files, (
        f"Leftover NotImplementedError stubs found in: {', '.join(offending_files)}"
    )