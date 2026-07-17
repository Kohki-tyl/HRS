# MySQL 接続・実行手順

## 1. 前提条件

- Python 3.10 以上
- MySQL Server がインストール済みで起動中であること
- ルートユーザーまたは作業用ユーザーでデータベースを作成できること

## 2. MySQL の準備

### 2.1 MySQL サーバーを起動

Windows では、MySQL のサービスを起動します。

```powershell
net start MySQL80
```

もしサービス名が異なる場合は、以下で確認してください。

```powershell
Get-Service MySQL* 
```

### 2.2 データベースを作成

MySQL に接続して、以下を実行します。

```sql
CREATE DATABASE hrs_db;
```

必要に応じてユーザー権限を付与します。

```sql
CREATE USER 'hrs_user'@'localhost' IDENTIFIED BY 'your_password';
GRANT ALL PRIVILEGES ON hrs_db.* TO 'hrs_user'@'localhost';
FLUSH PRIVILEGES;
```

## 3. 接続設定例

本プロジェクトでは、接続情報を辞書形式で渡します。

```python
DB_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "hrs_user",
    "password": "your_password",
    "database": "hrs_db",
    "autocommit": False,
}
```

## 4. 実行手順

### 4.1 依存関係のインストール

```powershell
cd c:\Users\okada\.github\HRS\.code
py -3 -m pip install -r requirements.txt
```

> requirements.txt が未作成の場合は、次の内容を追加してください。

```txt
fastapi
uvicorn
line-bot-sdk
mysql-connector-python
pytest
```

### 4.2 アプリケーション起動

```powershell
cd c:\Users\okada\.github\HRS\.code
py -3 main.py
```

または、FastAPI サーバーとして起動する場合は次のように実行します。

```powershell
cd c:\Users\okada\.github\HRS\.code
py -3 -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 4.3 動作確認

ブラウザまたは curl で動作確認します。

```powershell
curl http://localhost:8000/docs
```

## 5. 期待される動作

- アプリケーション起動時に、MySQL のテーブルが自動作成される
- 予約の保存・照会・チェックイン・チェックアウトが DB 上で動作する
- LINE Webhook の受信と処理が可能な状態になる

## 6. トラブルシューティング

### 6.1 接続できない場合

- MySQL サービスが起動しているか確認
- host / user / password / database 名が正しいか確認
- ファイアウォールやポート 3306 の開放状況を確認

### 6.2 テーブル作成エラー

- データベース名が存在するか確認
- ユーザーに権限が付与されているか確認

### 6.3 モジュールが見つからない場合

```powershell
py -3 -m pip install --upgrade pip
py -3 -m pip install fastapi uvicorn line-bot-sdk mysql-connector-python pytest
```
