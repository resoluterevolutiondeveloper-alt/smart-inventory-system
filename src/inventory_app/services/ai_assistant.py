import json
from typing import Any, Dict, List
from google import genai
from inventory_app.exceptions import ExternalServiceError, ValidationError
from inventory_app.models.product import Product
from inventory_app.services.inventory_service import InventoryService
from inventory_app.services.sales_service import SalesService


class InventoryAssistant:
    """Provides intelligent inventory analysis, trend detection, and restock recommendations."""

    def __init__(
        self,
        inventory_service: InventoryService,
        sales_service: SalesService,
        api_key: str = "",
        model_name: str = "gemini-2.5-flash",
    ) -> None:
        self._inventory = inventory_service
        self._sales = sales_service
        self._api_key = api_key.strip()
        self._model_name = model_name
        self._client = genai.Client(api_key=self._api_key) if self._api_key else None

    def generate_restock_recommendations(self) -> List[str]:
        """Analyze low-stock products and compute recommended reorder quantities.

        Rule: For every product in `self._inventory.get_low_stock_products()`,
        recommend ordering `max(10, (prod.min_stock_level * 2) - prod.quantity)` units.
        """
        low_stock_items: List[Product] = self._inventory.get_low_stock_products()
        if not low_stock_items:
            return ["All products are adequately stocked above minimum thresholds."]

        recommendations: List[str] = []
        for prod in low_stock_items:
            reorder_qty = max(10, (prod.min_stock_level * 2) - prod.quantity)
            recommendations.append(
                f"RESTOCK ALERT: {prod.name} ({prod.product_id}) has {prod.quantity} left (Min: {prod.min_stock_level}). Recommended order: {reorder_qty} units."
            )
        return recommendations

    def build_analytics_snapshot(self) -> Dict[str, Any]:
        """Compile real-time inventory and sales telemetry for AI context injection."""
        summary = self._sales.get_financial_summary()
        best_sellers = self._sales.get_best_selling_products(top_n=5)
        declining = self._sales.get_declining_products()
        low_stock = self._inventory.get_low_stock_products()

        return {
            "low_stock_products": [
                {
                    "product_id": p.product_id,
                    "name": p.name,
                    "quantity": p.quantity,
                    "min_stock_level": p.min_stock_level,
                }
                for p in low_stock
            ],
            "best_selling_products": [
                {"product_id": pid, "units_sold": units, "revenue": str(rev)}
                for pid, units, rev in best_sellers
            ],
            "declining_products": [
                {"product_id": pid, "previous_units": prev, "current_units": curr}
                for pid, prev, curr in declining
            ],
            "financial_summary": {
                "total_units_sold": summary.total_units_sold,
                "total_revenue": str(summary.total_revenue),
                "total_cogs": str(summary.total_cogs),
                "estimated_profit": str(summary.estimated_profit),
            },
            "restock_recommendations": self.generate_restock_recommendations(),
        }

    def ask(self, question: str) -> str:
        """Answer natural-language inventory questions using AI or deterministic fallback."""
        cleaned_q = question.strip()
        if not cleaned_q:
            raise ValidationError("Question to Inventory Assistant cannot be empty.")

        snapshot = self.build_analytics_snapshot()

        if self._client is not None:
            prompt = (
                "You are the Smart Inventory Assistant. Answer the user's question "
                "concisely and accurately using ONLY the following JSON store telemetry:\n"
                f"{json.dumps(snapshot, indent=2)}\n\n"
                f"User Question: {cleaned_q}"
            )
            try:
                response = self._client.models.generate_content(
                    model=self._model_name,
                    contents=prompt,
                )
                if response.text:
                    return response.text.strip()
            except Exception as exc:
                raise ExternalServiceError(f"AI Assistant query failed: {exc}") from exc

        # Deterministic local intelligence when offline or running without an API key
        q_lower = cleaned_q.lower()
        if "restock" in q_lower or "low" in q_lower:
            return "\n".join(snapshot["restock_recommendations"])
        if "best" in q_lower or "top" in q_lower:
            sellers = snapshot["best_selling_products"]
            if not sellers:
                return "No sales have been recorded yet."
            return "Best-Selling Products: " + ", ".join(
                f"{s['product_id']} ({s['units_sold']} units, ${s['revenue']})"
                for s in sellers
            )
        if "declin" in q_lower or "drop" in q_lower:
            dec = snapshot["declining_products"]
            if not dec:
                return "No products have experienced declining sales in the current window."
            return "Declining Products: " + ", ".join(
                f"{d['product_id']} (dropped from {d['previous_units']} to {d['current_units']} units)"
                for d in dec
            )
        fin = snapshot["financial_summary"]
        return (
            f"Sales Summary: {fin['total_units_sold']} units sold | "
            f"Revenue: ${fin['total_revenue']} | COGS: ${fin['total_cogs']} | "
            f"Estimated Profit: ${fin['estimated_profit']}"
        )