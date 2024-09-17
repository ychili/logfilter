#!/usr/bin/python3
#
#  Copyright 2023, 2024 Dylan Maltby
#  SPDX-Licence-Identifier: Apache-2.0
#
# pylint: disable=missing-class-docstring,missing-function-docstring

"""Unit tests for logfilter"""

import unittest

import logfilter


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

    @staticmethod
    def func(strings):
        return logfilter.parse_kv_config(strings)

    def test_basic(self):
        results = self.func(self.basic)
        self.assertEqual(results, {"key1": '"${HOME}"/logs'})

    def test_trailing(self):
        results = self.func(self.trailing)
        self.assertEqual(
            results, {"key1": "value", "key2": "value  # This comment is not discarded"}
        )

    def test_spacing(self):
        results = self.func(self.spacing)
        self.assertEqual(
            results, {"normalkey": "No line breaks please", "key with spaces": "Value"}
        )

    def test_punctuation(self):
        results = self.func(self.punctuation)
        self.assertEqual(results, {"equalssign": "2 + 2 = 4"})

    def test_empty_components(self):
        results = self.func(self.empty)
        self.assertEqual(results, {"keywithnovalue": "", "": ""})

    def test_ignored_lines(self):
        results = self.func(self.ignore)
        self.assertEqual(results, {})


class TestDateStr(unittest.TestCase):
    default_datefmt = logfilter.DEFAULTS["datefmt"]

    def test_availability(self):
        """Check if `date` is installed on $PATH."""
        self.assertIsNotNone(
            logfilter.shutil.which("date"), "'date' is not installed on $PATH"
        )

    def test_default_values(self):
        for value in (logfilter.DEFAULTS["after"], logfilter.DEFAULTS["before"]):
            # Just check datestr doesn't throw any exceptions.
            self.assertIsInstance(logfilter.datestr(value, self.default_datefmt), str)

    def test_relative_items(self):
        today = logfilter.datestr("today", self.default_datefmt)
        month_ago = logfilter.datestr("month ago", self.default_datefmt)
        self.assertLess(month_ago, today)
        last_tuesday = logfilter.datestr("last Tuesday", self.default_datefmt)
        self.assertLess(last_tuesday, today)

    def test_pure_numbers(self):
        today = logfilter.datestr("today", self.default_datefmt)
        ago = logfilter.datestr("20200721", self.default_datefmt)
        self.assertLess(ago, today)

    def test_seconds_since_the_epoch(self):
        epoch = logfilter.datestr("@0", self.default_datefmt)
        now = logfilter.datestr("now", self.default_datefmt)
        self.assertLess(epoch, now)

    def test_errors(self):
        # You forgot to prefix datefmt with '+'
        self.assertRaises(SystemExit, logfilter.datestr, datefmt="%Y-%m-%d")
        # Invalid date
        self.assertRaises(SystemExit, logfilter.datestr, date="my birthday")


class TestAWK(unittest.TestCase):
    def test_availability(self):
        """Check if `awk` is installed on $PATH."""
        self.assertIsNotNone(
            logfilter.shutil.which("awk"), "'awk' is not installed on $PATH"
        )


if __name__ == "__main__":
    unittest.main()
