"""Validated value objects (fields) used by contacts and notes.

A field is immutable: it normalizes and validates the raw text once,
in the constructor, and raises ValidationError when the text breaks
the rules. Changing a value means creating a new field object, so an
edit always runs exactly the same checks as a new entry.
"""

import re
from abc import ABC, abstractmethod
from datetime import date, datetime
from typing import Generic, TypeVar

from personal_assistant.errors import ValidationError

T = TypeVar("T")

# NUL, ESC and similar characters would corrupt the terminal output.
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")

# The longest piece of user input repeated in an error message.
_SHOWN_LENGTH = 40


def shorten(text: object) -> str:
    """Return ``text`` cut to 40 characters for messages."""
    value = str(text)
    if len(value) <= _SHOWN_LENGTH:
        return value
    cut = _SHOWN_LENGTH - 1
    return value[:cut] + "…"


class Field(ABC, Generic[T]):
    """Base class of every field (the template method pattern).

    Subclasses implement :meth:`parse`, which turns raw user text into
    the stored value; the base class checks that the input is text and
    provides comparison, hashing and printing for all of them.
    """

    def __init__(self, raw: str) -> None:
        # Data read from a damaged file may hold None, numbers or lists.
        if not isinstance(raw, str):
            raise ValidationError(
                f"{type(self).__name__} must be text, "
                f"not {type(raw).__name__}."
            )
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

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Field):
            return NotImplemented
        return type(self) is type(other) and self._value == other._value

    def __hash__(self) -> int:
        return hash((type(self).__name__, self._value))


class TextField(Field[str]):
    """Free text: trimmed, inner whitespace collapsed, length-limited.

    Subclasses set ``LABEL`` (used in messages) and ``MAX_LENGTH``.
    """

    LABEL: str
    MAX_LENGTH: int

    def parse(self, raw: str) -> str:
        """Collapse whitespace; check emptiness, length and characters."""
        text = " ".join(raw.split())
        if not text:
            raise ValidationError(f"{self.LABEL} cannot be empty.")
        if len(text) > self.MAX_LENGTH:
            raise ValidationError(
                f"{self.LABEL} is too long: {len(text)} characters "
                f"(maximum {self.MAX_LENGTH})."
            )
        if _CONTROL_CHARS.search(text):
            raise ValidationError(
                f"{self.LABEL} cannot contain control characters."
            )
        return text


class Name(TextField):
    """Contact name; any characters that people really use are allowed."""

    LABEL = "Name"
    MAX_LENGTH = 50


class Address(TextField):
    """Postal address as free text."""

    LABEL = "Address"
    MAX_LENGTH = 120


class NoteText(TextField):
    """Text of a note."""

    LABEL = "Note text"
    MAX_LENGTH = 1000


class Phone(Field[str]):
    """Ukrainian phone number, always stored as ``+380XXXXXXXXX``."""

    _SEPARATORS = re.compile(r"[\s\-.()]")
    _PATTERN = re.compile(r"(?:\+?380|0)([0-9]{9})")

    def parse(self, raw: str) -> str:
        """Drop separators and convert any accepted form to +380."""
        match = self._PATTERN.fullmatch(self._SEPARATORS.sub("", raw))
        if match is None:
            raise ValidationError(
                f"Invalid phone number '{shorten(raw)}'. Use +380XXXXXXXXX, "
                "380XXXXXXXXX or 0XXXXXXXXX; spaces, dashes, dots and "
                "brackets are allowed."
            )
        return "+380" + match.group(1)

    @property
    def local(self) -> str:
        """The number in the domestic form, e.g. ``0671234567``."""
        return "0" + self.value[4:]


class Email(Field[str]):
    """E-mail address; the domain part is stored in lower case."""

    MAX_LENGTH = 254
    _PATTERN = re.compile(
        # The name: allowed characters in dot-separated parts.
        r"[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+"
        r"(?:\.[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+)*"
        r"@"
        # The domain: labels of up to 63 characters, then a top level.
        r"(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+"
        r"[A-Za-z]{2,63}"
    )

    def parse(self, raw: str) -> str:
        """Check the ``name@domain.tld`` shape and the total length."""
        email = raw.strip()
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
        text = raw.strip()
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
        tag = raw.strip().lstrip("#").casefold()
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
