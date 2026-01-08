# セキュリティレビューレポート（第2回・詳細分析）

**プロジェクト**: asma - Agent Skills Manager
**レビュー日**: 2026-01-08（第2回）
**レビュー対象バージョン**: commit 5248431
**レビュアー**: Claude (Security Specialist - Deep Dive)

## エグゼクティブサマリー

第1回レビューで発見された**重大なtar抽出の脆弱性**は修正されました。第2回レビューでは、より詳細な分析を実施し、**4件の追加の脆弱性**と**8件の改善推奨事項**を発見しました。

**総合評価**: 🟡 **中程度のリスク（改善推奨）**

修正された脆弱性により、基本的なセキュリティは確保されていますが、追加の攻撃ベクトルと防御強化の機会が存在します。

---

## 🔴 新たに発見された重大な問題

### 1. Tar Bomb（圧縮爆弾）攻撃への脆弱性

**場所**: `asma/core/sources/github.py:295-303`

**問題の詳細**:
Tarアーカイブのサイズ制限や、展開後のファイル数・サイズの制限がないため、悪意のあるユーザーが極端に大きな圧縮ファイルを用いてディスク容量を枯渇させることが可能です。

**攻撃シナリオ**:
```python
# 攻撃者が作成する悪意のあるtarアーカイブの例：
# - 圧縮前: 1MB
# - 圧縮後: 10KB
# - 圧縮率: 100:1 または 1000:1（Zip bomb）
# - 展開すると数GB～数TBのディスク容量を消費
```

**影響**:
- ディスク容量の枯渇によるDoS攻撃
- システム全体のパフォーマンス低下
- 他のアプリケーションへの影響

**CVSS v3.1 スコア**: 7.5 (High)
- Attack Vector: Network
- Attack Complexity: Low
- Privileges Required: None
- User Interaction: None
- Scope: Unchanged
- Confidentiality: None
- Integrity: None
- Availability: High

**修正推奨**:

```python
# asma/core/sources/github.py

# 設定値を追加
MAX_EXTRACT_SIZE = 500 * 1024 * 1024  # 500 MB
MAX_FILE_COUNT = 10000
MAX_SINGLE_FILE_SIZE = 100 * 1024 * 1024  # 100 MB

def _safe_extract_tarball(self, tar: tarfile.TarFile, extract_dir: Path) -> None:
    """
    Safely extract tarball with path traversal and tar bomb protection.
    """
    if sys.version_info >= (3, 12):
        tar.extractall(path=extract_dir, filter="data")
    else:
        safe_members = []
        extract_dir_resolved = extract_dir.resolve()
        total_size = 0
        file_count = 0

        for member in tar.getmembers():
            # 既存の検証...

            # Tar bomb protection: check file count
            file_count += 1
            if file_count > MAX_FILE_COUNT:
                raise ValueError(
                    f"Tar archive contains too many files (>{MAX_FILE_COUNT}). "
                    f"Possible tar bomb attack."
                )

            # Tar bomb protection: check individual file size
            if member.size > MAX_SINGLE_FILE_SIZE:
                raise ValueError(
                    f"File too large in tar: {member.name} ({member.size} bytes, "
                    f"max {MAX_SINGLE_FILE_SIZE}). Possible tar bomb attack."
                )

            # Tar bomb protection: check total extracted size
            total_size += member.size
            if total_size > MAX_EXTRACT_SIZE:
                raise ValueError(
                    f"Total extracted size exceeds limit ({total_size} bytes, "
                    f"max {MAX_EXTRACT_SIZE}). Possible tar bomb attack."
                )

            # 既存の検証...
            safe_members.append(member)

        tar.extractall(path=extract_dir, members=safe_members)
```

**優先度**: 🔴 **高（2週間以内に対処）**

---

### 2. デバイスファイルと特殊ファイルのチェック欠如

**場所**: `asma/core/sources/github.py:95-142`

**問題の詳細**:
Tarアーカイブ内のデバイスファイル（block/character devices）、FIFO、特殊ファイルのチェックが実装されていません。これらのファイルは、展開時にシステムの脆弱性を引き起こす可能性があります。

