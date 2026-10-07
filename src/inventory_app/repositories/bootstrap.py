# bootstrap.py
"""Deterministic workspace initializer for the Smart Inventory Management System."""

import sys
from pathlib import Path
from typing import Sequence


class WorkspaceBootstrapError(RuntimeError):
    """Raised when filesystem provisioning fails due to OS permission or I/O errors."""


PROJECT_DIRECTORIES: Sequence[str] = (
    "data",
    "tests",
    "scripts",
    "src/inventory_app/models",
    "src/inventory_app/repositories",
    "src/inventory_app/services",
    "src/inventory_app/ui/views",
    "src/inventory_app/ui/components",
)

PROJECT_FILES: Sequence[str] = (
    ".gitignore",
    ".env.example",
    "pyproject.toml",
    "tests/__init__.py",
    "tests/test_models.py",
    "src/inventory_app/__init__.py",
    "src/inventory_app/config.py",
    "src/inventory_app/exceptions.py",
    "src/inventory_app/models/__init__.py",
    "src/inventory_app/models/product.py",
    "src/inventory_app/models/supplier.py",
    "src/inventory_app/models/transaction.py",
    "src/inventory_app/repositories/__init__.py",
    "src/inventory_app/repositories/csv_repo.py",
    "src/inventory_app/services/__init__.py",
    "src/inventory_app/services/inventory_service.py",
    "src/inventory_app/services/sales_service.py",
    "src/inventory_app/services/api_service.py",
    "src/inventory_app/services/ai_assistant.py",
    "src/inventory_app/ui/__init__.py",
    "src/inventory_app/ui/app_window.py",
    "src/inventory_app/ui/views/__init__.py",
    "src/inventory_app/ui/components/__init__.py",
)


def initialize_project_structure(root_dir: Path) -> None:
    """Create all required packages, directories, and module files idempotently.

    Args:
        root_dir: The canonical root directory of the project.

    Raises:
        WorkspaceBootstrapError: If directory or file creation fails.
    """
    try:
        for relative_dir in PROJECT_DIRECTORIES:
            dir_path: Path = root_dir / relative_dir
            dir_path.mkdir(parents=True, exist_ok=True)

        for relative_file in PROJECT_FILES:
            file_path: Path = root_dir / relative_file
            file_path.touch(exist_ok=True)

    except OSError as exc:
        raise WorkspaceBootstrapError(
            f"OS I/O failure while provisioning workspace at {root_dir}: {exc}"
        ) from exc


if __name__ == "__main__":
    current_root: Path = Path(__file__).resolve().parent
    print(f"[INFO] Bootstrapping project in: {current_root}", flush=True)
    try:
        initialize_project_structure(current_root)
        print(
            f"[BOOTSTRAP OK] Provisioned {len(PROJECT_DIRECTORIES)} directories "
            f"and {len(PROJECT_FILES)} files successfully.",
            flush=True,
        )
    except WorkspaceBootstrapError as err:
        print(f"[FATAL] {err}", file=sys.stderr, flush=True)
        sys.exit(1)