# Pull Request Summary

## Summary
<!-- 何を・なぜ変更したかを日本語で簡潔に記載する -->
-

## Changes
<!-- 変更点を層ごと（ui / application / domain / infrastructure / docs）に列挙する -->
-

## Testing
<!-- 実行したコマンドと結果（passed / failed の件数）を記載する -->

```powershell
cd .code
python -m pytest tests -q
```

- 結果:

## Notes
- 永続化は **SQLite** を使用する。DB ファイルのパスは環境変数 `HRS_DB_PATH`（既定 `.code/hrs.db`）で変更できる。初回起動時にスキーマは自動作成される。
- LINE を使わずに管理者画面を確認する場合は `python debug_web.py`（ログインパスワードは `ADMIN_PASSWORD`, 既定 `hrs-admin`）。
- 環境変数・実行手順の詳細は [README.md](../README.md), LINE 連携の設定は [LINE_SETUP.md](LINE_SETUP.md) を参照。
- 設計ドキュメントに影響する変更の場合は, [Design.md](../Design.md) / [Architecture.md](../Architecture.md) の該当箇所も更新する。
