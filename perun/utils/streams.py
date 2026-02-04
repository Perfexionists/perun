"""Functions for loading and working with streams (e.g. yaml)

Some of the stuff are stored in the stream, like e.g. yaml and are reused in several places.
This module encapsulates such functions, so they can be used in CLI, in tests, in configs.
"""

from __future__ import annotations

# Standard Imports
import contextlib
import gzip
import io
import json
import os
from pathlib import Path
import re
from typing import Any, BinaryIO, Iterator, IO, Literal, TextIO, TYPE_CHECKING, overload
import zlib

if TYPE_CHECKING:
    from _typeshed import OpenBinaryMode, OpenTextMode

# Third-Party Imports
from ruamel.yaml import YAML

# Perun Imports
from perun.utils import log

GzBinaryMode = Literal["r", "rb", "w", "wb", "x", "xb", "a", "ab"]
GzTextMode = Literal["rt", "wt", "xt", "at"]


def store_json(profile: dict[Any, Any], file_path: str) -> None:
    """Stores profile w.r.t. :ref:`profile-spec` to output file.

    :param profile: dictionary with profile w.r.t. :ref:`profile-spec`
    :param file_path: output path, where the `profile` will be stored
    """
    with open(file_path, "w") as profile_handle:
        serialized_profile = json.dumps(profile, indent=2)
        serialized_profile = re.sub(r",\s+(\d+)", r", \1", serialized_profile)
        profile_handle.write(serialized_profile)


def safely_load_yaml_from_file(yaml_file: str) -> dict[Any, Any]:
    """
    :param yaml_file: name of the yaml file
    :raises ruamel.yaml.scanner.ScannerError: when the input file contains error
    """
    if not os.path.exists(yaml_file):
        log.warn(f"yaml source file '{yaml_file}' does not exist")
        return {}

    with open(yaml_file, "r") as yaml_handle:
        return safely_load_yaml_from_stream(yaml_handle)


def safely_load_yaml_from_stream(yaml_stream: TextIO | str) -> dict[Any, Any]:
    """
    :param yaml_stream: stream in the yaml format (or not)
    :raises ruamel.yaml.scanner.ScannerError: when the input file contains error
    """
    # Remove the trailing double quotes screwing correct loading of yaml
    if isinstance(yaml_stream, str) and yaml_stream[0] == '"' and yaml_stream[-1] == '"':
        yaml_stream = yaml_stream[1:-1]
    try:
        loaded_yaml = YAML().load(yaml_stream)
        return loaded_yaml or {}
    except Exception as exc:
        log.warn(f"malformed yaml stream: {exc}")
        return {}


def safely_load_yaml(yaml_source: str) -> dict[Any, Any]:
    """Wrapper which takes the yaml source and either load it from the file or from the string

    :param yaml_source: either string or name of the file
    :raises ruamel.yaml.scanner.ScannerError: when the input file contains error
    """
    if os.path.exists(yaml_source):
        return safely_load_yaml_from_file(yaml_source)
    return safely_load_yaml_from_stream(yaml_source)


def yaml_to_string(dictionary: dict[Any, Any]) -> str:
    """Converts the dictionary representing the YAML into string

    :param dictionary: yaml stored as dictionary
    :return: string representation of the yaml
    """
    string_stream = io.StringIO()
    yaml_dumper = YAML()
    yaml_dumper.dump(dictionary, string_stream)
    string_stream.seek(0)
    return "".join([" " * 4 + s for s in string_stream.readlines()])


def safely_load_file(filename: str) -> list[str]:
    """Safely reads filename. In case of Unicode errors, returns empty list.

    :param filename: read filename
    :return: list of read lines
    """
    with open(filename, "r") as file_handle:
        try:
            return file_handle.readlines()
        except UnicodeDecodeError as ude:
            log.warn(f"Could not decode '{filename}': {ude}")
            return []


@overload
@contextlib.contextmanager
def safely_open_and_log(
    file_path: Path,
    mode: OpenTextMode,
    fatal_fail: Literal[False] = ...,
    success_msg: str = ...,
    fail_msg: str = ...,
    **open_args: Any,
) -> Iterator[TextIO | None]: ...


@overload
@contextlib.contextmanager
def safely_open_and_log(
    file_path: Path,
    mode: OpenBinaryMode,
    fatal_fail: Literal[False] = ...,
    success_msg: str = ...,
    fail_msg: str = ...,
    **open_args: Any,
) -> Iterator[BinaryIO | None]: ...


@overload
@contextlib.contextmanager
def safely_open_and_log(
    file_path: Path,
    mode: OpenTextMode,
    *,
    fatal_fail: Literal[True],
    success_msg: str = ...,
    fail_msg: str = ...,
    **open_args: Any,
) -> Iterator[TextIO]: ...


@overload
@contextlib.contextmanager
def safely_open_and_log(
    file_path: Path,
    mode: OpenBinaryMode,
    *,
    fatal_fail: Literal[True],
    success_msg: str = ...,
    fail_msg: str = ...,
    **open_args: Any,
) -> Iterator[BinaryIO]: ...


