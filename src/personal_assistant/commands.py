"""The commands of the assistant, registered by name in ``COMMANDS``.

A handler gets the shared Context and the words typed after the command
name. It returns a message or a table, or raises an AssistantError that
the loop in cli.py prints. An error without a message means "wrong
arguments", and the loop prints the usage line of the command instead.
"""

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date
from typing import TypeAlias

from rich.table import Table

from personal_assistant import views
from personal_assistant.contacts import SEARCH_FIELDS, AddressBook, Contact
from personal_assistant.errors import UsageError, ValidationError
from personal_assistant.fields import Name, Phone, Tag
from personal_assistant.notes import NoteBook
from personal_assistant.parser import parse_fields

CONTACT_FIELDS = ("phone", "email", "birthday", "address")
EDIT_FIELDS = ("name", "email", "birthday", "address")
DEFAULT_DAYS = 7
MAX_DAYS = 365
NO_NOTES = "No notes yet. Add one with: add-note <text>"

# Up to nine digits: no sign, no spaces, no huge numbers.
_NUMBER = re.compile(r"[0-9]{1,9}")


@dataclass
class Context:
    """The data that the commands work with."""

    book: AddressBook
    notes: NoteBook


Handler: TypeAlias = Callable[[Context, list[str]], str | Table]


@dataclass
class Command:
    """A command: its usage line, its handler and how to run it."""

    usage: str
    handler: Handler
    changes_data: bool
    exits: bool
    # Note commands get their text exactly as typed, quotes included:
    # the first ``free_text`` words, then the rest of the line as one.
    free_text: int | None


COMMANDS: dict[str, Command] = {}


def command(
    usage: str,
    *,
    changes_data: bool = False,
    exits: bool = False,
    free_text: int | None = None,
) -> Callable[[Handler], Handler]:
    """Register the decorated function as the command named in ``usage``."""

    def register(handler: Handler) -> Handler:
        name = usage.split()[0]
        COMMANDS[name] = Command(
            usage, handler, changes_data, exits, free_text
        )
        return handler

    return register


def expect(
    args: Sequence[str], minimum: int, maximum: int | None = None
) -> None:
    """Raise a UsageError if the number of arguments is wrong."""
    if len(args) < minimum or (maximum is not None and len(args) > maximum):
        raise UsageError()


def join_name(words: Sequence[str]) -> str:
    """Join the words of a contact name; quotes around it are optional."""
    if not words:
        raise UsageError()
    return " ".join(words)


def parse_days(raw: str) -> int:
    """Parse the number of days for the birthdays command."""
    if not _NUMBER.fullmatch(raw) or int(raw) > MAX_DAYS:
        raise ValidationError(
            f"Days must be a whole number from 0 to {MAX_DAYS}, not '{raw}'."
        )
    return int(raw)


def parse_note_id(raw: str) -> int:
    """Parse a note ID written as 3 or #3."""
    text = raw.removeprefix("#")
    if not _NUMBER.fullmatch(text):
        raise ValidationError(
            f"Note ID must be a number such as 3, not '{raw}'."
        )
    return int(text)


def is_phone(word: str) -> bool:
    """Check whether a word is a valid phone number."""
    try:
        Phone(word)
    except ValidationError:
        return False
    return True


# --- Contacts -------------------------------------------------------------


@command(
    "add-contact <name> [phone=<phone>]... [email=<email>] "
    "[birthday=<DD.MM.YYYY>] [address=<address>]",
    changes_data=True,
)
def add_contact(ctx: Context, args: list[str]) -> str:
    """Add a contact; only the name is required."""
    words, fields = parse_fields(args, CONTACT_FIELDS)
    for word in words:
        # The habit from "add Anna 0671234567" would make it a name.
        if is_phone(word):
            raise UsageError(
                f"'{word}' looks like a phone number. Write it as phone={word}"
            )
    contact = Contact(join_name(words))
    for key, value in fields:
        if key == "phone":
            contact.add_phone(value)
        else:
            contact.set_field(key, value)
    ctx.book.add(contact)
    return f"Contact '{contact.name}' added."


@command(
    "edit-contact <name> [name=<new name>] [email=<email>] "
    "[birthday=<DD.MM.YYYY>] [address=<address>]",
    changes_data=True,
)
def edit_contact(ctx: Context, args: list[str]) -> str:
    """Change fields of a contact; an empty value (email=) clears one."""
    words, fields = parse_fields(args, EDIT_FIELDS)
    if not fields:
        raise UsageError()
    contact = ctx.book.find(join_name(words))
    # Check every new value first, so that one bad value changes nothing.
    new_name = None
    for key, value in fields:
        if key == "name":
            new_name = Name(value).value
        else:
            Contact.make_field(key, value)
    if new_name is not None:
        ctx.book.rename(contact, new_name)
    for key, value in fields:
        if key != "name":
            contact.set_field(key, value)
    return f"Contact '{contact.name}' updated."


@command("add-phone <name> <phone>", changes_data=True)
def add_phone(ctx: Context, args: list[str]) -> str:
    """Add one more phone number to a contact."""
    expect(args, 2)
    contact = ctx.book.find(join_name(args[:-1]))
    phone = contact.add_phone(args[-1])
    return f"Phone {phone} added to {contact.name}."


@command("edit-phone <name> <old phone> <new phone>", changes_data=True)
def edit_phone(ctx: Context, args: list[str]) -> str:
    """Replace one phone number of a contact with another."""
    expect(args, 3)
    contact = ctx.book.find(join_name(args[:-2]))
    phone = contact.edit_phone(args[-2], args[-1])
    return f"Phone of {contact.name} changed to {phone}."


