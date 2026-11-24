"""Saving and loading the data file."""

from pathlib import Path

import pytest

from personal_assistant.contacts import AddressBook, Contact
from personal_assistant.errors import StorageError
from personal_assistant.notes import NoteBook
from personal_assistant.storage import DATA_DIR_ENV, Storage, default_data_dir


def sample_data():
    book = AddressBook()
    olena = Contact("Олена Мар'янівна")
    olena.add_phone("067 123 45 67")
    olena.set_field("email", "olena@example.com")
    olena.set_field("birthday", "29.02.2000")
    olena.set_field("address", "Київ, вул. Хрещатик, 1")
    book.add(olena)
    notes = NoteBook()
    notes.add("Купити подарунок").add_tags(["родина", "gift"])
    notes.delete(notes.add("temporary").id)
    return book, notes


def test_round_trip_keeps_everything(tmp_path):
    book, notes = sample_data()
    Storage(tmp_path / "new").save(book, notes)
    loaded_book, loaded_notes = Storage(tmp_path / "new").load()
    assert loaded_book.to_dict() == book.to_dict()
    assert loaded_notes.to_dict() == notes.to_dict()
    # Cyrillic is stored as readable UTF-8, not as \u escapes.
    text = (tmp_path / "new" / "data.json").read_text(encoding="utf-8")
    assert "Олена" in text


def test_missing_file_means_empty_books(tmp_path):
    book, notes = Storage(tmp_path).load()
    assert len(book) == 0
    assert len(notes) == 0


def test_default_data_dir(monkeypatch, tmp_path):
    monkeypatch.delenv(DATA_DIR_ENV, raising=False)
    assert default_data_dir() == Path.home() / ".personal_assistant"
    monkeypatch.setenv(DATA_DIR_ENV, str(tmp_path))
    assert default_data_dir() == tmp_path


@pytest.mark.parametrize(
    "content",
    [
        "",
        "{not json",
        "[]",
        '{"contacts": []}',
        '{"contacts": [{"name": "A", "phones": ["1"]}], "notes": []}',
    ],
)
def test_broken_file_is_reported_and_kept(tmp_path, content):
    path = tmp_path / "data.json"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(StorageError, match="Cannot read"):
        Storage(tmp_path).load()
    assert path.read_text(encoding="utf-8") == content


def test_failed_save_keeps_the_old_file(tmp_path, monkeypatch):
    book, notes = sample_data()
    storage = Storage(tmp_path)
    storage.save(book, notes)
    before = storage.path.read_text(encoding="utf-8")

    def broken_replace(*args, **kwargs):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(Path, "replace", broken_replace)
    with pytest.raises(StorageError, match="No space left"):
        storage.save(AddressBook(), NoteBook())
    assert storage.path.read_text(encoding="utf-8") == before
