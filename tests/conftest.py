import pytest

from app import Config


@pytest.fixture(autouse=True)
def _reset_config_state():
    """各テスト前に Config のグローバル状態を初期値に戻す"""
    Config.ENABLE_NOTIFICATIONS = True
    yield
