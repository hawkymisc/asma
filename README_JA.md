# asma - Agent Skills Manager

Claude Agent Skills のための宣言的パッケージマネージャー。vim-plug や Vundle にインスパイアされています。

## ⚠️ 免責事項

> **これは個人開発のα版（アルファ版）です。**
>
> - 🧪 **Vibe Coding** で構築 - AIアシストによるペアプログラミングで開発
> - 🔬 実験的なソフトウェア - バグや破壊的変更があり得ます
> - ⚡ このツールは非破壊的な設計です（`.claude/skills/` へのシンボリックリンク作成とファイルコピーのみ）が、**自己責任でご使用ください**
> - 💡 無保証です - バージョン管理にコミットする前に変更内容を確認してください

## ステータス

**MVP コア機能完了** ✅
- ✅ `asma init` - skillset.yaml の初期化
- ✅ `asma install` - skillset からスキルをインストール
- ✅ `asma list` - インストール済みスキル一覧表示
- ✅ `asma version` - バージョン表示
- ✅ ローカルファイルシステムソース (`local:`)
- ✅ GitHub ソース (`github:`)
- ✅ SKILL.md バリデーション
- ✅ グローバルとプロジェクトスコープ
- ✅ ロックファイル管理 (`skillset.lock`)

## 機能

- 📦 **宣言的設定**: `skillset.yaml` でスキルを定義
- 🔒 **ロックファイル管理**: 自動生成される `skillset.lock` で再現可能なインストールを保証
- 🌍 **マルチスコープ対応**: グローバル (`~/.claude/skills/`) とプロジェクト (`.claude/skills/`) スコープ
- ⚡ **シンプルな CLI**: 直感的なスキル管理コマンド
- ✅ **バリデーション**: SKILL.md の構造とメタデータを検証
- 🔗 **シンボリックリンク対応**: ローカルスキルは開発しやすいようにシンボリックリンクされます
- 🎨 **カラー出力**: 明確な進行状況とエラーメッセージ

## クイックスタート

### 1. インストール

#### オプション A: pipx（推奨）

```bash
# pipx がインストールされていない場合はインストール
pip install pipx
pipx ensurepath

# asma をグローバルにインストール
pipx install git+https://github.com/hawkymisc/asma.git

# または、ローカルクローンからインストール
git clone https://github.com/hawkymisc/asma.git
cd asma
pipx install .
```

#### オプション B: pip（開発用）

```bash
# リポジトリをクローン
git clone https://github.com/hawkymisc/asma.git
cd asma

# pip でインストール（開発用エディタブルモード）
pip install -e .
```

#### アンインストール

```bash
# pipx でインストールした場合
pipx uninstall asma

# pip でインストールした場合
pip uninstall asma
```

### 2. プロジェクトの初期化

```bash
# skillset.yaml テンプレートを作成
asma init
```

### 3. スキルを定義

`skillset.yaml` を編集:

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

### 4. スキルをインストール

```bash
# すべてのスキルをインストール
asma install

# グローバルスキルのみインストール
asma install --scope global

# 強制再インストール
asma install --force
```

## skillset.yaml フォーマット

```yaml
# オプションのグローバル設定
config:
  auto_update: false
  parallel_downloads: 4
  github_token_env: GITHUB_TOKEN

# グローバルスキル（個人用、すべてのプロジェクトで共有）
global:
  - name: document-analyzer
    source: local:~/skills/document-analyzer
    # オプションフィールド:
    # version: v1.0.0         # git ソース用
    # ref: main               # git ソース用
    # enabled: true           # false の場合スキップ
    # alias: custom-name      # 別名でインストール

  - name: code-reviewer
    source: github:anthropics/skills/code-reviewer
    version: v2.0.0

# プロジェクトスキル（チーム共有、バージョン管理）
project:
  - name: test-runner
    source: local:./local-skills/test-runner
```

## ソースタイプ

### ローカルソース (`local:`)

ローカルファイルシステムからスキルをインストール:

```yaml
- name: my-skill
  source: local:~/skills/my-skill      # 絶対パス
  source: local:./skills/my-skill      # 相対パス
```

### GitHub ソース (`github:`)

GitHub リポジトリからスキルをインストール:

```yaml
- name: skill-name
  source: github:owner/repo            # リポジトリルート
  source: github:owner/repo/subdir     # サブディレクトリ

# バージョン/ref 指定
- name: skill-with-version
  source: github:owner/repo
  version: v1.0.0                      # 特定タグ
  version: latest                      # 最新リリース

- name: skill-with-ref
  source: github:owner/repo
  ref: main                            # ブランチ
  ref: abc1234                         # コミット SHA
```

**認証**: プライベートリポジトリには `GITHUB_TOKEN` 環境変数を設定してください。

## コマンド

### `asma init`
テンプレート付きの新しい skillset.yaml ファイルを初期化。

**オプション**:
- `--force` - 既存ファイルを上書き

**例**:
```bash
asma init
asma init --force
```

### `asma install`
skillset.yaml からスキルをインストール。

**オプション**:
- `--file <path>` - 代替の skillset ファイルを使用（デフォルト: `./skillset.yaml`）
- `--scope <global|project>` - 指定したスコープのみインストール
- `--force` - インストール済みでも再インストール

