#!/bin/bash
# エラー通知ヘルパー
# 使い方: bash notify_error.sh "SNS名" コマンド...

SNS_NAME="$1"
shift

"$@"
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    osascript -e "display notification \"${SNS_NAME} の投稿に失敗しました（コード: ${EXIT_CODE}）\" with title \"天弥堂 SNS エラー\" sound name \"Basso\""
fi

exit $EXIT_CODE
