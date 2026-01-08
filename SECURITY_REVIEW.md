# セキュリティレビューレポート

**プロジェクト**: asma - Agent Skills Manager
**レビュー日**: 2026-01-08
**レビュー対象バージョン**: 0.1.0
**レビュアー**: Claude (Automated Security Review)

## エグゼクティブサマリー

asmaは、Claude Code用のスキルを管理するPython製のパッケージマネージャーです。本レビューでは、OWASP Top 10を含む一般的なセキュリティ脆弱性について包括的な分析を実施しました。

**総合評価**: 🟡 **中程度のリスク**

全体的にセキュリティ意識の高い実装がされていますが、**1件の重大な問題**と**いくつかの改善推奨事項**が見つかりました。

---

## 🔴 重大な問題（Critical）

### 1. Tar抽出のセキュリティ脆弱性（CVE-2007-4559類似）

**場所**: `asma/core/sources/github.py:224`

**問題の詳細**:
```python
tar.extractall(path=extract_dir, filter="data")
```

`filter="data"`パラメータはPython 3.12以降でのみ利用可能ですが、`pyproject.toml`では`requires-python = ">=3.8"`と指定されています。

**影響**:
- Python 3.8-3.11環境では、`filter`パラメータが無視されるか、TypeErrorが発生する可能性があります
- `filter`が適用されない場合、悪意のあるtarアーカイブによるパストラバーサル攻撃（ディレクトリトラバーサル）が可能になります
- 攻撃者が細工したGitHubリポジトリを通じて、システム上の任意の場所にファイルを書き込める可能性があります

**CVSS v3.1 スコア**: 8.1 (High)
- Attack Vector: Network
- Attack Complexity: Low
- Privileges Required: None
- User Interaction: Required
- Scope: Unchanged
- Confidentiality: None
- Integrity: High
- Availability: High

**修正推奨**:

#### オプション1: Python 3.12以上を必須にする
```toml
# pyproject.toml
requires-python = ">=3.12"
```

#### オプション2: バックワード互換性を保ちながら安全に実装する
```python
# asma/core/sources/github.py
import sys

def safe_extract(tar: tarfile.TarFile, path: Path) -> None:
    """Safely extract tarball with path traversal protection."""
    if sys.version_info >= (3, 12):
        # Python 3.12+: use built-in filter
        tar.extractall(path=path, filter="data")
    else:
        # Python 3.8-3.11: manual validation
        members = []
        for member in tar.getmembers():
            # Resolve the path and check it's within extract_dir
            member_path = (path / member.name).resolve()
            if not str(member_path).startswith(str(path.resolve())):
                raise ValueError(f"Attempted path traversal in tar: {member.name}")

            # Check for dangerous file types
            if member.issym() or member.islnk():
                # Validate symlink targets
                link_target = Path(member.linkname)
                if link_target.is_absolute() or ".." in link_target.parts:
                    raise ValueError(f"Dangerous symlink in tar: {member.name} -> {member.linkname}")

            members.append(member)

        tar.extractall(path=path, members=members)

# 使用箇所を更新:
# tar.extractall(path=extract_dir, filter="data")
# ↓
# safe_extract(tar, extract_dir)
```

#### オプション3: defusedxmlのようなライブラリを使用
```python
# 依存関係に追加
# dependencies = [..., "defusedtar>=0.1.0"]  # 仮想的な例
```

**優先度**: 🔴 **最高（即座に対処が必要）**

---

## 🟡 改善推奨事項（Medium Priority）

### 2. レート制限とDoS対策の欠如

**場所**: `asma/core/sources/github.py`

**問題の詳細**:
- GitHub APIのレート制限エラーは検出されますが、リトライロジックがありません
- タイムアウトは設定されていますが（30秒、60秒）、ダウンロードサイズの制限がありません
- 大きなリポジトリをダウンロードする際のディスク容量チェックがありません

**影響**:
- 悪意のあるユーザーが大きなリポジトリを指定して、ディスク容量を枯渇させる可能性があります
- ネットワーク障害時のリトライがないため、ユーザビリティが低下します

**修正推奨**:
```python
# asma/core/sources/github.py
MAX_DOWNLOAD_SIZE = 100 * 1024 * 1024  # 100 MB

def download(self, resolved: ResolvedSource) -> Path:
    # ...既存のコード...

    # ダウンロードサイズチェックを追加
    response = requests.get(
        resolved.download_url,
        headers=self._get_headers(),
        stream=True,
        timeout=60
    )
    response.raise_for_status()

    # Content-Lengthヘッダーをチェック
    content_length = response.headers.get('content-length')
    if content_length and int(content_length) > MAX_DOWNLOAD_SIZE:
        raise ValueError(f"Download size exceeds limit: {content_length} bytes")

    # ストリーミングダウンロード中もサイズをチェック
    downloaded_size = 0
    with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
        for chunk in response.iter_content(chunk_size=8192):
            downloaded_size += len(chunk)
            if downloaded_size > MAX_DOWNLOAD_SIZE:
                tmp_file.close()
                Path(tmp_file.name).unlink()
                raise ValueError(f"Download size exceeds limit during download")
            tmp_file.write(chunk)
    # ...残りの処理...
```

