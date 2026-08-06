"""Configuration discovery and loading.

Configuration is read from the ``[rtfc]`` table of ``rtfc.toml`` or, as a
fallback, the ``[tool.rtfc]`` table of ``pyproject.toml``. Files are only
looked up in the invocation directory.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any, cast

from rtfc._validation import (
    Field,
    Issue,
    Schema,
    ValidationContext,
    ValidationError,
    Validator,
    any_,
    bool_,
    dict_of,
    dir_path,
    file_path,
    float_,
    int_,
    iso_date,
    list_of,
    nullable,
    one_of,
    record,
    str_,
)

__all__ = ("Config", "ConfigError", "MetadataFieldConfig", "RenderConfig", "SectionConfig", "load_config")


class ConfigError(Exception):
    """Raised when the configuration is missing or invalid."""


_DEFAULT_ENTRY_TEMPLATE = "{{ content }}"

_DEFAULT_TEMPLATE = """\
{{ header }}
{% for section in sections if section.entries %}

{% if section.label %}
{{ section_header(section.label) }}

{% endif %}
{% for entry in section.entries | sort_entries %}
{{ list_item(render_entry(entry)) }}
{% endfor %}
{% endfor %}
"""


class SectionConfig(Schema):
    """Configuration of a changelog section (an entry category)."""

    id = Field(str_)
    """Id of the section, as used in the ``section`` field of entries."""

    label = Field(str_)
    """Heading used for the section in the changelog."""


def _derive_label(section_id: str) -> str:
    """Derive a section label from its id, e.g. ``'breaking_change'`` gives ``'Breaking change'``."""
    return section_id.replace("_", " ").replace("-", " ").capitalize()


class _SectionsValidator(Validator[dict[str, SectionConfig]]):
    """Validates the ``sections`` list into an id-keyed mapping, in list order."""

    def validate(self, value: object, context: ValidationContext) -> dict[str, SectionConfig]:
        if isinstance(value, dict) and all(isinstance(section, SectionConfig) for section in value.values()):
            # Already-normalized mappings (e.g. the field default) are passed through:
            return cast("dict[str, SectionConfig]", value)
        if type(value) is not list:
            raise ValidationError.single(context.path, f"expected list, got {type(value).__name__}")
        sections: dict[str, SectionConfig] = {}
        issues: list[Issue] = []
        for i, item in enumerate(value):
            item_context = context.at(i)
            if type(item) is str:
                section = SectionConfig.construct(id=item, label=_derive_label(item))
            else:
                try:
                    section = SectionConfig.validate(item, item_context)
                except ValidationError as exc:
                    issues.extend(exc.issues)
                    continue
            if section.id in sections:
                issues.append(Issue(item_context.path, f"duplicate section id {section.id!r}"))
            else:
                sections[section.id] = section
        if issues:
            raise ValidationError(issues)
        return sections


_METADATA_TYPES: dict[str, Validator[Any]] = {
    "string": str_,
    "integer": int_,
    "boolean": bool_,
    "number": float_,
    "date": iso_date,
}


class MetadataFieldConfig(Schema):
    """Configuration of an entry metadata field."""

    type = Field(one_of(*_METADATA_TYPES, "array"))
    """Type of the field value: ``'string'``, ``'integer'``, ``'boolean'``, ``'number'``,
    ``'date'``, or ``'array'`` (requires ``items``)."""

    items = Field(nullable(one_of(*_METADATA_TYPES)), default=None)
    """Type of the array items. Required and only allowed when ``type`` is ``'array'``."""

    required = Field(bool_, default=False)
    """Whether the field must be present on every entry. Mutually exclusive with ``default``."""

    default = Field(any_, default=None)
    """Value applied when the field is absent. Mutually exclusive with ``required``."""

    def _validator(self) -> Validator[Any]:
        """The validator for values of this field."""
        if self.type == "array":
            assert self.items is not None
            return list_of(_METADATA_TYPES[self.items])
        return _METADATA_TYPES[self.type]

    def __post_validate__(self, context: ValidationContext) -> None:
        if (self.type == "array") != (self.items is not None):
            message = (
                "'items' is required for 'array' fields"
                if self.items is None
                else "'items' is only allowed for 'array' fields"
            )
            raise ValidationError.single(context.path, message)
        if self.default is not None:
            if self.required:
                raise ValidationError.single(context.path, "'required' and 'default' are mutually exclusive")
            self._validator().validate(self.default, context.at("default"))


class RenderConfig(Schema):
    """Configuration of how entries are combined into the changelog."""

    template = Field(nullable(str_), default=None)
    """Jinja template rendering a version block. Mutually exclusive with ``template_file``."""

    template_file = Field(nullable(file_path), default=None)
    """Path to a file containing the version block template, relative to the invocation
    directory (resolved at validation time)."""

    entry_template = Field(nullable(str_), default=None)
    """Jinja template rendering a single entry. Mutually exclusive with ``entry_template_file``."""

    entry_template_file = Field(nullable(file_path), default=None)
    """Path to a file containing the entry template, relative to the configuration file."""

    def resolve_template(self) -> str:
        """Return the effective version block template text.

        Raises:
            ConfigError: If the template file cannot be read.
        """
        if self.template_file is not None:
            try:
                return self.template_file.read_text(encoding="utf-8")
            except OSError as exc:
                raise ConfigError(f"Cannot read template file: {exc}") from exc
        if self.template is not None:
            return self.template
        return _DEFAULT_TEMPLATE

    def resolve_entry_template(self) -> str:
        """Return the effective entry template text.

        Raises:
            ConfigError: If the template file cannot be read.
        """
        if self.entry_template_file is not None:
            try:
                return self.entry_template_file.read_text(encoding="utf-8")
            except OSError as exc:
                raise ConfigError(f"Cannot read entry template file: {exc}") from exc
        if self.entry_template is not None:
            return self.entry_template
        return _DEFAULT_ENTRY_TEMPLATE

    def __post_validate__(self, context: ValidationContext) -> None:
        if self.template is not None and self.template_file is not None:
            raise ValidationError.single(context.path, "'template' and 'template_file' are mutually exclusive")
        if self.entry_template is not None and self.entry_template_file is not None:
            raise ValidationError.single(
                context.path, "'entry_template' and 'entry_template_file' are mutually exclusive"
            )


def _default_sections() -> dict[str, SectionConfig]:
    return {
        "change": SectionConfig.construct(id="change", label="Changes"),
        "feature": SectionConfig.construct(id="feature", label="Features"),
        "bugfix": SectionConfig.construct(id="bugfix", label="Bug fixes"),
    }


class Config(Schema):
    """Top-level rtfc configuration."""

    directory = Field(dir_path, default=Path("changelog"))
    """Directory holding the changelog entry files, relative to the configuration file."""

    changelog = Field(file_path)
    """Path to the changelog file entries are combined into, relative to the configuration file."""

    format = Field(str_, default="rst")
    """Name of the documentation format used for entries and the changelog."""

    sections = Field(_SectionsValidator(), default_factory=_default_sections)
    """Changelog sections by id."""

    metadata = Field(dict_of(MetadataFieldConfig), default_factory=dict)
    """Schema of the entry metadata fields. When empty, metadata is free-form."""

    render = Field(RenderConfig, default_factory=RenderConfig.construct)
    """Rendering options."""

    def metadata_validator(self) -> Validator[dict[str, Any]] | None:
        """Build a validator for entry metadata from the configured schema.

        Returns ``None`` when no metadata schema is configured. Optional fields
        without a default take ``None`` when absent.
        """
        if not self.metadata:
            return None
        fields: dict[str, Field[Any]] = {}
        for name, metadata_field in self.metadata.items():
            type_validator = metadata_field._validator()
            if metadata_field.required:
                fields[name] = Field(type_validator)
            elif metadata_field.default is not None:
                fields[name] = Field(type_validator, default=metadata_field.default)
            else:
                fields[name] = Field(nullable(type_validator), default=None)
        return record(fields)


def _load_toml(file: Path) -> dict[str, Any]:
    try:
        with file.open("rb") as f:
            return tomllib.load(f)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"{file.name}: invalid TOML: {exc}") from exc


def _validate_config(data: object, context: ValidationContext, file_name: str) -> Config:
    try:
        return Config.validate(data, context)
    except ValidationError as exc:
        raise ConfigError(f"{file_name}: invalid configuration:\n{exc}") from exc


def load_config(directory: Path) -> Config:
    """Load the rtfc configuration from ``directory``.

    The ``[rtfc]`` table of ``rtfc.toml`` takes priority over the
    ``[tool.rtfc]`` table of ``pyproject.toml``. Only ``directory`` itself is
    searched.

    Args:
        directory: Directory containing the configuration file.

    Raises:
        ConfigError: If no configuration is found or it is invalid.
    """
    rtfc_toml = directory / "rtfc.toml"
    if rtfc_toml.is_file():
        data = _load_toml(rtfc_toml)
        if "rtfc" not in data:
            raise ConfigError(f"{rtfc_toml.name}: missing the [rtfc] table")
        context = ValidationContext(path=("rtfc",), current_directory=directory)
        return _validate_config(data["rtfc"], context, rtfc_toml.name)

    pyproject = directory / "pyproject.toml"
    if pyproject.is_file():
        tool = _load_toml(pyproject).get("tool")
        if isinstance(tool, dict) and "rtfc" in tool:
            context = ValidationContext(path=("tool", "rtfc"), current_directory=directory)
            return _validate_config(tool["rtfc"], context, pyproject.name)

    raise ConfigError("No configuration found: define an 'rtfc.toml' file or a '[tool.rtfc]' table in 'pyproject.toml'")
