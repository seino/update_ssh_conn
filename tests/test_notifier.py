import json
from unittest.mock import MagicMock, patch
from urllib.parse import unquote

import responses

from app import ChatworkNotifier, SlackNotifier, TeamsNotifier

# テスト用ダミー値（実在しないURL/トークン）
DUMMY_SLACK_WEBHOOK_URL = "https://hooks.slack.com/services/T000/B000/XXX"
DUMMY_TEAMS_HOOK_URL = "https://example.webhook.office.com/webhookb2/xxx"
DUMMY_CHATWORK_API_TOKEN = "token123"
DUMMY_CHATWORK_ROOM_ID = "12345"
DUMMY_CHATWORK_URL = (
    f"https://api.chatwork.com/v2/rooms/{DUMMY_CHATWORK_ROOM_ID}/messages"
)


class TestSlackNotifier:
    @responses.activate
    def test_webhookが設定されているとき_送信成功でTrueを返す(self):
        responses.add(responses.POST, DUMMY_SLACK_WEBHOOK_URL, status=200)

        notifier = SlackNotifier(DUMMY_SLACK_WEBHOOK_URL)
        result = notifier.send_notification("タイトル", "本文")

        assert result is True
        assert len(responses.calls) == 1
        body = responses.calls[0].request.body.decode("utf-8")
        payload = json.loads(body)
        assert payload["text"] == "*タイトル*\n本文"
        assert payload["username"] == "SSH接続更新通知"

    @responses.activate
    def test_HTTPエラーのとき_Falseを返す(self):
        responses.add(responses.POST, DUMMY_SLACK_WEBHOOK_URL, status=500)

        notifier = SlackNotifier(DUMMY_SLACK_WEBHOOK_URL)
        result = notifier.send_notification("タイトル", "本文")

        assert result is False

    def test_webhook_urlがNoneのとき_送信せずFalseを返す(self):
        notifier = SlackNotifier(None)
        result = notifier.send_notification("タイトル", "本文")

        assert result is False
        assert notifier.enabled is False

    @responses.activate
    def test_通知が無効化されているとき_送信せずFalseを返す(self):
        responses.add(responses.POST, DUMMY_SLACK_WEBHOOK_URL, status=200)

        notifier = SlackNotifier(DUMMY_SLACK_WEBHOOK_URL)
        notifier.enabled = False

        result = notifier.send_notification("タイトル", "本文")

        assert result is False
        assert len(responses.calls) == 0


class TestTeamsNotifier:
    @patch("app.pymsteams.connectorcard")
    def test_送信成功のとき_Trueを返す(self, mock_connectorcard):
        mock_card = MagicMock()
        mock_connectorcard.return_value = mock_card

        notifier = TeamsNotifier(DUMMY_TEAMS_HOOK_URL)
        result = notifier.send_notification("タイトル", "本文")

        assert result is True
        mock_connectorcard.assert_called_once_with(DUMMY_TEAMS_HOOK_URL)
        mock_card.title.assert_called_once_with("タイトル")
        mock_card.text.assert_called_once_with("本文")
        mock_card.send.assert_called_once()

    @patch("app.pymsteams.connectorcard")
    def test_送信時に例外が発生したとき_Falseを返す(self, mock_connectorcard):
        mock_card = MagicMock()
        mock_card.send.side_effect = RuntimeError("送信失敗")
        mock_connectorcard.return_value = mock_card

        notifier = TeamsNotifier(DUMMY_TEAMS_HOOK_URL)
        result = notifier.send_notification("タイトル", "本文")

        assert result is False

    def test_hook_urlがNoneのとき_送信せずFalseを返す(self):
        notifier = TeamsNotifier(None)
        result = notifier.send_notification("タイトル", "本文")

        assert result is False
        assert notifier.enabled is False

    @patch("app.pymsteams.connectorcard")
    def test_通知が無効化されているとき_送信せずFalseを返す(self, mock_connectorcard):
        notifier = TeamsNotifier(DUMMY_TEAMS_HOOK_URL)
        notifier.enabled = False

        result = notifier.send_notification("タイトル", "本文")

        assert result is False
        mock_connectorcard.assert_not_called()


class TestChatworkNotifier:
    @responses.activate
    def test_認証情報が揃っているとき_送信成功でTrueを返す(self):
        responses.add(
            responses.POST, DUMMY_CHATWORK_URL, status=200, json={"message_id": "1"}
        )

        notifier = ChatworkNotifier(DUMMY_CHATWORK_API_TOKEN, DUMMY_CHATWORK_ROOM_ID)
        result = notifier.send_notification("タイトル", "本文")

        assert result is True
        assert len(responses.calls) == 1
        request = responses.calls[0].request
        assert request.headers.get("X-ChatWorkToken") == DUMMY_CHATWORK_API_TOKEN
        raw_body = (
            request.body.decode("utf-8")
            if isinstance(request.body, bytes)
            else request.body
        )
        decoded = unquote(raw_body)
        assert "[info]" in decoded
        assert "[title]タイトル[/title]" in decoded
        assert "本文" in decoded

    @responses.activate
    def test_HTTPエラーのとき_Falseを返す(self):
        responses.add(responses.POST, DUMMY_CHATWORK_URL, status=401)

        notifier = ChatworkNotifier(DUMMY_CHATWORK_API_TOKEN, DUMMY_CHATWORK_ROOM_ID)
        result = notifier.send_notification("タイトル", "本文")

        assert result is False

    def test_api_tokenがNoneのとき_送信せずFalseを返す(self):
        notifier = ChatworkNotifier(None, DUMMY_CHATWORK_ROOM_ID)
        result = notifier.send_notification("タイトル", "本文")

        assert result is False
        assert notifier.enabled is False

    def test_room_idがNoneのとき_送信せずFalseを返す(self):
        notifier = ChatworkNotifier(DUMMY_CHATWORK_API_TOKEN, None)
        result = notifier.send_notification("タイトル", "本文")

        assert result is False
        assert notifier.enabled is False
