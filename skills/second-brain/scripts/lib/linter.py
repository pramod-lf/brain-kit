"""Vault linter. Errors as (path, field, problem) tuples.

Body wikilinks that do not resolve are WARNINGS (hand-written prose may point
at notes that do not exist yet); frontmatter wikilinks (attendees, source,
transcript, who) are ERRORS.
"""

import re
import subprocess
from pathlib import Path

from . import fmyaml
from .body import drifted_fields, sync_meta
from .core import (DATE_RE, ENUMS, META_LINES, NAMING, NULLABLE, REQUIRED,
                   TYPE_BY_FOLDER, WEEK_RE, wikilink_target,
                   write_text)

BODY_LINK_RE = re.compile(r"\[\[([^\]|#\n]+)(?:[|#][^\]]*)?\]\]")

WIKILINK_FIELDS = {
    "task": ["source", "owner"],
    "meeting": ["transcript"],
    "followup": ["who"],
}


def vault_files(vault):
    """All lintable .md files, sorted, as paths relative to vault root.
    Always '/'-separated and sorted as strings, so the result is the same on
    Windows (where str(Path) uses '\\' and Path sorting ignores case)."""
    out = []
    for folder in sorted(TYPE_BY_FOLDER):
        d = vault / folder
        if not d.is_dir():
            continue
        out += sorted(f.relative_to(vault).as_posix() for f in d.rglob("*.md"))
    return out


def link_index(vault, extra=()):
    """Set of resolvable wikilink targets: rel path w/o .md + bare stem."""
    idx = set()
    for rel in vault_files(vault):
        noext = rel[:-3]
        idx.add(noext)
        idx.add(Path(noext).name)
    # root-level md files are linkable too
    if vault.is_dir():
        for f in sorted(vault.glob("*.md")):
            idx.add(f.stem)
        for f in sorted(vault.glob("*.base")):
            idx.add(f.name)  # [[Tasks.base]]
    for rel in extra:
        noext = rel[:-3] if rel.endswith(".md") else rel
        idx.add(noext)
        idx.add(Path(noext).name)
    return idx


def resolves(target, idx):
    t = target.strip().strip("/")
    if t.endswith(".md"):
        t = t[:-3]
    return t in idx or Path(t).name in idx


def _folder_of(rel):
    return rel.split("/", 1)[0]


def title_of(rel, body):
    """Deterministic display title: the body H1 if there is one, else the
    filename stem with dashes turned back into spaces."""
    m = re.search(r"^# (.+)$", body, re.MULTILINE)
    if m and m.group(1).strip():
        return m.group(1).strip()
    return Path(rel).stem.replace("-", " ")


def expected_type(rel):
    folder = _folder_of(rel)
    t = TYPE_BY_FOLDER.get(folder)
    if folder == "Projects":
        p = Path(rel)
        # Projects/slug.md and Projects/slug/slug.md are project notes;
        # any other nested file is auxiliary material -> reference
        if len(p.parts) >= 3:
            return "project" if (len(p.parts) == 3 and p.parts[1] == p.stem) \
                else "reference"
    return t


