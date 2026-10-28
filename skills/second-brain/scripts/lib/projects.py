"""Active-project lookup shared by capture (project inference) and query."""

from pathlib import Path

from . import fmyaml
from .core import die


def active_project_slugs(vault):
    """Stems of Projects/**/*.md notes whose frontmatter is type: project,
    status: active. A nested project folder uses its own note stem."""
    d = vault / "Projects"
    if not d.is_dir():
        return []
    out = []
    for f in sorted(d.rglob("*.md")):
        try:
            fm, _ = fmyaml.parse(f.read_text(encoding="utf-8"))
        except OSError:
            continue
        if fm.get("type") == "project" and fm.get("status") == "active":
            out.append(f.stem)
    return sorted(set(out))


def project_rels(vault):
    """slug -> rel for every project note of any status. Mirrors the linter:
    Projects/slug.md and Projects/slug/slug.md; other nested files are
    reference material."""
    d = vault / "Projects"
    out = {}
    if not d.is_dir():
        return out
    for f in sorted(d.rglob("*.md")):
        parts = f.relative_to(vault).parts
        if len(parts) == 2 or (len(parts) == 3 and parts[1] == f.stem):
            out[f.stem] = "/".join(parts)
    return out


def require_project_slug(vault, slug):
    """A repo must belong to an existing project note (any status) — unlike
    task/meeting's advisory `project`, this is enforced at write time."""
    known = project_rels(vault)
    if slug not in known:
        near = ", ".join(sorted(known)) or "(no projects yet)"
        die(f"no such project: '{slug}'. Known projects: {near}. Create one "
            "with `brain capture project`. Nothing was written.")
    return slug
