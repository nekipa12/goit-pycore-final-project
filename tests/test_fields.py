"""Validation and normalization of every field (criterion 13)."""

from datetime import date, timedelta

import pytest

from personal_assistant.errors import ValidationError
from personal_assistant.fields import (
    Address,
    Birthday,
    Email,
    Name,
    NoteText,
    Phone,
    Tag,
)


@pytest.mark.parametrize(
    "raw",
    [
        "+380671234567",
        "380671234567",
        "0671234567",
        "067 123 45 67",
        "(067) 123-45-67",
        "  0671234567  ",
    ],
)
def test_phone_accepts_ukrainian_formats(raw):
    assert Phone(raw).value == "+380671234567"


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "12345",
        "067123456",
        "06712345678",
        "+0671234567",
        "+1 202 555 0100",
        "067-123-45-6x",
        "phone",
        "٠٦٧١٢٣٤٥٦٧",
    ],
)
def test_phone_rejects_other_input(raw):
    with pytest.raises(ValidationError, match="Invalid phone number"):
        Phone(raw)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("anna@example.com", "anna@example.com"),
        (" Anna.K+work@Mail.Example.COM ", "Anna.K+work@Mail.Example.COM"),
    ],
)
def test_email_valid(raw, expected):
    assert Email(raw).value == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "anna",
        "anna@",
        "@example.com",
        "anna@example",
        "anna@@example.com",
        "anna@example.c",
        "an na@example.com",
    ],
)
def test_email_invalid(raw):
    with pytest.raises(ValidationError, match="Invalid email"):
        Email(raw)


def test_birthday_is_parsed_and_printed_back():
    birthday = Birthday(" 24.08.1991 ")
    assert birthday.value == date(1991, 8, 24)
    assert str(birthday) == "24.08.1991"


def test_birthday_on_29_february_of_a_leap_year():
    assert Birthday("29.02.2000").value == date(2000, 2, 29)


@pytest.mark.parametrize(
    "raw",
    ["", "1991-08-24", "24/08/1991", "24.08.91", "31.02.2000", "29.02.2023"],
)
def test_birthday_must_be_a_real_date(raw):
    with pytest.raises(ValidationError, match="Use a real date"):
        Birthday(raw)


def test_birthday_must_be_between_1900_and_today():
    tomorrow = date.today() + timedelta(days=1)
    for raw in ["31.12.1899", "01.01.0999", tomorrow.strftime("%d.%m.%Y")]:
        with pytest.raises(ValidationError, match="between 1900 and today"):
            Birthday(raw)


def test_name_is_trimmed_and_inner_spaces_collapsed():
    assert Name("  Anna    Kovalenko ").value == "Anna Kovalenko"


@pytest.mark.parametrize(
    "raw", ["Мар'яна", "Dr. Smith", "Іван (робота)", "O'Neil-Smith"]
)
def test_name_accepts_real_world_names(raw):
    assert Name(raw).value == raw


@pytest.mark.parametrize(
    ("raw", "message"),
    [("", "cannot be empty"), ("   ", "cannot be empty"), ("A" * 51, "long")],
)
def test_name_invalid(raw, message):
    with pytest.raises(ValidationError, match=message):
        Name(raw)


def test_address_and_note_text_lengths():
    assert Address("x" * 120).value == "x" * 120
    assert NoteText("x" * 1000).value == "x" * 1000
    with pytest.raises(ValidationError, match="Address is too long"):
        Address("x" * 121)
    with pytest.raises(ValidationError, match="Note text is too long"):
        NoteText("x" * 1001)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("work", "work"),
        ("#Work", "work"),
        ("  РОБОТА ", "робота"),
        ("to-do", "to-do"),
    ],
)
def test_tag_is_normalized(raw, expected):
    assert Tag(raw).value == expected


@pytest.mark.parametrize("raw", ["", "#", "two words", "tag!"])
def test_tag_invalid(raw):
    with pytest.raises(ValidationError, match="Invalid tag"):
        Tag(raw)


def test_fields_compare_by_type_and_value():
    assert Phone("0671234567") == Phone("+380671234567")
    assert Name("Kyiv") != Address("Kyiv")
    assert len({Tag("work"), Tag("#WORK")}) == 1
    assert str(Tag("work")) == "#work"
