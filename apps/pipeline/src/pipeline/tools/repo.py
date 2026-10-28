"""Course-repo manager (03-prd §7.4).

Every filesystem and command interaction with a course repo goes through
`CourseRepo`: paths resolve inside the repo only, commands are argument lists
(no shell strings) from an allowlist, and file writes pass a secrets scan before
a commit. Running generated code is the one risky step, so the test runner here
executes nothing beyond the allowlisted commands.
"""
from __future__ import annotations

import re
import subprocess
import time
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path

_REPO_CMDS = ["uv sync", "uv add", "uv run pytest", "uv run ruff check"]
DEFAULT_TIMEOUT = 600.0

# Strings that look like live credentials; a commit carrying one is blocked.
SECRET_PATTERNS = [
    r"sk-[A-Za-z0-9_-]{20,}",                      # OpenAI / OpenRouter style keys
    r"AKIA[0-9A-Z]{16}",                           # AWS access keys
    r"gh[pousr]_[A-Za-z0-9]{30,}",                 # GitHub tokens
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    r"(?i)\b(api[_-]?key|secret|password|token)\b\s*[=:]\s*['\"][^'\"]{12,}",
    r"(?i)authorization:\s*bearer\s+[A-Za-z0-9._-]{16,}",
]
_SECRETS = [re.compile(p) for p in SECRET_PATTERNS]

# Subprocess env: PATH and locale only — API keys must never reach the project.
_KEEP_ENV = ("PATH", "HOME", "LANG", "LC_ALL", "TERM", "TMPDIR", "SYSTEMROOT", "COMSPEC")


class RepoError(Exception):
    pass


def scrubbed_env() -> dict[str, str]:
    return {k: v for k, v in __import__("os").environ.items() if k in _KEEP_ENV and v is not None}


def secrets_scan(text: str) -> list[str]:
    """All secret-like matches found in `text` (deduplicated, truncated)."""
    out: list[str] = []
    for rx in _SECRETS:
        for m in rx.finditer(text):
            out.append(m.group(0)[:60])
    return sorted(set(out))


def _cmd_allowed(argv: list[str], allowlist: list[str]) -> bool:
    s = " ".join(argv)
    return any(s == c or s.startswith(c + " ") for c in allowlist)


