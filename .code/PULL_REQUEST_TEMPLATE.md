# Pull Request Summary

## Summary
- MySQL ベースの予約リポジトリ実装を追加しました。
- 予約の保存・検索・復元処理をインフラ層として実装しました。
- スキーマ作成処理とテストを追加しました。

## Changes
- Added MySQL reservation repository implementation
- Added SQL schema for reservations and reservation_rooms
- Added repository tests for save/find behavior
- Added setup guide for local MySQL execution

## Testing
- Verified with:

```powershell
cd c:\Users\okada\.github\HRS\.code
py -3 -m pytest -q tests/test_mysql_repository.py
```

## Notes
- MySQL サーバーが必要です。
- 接続情報は環境やローカル設定に合わせて変更してください。
- 詳細な実行手順は [MYSQL_SETUP_GUIDE.md](MYSQL_SETUP_GUIDE.md) を参照してください。
