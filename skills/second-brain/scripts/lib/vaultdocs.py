"""Vault scaffolding written by `brain init`: the folder skeleton, a README
that documents the schema, Obsidian `_templates/` that produce lint-clean
notes, and a `Tasks.base` view.

Everything here is deterministic and never overwrites a file that already
exists, so re-running `brain init` is safe.

Nothing here is linted (the linter only walks the ten schema folders), but the
templates are written so that a note created from one passes lint once its
obvious blanks are filled.
"""

from .core import ENUMS, FOLDERS, write_text

README = """# {title}

This vault is managed by the **second-brain** CLI (`schema: 1`). Notes are
written by `brain capture ...`, not by hand.

## Folders

| Folder | `type` | Filename |
|---|---|---|
| `Daily/` | daily | `YYYY-MM-DD.md` |
| `Meetings/` | meeting | `topic-YYYY-MM-DD.md` |
| `Transcripts/` | transcript | `topic-YYYY-MM-DD-transcript.md` |
| `Interviews/` | interview | `first-last-role-YYYY-MM-DD.md` |
| `Projects/` | project | `slug.md` or `slug/slug.md` |
| `Repos/` | repo | `project-repo.md` (project-prefixed to avoid name collisions) |
| `People/` | person | `Firstname-Lastname.md` |
| `Tasks/` | task | `slug.md` (CLI-written ones are `area-slug.md`) |
| `Follow-ups/` | followup | `firstname-topic.md` |
| `Content/` | content | `slug.md` |
| `Reference/` | reference | `slug.md` |
| `_templates/` | — | Obsidian template picker only |

Anything outside those folders (this file, `Tasks.base`, `.obsidian/`) is
unmanaged: the linter does not walk it and no query reads it.

## Frontmatter

Every note starts with these four keys, in this order, and opens its body with
an H1 title:

```yaml
type: <one of the ten above>
schema: 1
created: YYYY-MM-DD
tags: [<type>]
```

`title` is deliberately not a frontmatter field: the H1 is the title.

Type-specific required fields:

{fields}

Enums:

{enums}

`week` (`YYYY-Www`) is required on a task whose status is `this-week` or `done`.
`person.org` is `internal` for people in your own organization, `external`
for everyone else.

## Task ownership

`owner` is required and is a `[[People/...]]` wikilink. Your own tasks carry
`[[People/OWNER]]`; an action item someone else took on carries **their** link.
Only your own tasks appear in `brain query tasks`, `working-on` and `today`,
and only those can be promoted. Everyone else's appear under
`brain query waiting-on`.

## Follow-up direction

A `followup` note means **you are waiting on `who`**. If you owe someone, that
is not a follow-up: it is a task with `owner: [[People/OWNER]]`.

## Rules

- The CLI is the only writer. It is atomic (nothing is written unless the
  whole set lints) and idempotent (re-running a command produces the same
  bytes).
- A section that would be empty is not written. A meeting or interview note
  built from a transcript must carry a summary or assessment.
- Run `brain lint` (or `brain lint --fix-safe`) after any manual change.
  Frontmatter wikilinks that do not resolve are errors; body wikilinks that do
  not resolve are warnings.
"""

# --- Obsidian templates -------------------------------------------
# Placeholders are Obsidian-core `{{date}}` / `{{title}}`; anything else is left
# for the human to fill. Written so a note created from a template lints once
# the obvious blanks are filled.

TEMPLATES = {
    "Daily": """---
type: daily
schema: 1
created: {{date}}
tags:
  - daily
---

# {{date}}

## Meetings

## Interviews

## Priority Tasks

## Waiting On

## Work Log

## Brain Dump
""",
    "Meeting": """---
type: meeting
schema: 1
created: {{date}}
tags:
  - meeting
date: {{date}}
attendees:
  - "[[People/FIRST-LAST]]"
project: null
transcript: null
---

# {{title}}

**Date:** {{date}}
**Project:** —
**Attendees:** —

## Summary

## Decisions

## Action Items

## Links
""",
    "Interview": """---
type: interview
schema: 1
created: {{date}}
tags:
  - interview
candidate: FIRST LAST
role: ROLE
round: "1"
date: {{date}}
verdict: pending
---

# {{title}}

**Candidate:** [[People/FIRST-LAST]]
**Round:** 1
**Verdict:** pending

## Notes During Interview

## Assessment
""",
    "Task": """---
type: task
schema: 1
created: {{date}}
tags:
  - task
status: backlog
owner: "[[People/OWNER]]"
project: null
area: internal
priority: medium
source: null
---

# {{title}}

**Owner:** [[People/OWNER]]
**Source:** —
""",
    "Person": """---
type: person
schema: 1
created: {{date}}
tags:
  - person
org: {org}
role: null
email: null
---

# {{title}}

## Context
""",
    "Project": """---
type: project
schema: 1
created: {{date}}
tags:
  - project
status: active
area: internal
---

# {{title}}

## Context

## Milestones
""",
    "Repo": """---
type: repo
schema: 1
created: {{date}}
tags:
  - repo
project: PROJECT-SLUG
status: active
role: null
path: null
remote: null
---

# {{title}}

**Project:** [[Projects/PROJECT-SLUG]]
**Role:** —

## Purpose

## Activity Log
""",
    "Follow-up": """---
type: followup
schema: 1
created: {{date}}
tags:
  - followup
who: "[[People/FIRST-LAST]]"
about: WHAT YOU ARE WAITING FOR
opened: {{date}}
status: waiting
---

# {{title}}

**Who:** [[People/FIRST-LAST]]
**About:** WHAT YOU ARE WAITING FOR

> A follow-up means YOU are waiting on THEM. If you owe them, make a task
> with owner [[People/OWNER]] instead.
""",
    "Content": """---
type: content
schema: 1
created: {{date}}
tags:
  - content
status: draft
---

# {{title}}

## Draft
""",
    "Reference": """---
type: reference
schema: 1
created: {{date}}
tags:
  - reference
---

# {{title}}

## Notes
""",
    "Transcript": """---
type: transcript
schema: 1
created: {{date}}
tags:
  - transcript
---

# {{title}} — Transcript

## Raw Transcript
""",
}