class CourseRepo:
    """Safety wrapper around exactly one local course git repo."""

    def __init__(self, root: Path, cmds: list[str] | None = None, timeout: float = DEFAULT_TIMEOUT):
        self.root = Path(root).expanduser().resolve()
        self.allowlist = list(cmds if cmds is not None else _REPO_CMDS)
        self.timeout = timeout
        if not (self.root / ".git").exists():
            raise RepoError(f"not a git repository: {self.root}")

    # ------------------------------------------------------------------ paths
    def resolve(self, rel: str | Path) -> Path:
        """Resolve a path inside the repo; reject `.git` and everything outside."""
        p = Path(rel)
        if p.is_absolute() or any(part == ".." for part in p.parts):
            raise RepoError(f"path escapes the repo: {rel}")
        if any(part == ".git" for part in p.parts):
            raise RepoError(f"refusing to touch .git: {rel}")
        full = (self.root / p).resolve()
        if full != self.root and self.root not in full.parents:
            raise RepoError(f"path escapes the repo: {rel}")
        return full

    # ------------------------------------------------------------------ commands
    def run(self, argv: list[str], timeout: float | None = None, check: bool = True,
            env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        """Run an allowlisted command (argument list only) in the repo."""
        if not argv or not isinstance(argv, list):
            raise RepoError("command must be a non-empty argv list")
        if not _cmd_allowed(argv, self.allowlist):
            raise RepoError(f"command not in the allowlist: {argv[0]}")
        try:
            cp = subprocess.run(  # noqa: S603 — argv only, no shell, cwd pinned
                argv, cwd=self.root, capture_output=True, text=True,
                timeout=timeout or self.timeout, env=env or scrubbed_env())
        except subprocess.TimeoutExpired as e:
            raise RepoError(f"command timed out after {timeout or self.timeout:.0f}s: {' '.join(argv)}") from e
        if check and cp.returncode != 0:
            raise RepoError(f"{' '.join(argv)} failed (rc {cp.returncode}):\n{(cp.stderr or cp.stdout)[-1200:]}")
        return cp

    def git(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        try:
            cp = subprocess.run(  # noqa: S603 — fixed argv[0], developer-provided flags
                ["git", *args], cwd=self.root, capture_output=True, text=True, timeout=300)
        except subprocess.TimeoutExpired as e:
            raise RepoError(f"git {args[0]} timed out") from e
        if check and cp.returncode != 0:
            raise RepoError(f"git {' '.join(args)} failed: {(cp.stderr or cp.stdout)[-800:]}")
        return cp

    # ------------------------------------------------------------------ state
    def head(self) -> str:
        return self.git("rev-parse", "HEAD").stdout.strip()

    def branch(self) -> str:
        return self.git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()

    def is_clean(self) -> bool:
        return self.git("status", "--porcelain").stdout.strip() == ""

    def status(self) -> str:
        return self.git("status", "--porcelain").stdout.strip()

    def tree(self) -> list[dict]:
        """Tracked files as [{path, size}], .git excluded, sorted."""
        out = self.git("ls-files", "-z", "--deduplicate").stdout.split("\0")
        files = []
        for rel in sorted(f for f in out if f):
            p = self.root / rel
            try:
                files.append({"path": rel, "size": p.stat().st_size})
            except OSError:
                continue
        return files

    def read(self, rel: str) -> str:
        p = self.resolve(rel)
        if not p.is_file():
            raise RepoError(f"no such file in the repo: {rel}")
        return p.read_text(encoding="utf-8", errors="replace")

    def read_head(self, rel: str) -> str | None:
        """File content at HEAD (None if absent) — for lesson placeholders."""
        cp = self.git("show", f"HEAD:{rel}", check=False)
        return cp.stdout if cp.returncode == 0 else None

    def tree_paths(self) -> list[str]:
        return [f["path"] for f in self.tree()]

    def files_line_numbered(self, paths: list[str], max_bytes: int = 24_000) -> dict[str, str]:
        """Bounded line-numbered snapshots of repo files (for code/lesson prompts)."""
        out = {}
        used = 0
        for rel in paths:
            try:
                content = self.read(rel)
            except RepoError:
                continue
            if used + len(content) > max_bytes:
                break
            used += len(content)
            out[rel] = content
        return out

    def commit_list(self, range_: str | None = None) -> list[dict]:
        """Commits as [{sha, message}] (optionally a range like part-0..HEAD)."""
        spec = range_ or "HEAD"
        out = self.git("log", "--format=%H%x00%s", "--reverse", spec).stdout
        commits = []
        for line in out.splitlines():
            if not line.strip():
                continue
            sha, _, msg = line.partition("\x00")
            commits.append({"sha": sha, "message": msg})
        return commits

    def write_file(self, rel: str, content: str) -> None:
        p = self.resolve(rel)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")

    def delete_file(self, rel: str) -> None:
        p = self.resolve(rel)
        if p.is_file():
            p.unlink()

    def diff(self, ref_a: str, ref_b: str | None = None) -> str:
        args = ["diff", ref_a] if ref_b is None else ["diff", f"{ref_a}..{ref_b}"]
        return self.git(*args, "--stat", "--patch", "--no-color").stdout

    # ------------------------------------------------------------------ changes
    def stage_and_commit(self, message: str, paths: list[str] | None = None,
                         trailer: str = "Assisted-by: content-pipeline") -> str:
        """Stage paths (or everything pending), scan for secrets, commit. Returns the sha.

        Paths must already exist or have been removed via delete_file; use [] together
        with prior manual writes only when you truly want `git add -A`.
        """
        if paths is None:
            self.git("add", "-A")
        else:
            for p in paths:
                self.resolve(p)  # safety check even though `git add` resolves itself
            if paths:
                self.git("add", *paths)
        if self.is_clean():  # nothing staged
            raise RepoError("nothing to commit")
        staged = self.git("diff", "--staged", "--no-color").stdout
        hits = secrets_scan(message) + secrets_scan(staged)
        if hits:
            self.git("reset")  # leave nothing staged behind the failure
            raise RepoError("commit blocked: secret-looking string(s) found: " + ", ".join(hits[:4]))
        msg = message if trailer in message else f"{message}\n\n{trailer}"
        self.git("commit", "-m", msg)
        return self.head()

    def tag(self, n: int, message: str | None = None) -> str:
        name = f"part-{n}"
        if n > 0 and not self.git("rev-parse", "--verify", "--quiet", f"refs/tags/part-{n - 1}", check=False).stdout.strip():
            raise RepoError(f"tag part-{n - 1} must exist before tagging {name}")
        msg = message or f"part-{n}"
        self.git("tag", "-a", name, "-m", msg)
        return name

    def push(self, what: str = "--follow-tags") -> str:
        """Push the current branch (and annotated tags by default)."""
        cp = self.git("push", self.git_remote(), what, check=False)
        if cp.returncode != 0:
            raise RepoError(f"push failed: {(cp.stderr or cp.stdout)[-800:]}")
        return (cp.stderr or cp.stdout).strip()[-400:]

    def git_remote(self) -> str:
        out = self.git("remote").stdout.strip()
        return out.splitlines()[0] if out else "origin"

    def default_branch(self) -> str:
        return self.git("symbolic-ref", "refs/remotes/origin/HEAD", "--short", check=False).stdout.strip()

    # ------------------------------------------------------------------ part loop (03-prd §7.5)
    def start_part(self, n: int) -> str:
        """Create/checkout `wip/part-N` from main (or the previous tag). Returns the start sha."""
        branch = f"wip/part-{n}"
        if self.git("rev-parse", "--verify", branch, check=False).returncode == 0:
            self.git("checkout", branch)
        else:
            base = "main"
            if n > 0 and self.git("rev-parse", "--verify", f"refs/tags/part-{n - 1}", check=False).returncode == 0:
                # branch from the previous tag only when it sits on main (it must,
                # so publishing can ff-merge back); otherwise main is the safe base
                if self.git("merge-base", "--is-ancestor", f"part-{n - 1}", "main", check=False).returncode == 0:
                    base = f"part-{n - 1}"
            self.git("checkout", "-b", branch, base)
        if self.git("status", "--porcelain").stdout.strip():
            raise RepoError(f"{branch} has uncommitted changes; commit or reset them first")
        return self.head()

    def apply_file_edit(self, path: str, op: str, content: str | None = None,
                        edits: list[dict] | None = None) -> str:
        """One FileEdit, applied on disk with all safety checks. Returns the new content (for diffing)."""
        p = self.resolve(path)
        if op == "create":
            if p.exists():
                raise RepoError(f"create: {path} already exists (use edit or replace)")
            if not content or not content.strip():
                raise RepoError(f"create: {path} would be empty")
            self.write_file(path, content)
            return content
        if op == "delete":
            if not p.exists():
                raise RepoError(f"delete: {path} does not exist")
            p.unlink()
            return ""
        if not p.exists():
            raise RepoError(f"{op}: {path} does not exist")
        text = p.read_text(encoding="utf-8")
        if op == "replace":
            if content is None:
                raise RepoError(f"replace: {path} needs content")
            self.write_file(path, content)
            return content
        # edit: every search must match exactly once
        for e in edits or []:
            hits = text.count(e["search"])
            if hits == 0:
                raise RepoError(f"edit: search text not found in {path}: {e['search'][:80]!r}")
            if hits > 1:
                raise RepoError(f"edit: search text matches {hits} times in {path} (must match once): {e['search'][:80]!r}")
            text = text.replace(e["search"], e["replace"], 1)
        self.write_file(path, text)
        return text

    def changed_lines(self) -> int:
        """Changed (added+removed) lines vs the merge-base, for the 200-600 budget."""
        base = self.git("merge-base", "main", "HEAD", check=False).stdout.strip() or "main"
        stat = self.git("diff", "--numstat", base, "HEAD").stdout
        total = 0
        for line in stat.splitlines():
            parts = line.split("\t")
            if len(parts) >= 2:
                with suppress(ValueError):
                    total += int(parts[0]) + int(parts[1])
        return total

    def run_tests(self, timeout: float | None = None) -> dict:
        """`uv run pytest -q` with the scrubbed env. Output recorded for the tests gate."""
        t0 = time.monotonic()
        cp = self.run(["uv", "run", "pytest", "-q"], timeout=timeout or 600, check=False)
        output = ((cp.stdout or "") + (cp.stderr or ""))[-6000:]
        return {"ok": cp.returncode == 0, "output": output,
                "seconds": round(time.monotonic() - t0, 1),
                "at": datetime.now(UTC).isoformat(timespec="seconds")}


def doctor(path: Path, remote_url: str | None = None) -> dict:
    """Pre-flight checks for an empty (or existing) course repo remote (03-prd §7.4)."""
    out: dict = {"remote_ok": False, "empty_ok": False, "branch_ok": False, "detail": ""}
    root = Path(path).expanduser().resolve()
    try:
        repo = CourseRepo(root)
        out["branch_ok"] = repo.branch() == "main"
    except RepoError as e:
        out["detail"] = str(e)
        return out
    remotes = repo.git("remote", "-v").stdout.strip()
    if not remotes and remote_url:
        repo.git("remote", "add", "origin", remote_url)
    ls = repo.git("ls-remote", remote_url or repo.git_remote(), check=False)
    if ls.returncode != 0:
        out["detail"] = (ls.stderr or "").strip()[-300:] or "no git remote configured"
        return out
    out["remote_ok"] = True
    out["empty_ok"] = ls.stdout.strip() == ""          # nothing pushed yet (neither branches nor tags)
    out["branch_ok"] = repo.branch() == "main"
    if not out["empty_ok"]:
        heads = [ln.split("\t", 1)[1] for ln in ls.stdout.splitlines() if "\t" in ln]
        out["detail"] = "remote not empty: " + ", ".join(h[:40] for h in heads[:8])
    return out


def repo_dir(courses_root: Path, repo_name: str) -> Path:
    """Sanitized repo folder name under COURSES_DIR (03-prd §7.4)."""
    name = repo_name.strip().strip("/")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{1,80}", name):
        raise RepoError(f"invalid repo name: {repo_name!r}")
    if name.startswith((".", "-")) or name.endswith(".git"):
        raise RepoError(f"refusing repo name: {repo_name!r}")
    return Path(courses_root) / name
