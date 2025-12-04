# Comment Sakusaku Checker

YouTubeコメントをAIでサクサク返信するツール

## 🚀 起動方法

### 1. ローカル環境で起動（自分だけで使う）

```bash
# プロジェクトディレクトリに移動
cd /Users/yuyumac/DO/youtube_comment_replyer

# 仮想環境を有効化
source venv/bin/activate

# アプリを起動
python app.py
```

ブラウザで `http://localhost:8080` にアクセス

### 2. Ngrok経由で外部公開（友人と共有）

```bash
# 1. アプリをバックグラウンドで起動
venv/bin/python app.py &

# 2. Ngrokでトンネルを開通
ngrok http 8080
```

表示されたURL（例: `https://xxxx.ngrok-free.dev`）を共有

**重要**: Ngrokを使う場合は、Google Cloud Consoleで以下のURLをリダイレクトURIに追加してください：
```
https://xxxx.ngrok-free.dev/oauth2callback
```

## 🛑 終了方法

```bash
# Flaskアプリとngrokを停止
pkill -f "python"
pkill -f "ngrok"
```

または、ターミナルウィンドウを閉じる

## 📋 確認コマンド

```bash
# ポート8080で動いているプロセスを確認
lsof -i :8080

# ngrokが動いているか確認
ps aux | grep ngrok

# ngrokのURLを確認
curl -s http://localhost:4040/api/tunnels | grep public_url
```

## ⚙️ 環境変数

`.env` ファイルに以下を設定：

```
SECRET_KEY=your-secret-key
CLIENT_SECRET_FILE=client_secret.json
GEMINI_API_KEY=your-gemini-api-key
```

## 🔧 トラブルシューティング

### ポート8080が使用中の場合

```bash
# 使用中のプロセスを強制終了
lsof -t -i :8080 | xargs kill -9
```

### Ngrokが "already online" エラーの場合

既にngrokが起動しています。以下で確認：

```bash
curl -s http://localhost:4040/api/tunnels
```

## 📦 依存関係のインストール

```bash
pip install -r requirements.txt
```
