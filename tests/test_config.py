from unittest.mock import patch

from app import Config


class TestConfigValidate:
    def _reset_config(self):
        Config.ENABLE_NOTIFICATIONS = True

    def test_teams_valid(self):
        self._reset_config()
        with (
            patch.object(Config, "NOTIFICATION_TYPE", "teams"),
            patch.object(Config, "TEAMS_WEBHOOK_URL", "https://example.com/webhook"),
        ):
            Config.validate()
            assert Config.ENABLE_NOTIFICATIONS is True

    def test_teams_missing_url_disables(self):
        self._reset_config()
        with (
            patch.object(Config, "NOTIFICATION_TYPE", "teams"),
            patch.object(Config, "TEAMS_WEBHOOK_URL", None),
        ):
            Config.validate()
            assert Config.ENABLE_NOTIFICATIONS is False

    def test_slack_valid(self):
        self._reset_config()
        with (
            patch.object(Config, "NOTIFICATION_TYPE", "slack"),
            patch.object(Config, "SLACK_WEBHOOK_URL", "https://hooks.slack.com/test"),
        ):
            Config.validate()
            assert Config.ENABLE_NOTIFICATIONS is True

    def test_slack_missing_url_disables(self):
        self._reset_config()
        with (
            patch.object(Config, "NOTIFICATION_TYPE", "slack"),
            patch.object(Config, "SLACK_WEBHOOK_URL", None),
        ):
            Config.validate()
            assert Config.ENABLE_NOTIFICATIONS is False

    def test_chatwork_valid(self):
        self._reset_config()
        with (
            patch.object(Config, "NOTIFICATION_TYPE", "chatwork"),
            patch.object(Config, "CHATWORK_API_TOKEN", "token123"),
            patch.object(Config, "CHATWORK_ROOM_ID", "12345"),
        ):
            Config.validate()
            assert Config.ENABLE_NOTIFICATIONS is True

    def test_chatwork_missing_token_disables(self):
        self._reset_config()
        with (
            patch.object(Config, "NOTIFICATION_TYPE", "chatwork"),
            patch.object(Config, "CHATWORK_API_TOKEN", None),
            patch.object(Config, "CHATWORK_ROOM_ID", "12345"),
        ):
            Config.validate()
            assert Config.ENABLE_NOTIFICATIONS is False

    def test_chatwork_missing_room_id_disables(self):
        self._reset_config()
        with (
            patch.object(Config, "NOTIFICATION_TYPE", "chatwork"),
            patch.object(Config, "CHATWORK_API_TOKEN", "token123"),
            patch.object(Config, "CHATWORK_ROOM_ID", None),
        ):
            Config.validate()
            assert Config.ENABLE_NOTIFICATIONS is False

    def test_notifications_disabled_skips_validation(self):
        Config.ENABLE_NOTIFICATIONS = False
        with (
            patch.object(Config, "NOTIFICATION_TYPE", "teams"),
            patch.object(Config, "TEAMS_WEBHOOK_URL", None),
        ):
            Config.validate()
            # 無効のまま変更なし
            assert Config.ENABLE_NOTIFICATIONS is False

    def test_unknown_type_disables(self):
        self._reset_config()
        with patch.object(Config, "NOTIFICATION_TYPE", "unknown"):
            Config.validate()
            assert Config.ENABLE_NOTIFICATIONS is False
