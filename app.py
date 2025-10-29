import csv
import os
import requests
import pymsteams
import time
import logging
import ipaddress
from abc import ABC, abstractmethod
from typing import List, Optional
from functools import lru_cache
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

# 環境変数を読み込み
load_dotenv()

# ロギングの設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s: %(message)s",
    datefmt="%Y年%m月%d日 %H:%M:%S",
)
logger = logging.getLogger(__name__)


@dataclass
class ServerInfo:
    """サーバー接続情報を格納するデータクラス"""

    url: str
    user_id: str
    credential: str  # password or api_key


@dataclass
class UpdateResult:
    """更新結果を格納するデータクラス"""

    server: str
    success: bool
    error_message: Optional[str] = None


class Config:
    """設定クラス - 環境変数から設定を読み込み"""

    # スクリプトのディレクトリを基準にする
    BASE_DIR = Path(__file__).resolve().parent

    # URL設定
    VALUE_SERVER_URL = "https://{}.valueserver.jp/cp/admin.cgi?telnet=1"
    CORE_SERVER_URL = "https://api.coreserver.jp/v1/tool/ssh_ip_allow"
    IP_CHECK_URL = os.getenv(
        "IP_CHECK_URL", "http://dyn.value-domain.com/cgi-bin/dyn.fcg?ip"
    )

    # 固定IPアドレス（設定されている場合は動的取得より優先）
    FIXED_IP_ADDRESS = os.getenv("FIXED_IP_ADDRESS", "").strip()

    # 認証とリクエスト設定
    SSH_KEYWORD = "SSH登録"
    REQUEST_DELAY = int(os.getenv("REQUEST_DELAY", "2"))  # リクエスト間の遅延（秒）
    RATE_LIMIT_ADDITIONAL_DELAY = int(
        os.getenv("RATE_LIMIT_DELAY", "4")
    )  # レート制限時の追加遅延（秒）
    MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))  # 最大リトライ回数
    RETRY_BACKOFF_FACTOR = float(
        os.getenv("RETRY_BACKOFF_FACTOR", "2.0")
    )  # リトライ時のバックオフ係数

    # 通知設定
    NOTIFICATION_TYPE = os.getenv("NOTIFICATION_TYPE", "teams").lower()  # teams, slack, chatwork
    TEAMS_WEBHOOK_URL = os.getenv("TEAMS_WEBHOOK_URL")
    SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")
    CHATWORK_API_TOKEN = os.getenv("CHATWORK_API_TOKEN")
    CHATWORK_ROOM_ID = os.getenv("CHATWORK_ROOM_ID")
    ENABLE_NOTIFICATIONS = os.getenv("ENABLE_NOTIFICATIONS", "true").lower() == "true"

    # ファイルパス（環境変数で絶対パス指定可能、デフォルトは相対パス）
    VALUESERVER_CSV = os.getenv(
        "VALUESERVER_CSV", str(BASE_DIR / "csv" / "list_valueserver.csv")
    )
    CORESERVER_CSV = os.getenv(
        "CORESERVER_CSV", str(BASE_DIR / "csv" / "list_coreserver.csv")
    )

    @classmethod
    def validate(cls):
        """設定の妥当性を検証"""
        if cls.ENABLE_NOTIFICATIONS and not cls.TEAMS_WEBHOOK_URL:
            logger.warning("通知が有効ですがWebhook URLが設定されていません")
            cls.ENABLE_NOTIFICATIONS = False

        # CSVファイルの存在確認
        for csv_path in [cls.VALUESERVER_CSV, cls.CORESERVER_CSV]:
            if not Path(csv_path).exists():
                logger.warning(f"CSVファイルが見つかりません: {csv_path}")


class Notifier(ABC):
    """通知サービスの基底クラス"""

    def __init__(self):
        self.enabled = Config.ENABLE_NOTIFICATIONS

    @abstractmethod
    def send_notification(self, title: str, text: str) -> bool:
        """通知を送信する抽象メソッド"""
        pass