def lint_note(rel, fm, body, idx):
    """Return (errors, warnings) lists of (rel, field, problem)."""
    errs, warns = [], []
    folder = _folder_of(rel)
    e = lambda field, prob: errs.append((rel, field, prob))

    # naming
    pat = NAMING.get(folder)
    inner = rel.split("/", 1)[1] if "/" in rel else rel
    if pat and not pat.match(inner):
        e("name", f"filename violates {folder}/ naming ({pat.pattern})")

    if not fm:
        e("frontmatter", "missing frontmatter")
        return errs, warns

    ntype = fm.get("type")
    want = expected_type(rel)
    valid_types = set(TYPE_BY_FOLDER.values())
    if ntype not in valid_types:
        e("type", f"type must be one of {sorted(valid_types)}, got {ntype!r}")
        return errs, warns
    if want and ntype != want:
        e("type", f"type '{ntype}' does not match folder (expected '{want}')")

    if str(fm.get("schema")) != "1":
        e("schema", "schema must be 1")
    created = fm.get("created")
    if not (isinstance(created, str) and DATE_RE.match(created)):
        e("created", "created must be YYYY-MM-DD")

    # frontmatter policy: `tags` on every note, `title` on none (the H1 is the title)
    tags = fm.get("tags")
    if not isinstance(tags, list) or ntype not in tags:
        e("tags", f"tags must be a list containing '{ntype}'")
    if "title" in fm:
        e("title", "title is not a frontmatter field — the H1 is the "
                   "title (run `brain lint --fix-safe`)")
    if not re.search(r"^# .+$", body, re.MULTILINE):
        e("body", "note must open with an H1 title line")

    # required fields
    for field in REQUIRED.get(ntype, []):
        if field not in fm:
            e(field, f"missing required field for type {ntype}")
        elif fm[field] in (None, "", []) and field not in NULLABLE.get(ntype, set()):
            e(field, f"required field is empty (type {ntype})")

    # enums
    for key, allowed in ENUMS.items():
        t, field = key.split(".")
        if ntype == t and field in fm and fm[field] is not None:
            if fm[field] not in allowed:
                e(field, f"invalid value {fm[field]!r} — allowed: {sorted(allowed)}")

    # dates
    for field in ("date", "opened"):
        if field in REQUIRED.get(ntype, []) and isinstance(fm.get(field), str):
            if not DATE_RE.match(fm[field]):
                e(field, "must be YYYY-MM-DD")

    # task week conditional
    if ntype == "task":
        status = fm.get("status")
        week = fm.get("week")
        if status in ("this-week", "done"):
            if not (isinstance(week, str) and WEEK_RE.match(week)):
                e("week", f"week (YYYY-Www) required when status={status}")
        # project must be a slug, not a wikilink
        proj = fm.get("project")
        if isinstance(proj, str) and ("[[" in proj or "/" in proj):
            e("project", "project must be a plain slug or null")

    if ntype == "meeting":
        att = fm.get("attendees")
        if isinstance(att, list):
            for a in att:
                tgt = wikilink_target(a)
                if tgt is None:
                    e("attendees", f"attendee {a!r} is not a wikilink")
                elif not resolves(tgt, idx):
                    e("attendees", f"attendee link target missing: {tgt}")
        proj = fm.get("project")
        if isinstance(proj, str) and ("[[" in proj):
            e("project", "project must be a plain slug or null")

    # frontmatter wikilink fields must resolve
    for field in WIKILINK_FIELDS.get(ntype, []):
        val = fm.get(field)
        if val in (None, "", []):
            continue
        tgt = wikilink_target(val)
        if tgt is None:
            e(field, f"must be a wikilink, got {val!r}")
        elif not resolves(tgt, idx):
            e(field, f"wikilink target missing: {tgt}")

    # task/meeting project slugs should name a project note (warning: older
    # vaults and hand-written notes may predate the project note)
    if ntype in ("task", "meeting"):
        proj = fm.get("project")
        if isinstance(proj, str) and proj and "[[" not in proj and "/" not in proj \
                and f"Projects/{proj}" not in idx and f"Projects/{proj}/{proj}" not in idx:
            warns.append((rel, "project", f"no project note for '{proj}' "
                                          "(create it with `brain capture project`)"))

    # a repo's project is required and validated at write time (unlike
    # task/meeting's advisory, nullable project), so an unresolved one here
    # is an ERROR, not a warning.
    if ntype == "repo":
        proj = fm.get("project")
        if isinstance(proj, str) and ("[[" in proj or "/" in proj):
            e("project", "project must be a plain slug")
        elif proj and f"Projects/{proj}" not in idx and f"Projects/{proj}/{proj}" not in idx:
            e("project", f"no project note for '{proj}' "
                         "(create it with `brain capture project`)")

    # body meta lines (`**Owner:** ...`) mirror frontmatter; flag drift
    for field in sorted(drifted_fields(ntype, fm, body)):
        label = META_LINES[ntype][field]
        warns.append((rel, "meta", f"body '{label}' line disagrees with "
                                   f"frontmatter {field} (run `brain lint --fix-safe`)"))

    # body wikilinks — warnings only (prose may reference notes not written yet)
    for m in BODY_LINK_RE.finditer(body):
        tgt = m.group(1).strip()
        if tgt and not tgt.startswith("http") and not resolves(tgt, idx):
            warns.append((rel, "body", f"unresolved wikilink [[{tgt}]]"))

    return errs, warns


