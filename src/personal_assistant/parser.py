"""Splitting typed lines into words and ``field=value`` pairs."""

import re
import shlex
from collections.abc import Sequence

from personal_assistant.errors import UsageError

_FIELD = re.compile(r"([A-Za-z]+)=(.*)", re.DOTALL)


def split_line(line: str) -> list[str]:
    """Split a line into words.

    Double quotes group words ("Anna Kovalenko"). Apostrophes are
    ordinary letters, so names such as Mar'yana need no quotes, and
    '#' and backslashes are kept exactly as typed.
    """
    lexer = shlex.shlex(line, posix=True)
    lexer.whitespace_split = True
    lexer.quotes = '"'
    lexer.escape = ""
    lexer.commenters = ""
    try:
        return list(lexer)
    except ValueError:
        raise UsageError(
            'A double quote is not closed. Example: add-contact "Anna K."'
        ) from None


def parse_fields(
    words: Sequence[str], allowed: Sequence[str]
) -> tuple[list[str], list[tuple[str, str]]]:
    """Split words into the leading words and ``field=value`` pairs.

    A value runs until the next ``field=``, so quotes are optional:
    ``Anna Kovalenko phone=067 123 45 67 address=Kyiv, Main St 1``
    gives ``["Anna", "Kovalenko"]`` and the pairs ("phone",
    "067 123 45 67") and ("address", "Kyiv, Main St 1"). Field names
    ignore case; an empty value (``email=``) is kept as "".
    """
    head: list[str] = []
    fields: list[tuple[str, str]] = []
    for word in words:
        match = _FIELD.fullmatch(word)
        if match:
            key = match.group(1).casefold()
            if key not in allowed:
                names = ", ".join(f"{name}=" for name in allowed)
                raise UsageError(f"Unknown field '{key}'. Use: {names}")
            fields.append((key, match.group(2)))
        elif fields:
            key, value = fields[-1]
            fields[-1] = (key, f"{value} {word}".strip())
        else:
            head.append(word)
    return head, fields
