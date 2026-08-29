from pathlib import Path

import pytest

from rtfc._cli import main
from rtfc._config import Config, EngineConfig, ExporterConfig
from rtfc._export import ExportError, get_exporter

pytest.importorskip("sphinx")

INDEX = """\
Test project
============

.. _the-label:

Some target
-----------

Content.
"""

RTFC_TOML = """\
[rtfc]
changelog = "changelog.rst"
directory = "changelog"

[rtfc.export.markdown.engine]
name = "sphinx"
sphinx_directory = "docs"
base_url = "https://docs.example"

[rtfc.export.github-markdown.engine]
name = "sphinx"
sphinx_directory = "docs"

[rtfc.export.gitlab-markdown.engine]
name = "sphinx"
sphinx_directory = "docs"
"""


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "rtfc.toml").write_text(RTFC_TOML)
    (tmp_path / "changelog.rst").write_text("Changelog\n=========\n\n.. rtfc-insert\n")
    (tmp_path / "changelog").mkdir()
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "conf.py").write_text('project = "test"\nextensions = []\n')
    (docs / "index.rst").write_text(INDEX)
    return tmp_path


def write_entry(project: Path, nonce: str, content: str) -> None:
    file = project / "changelog" / f"{nonce}.bugfix.rtfc"
    file.write_text(f'+++\ndate = 2025-08-01\nnonce = "{nonce}"\nsection = "bugfix"\n+++\n{content}\n')


def set_export_config(project: Path, table: str) -> None:
    config = RTFC_TOML.split("[rtfc.export.markdown.engine]", maxsplit=1)[0] + table
    (project / "rtfc.toml").write_text(config)


def test_export_resolves_references(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    write_entry(project, "abc", "See :ref:`the-label`, ``some_code`` and `GH <https://github.com>`_.")

    assert main(["export", "markdown", "--version", "1.0.0"]) == 0

    output = capsys.readouterr().out
    assert "# v1.0.0 (" in output
    assert "## Bug fixes" in output
    assert (
        "- See [Some target](https://docs.example/index.html#the-label), `some_code` and [GH](https://github.com)."
        in output
    )


def test_export_unknown_syntax_degrades_to_text(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    write_entry(project, "abc", "Improve :math:`x^2` handling.")

    assert main(["export", "markdown", "--version", "1.0.0"]) == 0

    assert "- Improve x^2 handling." in capsys.readouterr().out


def test_export_not_configured(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    set_export_config(project, "")
    write_entry(project, "abc", "Fix a bug.")

    assert main(["export", "markdown", "--version", "1.0.0"]) == 1

    assert "The 'markdown' exporter is not configured" in capsys.readouterr().err


def test_export_unknown_exporter(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    set_export_config(project, '[rtfc.export.typo.engine]\nname = "sphinx"\nsphinx_directory = "docs"')
    write_entry(project, "abc", "Fix a bug.")

    assert main(["export", "typo", "--version", "1.0.0"]) == 1

    error = capsys.readouterr().err
    assert "Unknown exporter 'typo' (available: 'markdown', 'github-markdown', 'gitlab-markdown')" in error


def test_unknown_format_engine_rejected_at_config_load(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    set_export_config(project, '[rtfc.export.markdown.engine]\nname = "mkdocs"')
    write_entry(project, "abc", "Fix a bug.")

    assert main(["export", "markdown", "--version", "1.0.0"]) == 1

    assert "rtfc.export.markdown.engine.name: expected one of 'sphinx', got 'mkdocs'" in capsys.readouterr().err


def test_sphinx_directory_required_at_config_load(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    set_export_config(project, '[rtfc.export.markdown.engine]\nname = "sphinx"')
    write_entry(project, "abc", "Fix a bug.")

    assert main(["export", "markdown", "--version", "1.0.0"]) == 1

    assert "rtfc.export.markdown.engine.sphinx_directory: missing required key" in capsys.readouterr().err


def test_unsupported_format_engine() -> None:
    config = Config.construct(
        changelog=Path("changelog.rst"),
        export={"markdown": ExporterConfig.construct(engine=EngineConfig.construct(name="mkdocs"))},
    )

    with pytest.raises(ExportError, match="Format engine 'mkdocs' is not supported by the 'markdown' exporter"):
        get_exporter(config, "markdown")


def test_export_no_entries(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["export", "markdown", "--version", "1.0.0"]) == 1
    assert "No changelog entries found" in capsys.readouterr().err


def test_export_cleans_up_synthesized_document(project: Path) -> None:
    write_entry(project, "abc", "Fix a bug.")

    assert main(["export", "markdown", "--version", "1.0.0"]) == 0

    assert not list((project / "docs").glob("_rtfc-export*"))


NOTE_ENTRY = "Fix a bug.\n\n.. note::\n\n   Be careful."


def test_markdown_renders_commonmark_admonitions(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    write_entry(project, "abc", NOTE_ENTRY)

    assert main(["export", "markdown", "--version", "1.0.0"]) == 0

    output = capsys.readouterr().out
    assert "> **Note**" in output
    assert "> Be careful." in output
    assert "[!NOTE]" not in output


def test_github_markdown_renders_alerts(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    write_entry(project, "abc", NOTE_ENTRY)

    assert main(["export", "github-markdown", "--version", "1.0.0"]) == 0

    output = capsys.readouterr().out
    assert "> [!NOTE]" in output
    assert "> Be careful." in output


def test_gitlab_markdown_renders_alerts(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    write_entry(project, "abc", NOTE_ENTRY)

    assert main(["export", "gitlab-markdown", "--version", "1.0.0"]) == 0

    output = capsys.readouterr().out
    assert "> [!note]" in output
    assert "> Be careful." in output
