import csv
import tempfile
from pathlib import Path

import pytest

from app import CoreServerUpdater, Notifier, ServerInfo


class StubNotifier(Notifier):
    def send_notification(self, title: str, text: str) -> bool:
        return True


def _create_csv(rows: list[list[str]]) -> str:
    """一時CSVファイルを作成してパスを返す"""
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".csv", delete=False, encoding="utf-8", newline=""
    )
    writer = csv.writer(tmp)
    writer.writerows(rows)
    tmp.close()
    return tmp.name


class TestReadServerList:

    def _make_updater(self, csv_path: str) -> CoreServerUpdater:
        return CoreServerUpdater(csv_path, "Test", StubNotifier())

    def test_normal_csv(self):
        path = _create_csv([
            ["server1", "user1", "pass1"],
            ["server2", "user2", "pass2"],
        ])
        updater = self._make_updater(path)
        result = updater._read_server_list()
        assert len(result) == 2
        assert result[0] == ServerInfo(url="server1", user_id="user1", credential="pass1")
        Path(path).unlink()

    def test_header_row_skipped(self):
        path = _create_csv([
            ["サブドメイン", "アカウント", "パスワード"],
            ["server1", "user1", "pass1"],
        ])
        updater = self._make_updater(path)
        result = updater._read_server_list()
        assert len(result) == 1
        assert result[0].url == "server1"
        Path(path).unlink()

    def test_subdomain_header_skipped(self):
        path = _create_csv([
            ["subdomain", "account", "key"],
            ["server1", "user1", "pass1"],
        ])
        updater = self._make_updater(path)
        result = updater._read_server_list()
        assert len(result) == 1
        Path(path).unlink()

    def test_empty_rows_skipped(self):
        path = _create_csv([
            ["server1", "user1", "pass1"],
            [],
            ["", "", ""],
            ["server2", "user2", "pass2"],
        ])
        updater = self._make_updater(path)
        result = updater._read_server_list()
        assert len(result) == 2
        Path(path).unlink()

    def test_incomplete_rows_skipped(self):
        path = _create_csv([
            ["server1", "user1", "pass1"],
            ["only_url"],
            ["server2", "user2", "pass2"],
        ])
        updater = self._make_updater(path)
        result = updater._read_server_list()
        assert len(result) == 2
        Path(path).unlink()

    def test_empty_file_raises(self):
        path = _create_csv([])
        updater = self._make_updater(path)
        with pytest.raises(ValueError, match="有効なサーバー情報がありません"):
            updater._read_server_list()
        Path(path).unlink()

    def test_file_not_found(self):
        updater = self._make_updater("/nonexistent/path.csv")
        with pytest.raises(FileNotFoundError):
            updater._read_server_list()

    def test_whitespace_stripped(self):
        path = _create_csv([
            ["  server1  ", "  user1  ", "  pass1  "],
        ])
        updater = self._make_updater(path)
        result = updater._read_server_list()
        assert result[0] == ServerInfo(url="server1", user_id="user1", credential="pass1")
        Path(path).unlink()
