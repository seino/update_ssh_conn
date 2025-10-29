# SSH 接続 IP 自動更新スクリプト

ValueServer と CoreServer の SSH 接続許可 IP アドレスを自動更新する Python スクリプト

## 機能

- 複数サーバーの SSH 接続 IP 設定を一括更新
- 環境変数による柔軟な設定管理
- 複数の通知サービスに対応（Teams / Slack / Chatwork）
- エラーハンドリングとリトライ機能
- 固定 IP 指定または動的 IP 取得の選択可能
- IPv4/IPv6 対応の厳密な IP アドレス検証
- cron による定期実行対応

## セットアップ

### 1. 依存パッケージのインストール

```bash
pip install -r requirements.txt
```

### 2. 環境設定

`.env.example`を`.env`にコピーして設定を編集:

```bash
cp .env.example .env
```

主な設定項目:

- `NOTIFICATION_TYPE`: 通知サービスの種類（`teams`, `slack`, `chatwork`）
- `TEAMS_WEBHOOK_URL`: Teams 通知用の Webhook URL
- `SLACK_WEBHOOK_URL`: Slack 通知用の Webhook URL
- `CHATWORK_API_TOKEN`: Chatwork API トークン
- `CHATWORK_ROOM_ID`: Chatwork ルーム ID
- `FIXED_IP_ADDRESS`: 固定 IP アドレス（省略時は動的取得）
- `VALUESERVER_CSV`: ValueServer の認証情報 CSV パス
- `CORESERVER_CSV`: CoreServer の認証情報 CSV パス

### 3. CSV ファイルの準備

`csv/`ディレクトリに CSV ファイルを配置:

#### ValueServer 用 (list_valueserver.csv)

```csv
サブドメイン,アカウント,パスワード
example1,user1,password1
example2,user2,password2
```

#### CoreServer 用 (list_coreserver.csv)

```csv
サブドメイン,アカウント,APIキー
c1001,account1,apikey1
c1002,account2,apikey2
```

## 使用方法

### 手動実行

```bash
python app.py
```

### Cron 設定（15 日ごとの自動実行）

```bash
# crontabを編集
crontab -e

# 毎月1日と16日の午前3時に実行
0 3 1,16 * * /usr/bin/python3 /home/user/apps/update_ssh_conn/app.py >> /home/user/apps/update_ssh_conn/log/cron.log 2>&1
```

詳細は`cron_setup.sh`を参照してください。

## 固定 IP アドレスの使用

特定の IP アドレスを登録したい場合は、`.env`ファイルで指定:

```bash
# 固定IPを使用
FIXED_IP_ADDRESS=123.456.789.012

# 動的に取得（空欄にする）
FIXED_IP_ADDRESS=
```

## ログ

実行時のログは標準出力に表示されます。cron 実行時は指定したログファイルに記録されます。

ログ内容:

- 各サーバーの更新開始/成功/失敗
- 登録された IP アドレス
- エラー詳細とリトライ情報
- Teams 通知の送信状況

## トラブルシューティング

### CSV ファイルが見つからない

- ファイルパスが正しいか`.env`で確認
- ファイルの存在と読み取り権限を確認

### 通知が届かない

- 使用する通知サービスに応じて設定を確認:
  - **Teams**: `TEAMS_WEBHOOK_URL` が正しいか確認
  - **Slack**: `SLACK_WEBHOOK_URL` が正しいか確認
  - **Chatwork**: `CHATWORK_API_TOKEN` と `CHATWORK_ROOM_ID` が正しいか確認
- `NOTIFICATION_TYPE` が正しく設定されているか確認（`teams`, `slack`, `chatwork`）
- `ENABLE_NOTIFICATIONS=true` になっているか確認

### IP 取得エラー

- インターネット接続を確認
- `IP_CHECK_URL`のサービスが稼働しているか確認
- 固定 IP アドレスの使用を検討

## セキュリティ

- `.env`ファイルは`.gitignore`に登録済み
- CSV ファイルも同様に Git 管理対象外
- 認証情報は環境変数で管理
- ログにパスワードや API キーは記録されません
