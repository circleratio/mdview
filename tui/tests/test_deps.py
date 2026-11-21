import importlib.metadata
import re
import unittest
from pathlib import Path
from unittest import mock

from mdview_tui import deps

PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"


def fake_versions(versions):
    """Patch importlib.metadata.version to return `versions[dist]` (missing: not found)."""
    def version(dist):
        if dist not in versions:
            raise importlib.metadata.PackageNotFoundError(dist)
        return versions[dist]
    return mock.patch.object(deps.importlib.metadata, "version", side_effect=version)


OK = {"textual": "2.1.2", "markdown-it-py": "3.0.0", "PyYAML": "6.0.2"}


class VersionTupleTest(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(deps.version_tuple("2.1.2"), (2, 1, 2))
        self.assertEqual(deps.version_tuple("2.0"), (2, 0))
        self.assertEqual(deps.version_tuple("0.47.1rc1"), (0, 47, 1))
        self.assertEqual(deps.version_tuple("2.1.2-1"), (2, 1, 2))
        self.assertEqual(deps.version_tuple("unknown"), ())

    def test_compare(self):
        self.assertLess(deps.version_tuple("0.47.1"), deps.version_tuple("2.0"))
        self.assertGreaterEqual(deps.version_tuple("2.0.0"), deps.version_tuple("2.0"))
        self.assertGreaterEqual(deps.version_tuple("10.0"), deps.version_tuple("2.0"))


class DependencyErrorTest(unittest.TestCase):
    def test_all_ok(self):
        with fake_versions(OK):
            self.assertIsNone(deps.dependency_error())

    def test_too_old(self):
        with fake_versions({**OK, "textual": "0.47.1"}):
            self.assertEqual(deps.dependency_error(), "textual>=2.0 is required (found 0.47.1)")

    def test_missing_and_old(self):
        versions = {"textual": "1.0.0", "markdown-it-py": "3.0.0"}
        with fake_versions(versions), mock.patch.object(deps.importlib.util, "find_spec", return_value=None):
            self.assertEqual(
                deps.dependency_error(),
                "textual>=2.0 is required (found 1.0.0); PyYAML>=6.0 is required (not installed)",
            )

    def test_importable_without_metadata(self):
        versions = {k: v for k, v in OK.items() if k != "PyYAML"}
        with fake_versions(versions), mock.patch.object(deps.importlib.util, "find_spec", return_value=object()):
            self.assertIsNone(deps.dependency_error())

    def test_actual_environment(self):
        self.assertIsNone(deps.dependency_error())

    def test_matches_pyproject(self):
        text = PYPROJECT.read_text(encoding="utf-8")
        block = re.search(r"^dependencies\s*=\s*\[(.*?)^\]", text, re.M | re.S).group(1)
        declared = {}
        for req in re.findall(r'"([^"]+)"', block):
            m = re.fullmatch(r"([A-Za-z0-9_.-]+)(?:\[[^\]]*\])?>=([0-9.]+)", req)
            declared[m.group(1)] = m.group(2)
        self.assertEqual(declared, {dist: minimum for dist, _, minimum in deps.REQUIREMENTS})


if __name__ == "__main__":
    unittest.main()
