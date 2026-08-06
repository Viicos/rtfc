import pytest

from rtfc._changelog import ChangelogError, insert_version
from rtfc._format import RstFormat

RST = RstFormat()

CHANGELOG = """\
Changelog
=========

.. rtfc-insert

v1.0.0 (2025-07-01)
-------------------

- An older change.
"""

BLOCK = "v1.1.0 (2025-08-01)\n-------------------\n\n- A new change."


def test_insert_version() -> None:
    assert insert_version(CHANGELOG, BLOCK, fmt=RST) == (
        "Changelog\n"
        "=========\n"
        "\n"
        ".. rtfc-insert\n"
        "\n"
        "v1.1.0 (2025-08-01)\n"
        "-------------------\n"
        "\n"
        "- A new change.\n"
        "\n"
        "v1.0.0 (2025-07-01)\n"
        "-------------------\n"
        "\n"
        "- An older change.\n"
    )


def test_insert_version_marker_at_end() -> None:
    changelog = "Changelog\n=========\n\n.. rtfc-insert\n"

    assert insert_version(changelog, BLOCK, fmt=RST) == (
        "Changelog\n=========\n\n.. rtfc-insert\n\nv1.1.0 (2025-08-01)\n-------------------\n\n- A new change.\n"
    )


def test_insert_version_missing_marker() -> None:
    with pytest.raises(ChangelogError, match=r"missing the '\.\. rtfc-insert' insert marker"):
        insert_version("Changelog\n=========\n", BLOCK, fmt=RST)


def test_insert_version_leaves_rest_untouched() -> None:
    result = insert_version(CHANGELOG, BLOCK, fmt=RST)

    assert result.startswith("Changelog\n=========\n\n.. rtfc-insert\n")
    assert result.endswith("- An older change.\n")


def test_trailing_newline_added() -> None:
    changelog = "Changelog\n=========\n\n.. rtfc-insert"

    assert insert_version(changelog, BLOCK, fmt=RST).endswith("- A new change.\n")
