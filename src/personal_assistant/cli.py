"""The loop that reads and runs commands, and the program's entry point."""

import sys
from collections.abc import Callable
from difflib import get_close_matches

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from rich.console import Console
from rich.table import Table
from rich.text import Text

from personal_assistant.commands import COMMANDS, Context
from personal_assistant.contacts import AddressBook
from personal_assistant.errors import AssistantError, StorageError
from personal_assistant.notes import NoteBook
from personal_assistant.parser import split_line
from personal_assistant.storage import Storage, default_data_dir

PROMPT = "assistant> "


def unknown_command(name: str) -> str:
    """Return the message for an unknown command, with a suggestion."""
    close = get_close_matches(name.lower(), COMMANDS, n=1)
    hint = f" Did you mean '{close[0]}'?" if close else ""
    return f"Unknown command '{name}'.{hint} Type 'help' to see all commands."


class Assistant:
    """Reads commands, runs them and saves the data after every change."""

    def __init__(
        self,
        storage: Storage,
        book: AddressBook,
        notes: NoteBook,
        console: Console,
        read: Callable[[str], str] = input,
    ) -> None:
        self.storage = storage
        self.context = Context(book, notes)
        self.console = console
        self.read = read

    def run(self) -> None:
        """Greet the user and run commands until the exit command."""
        self.show(
            "Personal Assistant: contacts, birthdays and notes.\n"
            f"Data file: {self.storage.path}\n"
            "Type 'help' to see the commands or 'exit' to quit."
        )
        while True:
            try:
                line = self.read(PROMPT)
            except (EOFError, KeyboardInterrupt):
                # Ctrl+D or Ctrl+C: every change is already saved.
                self.show("\nGoodbye!")
                return
            if not self.execute(line):
                return

    def execute(self, line: str) -> bool:
        """Run one command line; return False when it is time to exit."""
        words = line.split(None, 1)
        if not words:
            return True
        command = COMMANDS.get(words[0].lower())
        if command is None:
            self.error(unknown_command(words[0]))
            return True
        rest = words[1] if len(words) > 1 else ""
        try:
            if command.free_text is None:
                args = split_line(rest)
            else:
                args = rest.split(None, command.free_text)
            self.show(command.handler(self.context, args))
            if command.changes_data:
                self.storage.save(self.context.book, self.context.notes)
        except AssistantError as error:
            self.error(str(error) or f"Usage: {command.usage}")
            return True
        except Exception as error:  # a bug must never close the program
            self.error(f"Unexpected error: {error!r}")
            return True
        return not command.exits

    def show(self, output: str | Table) -> None:
        """Print a table, or a message exactly as it is written."""
        self.console.print(Text(output) if isinstance(output, str) else output)

    def error(self, message: str) -> None:
        """Print an error message in red."""
        self.console.print(Text(message, style="red"))


def main() -> None:
    """Load the data and start the assistant."""
    storage = Storage(default_data_dir())
    try:
        book, notes = storage.load()
    except StorageError as error:
        sys.exit(f"personal-assistant: {error}")
    read: Callable[[str], str] = input
    if sys.stdin.isatty() and sys.stdout.isatty():
        # A real terminal: line editing, history and Tab completion.
        completer = WordCompleter(list(COMMANDS), sentence=True)
        session: PromptSession[str] = PromptSession(completer=completer)
        read = session.prompt
    Assistant(storage, book, notes, Console(), read).run()
