from decimal import Decimal
from typing import Dict
import requests
from inventory_app.exceptions import ExternalServiceError, ValidationError


class ExchangeRateAPIService:
    """Communicates with an external REST API to convert supplier costs across currencies."""

    API_URL_TEMPLATE: str = "https://open.er-api.com/v6/latest/{base}"

    def __init__(self, timeout_seconds: float = 5.0) -> None:
        self._timeout: float = timeout_seconds
        self._rates_cache: Dict[str, Dict[str, Decimal]] = {}

    def fetch_rates(self, base_currency: str = "USD") -> Dict[str, Decimal]:
        """Fetch and cache exchange rates for base_currency from the external API.

        Raises:
            ValidationError: If base_currency is empty.
            ExternalServiceError: If the HTTP request fails or returns invalid JSON.
        """
        base = base_currency.strip().upper()
        if not base:
            raise ValidationError("Base currency code cannot be empty.")

        if base in self._rates_cache:
            return self._rates_cache[base]

        url = self.API_URL_TEMPLATE.format(base=base)
        try:
            response = requests.get(url, timeout=self._timeout)
            response.raise_for_status()
            payload = response.json()
            raw_rates = payload.get("rates", {})
            if not raw_rates:
                raise ExternalServiceError(f"Missing 'rates' in API payload from {url}")

            parsed_rates: Dict[str, Decimal] = {
                code.upper(): Decimal(str(rate)) for code, rate in raw_rates.items()
            }
            self._rates_cache[base] = parsed_rates
            return parsed_rates
        except (requests.RequestException, ValueError, KeyError) as exc:
            raise ExternalServiceError(
                f"Failed to retrieve exchange rates from external API: {exc}"
            ) from exc

    def convert_price(
        self, amount: Decimal, from_currency: str, to_currency: str = "NGN"
    ) -> Decimal:
        """Convert a monetary amount from one currency to another using live API rates.

        Raises:
            ValidationError: If amount is negative or target currency is unsupported.
            ExternalServiceError: If the underlying API call fails.
        """
        if amount < Decimal("0.00"):
            raise ValidationError("Cannot convert a negative monetary amount.")

        target = to_currency.strip().upper()
        rates = self.fetch_rates(base_currency=from_currency)

        if target not in rates:
            raise ValidationError(f"Unsupported target currency code: '{target}'")
        target_rate = amount * rates[target]
        return target_rate.quantize(Decimal("0.01"))