class TeamsNotifier(Notifier):
    """Microsoft Teamsへの通知を処理するクラス"""

    def __init__(self, hook_url: Optional[str]):
        super().__init__()
        self.hook_url = hook_url
        self.enabled = self.enabled and bool(hook_url)

    def send_notification(self, title: str, text: str) -> bool:
        """TeamsにカードメッセージとしてWebhook通知を送信"""
        if not self.enabled:
            logger.info(f"通知スキップ（無効化中）: {title}")
            return False

        try:
            teams_message = pymsteams.connectorcard(self.hook_url)
            teams_message.title(title)
            teams_message.text(text)
            teams_message.send()
            logger.info(f"Teams通知送信成功: {title}")
            return True
        except Exception as e:
            logger.error(f"Teams通知送信失敗: {e}")
            return False


class SlackNotifier(Notifier):
    """Slackへの通知を処理するクラス"""

    def __init__(self, webhook_url: Optional[str]):
        super().__init__()
        self.webhook_url = webhook_url
        self.enabled = self.enabled and bool(webhook_url)

    def send_notification(self, title: str, text: str) -> bool:
        """SlackにWebhook通知を送信"""
        if not self.enabled:
            logger.info(f"通知スキップ（無効化中）: {title}")
            return False

        try:
            payload = {
                "text": f"*{title}*\n{text}",
                "username": "SSH接続更新通知",
            }
            response = requests.post(
                self.webhook_url, json=payload, timeout=10
            )
            response.raise_for_status()
            logger.info(f"Slack通知送信成功: {title}")
            return True
        except Exception as e:
            logger.error(f"Slack通知送信失敗: {e}")
            return False


class ChatworkNotifier(Notifier):
    """Chatworkへの通知を処理するクラス"""

    def __init__(self, api_token: Optional[str], room_id: Optional[str]):
        super().__init__()
        self.api_token = api_token
        self.room_id = room_id
        self.enabled = self.enabled and bool(api_token) and bool(room_id)

    def send_notification(self, title: str, text: str) -> bool:
        """ChatworkにAPI経由で通知を送信"""
        if not self.enabled:
            logger.info(f"通知スキップ（無効化中）: {title}")
            return False

        try:
            url = f"https://api.chatwork.com/v2/rooms/{self.room_id}/messages"
            headers = {"X-ChatWorkToken": self.api_token}
            body = f"[info][title]{title}[/title]{text}[/info]"
            response = requests.post(
                url, headers=headers, data={"body": body}, timeout=10
            )
            response.raise_for_status()
            logger.info(f"Chatwork通知送信成功: {title}")
            return True
        except Exception as e:
            logger.error(f"Chatwork通知送信失敗: {e}")
            return False


class NotifierFactory:
    """通知サービスのファクトリークラス"""

    @staticmethod
    def create() -> Notifier:
        """環境変数に基づいて適切な通知サービスを生成"""
        notification_type = Config.NOTIFICATION_TYPE

        if notification_type == "slack":
            return SlackNotifier(Config.SLACK_WEBHOOK_URL)
        elif notification_type == "chatwork":
            return ChatworkNotifier(Config.CHATWORK_API_TOKEN, Config.CHATWORK_ROOM_ID)
        else:  # デフォルトはteams
            return TeamsNotifier(Config.TEAMS_WEBHOOK_URL)


class IPAddressFetcher:
    """現在のIPアドレスを取得するクラス"""

    @staticmethod
    def _validate_ip_address(ip_str: str) -> str:
        """IPアドレスの妥当性を検証（IPv4/IPv6対応）"""
        try:
            # ipaddressモジュールで厳密な検証
            ip_obj = ipaddress.ip_address(ip_str)
            return str(ip_obj)
        except ValueError as e:
            raise ValueError(f"無効なIPアドレス形式: {ip_str} ({e})")

    @staticmethod
    @lru_cache(maxsize=1)
    def get_current_ip() -> str:
        """現在のIPアドレスを取得（固定IP優先、なければ動的取得）"""
        # 環境変数で固定IPが設定されている場合はそれを使用
        if Config.FIXED_IP_ADDRESS:
            ip_address = IPAddressFetcher._validate_ip_address(
                Config.FIXED_IP_ADDRESS
            )
            logger.info(f"固定IPアドレスを使用: {ip_address}")
            return ip_address

        # 固定IPが設定されていない場合は動的に取得
        try:
            response = requests.get(Config.IP_CHECK_URL, timeout=10)
            response.raise_for_status()
            ip_address = response.text.strip()

            # IPアドレスの厳密な検証
            validated_ip = IPAddressFetcher._validate_ip_address(ip_address)
            logger.info(f"動的に取得したIPアドレス: {validated_ip}")
            return validated_ip
        except requests.RequestException as e:
            logger.error(f"IP取得エラー: {e}")
            raise
        except ValueError as e:
            logger.error(f"IP検証エラー: {e}")
            raise