**攻撃シナリオ**:
- `/dev/zero`や`/dev/random`へのアクセスを含むtarアーカイブ
- FIFOを使ったハングアップ攻撃
- Setuid/setgidビットを持つファイル

**影響**:
- システムリソースの不正利用
- プロセスのハングアップ
- 権限昇格の可能性（低確率）

**CVSS v3.1 スコア**: 5.3 (Medium)

**修正推奨**:

```python
# Validate file type
if member.isdev() or member.isfifo():
    raise ValueError(
        f"Dangerous file type in tar: {member.name} "
        f"(device file or FIFO not allowed)"
    )

# Check for setuid/setgid bits
if member.mode & 0o6000:  # Check for setuid (4000) or setgid (2000)
    # Remove dangerous bits instead of rejecting
    member.mode &= 0o1777
```

**優先度**: 🟡 **中（1ヶ月以内に対処）**

---

### 3. TOCTOU（Time-of-Check to Time-of-Use）脆弱性

**場所**: `asma/core/installer.py:82-86`

**問題の詳細**:
```python
if install_path.exists():           # Time of Check
    if install_path.is_symlink():
        install_path.unlink()       # Time of Use
    else:
        shutil.rmtree(install_path) # Time of Use
```

チェックと使用の間に、攻撃者がファイルシステムの状態を変更できる可能性があります。

**攻撃シナリオ**:
1. 正当なディレクトリが存在する
2. `exists()`チェックがパスする
3. **攻撃者がディレクトリをシンボリックリンクに置き換える**
4. `is_symlink()`チェックがシンボリックリンクを検出
5. `unlink()`が呼ばれる（予期しない動作）

または：
1. シンボリックリンクが存在する
2. `is_symlink()`チェックがパスする
3. **攻撃者がシンボリックリンクをディレクトリに置き換える**
4. `unlink()`が失敗する、または`rmtree()`が呼ばれる

**影響**:
- ファイルシステムの予期しない変更
- シンボリックリンクのターゲットの削除
- DoS（サービス拒否）

**実際のリスク**: 🟢 **低**
- ユーザーの`~/.claude/skills/`または`.claude/skills/`ディレクトリ内での操作
- 通常、攻撃者はこのディレクトリへのアクセス権がない
- ただし、共有環境や特殊な権限設定では問題になる可能性

**CVSS v3.1 スコア**: 4.7 (Medium)

**修正推奨**:

```python
# Option 1: Use try-except for atomic operation
try:
    if install_path.is_symlink():
        install_path.unlink()
    elif install_path.is_dir():
        shutil.rmtree(install_path)
    elif install_path.exists():
        install_path.unlink()
except OSError as e:
    return InstallResult(
        success=False,
        skill_name=skill.name,
        install_path=install_path,
        error=f"Failed to remove existing installation: {e}"
    )

# Option 2: Use os.replace() for atomic operations where applicable
# (Not directly applicable here, but useful for other file operations)
```

**優先度**: 🟡 **中（2ヶ月以内に対処、共有環境では優先度↑）**

---

### 4. ファイル名の長さ制限なし

**場所**: `asma/core/sources/github.py:95-142`

**問題の詳細**:
極端に長いファイル名（例: 10,000文字）を含むtarアーカイブによるDoS攻撃の可能性があります。

**影響**:
- ファイルシステムのエラー
- メモリ消費の増加
- ログファイルの肥大化

**CVSS v3.1 スコア**: 3.7 (Low)

**修正推奨**:

```python
# Validate filename length
MAX_FILENAME_LENGTH = 255  # Standard Linux/Unix limit

if len(member.name) > MAX_FILENAME_LENGTH:
    raise ValueError(
        f"Filename too long in tar: {member.name[:50]}... "
        f"({len(member.name)} chars, max {MAX_FILENAME_LENGTH})"
    )

# Also check for null bytes (can cause issues)
if '\0' in member.name:
    raise ValueError(f"Null byte in filename: {member.name}")
```

