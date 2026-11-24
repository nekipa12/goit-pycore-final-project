"""Contacts, the address book, search and birthdays."""

from datetime import date

import pytest

from personal_assistant.contacts import AddressBook, Contact, anniversary
from personal_assistant.errors import (
    DuplicateError,
    NotFoundError,
    ValidationError,
)

TODAY = date(2026, 11, 23)  # a Monday; 2026 and 2027 are not leap years


def contact(name, birthday=None, phones=(), email=None, address=None):
    item = Contact(name)
    for phone in phones:
        item.add_phone(phone)
    if birthday:
        item.set_field("birthday", birthday)
    if email:
        item.set_field("email", email)
    if address:
        item.set_field("address", address)
    return item


def test_anniversary_moves_29_february_in_non_leap_years():
    assert anniversary(date(2000, 2, 29), 2027) == date(2027, 3, 1)
    assert anniversary(date(2000, 2, 29), 2028) == date(2028, 2, 29)


def test_phones_are_added_edited_and_removed():
    anna = contact("Anna", phones=["0671234567"])
    anna.add_phone("+380501234567")
    anna.edit_phone("067 123 45 67", "0631234567")
    assert [p.value for p in anna.phones] == [
        "+380631234567",
        "+380501234567",
    ]
    anna.remove_phone("0501234567")
    assert [p.value for p in anna.phones] == ["+380631234567"]


def test_same_phone_in_another_format_is_a_duplicate():
    anna = contact("Anna", phones=["0671234567"])
    with pytest.raises(DuplicateError):
        anna.add_phone("+38 (067) 123-45-67")


def test_failed_phone_edit_changes_nothing():
    anna = contact("Anna", phones=["0671234567", "0501234567"])
    with pytest.raises(ValidationError):
        anna.edit_phone("0671234567", "123")
    with pytest.raises(DuplicateError):
        anna.edit_phone("0671234567", "0501234567")
    with pytest.raises(NotFoundError):
        anna.remove_phone("0991234567")
    assert [p.value for p in anna.phones] == [
        "+380671234567",
        "+380501234567",
    ]


def test_optional_field_can_be_cleared():
    anna = contact("Anna", email="anna@example.com")
    anna.set_field("email", "")
    assert anna.email is None


def test_names_are_unique_ignoring_case():
    book = AddressBook()
    book.add(Contact("Anna"))
    with pytest.raises(DuplicateError):
        book.add(Contact("ANNA"))
    assert book.find("aNNa").name.value == "Anna"
    with pytest.raises(NotFoundError, match="not found"):
        book.find("Bohdan")


def test_rename_moves_the_key_and_rejects_duplicates():
    book = AddressBook()
    anna = Contact("Anna")
    book.add(anna)
    book.add(Contact("Bohdan"))
    with pytest.raises(DuplicateError):
        book.rename(anna, "bohdan")
    book.rename(anna, "Anna Petrenko")
    assert book.find("anna petrenko") is anna
    with pytest.raises(NotFoundError):
        book.find("Anna")


def test_delete():
    book = AddressBook()
    book.add(Contact("Anna"))
    book.delete("ANNA")
    assert len(book) == 0


@pytest.fixture
def book():
    result = AddressBook()
    result.add(
        contact(
            "Anna Kovalenko",
            phones=["0671234567"],
            email="anna@example.com",
            address="Kyiv, Khreshchatyk St 1",
        )
    )
    result.add(contact("Bohdan", email="bohdan@gmail.com", address="Lviv"))
    result.add(contact("Олена", birthday="05.03.1985"))
    return result


@pytest.mark.parametrize(
    ("query", "field", "expected"),
    [
        ("anna", None, ["Anna Kovalenko"]),
        ("067 123", None, ["Anna Kovalenko"]),
        ("+380671", None, ["Anna Kovalenko"]),
        ("LVIV", None, ["Bohdan"]),
        ("ОЛЕНА", None, ["Олена"]),
        ("05.03", None, ["Олена"]),
        ("gmail", "email", ["Bohdan"]),
        ("anna", "address", []),
        ("o", "name", ["Anna Kovalenko", "Bohdan"]),
    ],
)
def test_search(book, query, field, expected):
    found = book.search(query, field)
    assert [item.name.value for item in found] == expected


@pytest.fixture
def birthday_book():
    result = AddressBook()
    for name, born in [
        ("Today", "23.11.1990"),
        ("Tomorrow", "24.11.1990"),
        ("Week", "30.11.1990"),
        ("Eight", "01.12.1990"),
        ("NewYear", "01.01.1990"),
        ("Leap", "29.02.2000"),
        ("Yesterday", "22.11.1990"),
    ]:
        result.add(contact(name, birthday=born))
    result.add(Contact("NoBirthday"))
    return result


@pytest.mark.parametrize(
    ("days", "expected"),
    [
        (0, ["Today"]),
        (1, ["Today", "Tomorrow"]),
        (7, ["Today", "Tomorrow", "Week"]),
        (39, ["Today", "Tomorrow", "Week", "Eight", "NewYear"]),
        (98, ["Today", "Tomorrow", "Week", "Eight", "NewYear", "Leap"]),
        (
            365,
            [
                "Today",
                "Tomorrow",
                "Week",
                "Eight",
                "NewYear",
                "Leap",
                "Yesterday",
            ],
        ),
    ],
)
def test_upcoming_birthdays_window_includes_both_ends(
    birthday_book, days, expected
):
    upcoming = birthday_book.upcoming_birthdays(days, TODAY)
    assert [item.name.value for item, _ in upcoming] == expected


def test_upcoming_birthdays_give_the_real_dates(birthday_book):
    upcoming = dict(
        (item.name.value, day)
        for item, day in birthday_book.upcoming_birthdays(365, TODAY)
    )
    assert upcoming["Today"] == date(2026, 11, 23)
    assert upcoming["NewYear"] == date(2027, 1, 1)
    assert upcoming["Leap"] == date(2027, 3, 1)
    assert upcoming["Yesterday"] == date(2027, 11, 22)


def test_round_trip_through_dict(book):
    restored = AddressBook.from_dict(book.to_dict())
    assert restored.to_dict() == book.to_dict()


def test_from_dict_validates_again():
    data = {"contacts": [{"name": "Anna", "phones": ["123"]}]}
    with pytest.raises(ValidationError):
        AddressBook.from_dict(data)
