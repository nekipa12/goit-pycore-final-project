"""Tables for the assistant's output, drawn with rich.

Values go into the tables as Text, which rich prints exactly as it is:
a contact called "[red]" is not read as rich markup.
"""

from collections.abc import Iterable
from datetime import date, timedelta

from rich.table import Table
from rich.text import Text

from personal_assistant.contacts import Contact
from personal_assistant.notes import Note


def cell(value: object) -> Text:
    """Return a value as literal text; None becomes an empty cell."""
    return Text("" if value is None else str(value))


def table(title: str, *columns: str) -> Table:
    """Create an empty table; long values wrap instead of being cut."""
    result = Table(title=Text(title))
    for column in columns:
        result.add_column(column, overflow="fold")
    return result


def contacts_table(
    contacts: Iterable[Contact], title: str = "Contacts"
) -> Table:
    """Show contacts as a table, one row per contact."""
    result = table(title, "Name", "Phones", "Email", "Birthday", "Address")
    for contact in contacts:
        result.add_row(
            cell(contact.name),
            cell("\n".join(str(phone) for phone in contact.phones)),
            cell(contact.email),
            cell(contact.birthday),
            cell(contact.address),
        )
    return result


def birthdays_table(
    rows: Iterable[tuple[Contact, date]], today: date, days: int
) -> Table:
    """Show upcoming birthdays with their date and day of the week."""
    last = today + timedelta(days=days)
    result = table(
        f"Birthdays from {today:%d.%m.%Y} to {last:%d.%m.%Y}",
        "Name",
        "Born",
        "Birthday",
        "Weekday",
    )
    for contact, day in rows:
        result.add_row(
            cell(contact.name),
            cell(contact.birthday),
            cell(f"{day:%d.%m.%Y}"),
            cell(f"{day:%A}"),
        )
    return result


def notes_table(notes: Iterable[Note], title: str = "Notes") -> Table:
    """Show notes as a table, one row per note."""
    result = table(title, "ID", "Note", "Tags")
    for note in notes:
        tags = " ".join(str(tag) for tag in note.tags)
        result.add_row(cell(note.id), cell(note.text), cell(tags))
    return result


def help_table(commands: Iterable[tuple[str, str]]) -> Table:
    """Show the usage line and the description of every command."""
    result = table("Commands", "Usage", "What it does")
    for usage, description in commands:
        result.add_row(cell(usage), cell(description))
    return result