# --- Tasks.base ----------------------------------------------------------------
# Obsidian Bases: `filters` narrows the note set, each view is a table over it.
# Kept deliberately simple — folder + schema + type, then one view per status,
# with `owner` visible everywhere because it is the field that decides whose
# work a row represents.

TASKS_BASE = """filters:
  and:
    - file.inFolder("Tasks")
    - type == "task"
    - schema == 1
views:
  - type: table
    name: My backlog
    filters:
      and:
        - status == "backlog"
        - owner == "[[People/OWNER]]"
    order:
      - file.name
      - priority
      - project
      - area
      - source
    sort:
      - property: priority
        direction: ASC
    columnSize:
      file.name: 320
  - type: table
    name: This week
    filters:
      and:
        - status == "this-week"
        - owner == "[[People/OWNER]]"
    order:
      - file.name
      - priority
      - project
      - week
    columnSize:
      file.name: 320
  - type: table
    name: Owed by others
    filters:
      and:
        - status != "done"
        - owner != "[[People/OWNER]]"
    order:
      - file.name
      - owner
      - project
      - source
    sort:
      - property: owner
        direction: ASC
  - type: table
    name: All
    order:
      - file.name
      - status
      - owner
      - priority
      - project
      - area
      - week
      - source
    sort:
      - property: status
        direction: ASC
"""


def _fields_table():
    from .core import NULLABLE, REQUIRED
    rows = ["| type | required fields (beyond the common four) |", "|---|---|"]
    for t in sorted(REQUIRED):
        fields = REQUIRED[t]
        if not fields:
            rows.append(f"| {t} | — |")
            continue
        nul = NULLABLE.get(t, set())
        rows.append("| {} | {} |".format(
            t, ", ".join(f"`{f}`" + (" (nullable)" if f in nul else "")
                         for f in fields)))
    return "\n".join(rows)


def _enums_table():
    rows = ["| field | allowed |", "|---|---|"]
    for key in sorted(ENUMS):
        rows.append(f"| `{key}` | {', '.join(sorted(ENUMS[key]))} |")
    return "\n".join(rows)


PLACEHOLDER = "[[People/OWNER]]"


def _put(path, text, owner_link, written):
    """Create `path` if missing. An existing file is left alone, with one
    exception: if it is byte-for-byte what an earlier `init` wrote without an
    owner (so it still carries the placeholder and the user has not edited it),
    it is regenerated now that the owner is known."""
    final = text.replace(PLACEHOLDER, owner_link)
    if path.exists():
        old = path.read_text(encoding="utf-8")
        if old != final and PLACEHOLDER in old and old == text \
                and owner_link != PLACEHOLDER:
            write_text(path, final)
            written.append(f"updated {path} (owner filled in)")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    write_text(path, final)
    written.append(f"created {path}")


def write_all(vault, mode, owner_link=None):
    """Create the folder skeleton plus README.md, _templates/*.md and
    Tasks.base. Existing files are left untouched. Returns log lines."""
    owner_link = owner_link or PLACEHOLDER
    out = []
    for folder in FOLDERS:
        d = vault / folder
        if not d.is_dir():
            d.mkdir(parents=True)
            out.append(f"created {d}/")
    title = "Work brain" if mode == "work" else "Personal brain"
    _put(vault / "README.md",
         README.format(title=title, fields=_fields_table(),
                       enums=_enums_table()), owner_link, out)
    org = "internal" if mode == "work" else "external"
    for name, text in sorted(TEMPLATES.items()):
        _put(vault / "_templates" / f"{name}.md", text.replace("{org}", org),
             owner_link, out)
    _put(vault / "Tasks.base", TASKS_BASE, owner_link, out)
    return out
