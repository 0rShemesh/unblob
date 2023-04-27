import hashlib
import os
import stat
import statistics
import traceback
from enum import Enum
from pathlib import Path
from typing import List, Optional, Union, final

import attr


@attr.define(kw_only=True, frozen=True)
class Report:
    """A common base class for different reports."""

    def asdict(self) -> dict:
        return attr.asdict(self)


class Severity(Enum):
    """Represents possible problems encountered during execution."""

    ERROR = "ERROR"
    WARNING = "WARNING"


@attr.define(kw_only=True)
class ErrorReport(Report):
    severity: Severity


STR = Union[str, Exception]
"""STR is a workaround for UnknownError.exception & pyright, do not use elsewhere!

Note, that when you inline this type, the documentation for UnknownError.exception
as generated by pyright will be wrong.
It will also break the formatting for `black`, which is a big issue, as we have
a pyright comment there to work around pyright.

See:
    - https://www.attrs.org/en/stable/types.html#pyright
    - https://github.com/microsoft/pyright/blob/main/docs/comments.md#line-level-diagnostic-suppression

"""


def _convert_exception_to_str(obj: Union[str, Exception]) -> str:
    if isinstance(obj, str):
        return obj
    if isinstance(obj, Exception):
        e: Exception = obj
        return "".join(traceback.format_exception(type(e), e, e.__traceback__))
    raise ValueError("Invalid exception object", obj)


@attr.define(kw_only=True)
class UnknownError(ErrorReport):
    """Describes an exception raised during file processing."""

    severity: Severity = attr.field(default=Severity.ERROR)
    exception: STR = attr.field(  # pyright: reportGeneralTypeIssues=false
        converter=_convert_exception_to_str
    )
    """Exceptions are also formatted at construct time.

    `attrs` is not integrated enough with type checker/LSP provider `pyright` to include converters.

    See: https://www.attrs.org/en/stable/types.html#pyright
    """


@attr.define(kw_only=True)
class CalculateChunkExceptionReport(UnknownError):
    """Describes an exception raised during calculate_chunk execution."""

    start_offset: int
    # Stored in `str` rather than `Handler`, because the pickle picks ups structs from `C_DEFINITIONS`
    handler: str


@attr.define(kw_only=True)
class ExtractCommandFailedReport(ErrorReport):
    """Describes an error when failed to run the extraction command."""

    severity: Severity = Severity.WARNING
    command: str
    stdout: bytes
    stderr: bytes
    exit_code: int


@attr.define(kw_only=True)
class ExtractDirectoryExistsReport(ErrorReport):
    severity: Severity = Severity.ERROR
    path: Path


@attr.define(kw_only=True)
class ExtractorDependencyNotFoundReport(ErrorReport):
    """Describes an error when the dependency of an extractor doesn't exist."""

    severity: Severity = Severity.ERROR
    dependencies: List[str]


@attr.define(kw_only=True)
class MaliciousSymlinkRemoved(ErrorReport):
    """Describes an error when malicious symlinks have been removed from disk."""

    severity: Severity = Severity.WARNING
    link: str
    target: str


@attr.define(kw_only=True)
class StatReport(Report):
    path: Path
    size: int
    is_dir: bool
    is_file: bool
    is_link: bool
    link_target: Optional[Path]

    @classmethod
    def from_path(cls, path: Path):
        st = path.lstat()
        mode = st.st_mode
        try:
            link_target = Path(os.readlink(path))
        except OSError:
            link_target = None

        return cls(
            path=path,
            size=st.st_size,
            is_dir=stat.S_ISDIR(mode),
            is_file=stat.S_ISREG(mode),
            is_link=stat.S_ISLNK(mode),
            link_target=link_target,
        )


@attr.define(kw_only=True)
class HashReport(Report):
    md5: str
    sha1: str
    sha256: str

    @classmethod
    def from_path(cls, path: Path):
        chunk_size = 1024 * 64
        md5 = hashlib.md5()  # noqa: S324
        sha1 = hashlib.sha1()  # noqa: S324
        sha256 = hashlib.sha256()

        with path.open("rb") as f:
            while chunk := f.read(chunk_size):
                md5.update(chunk)
                sha1.update(chunk)
                sha256.update(chunk)

        return cls(
            md5=md5.hexdigest(),
            sha1=sha1.hexdigest(),
            sha256=sha256.hexdigest(),
        )


@attr.define(kw_only=True)
class FileMagicReport(Report):
    magic: str
    mime_type: str


@attr.define(kw_only=True)
class EntropyReport(Report):
    percentages: List[float]
    block_size: int

    @property
    def mean(self):
        return statistics.mean(self.percentages)

    @property
    def highest(self):
        return max(self.percentages)

    @property
    def lowest(self):
        return min(self.percentages)


@final
@attr.define(kw_only=True)
class ChunkReport(Report):
    chunk_id: str
    handler_name: str
    start_offset: int
    end_offset: int
    size: int
    is_encrypted: bool
    extraction_reports: List[Report]


@final
@attr.define(kw_only=True)
class UnknownChunkReport(Report):
    chunk_id: str
    start_offset: int
    end_offset: int
    size: int
    entropy: Optional[EntropyReport]
