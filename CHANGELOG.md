# Changelog

All notable changes to this project are documented here. The format
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the
project uses [Semantic Versioning](https://semver.org/).

## [1.0.0] - 2026-11-24

### Added

- Contacts with a name, several phone numbers, email, birthday and
  address: add, list, search (all fields or one), edit and delete.
- `birthdays [days]`: birthdays from today up to N days ahead.
- Validation of every field on create and on edit, with clear messages.
- Notes with IDs: add, list, search, edit and delete.
- Tags on notes: add, remove, search by several tags, notes sorted by tag.
- Storage in `~/.personal_assistant/data.json`, saved after every change;
  a file that cannot be read stops the program and is never overwritten.
- Interactive loop with `help`, Tab completion of command names and typo
  suggestions.
- Installable package with the `personal-assistant` command.
- Tests, linting (ruff, flake8), type checking (mypy) and GitHub Actions CI.

[1.0.0]: https://github.com/nekipa12/goit-pycore-final-project/releases/tag/v1.0.0
