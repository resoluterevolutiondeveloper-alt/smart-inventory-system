"""Custom domain exception hierarchy for the Smart Inventory System."""


class InventoryAppError(Exception):
    """Base exception for all application errors."""


class ValidationError(InventoryAppError, ValueError):
    """Raised when domain entity validation or CSV parsing fails."""


class InsufficientStockError(InventoryAppError):
    """Raised when a sale or stock-out exceeds available quantity."""


class DuplicateProductError(InventoryAppError):
    """Raised when registering a product ID that already exists."""


class StorageWriteError(InventoryAppError):
    """Raised when atomic CSV file persistence fails."""


class ExternalServiceError(InventoryAppError):
    """Raised when an external API or AI request fails."""