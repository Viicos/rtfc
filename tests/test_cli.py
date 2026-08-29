import datetime
from pathlib import Path

import pytest

from rtfc._cli import main
from rtfc._entry import Entry

CHANGELOG = """\
Changelog
=========

.. rtfc-insert
"""


@pytest.fixture(autouse=True)
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("EDITOR", raising=False)
    (tmp_path / "rtfc.toml").write_text('[rtfc]\ndirectory = "changelog"\nchangelog = "changelog.rst"')
    (tmp_path / "changelog").mkdir()
    (tmp_path / "changelog.rst").write_text(CHANGELOG)
    return tmp_path


def write_entry(project: Path, nonce: str, *, section: str = "bugfix", content: str = "Fix a bug.") -> Path:
    file = project / "changelog" / f"{nonce}.{section}.rtfc"
    file.write_text(f'+++\ndate = 2025-08-01\nnonce = "{nonce}"\nsection = "{section}"\n+++\n{content}\n')
    return file


def test_check_ok(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    write_entry(project, "abc")

    assert main(["check"]) == 0
    assert "OK: 1 valid entries" in capsys.readouterr().out


def test_check_reports_errors(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (project / "changelog" / "bad.rtfc").write_text("no frontmatter")

    assert main(["check"]) == 1
    assert "bad.rtfc: Entry must start with" in capsys.readouterr().err


def test_check_missing_config(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (project / "rtfc.toml").unlink()

    assert main(["check"]) == 1
    assert "No configuration found" in capsys.readouterr().err


def test_build_dry_run(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    entry = write_entry(project, "abc")

    assert main(["build", "--version", "1.0.0", "--dry-run"]) == 0

    output = capsys.readouterr().out
    assert f"v1.0.0 ({datetime.date.today().isoformat()})" in output
    assert "- Fix a bug." in output
    assert (project / "changelog.rst").read_text() == CHANGELOG
    assert entry.exists()


def test_build_version(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    entry = write_entry(project, "abc")

    assert main(["build", "--version", "1.0.0"]) == 0

    changelog = (project / "changelog.rst").read_text()
    assert f"v1.0.0 ({datetime.date.today().isoformat()})" in changelog
    assert "Bug fixes" in changelog
    assert "- Fix a bug." in changelog
    assert not entry.exists()


def test_build_requires_version(project: Path) -> None:
    with pytest.raises(SystemExit):
        main(["build"])


def test_build_no_entries(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["build", "--version", "1.0.0"]) == 1
    assert "No changelog entries found" in capsys.readouterr().err


def test_new(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["new", "--section", "feature", "--meta", "gh_issue=123", "--content", "Add a feature."]) == 0

    files = list((project / "changelog").glob("*.rtfc"))
    assert len(files) == 1
    entry = Entry.from_file(files[0], sections=("feature", "bugfix"))
    assert entry.date == datetime.date.today()
    assert entry.section == "feature"
    assert entry.metadata == {"gh_issue": 123}
    assert entry.content == "Add a feature."
    assert f"Created {files[0]}" in capsys.readouterr().out


def test_new_placeholder_content(project: Path) -> None:
    assert main(["new"]) == 0

    (file,) = (project / "changelog").glob("*.rtfc")
    entry = Entry.from_file(file, sections=())
    assert entry.section is None
    assert entry.content == "Describe the change."


def test_new_string_meta_value(project: Path) -> None:
    assert main(["new", "--meta", "author=victorien"]) == 0

    (file,) = (project / "changelog").glob("*.rtfc")
    assert Entry.from_file(file, sections=()).metadata == {"author": "victorien"}


def test_new_unknown_section(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        main(["new", "--section", "typo"])
    assert "argument -s/--section: invalid choice: 'typo'" in capsys.readouterr().err


def test_new_help_lists_configured_sections(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (project / "rtfc.toml").write_text('[rtfc]\nchangelog = "changelog.rst"\nsections = ["breaking", "perf"]')

    with pytest.raises(SystemExit):
        main(["new", "--help"])

    assert "--section {breaking,perf}" in capsys.readouterr().out


def test_no_valid_config_fails_early(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (project / "rtfc.toml").unlink()

    assert main(["new", "--help"]) == 1

    assert "No configuration found" in capsys.readouterr().err


def test_new_invalid_meta(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        main(["new", "--meta", "gh_issue"])
    assert "argument --meta: 'gh_issue' is not of the form KEY=VALUE" in capsys.readouterr().err


INTERACTIVE_CONFIG = """\
[rtfc]
directory = "changelog"
changelog = "changelog.rst"

[rtfc.metadata.gh_issue]
type = "integer"
required = true

[rtfc.metadata.author]
type = "string"
default = "unknown"
"""


def interactive(monkeypatch: pytest.MonkeyPatch, responses: list[str]) -> None:
    answers = iter(responses)

    def fake_input(prompt: str = "") -> str:
        try:
            return next(answers)
        except StopIteration:
            raise EOFError from None

    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("builtins.input", fake_input)


def test_new_interactive(project: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    (project / "rtfc.toml").write_text(INTERACTIVE_CONFIG)
    # Unknown section then valid one; invalid gh_issue then valid; author skipped:
    interactive(monkeypatch, ["typo", "feature", "abc", "123", ""])

    assert main(["new", "--content", "Add a feature."]) == 0

    output = capsys.readouterr().out
    assert "Unknown section 'typo'" in output
    assert "gh_issue: expected int, got str" in output
    (file,) = (project / "changelog").glob("*.rtfc")
    entry = Entry.from_file(file, sections=("feature", "bugfix"))
    assert entry.section == "feature"
    assert entry.metadata == {"gh_issue": 123}


def test_new_interactive_required_metadata(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (project / "rtfc.toml").write_text(INTERACTIVE_CONFIG)
    # Empty answer for a required field is asked again:
    interactive(monkeypatch, ["", "", "42", ""])

    assert main(["new", "--content", "Change."]) == 0

    (file,) = (project / "changelog").glob("*.rtfc")
    assert Entry.from_file(file, sections=()).metadata == {"gh_issue": 42}


def test_new_interactive_skips_provided_arguments(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (project / "rtfc.toml").write_text(INTERACTIVE_CONFIG)
    # Only author is prompted for (section and gh_issue given as arguments):
    interactive(monkeypatch, ["victorien"])

    assert main(["new", "--section", "bugfix", "--meta", "gh_issue=1", "--content", "Fix."]) == 0

    (file,) = (project / "changelog").glob("*.rtfc")
    entry = Entry.from_file(file, sections=("bugfix",))
    assert entry.metadata == {"gh_issue": 1, "author": "victorien"}


def test_new_interactive_aborted(
    project: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (project / "rtfc.toml").write_text(INTERACTIVE_CONFIG)
    interactive(monkeypatch, [])  # Immediate EOF (ctrl-D).

    assert main(["new", "--content", "Change."]) == 1

    assert "Aborted" in capsys.readouterr().err
    assert not list((project / "changelog").glob("*.rtfc"))


def test_new_not_interactive_without_tty(project: Path) -> None:
    (project / "rtfc.toml").write_text(INTERACTIVE_CONFIG)

    assert main(["new", "--content", "Change."]) == 0

    (file,) = (project / "changelog").glob("*.rtfc")
    assert Entry.from_file(file, sections=()).metadata == {}