**優先度**: 🟢 **低（次のマイナーリリース）**

---

## 🟡 追加の改善推奨事項（第2回）

### 5. シンボリックリンクの解決における潜在的な問題

**場所**: `asma/core/sources/github.py:97, 132`

**問題の詳細**:
```python
member_path = (extract_dir / member.name).resolve()
```

`resolve()`は、ファイルがまだ存在しない状態で呼ばれています。Python 3.6+では`resolve(strict=False)`がデフォルトなので動作しますが、シンボリックリンクの解決は不完全です。

**推奨される改善**:

```python
# 存在しないパスのresolveは、親ディレクトリのみ解決
member_path_parent = (extract_dir / member.name).parent.resolve()
member_path = member_path_parent / Path(member.name).name

# より厳密なチェック
try:
    # extract_dir自体がシンボリックリンクでないことを確認
    if extract_dir.is_symlink():
        raise ValueError(f"Extraction directory is a symlink: {extract_dir}")

    member_path.relative_to(extract_dir_resolved)
except ValueError:
    raise ValueError(f"Attempted path traversal in tar archive: {member.name}")
```

**優先度**: 🟡 **中**

---

### 6. HTTPリクエストのタイムアウトとリトライ戦略

**場所**: `asma/core/sources/github.py:171, 282-290`

**現状**:
- タイムアウトは設定されています（30秒、60秒）
- リトライロジックがありません
- ネットワークエラーの詳細が漏洩する可能性

**推奨される改善**:

```python
import time
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

class GitHubSourceHandler(SourceHandler):
    def __init__(self, ...):
        # ...既存のコード...

        # Configure retry strategy
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,  # 1s, 2s, 4s
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)

    def _api_request(self, endpoint: str) -> dict:
        url = f"{self.API_BASE}{endpoint}"
        try:
            response = self.session.get(url, headers=self._get_headers(), timeout=30)
        except requests.exceptions.RequestException as e:
            # Don't leak sensitive error details
            raise ConnectionError("Failed to connect to GitHub API") from None
        # ...残りの処理...
```

**優先度**: 🟡 **中**

---

### 7. エラーメッセージの情報漏洩リスク

**場所**: 複数箇所

**発見された情報漏洩**:

1. **低リスク（許容可能）**:
   - `asma/core/sources/github.py:104` - パストラバーサルの試行パス
   - `asma/core/sources/github.py:299` - Tarファイルのエラー

2. **中リスク（改善推奨）**:
   - `asma/core/sources/github.py:173` - ネットワーク例外の詳細
   ```python
   raise ConnectionError(f"Failed to connect to GitHub API: {e}")
   ```

   **改善案**:
   ```python
   # 詳細なエラーはログに記録し、ユーザーには一般的なメッセージを表示
   import logging
   logger = logging.getLogger(__name__)

   logger.debug(f"GitHub API connection error: {e}")
   raise ConnectionError("Failed to connect to GitHub API. Check your network connection.") from None
   ```

**優先度**: 🟢 **低（セキュリティ強化として推奨）**

---

### 8. キャッシュディレクトリのアクセス権限

**場所**: `asma/core/sources/github.py:268-269`

**問題の詳細**:
```python
# Create cache directory
self.cache_dir.mkdir(parents=True, exist_ok=True)
```

キャッシュディレクトリの権限が明示的に設定されていません。デフォルトのumaskが適用されますが、より厳密な権限設定が推奨されます。

**推奨される改善**:

```python
# Create cache directory with restricted permissions
self.cache_dir.mkdir(parents=True, exist_ok=True, mode=0o700)

# Verify permissions (especially if directory already exists)
if self.cache_dir.stat().st_mode & 0o777 != 0o700:
    self.cache_dir.chmod(0o700)
```

**優先度**: 🟢 **低（防御強化として推奨）**

---

### 9. 依存関係の具体的なバージョン情報

**現在のバージョン**:
```
requests: 2.32.5
PyYAML: 6.0.1
click: 8.3.1
rich: 14.2.0
jsonschema: 4.26.0
```

