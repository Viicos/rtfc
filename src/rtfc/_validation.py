"""Standalone validation framework for TOML-sourced data (config and frontmatter).

Validators are composable objects implementing the :class:`Validator` protocol.
Schemas declare fields as :class:`Field` descriptors, making validated attribute
access fully type-checked without any annotation introspection::

    class Section(Schema):
        label = Field(str_)

    section = Section.validate({'label': 'Features'})
    section.label  # inferred as ``str``

Scalar validators use exact type checks: a ``bool`` is not accepted where an
``int`` is expected, nor a ``datetime`` where a ``date`` is expected.
"""

from __future__ import annotations

import datetime
import inspect
import pathlib
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from typing import (
    Any,
    ClassVar,
    Generic,
    Literal,
    Never,
    Protocol,
    Self,
    TypeAlias,
    TypeVar,
    cast,
    overload,
)

from typing_extensions import Sentinel

__all__ = (
    "Field",
    "Issue",
    "KeyPath",
    "Schema",
    "ValidationContext",
    "ValidationError",
    "Validator",
    "any_",
    "bool_",
    "dict_of",
    "dir_path",
    "file_path",
    "float_",
    "int_",
    "iso_date",
    "list_of",
    "nullable",
    "one_of",
    "record",
    "str_",
)

T = TypeVar("T")

KeyPath: TypeAlias = tuple[str | int, ...]
"""Location of a value relative to the document root, e.g. ``('sections', 'feature', 'label')``."""


@dataclass(frozen=True)
class ValidationContext:
    """Contextual information carried through validators during validation."""

    path: KeyPath = ()
    """Location of the value being validated in the document it is part of."""

    current_directory: pathlib.Path = dataclass_field(default_factory=pathlib.Path.cwd)
    """Directory against which relative paths are resolved."""

    def at(self, part: str | int) -> ValidationContext:
        """Return a copy with ``part`` appended to the location path."""
        return ValidationContext(path=(*self.path, part), current_directory=self.current_directory)


def _format_path(path: KeyPath) -> str:
    formatted = ""
    for part in path:
        if isinstance(part, int):
            formatted += f"[{part}]"
        else:
            formatted += f".{part}" if formatted else part
    return formatted or "<root>"


@dataclass
class Issue:
    """A single validation failure at a specific location."""

    path: KeyPath
    message: str

    def __str__(self) -> str:
        return f"{_format_path(self.path)}: {self.message}"


class ValidationError(Exception):
    """Raised when validation fails, aggregating one or more issues."""

    issues: list[Issue]

    def __init__(self, issues: list[Issue]) -> None:
        super().__init__("\n".join(str(issue) for issue in issues))
        self.issues = issues

    @classmethod
    def single(cls, path: KeyPath, message: str) -> ValidationError:
        """Create an error holding a single issue."""
        return cls([Issue(path, message)])


#  Invariant and not covariant to ensure the inference of `T` in `Field(validator, default=...)`
# matches exactly the validator's type (otherwise `Field(str_, default=3)` widens to `str | int`):
class Validator(Protocol[T]):  # pyright: ignore[reportInvalidTypeVarUse]
    """A composable validator producing values of a fixed type."""

    def validate(self, value: object, context: ValidationContext) -> T:
        """Validate ``value``, returning it (possibly converted) on success.

        Args:
            value: The value to validate.
            context: The validation context, carrying the location of
                ``value`` in the document it is part of. Container validators
                extend the location as they recurse (e.g. with the key of each
                table value), so that reported issues carry the full location
                of the offending value, like ``sections.feature.label``.

        Raises:
            ValidationError: If ``value`` is invalid.
        """
        ...


class _Exact(Validator[T]):
    def __init__(self, typ: type[T], name: str) -> None:
        self._typ = typ
        self._name = name

    def validate(self, value: object, context: ValidationContext) -> T:
        # An exact type check avoids `bool` passing as `int` (and similar subclass leaks):
        if type(value) is not self._typ:
            raise ValidationError.single(context.path, f"expected {self._name}, got {type(value).__name__}")
        return cast(T, value)


class _Float(Validator[float]):
    def validate(self, value: object, context: ValidationContext) -> float:
        if type(value) is float:
            return value
        if type(value) is int:
            return float(value)
        raise ValidationError.single(context.path, f"expected float, got {type(value).__name__}")