class RetryHandler:
    """リトライ処理を管理するクラス"""

    @staticmethod
    def with_retry(func, *args, max_retries: int = None, **kwargs):
        """指定された関数をリトライ付きで実行"""
        max_retries = max_retries or Config.MAX_RETRIES
        last_exception = None

        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                if attempt < max_retries - 1:
                    wait_time = Config.REQUEST_DELAY * (
                        Config.RETRY_BACKOFF_FACTOR**attempt
                    )
                    logger.warning(
                        f"リトライ {attempt + 1}/{max_retries}: {wait_time}秒待機"
                    )
                    time.sleep(wait_time)
                else:
                    logger.error(f"最大リトライ回数に到達: {e}")

        raise last_exception


class ServerUpdater:
    """サーバーのSSH接続設定を更新する基底クラス"""

    def __init__(self, csv_file: str, server_type: str, notifier: Notifier):
        self.csv_file = csv_file
        self.server_type = server_type
        self.notifier = notifier
        self.ip_fetcher = IPAddressFetcher()
        self.retry_handler = RetryHandler()

    def update_all_servers(self) -> List[UpdateResult]:
        """CSVから全てのサーバー情報を読み込み、SSH設定を更新"""
        results = []

        try:
            server_list = self._read_server_list()
        except Exception as e:
            logger.error(f"サーバーリスト読み込み失敗: {e}")
            self._send_error_notification(f"サーバーリスト読み込みエラー: {str(e)}")
            return results

        success_count = 0
        failure_count = 0
        failed_servers = []

        for server_info in server_list:
            try:
                # リトライ付きで更新を実行
                self.retry_handler.with_retry(self._update_server, server_info)
                results.append(UpdateResult(server=server_info.url, success=True))
                success_count += 1

            except Exception as e:
                error_msg = str(e)
                results.append(
                    UpdateResult(
                        server=server_info.url, success=False, error_message=error_msg
                    )
                )
                failure_count += 1
                failed_servers.append(f"{server_info.url}: {error_msg}")
                logger.error(f"更新失敗 ({server_info.url}): {error_msg}")
                # エラーがあっても次のサーバーの処理を継続

            # リクエスト間に遅延を入れる
            time.sleep(Config.REQUEST_DELAY)

        # 結果の通知
        self._send_completion_notification(success_count, failure_count, failed_servers)

        return results

    def _read_server_list(self) -> List[ServerInfo]:
        """CSVファイルからサーバー情報を読み込む"""
        server_list = []

        try:
            with open(self.csv_file, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                for row_num, row in enumerate(reader, 1):
                    # 空行をスキップ
                    if not row or all(not cell.strip() for cell in row):
                        logger.debug(f"行{row_num}: 空行をスキップ")
                        continue

                    # 不完全なデータをスキップ（詳細ログ付き）
                    if len(row) < 3:
                        logger.warning(
                            f"行{row_num}: 不完全なデータをスキップ - "
                            f"フィールド数: {len(row)}, 内容: {row}"
                        )
                        continue

                    server_list.append(
                        ServerInfo(
                            url=row[0].strip(),
                            user_id=row[1].strip(),
                            credential=row[2].strip(),
                        )
                    )

        except FileNotFoundError:
            logger.error(f"CSVファイルが見つかりません: {self.csv_file}")
            raise
        except csv.Error as e:
            logger.error(f"CSV解析エラー: {e}")
            raise
        except Exception as e:
            logger.error(f"予期しないエラー: {e}")
            raise

        if not server_list:
            raise ValueError(f"有効なサーバー情報がありません: {self.csv_file}")

        logger.info(f"{len(server_list)}件のサーバー情報を読み込みました")
        return server_list

    def _update_server(self, server_info: ServerInfo) -> None:
        """サブクラスで実装する抽象メソッド"""
        raise NotImplementedError("サブクラスでこのメソッドを実装する必要があります")

    def _send_completion_notification(
        self, success_count: int, failure_count: int, failed_servers: List[str]
    ) -> None:
        """更新完了をTeamsに通知"""
        if success_count == 0 and failure_count == 0:
            return

        title = f"{self.server_type} SSH接続設定更新完了"

        text_parts = [f"成功: {success_count}件, 失敗: {failure_count}件"]
        if failed_servers:
            text_parts.append("\n失敗したサーバー:")
            text_parts.extend(
                f"  - {server}" for server in failed_servers[:10]
            )  # 最大10件まで表示
            if len(failed_servers) > 10:
                text_parts.append(f"  ... 他{len(failed_servers) - 10}件")

        text = "\n".join(text_parts)
        self.notifier.send_notification(title, text)

    def _send_error_notification(self, error_message: str) -> None:
        """エラー通知を送信"""
        title = f"{self.server_type} エラー発生"
        self.notifier.send_notification(title, error_message)


class ValueServerUpdater(ServerUpdater):
    """ValueServerのSSH接続設定を更新するクラス"""

    # ValueServer固有のエンコーディング設定
    ENCODING = "shift_jis"

    def _update_server(self, server_info: ServerInfo) -> None:
        """ValueServerのSSH接続IPを更新"""
        current_ip = self.ip_fetcher.get_current_ip()
        logger.info(
            f"ValueServer更新開始: {server_info.url}, アカウント: {server_info.user_id}, 登録IP: {current_ip}"
        )

        payload = {
            "id": server_info.user_id,
            "pass": server_info.credential,
            "remote_host": current_ip,
            "ssh2": Config.SSH_KEYWORD.encode(self.ENCODING),
        }

        try:
            response = requests.post(
                Config.VALUE_SERVER_URL.format(server_info.url),
                data=payload,
                timeout=30,
            )
            response.raise_for_status()

            # レスポンスの検証
            if "エラー" in response.text or "失敗" in response.text:
                raise ValueError(f"サーバーエラーレスポンス: {response.text[:200]}")

            logger.info(f"ValueServer更新成功: {server_info.url}, 登録IP: {current_ip}")

        except requests.Timeout:
            raise TimeoutError(f"リクエストタイムアウト: {server_info.url}")
        except requests.RequestException as e:
            raise RuntimeError(f"HTTPエラー: {e}")


class CoreServerUpdater(ServerUpdater):
    """CoreServerのSSH接続設定を更新するクラス"""

    def _update_server(self, server_info: ServerInfo) -> None:
        """CoreServerのSSH接続IPを更新"""
        server_name = f"{server_info.url}.coreserver.jp"
        current_ip = self.ip_fetcher.get_current_ip()
        logger.info(
            f"CoreServer更新開始: {server_name}, アカウント: {server_info.user_id}, 登録IP: {current_ip}"
        )

        # APIリクエストの準備
        payload = (
            f"account={server_info.user_id}&"
            f"server_name={server_name}&"
            f"api_secret_key={server_info.credential}&"
            f"param[addr]={current_ip}"
        )
        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        try:
            # APIリクエスト送信
            response = requests.post(
                Config.CORE_SERVER_URL, data=payload, headers=headers, timeout=30
            )

            # レスポンスの詳細をログに記録（APIキーは除く）
            logger.info(f"CoreServer応答ステータス: {response.status_code}")

            # JSONレスポンスの解析とエラーチェック
            try:
                response_data = response.json()
            except ValueError:
                raise ValueError(f"無効なJSONレスポンス: {response.text[:200]}")

            if response_data.get("status_code") == 500:
                error_target = response_data.get("error_target", "")
                error_message = response_data.get("error_message", "")
                error_code = response_data.get("error_code", "")

                logger.error(
                    f"CoreServerエラー: {error_target}, {error_message}, コード: {error_code}"
                )

                # レート制限エラーの場合、追加の遅延を設定
                if "secret key error limit over" in error_target:
                    logger.warning(
                        f"レート制限検出: {Config.RATE_LIMIT_ADDITIONAL_DELAY}秒待機"
                    )
                    time.sleep(Config.RATE_LIMIT_ADDITIONAL_DELAY)
                    raise RuntimeError(f"レート制限エラー: {error_message}")

                raise RuntimeError(f"APIエラー: {error_message}")

            # 成功レスポンスの確認
            if response_data.get("status_code") != 200:
                raise RuntimeError(
                    f"予期しないステータスコード: {response_data.get('status_code')}"
                )

            logger.info(f"CoreServer更新成功: {server_name}, 登録IP: {current_ip}")

        except requests.Timeout:
            raise TimeoutError(f"リクエストタイムアウト: {server_name}")
        except requests.RequestException as e:
            raise RuntimeError(f"HTTPエラー: {e}")


def main():
    """メイン実行関数"""
    logger.info("=" * 50)
    logger.info("SSH接続更新処理を開始")
    logger.info("=" * 50)

    # 設定の検証
    Config.validate()

    try:
        # 通知ハンドラの初期化（ファクトリーパターンで生成）
        notifier = NotifierFactory.create()
        logger.info(f"通知サービス: {Config.NOTIFICATION_TYPE}")

        # 全体の結果を格納
        all_results = []

        # ValueServerの更新
        if Path(Config.VALUESERVER_CSV).exists():
            logger.info("\n--- ValueServer更新開始 ---")
            value_server_updater = ValueServerUpdater(
                Config.VALUESERVER_CSV, "ValueServer", notifier
            )
            value_results = value_server_updater.update_all_servers()
            all_results.extend(value_results)
        else:
            logger.warning(
                f"ValueServer CSVファイルが存在しません: {Config.VALUESERVER_CSV}"
            )

        # CoreServerの更新
        if Path(Config.CORESERVER_CSV).exists():
            logger.info("\n--- CoreServer更新開始 ---")
            core_server_updater = CoreServerUpdater(
                Config.CORESERVER_CSV, "CoreServer", notifier
            )
            core_results = core_server_updater.update_all_servers()
            all_results.extend(core_results)
        else:
            logger.warning(
                f"CoreServer CSVファイルが存在しません: {Config.CORESERVER_CSV}"
            )

        # 結果のサマリー
        success_count = sum(1 for r in all_results if r.success)
        failure_count = sum(1 for r in all_results if not r.success)

        # 現在のIPアドレスを最終確認として表示
        try:
            final_ip = IPAddressFetcher.get_current_ip()
            logger.info(f"\n最終確認 - 登録されたIPアドレス: {final_ip}")
        except Exception as e:
            logger.warning(f"最終IP確認時のエラー: {e}")

        logger.info("\n" + "=" * 50)
        logger.info(f"処理完了 - 成功: {success_count}件, 失敗: {failure_count}件")
        logger.info("=" * 50)

        # 失敗があった場合は詳細を表示
        if failure_count > 0:
            logger.error("\n失敗した更新:")
            for result in all_results:
                if not result.success:
                    logger.error(f"  - {result.server}: {result.error_message}")
            return 1  # エラーコードを返す

        return 0  # 正常終了

    except Exception as e:
        logger.error(f"予期しないエラー: {str(e)}")

        # エラーを通知サービスに通知
        try:
            error_notifier = NotifierFactory.create()
            error_title = "SSH接続更新 - 重大エラー"
            error_text = f"処理中に予期しないエラーが発生しました:\n{str(e)}"
            error_notifier.send_notification(error_title, error_text)
        except Exception as notify_error:
            logger.error(f"エラー通知の送信に失敗: {str(notify_error)}")

        return 1  # エラーコードを返す


if __name__ == "__main__":
    exit(main())
