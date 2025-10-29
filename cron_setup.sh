#!/bin/bash

# SSH接続更新スクリプトのcron設定例
# このスクリプトを参考にcrontabを設定してください

cat << 'EOF'
# SSH接続IPアドレス更新 - crontab設定例
#
# crontab -e で以下の行を追加してください：
#
# 15日ごとに実行する例（毎月1日と16日の午前3時）:
0 3 1,16 * * /usr/bin/python3 /home/user/apps/update_ssh_conn/app.py >> /home/user/apps/update_ssh_conn/log/cron.log 2>&1

# または、15日間隔で実行（毎月1日、15日、29日の午前3時）:
# 0 3 1,15,29 * * /usr/bin/python3 /home/user/apps/update_ssh_conn/app.py >> /home/user/apps/update_ssh_conn/log/cron.log 2>&1

# テスト用：毎日実行する場合:
# 0 3 * * * /usr/bin/python3 /home/user/apps/update_ssh_conn/app.py >> /home/user/apps/update_ssh_conn/log/cron.log 2>&1

# 注意事項:
# 1. Pythonのパスは環境によって異なる場合があります（which python3 で確認）
# 2. .envファイルは絶対パスで指定されていることを確認してください
# 3. ログファイルのディレクトリが存在することを確認してください
# 4. 実行権限があることを確認してください: chmod +x /home/user/apps/update_ssh_conn/app.py

# 動作確認用のテストコマンド:
# cd /home/user/apps/update_ssh_conn && /usr/bin/python3 app.py

EOF

echo ""
echo "現在のcrontab設定を確認するには: crontab -l"
echo "crontabを編集するには: crontab -e"