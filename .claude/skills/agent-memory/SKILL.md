# Agent Memory Skill

エージェントが対話中の重要な情報を記憶・想起するためのスキルです。

## トリガー

以下のような発話を検知したときに、このスキルを起動してください:

- 「これを記憶して」「覚えておいて」「メモして」
- 「思い出して」「覚えてる?」「前に話した〜」
- 「記憶を確認」「何を覚えてる?」「メモリーを見せて」
- 「記憶を削除」「忘れて」

## 動作

### 1. 記憶を保存する (Save Memory)

ユーザーが記憶を依頼したとき:

1. 記憶する内容を要約して確認する
2. `memories/` ディレクトリに Markdown ファイルとして保存
3. ファイル名: `YYYY-MM-DD-{short-description}.md`
4. フォーマット:

```markdown
---
summary: 簡潔な要約（1行）
tags: [tag1, tag2, tag3]
created: YYYY-MM-DDTHH:MM:SSZ
---

# タイトル

詳細な内容...
```

**実装方法:**
```bash
# 1. ファイル名を生成
DATE=$(date +%Y-%m-%d)
SLUG="short-description"  # ユーザー入力から生成
FILENAME="memories/${DATE}-${SLUG}.md"

# 2. Write toolでファイル作成
# (frontmatter + content)

# 3. 確認メッセージ
echo "✓ 記憶しました: ${SLUG}"
```

### 2. 記憶を想起する (Recall Memory)

ユーザーが記憶の想起を依頼したとき:

1. `memories/` ディレクトリをGrepで検索
2. キーワードに関連するファイルを特定
3. 該当ファイルを読み込んで内容を表示

**実装方法:**
```bash
# 1. キーワードで検索 (summaryをripgrep)
# Grep tool: pattern="キーワード", path=".claude/skills/agent-memory/memories/"

# 2. 該当ファイルが見つかったら Read tool で読み込み

# 3. 内容をユーザーに提示
```

### 3. 記憶一覧を表示する (List Memories)

ユーザーが記憶の確認を依頼したとき:

1. `memories/` 内の全ファイルを列挙
2. 各ファイルの `summary` を抽出して表示

**実装方法:**
```bash
# 1. Glob tool: pattern="*.md", path=".claude/skills/agent-memory/memories/"

# 2. 各ファイルをRead toolで読み込み、frontmatterのsummaryを抽出

# 3. リスト形式で表示:
# - 2026-01-09: AI context tracking workflow implementation
# - 2026-01-08: User requested feature X
```

### 4. 記憶を削除する (Delete Memory)

ユーザーが記憶の削除を依頼したとき:

1. 削除対象を確認
2. ファイルを削除

**実装方法:**
```bash
# 1. 削除対象のファイル名を確認

# 2. Bash tool: rm memories/{filename}.md

# 3. 確認メッセージ
```

## 段階的開示パターン

記憶の想起時は、以下の順序で効率的に情報を取得します:

1. **Grep**で `summary:` フィールドを検索 → 概要を把握
2. 必要なファイルのみ **Read** → 詳細を取得

これにより、不要な全文読み込みを避け、トークン使用量を最適化します。

## ユースケース

### 1. 作業中断時の記憶
```
ユーザー: 「今やってる作業を記憶しておいて。後で戻ってくる」
エージェント: (現在の状態を要約して保存)
```

### 2. 設計方針の記録
```
ユーザー: 「このプロジェクトではSupabase AuthとGemini APIを使うって決めたこと、覚えておいて」
エージェント: (技術スタックの決定を記憶)
```

### 3. 調査結果の保存
```
ユーザー: 「さっき調べたYouTube API v3のコメント取得方法、メモしておいて」
エージェント: (APIの使い方を記憶)
```

### 4. 長期的なコンテキスト管理
```
ユーザー: 「前に話した収益目標、覚えてる?」
エージェント: (memories/ を検索して該当記憶を想起)
```

## プロジェクト固有の拡張

ReplyAIプロジェクトでは、以下のような情報を記憶すると有用:

- **ビジネス目標**: 月間売上目標 (¥1,000,000)
- **技術スタック決定**: Supabase Auth, Gemini 2.5 Flash Lite, Flask
- **開発ポリシー**: Dev mode first, user approval before production
- **ユーザーフィードバック**: 「この機能が欲しい」といったリクエスト
- **バグ情報**: 「このエラーが出た」という報告
- **APIクォータ管理**: YouTube API使用量の制限値

## タグの推奨

記憶を分類するために、以下のタグを使用してください:

- `business` - ビジネス目標、戦略
- `technical` - 技術仕様、アーキテクチャ
- `feature-request` - 機能リクエスト
- `bug` - バグ報告
- `decision` - 重要な意思決定
- `reminder` - リマインダー
- `research` - 調査結果
- `meeting` - ミーティングメモ

## 注意事項

- 機密情報（パスワード、APIキーなど）は記憶しない
- `memories/` は `.gitignore` で除外されているため、個人用途のみ
- チーム共有したい情報は `documents/` に別途記録する

## 実装チェックリスト

エージェントがこのスキルを使用する際:

- [ ] ユーザーの発話からトリガーを検知
- [ ] 記憶内容を要約して確認
- [ ] 適切なタグを付与
- [ ] ファイル名は日付ベースで衝突を回避
- [ ] 想起時は段階的開示パターンを使用
- [ ] 操作完了後、確認メッセージを表示

## 例

### 記憶の保存例

**ユーザー**: 「Elena さんのカバー曲投稿戦略、週20時間で4000時間達成を目指すって話、覚えておいて」

**エージェント**:
```markdown
記憶します。以下の内容でよろしいですか?

**要約**: Elenaさんのカバー曲戦略 - 週20時間で4000時間視聴達成目標

**詳細**:
- 工数: 週20時間
- 目標: 4000時間達成
- 施策: Instagram Reels、YouTube Live、カバー曲投稿

タグ: business, strategy, elena
```

(ユーザーの承認後)

```bash
# .claude/skills/agent-memory/memories/2026-01-09-elena-cover-strategy.md に保存
✓ 記憶しました: elena-cover-strategy
```

### 記憶の想起例

**ユーザー**: 「Elenaさんの戦略、何だっけ?」

**エージェント**:
```bash
# 1. Grep で "Elena" を検索
# 2. 該当ファイル: memories/2026-01-09-elena-cover-strategy.md
# 3. Read tool で読み込み
```

```markdown
思い出しました!

**Elenaさんのカバー曲投稿戦略** (2026-01-09に記録)

- 工数: 週20時間
- 目標: 4000時間視聴達成
- 施策:
  - Instagram Reelsへのタグ追加
  - 定期的なYouTube Live配信
  - カバー曲のYoutube Long投稿

カバー曲制作工程:
- 選定: 5時間
- 準備: 5時間
- 撮影: 1時間
- タグ選定: 1時間
- 投稿: 30分

推奨タグ: #Elena, #歌ってみた, #カバー
```
