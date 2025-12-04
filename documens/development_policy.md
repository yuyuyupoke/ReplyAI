# 開発方針
基本的に、Dev環境（`USE_MOCK_DATA=true`）でアプリケーションの構築、動作確認を行う。
ユーザーが承認した後、本番環境（Google 認証付きの環境）にコードを反映する。

API機能を実装するときは、**必ず**以下のAPIリファレンスを参照すること。
https://developers.google.com/youtube/v3/docs?hl=en&_gl=1*1t90ld9*_up*MQ..*_ga*NjMwNTk2Mjc1LjE3NjQ4MzIyNjg.*_ga_SM8HXJ53K2*czE3NjQ4MzIyNjgkbzEkZzAkdDE3NjQ4MzIyNjgkajYwJGwwJGgw

## 運用フロー
1. **Dev環境での実装**:
   - 新機能や修正はまずDevモードで実装する。
   - `mock_youtube_service.py` を使用して、Google APIに依存しない形で動作確認を行う。
   - 必要に応じてモックデータを調整し、エッジケースのテストも行う。

2. **ユーザー承認**:
   - Dev環境での動作をユーザー（またはAIエージェントのブラウザテスト）が確認する。
   - スクリーンショットやログを用いて動作を証明する。

3. **本番反映**:
   - 承認が得られたら、本番環境（`app.py` の `USE_MOCK_DATA=false`）での動作を想定した最終確認を行う。
   - 必要であれば本番環境でのスモークテストを行う（ただし、APIクォータやデータへの影響を最小限にする）。


## テスト方針
実装したら、全てのボタンが正常に動作するのかを、Antigravity Browser Extensionを利用して 必ず確認する
