#!/usr/bin/python3
#
#  Copyright 2023–2026 Dylan Maltby
#  SPDX-Licence-Identifier: Apache-2.0
#
# pylint: disable=missing-class-docstring,missing-function-docstring

"""Unit tests for logfilter"""

import configparser
import functools
import os
import os.path
import shutil
import tempfile
import unittest

import logfilter


class TestDisambiguate(unittest.TestCase):
    _NAMES = frozenset({"a", "aa", "ab", "ac", "ade"})

    def test_checker(self) -> None:
        checker = logfilter.disambiguate(self._NAMES)
        self.assertEqual(checker("b"), "b")
        self.assertEqual(checker("a"), "a")
        self.assertEqual(checker("aa"), "aa")
        self.assertEqual(checker("ad"), "ade")

    def test_no_copy(self) -> None:
        checker = logfilter.disambiguate(iter(self._NAMES))
        self.assertEqual(checker("ad"), "ade")
        self.assertEqual(checker("ad"), "ad")


class TestLoadConfigPaths(unittest.TestCase):
    def setUp(self) -> None:
        self.environ_save = os.environ.copy()

    def tearDown(self) -> None:
        # Restore environment variables.
        # Assigning to os.environ does not clear the environment.
        # Therefore, set values one by one.
        os.environ.clear()
        for name, value in self.environ_save.items():
            os.environ[name] = value

    def test_load_config_paths(self) -> None:
        """
        Procedure adapted from:
        https://github.com/takluyver/pyxdg/blob/master/test/test_basedirectory.py#L81
        """
        _dirname = "test_load_config_paths0"
        tmpdir0 = tempfile.TemporaryDirectory()
        home_path = os.path.join(tmpdir0.name, _dirname)
        tmpdir1 = tempfile.TemporaryDirectory()
        etc_path = os.path.join(tmpdir1.name, _dirname)
        with tmpdir0, tmpdir1:
            os.mkdir(home_path)
            os.mkdir(etc_path)
            os.environ["XDG_CONFIG_HOME"] = tmpdir0.name
            os.environ["XDG_CONFIG_DIRS"] = f"{tmpdir1.name}:/etc/xdg"
            config_dirs = logfilter.load_config_paths(_dirname)
            self.assertEqual(list(config_dirs), [home_path, etc_path])


class TestMatchSection(unittest.TestCase):
    def setUp(self) -> None:
        self.config = configparser.ConfigParser(interpolation=None)
        self.func = functools.partial(
            logfilter.get_matching_settings, config=self.config
        )

    def test_redundant_default(self) -> None:
        self.assertFalse(self.func(""), "An empty config won't ever match.")
        self.config.read_dict({"DEFAULT": {"1": "default"}, "*": {"2": "*"}})
        all_defaults = self.func("")
        self.assertEqual(all_defaults["1"], "default")
        self.assertEqual(all_defaults["2"], "*")
        self.config.read_dict({"ab*": {"3": "ab*"}})
        matched_settings = self.func("abc")
        self.assertEqual(matched_settings["1"], "default")
        self.assertEqual(matched_settings["2"], "*")
        self.assertEqual(matched_settings["3"], "ab*")

    def test_later_override(self) -> None:
        self.config.read_dict({"DEFAULT": {"1": "default"}})
        self.assertFalse(self.func(""), "A DEFAULT-only config won't ever match.")
        self.config.read_dict({"b": {"2": "b"}})
        one_section = self.func("b")
        self.assertEqual(one_section["1"], "default")
        self.assertEqual(one_section["2"], "b")
        self.config.read_dict({"*": {"2": "*"}})
        overridden = self.func("b")
        self.assertEqual(overridden["1"], "default")
        self.assertEqual(overridden["2"], "*")


class TestKVParse(unittest.TestCase):
    basic = r"""
    # Each line in this string is indented, but that shouldn't matter.
    key1="${HOME}"/logs

    """.splitlines(
        keepends=True
    )
    trailing = ["key1=value    \n", "key2=value  # This comment is not discarded\n"]
    spacing = ["  NormalKey = No line breaks please\n", "  Key With Spaces = Value\n"]
    punctuation = ["EqualsSign = 2 + 2 = 4\n", "\n"]
    empty = ["  \n", "  KeyWithNoValue = \n", "   = Value with no key\n", "   =\n"]
    ignore = [
        "    # Comments = good \n",
        "Any line without an equals sign will also be ignored.\n",
    ]

    func = staticmethod(logfilter.parse_kv_config)

    def test_basic(self) -> None:
        results = self.func(self.basic)
        self.assertEqual(results, {"key1": '"${HOME}"/logs'})

    def test_trailing(self) -> None:
        results = self.func(self.trailing)
        self.assertEqual(
            results, {"key1": "value", "key2": "value  # This comment is not discarded"}
        )

    def test_spacing(self) -> None:
        results = self.func(self.spacing)
        self.assertEqual(
            results, {"normalkey": "No line breaks please", "key with spaces": "Value"}
        )

    def test_punctuation(self) -> None:
        results = self.func(self.punctuation)
        self.assertEqual(results, {"equalssign": "2 + 2 = 4"})

    def test_empty_components(self) -> None:
        results = self.func(self.empty)
        self.assertEqual(results, {"keywithnovalue": "", "": ""})

    def test_ignored_lines(self) -> None:
        results = self.func(self.ignore)
        self.assertEqual(results, {})


class TestDateStr(unittest.TestCase):
    default_datefmt = logfilter.DEFAULTS["datefmt"]

    def test_availability(self) -> None:
        """Check if `date` is installed on $PATH."""
        self.assertIsNotNone(shutil.which("date"), "'date' is not installed on $PATH")

    def test_default_values(self) -> None:
        for value in (logfilter.DEFAULTS["after"], logfilter.DEFAULTS["before"]):
            # Just check datestr doesn't throw any exceptions.
            self.assertIsInstance(logfilter.datestr(value, self.default_datefmt), str)

    def test_relative_items(self) -> None:
        today = logfilter.datestr("today", self.default_datefmt)
        month_ago = logfilter.datestr("month ago", self.default_datefmt)
        self.assertLess(month_ago, today)
        last_tuesday = logfilter.datestr("last Tuesday", self.default_datefmt)
        self.assertLess(last_tuesday, today)

    def test_pure_numbers(self) -> None:
        today = logfilter.datestr("today", self.default_datefmt)
        ago = logfilter.datestr("20200721", self.default_datefmt)
        self.assertLess(ago, today)

    def test_seconds_since_the_epoch(self) -> None:
        epoch = logfilter.datestr("@0", self.default_datefmt)
        now = logfilter.datestr("now", self.default_datefmt)
        self.assertLess(epoch, now)

    def test_errors(self) -> None:
        # You forgot to prefix datefmt with '+'
        self.assertRaises(SystemExit, logfilter.datestr, datefmt="%Y-%m-%d")
        # Invalid date
        self.assertRaises(SystemExit, logfilter.datestr, date="my birthday")


class TestAWK(unittest.TestCase):
    def test_availability(self) -> None:
        """Check if `awk` is installed on $PATH."""
        self.assertIsNotNone(shutil.which("awk"), "'awk' is not installed on $PATH")


if __name__ == "__main__":
    unittest.main()
