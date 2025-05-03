#  Copyright 2025 Dylan Maltby
#  SPDX-Licence-Identifier: Apache-2.0
#
# pylint: disable=missing-function-docstring

"""End-to-end tests for logfilter"""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

import logfilter

if TYPE_CHECKING:
    from _typeshed import ReadableBuffer, StrPath


@pytest.fixture(autouse=True)
def debug_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LF_DEBUG", "1")


@pytest.fixture(autouse=True)
def isolate(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch out `load_config_paths`."""
    monkeypatch.setattr(logfilter, "load_config_paths", lambda *_: [])


@dataclasses.dataclass
class _FileWriter:
    """A function object to write some data to a temporary file."""

    tmp_dir: Path

    def __call__(
        self, contents: ReadableBuffer, filename: StrPath = "test.log"
    ) -> Path:
        path = self.tmp_dir / filename
        path.write_bytes(contents)
        return path


@pytest.fixture(name="filewriter")
def filewriter_fixture(tmp_path: Path) -> _FileWriter:
    return _FileWriter(tmp_path)


CONTENTS = [
    b"2025-04-27 20:27:00 NOTICE This log is too old\n",
    b"2025-04-28 16:54:44 INFO This log has a lower priority\n",
]


@pytest.mark.parametrize(
    ("options", "expected"),
    [
        ([], []),
        (["--after=2025-04-27"], CONTENTS[1:]),
        (["--after=2025-01-01", "--level=ERR"], []),
        (["--after=2025-01-01", "--level=notice"], CONTENTS[:1]),
    ],
)
def test_with_batch(
    filewriter: _FileWriter,
    capfdbinary: pytest.CaptureFixture[bytes],
    options: Sequence[str],
    expected: list[bytes],
):
    """Test the "happy path"."""
    log_path = filewriter(b"".join(CONTENTS))
    logfilter.main(["--batch", *options, str(log_path)])
    stdout, stderr = capfdbinary.readouterr()
    print(stdout)
    print(stderr)
    assert stdout == b"".join(expected)