**例**:
```bash
# すべてのスキルをインストール
asma install

# グローバルスキルのみインストール
asma install --scope global

# カスタムファイルを使用
asma install --file custom-skills.yaml

# 強制再インストール
asma install --force
```

### `asma list`
skillset.lock からインストール済みスキルを一覧表示。

**オプション**:
- `--scope <global|project>` - スコープでフィルタリング

**例**:
```bash
# すべてのインストール済みスキルを一覧表示
asma list

# グローバルスキルのみ表示
asma list --scope global

# プロジェクトスキルのみ表示
asma list --scope project
```

**出力例**:
```
Global Skills:
  • document-analyzer
    Source: github:anthropics/skills/document-analyzer
    Version: v1.0.0

Project Skills:
  • test-runner
    Source: local:/path/to/skills/test-runner
    Version: local@abc123
```

### `asma version`
asma バージョンを表示。

**例**:
```bash
asma version
# 出力: asma version 0.1.0
```

## スキル構造

有効なスキルには frontmatter 付きの `SKILL.md` が必要:

```markdown
---
name: my-skill
description: X を行うための便利なスキル
---

# My Skill

## Instructions
Claude への詳細な指示...

## Examples
- 例 1
- 例 2

## Guidelines
- ガイドライン 1
- ガイドライン 2
```

**要件**:
- `name`: 小文字、数字、ハイフンのみ（例: `my-skill-123`）
- `description`: スキルの目的を説明する空でない文字列

## ロックファイル (`skillset.lock`)

`skillset.lock` ファイルは `asma install` 実行時に**自動生成**され、再現可能なスキルインストールを保証します。

**目的**:
- 🔒 インストールされたスキルの正確なバージョンとチェックサムを記録
- 📌 チームメンバー間で一貫した環境を保証
- ✅ 整合性検証のためのインストールメタデータを追跡

**フォーマット**（自動生成 - 手動編集不可）:
```yaml
version: 1
generated_at: "2025-12-29T12:00:00Z"
skills:
  global:
    my-skill:
      source: github:owner/repo
      resolved_version: v1.2.3
      resolved_commit: abc123def456
      installed_at: "2025-12-29T11:59:30Z"
      checksum: sha256:9f86d081884c7d659a2feaa0...

  project:
    team-skill:
      source: local:/path/to/skill
      resolved_version: local@def456ab
      resolved_commit: def456ab
      installed_at: "2025-12-29T12:00:15Z"
      checksum: sha256:5e884898da28047...
      symlink: true
      resolved_path: /path/to/skill
```

**ベストプラクティス**:
- ✅ **`skillset.lock` をバージョン管理にコミット**（`package-lock.json` と同様）
- ✅ **変更をプル後に `asma install` を実行**してロックされたバージョンと同期
- ❌ **手動編集しない** - asma に管理させる

## 開発

### セットアップ

```bash
# 開発用依存関係と一緒にインストール
pip install -e ".[dev]"
```

### テストの実行

```bash
# すべてのテストを実行
pytest

# カバレッジ付きで実行
pytest --cov=asma

# 特定のテストファイルを実行
pytest tests/test_validator.py -v
```

### テストカバレッジ

**現在**: 107 テスト、**98% カバレッジ**

| モジュール | カバレッジ | テスト数 |
|-----------|-----------|---------|
| cli/main | 98% | 22 |
| core/config | 100% | 10 |
| core/installer | 100% | 9 |
| core/validator | 100% | 11 |
| models/skill | 100% | 8 |
| models/lock | 94% | 7 |
| sources/local | 100% | 8 |
| sources/github | 99% | 32 |

### TDD アプローチ

このプロジェクトは Kent Beck のテスト駆動開発方法論に従っています:
1. 🔴 **RED**: 最初に失敗するテストを書く
2. 🟢 **GREEN**: パスするための最小限のコードを実装
3. 🔵 **REFACTOR**: 実装をクリーンアップ

## ドキュメント

- [SPEC.md](SPEC.md) - 完全な技術仕様（MVP 要件、コマンド、フォーマット）
- [DESIGN.md](DESIGN.md) - 詳細設計ドキュメント（アーキテクチャ、アルゴリズム、データモデル）

## ロードマップ

### ✅ MVP（完了）
- [x] プロジェクト構造とビルドシステム
- [x] SKILL.md バリデータ
- [x] Skill と Skillset モデル
- [x] ローカルソースハンドラー
- [x] GitHub ソースハンドラー
- [x] スキルインストーラー
- [x] CLI コマンド（init, version, install）

### 🚧 次のステップ
- [x] ロックファイル管理（`skillset.lock`）- **完了** ✅
- [x] `asma list` コマンド - **完了** ✅
- [ ] `asma update` コマンド
- [ ] `asma uninstall` コマンド
- [ ] Git ソースハンドラー（`git:https://...`）

### 🔮 将来
- [ ] 依存関係解決
- [ ] 中央スキルレジストリ
- [ ] スキル検索と発見
- [ ] 並列インストール
- [ ] インストールフック

## コントリビューション

コントリビューション歓迎！以下の手順で:
1. リポジトリをフォーク
2. フィーチャーブランチを作成
3. テストを書く（TDD アプローチ）
4. すべてのテストがパスすることを確認（`pytest`）
5. プルリクエストを送信

## ライセンス

MIT
