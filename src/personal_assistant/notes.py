"""Notes with tags and the notebook."""

from __future__ import annotations

from collections import UserDict
from collections.abc import Iterable
from typing import Any

from personal_assistant.errors import NotFoundError
from personal_assistant.fields import NoteText, Tag


class Note:
    """A text note with an ID and a sorted list of tags."""

    def __init__(
        self, note_id: int, text: str, tags: Iterable[str] = ()
    ) -> None:
        self.id = note_id
        self.text = NoteText(text)
        self.tags: list[Tag] = []
        self.add_tags(tags)

    def edit(self, text: str) -> None:
        """Replace the text of the note."""
        self.text = NoteText(text)

    def add_tags(self, raw_tags: Iterable[str]) -> list[Tag]:
        """Add tags and return the ones that were not there before."""
        # Check every tag first, so that one bad tag adds nothing.
        tags = [Tag(raw) for raw in raw_tags]
        added: list[Tag] = []
        for tag in tags:
            if tag not in self.tags and tag not in added:
                added.append(tag)
        self.tags = sorted(self.tags + added, key=lambda tag: tag.value)
        return added

    def remove_tags(self, raw_tags: Iterable[str]) -> list[Tag]:
        """Remove tags; every one of them must be on the note."""
        tags = [Tag(raw) for raw in raw_tags]
        for tag in tags:
            if tag not in self.tags:
                raise NotFoundError(f"Note #{self.id} has no tag {tag}.")
        self.tags = [tag for tag in self.tags if tag not in tags]
        return tags

    def matches(self, query: str) -> bool:
        """Check whether the text or a tag contains ``query``."""
        needle = query.strip().lower()
        tag_needle = needle.lstrip("#")
        return needle in self.text.value.lower() or any(
            tag_needle in tag.value for tag in self.tags
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert the note to JSON-ready data."""
        return {
            "id": self.id,
            "text": self.text.value,
            "tags": [tag.value for tag in self.tags],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Note:
        """Rebuild a note from saved data, checking every field again."""
        return cls(data["id"], data["text"], data["tags"])


class NoteBook(UserDict[int, Note]):
    """All notes, keyed by ID."""

    def add(self, text: str) -> Note:
        """Create a note with the next free ID and return it."""
        note = Note(max(self.data, default=0) + 1, text)
        self.data[note.id] = note
        return note

    def find(self, note_id: int) -> Note:
        """Return the note with ``note_id``."""
        try:
            return self.data[note_id]
        except KeyError:
            raise NotFoundError(f"Note #{note_id} not found.") from None

    def delete(self, note_id: int) -> Note:
        """Remove the note with ``note_id`` and return it."""
        note = self.find(note_id)
        del self.data[note_id]
        return note

    def sorted_notes(self) -> list[Note]:
        """Return all notes ordered by ID."""
        return [self.data[note_id] for note_id in sorted(self.data)]

    def search(self, query: str) -> list[Note]:
        """Return the notes whose text or tags contain ``query``."""
        return [note for note in self.sorted_notes() if note.matches(query)]

    def search_by_tags(self, tags: Iterable[Tag]) -> list[Note]:
        """Return the notes that have every one of ``tags``."""
        wanted = list(tags)
        return [
            note
            for note in self.sorted_notes()
            if all(tag in note.tags for tag in wanted)
        ]

    def sorted_by_tags(self) -> list[Note]:
        """Return the notes sorted by their tags; untagged notes go last."""
        return sorted(
            self.sorted_notes(),
            key=lambda note: (not note.tags, [tag.value for tag in note.tags]),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert the notebook to JSON-ready data."""
        return {"notes": [note.to_dict() for note in self.sorted_notes()]}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NoteBook:
        """Rebuild the notebook from saved data, checking every note."""
        book = cls()
        for item in data["notes"]:
            note = Note.from_dict(item)
            book.data[note.id] = note
        return book