def lint_vault(vault, extra_targets=()):
    """Lint whole vault. Returns (errors, warnings)."""
    idx = link_index(vault, extra=extra_targets)
    errs, warns = [], []
    titles = {}
    for rel in vault_files(vault):
        text = (vault / rel).read_text(encoding="utf-8")
        fm, body = fmyaml.parse(text)
        e, w = lint_note(rel, fm, body, idx)
        errs += e
        warns += w
        # duplicate task definitions: same H1 title across Tasks/, or task-typed
        # notes outside Tasks/
        if fm.get("type") == "task":
            if _folder_of(rel) != "Tasks":
                errs.append((rel, "type", "task-typed note outside Tasks/"))
            m = re.search(r"^# (.+)$", body, re.MULTILINE)
            if m:
                key = m.group(1).strip().lower()
                if key in titles:
                    errs.append((rel, "title",
                                 f"duplicate task definition (same title as {titles[key]})"))
                else:
                    titles[key] = rel
    return sorted(errs), sorted(warns)


ANY_LINK_RE = re.compile(r"\[\[([^\]|#\n]+)(?:[|#][^\]]*)?\]\]")


def orphans(vault):
    """Notes nothing links to (frontmatter or body). Daily/ is exempt: dailies
    are entry points, not link targets."""
    files = [r for r in vault_files(vault) if _folder_of(r) != "Daily"]
    linked = set()
    for rel in vault_files(vault):
        text = (vault / rel).read_text(encoding="utf-8")
        for m in ANY_LINK_RE.finditer(text):
            t = m.group(1).strip().strip("/")
            t = t[:-3] if t.endswith(".md") else t
            linked.add(t)
            linked.add(Path(t).name)
    return [r for r in files if r[:-3] not in linked and Path(r).stem not in linked]


def git_created_date(vault, rel):
    try:
        out = subprocess.run(
            ["git", "-C", str(vault), "log", "--diff-filter=A", "--follow",
             "--format=%as", "--", rel],
            capture_output=True, text=True, timeout=15)
        dates = out.stdout.split()
        if dates:
            return dates[-1]
    except Exception:
        pass
    return None


def infer_created(vault, rel, fm):
    for cand in (fm.get("created"), fm.get("date"), fm.get("opened")):
        if isinstance(cand, str) and DATE_RE.match(cand):
            return cand
    m = re.search(r"(\d{4}-\d{2}-\d{2})", rel)
    if m:
        return m.group(1)
    d = git_created_date(vault, rel)
    if d:
        return d
    import datetime
    mtime = (vault / rel).stat().st_mtime
    return datetime.date.fromtimestamp(mtime).isoformat()


def fix_safe(vault):
    """Apply safe, mechanical autofixes so existing or hand-written notes can be
    adopted into the schema: set `schema`, infer a missing `created`, add an H1
    (from a frontmatter `title` if there is one), drop the frontmatter `title`,
    make `tags` contain the type, sort attendees. Never touches prose.
    Returns list of (rel, fix-description)."""
    fixes = []
    for rel in vault_files(vault):
        p = vault / rel
        text = p.read_text(encoding="utf-8")
        fm, body = fmyaml.parse(text)
        if not fm:
            continue
        changed = False
        if str(fm.get("schema")) != "1":
            fm["schema"] = "1"
            fixes.append((rel, "set schema: 1"))
            changed = True
        created = fm.get("created")
        if not (isinstance(created, str) and DATE_RE.match(created)):
            fm["created"] = infer_created(vault, rel, fm)
            fixes.append((rel, f"set created: {fm['created']}"))
            changed = True
        if not re.search(r"^# .+$", body, re.MULTILINE):
            head = fm["title"] if isinstance(fm.get("title"), str) and fm["title"].strip() \
                else title_of(rel, body)
            body = f"# {head}\n\n" + body.lstrip("\n")
            fixes.append((rel, f"added H1: {head}"))
            changed = True
        if "title" in fm:
            del fm["title"]
            fixes.append((rel, "removed frontmatter title (H1 is the title)"))
            changed = True
        ntype = fm.get("type")
        if ntype in TYPE_BY_FOLDER.values():
            tags = fm.get("tags")
            if not isinstance(tags, list) or ntype not in tags:
                fm["tags"] = sorted(set(tags or []) | {ntype}) if isinstance(tags, list) \
                    else [ntype]
                fixes.append((rel, f"set tags: {fm['tags']}"))
                changed = True
        if fm.get("type") == "meeting" and isinstance(fm.get("attendees"), list):
            srt = sorted(fm["attendees"])
            if srt != fm["attendees"]:
                fm["attendees"] = srt
                fixes.append((rel, "sorted attendees"))
                changed = True
        drifted = drifted_fields(ntype, fm, body)
        if drifted:
            body = sync_meta(ntype, fm, body, fields=drifted)
            fixes.append((rel, f"re-synced body lines: {sorted(drifted)}"))
            changed = True
        if changed:
            write_text(p, fmyaml.compose(fm, body))
    return fixes