**優先度**: 🟡 **中（次回のリリースで対処）**

---

### 3. シンボリックリンクの検証不足

**場所**: `asma/core/installer.py:94`

**問題の詳細**:
```python
install_path.symlink_to(source_path, target_is_directory=True)
```

シンボリックリンクが作成される際、ターゲットパスの検証は行われていますが、追加の安全性チェックがあるとより良いです。

**影響**:
- ローカルソースからのインストール時に、意図しない場所へのシンボリックリンクが作成される可能性があります（現在の実装では`resolve()`により軽減済み）

**修正推奨**:
```python
# asma/core/installer.py
def install_skill(self, ...):
    # ...既存のコード...

    # Install (symlink or copy)
    is_symlink = source_handler.should_symlink()
    if is_symlink:
        # 追加の安全性チェック
        resolved_source = source_path.resolve()
        if not resolved_source.exists():
            return InstallResult(
                success=False,
                skill_name=skill.name,
                install_path=install_path,
                error=f"Source path does not exist: {resolved_source}"
            )

        # ホームディレクトリ外へのシンボリックリンクを警告
        home = Path.home()
        if not str(resolved_source).startswith(str(home)) and not str(resolved_source).startswith("/opt"):
            # 警告をログに記録（ブロックはしない）
            pass

        install_path.symlink_to(resolved_source, target_is_directory=True)
    # ...
```

**優先度**: 🟡 **中（次回のリリースで対処）**

---

### 4. 依存関係のバージョン固定

**場所**: `pyproject.toml`

**問題の詳細**:
```toml
dependencies = [
    "click>=8.0.0",
    "pyyaml>=6.0",
    "requests>=2.28.0",
    "rich>=13.0.0",
    "jsonschema>=4.17.0",
]
```

最小バージョンのみが指定されており、上限が設定されていません。

**影響**:
- 将来的に依存関係の破壊的変更により、予期しない動作やセキュリティ問題が発生する可能性があります
- 特に`pyyaml`と`requests`はセキュリティパッチが頻繁にリリースされます

**修正推奨**:
```toml
dependencies = [
    "click>=8.0.0,<9.0",
    "pyyaml>=6.0,<7.0",
    "requests>=2.28.0,<3.0",
    "rich>=13.0.0,<14.0",
    "jsonschema>=4.17.0,<5.0",
]
```

また、`dependabot`や`renovate`を使用して依存関係を自動更新することを推奨します。

**優先度**: 🟢 **低（将来的な改善）**

---

### 5. HTTPSの明示的な検証

**場所**: `asma/core/sources/github.py`

**問題の詳細**:
`requests`ライブラリはデフォルトでSSL検証を行いますが、明示的に指定されていません。

**修正推奨**:
```python
# asma/core/sources/github.py
response = requests.get(
    url,
    headers=self._get_headers(),
    timeout=30,
    verify=True  # 明示的にSSL検証を有効化
)
```

**優先度**: 🟢 **低（既にデフォルトで安全）**

---

## ✅ 良好な実装（Good Practices）

以下の点において、セキュリティのベストプラクティスが適切に実装されています：

### 1. コマンドインジェクションの防止 ✅
- `subprocess.run()`、`os.system()`、`eval()`、`exec()`などの危険な関数は一切使用されていません
- すべてのファイル操作はPythonの標準ライブラリの安全なAPIを使用しています

### 2. YAML安全性 ✅
- すべての箇所で`yaml.safe_load()`を使用しており、任意のコード実行を防いでいます
- `yaml.load()`（危険）は一切使用されていません

**検証箇所**:
- `asma/core/config.py:173`
- `asma/core/validator.py:85`
- `asma/core/context.py:129`
- `asma/models/lock.py:118`
- `asma/core/skillset_writer.py:44`

### 3. 入力検証 ✅
**スキル名の検証** (`asma/models/skill.py:32`):
```python
if not re.match(r'^[a-z0-9-]+$', self.name):
    raise ValueError(...)
```

**ソース形式の検証** (`asma/models/skill.py:39-44`):
```python
valid_prefixes = ('github:', 'local:', 'git:')
if not self.source.startswith(valid_prefixes):
    raise ValueError(...)
```

**SKILL.mdのフロントマター検証** (`asma/core/validator.py:55`):
```python
if not re.match(r'^[a-z0-9-]{1,64}$', frontmatter["name"]):
    errors.append(...)
```

### 4. パストラバーサル防止 ✅
**ローカルパスの正規化** (`asma/core/sources/local.py:28`):
```python
path = Path(path_str).expanduser().resolve()
```

