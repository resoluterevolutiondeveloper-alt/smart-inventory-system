"""Application composition root and entry point."""

from inventory_app.config import AppConfig, ensure_src_on_sys_path
from inventory_app.models.product import PRODUCT_CSV_FIELDS, Product
from inventory_app.models.transaction import TRANSACTION_CSV_FIELDS, Transaction
from inventory_app.repositories.csv_repo import CSVRepository
from inventory_app.services.ai_assistant import InventoryAssistant
from inventory_app.services.api_service import ExchangeRateAPIService
from inventory_app.services.inventory_service import InventoryService
from inventory_app.services.sales_service import SalesService
from inventory_app.ui.app_window import InventoryAppWindow


def main() -> None:
    """Initialize configuration, repositories, services, and launch the Tkinter GUI."""
    ensure_src_on_sys_path()
    config = AppConfig.load()

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

    inv_service = InventoryService(product_repo=product_repo, transaction_repo=tx_repo)
    sales_service = SalesService(inventory_service=inv_service)
    api_service = ExchangeRateAPIService(timeout_seconds=config.api_timeout_seconds)
    ai_assistant = InventoryAssistant(
        inventory_service=inv_service,
        sales_service=sales_service,
        api_key=config.gemini_api_key
    )
    app = InventoryAppWindow(
        inv_service,
        sales_service,
        api_service,
        ai_assistant
    )
    app.mainloop()


if __name__ == "__main__":
    main()