**既知の脆弱性チェック結果**: ✅ **問題なし**

すべての依存関係は最新版に近く、既知の重大な脆弱性は含まれていません。

**ただし、PyYAML 6.0.1に関する注意**:
- PyYAML 5.xには任意コード実行の脆弱性がありました（CVE-2020-14343）
- PyYAML 6.0+では修正されています ✅
- 本プロジェクトではすべて`yaml.safe_load()`を使用しているため、さらに安全です ✅

**推奨**:
- 定期的な`pip-audit`または`safety`によるスキャン
- Dependabotの有効化

**優先度**: 🟢 **低（継続的な監視）**

---

### 10. チェックサムアルゴリズムの強化

**場所**: `asma/core/installer.py:102`, `asma/core/sources/local.py:43`, `asma/core/checker.py:141`

**現状**: SHA-256を使用（✅ 適切）

**SHA-256は現在でも安全**ですが、将来的な耐量子コンピュータ性を考慮すると、以下のオプションを検討できます：

1. **SHA-3（推奨）**: 量子コンピュータに対してより強固
2. **BLAKE3**: より高速で安全

**現時点では変更不要ですが、将来のアップグレードパスを検討**:

```python
# Future-proof: Allow configurable hash algorithm
HASH_ALGORITHM = "sha256"  # or "sha3_256", "blake3"

def calculate_checksum(file_path: Path) -> str:
    content = file_path.read_bytes()
    if HASH_ALGORITHM == "sha3_256":
        import hashlib
        digest = hashlib.sha3_256(content).hexdigest()
    else:
        digest = hashlib.sha256(content).hexdigest()
    return f"{HASH_ALGORITHM}:{digest}"
```

**優先度**: 🟢 **極低（将来の検討事項）**

---

### 11. レート制限の実装（再強調）

第1回レビューでも指摘しましたが、より詳細な実装案を提示します。

**場所**: `asma/core/sources/github.py`

**詳細な実装案**:

```python
import time
from collections import deque
from threading import Lock

class RateLimiter:
    """Simple rate limiter for API requests."""

    def __init__(self, max_requests: int = 60, time_window: int = 60):
        """
        Args:
            max_requests: Maximum number of requests allowed
            time_window: Time window in seconds
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = deque()
        self.lock = Lock()

    def acquire(self) -> None:
        """Wait if necessary to stay within rate limits."""
        with self.lock:
            now = time.time()

            # Remove old requests outside time window
            while self.requests and self.requests[0] < now - self.time_window:
                self.requests.popleft()

            # If at limit, wait
            if len(self.requests) >= self.max_requests:
                sleep_time = self.requests[0] + self.time_window - now
                if sleep_time > 0:
                    time.sleep(sleep_time)
                    return self.acquire()  # Retry

            # Record this request
            self.requests.append(now)

class GitHubSourceHandler(SourceHandler):
    def __init__(self, ...):
        # ...既存のコード...
        self.rate_limiter = RateLimiter(max_requests=60, time_window=60)

    def _api_request(self, endpoint: str) -> dict:
        # Wait for rate limit
        self.rate_limiter.acquire()

        # ...既存のリクエストコード...
```

**優先度**: 🟡 **中**

---

### 12. セキュアなテンポラリファイルの使用

**場所**: ダウンロード処理全般

**現状**:
- ダウンロードは直接ストリームから抽出されています
- キャッシュディレクトリは`~/.cache/asma/github/`

**推奨される改善**:

```python
import tempfile
import atexit

# Use secure temporary directory
with tempfile.TemporaryDirectory(prefix="asma_", suffix="_download") as tmpdir:
    extract_dir = Path(tmpdir) / "extract"
    extract_dir.mkdir()

    # Download and extract
    # ...

    # Move to final location only after successful extraction
    shutil.move(extract_dir, final_cache_dir)
```

**メリット**:
- 失敗時の自動クリーンアップ
- 他のプロセスからの分離
- より安全な権限設定

