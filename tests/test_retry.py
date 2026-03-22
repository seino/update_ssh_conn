from unittest.mock import patch

import pytest

from app import with_retry


class TestWithRetry:
    def test_success_on_first_attempt(self):
        result = with_retry(lambda: 42)
        assert result == 42

    @patch("app.time.sleep")
    def test_success_on_second_attempt(self, mock_sleep):
        call_count = 0

        def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise RuntimeError("一時的なエラー")
            return "成功"

        result = with_retry(flaky, max_retries=3)
        assert result == "成功"
        assert call_count == 2
        mock_sleep.assert_called_once()

    @patch("app.time.sleep")
    def test_all_retries_exhausted(self, mock_sleep):
        def always_fail():
            raise RuntimeError("常に失敗")

        with pytest.raises(RuntimeError, match="常に失敗"):
            with_retry(always_fail, max_retries=3)

        assert mock_sleep.call_count == 2  # max_retries - 1 回のsleep

    @patch("app.time.sleep")
    def test_backoff_timing(self, mock_sleep):
        """バックオフ係数が正しく適用されるか"""
        call_count = 0

        def fail_twice():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise RuntimeError("失敗")
            return "OK"

        with (
            patch("app.Config.REQUEST_DELAY", 1),
            patch("app.Config.RETRY_BACKOFF_FACTOR", 2.0),
        ):
            with_retry(fail_twice, max_retries=3)

        # 1回目のリトライ: 1 * (2.0 ** 0) = 1.0秒
        # 2回目のリトライ: 1 * (2.0 ** 1) = 2.0秒
        assert mock_sleep.call_args_list[0][0][0] == 1.0
        assert mock_sleep.call_args_list[1][0][0] == 2.0

    def test_passes_args_and_kwargs(self):
        def add(a: int, b: int, offset: int = 0) -> int:
            return a + b + offset

        result = with_retry(add, 1, 2, offset=10)
        assert result == 13
