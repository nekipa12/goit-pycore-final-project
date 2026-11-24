"""Contacts and the address book."""

from __future__ import annotations

import re
from collections import UserDict
from datetime import date
from typing import Any

from personal_assistant.errors import DuplicateError, NotFoundError
from personal_assistant.fields import (
    Address,
    Birthday,
    Email,
    Field,
    Name,
    Phone,
)

# Fields that search can be limited to, e.g. "search-contacts email=gmail".
SEARCH_FIELDS = ("name", "phone", "email", "birthday", "address")

# Optional single-value fields and the classes that check them.
OPTIONAL_FIELDS: dict[str, type[Field[Any]]] = {
    "email": Email,
    "birthday": Birthday,
    "address": Address,
}


def anniversary(born: date, year: int) -> date:
    """Return the birthday in ``year``; 29 Feb moves to 1 Mar if needed."""
    try:
        return born.replace(year=year)
    except ValueError:
        # Only 29 February fails, and only in a non-leap year.
        return date(year, 3, 1)


class Contact:
    """A person, composed of Name, Phone, Email, Birthday and Address."""

    def __init__(self, name: str) -> None:
        self.name = Name(name)
        self.phones: list[Phone] = []
        self.email: Email | None = None
        self.birthday: Birthday | None = None
        self.address: Address | None = None

    @staticmethod
    def make_field(key: str, raw: str) -> Field[Any] | None:
        """Check an optional field value; a blank value means "none"."""
        return OPTIONAL_FIELDS[key](raw) if raw.strip() else None

    def set_field(self, key: str, raw: str) -> None:
        """Set or clear (with a blank value) email, birthday or address."""
        setattr(self, key, self.make_field(key, raw))

    def add_phone(self, raw: str) -> Phone:
        """Add a phone number; the same number cannot be added twice."""
        phone = Phone(raw)
        if phone in self.phones:
            raise DuplicateError(f"{self.name} already has phone {phone}.")
        self.phones.append(phone)
        return phone

    def find_phone(self, raw: str) -> Phone:
        """Return the stored phone equal to ``raw`` (in any format)."""
        phone = Phone(raw)
        if phone not in self.phones:
            raise NotFoundError(f"{self.name} has no phone {phone}.")
        return phone

    def remove_phone(self, raw: str) -> Phone:
        """Remove a phone number and return it."""
        phone = self.find_phone(raw)
        self.phones.remove(phone)
        return phone

    def edit_phone(self, old: str, new: str) -> Phone:
        """Replace phone ``old`` with ``new``, keeping its place."""
        index = self.phones.index(self.find_phone(old))
        phone = Phone(new)
        if phone in self.phones and self.phones[index] != phone:
            raise DuplicateError(f"{self.name} already has phone {phone}.")
        self.phones[index] = phone
        return phone

    def next_birthday(self, today: date) -> date | None:
        """Return the date of the next birthday on or after ``today``."""
        if self.birthday is None:
            return None
        upcoming = anniversary(self.birthday.value, today.year)
        if upcoming < today:
            upcoming = anniversary(self.birthday.value, today.year + 1)
        return upcoming

    def matches(self, query: str, field: str | None = None) -> bool:
        """Check whether any field (or only ``field``) contains ``query``.

        Letter case does not matter. For phones, spaces, dashes and
        brackets in the query are ignored, so "067 123" finds 0671234567.
        """
        texts = {
            "name": self.name.value,
            "phone": " ".join(phone.value for phone in self.phones),
            "email": self.email.value if self.email else "",
            "birthday": str(self.birthday) if self.birthday else "",
            "address": self.address.value if self.address else "",
        }
        needle = query.strip().lower()
        for key, text in texts.items():
            if field is not None and key != field:
                continue
            target = needle
            if key == "phone":
                target = re.sub(r"[\s()-]", "", needle)
            if target and target in text.lower():
                return True
        return False

    def to_dict(self) -> dict[str, Any]:
        """Convert the contact to JSON-ready data."""
        return {
            "name": self.name.value,
            "phones": [phone.value for phone in self.phones],
            "email": self.email.value if self.email else None,
            "birthday": str(self.birthday) if self.birthday else None,
            "address": self.address.value if self.address else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Contact:
        """Rebuild a contact from saved data, checking every field again."""
        contact = cls(data["name"])
        for phone in data["phones"]:
            contact.add_phone(phone)
        for key in OPTIONAL_FIELDS:
            contact.set_field(key, data[key] or "")
        return contact


class AddressBook(UserDict[str, Contact]):
    """All contacts, keyed by the name in lower case."""

    def add(self, contact: Contact) -> None:
        """Add a new contact; names are unique regardless of case."""
        key = contact.name.value.lower()
        if key in self.data:
            raise DuplicateError(f"Contact '{contact.name}' already exists.")
        self.data[key] = contact

    def find(self, name: str) -> Contact:
        """Return the contact called ``name`` (in any letter case)."""
        try:
            return self.data[Name(name).value.lower()]
        except KeyError:
            raise NotFoundError(f"Contact '{name}' not found.") from None

    def delete(self, name: str) -> Contact:
        """Remove the contact called ``name`` and return it."""
        contact = self.find(name)
        del self.data[contact.name.value.lower()]
        return contact

    def rename(self, contact: Contact, new_name: str) -> None:
        """Give ``contact`` a new name that no other contact has."""
        name = Name(new_name)
        old_key = contact.name.value.lower()
        new_key = name.value.lower()
        if new_key != old_key and new_key in self.data:
            raise DuplicateError(f"Contact '{name}' already exists.")
        del self.data[old_key]
        contact.name = name
        self.data[new_key] = contact

    def sorted_contacts(self) -> list[Contact]:
        """Return all contacts sorted by name."""
        return sorted(self.data.values(), key=lambda c: c.name.value.lower())

    def search(self, query: str, field: str | None = None) -> list[Contact]:
        """Return the contacts matching ``query``, sorted by name."""
        return [c for c in self.sorted_contacts() if c.matches(query, field)]

    def upcoming_birthdays(
        self, days: int, today: date
    ) -> list[tuple[Contact, date]]:
        """Return contacts whose birthday is within ``days`` days.

        The window includes both ends: ``days=0`` means today only,
        ``days=7`` means today and the next seven days. The result is
        a list of (contact, birthday date) pairs sorted by date.
        """
        upcoming: list[tuple[Contact, date]] = []
        for contact in self.data.values():
            birthday = contact.next_birthday(today)
            if birthday is not None and (birthday - today).days <= days:
                upcoming.append((contact, birthday))
        upcoming.sort(key=lambda item: (item[1], item[0].name.value.lower()))
        return upcoming

    def to_dict(self) -> dict[str, Any]:
        """Convert the book to JSON-ready data."""
        return {"contacts": [c.to_dict() for c in self.sorted_contacts()]}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AddressBook:
        """Rebuild the book from saved data, checking every contact."""
        book = cls()
        for item in data["contacts"]:
            book.add(Contact.from_dict(item))
        return book
