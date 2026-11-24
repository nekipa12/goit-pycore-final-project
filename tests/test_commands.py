"""Commands as the user types them, run through the assistant loop."""

import io
import json
from datetime import date, timedelta

import pytest
from rich.console import Console

from personal_assistant.cli import Assistant
from personal_assistant.commands import COMMANDS
from personal_assistant.contacts import AddressBook
from personal_assistant.errors import StorageError
from personal_assistant.notes import NoteBook
from personal_assistant.storage import Storage


@pytest.fixture
def app(tmp_path):
    console = Console(file=io.StringIO(), width=200)
    return Assistant(Storage(tmp_path), AddressBook(), NoteBook(), console)


def run(app, line):
    app.console.file = io.StringIO()
    assert app.execute(line) is True
    return app.console.file.getvalue()


def saved(app):
    return json.loads(app.storage.path.read_text(encoding="utf-8"))


def test_add_contact_with_all_fields(app):
    out = run(
        app,
        "add-contact Anna Kovalenko phone=067 123 45 67 "
        "email=anna@example.com birthday=24.11.1990 "
        "address=Kyiv, Khreshchatyk St 1",
    )
    assert "Contact 'Anna Kovalenko' added." in out
    out = run(app, "contacts")
    for text in [
        "Anna Kovalenko",
        "+380671234567",
        "anna@example.com",
        "24.11.1990",
        "Kyiv, Khreshchatyk St 1",
    ]:
        assert text in out
    # Saved right away, without waiting for "exit".
    assert saved(app)["contacts"][0]["name"] == "Anna Kovalenko"


def test_invalid_field_adds_nothing(app):
    out = run(app, "add-contact Anna phone=123")
    assert "Invalid phone number '123'" in out
    assert "Invalid email" in run(app, "add-contact Anna email=anna@")
    assert len(app.context.book) == 0


def test_phone_typed_without_field_name_gets_a_hint(app):
    out = run(app, "add-contact Anna 0671234567")
    assert "looks like a phone number" in out
    assert "phone=0671234567" in out
    assert len(app.context.book) == 0


def test_edit_contact_changes_all_or_nothing(app):
    run(app, "add-contact Anna email=anna@example.com address=Kyiv")
    out = run(app, "edit-contact Anna email=bad name=Olena")
    assert "Invalid email" in out
    assert app.context.book.find("Anna").email.value == "anna@example.com"
    out = run(app, "edit-contact Anna email=new@example.com address=")
    assert "updated" in out
    anna = app.context.book.find("Anna")
    assert anna.email.value == "new@example.com"
    assert anna.address is None
    run(app, "edit-contact Anna name=Anna Petrenko")
    assert app.context.book.find("anna petrenko") is anna


def test_phone_commands(app):
    run(app, "add-contact Anna Kovalenko phone=0671234567")
    assert "added to Anna Kovalenko" in run(
        app, "add-phone Anna Kovalenko 050-123-45-67"
    )
    assert "changed to +380631234567" in run(
        app, "edit-phone Anna Kovalenko 0501234567 0631234567"
    )
    assert "removed" in run(app, "remove-phone Anna Kovalenko 0631234567")
    out = run(app, "remove-phone Anna Kovalenko 0631234567")
    assert "has no phone +380631234567" in out


def test_search_contacts(app):
    run(app, "add-contact Anna phone=0671234567 email=anna@example.com")
    run(app, "add-contact Bohdan email=bohdan@gmail.com")
    assert "Anna" in run(app, "search-contacts 067 123")
    out = run(app, "search-contacts email=gmail")
    assert "Bohdan" in out and "Anna" not in out
    assert "No contacts match 'zzz'." in run(app, "search-contacts zzz")


def test_delete_contact(app):
    run(app, "add-contact Anna")
    assert "Contact 'Anna' deleted." in run(app, "delete-contact anna")
    assert saved(app)["contacts"] == []
    assert "No contacts yet." in run(app, "contacts")


