from pathlib import Path

import pytest

pytest.importorskip("sphinx")

from sphinx.cmd.build import build_main

CONF = """
extensions = ["rtfc.sphinx"]
rtfc_config_directory = "../project"
"""

INDEX = """\
Changelog
=========

.. rtfc-unreleased::

.. rtfc-insert
"""


@pytest.fixture
def docs(tmp_path: Path) -> Path:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "conf.py").write_text(CONF)
    (docs / "index.rst").write_text(INDEX)
    project = tmp_path / "project"
    project.mkdir()
    (project / "changelog.rst").touch()
    (project / "rtfc.toml").write_text('[rtfc]\nchangelog = "changelog.rst"')
    (project / "changelog").mkdir()
    return docs


def build_text(docs: Path) -> str:
    out = docs.parent / "out"
    assert build_main(["-b", "text", "-q", "-W", str(docs), str(out)]) == 0
    return (out / "index.txt").read_text()


def write_entry(project: Path, nonce: str, *, section: str = "bugfix", content: str = "Fix a bug.") -> None:
    file = project / "changelog" / f"{nonce}.{section}.rtfc"
    file.write_text(f'+++\ndate = 2025-08-01\nnonce = "{nonce}"\nsection = "{section}"\n+++\n{content}\n')


def test_directive_injects_unreleased_entries(docs: Path) -> None:
    write_entry(docs.parent / "project", "abc", content="Fix the sphinx bug.")
    write_entry(docs.parent / "project", "def", section="feature", content="Add the sphinx feature.")

    text = build_text(docs)

    assert "Unreleased" in text
    assert "Features" in text
    assert "Add the sphinx feature." in text
    assert "* Fix the sphinx bug." in text


def test_directive_renders_nothing_without_entries(docs: Path) -> None:
    text = build_text(docs)

    assert "Unreleased" not in text


def test_directive_reports_config_errors(docs: Path) -> None:
    (docs.parent / "project" / "rtfc.toml").write_text('[rtfc]\nchangelog = "missing.rst"')

    out = docs.parent / "out"
    assert build_main(["-b", "text", "-q", "-W", str(docs), str(out)]) != 0


def test_directive_content_rendered_as_note(docs: Path) -> None:
    write_entry(docs.parent / "project", "abc")
    (docs / "index.rst").write_text(
        "Changelog\n=========\n\n.. rtfc-unreleased::\n\n   Not released yet, careful out there.\n"
    )

    text = build_text(docs)

    note_position = text.index("Not released yet, careful out there.")
    assert "Note:" in text
    assert text.index("Unreleased") < note_position < text.index("Fix a bug.")


def test_directive_without_content_has_no_note(docs: Path) -> None:
    write_entry(docs.parent / "project", "abc")

    assert "Note:" not in build_text(docs)
