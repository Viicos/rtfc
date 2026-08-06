from pathlib import Path

import pytest

from rtfc._config import ConfigError, RenderConfig, load_config
from rtfc._validation import ValidationContext, ValidationError


@pytest.fixture(autouse=True)
def _in_tmp_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Defaults are validated: the default of ``Config.directory`` must exist."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "changelog").mkdir()


def test_rtfc_toml_minimal(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/changelog.rst").touch()
    (tmp_path / "rtfc.toml").write_text('[rtfc]\nchangelog = "docs/changelog.rst"')

    config = load_config(tmp_path)

    assert config.changelog == tmp_path / "docs/changelog.rst"
    assert config.directory == tmp_path / "changelog"
    assert config.format == "rst"
    assert {section_id: section.label for section_id, section in config.sections.items()} == {
        "change": "Changes",
        "feature": "Features",
        "bugfix": "Bug fixes",
    }
    assert config.render == RenderConfig.construct()


def test_pyproject_fallback(tmp_path: Path) -> None:
    (tmp_path / "c.rst").touch()
    (tmp_path / "pyproject.toml").write_text(
        """
[tool.rtfc]
changelog = "c.rst"
sections = [{ id = "breaking", label = "Breaking changes" }]
"""
    )

    config = load_config(tmp_path)

    assert config.changelog == tmp_path / "c.rst"
    assert list(config.sections) == ["breaking"]
    assert config.sections["breaking"].label == "Breaking changes"


def test_rtfc_toml_priority_over_pyproject(tmp_path: Path) -> None:
    (tmp_path / "a.rst").touch()
    (tmp_path / "rtfc.toml").write_text('[rtfc]\nchangelog = "a.rst"')
    (tmp_path / "pyproject.toml").write_text('[tool.rtfc]\nchangelog = "b.rst"')

    assert load_config(tmp_path).changelog == tmp_path / "a.rst"


def test_missing_config(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="No configuration found"):
        load_config(tmp_path)


def test_pyproject_without_rtfc_table(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"')

    with pytest.raises(ConfigError, match="No configuration found"):
        load_config(tmp_path)


def test_pyproject_tool_not_a_table(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("tool = 3")

    with pytest.raises(ConfigError, match="No configuration found"):
        load_config(tmp_path)


def test_invalid_toml(tmp_path: Path) -> None:
    (tmp_path / "rtfc.toml").write_text("[rtfc]\nchangelog = ")

    with pytest.raises(ConfigError, match=r"rtfc\.toml: invalid TOML"):
        load_config(tmp_path)


def test_invalid_config_rtfc_toml(tmp_path: Path) -> None:
    (tmp_path / "rtfc.toml").write_text("[rtfc]\nchangelog = 1\ntypo = true")

    with pytest.raises(ConfigError) as exc_info:
        load_config(tmp_path)

    message = str(exc_info.value)
    assert "rtfc.toml: invalid configuration:" in message
    assert "changelog: expected path, got int" in message
    assert "typo: unknown key" in message


def test_invalid_config_pyproject_paths_prefixed(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        """
[tool.rtfc]
changelog = 1

[tool.rtfc.render]
flat = "yes"
"""
    )

    with pytest.raises(ConfigError) as exc_info:
        load_config(tmp_path)

    message = str(exc_info.value)
    assert "pyproject.toml: invalid configuration:" in message
    assert "tool.rtfc.changelog: expected path, got int" in message
    assert "tool.rtfc.render.flat: unknown key" in message


def test_no_parent_traversal(tmp_path: Path) -> None:
    (tmp_path / "rtfc.toml").write_text('[rtfc]\nchangelog = "a.rst"')
    child = tmp_path / "sub"
    child.mkdir()

    with pytest.raises(ConfigError, match="No configuration found"):
        load_config(child)


def test_entry_template_and_file_mutually_exclusive(tmp_path: Path) -> None:
    (tmp_path / "c.rst").touch()
    (tmp_path / "t.jinja").touch()
    (tmp_path / "rtfc.toml").write_text(
        '[rtfc]\nchangelog = "c.rst"\n[rtfc.render]\nentry_template = "{{ content }}"\nentry_template_file = "t.jinja"'
    )

    with pytest.raises(ConfigError, match="'entry_template' and 'entry_template_file' are mutually exclusive"):
        load_config(tmp_path)


def test_resolve_entry_template_default() -> None:
    assert RenderConfig.construct().resolve_entry_template() == "{{ content }}"


def test_resolve_entry_template_inline() -> None:
    render = RenderConfig.construct(entry_template="{{ content }}!")

    assert render.resolve_entry_template() == "{{ content }}!"


def test_resolve_entry_template_from_file(tmp_path: Path) -> None:
    (tmp_path / "t.jinja").write_text("{{ content }} (from file)")
    render = RenderConfig.construct(entry_template_file=tmp_path / "t.jinja")

    assert render.resolve_entry_template() == "{{ content }} (from file)"


def test_resolve_entry_template_missing_file(tmp_path: Path) -> None:
    render = RenderConfig.construct(entry_template_file=tmp_path / "missing.jinja")

    with pytest.raises(ConfigError, match="Cannot read entry template file"):
        render.resolve_entry_template()


def test_entry_template_file_resolved_at_load_time(tmp_path: Path) -> None:
    (tmp_path / "c.rst").touch()
    (tmp_path / "t.jinja").write_text("{{ content }} (from file)")
    (tmp_path / "rtfc.toml").write_text('[rtfc]\nchangelog = "c.rst"\n[rtfc.render]\nentry_template_file = "t.jinja"')

    config = load_config(tmp_path)

    assert config.render.entry_template_file == tmp_path / "t.jinja"
    assert config.render.resolve_entry_template() == "{{ content }} (from file)"


def test_metadata_schema(tmp_path: Path) -> None:
    (tmp_path / "c.rst").touch()
    (tmp_path / "rtfc.toml").write_text(
        """
[rtfc]
changelog = "c.rst"

[rtfc.metadata.gh_issue]
type = "integer"
required = true

[rtfc.metadata.author]
type = "string"
default = "unknown"

[rtfc.metadata.backport]
type = "boolean"
"""
    )

    validator = load_config(tmp_path).metadata_validator()

    assert validator is not None
    validated = validator.validate({"gh_issue": 1}, ValidationContext())
    assert validated == {"gh_issue": 1, "author": "unknown", "backport": None}
    with pytest.raises(ValidationError, match="gh_issue: expected int, got str"):
        validator.validate({"gh_issue": "1"}, ValidationContext())


def test_metadata_validator_none_when_not_configured(tmp_path: Path) -> None:
    (tmp_path / "c.rst").touch()
    (tmp_path / "rtfc.toml").write_text('[rtfc]\nchangelog = "c.rst"')

    assert load_config(tmp_path).metadata_validator() is None


def test_metadata_schema_unknown_type(tmp_path: Path) -> None:
    (tmp_path / "c.rst").touch()
    (tmp_path / "rtfc.toml").write_text('[rtfc]\nchangelog = "c.rst"\n[rtfc.metadata.gh_issue]\ntype = "typo"')

    with pytest.raises(ConfigError, match=r"metadata\.gh_issue\.type: expected one of 'string', .*, got 'typo'"):
        load_config(tmp_path)


def test_metadata_schema_required_and_default_exclusive(tmp_path: Path) -> None:
    (tmp_path / "c.rst").touch()
    (tmp_path / "rtfc.toml").write_text(
        '[rtfc]\nchangelog = "c.rst"\n[rtfc.metadata.gh_issue]\ntype = "integer"\nrequired = true\ndefault = 1'
    )

    with pytest.raises(ConfigError, match=r"metadata\.gh_issue: 'required' and 'default' are mutually exclusive"):
        load_config(tmp_path)


def test_metadata_schema_default_type_mismatch(tmp_path: Path) -> None:
    (tmp_path / "c.rst").touch()
    (tmp_path / "pyproject.toml").write_text(
        '[tool.rtfc]\nchangelog = "c.rst"\n[tool.rtfc.metadata.gh_issue]\ntype = "integer"\ndefault = "x"'
    )

    with pytest.raises(ConfigError, match=r"tool\.rtfc\.metadata\.gh_issue\.default: expected int, got str"):
        load_config(tmp_path)


def test_metadata_schema_array(tmp_path: Path) -> None:
    (tmp_path / "c.rst").touch()
    (tmp_path / "rtfc.toml").write_text(
        """
[rtfc]
changelog = "c.rst"

[rtfc.metadata.contributors]
type = "array"
items = "string"
required = true
"""
    )

    validator = load_config(tmp_path).metadata_validator()

    assert validator is not None
    assert validator.validate({"contributors": ["a", "b"]}, ValidationContext()) == {"contributors": ["a", "b"]}
    with pytest.raises(ValidationError, match=r"contributors\[1\]: expected str, got int"):
        validator.validate({"contributors": ["a", 2]}, ValidationContext())


def test_metadata_schema_array_default(tmp_path: Path) -> None:
    (tmp_path / "c.rst").touch()
    (tmp_path / "rtfc.toml").write_text(
        '[rtfc]\nchangelog = "c.rst"\n[rtfc.metadata.tags]\ntype = "array"\nitems = "string"\ndefault = ["misc"]'
    )

    validator = load_config(tmp_path).metadata_validator()

    assert validator is not None
    assert validator.validate({}, ValidationContext()) == {"tags": ["misc"]}


def test_metadata_schema_array_requires_items(tmp_path: Path) -> None:
    (tmp_path / "c.rst").touch()
    (tmp_path / "rtfc.toml").write_text('[rtfc]\nchangelog = "c.rst"\n[rtfc.metadata.tags]\ntype = "array"')

    with pytest.raises(ConfigError, match="'items' is required for 'array' fields"):
        load_config(tmp_path)


def test_metadata_schema_items_only_for_arrays(tmp_path: Path) -> None:
    (tmp_path / "c.rst").touch()
    (tmp_path / "rtfc.toml").write_text(
        '[rtfc]\nchangelog = "c.rst"\n[rtfc.metadata.tags]\ntype = "string"\nitems = "string"'
    )

    with pytest.raises(ConfigError, match="'items' is only allowed for 'array' fields"):
        load_config(tmp_path)


def test_metadata_schema_array_default_type_mismatch(tmp_path: Path) -> None:
    (tmp_path / "c.rst").touch()
    (tmp_path / "rtfc.toml").write_text(
        'changelog = "c.rst"\n[rtfc.metadata.tags]\ntype = "array"\nitems = "integer"\ndefault = [1, "x"]'
    )

    with pytest.raises(ConfigError, match=r"metadata\.tags\.default\[1\]: expected int, got str"):
        load_config(tmp_path)


def test_default_directory_relative_to_config_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "c.rst").touch()
    (tmp_path / "rtfc.toml").write_text('[rtfc]\nchangelog = "c.rst"')
    monkeypatch.chdir(tmp_path.parent)

    assert load_config(tmp_path).directory == tmp_path / "changelog"


def test_sections_plain_strings_derive_labels(tmp_path: Path) -> None:
    (tmp_path / "c.rst").touch()
    (tmp_path / "rtfc.toml").write_text('[rtfc]\nchangelog = "c.rst"\nsections = ["breaking_change", "perf"]')

    config = load_config(tmp_path)

    assert {section_id: section.label for section_id, section in config.sections.items()} == {
        "breaking_change": "Breaking change",
        "perf": "Perf",
    }


def test_sections_mixed_items(tmp_path: Path) -> None:
    (tmp_path / "c.rst").touch()
    (tmp_path / "rtfc.toml").write_text(
        '[rtfc]\nchangelog = "c.rst"\nsections = ["perf", { id = "bugfix", label = "Bug fixes" }]'
    )

    config = load_config(tmp_path)

    assert list(config.sections) == ["perf", "bugfix"]
    assert config.sections["bugfix"].label == "Bug fixes"


def test_sections_duplicate_id(tmp_path: Path) -> None:
    (tmp_path / "c.rst").touch()
    (tmp_path / "rtfc.toml").write_text(
        '[rtfc]\nchangelog = "c.rst"\nsections = ["bugfix", { id = "bugfix", label = "Bug fixes" }]'
    )

    with pytest.raises(ConfigError, match=r"sections\[1\]: duplicate section id 'bugfix'"):
        load_config(tmp_path)


def test_sections_invalid_item(tmp_path: Path) -> None:
    (tmp_path / "c.rst").touch()
    (tmp_path / "rtfc.toml").write_text('[rtfc]\nchangelog = "c.rst"\nsections = [1]\n')

    with pytest.raises(ConfigError, match=r"sections\[0\]: expected table, got int"):
        load_config(tmp_path)


def test_sections_item_missing_keys(tmp_path: Path) -> None:
    (tmp_path / "c.rst").touch()
    (tmp_path / "rtfc.toml").write_text('[rtfc]\nchangelog = "c.rst"\nsections = [{ label = "Perf" }]')

    with pytest.raises(ConfigError, match=r"sections\[0\]\.id: missing required key"):
        load_config(tmp_path)


def test_sections_table_syntax_rejected(tmp_path: Path) -> None:
    (tmp_path / "c.rst").touch()
    (tmp_path / "rtfc.toml").write_text('[rtfc]\nchangelog = "c.rst"\n[rtfc.sections.feature]\nlabel = "Features"')

    with pytest.raises(ConfigError, match="sections: expected list, got dict"):
        load_config(tmp_path)


def test_missing_entry_directory(tmp_path: Path) -> None:
    (tmp_path / "c.rst").touch()
    (tmp_path / "rtfc.toml").write_text('[rtfc]\nchangelog = "c.rst"\ndirectory = "missing"')

    with pytest.raises(ConfigError, match="directory: path 'missing' does not exist"):
        load_config(tmp_path)


def test_changelog_must_be_a_file(tmp_path: Path) -> None:
    (tmp_path / "rtfc.toml").write_text('[rtfc]\nchangelog = "changelog"')

    with pytest.raises(ConfigError, match="changelog: path 'changelog' is not a file"):
        load_config(tmp_path)


def test_rtfc_toml_missing_table(tmp_path: Path) -> None:
    (tmp_path / "c.rst").touch()
    (tmp_path / "rtfc.toml").write_text('changelog = "c.rst"')

    with pytest.raises(ConfigError, match=r"rtfc\.toml: missing the \[rtfc\] table"):
        load_config(tmp_path)


def test_template_and_file_mutually_exclusive(tmp_path: Path) -> None:
    (tmp_path / "c.rst").touch()
    (tmp_path / "t.jinja").touch()
    (tmp_path / "rtfc.toml").write_text(
        '[rtfc]\nchangelog = "c.rst"\n[rtfc.render]\ntemplate = "{{ header }}"\ntemplate_file = "t.jinja"'
    )

    with pytest.raises(ConfigError, match="'template' and 'template_file' are mutually exclusive"):
        load_config(tmp_path)


def test_resolve_template_default() -> None:
    assert RenderConfig.construct().resolve_template().startswith("{{ header }}")