`.resolve()`を使用することで、相対パスや`..`を含むパスが適切に処理されます。

### 5. 機密情報の管理 ✅
**GitHub トークンの取り扱い**:
- トークンは環境変数(`GITHUB_TOKEN`)から取得されます
- コードやログに直接埋め込まれていません
- HTTPヘッダーで安全に送信されます（HTTPS経由）

**検証箇所**:
- `asma/cli/main.py:415`
- `asma/core/sources/github.py:79`

### 6. エラー処理 ✅
- 適切な例外処理が実装されています
- センシティブな情報がエラーメッセージに含まれていません
- すべてのファイル操作でエラーハンドリングが行われています

### 7. 型安全性 ✅
`mypy`の厳格な設定:
```toml
[tool.mypy]
disallow_untyped_defs = true
disallow_incomplete_defs = true
check_untyped_defs = true
```

型アノテーションにより、多くの潜在的なバグを事前に検出できます。

---

## 🔍 追加の推奨事項

### 1. セキュリティポリシーの策定
`SECURITY.md`ファイルを作成し、脆弱性報告のプロセスを明確にすることを推奨します。

```markdown
# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in asma, please report it by emailing
[security@example.com] or opening a private security advisory on GitHub.

Please do NOT open a public issue for security vulnerabilities.

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |
```

### 2. セキュリティテストの追加
以下のテストケースを追加することを推奨します：

```python
# tests/test_security.py
def test_path_traversal_in_local_source():
    """Test that path traversal attempts are blocked."""
    with pytest.raises(FileNotFoundError):
        skill = Skill(
            name="malicious",
            source="local:../../../../etc/passwd",
            scope=SkillScope.PROJECT
        )
        handler = LocalSourceHandler()
        handler.resolve(skill)

def test_dangerous_tar_extraction():
    """Test that malicious tar files are rejected."""
    # Create a tar with path traversal
    # Verify it's rejected
    pass

def test_skill_name_injection():
    """Test that skill names with special characters are rejected."""
    with pytest.raises(ValueError):
        Skill(
            name="../../../etc/passwd",
            source="github:test/test",
            scope=SkillScope.PROJECT
        )
```

### 3. 依存関係の脆弱性スキャン
GitHub Dependabotまたは`safety`ツールを使用して、依存関係の脆弱性を定期的にスキャンすることを推奨します。

```yaml
# .github/dependabot.yml
version: 2
updates:
  - package-ecosystem: "pip"
    directory: "/"
    schedule:
      interval: "weekly"
    open-pull-requests-limit: 10
```

### 4. CI/CDでのセキュリティチェック
```yaml
# .github/workflows/security.yml
name: Security Checks

on: [push, pull_request]

jobs:
  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run safety check
        run: |
          pip install safety
          safety check
      - name: Run bandit
        run: |
          pip install bandit
          bandit -r asma/
```

---

## 📊 リスク評価マトリックス

| 脆弱性 | 重大度 | 影響 | 悪用の容易性 | 優先度 |
|--------|--------|------|--------------|--------|
| Tar抽出の脆弱性 | High | High | Medium | 🔴 Critical |
| DoS対策の欠如 | Medium | Medium | Low | 🟡 Medium |
| シンボリックリンク検証 | Low | Low | Low | 🟡 Medium |
| 依存関係のバージョン | Low | Medium | Low | 🟢 Low |

---

## 📝 対応アクションアイテム

### 即座に対応（1週間以内）
- [ ] **🔴 [Critical]** Tar抽出の脆弱性を修正（Python 3.12以上を必須にするか、安全な抽出ロジックを実装）
- [ ] 修正後にセキュリティテストを追加

### 次回リリース（1ヶ月以内）
- [ ] **🟡 [Medium]** ダウンロードサイズ制限を実装
- [ ] **🟡 [Medium]** シンボリックリンクの追加検証を実装
- [ ] SECURITY.mdを作成

### 将来的な改善
- [ ] **🟢 [Low]** 依存関係のバージョン上限を設定
- [ ] **🟢 [Low]** Dependabotを有効化
- [ ] **🟢 [Low]** CI/CDにセキュリティスキャンを追加
- [ ] HTTPSの明示的な検証を追加

---

## 結論

asmaプロジェクトは全体的にセキュリティ意識の高い実装がされていますが、**tar抽出の脆弱性**は即座に対処が必要です。この問題を修正すれば、プロダクション環境で使用するのに十分な安全性が確保されます。

その他の改善推奨事項は、プロジェクトの成熟度を高め、長期的なメンテナンス性を向上させるために有用です。

**次のステップ**:
1. tar抽出の脆弱性を修正するためのパッチを作成
2. セキュリティテストを追加
3. パッチをリリース（v0.1.1）
4. SECURITY.mdを作成し、脆弱性報告プロセスを確立

---

**レビュー完了日**: 2026-01-08
