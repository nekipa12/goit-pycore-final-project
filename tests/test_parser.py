"""Splitting command lines and field=value pairs."""

import pytest

from personal_assistant.errors import UsageError
from personal_assistant.parser import parse_fields, split_line

FIELDS = ("phone", "email", "birthday", "address")


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("add-contact Мар'яна", ["add-contact", "Мар'яна"]),
        (
            'add-contact "Anna Kovalenko" phone=0671234567',
            ["add-contact", "Anna Kovalenko", "phone=0671234567"],
        ),
        ('address="Kyiv, Main St 1"', ["address=Kyiv, Main St 1"]),
        ("add-tag 1 #work", ["add-tag", "1", "#work"]),
        ("note C:\\temp\\file", ["note", "C:\\temp\\file"]),
        ("  spaced   out  ", ["spaced", "out"]),
        ("", []),
    ],
)
def test_split_line(line, expected):
    assert split_line(line) == expected


def test_unbalanced_double_quote_is_a_usage_error():
    with pytest.raises(UsageError, match="not closed"):
        split_line('add-contact "Anna')


def test_field_values_run_until_the_next_field():
    line = "Anna Kovalenko phone=067 123 45 67 address=Kyiv, Main St"
    head, fields = parse_fields(split_line(line), FIELDS)
    assert head == ["Anna", "Kovalenko"]
    assert fields == [
        ("phone", "067 123 45 67"),
        ("address", "Kyiv, Main St"),
    ]


def test_empty_values_and_field_case():
    head, fields = parse_fields(["Anna", "EMAIL=", "Phone=1"], FIELDS)
    assert head == ["Anna"]
    assert fields == [("email", ""), ("phone", "1")]


def test_unknown_field():
    with pytest.raises(UsageError, match="Unknown field 'foo'"):
        parse_fields(["Anna", "foo=bar"], FIELDS)
