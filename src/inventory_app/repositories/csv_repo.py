import csv
import os
import tempfile
from pathlib import Path
from typing import Callable, Dict, Generic, List, Sequence, TypeVar
from inventory_app.exceptions import InventoryAppError, StorageWriteError

T = TypeVar("T")


class CSVRepository(Generic[T]):
    def __init__(
        self,
        file_path: Path,
        fieldnames: Sequence[str],
        serializer: Callable[[T], Dict[str, str]],
        deserializer: Callable[[Dict[str, str]], T],
    ) -> None:
        self._file_path = file_path
        self._fieldnames = list(fieldnames)
        self._serializer = serializer
        self._deserializer = deserializer
        self._ensure_file_exists()

    def _ensure_file_exists(self) -> None:
        """Create parent directory and header row if the CSV file does not exist."""
        self._file_path.parent.mkdir(parents=True, exist_ok=True)
        if not self._file_path.exists():
            with self._file_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=self._fieldnames)
                writer.writeheader()

    def load_all(self) -> List[T]:
        """Read and deserialize all rows from the CSV file."""
        items: List[T] = []
        try:
            with self._file_path.open("r", encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                for line_number, row in enumerate(reader, start=2):
                    try:
                        items.append(self._deserializer(row))
                    except (KeyError, TypeError, ValueError) as exc:
                        raise InventoryAppError(
                            f"Error deserializing row {line_number} in {self._file_path.name}: {exc}"
                        ) from exc
        except InventoryAppError:
            raise
        except (csv.Error, OSError) as exc:
            raise InventoryAppError(
                f"Failed to read {self._file_path.name}: {exc}"
            ) from exc
        return items

    def save_all(self, items: Sequence[T]) -> None:
        """Atomically write all items to a temporary file and replace target CSV."""
        tmp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="",
                dir=self._file_path.parent,
                delete=False,
                suffix=".tmp",
            ) as tmp_file:
                tmp_path = Path(tmp_file.name)
                writer = csv.DictWriter(tmp_file, fieldnames=self._fieldnames)
                writer.writeheader()
                for item in items:
                    writer.writerow(self._serializer(item))
                tmp_file.flush()
                os.fsync(tmp_file.fileno())

            os.replace(tmp_path, self._file_path)
        except (OSError, csv.Error) as exc:
            if tmp_path is not None and tmp_path.exists():
                tmp_path.unlink(missing_ok=True)
            raise StorageWriteError(
                f"Atomic write failed for {self._file_path.name}: {exc}"
            ) from exc