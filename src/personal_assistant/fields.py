"""Fields of contacts and notes; each one checks its value when created."""

import re
from abc import ABC, abstractmethod
from datetime import date, datetime
from typing import Generic, TypeVar

from personal_assistant.errors import ValidationError

T = TypeVar("T")


class Field(ABC, Generic[T]):
    """Base class of all fields: subclasses check the value in parse()."""

    def __init__(self, raw: str) -> None:
        self.value: T = self.parse(raw)

    @abstractmethod
    def parse(self, raw: str) -> T:
        """Return the cleaned-up value or raise ValidationError."""

    def __str__(self) -> str:
        return str(self.value)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, type(self)) and self.value == other.value

    def __hash__(self) -> int:
        return hash((type(self), self.value))


class TextField(Field[str]):
    """Free text without extra spaces; must not be empty or too long."""

    LABEL: str
    MAX_LENGTH: int

    def parse(self, raw: str) -> str:
        """Collapse spaces; check that the text is not empty or too long."""
        text = " ".join(raw.split())
        if not text:
            raise ValidationError(f"{self.LABEL} cannot be empty.")
        if len(text) > self.MAX_LENGTH:
            raise ValidationError(
                f"{self.LABEL} is too long (maximum {self.MAX_LENGTH})."
            )
        return text


class Name(TextField):
    """Contact name."""

    LABEL = "Name"
    MAX_LENGTH = 50


class Address(TextField):
    """Postal address."""

    LABEL = "Address"
    MAX_LENGTH = 120


class NoteText(TextField):
    """Text of a note."""

    LABEL = "Note text"
    MAX_LENGTH = 1000


class Phone(Field[str]):
    """Ukrainian phone number, stored as +380XXXXXXXXX."""

    _PATTERN = re.compile(r"(?:\+?380|0)([0-9]{9})")

    def parse(self, raw: str) -> str:
        """Accept +380..., 380... or 0..., with spaces, dashes or brackets."""
        match = self._PATTERN.fullmatch(re.sub(r"[\s()-]", "", raw))
        if match is None:
            raise ValidationError(
                f"Invalid phone number '{raw}'. "
                "Use +380XXXXXXXXX, 380XXXXXXXXX or 0XXXXXXXXX."
            )
        return "+380" + match.group(1)


class Email(Field[str]):
    """E-mail address such as name@example.com."""

    _PATTERN = re.compile(r"[\w.+-]+@([\w-]+\.)+[A-Za-z]{2,}")

    def parse(self, raw: str) -> str:
        """Check the name@domain.tld shape."""
        email = raw.strip()
        if not self._PATTERN.fullmatch(email):
            raise ValidationError(
                f"Invalid email '{email}'. Use the form name@example.com."
            )
        return email


class Birthday(Field[date]):
    """Birthday written as DD.MM.YYYY, from 1900 up to today."""

    FORMAT = "%d.%m.%Y"

    def parse(self, raw: str) -> date:
        """Parse the date and check that it is between 1900 and today."""
        try:
            born = datetime.strptime(raw.strip(), self.FORMAT).date()
        except ValueError:
            raise ValidationError(
                f"Invalid birthday '{raw}'. Use a real date as DD.MM.YYYY."
            ) from None
        if not date(1900, 1, 1) <= born <= date.today():
            raise ValidationError("Birthday must be between 1900 and today.")
        return born

    def __str__(self) -> str:
        return self.value.strftime(self.FORMAT)


class Tag(Field[str]):
    """Note tag: one word, stored in lower case without '#'."""

    _PATTERN = re.compile(r"[\w-]+")

    def parse(self, raw: str) -> str:
        """Drop a leading '#', lower the case and check it is one word."""
        tag = raw.strip().lstrip("#").lower()
        if not self._PATTERN.fullmatch(tag):
            raise ValidationError(f"Invalid tag '{raw}'. Use one word: #work.")
        return tag

    def __str__(self) -> str:
        return f"#{self.value}"
