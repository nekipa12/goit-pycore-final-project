"""Saving and loading the data as one JSON file in the home folder.

The file is ``~/.personal_assistant/data.json``; the environment
variable ``PERSONAL_ASSISTANT_DATA_DIR`` names another folder, e.g. for
tests or a demo. A save writes a temporary file and then puts it in
place of the old one in one step, so a crash never leaves half a file.
"""

import json
import os
from pathlib import Path

from personal_assistant.contacts import AddressBook
from personal_assistant.errors import StorageError
from personal_assistant.notes import NoteBook

DATA_DIR_ENV = "PERSONAL_ASSISTANT_DATA_DIR"


def default_data_dir() -> Path:
    """Return the data folder: ~/.personal_assistant or the override."""
    override = os.environ.get(DATA_DIR_ENV)
    return Path(override) if override else Path.home() / ".personal_assistant"


class Storage:
    """Keeps the address book and the notebook in ``data.json``."""

    def __init__(self, data_dir: Path) -> None:
        self.path = data_dir / "data.json"

    def load(self) -> tuple[AddressBook, NoteBook]:
        """Read the data; with no file yet, both books start empty."""
        if not self.path.exists():
            return AddressBook(), NoteBook()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return AddressBook.from_dict(data), NoteBook.from_dict(data)
        except Exception as error:  # any problem here means a broken file
            # Stop instead of starting empty and overwriting the file.
            raise StorageError(
                f"Cannot read {self.path}: {error!r}. "
                "Fix the file or move it away, then start again."
            ) from error

    def save(self, book: AddressBook, notes: NoteBook) -> None:
        """Write the data to a temporary file, then put it in place."""
        data = {**book.to_dict(), **notes.to_dict()}
        text = json.dumps(data, ensure_ascii=False, indent=2)
        temp = self.path.with_suffix(".tmp")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temp.write_text(text, encoding="utf-8")
            temp.replace(self.path)
        except OSError as error:
            raise StorageError(f"Cannot save {self.path}: {error}") from error