class _IsoDate(Validator[datetime.date]):
    def validate(self, value: object, context: ValidationContext) -> datetime.date:
        # Exact check: `datetime` is a `date` subclass but is not accepted here.
        if type(value) is datetime.date:
            return value
        if type(value) is str:
            try:
                return datetime.date.fromisoformat(value)
            except ValueError:
                raise ValidationError.single(context.path, f"invalid ISO date: {value!r}") from None
        raise ValidationError.single(context.path, f"expected ISO date, got {type(value).__name__}")


class _PathValidator(Validator[pathlib.Path]):
    def __init__(self, kind: Literal["file", "directory"] | None = None) -> None:
        self._kind: Literal["file", "directory"] | None = kind

    def validate(self, value: object, context: ValidationContext) -> pathlib.Path:
        if not isinstance(value, str | pathlib.Path):
            raise ValidationError.single(context.path, f"expected path, got {type(value).__name__}")
        resolved = context.current_directory / value
        if not resolved.exists():
            raise ValidationError.single(context.path, f"path {str(value)!r} does not exist")
        if self._kind == "file" and not resolved.is_file():
            raise ValidationError.single(context.path, f"path {str(value)!r} is not a file")
        if self._kind == "directory" and not resolved.is_dir():
            raise ValidationError.single(context.path, f"path {str(value)!r} is not a directory")
        return resolved


class _Anything(Validator[Any]):
    def validate(self, value: object, context: ValidationContext) -> Any:
        return value


bool_: Validator[bool] = _Exact(bool, "bool")
"""Validator accepting exactly :class:`bool` values."""

int_: Validator[int] = _Exact(int, "int")
"""Validator accepting exactly :class:`int` values."""

float_: Validator[float] = _Float()
"""Validator accepting :class:`float` values, converting from :class:`int`."""

str_: Validator[str] = _Exact(str, "str")
"""Validator accepting exactly :class:`str` values."""

iso_date: Validator[datetime.date] = _IsoDate()
"""Validator accepting :class:`datetime.date` values or ISO format strings."""

file_path: Validator[pathlib.Path] = _PathValidator("file")
"""Validator accepting :class:`str` or :class:`~pathlib.Path` values pointing to an existing file.

Relative paths are resolved against the context's current directory, and stored resolved.
"""

dir_path: Validator[pathlib.Path] = _PathValidator("directory")
"""Validator accepting :class:`str` or :class:`~pathlib.Path` values pointing to an existing directory.

Relative paths are resolved against the context's current directory, and stored resolved.
"""

any_: Validator[Any] = _Anything()
"""Validator accepting any value unchanged."""


class _Nullable(Validator[T | None]):
    def __init__(self, inner: Validator[T]) -> None:
        self._inner = inner

    def validate(self, value: object, context: ValidationContext) -> T | None:
        if value is None:
            return None
        return self._inner.validate(value, context)


def nullable(validator: Validator[T]) -> Validator[T | None]:
    """Wrap ``validator`` to also accept ``None``."""
    return _Nullable(validator)


class _OneOf(Validator[T]):
    def __init__(self, values: tuple[T, ...]) -> None:
        self._values = values

    def validate(self, value: object, context: ValidationContext) -> T:
        for allowed in self._values:
            # An exact type check avoids e.g. `True` matching an allowed `1`:
            if type(value) is type(allowed) and value == allowed:
                return cast(T, value)
        expected = ", ".join(map(repr, self._values))
        raise ValidationError.single(context.path, f"expected one of {expected}, got {value!r}")


def one_of(*values: T) -> Validator[T]:
    """Create a validator accepting only the given values."""
    if not values:
        raise TypeError("one_of() requires at least one value")
    return _OneOf(values)


class _List(Validator[list[T]]):
    def __init__(self, item: Validator[T]) -> None:
        self._item = item

    def validate(self, value: object, context: ValidationContext) -> list[T]:
        if type(value) is not list:
            raise ValidationError.single(context.path, f"expected list, got {type(value).__name__}")
        items: list[T] = []
        issues: list[Issue] = []
        for i, item in enumerate(value):
            try:
                items.append(self._item.validate(item, context.at(i)))
            except ValidationError as exc:
                issues.extend(exc.issues)
        if issues:
            raise ValidationError(issues)
        return items