def test_birthdays(app):
    soon = date.today() + timedelta(days=3)
    run(app, f"add-contact Anna birthday={soon:%d.%m}.2000")
    out = run(app, "birthdays")
    assert "Anna" in out
    assert f"{soon:%d.%m.%Y}" in out and f"{soon:%A}" in out
    assert "No birthdays in the next 2 days." in run(app, "birthdays 2")


@pytest.mark.parametrize("days", ["-1", "abc", "1.5", "366", "99999999999"])
def test_birthdays_rejects_bad_numbers(app, days):
    assert "Days must be a whole number" in run(app, f"birthdays {days}")


def test_notes_and_tags(app):
    assert "No notes yet." in run(app, "notes")
    out = run(app, 'add-note Call Мар\'яна about the "big" trip')
    assert "Note #1 added." in out
    assert 'Call Мар\'яна about the "big" trip' in run(app, "notes")
    run(app, "add-note Prepare the report")
    assert "Added #work #urgent" in run(app, "add-tag 2 Work urgent")
    assert "already has these tags" in run(app, "add-tag 2 #work")
    out = run(app, "search-tags work")
    assert "Prepare the report" in out and "Мар'яна" not in out
    out = run(app, "notes-by-tag")
    assert out.index("Prepare the report") < out.index("Мар'яна")
    assert "Removed #urgent" in run(app, "remove-tag 2 urgent")
    run(app, "edit-note 1 Call Мар'яна tomorrow")
    assert "tomorrow" in run(app, "search-notes мар'яна")
    assert "Note #1 deleted." in run(app, "delete-note #1")
    assert [note["id"] for note in saved(app)["notes"]] == [2]


@pytest.mark.parametrize(
    ("line", "message"),
    [
        ("add-contakt Anna", "Did you mean 'add-contact'?"),
        ("add-phone Anna", "Usage: add-phone <name> <phone>"),
        ("exit now", "Usage: exit"),
        ("delete-note x", "Note ID must be a number"),
        ("delete-note 42", "Note #42 not found."),
        ('add-contact "Anna', "double quote is not closed"),
        ("add-contact Anna foo=bar", "Unknown field 'foo'"),
        ("delete-contact Nobody", "Contact 'Nobody' not found."),
        ("search-notes", "Usage: search-notes <text>"),
        ("search-tags bad!", "Invalid tag"),
        ("add-contact", "Usage: add-contact <name>"),
        ("edit-contact Anna", "Usage: edit-contact <name>"),
        ("search-contacts anna email=x", "Usage: search-contacts"),
        ("search-contacts email=", "Usage: search-contacts"),
        ("search-notes zzz", "No notes match 'zzz'."),
        ("search-tags zzz", "No notes with #zzz."),
        ("notes-by-tag", "No notes yet."),
    ],
)
def test_wrong_input_and_empty_results_are_explained(app, line, message):
    assert message in run(app, line)


def test_blank_line_does_nothing(app):
    assert run(app, "   ") == ""


def test_text_is_printed_literally(app):
    run(app, "add-contact [red]Anna[/]")
    assert "[red]Anna[/]" in run(app, "contacts")
    run(app, "add-note :fire: [bold]drill[/]")
    assert ":fire: [bold]drill[/]" in run(app, "notes")


def test_help_lists_every_command(app):
    out = run(app, "help")
    for name in COMMANDS:
        assert name in out


def test_exit_stops_the_loop(app):
    assert app.execute("exit") is False


def test_unexpected_error_does_not_stop_the_loop(app, monkeypatch):
    def broken(*args, **kwargs):
        raise RuntimeError("boom")

    run(app, "add-contact Anna")
    monkeypatch.setattr(app.context.book, "sorted_contacts", broken)
    assert "Unexpected error: RuntimeError('boom')" in run(app, "contacts")
    assert "Contact 'Bohdan' added." in run(app, "add-contact Bohdan")


def test_failed_save_is_reported(app, monkeypatch):
    def failing_save(book, notes):
        raise StorageError("Cannot save data.json: disk full")

    monkeypatch.setattr(app.storage, "save", failing_save)
    assert "disk full" in run(app, "add-contact Anna")
    assert len(app.context.book) == 1
