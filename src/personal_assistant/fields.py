"""Validated value objects (fields) used by contacts and notes.

A field is immutable: it normalizes and validates the raw text once,
in the constructor, and raises ValidationError when the text breaks
the rules. Changing a value means creating a new field object, so an
edit always runs exactly the same checks as a new entry.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from datetime import date, datetime
from typing import Generic, TypeVar

from personal_assistant.errors import ValidationError

T = TypeVar("T")

# NUL, ESC and similar characters would corrupt the terminal output.
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")


def shorten(text: object, limit: int = 40) -> str:
    """Return ``text`` cut to ``limit`` characters for messages."""
    value = str(text)
    if len(value) <= limit:
        return value
    cut = limit - 1
    return value[:cut] + "…"


class Field(ABC, Generic[T]):
    """Base class of every field (the template method pattern).

    Subclasses implement :meth:`parse`, which turns raw user text into
    the stored value; the base class provides comparison, hashing and
    printing for all of them.
    """

    def __init__(self, raw: str) -> None:
        self._value: T = self.parse(raw)

    @property
    def value(self) -> T:
        """The normalized, validated value."""
        return self._value

    @abstractmethod
    def parse(self, raw: str) -> T:
        """Normalize and validate ``raw`` or raise ValidationError."""

    def __str__(self) -> str:
        return str(self._value)

    def __repr__(self) -> str:
        return f"{type(self).__name__}({str(self)!r})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Field):
            return NotImplemented
        return type(self) is type(other) and self._value == other._value

    def __hash__(self) -> int:
        return hash((type(self).__name__, self._value))


class TextField(Field[str]):
    """Free text: trimmed, inner whitespace collapsed, length-limited."""

    label = "Text"
    max_length = 100

    def parse(self, raw: str) -> str:
        """Collapse whitespace; check emptiness, length and characters."""
        text = " ".join(str(raw).split())
        if not text:
            raise ValidationError(f"{self.label} cannot be empty.")
        if len(text) > self.max_length:
            raise ValidationError(
                f"{self.label} is too long: {len(text)} characters "
                f"(maximum {self.max_length})."
            )
        if _CONTROL_CHARS.search(text):
            raise ValidationError(
                f"{self.label} cannot contain control characters."
            )
        return text


class Name(TextField):
    """Contact name; any characters that people really use are allowed."""

    label = "Name"
    max_length = 50


class Address(TextField):
    """Postal address as free text."""

    label = "Address"
    max_length = 120


class NoteText(TextField):
    """Text of a note."""

    label = "Note text"
    max_length = 1000


class Phone(Field[str]):
    """Ukrainian phone number, always stored as ``+380XXXXXXXXX``."""

    FORMATS = "+380XXXXXXXXX, 380XXXXXXXXX or 0XXXXXXXXX"
    _SEPARATORS = re.compile(r"[\s\-.()]")
    _PATTERN = re.compile(r"(?:\+?380|0)([0-9]{9})")

    def parse(self, raw: str) -> str:
        """Drop separators and convert any accepted form to +380."""
        compact = self._SEPARATORS.sub("", str(raw))
        match = self._PATTERN.fullmatch(compact)
        if match is None:
            raise ValidationError(
                f"Invalid phone number '{shorten(raw)}'. Use {self.FORMATS};"
                " spaces, dashes, dots and brackets are allowed."
            )
        return "+380" + match.group(1)

    @property
    def local(self) -> str:
        """The number in the domestic form, e.g. ``0671234567``."""
        return "0" + self.value[4:]


class Email(Field[str]):
    """E-mail address; the domain part is stored in lower case."""

    MAX_LENGTH = 254
    _LOCAL = (
        r"[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+"
        r"(?:\.[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+)*"
    )
    _DOMAIN = (
        r"(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+"
        r"[A-Za-z]{2,63}"
    )
    _PATTERN = re.compile(_LOCAL + "@" + _DOMAIN)

    def parse(self, raw: str) -> str:
        """Check the ``name@domain.tld`` shape and the total length."""
        email = str(raw).strip()
        if len(email) > self.MAX_LENGTH or not self._PATTERN.fullmatch(email):
            raise ValidationError(
                f"Invalid email '{shorten(email)}'. "
                "Expected something like name@example.com."
            )
        local, domain = email.rsplit("@", 1)
        return f"{local}@{domain.lower()}"


class Birthday(Field[date]):
    """Date of birth written as ``DD.MM.YYYY``; never in the future."""

    FORMAT = "%d.%m.%Y"
    MIN_YEAR = 1900
    _PATTERN = re.compile(r"[0-9]{2}\.[0-9]{2}\.[0-9]{4}")

    def parse(self, raw: str) -> date:
        """Parse a real calendar date between 1900 and today."""
        text = str(raw).strip()
        if not self._PATTERN.fullmatch(text):
            raise ValidationError(
                f"Invalid birthday '{shorten(text)}'. "
                "Use DD.MM.YYYY, e.g. 24.08.1991."
            )
        try:
            born = datetime.strptime(text, self.FORMAT).date()
        except ValueError:
            raise ValidationError(
                f"Invalid birthday '{text}': there is no such date."
            ) from None
        if born.year < self.MIN_YEAR:
            raise ValidationError(
                f"Birthday year must be {self.MIN_YEAR} or later."
            )
        if born > date.today():
            raise ValidationError("Birthday cannot be in the future.")
        return born

    def __str__(self) -> str:
        return self.value.strftime(self.FORMAT)


class Tag(Field[str]):
    """Note keyword: one word, stored without '#' and in lower case."""

    MAX_LENGTH = 30
    # A letter or digit first, then letters, digits, '-' or '_'.
    _PATTERN = re.compile(r"[^\W_][\w-]*")

    def parse(self, raw: str) -> str:
        """Drop a leading '#', lower the case and check the characters."""
        tag = str(raw).strip().lstrip("#").casefold()
        if not tag:
            raise ValidationError("Tag cannot be empty.")
        if len(tag) > self.MAX_LENGTH:
            raise ValidationError(
                f"Tag is too long (maximum {self.MAX_LENGTH} characters)."
            )
        if not self._PATTERN.fullmatch(tag):
            raise ValidationError(
                f"Invalid tag '{shorten(raw)}'. Use one word of letters, "
                "digits, '-' or '_', e.g. #work."
            )
        return tag

    def __str__(self) -> str:
        return f"#{self.value}"