@contextlib.contextmanager
def safely_open_and_log(
    file_path: Path,
    mode: str,
    fatal_fail: bool = False,
    success_msg: str = "found",
    fail_msg: str = "not found",
    **open_args: Any,
) -> Iterator[IO[Any] | None]:
    """Attempt to safely open a file and log a success or failure message.

    If fatal_fail is specified as True, the function will either return a valid file handle or
    terminate the program; a None value will never be returned if fatal_fail is True.

    When providing a fatal_fail parameter value, it needs to be written with a keyword, e.g.,
    safely_open_and_log(path, mode, fatal_fail=True) to conform to the expected call signature
    given how mypy currently handles overloads for parameters with default values.
    See this mypy issue for more details: https://github.com/python/mypy/issues/7333

    :param file_path: path to the file to open.
    :param mode: file opening mode.
    :param fatal_fail: specifies whether failing to open a file should terminate the program.
    :param success_msg: a log message when the file has been successfully opened.
    :param fail_msg: a log message when the file could not be opened.
    :param open_args: additional arguments to pass to the open function.

    :return: a file handle or None, depending on the success of opening the file.
    """
    try:
        with open(file_path, mode, **open_args) as f_handle:
            log.minor_success(log.path_style(str(file_path)), success_msg)
            yield f_handle
    except OSError as exc:
        log.minor_fail(log.path_style(str(file_path)), fail_msg)
        if fatal_fail:
            log.error(str(exc), exc)
        yield None


@overload
@contextlib.contextmanager
def safely_open_and_log_gz(
    file_path: Path,
    mode: GzTextMode,
    fatal_fail: Literal[False] = ...,
    success_msg: str = ...,
    fail_msg: str = ...,
    **open_args: Any,
) -> Iterator[TextIO | None]: ...


@overload
@contextlib.contextmanager
def safely_open_and_log_gz(
    file_path: Path,
    mode: GzBinaryMode,
    fatal_fail: Literal[False] = ...,
    success_msg: str = ...,
    fail_msg: str = ...,
    **open_args: Any,
) -> Iterator[gzip.GzipFile | None]: ...


@overload
@contextlib.contextmanager
def safely_open_and_log_gz(
    file_path: Path,
    mode: GzTextMode,
    *,
    fatal_fail: Literal[True],
    success_msg: str = ...,
    fail_msg: str = ...,
    **open_args: Any,
) -> Iterator[TextIO]: ...


@overload
@contextlib.contextmanager
def safely_open_and_log_gz(
    file_path: Path,
    mode: GzBinaryMode,
    *,
    fatal_fail: Literal[True],
    success_msg: str = ...,
    fail_msg: str = ...,
    **open_args: Any,
) -> Iterator[gzip.GzipFile]: ...


@contextlib.contextmanager
def safely_open_and_log_gz(
    file_path: Path,
    mode: GzTextMode | GzBinaryMode,
    fatal_fail: bool = False,
    success_msg: str = "found",
    fail_msg: str = "not found",
    **open_args: Any,
) -> Iterator[TextIO | gzip.GzipFile | None]:
    """Attempt to safely open a gzipped file and log a success or failure message.

    The gzipped file may be opened in binary or text mode. The text mode allows iteration over
    the lines of the file without the need to load the entire file into the memory.

    If the file is not a valid gzipped file, the function either returns a None or terminates the
    program depending on the fatal_fail parameter value. If fatal_fail is specified as True, the
    function will either return a valid file handle or terminate the program; a None value will
    never be returned if fatal_fail is True.

    When providing a fatal_fail parameter value, it needs to be written with a keyword, e.g.,
    safely_open_and_log_gz(path, mode, fatal_fail=True) to conform to the expected call signature
    given how mypy currently handles overloads for parameters with default values.
    See this mypy issue for more details: https://github.com/python/mypy/issues/7333

    :param file_path: path to the gzip file to open.
    :param mode: file opening mode.
    :param fatal_fail: specifies whether failing to open a file should terminate the program.
    :param success_msg: a log message when the file has been successfully opened.
    :param fail_msg: a log message when the file could not be opened.
    :param open_args: additional arguments to pass to the open function.

    :return: a file handle or None, depending on the success of opening the file.
    """
    try:
        with gzip.open(file_path, mode, **open_args) as gz_handle:
            log.minor_success(log.path_style(str(file_path)), success_msg)
            # The file has been successfully opened, but decompression errors might still happen
            fail_msg = "reading failed"
            yield gz_handle
    except (OSError, gzip.BadGzipFile, EOFError, zlib.error) as exc:
        # This will either print the original fail_msg if opening the file failed, or the updated
        # fail_msg if reading and decompressing the file failed for some reason.
        log.minor_fail(log.path_style(str(file_path)), fail_msg)
        if fatal_fail:
            log.error(str(exc), exc)
        yield None