**優先度**: 🟢 **低（クリーンコードのベストプラクティス）**

---

## 🔒 追加のセキュリティテスト推奨

第1回で作成したテストに加えて、以下のテストを追加することを推奨します：

### Tar Bomb テスト

```python
def test_tar_bomb_too_many_files(self, tmp_path: Path) -> None:
    """Test that tarballs with too many files are rejected."""
    handler = GitHubSourceHandler()
    extract_dir = tmp_path / "extract"
    extract_dir.mkdir()

    # Create tar with excessive number of files
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode='w:gz') as tar:
        for i in range(11000):  # Exceeds MAX_FILE_COUNT
            info = tarfile.TarInfo(name=f'file_{i}.txt')
            info.size = 10
            tar.addfile(info, io.BytesIO(b'x' * 10))
    buffer.seek(0)

    with tarfile.open(fileobj=buffer, mode='r:gz') as tar:
        with pytest.raises(ValueError, match="too many files|tar bomb"):
            handler._safe_extract_tarball(tar, extract_dir)

def test_tar_bomb_large_file(self, tmp_path: Path) -> None:
    """Test that tarballs with extremely large files are rejected."""
    handler = GitHubSourceHandler()
    extract_dir = tmp_path / "extract"
    extract_dir.mkdir()

    # Create tar with huge file
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode='w:gz') as tar:
        info = tarfile.TarInfo(name='huge_file.bin')
        info.size = 200 * 1024 * 1024  # 200 MB (exceeds limit)
        # Don't actually write data, just metadata
        tar.addfile(info, io.BytesIO(b''))
    buffer.seek(0)

    with tarfile.open(fileobj=buffer, mode='r:gz') as tar:
        with pytest.raises(ValueError, match="File too large|tar bomb"):
            handler._safe_extract_tarball(tar, extract_dir)

def test_device_file_rejected(self, tmp_path: Path) -> None:
    """Test that device files in tarballs are rejected."""
    handler = GitHubSourceHandler()
    extract_dir = tmp_path / "extract"
    extract_dir.mkdir()

    # Create tar with device file
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode='w:gz') as tar:
        info = tarfile.TarInfo(name='dev_file')
        info.type = tarfile.CHRTYPE  # Character device
        tar.addfile(info)
    buffer.seek(0)

    with tarfile.open(fileobj=buffer, mode='r:gz') as tar:
        with pytest.raises(ValueError, match="device|FIFO"):
            handler._safe_extract_tarball(tar, extract_dir)

def test_filename_too_long_rejected(self, tmp_path: Path) -> None:
    """Test that files with excessively long names are rejected."""
    handler = GitHubSourceHandler()
    extract_dir = tmp_path / "extract"
    extract_dir.mkdir()

    # Create tar with very long filename
    long_name = 'a' * 300  # Exceeds typical filesystem limits
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode='w:gz') as tar:
        info = tarfile.TarInfo(name=long_name)
        info.size = 10
        tar.addfile(info, io.BytesIO(b'test'))
    buffer.seek(0)

    with tarfile.open(fileobj=buffer, mode='r:gz') as tar:
        with pytest.raises(ValueError, match="Filename too long"):
            handler._safe_extract_tarball(tar, extract_dir)
```

---

## 📊 更新されたリスク評価マトリックス

| 脆弱性 | 重大度 | 影響 | 悪用の容易性 | 実際のリスク | 優先度 |
|--------|--------|------|--------------|--------------|--------|
| **第1回で修正済み** |
| Tar抽出の脆弱性（修正済み） | ~~High~~ | ~~High~~ | ~~Medium~~ | ✅ **修正済み** | - |
| **第2回で発見** |
| Tar Bomb攻撃 | High | High | Low | 🟡 Medium | 🔴 High |
| デバイス/特殊ファイル | Medium | Medium | Low | 🟢 Low | 🟡 Medium |
| TOCTOU脆弱性 | Medium | Low | Very Low | 🟢 Very Low | 🟡 Medium |
| ファイル名の長さ | Low | Low | Very Low | 🟢 Very Low | 🟢 Low |
| DoS対策の欠如（再掲） | Medium | Medium | Low | 🟡 Medium | 🟡 Medium |
| シンボリックリンク解決 | Low | Low | Low | 🟢 Very Low | 🟡 Medium |
| エラーメッセージ漏洩 | Low | Low | Medium | 🟢 Very Low | 🟢 Low |

