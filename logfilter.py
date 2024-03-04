#!/usr/bin/python3
#
#  Copyright 2023, 2024 Dylan Maltby
#  SPDX-Licence-Identifier: Apache-2.0
#
"""Filter some logs using AWK.

Depends on:
-  AWK
-  GNU date
"""

from __future__ import annotations

import argparse
import collections
import configparser
import fnmatch
import glob
import logging
import os
import shlex
import shutil
import subprocess
import sys
from collections.abc import Iterable, Iterator, Mapping, MutableMapping
from typing import Any, Callable, NoReturn, Optional, Union

__prog__ = "logfilter"
__version__ = "0.2.0.dev1"

CONFIG_PATH = "config"
LOGFILES_CONF_PATH = "logfiles.conf"
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
    """
    Split *paths* like a shell, and expand environment variables and globs.
    """
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
        default=list(expand_paths(logfiles)),
        metavar="FILE",
        help=f"filter %(metavar)s(s) or default logfiles: {logfiles}",
    )
    parser.add_argument(
        "-a",
        "--after",
        metavar="DATE",
        help="filter logs older than %(metavar)s",
    )
    parser.add_argument(
        "-b",
        "--before",
        metavar="DATE",
        help="filter logs newer than %(metavar)s",
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
        metavar="LEVEL",
        help="filter logs below %(metavar)s (choose from %(choices)s)",
    )
    return parser


def main() -> None:
    """Parsing arguments from sys.argv, print results to sys.stdout."""
    if "LF_DEBUG" in os.environ:
        logging.basicConfig(level=logging.DEBUG)
    general_defaults = load_defaults(DEFAULTS)
    cfg = configparser.ConfigParser(defaults=general_defaults, interpolation=None)
    try:
        read_configuration(cfg, LOGFILES_CONF_PATH)
    except configparser.Error as err:
        die(f"Error with configuration file: {err}")
    cfg_defaults = cfg.defaults()
    args = build_cla_parser(cfg_defaults).parse_args()
    logging.debug(args)
    logfiles = args.logfiles
    if not logfiles:
        logging.debug("null glob")
        return

    for logfile in logfiles:
        section = match_section(logfile, cfg) or cfg_defaults
        try:
            awk_variables = _set_awk_variables(args, section)
            awk_options = _set_awk_options(section)
        except configparser.Error as err:
            die(f"Error with configuration file: {err}")
        if not args.batch:
            print()
            print("==>", logfile, "<==")
            # Flush headers before awk starts writing
            sys.stdout.flush()
        awk(files=[logfile], **awk_options, variables=awk_variables)


def _set_awk_variables(
    args: argparse.Namespace, section: Mapping[str, str]
) -> dict[str, str]:
    awk_variables = {}
    level = args.level or section["level"]
    try:
        awk_variables["level"] = "|".join(LOG_LEVELS[: LOG_LEVELS.index(level) + 1])
    except ValueError:
        section_name = getattr(section, "name", "DEFAULT")
        die(f"In section [{section_name}]: invalid level name: {level}")
    awk_variables["after"] = datestr(args.after or section["after"], section["datefmt"])
    awk_variables["before"] = datestr(
        args.before or section["before"], section["datefmt"]
    )
    return awk_variables


def _set_awk_options(section: Mapping[str, str]) -> dict[str, str]:
    if progfile := section.get("progfile"):
        return {"progfiles": progfile}
    return {"program_text": section["program"]}


def awk(
    files: Iterable[Arg],
    program_text: Optional[Arg] = None,
    progfiles: Optional[Iterable[Arg]] = None,
    variables: Optional[Mapping[Any, Any]] = None,
    field_sep: Optional[Arg] = None,
    executable: Union[str, os.PathLike[str]] = "awk",
) -> int:
    """Call `awk` with the given arguments, returning its exit status.

    ::
        awk [-v variables...] [-F field_sep] [-f progfiles... | program_text]
            [files...]
    """
    executable = shutil.which(os.environ.get("LF_AWK", executable)) or die(
        f"{executable}: command not found"
    )
    cmds: list[Arg] = [executable]
    if variables is not None:
        for var, value in variables.items():
            cmds += ["-v", f"{var}={value}"]
    if field_sep is not None:
        cmds += ["-F", field_sep]
    if program_text is not None:
        cmds += ["--", program_text, *files]
    elif progfiles is not None:
        for program_file in progfiles:
            cmds += ["-f", program_file]
        cmds += ["--", *files]
    logging.debug(cmds)
    try:
        proc = subprocess.run(cmds, check=True)
    except subprocess.CalledProcessError as err:
        die(str(err))
    return proc.returncode


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


def load_defaults(defaults: MutableMapping[str, str]) -> collections.ChainMap[str, str]:
    """Merge *defaults* with k:v loaded from configuration files."""
    maps = []
    for cfg in load_config_paths(__prog__, CONFIG_PATH):
        try:
            file = open(cfg, encoding="utf-8")
        except OSError:
            logging.debug("found config file but couldn't open for reading: %s", cfg)
            continue
        with file:
            maps.append(parse_kv_config(file))
            logging.debug("read configuration from file: %s", cfg)
    return collections.ChainMap(*maps, defaults)


def read_configuration(
    config: configparser.ConfigParser, pathname: Union[str, os.PathLike[str]]
) -> list[str]:
    """Load configuration files into *config*.

    Return a list of files read.
    """
    cfgs = list(load_config_paths(__prog__, pathname))
    files_read = config.read(reversed(cfgs))
    logging.debug("read configuration from files: %s", files_read)
    return files_read


def match_section(
    name: str, config: configparser.ConfigParser
) -> Optional[configparser.SectionProxy]:
    """Return a section of config if its name fnmatches *name*."""
    for section in config.sections():
        if fnmatch.fnmatch(name, section):
            return config[section]
    return None


def parse_kv_config(reader: Iterable[str]) -> dict[str, str]:
    """Return a dict of keys to values parsed from lines of text in *reader*.

    Simple syntax:
      - Keys separated from values by '='
      - Comments starting with '#'
      - Each line either a key–value pair or a comment
      - External whitespace ignored
    """
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


def datestr(date: Optional[str] = None, datefmt: Optional[str] = None) -> str:
    """Call `date` with the given arguments and return its stdout as a string.

    ::
        $(date [--date ${date}] [${datefmt}])
    """
    executable = shutil.which("date") or die("date: command not found")
    cmds = [executable]
    if date is not None:
        cmds += ["--date", date]
    if datefmt is not None:
        cmds.append(datefmt)
    try:
        proc = subprocess.run(cmds, check=True, stdout=subprocess.PIPE)
    except subprocess.CalledProcessError as err:
        die(str(err))
    return proc.stdout.decode().strip()


def die(message: str) -> NoReturn:
    print(f"{__prog__}: {message}", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