def list_of(item: Validator[T]) -> Validator[list[T]]:
    """Create a validator for lists with items validated by ``item``."""
    return _List(item)


class _Dict(Validator[dict[str, T]]):
    def __init__(self, item: Validator[T]) -> None:
        self._item = item

    def validate(self, value: object, context: ValidationContext) -> dict[str, T]:
        if not isinstance(value, Mapping):
            raise ValidationError.single(context.path, f"expected table, got {type(value).__name__}")
        items: dict[str, T] = {}
        issues: list[Issue] = []
        for key, item in value.items():
            if type(key) is not str:
                issues.append(Issue(context.path, f"expected string key, got {key!r}"))
                continue
            try:
                items[key] = self._item.validate(item, context.at(key))
            except ValidationError as exc:
                issues.extend(exc.issues)
        if issues:
            raise ValidationError(issues)
        return items


def dict_of(item: Validator[T]) -> Validator[dict[str, T]]:
    """Create a validator for string-keyed tables with values validated by ``item``."""
    return _Dict(item)


_UNSET = Sentinel("_UNSET")


def _takes_context(factory: Callable[..., Any]) -> bool:
    """Whether a default factory takes the validation context as an argument."""
    try:
        parameters = inspect.signature(factory).parameters.values()
    except (TypeError, ValueError):
        # Some builtin callables (e.g. `dict`) expose no signature; they are
        # only ever useful as zero-argument factories here:
        return False
    return any(
        parameter.default is parameter.empty
        and parameter.kind in (parameter.POSITIONAL_ONLY, parameter.POSITIONAL_OR_KEYWORD)
        for parameter in parameters
    )


class Field(Generic[T]):
    """Descriptor declaring a validated :class:`Schema` field.

    The attribute type is inferred from the validator, e.g. ``Field(str_)``
    produces a ``str`` attribute. A field with no default is required.

    Args:
        validator: Validator applied to the raw value.
        default: Value used when the key is absent.
        default_factory: A callable producing the default, for mutable or
            context-dependent defaults. Either takes no argument, or the
            :class:`ValidationContext` (e.g. to resolve a default path against
            the context's current directory). Mutually exclusive with
            ``default``.
    """

    def __init__(
        self,
        validator: Validator[T],
        *,
        default: T | _UNSET = _UNSET,
        default_factory: Callable[[], T] | Callable[[ValidationContext], T] | None = None,
    ) -> None:
        if default is not _UNSET and default_factory is not None:
            raise TypeError("'default' and 'default_factory' are mutually exclusive")
        self._validator = validator
        self._default = default
        self._default_factory: Callable[[ValidationContext], T] | None
        if default_factory is not None and not _takes_context(default_factory):
            zero_arg_factory = cast("Callable[[], T]", default_factory)
            self._default_factory = lambda context: zero_arg_factory()
        else:
            self._default_factory = cast("Callable[[ValidationContext], T] | None", default_factory)
        self._name = "<unbound>"

    def __set_name__(self, owner: type, name: str) -> None:
        self._name = name

    @overload
    def __get__(self, obj: None, owner: type) -> Self: ...
    @overload
    def __get__(self, obj: object, owner: type | None = None) -> T: ...
    def __get__(self, obj: object | None, owner: type | None = None) -> Self | T:
        if obj is None:
            return self
        return cast(T, obj.__dict__[self._name])

    def __set__(self, obj: object, value: Never) -> None:
        raise AttributeError(f"{type(obj).__name__!r} instances are frozen")