---

## 📝 更新されたアクションアイテム

### 🔴 高優先度（2週間以内）
- [ ] **Tar Bomb対策の実装**
  - ファイル数の制限（MAX_FILE_COUNT）
  - 個別ファイルサイズの制限（MAX_SINGLE_FILE_SIZE）
  - 総展開サイズの制限（MAX_EXTRACT_SIZE）
  - テストケースの追加

### 🟡 中優先度（1-2ヶ月以内）
- [ ] **デバイスファイルと特殊ファイルのチェック追加**
  - `isdev()`, `isfifo()`のチェック
  - setuid/setgidビットの除去
  - テストケースの追加

- [ ] **TOCTOU脆弱性の軽減**
  - try-exceptを使った原子的な操作
  - 共有環境での追加ドキュメント

- [ ] **HTTPリクエストの改善**
  - リトライロジックの実装
  - エラーメッセージの改善

- [ ] **レート制限の実装**
  - シンプルなレートリミッターの追加
  - GitHub APIのレート制限に準拠

### 🟢 低優先度（次のマイナー/メジャーリリース）
- [ ] **ファイル名の長さ制限**
- [ ] **シンボリックリンク解決の強化**
- [ ] **キャッシュディレクトリの権限設定**
- [ ] **エラーメッセージの情報漏洩対策**
- [ ] **セキュアなテンポラリファイル使用**
- [ ] **継続的なセキュリティスキャンの設定**
  - GitHub Dependabot
  - `pip-audit`または`safety`のCI統合

---

## 🎯 結論と推奨事項

### 主要な改善点

✅ **第1回で修正された項目**:
1. **Critical**: Tar抽出のパストラバーサル脆弱性（CVE-2007-4559類似）が修正されました
2. 包括的なセキュリティテストスイートが追加されました
3. 詳細なセキュリティレビューレポートが作成されました

### 現在の状態

🟡 **Good, but can be better**:
- 基本的なセキュリティは確保されています
- 追加の攻撃ベクトル（Tar Bomb、デバイスファイル等）への対策が必要です
- 防御深化（Defense in Depth）の観点から、複数の保護層を追加することを推奨します

### 次のステップ（優先順位順）

1. **🔴 Tar Bomb対策の実装**（2週間以内）
   - これがないと、修正したパストラバーサル脆弱性の意味が半減します
   - ディスク容量枯渇によるDoSは実際に起こりうる攻撃です

2. **🟡 デバイスファイルチェックの追加**（1ヶ月以内）
   - 完全性を高めるための重要な追加

3. **🟡 HTTPリクエストの改善**（1ヶ月以内）
   - ユーザビリティとセキュリティの両面で有益

4. **🟢 継続的なセキュリティ監視**
   - Dependabotの有効化
   - 定期的な脆弱性スキャン

### セキュリティ成熟度評価

**現在**: Level 3 / 5（良好）
- ✅ 基本的なセキュリティ対策
- ✅ 入力検証
- ✅ セキュアなAPI使用
- ⚠️ 高度な攻撃への対策（部分的）
- ❌ 継続的なセキュリティ監視（未設定）

**推奨ターゲット**: Level 4 / 5（優秀）
- すべての推奨事項を実装
- 継続的なセキュリティ監視
- 定期的なペネトレーションテスト

---

**総評**: プロジェクトは正しい方向に進んでいます。第1回の修正により重大な脆弱性は解消されましたが、追加の防御層を実装することで、さらに堅牢なシステムになります。

**レビュー完了日**: 2026-01-08（第2回）
**次回レビュー推奨日**: Tar Bomb対策実装後、または2026-03-01
