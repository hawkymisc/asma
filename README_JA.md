# asma - Claude Code Skills Manager

[Claude Code](https://docs.anthropic.com/en/docs/claude-code) スキルのための宣言的パッケージマネージャー。vim-plug や Vundle にインスパイアされています。

> **Note**: このツールは Claude Code のスキルシステム専用に設計されています。`~/.claude/skills/`（グローバル）と `.claude/skills/`（プロジェクト）にインストールされるスキルを管理します。

## 免責事項

> **これは個人開発のアルファ版です。**
>
> - 実験的なソフトウェア - バグや破壊的変更があり得ます
> - このツールは非破壊的な設計です（シンボリックリンク作成とファイルコピーのみ）が、**自己責任でご使用ください**
> - 無保証です - コミットする前に変更内容を確認してください

## 機能

- **宣言的設定** - `skillset.yaml` でスキルを定義
- **ロックファイル管理** - `skillset.lock` で再現可能なインストール
- **マルチスコープ対応** - グローバル (`~/.claude/skills/`) とプロジェクト (`.claude/skills/`) スコープ
- **複数ソース対応** - ローカルファイルシステムまたは GitHub からインストール
- **バリデーション** - SKILL.md の構造とメタデータを検証
- **シンボリックリンク対応** - ローカルスキルは開発しやすいようにシンボリックリンク

## クイックスタート

### インストール

```bash
# pipx を使用（推奨）
pipx install git+https://github.com/hawkymisc/asma.git

# または pip を使用
pip install git+https://github.com/hawkymisc/asma.git
```

### 基本的な使い方

```bash
# 1. skillset.yaml を初期化
asma init

# 2. skillset.yaml を編集してスキルを追加

# 3. スキルをインストール
asma install

# 4. インストールを確認
asma list
asma check
```

## 設定

プロジェクトルートに `skillset.yaml` を作成:

```yaml
# グローバルスキル（~/.claude/skills/ にインストール）
global:
  - name: my-skill
    source: local:~/my-skills/my-skill

  - name: github-skill
    source: github:owner/repo
    version: v1.0.0

# プロジェクトスキル（.claude/skills/ にインストール）
project:
  - name: team-skill
    source: local:./skills/team-skill
```

### ソースタイプ

**ローカルファイルシステム:**
```yaml
- name: my-skill
  source: local:~/skills/my-skill      # 絶対パス
  source: local:./skills/my-skill      # 相対パス
```

**GitHub:**
```yaml
- name: skill-name
  source: github:owner/repo            # リポジトリルート
  source: github:owner/repo/subdir     # サブディレクトリ
  version: v1.0.0                      # タグまたは "latest"
  ref: main                            # ブランチまたはコミット SHA
```

プライベートリポジトリには `GITHUB_TOKEN` 環境変数を設定してください。

## コマンド

| コマンド | 説明 |
|---------|------|
| `asma init` | skillset.yaml テンプレートを作成 |
| `asma install` | skillset.yaml からスキルをインストール |
| `asma list` | インストール済みスキルを一覧表示 |
| `asma check` | インストール済みスキルの存在を確認 |
| `asma context` | スキルのメタデータ（SKILL.md frontmatter）を表示 |
| `asma version` | asma バージョンを表示 |

### コマンドオプション

**asma install**
```bash
asma install                      # すべてのスキルをインストール
asma install --scope global       # グローバルスキルのみ
asma install --force              # 強制再インストール
asma install --file custom.yaml   # 代替設定ファイルを使用
```

**asma list**
```bash
asma list                    # すべてのインストール済みスキルを表示
asma list --scope project    # スコープでフィルタリング
```

**asma check**
```bash
asma check                   # すべてのスキルをチェック
asma check --checksum        # チェックサムも検証
asma check --quiet           # エラーのみ表示
```

**asma context**
```bash
asma context                       # すべてのスキルのメタデータを表示
asma context my-skill              # 特定のスキルを表示
asma context --format yaml         # YAML で出力
asma context --format json         # JSON で出力
```

## スキル構造

有効なスキルには frontmatter 付きの `SKILL.md` が必要:

```markdown
---
name: my-skill
description: X を行うための便利なスキル
---

# My Skill

Claude Code への指示...
```

要件:
- `name`: 小文字、数字、ハイフンのみ
- `description`: 空でない文字列

## ロックファイル

`skillset.lock` は `asma install` 実行時に自動生成されます。正確なバージョンとチェックサムを記録し、再現可能なインストールを保証します。

**ベストプラクティス:**
- `skillset.lock` をバージョン管理にコミット
- 変更をプル後に `asma install` を実行
- 手動編集しない

## 開発

```bash
# クローンして開発モードでインストール
git clone https://github.com/hawkymisc/asma.git
cd asma
pip install -e ".[dev]"

# テストを実行
pytest
```

開発ガイドラインは [CONTRIBUTING.md](CONTRIBUTING.md) を参照してください。

## ライセンス

MIT
