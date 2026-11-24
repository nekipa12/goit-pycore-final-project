"""The installed command, run from other folders with piped input."""

import os
import shutil
import subprocess
import sysconfig

from personal_assistant.storage import DATA_DIR_ENV

# The console script that "pip install" puts next to the interpreter.
COMMAND = shutil.which(
    "personal-assistant", path=sysconfig.get_path("scripts")
)


def run_cli(data_dir, cwd, stdin):
    assert COMMAND, "Install the package first: pip install -e ."
    env = {
        **os.environ,
        DATA_DIR_ENV: str(data_dir),
        "PYTHONIOENCODING": "utf-8",
    }
    return subprocess.run(
        [COMMAND],
        input=stdin,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        cwd=cwd,
        timeout=60,
    )


def test_data_survives_a_restart_from_another_folder(tmp_path):
    data = tmp_path / "data"
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    result = run_cli(
        data, first, "add-contact Мар'яна phone=067 123 45 67\nexit\n"
    )
    assert result.returncode == 0, result.stderr
    assert "Contact 'Мар'яна' added." in result.stdout
    result = run_cli(data, second, "search-contacts мар'яна\nexit\n")
    assert "+380671234567" in result.stdout
    # Nothing is written to the folder the program was started from.
    assert list(first.iterdir()) == []
    assert list(second.iterdir()) == []


def test_end_of_input_without_exit_quits_cleanly(tmp_path):
    result = run_cli(tmp_path / "data", tmp_path, "help\n")
    assert result.returncode == 0
    assert "Goodbye!" in result.stdout
    assert "Traceback" not in result.stdout + result.stderr


def test_bad_input_never_crashes(tmp_path):
    lines = [
        "",
        "   ",
        "nonsense",
        'add-contact "unclosed',
        "add-contact",
        "add-contact Anna phone=1",
        "birthdays -5",
        "birthdays 99999999999999999999",
        "delete-note #abc",
        "search-contacts (",
        "search-notes [",
        "add-contact [/]",
        "delete-contact Nobody",
        "edit-contact Nobody email=x@y.zz",
        "add-tag 1 bad tag!",
        "exit",
    ]
    result = run_cli(tmp_path / "data", tmp_path, "\n".join(lines) + "\n")
    assert result.returncode == 0
    assert "Traceback" not in result.stdout + result.stderr
    assert "Goodbye!" in result.stdout


def test_broken_data_file_stops_start_up_and_is_kept(tmp_path):
    path = tmp_path / "data.json"
    path.write_text("{broken", encoding="utf-8")
    result = run_cli(tmp_path, tmp_path, "exit\n")
    assert result.returncode == 1
    assert "Cannot read" in result.stderr
    assert path.read_text(encoding="utf-8") == "{broken"
