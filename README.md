"# HRS" 

## 技術スタック ##
python 3.12+

## 仕様 ##
LINEのAPIを用いてホテル予約・チェックイン・チェックアウトを行うチャットボットシステム

## LINE Messaging API

LINE公式アカウント、Webhook、Channel secret、Channel access tokenの設定方法は
[LINE_SETUP.md](.code/LINE_SETUP.md) を参照してください。

Webhook URLは次の形式です。

```text
https://公開ホスト名/callback
```

稼働状態とLINE設定の有無は `GET /health` で確認できます。