def _validate_fields(fields: Mapping[str, Field[Any]], value: object, context: ValidationContext) -> dict[str, Any]:
    """Validate a mapping against a fixed set of fields, collecting all issues.

    Missing fields take their default, which is validated like a provided
    value; fields without a default are required. Unknown keys are rejected.
    """
    if not isinstance(value, Mapping):
        raise ValidationError.single(context.path, f"expected table, got {type(value).__name__}")
    values: dict[str, Any] = {}
    issues: list[Issue] = []
    for name, field in fields.items():
        if name in value:
            candidate = value[name]
        elif field._default is not _UNSET:
            candidate = field._default
        elif field._default_factory is not None:
            candidate = field._default_factory(context)
        else:
            issues.append(Issue((*context.path, name), "missing required key"))
            continue
        try:
            values[name] = field._validator.validate(candidate, context.at(name))
        except ValidationError as exc:
            issues.extend(exc.issues)
    for key in value:
        if key not in fields:
            issues.append(Issue((*context.path, str(key)), "unknown key"))
    if issues:
        raise ValidationError(issues)
    return values


class _Record(Validator[dict[str, Any]]):
    def __init__(self, fields: dict[str, Field[Any]]) -> None:
        self._fields = fields

    def validate(self, value: object, context: ValidationContext) -> dict[str, Any]:
        return _validate_fields(self._fields, value, context)


def record(fields: Mapping[str, Field[Any]]) -> Validator[dict[str, Any]]:
    """Create a validator for a table with a fixed set of fields, returning a plain dict.

    Missing fields take their default; fields without a default are required.
    Unknown keys are rejected.
    """
    return _Record(dict(fields))


class Schema:  # noqa: PLW1641
    """Base class for validated mappings.

    Subclasses declare fields as class attributes::

        class Config(Schema):
            directory = Field(str_, default='changelog.d')

    Instances are frozen and cannot be created directly: use :meth:`validate`
    for untrusted data or :meth:`construct` for known-valid values. Schema
    classes themselves satisfy the :class:`Validator` protocol, so they can be
    nested: ``Field(Config)``, ``dict_of(Config)``.
    """

    __fields__: ClassVar[dict[str, Field[Any]]] = {}

    def __init__(self, *args: Never, **kwargs: Never) -> None:
        raise TypeError(
            f"{type(self).__name__!r} cannot be instantiated directly, use 'validate()' or 'construct()' instead"
        )

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        cls.__fields__ = cls.__fields__ | {name: field for name, field in vars(cls).items() if isinstance(field, Field)}

    @classmethod
    def validate(cls, value: object, context: ValidationContext | None = None) -> Self:
        """Validate a mapping against the schema.

        Args:
            value: The value to validate. Must be a mapping.
            context: The validation context: the location of ``value`` in the
                document it is part of, used to report issues with their full
                location, and the directory relative paths are resolved
                against. Defaults to an empty location and the current working
                directory.

        Returns:
            A frozen instance with validated field values.

        Raises:
            ValidationError: If ``value`` does not conform to the schema. All
                issues are collected and reported together.
        """
        if isinstance(value, cls):
            # Already-validated instances (e.g. used as field defaults) are passed through:
            return value
        context = ValidationContext() if context is None else context
        values = _validate_fields(cls.__fields__, value, context)
        self = cls.__new__(cls)
        self.__dict__.update(values)
        self.__post_validate__(context)
        return self

    def __post_validate__(self, context: ValidationContext) -> None:
        """Validate constraints spanning multiple fields.

        Called by :meth:`validate` on the constructed instance, once all fields
        validated successfully. Not called by :meth:`construct`.

        Raises:
            ValidationError: If the constraints are not met.
        """

    @classmethod
    def construct(cls, **values: Any) -> Self:
        """Create an instance from known-valid field values, without validation.

        Missing fields take their default; fields without a default are
        required.

        Raises:
            TypeError: If a required field is missing or an unknown field is provided.
        """
        self = cls.__new__(cls)
        for name, field in cls.__fields__.items():
            if name in values:
                self.__dict__[name] = values.pop(name)
            elif field._default is not _UNSET:
                self.__dict__[name] = field._default
            elif field._default_factory is not None:
                self.__dict__[name] = field._default_factory(ValidationContext())
            else:
                raise TypeError(f"missing value for field {name!r}")
        if values:
            raise TypeError(f"unknown fields: {', '.join(values)}")
        return self

    def __repr__(self) -> str:
        args = ", ".join(f"{name}={self.__dict__[name]!r}" for name in type(self).__fields__)
        return f"{type(self).__name__}({args})"

    def __eq__(self, other: object) -> bool:
        if type(other) is not type(self):
            return NotImplemented
        return self.__dict__ == other.__dict__
