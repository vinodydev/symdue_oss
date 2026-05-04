"""
Unit tests for FilesHelper.

Tests run with monkeypatched SAFE_ROOTS pointing into a tmp_path so the
class can be exercised without needing the real /workspace/files,
/storage, etc. mounts.
"""
import json
import pytest
from pathlib import Path

from services.docker import files_helper as files_helper_module
from services.docker.files_helper import FilesHelper


@pytest.fixture
def helper(tmp_path, monkeypatch):
    """FilesHelper with SAFE_ROOTS swapped to the test's tmp_path.

    Sandbox-realm paths like /workspace/files don't exist in the unit-test
    environment, so we redirect SAFE_ROOTS to a per-test directory and feed
    paths under that directory in the assertions.
    """
    monkeypatch.setattr(files_helper_module, "SAFE_ROOTS", (str(tmp_path),))
    return FilesHelper()


class TestPathTraversal:
    def test_path_outside_safe_roots_raises(self, helper):
        """Reading any path not under SAFE_ROOTS must raise PermissionError."""
        with pytest.raises(PermissionError, match="path outside allowed roots"):
            helper.read_text("/etc/passwd")

    def test_path_inside_safe_roots_resolves(self, helper, tmp_path):
        f = tmp_path / "inside.txt"
        f.write_text("ok")
        assert helper.read_text(str(f)) == "ok"

    def test_relative_path_traversal_blocked(self, helper, tmp_path):
        """Path resolution should reject ../../etc/passwd-style traversal."""
        # Build a path that LOOKS like it's inside tmp_path but resolves elsewhere
        bad = tmp_path / ".." / ".." / "etc" / "passwd"
        with pytest.raises(PermissionError):
            helper.read_text(str(bad))

    def test_safe_root_prefix_match_is_strict(self, helper, tmp_path, monkeypatch):
        """A path whose string-prefix matches a SAFE_ROOT but isn't actually
        inside it (e.g. /workspace_evil vs /workspace) should be rejected."""
        # Use a fixed root and a sibling that prefix-matches
        evil_neighbor = str(tmp_path) + "_evil_neighbor/file.txt"
        Path(str(tmp_path) + "_evil_neighbor").mkdir(exist_ok=True, parents=True)
        Path(evil_neighbor).write_text("nope")
        with pytest.raises(PermissionError):
            helper.read_text(evil_neighbor)


class TestReadMethods:
    def test_read_text(self, helper, tmp_path):
        f = tmp_path / "hello.txt"
        f.write_text("hello world")
        assert helper.read_text(str(f)) == "hello world"

    def test_read_text_custom_encoding(self, helper, tmp_path):
        f = tmp_path / "latin.txt"
        f.write_bytes("café".encode("latin-1"))
        assert helper.read_text(str(f), encoding="latin-1") == "café"

    def test_read_bytes(self, helper, tmp_path):
        f = tmp_path / "blob.bin"
        f.write_bytes(b"\x00\x01\x02\xff")
        assert helper.read_bytes(str(f)) == b"\x00\x01\x02\xff"

    def test_read_json(self, helper, tmp_path):
        f = tmp_path / "config.json"
        f.write_text(json.dumps({"key": "value", "n": 42}))
        assert helper.read_json(str(f)) == {"key": "value", "n": 42}

    def test_read_csv_returns_list_of_dicts(self, helper, tmp_path):
        f = tmp_path / "data.csv"
        f.write_text("name,age\nAlice,30\nBob,25\n")
        rows = helper.read_csv(str(f))
        assert rows == [{"name": "Alice", "age": "30"}, {"name": "Bob", "age": "25"}]

    def test_read_csv_empty_returns_empty_list(self, helper, tmp_path):
        f = tmp_path / "empty.csv"
        f.write_text("name,age\n")
        assert helper.read_csv(str(f)) == []


class TestExists:
    def test_exists_true(self, helper, tmp_path):
        f = tmp_path / "present.txt"
        f.write_text("x")
        assert helper.exists(str(f)) is True

    def test_exists_false(self, helper, tmp_path):
        assert helper.exists(str(tmp_path / "absent.txt")) is False

    def test_exists_outside_safe_roots_returns_false(self, helper):
        """Existence check must not raise for paths outside SAFE_ROOTS — return False."""
        # /etc/passwd exists on Linux but it's not in our SAFE_ROOTS
        assert helper.exists("/etc/passwd") is False


class TestListDir:
    def test_list_dir_returns_sorted_files(self, helper, tmp_path):
        (tmp_path / "b.txt").write_text("")
        (tmp_path / "a.txt").write_text("")
        (tmp_path / "c.txt").write_text("")
        result = helper.list_dir(str(tmp_path))
        assert result == sorted(result)
        assert all(p.endswith(".txt") for p in result)
        assert len(result) == 3

    def test_list_dir_with_suffix_filter(self, helper, tmp_path):
        (tmp_path / "a.json").write_text("{}")
        (tmp_path / "b.json").write_text("{}")
        (tmp_path / "c.txt").write_text("")
        result = helper.list_dir(str(tmp_path), suffix=".json")
        assert len(result) == 2
        assert all(p.endswith(".json") for p in result)

    def test_list_dir_excludes_subdirs(self, helper, tmp_path):
        (tmp_path / "subdir").mkdir()
        (tmp_path / "file.txt").write_text("")
        result = helper.list_dir(str(tmp_path))
        assert len(result) == 1
        assert result[0].endswith("file.txt")

    def test_list_dir_on_file_raises(self, helper, tmp_path):
        f = tmp_path / "not_a_dir.txt"
        f.write_text("")
        with pytest.raises(NotADirectoryError):
            helper.list_dir(str(f))

    def test_list_dir_outside_safe_roots_raises(self, helper):
        with pytest.raises(PermissionError):
            helper.list_dir("/etc")
