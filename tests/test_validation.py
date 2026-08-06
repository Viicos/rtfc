import datetime
from pathlib import Path

import pytest

from rtfc._validation import (
    Field,
    Issue,
    Schema,
    ValidationContext,
    ValidationError,
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

CTX = ValidationContext()


class Inner(Schema):
    name = Field(str_)


class Outer(Schema):
    req = Field(int_)
    opt = Field(str_, default="d")
    items = Field(list_of(int_), default_factory=list)
    inner = Field(Inner)
    maybe = Field(nullable(str_), default=None)


def issues(exc_info: pytest.ExceptionInfo[ValidationError]) -> list[tuple[tuple[str | int, ...], str]]:
    return [(issue.path, issue.message) for issue in exc_info.value.issues]


def test_issue_str() -> None:
    assert str(Issue((), "msg")) == "<root>: msg"
    assert str(Issue(("a", 0, "b"), "msg")) == "a[0].b: msg"


def test_bool() -> None:
    assert bool_.validate(True, CTX) is True
    with pytest.raises(ValidationError, match="expected bool, got int"):
        bool_.validate(1, CTX)


def test_int() -> None:
    assert int_.validate(3, CTX) == 3
    with pytest.raises(ValidationError, match="expected int, got str"):
        int_.validate("3", CTX)


def test_int_rejects_bool() -> None:
    with pytest.raises(ValidationError, match="expected int, got bool"):
        int_.validate(True, CTX)


def test_str() -> None:
    assert str_.validate("a", CTX) == "a"
    with pytest.raises(ValidationError, match="expected str, got NoneType"):
        str_.validate(None, CTX)


def test_float() -> None:
    assert float_.validate(1.5, CTX) == 1.5
    with pytest.raises(ValidationError, match="expected float, got str"):
        float_.validate("1.5", CTX)


def test_float_converts_int() -> None:
    value = float_.validate(1, CTX)
    assert type(value) is float
    assert value == 1.0


def test_float_rejects_bool() -> None:
    with pytest.raises(ValidationError, match="expected float, got bool"):
        float_.validate(True, CTX)


def test_iso_date() -> None:
    assert iso_date.validate(datetime.date(2025, 8, 1), CTX) == datetime.date(2025, 8, 1)
    assert iso_date.validate("2025-08-01", CTX) == datetime.date(2025, 8, 1)


def test_iso_date_rejects_datetime() -> None:
    with pytest.raises(ValidationError, match="expected ISO date, got datetime"):
        iso_date.validate(datetime.datetime(2025, 8, 1), CTX)


def test_iso_date_invalid_string() -> None:
    with pytest.raises(ValidationError, match="invalid ISO date: 'not-a-date'"):
        iso_date.validate("not-a-date", CTX)


def test_any() -> None:
    value = object()
    assert any_.validate(value, CTX) is value


def test_nullable() -> None:
    validator = nullable(str_)
    assert validator.validate(None, CTX) is None
    assert validator.validate("a", CTX) == "a"
    with pytest.raises(ValidationError, match="expected str, got int"):
        validator.validate(1, CTX)


def test_list_of_rejects_non_list() -> None:
    with pytest.raises(ValidationError, match="expected list, got str"):
        list_of(str_).validate("abc", CTX)


def test_list_of_collects_item_issues() -> None:
    with pytest.raises(ValidationError) as exc_info:
        list_of(str_).validate(["a", 1, None], ValidationContext(path=("k",)))
    assert issues(exc_info) == [
        (("k", 1), "expected str, got int"),
        (("k", 2), "expected str, got NoneType"),
    ]


def test_dict_of_rejects_non_mapping() -> None:
    with pytest.raises(ValidationError, match="expected table, got list"):
        dict_of(str_).validate([], CTX)


def test_dict_of_rejects_non_string_keys() -> None:
    with pytest.raises(ValidationError, match="expected string key, got 1"):
        dict_of(int_).validate({1: 2}, CTX)


def test_dict_of_collects_value_issues() -> None:
    with pytest.raises(ValidationError) as exc_info:
        dict_of(int_).validate({"a": 1, "b": "x", "c": None}, CTX)
    assert issues(exc_info) == [
        (("b",), "expected int, got str"),
        (("c",), "expected int, got NoneType"),
    ]


def test_dict_of_nested_schema() -> None:
    result = dict_of(Inner).validate({"x": {"name": "n"}}, CTX)
    assert result["x"].name == "n"


def test_schema_validate() -> None:
    outer = Outer.validate({"req": 1, "opt": "o", "items": [1, 2], "inner": {"name": "n"}, "maybe": "m"})
    assert outer.req == 1
    assert outer.opt == "o"
    assert outer.items == [1, 2]
    assert outer.inner.name == "n"
    assert outer.maybe == "m"


def test_schema_defaults() -> None:
    outer = Outer.validate({"req": 1, "inner": {"name": "n"}})
    assert outer.opt == "d"
    assert outer.items == []
    assert outer.maybe is None


def test_schema_default_factory_not_shared() -> None:
    first = Outer.validate({"req": 1, "inner": {"name": "n"}})
    second = Outer.validate({"req": 1, "inner": {"name": "n"}})
    assert first.items is not second.items


def test_schema_rejects_non_mapping() -> None:
    with pytest.raises(ValidationError, match="expected table, got list"):
        Outer.validate([])


def test_schema_collects_issues() -> None:
    with pytest.raises(ValidationError) as exc_info:
        Outer.validate({"opt": 1, "items": [1, "x"], "inner": {"name": 2}, "typo": True})
    assert issues(exc_info) == [
        (("req",), "missing required key"),
        (("opt",), "expected str, got int"),
        (("items", 1), "expected int, got str"),
        (("inner", "name"), "expected str, got int"),
        (("typo",), "unknown key"),
    ]


def test_schema_nested_path_prefix() -> None:
    with pytest.raises(ValidationError) as exc_info:
        Outer.validate({"req": 1, "inner": []}, ValidationContext(path=("tool", "rtfc")))
    assert issues(exc_info) == [(("tool", "rtfc", "inner"), "expected table, got list")]


def test_schema_inheritance() -> None:
    class Sub(Outer):
        extra = Field(bool_, default=True)

    sub = Sub.validate({"req": 1, "inner": {"name": "n"}})
    assert sub.req == 1
    assert sub.extra is True


def test_schema_no_direct_instantiation() -> None:
    with pytest.raises(TypeError, match="cannot be instantiated directly"):
        Inner()


def test_schema_frozen() -> None:
    inner = Inner.validate({"name": "n"})
    with pytest.raises(AttributeError, match="'Inner' instances are frozen"):
        inner.name = "other"  # pyright: ignore[reportAttributeAccessIssue]


def test_schema_class_level_field_access() -> None:
    assert isinstance(Inner.name, Field)


def test_schema_repr() -> None:
    assert repr(Inner.validate({"name": "n"})) == "Inner(name='n')"


def test_schema_eq() -> None:
    class Other(Schema):
        name = Field(str_)

    assert Inner.validate({"name": "n"}) == Inner.validate({"name": "n"})
    assert Inner.validate({"name": "n"}) != Inner.validate({"name": "m"})
    assert Inner.validate({"name": "n"}) != Other.validate({"name": "n"})


def test_construct() -> None:
    outer = Outer.construct(req=1, inner=Inner.construct(name="n"))
    assert outer.req == 1
    assert outer.opt == "d"
    assert outer.items == []
    assert outer.inner.name == "n"


def test_construct_skips_validation() -> None:
    inner = Inner.construct(name=42)
    assert inner.name == 42  # pyright: ignore[reportUnnecessaryComparison]


def test_construct_missing_required() -> None:
    with pytest.raises(TypeError, match="missing value for field 'name'"):
        Inner.construct()


def test_construct_unknown_field() -> None:
    with pytest.raises(TypeError, match="unknown fields: typo"):
        Inner.construct(name="n", typo=1)


def test_field_default_and_factory_mutually_exclusive() -> None:
    with pytest.raises(TypeError, match="mutually exclusive"):
        Field(str_, default="a", default_factory=lambda: "b")


def test_paths_resolved_against_context_directory(tmp_path: Path) -> None:
    (tmp_path / "f.txt").touch()
    (tmp_path / "sub").mkdir()
    context = ValidationContext(current_directory=tmp_path)
    assert file_path.validate("f.txt", context) == tmp_path / "f.txt"
    assert dir_path.validate(Path("sub"), context) == tmp_path / "sub"
    with pytest.raises(ValidationError, match="expected path, got int"):
        file_path.validate(1, context)


def test_paths_must_exist(tmp_path: Path) -> None:
    context = ValidationContext(current_directory=tmp_path)
    with pytest.raises(ValidationError, match=r"path 'missing\.txt' does not exist"):
        file_path.validate("missing.txt", context)
    with pytest.raises(ValidationError, match=r"path 'missing' does not exist"):
        dir_path.validate("missing", context)


def test_paths_kind_checked(tmp_path: Path) -> None:
    (tmp_path / "f.txt").touch()
    (tmp_path / "sub").mkdir()
    context = ValidationContext(current_directory=tmp_path)
    with pytest.raises(ValidationError, match="path 'sub' is not a file"):
        file_path.validate("sub", context)
    with pytest.raises(ValidationError, match=r"path 'f\.txt' is not a directory"):
        dir_path.validate("f.txt", context)


def test_record() -> None:
    validator = record({"a": Field(int_), "b": Field(str_, default="d")})

    assert validator.validate({"a": 1}, CTX) == {"a": 1, "b": "d"}


def test_record_collects_issues() -> None:
    validator = record({"a": Field(int_), "b": Field(str_, default="d")})

    with pytest.raises(ValidationError) as exc_info:
        validator.validate({"b": 1, "typo": True}, ValidationContext(path=("metadata",)))

    assert issues(exc_info) == [
        (("metadata", "a"), "missing required key"),
        (("metadata", "b"), "expected str, got int"),
        (("metadata", "typo"), "unknown key"),
    ]


def test_record_rejects_non_mapping() -> None:
    with pytest.raises(ValidationError, match="expected table, got list"):
        record({}).validate([], CTX)


def test_one_of() -> None:
    validator = one_of("string", "integer")

    assert validator.validate("string", CTX) == "string"
    with pytest.raises(ValidationError, match="expected one of 'string', 'integer', got 'typo'"):
        validator.validate("typo", CTX)


def test_one_of_exact_types() -> None:
    with pytest.raises(ValidationError, match="expected one of 0, 1, got True"):
        one_of(0, 1).validate(True, CTX)


def test_one_of_requires_values() -> None:
    with pytest.raises(TypeError, match="at least one value"):
        one_of()


def test_schema_post_validate() -> None:
    class Exclusive(Schema):
        a = Field(nullable(int_), default=None)
        b = Field(nullable(int_), default=None)

        def __post_validate__(self, context: ValidationContext) -> None:
            if self.a is not None and self.b is not None:
                raise ValidationError.single(context.path, "'a' and 'b' are mutually exclusive")

    assert Exclusive.validate({"a": 1}).a == 1
    with pytest.raises(ValidationError, match="nested: 'a' and 'b' are mutually exclusive"):
        Exclusive.validate({"a": 1, "b": 2}, ValidationContext(path=("nested",)))


def test_schema_post_validate_skipped_on_field_issues() -> None:
    class Checked(Schema):
        a = Field(int_)

        def __post_validate__(self, context: ValidationContext) -> None:
            raise AssertionError("should not run")

    with pytest.raises(ValidationError) as exc_info:
        Checked.validate({"a": "x"})

    assert issues(exc_info) == [(("a",), "expected int, got str")]


def test_schema_post_validate_not_called_by_construct() -> None:
    class Checked(Schema):
        a = Field(int_)

        def __post_validate__(self, context: ValidationContext) -> None:
            raise AssertionError("should not run")

    assert Checked.construct(a=1).a == 1


def test_default_factory_with_context(tmp_path: Path) -> None:
    class WithPath(Schema):
        directory = Field(dir_path, default_factory=lambda context: context.current_directory / "sub")

    (tmp_path / "sub").mkdir()
    schema = WithPath.validate({}, ValidationContext(current_directory=tmp_path))

    assert schema.directory == tmp_path / "sub"


def test_defaults_are_validated() -> None:
    class WithBadDefault(Schema):
        count = Field(int_, default="x")  # pyright: ignore[reportArgumentType]

    with pytest.raises(ValidationError) as exc_info:
        WithBadDefault.validate({})

    assert issues(exc_info) == [(("count",), "expected int, got str")]


def test_schema_instances_passed_through() -> None:
    inner = Inner.validate({"name": "n"})

    assert Inner.validate(inner) is inner
