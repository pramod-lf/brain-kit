"""Git helpers for repo-note cwd auto-detection. No vault knowledge here."""

import subprocess


def git_remote_url(cwd):
    """`git remote get-url origin` run in `cwd`, or None on ANY failure: no
    git installed, cwd not a git repo, no `origin` remote. Never raises —
    auto-detection falls through to its next stage instead of erroring."""
    try:
        out = subprocess.run(
            ["git", "-C", str(cwd), "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    url = out.stdout.strip()
    return url or None


def normalize_remote(url):
    """Loose equality between two spellings of the same remote: trims
    whitespace, a trailing '/', and a trailing '.git'. Deliberately does NOT
    translate between ssh (`git@host:org/repo`) and https
    (`https://host/org/repo`) forms — same remote cloned with a different
    protocol will not match in v1."""
    u = (url or "").strip().rstrip("/")
    if u.endswith(".git"):
        u = u[:-4]
    return u
