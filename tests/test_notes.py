"""Notes, tags, search and sorting by tags."""

import pytest

from personal_assistant.errors import NotFoundError, ValidationError
from personal_assistant.fields import Tag
from personal_assistant.notes import Note, NoteBook


def test_new_note_gets_the_next_id():
    notes = NoteBook()
    assert notes.add("one").id == 1
    assert notes.add("two").id == 2
    notes.delete(1)
    assert notes.add("three").id == 3


def test_round_trip_through_dict():
    notes = NoteBook()
    notes.add("one").add_tags(["work"])
    notes.add("two")
    restored = NoteBook.from_dict(notes.to_dict())
    assert restored.to_dict() == notes.to_dict()


def test_edit_replaces_text_and_keeps_old_text_on_error():
    note = Note(1, "first")
    note.edit("  second   version ")
    assert note.text.value == "second version"
    with pytest.raises(ValidationError):
        note.edit("")
    assert note.text.value == "second version"


def test_tags_are_normalized_deduplicated_and_sorted():
    note = Note(1, "text")
    added = note.add_tags(["Work", "#work", "urgent"])
    assert [tag.value for tag in added] == ["work", "urgent"]
    assert [tag.value for tag in note.tags] == ["urgent", "work"]
    assert note.add_tags(["WORK"]) == []


def test_one_bad_tag_adds_nothing():
    note = Note(1, "text", ["home"])
    with pytest.raises(ValidationError):
        note.add_tags(["ok", "bad tag!"])
    assert [tag.value for tag in note.tags] == ["home"]


def test_remove_tags_requires_every_tag_to_exist():
    note = Note(1, "text", ["home", "work"])
    with pytest.raises(NotFoundError):
        note.remove_tags(["home", "missing"])
    assert [tag.value for tag in note.tags] == ["home", "work"]
    note.remove_tags(["#HOME"])
    assert [tag.value for tag in note.tags] == ["work"]


@pytest.fixture
def notes():
    result = NoteBook()
    result.add("Buy milk").add_tags(["shopping", "home"])
    result.add("Prepare the Q4 report").add_tags(["work", "urgent"])
    result.add("Call Мар'яна about the trip").add_tags(["family"])
    result.add("Read a book")
    result.add("Deploy on Friday").add_tags(["work"])
    return result


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("milk", [1]),
        ("REPORT", [2]),
        ("мар'яна", [3]),
        ("#work", [2, 5]),
        ("shop", [1]),
        ("nothing", []),
    ],
)
def test_search_looks_at_text_and_tags(notes, query, expected):
    assert [note.id for note in notes.search(query)] == expected


def test_search_by_tags_requires_all_tags(notes):
    found = notes.search_by_tags([Tag("work"), Tag("urgent")])
    assert [note.id for note in found] == [2]
    found = notes.search_by_tags([Tag("work")])
    assert [note.id for note in found] == [2, 5]


def test_sorted_by_tags_puts_untagged_notes_last(notes):
    # Tags of each note: 1 [home, shopping], 2 [urgent, work],
    # 3 [family], 4 [], 5 [work].
    assert [note.id for note in notes.sorted_by_tags()] == [3, 1, 2, 5, 4]


def test_missing_note():
    with pytest.raises(NotFoundError, match="Note #7 not found."):
        NoteBook().find(7)
