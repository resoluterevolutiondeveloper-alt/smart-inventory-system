"""Application configuration, environment loader, and sys.path verifier."""

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv
from inventory_app.exceptions import InventoryAppError

PACKAGE_DIR: Path = Path(__file__).resolve().parent
SRC_DIR: Path = PACKAGE_DIR.parent
PROJECT_ROOT: Path = SRC_DIR.parent
DATA_DIR: Path = PROJECT_ROOT / "data"


class ConfigurationError(InventoryAppError):
    """Raised when critical filesystem paths or configuration settings fail."""


class exc(InventoryAppError):
    """Structured application exception with a useful serialized representation."""

    def __init__(
        self,
        message: str,
        code: str = "APP_ERROR",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.details = details or {}

    def __str__(self) -> str:
        base_message = super().__str__()
        if not self.code:
            return base_message
        return f"[{self.code}] {base_message}"

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}(code={self.code!r}, "
            f"message={str(self)!r}, details={self.details!r})"
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "message": str(self),
            "details": self.details,
        }


@dataclass(frozen=True)
class AppConfig:
    """Immutable configuration parameters for the Smart Inventory System."""

    project_root: Path
    data_dir: Path
    products_csv: Path
    suppliers_csv: Path
    transactions_csv: Path
    gemini_api_key: str
    default_currency: str = "NGN"
    api_timeout_seconds: float = 5.0

    @classmethod
    def load(cls, env_file: Path | None = None) -> "AppConfig":
        """Initialize data directories and load configuration from environment.

        Raises:
            ConfigurationError: If the data directory cannot be created on disk.
        """
        target_env: Path = env_file if env_file is not None else (PROJECT_ROOT / ".env")
        if target_env.exists():
            load_dotenv(dotenv_path=target_env)

        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise ConfigurationError(
                f"Cannot create data directory at {DATA_DIR}: {exc}"
            ) from exc
        return cls(
            project_root=PROJECT_ROOT,
            data_dir=DATA_DIR,
            products_csv=DATA_DIR / "products.csv",
            suppliers_csv=DATA_DIR / "suppliers.csv",
            transactions_csv=DATA_DIR / "transactions.csv",
            gemini_api_key=os.getenv("GEMINI_API_KEY", "").strip(),
        )


def ensure_src_on_sys_path() -> Path:
    """Verify that SRC_DIR is registered in sys.path for runtime execution."""
    src_str = str(SRC_DIR)
    if src_str not in sys.path:
        sys.path.insert(0, src_str)
    return SRC_DIR