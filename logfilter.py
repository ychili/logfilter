#!/usr/bin/python3
#
#  Copyright 2023 Dylan Maltby
#  SPDX-Licence-Identifier: Apache-2.0
#
"""Filter some logs using AWK.

Depends on:
-  AWK
-  GNU date
"""

from __future__ import annotations

import argparse
import functools
import glob
import logging
import os
import shlex
import shutil
import subprocess
import sys
from collections.abc import Iterable, Iterator, Mapping
from typing import Any, Callable, Union

__prog__ = "logfilter"
__version__ = "0.1.0"

CONFIG_PATH: str = "config"
LOG_LEVELS: list[str] = ["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"]
DEFAULTS: dict[str, str] = {
    "after": "today-3days",
    "before": "today+1day",
    "batch": "0",
    "datefmt": "+%Y-%m-%d",
    "level": "INFO",
    "logfiles": "~/.log/*.log",
    "program": "$1 > after && $1 <= before && $3 ~ level",
}
BOOLEAN_STATES: dict[str, bool] = {
    "1": True,
    "yes": True,
    "true": True,
    "on": True,
    "0": False,
    "no": False,
    "false": False,
    "off": False,
}

# Argument type for cmds of subprocess.run
Arg = Union[str, bytes, os.PathLike[str], os.PathLike[bytes]]


def disambiguate(
    names: Iterable[str], func: Callable[[str], str] = str
) -> Callable[[str], str]:
    """Return a function that can disambiguate a string between *names*.

    >>> disambiguate(LOG_LEVELS, str.upper)("warn")
    'WARNING'
    """

    def type_checker(value: str) -> str:
        value = func(value)
        candidates = [name for name in names if func(name).startswith(value)]
        if len(candidates) != 1:
            return value
        return candidates[0]

    return type_checker


def expand_paths(paths: str) -> Iterator[str]:
    for word in shlex.split(paths):
        word = os.path.expanduser(word)
        word = os.path.expandvars(word)
        yield from glob.iglob(word)


def convert_boolean(value: str) -> bool:
    return BOOLEAN_STATES.get(value.lower(), bool(value))


def build_cla_parser(defaults: Mapping[str, str]) -> argparse.ArgumentParser:
    """Build and return command-line argument parser."""
    parser = argparse.ArgumentParser(
        prog=__prog__, description="Filter some logs based on date and log level."
    )
    logfiles = defaults["logfiles"]
    parser.add_argument(
        "logfiles",
        nargs="*",
        default=expand_paths(logfiles),
        metavar="FILE",
        help=f"filter %(metavar)s(s) or default logfiles: {logfiles}",
    )
    parser.add_argument(
        "-a",
        "--after",
        default=defaults["after"],
        metavar="DATE",
        help="filter logs older than %(metavar)s (default: %(default)s)",
    )
    parser.add_argument(
        "-b",
        "--before",
        default=defaults["before"],
        metavar="DATE",
        help="filter logs newer than %(metavar)s (default: %(default)s)",
    )
    parser.set_defaults(batch=convert_boolean(defaults["batch"]))
    parser.add_argument(
        "--batch",
        action=argparse.BooleanOptionalAction,
        help="don't print headers giving file names",
    )
    parser.add_argument(
        "-l",
        "--level",
        type=disambiguate(LOG_LEVELS, str.upper),
        choices=LOG_LEVELS,
        default=defaults["level"],
        metavar="LEVEL",
        help="filter logs below %(metavar)s (choose from %(choices)s) (default: %(default)s)",
    )
    return parser


def main() -> None:
    if "LF_DEBUG" in os.environ:
        logging.basicConfig(level=logging.DEBUG)
    defaults = load_defaults(DEFAULTS)
    args = build_cla_parser(defaults).parse_args()
    logging.debug(args)
    logfiles = list(args.logfiles)
    if not logfiles:
        logging.debug("null glob")
        return
    level = "|".join(LOG_LEVELS[: LOG_LEVELS.index(args.level) + 1])
    start = datestr(args.after, defaults["datefmt"])
    end = datestr(args.before, defaults["datefmt"])
    awk_func = functools.partial(
        awk, program_text=defaults["program"], level=level, after=start, before=end
    )
    if args.batch:
        awk_func(files=logfiles)
        return
    for file in logfiles:
        print()
        print("==>", file, "<==")
        awk_func(files=[file])


def awk(files: Iterable[Arg], program_text: Arg, **variables: Any) -> None:
    """Call `awk` with the given arguments.

    ::
        awk [-v variables...] program_text [files...]
    """
    executable = shutil.which("awk") or die("awk: command not found")
    cmds = [executable]
    for var, value in variables.items():
        cmds += ["-v", f"{var}={value}"]
    cmds += ["--", program_text, *files]
    logging.debug(cmds)
    subprocess.run(cmds, check=True)


def load_config_paths(*resource: Union[str, os.PathLike[str]]) -> Iterator[str]:
    """
    Return an iterator which gives each directory named *resource* in the
    configuration search path. Information provided by earlier directories
    should take precedence over later ones.

    Procedure copied from:
    https://pyxdg.readthedocs.io/en/latest/_modules/xdg/BaseDirectory.html
    """
    xdg_config_home = os.environ.get("XDG_CONFIG_HOME") or os.path.join(
        os.path.expanduser("~"), ".config"
    )
    xdg_config_dirs = [xdg_config_home] + (
        os.environ.get("XDG_CONFIG_DIRS") or "/etc/xdg"
    ).split(":")
    resource_path = os.path.join(*resource)
    for config_dir in xdg_config_dirs:
        path = os.path.join(config_dir, resource_path)
        if os.path.exists(path):
            yield path


def load_defaults(defaults: dict[str, str]) -> dict[str, str]:
    """Merge *defaults* with k:v loaded from configuration files."""
    config_files = reversed(list(load_config_paths(__prog__, CONFIG_PATH)))
    for cfg in config_files:
        try:
            file = open(cfg)
        except OSError:
            logging.debug("found config file but couldn't open for reading: %s", cfg)
            continue
        with file:
            defaults.update(parse_kv_config(file))
            logging.debug("read configuration from file: %s", cfg)
    return defaults


def parse_kv_config(reader: Iterable[str]) -> dict[str, str]:
    symbols = {}
    for line in reader:
        line = line.lstrip()
        if line.startswith("#"):
            continue
        key, sep, val = line.partition("=")
        if not sep:
            continue
        symbols[key.strip().lower()] = val.strip()
    return symbols


def datestr(date: str, datefmt: str) -> str:
    """Call `date` with the given arguments and return its stdout as a string.

    ::
        $(date --date ${date} ${datefmt})
    """
    executable = shutil.which("date") or die("date: command not found")
    cmds = [executable, "--date", date, datefmt]
    proc = subprocess.run(cmds, check=True, stdout=subprocess.PIPE)
    return proc.stdout.decode().strip()


def die(message: str):
    print(f"{__prog__}: {message}", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
