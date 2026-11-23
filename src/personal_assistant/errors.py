"""Errors that the assistant reports to the user as plain messages."""


class AssistantError(Exception):
    """Base class for expected problems with a user-facing message."""


class ValidationError(AssistantError):
    """A value does not follow the rules of its field."""


class NotFoundError(AssistantError):
    """A contact, phone, note or tag does not exist."""


class DuplicateError(AssistantError):
    """The same contact, phone or tag already exists."""


class UsageError(AssistantError):
    """A command was typed with wrong arguments.

    Raised without a message, it means "show the usage of the command".
    """


class StorageError(AssistantError):
    """The data files cannot be read or written."""