@command("remove-phone <name> <phone>", changes_data=True)
def remove_phone(ctx: Context, args: list[str]) -> str:
    """Remove a phone number from a contact."""
    expect(args, 2)
    contact = ctx.book.find(join_name(args[:-1]))
    phone = contact.remove_phone(args[-1])
    return f"Phone {phone} removed from {contact.name}."


@command("contacts")
def list_contacts(ctx: Context, args: list[str]) -> str | Table:
    """List all contacts sorted by name."""
    expect(args, 0, 0)
    if not ctx.book:
        return "No contacts yet. Add one with: add-contact <name>"
    return views.contacts_table(ctx.book.sorted_contacts())


@command("search-contacts <text> | <field>=<text>")
def search_contacts(ctx: Context, args: list[str]) -> str | Table:
    """Find contacts by text in any field or in one chosen field."""
    words, fields = parse_fields(args, SEARCH_FIELDS)
    if (words and fields) or len(fields) > 1:
        raise UsageError()
    field: str | None = None
    query = " ".join(words)
    if fields:
        field, query = fields[0]
    if not query.strip():
        raise UsageError()
    found = ctx.book.search(query, field)
    if not found:
        return f"No contacts match '{query}'."
    return views.contacts_table(found, f"Contacts matching '{query}'")


@command("delete-contact <name>", changes_data=True)
def delete_contact(ctx: Context, args: list[str]) -> str:
    """Delete a contact."""
    contact = ctx.book.delete(join_name(args))
    return f"Contact '{contact.name}' deleted."


# --- Birthdays ------------------------------------------------------------


@command("birthdays [days]")
def birthdays(ctx: Context, args: list[str]) -> str | Table:
    """Show birthdays from today up to N days ahead (7 by default)."""
    expect(args, 0, 1)
    days = parse_days(args[0]) if args else DEFAULT_DAYS
    today = date.today()
    upcoming = ctx.book.upcoming_birthdays(days, today)
    if not upcoming:
        return f"No birthdays in the next {days} days."
    return views.birthdays_table(upcoming, today, days)


# --- Notes ----------------------------------------------------------------


@command("add-note <text>", changes_data=True, free_text=0)
def add_note(ctx: Context, args: list[str]) -> str:
    """Add a note; everything after the command is its text."""
    expect(args, 1, 1)
    note = ctx.notes.add(args[0])
    return f"Note #{note.id} added."


@command("notes")
def list_notes(ctx: Context, args: list[str]) -> str | Table:
    """List all notes."""
    expect(args, 0, 0)
    if not ctx.notes:
        return NO_NOTES
    return views.notes_table(ctx.notes.sorted_notes())


@command("edit-note <id> <new text>", changes_data=True, free_text=1)
def edit_note(ctx: Context, args: list[str]) -> str:
    """Replace the text of a note."""
    expect(args, 2, 2)
    note = ctx.notes.find(parse_note_id(args[0]))
    note.edit(args[1])
    return f"Note #{note.id} updated."


@command("delete-note <id>", changes_data=True)
def delete_note(ctx: Context, args: list[str]) -> str:
    """Delete a note."""
    expect(args, 1, 1)
    note = ctx.notes.delete(parse_note_id(args[0]))
    return f"Note #{note.id} deleted."


@command("search-notes <text>", free_text=0)
def search_notes(ctx: Context, args: list[str]) -> str | Table:
    """Find notes whose text or tags contain the given text."""
    expect(args, 1, 1)
    found = ctx.notes.search(args[0])
    if not found:
        return f"No notes match '{args[0]}'."
    return views.notes_table(found, f"Notes matching '{args[0]}'")


# --- Tags -----------------------------------------------------------------


@command("add-tag <id> <tag> [tag]...", changes_data=True)
def add_tag(ctx: Context, args: list[str]) -> str:
    """Add one or more tags to a note."""
    expect(args, 2)
    note = ctx.notes.find(parse_note_id(args[0]))
    added = note.add_tags(args[1:])
    if not added:
        return f"Note #{note.id} already has these tags."
    tags = " ".join(str(tag) for tag in added)
    return f"Added {tags} to note #{note.id}."


@command("remove-tag <id> <tag> [tag]...", changes_data=True)
def remove_tag(ctx: Context, args: list[str]) -> str:
    """Remove one or more tags from a note."""
    expect(args, 2)
    note = ctx.notes.find(parse_note_id(args[0]))
    removed = note.remove_tags(args[1:])
    tags = " ".join(str(tag) for tag in removed)
    return f"Removed {tags} from note #{note.id}."


@command("search-tags <tag> [tag]...")
def search_tags(ctx: Context, args: list[str]) -> str | Table:
    """Find notes that have all of the given tags."""
    expect(args, 1)
    tags = [Tag(raw) for raw in args]
    label = " ".join(str(tag) for tag in tags)
    found = ctx.notes.search_by_tags(tags)
    if not found:
        return f"No notes with {label}."
    return views.notes_table(found, f"Notes with {label}")


@command("notes-by-tag")
def notes_by_tag(ctx: Context, args: list[str]) -> str | Table:
    """Show notes sorted by tag; notes without tags come last."""
    expect(args, 0, 0)
    if not ctx.notes:
        return NO_NOTES
    return views.notes_table(ctx.notes.sorted_by_tags(), "Notes by tag")


# --- General --------------------------------------------------------------


@command("help")
def show_help(ctx: Context, args: list[str]) -> Table:
    """Show all commands."""
    expect(args, 0, 0)
    return views.help_table(
        (item.usage, item.handler.__doc__ or "") for item in COMMANDS.values()
    )


@command("exit", exits=True)
def exit_assistant(ctx: Context, args: list[str]) -> str:
    """Quit the assistant (every change is already saved)."""
    expect(args, 0, 0)
    return "Goodbye!"
