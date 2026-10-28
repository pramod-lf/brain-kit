# Vault schema (`schema: 1`)

Both vaults (work and personal) share one schema. `brain lint` enforces it;
`brain lint --fix-safe` repairs what can be repaired mechanically. The source
of truth is `skills/second-brain/scripts/lib/core.py` (`FOLDERS`, `ENUMS`,
`REQUIRED`, `NULLABLE`, `NAMING`).

## Folders

| Folder | `type` | Filename |
|---|---|---|
| `Daily/` | daily | `YYYY-MM-DD.md` |
| `Meetings/` | meeting | `topic-YYYY-MM-DD.md` |
| `Transcripts/` | transcript | `topic-YYYY-MM-DD-transcript.md` |
| `Interviews/` | interview | `first-last-role-YYYY-MM-DD.md` |
| `Projects/` | project | `slug.md` or `slug/slug.md` (other files inside a project folder are `reference`) |
| `Repos/` | repo | `project-repo.md` (project-prefixed, since repo names like `api` collide across projects) |
| `People/` | person | `Firstname-Lastname.md` (single names are allowed) |
| `Tasks/` | task | `slug.md`; the CLI writes `area-slug.md` |
| `Follow-ups/` | followup | `slug.md`; the CLI writes `firstname-topic.md` |
| `Content/` | content | `slug.md` |
| `Reference/` | reference | `slug.md` |
| `_templates/` | — | Obsidian templates; not linted |

Only the first ten folders are linted and queried. Anything else in a vault
(`README.md`, `Tasks.base`, `.obsidian/`, your own folders) is left alone.

Slugs are lowercase ASCII words joined by `-`. Accented names are
transliterated (`Inés Peña` → `People/Ines-Pena.md`); each word and
hyphenated part of a person's name is capitalised (`anne-marie smith` →
`People/Anne-Marie-Smith.md`). Names and titles with no Latin letters or
digits (e.g. `李雷`) are refused, because no filename can be built from them. Filename slugs drop
stopwords and keep the first few significant words, so two phrasings of the
same request land on the same file.

## Common frontmatter

Every note starts with these keys, in this order, and its body opens with an
H1 title:

```yaml
type: daily|meeting|transcript|interview|project|person|task|followup|content|reference
schema: 1
created: YYYY-MM-DD
tags: [<type>, ...]
```

- `tags` always contains the note's `type`, so `#task`, `#meeting`, etc. work
  in Obsidian search.
- `title` is **not** a frontmatter field. The H1 is the title.
- `created` is the date of the thing the note records:
  - meeting, interview, daily: its `date`;
  - transcript: the date of the meeting or interview it belongs to;
  - task created by `capture meeting` or `extract-tasks`: that meeting's /
    source's `--date`; a standalone `capture task`: today;
  - follow-up: its `opened` date (the meeting date when raised in a meeting);
  - person, note (reference/content): the day it was written.
  `lint --fix-safe` fills a missing `created` from `date`/`opened`, a date in
  the filename, git history, or the file's modification time, in that order.

## Type-specific fields

| type | field | values |
|---|---|---|
| task | `status` | `backlog`, `this-week`, `done` |
| | `owner` | `[[People/...]]` wikilink, required |
| | `project` | project slug or `null` |
| | `area` | `client`, `internal`, `admin`, `learning` |
| | `priority` | `high`, `medium`, `low` |
| | `source` | wikilink or `null` |
| | `week` | `YYYY-Www`, required when status is `this-week` or `done` |
| meeting | `date` | `YYYY-MM-DD` |
| | `attendees` | list of `[[People/...]]` wikilinks (may be empty) |
| | `project` | project slug or `null` |
| | `transcript` | wikilink or `null` |
| interview | `candidate`, `role`, `round` | text |
| | `date` | `YYYY-MM-DD` |
| | `verdict` | `pending`, `hire`, `no-hire` |
| person | `org` | `internal` (your own organization), `external` |
| | `role`, `email` | text or `null` |
| followup | `who` | `[[People/...]]` wikilink |
| | `about` | text |
| | `opened` | `YYYY-MM-DD` |
| | `status` | `waiting`, `done` |
| project | `status` | `active`, `paused`, `done` |
| | `area` | `client`, `internal`, `admin`, `learning` |
| repo | `project` | project slug, required — a repo always belongs to one project |
| | `status` | `active`, `archived` |
| | `role` | text or `null` (e.g. `api`, `frontend`, `infra`; no enum — too variable) |
| | `path` | local filesystem path or `null`; used to auto-detect "the repo I'm in" |
| | `remote` | git remote URL or `null`; second auto-detect signal |
| content | `status` | `draft`, `published` |
| daily, transcript, reference | — | no extra fields |

### `person.org`

`internal` means the vault owner's own organization. When a person is created
without `--org`:

1. if `BRAIN_ORG_DOMAIN` is set and the person has an email, an address at
   that domain is `internal` and any other is `external`;
2. otherwise people in the work vault default to `internal` and people in the
   personal vault to `external`.

Interview candidates are always `external`.

## Ownership and direction

- `task.owner` decides whose work a task is. The owner's own tasks carry
  `[[People/<BRAIN_OWNER>]]`; someone else's action item carries their link.
  Only the owner's tasks appear in `query tasks`, `working-on` and `today`,
  and only those can be promoted. Everyone else's appear under
  `query waiting-on`.
- A `followup` means **the owner is waiting on `who`**. If the owner owes
  someone, it is a task, not a follow-up.

## Multi-repo projects

A `project` can span several repos. Each repo gets its own `repo` note
pointing up at its project (the project note's body never stores a list of
its repos — `query project` and `query repo` both aggregate repos
dynamically, the same way they already aggregate tasks and meetings).

`query repo` with no name auto-detects which repo note matches the current
directory, trying three signals in order and stopping at the first one that
produces a match — ambiguity at a stage (e.g. two repo notes sharing a
`path`) is a terminal error, it never falls through to a weaker later signal:

1. `path` — an exact match against the current directory.
2. `remote` — the output of `git remote get-url origin` in the current
   directory, compared loosely (trailing `/` and `.git` ignored; ssh vs.
   https forms are NOT treated as equal).
3. the current directory's name, matched against the repo note's title.

With no match at all, the command lists every known repo and asks for the
name explicitly, or for `brain capture repo` to register the directory.

## Sections

The CLI writes these section names; queries read them.

- meeting: `## Summary`, `## Decisions`, `## Action Items`, `## Links`
- interview: `## Notes During Interview`, `## Assessment`
- daily: `## Meetings`, `## Interviews`, `## Priority Tasks`, `## Waiting On`,
  `## Work Log`, `## Brain Dump`
- content: `## Draft`; reference: `## Notes`

A section that would be empty is not written (daily notes always get the full
set). A meeting or interview note built from a transcript must carry a summary
or assessment; the CLI refuses otherwise.

## Other lint rules

- Two task notes with the same H1 title are an error (duplicate task).
- A note with `type: task` outside `Tasks/` is an error.
- `task.project` and `meeting.project` are plain slugs: they may not contain
  `[[` (and task `project` may not contain `/`).
- Required keys must be present even when their value may be `null`: a
  person note always has `role:` and `email:` keys, a task always has
  `project:` and `source:`, a meeting always has `attendees:`, `project:` and
  `transcript:`.
- `week` must be `YYYY-Www`; `date`, `opened`, `created` must be `YYYY-MM-DD`.
- Filenames must match the naming rules above.
- Warnings (not errors): a `task.project` / `meeting.project` with no project
  note; a body meta line (`**Owner:**`, `**Role:**`, `**Verdict:**`, …) that
  disagrees with its frontmatter field (`lint --fix-safe` re-syncs it).
- A `repo.project` with no matching project note is an **error**, not a
  warning — unlike task/meeting, a repo's `project` is required and
  validated against existing project notes at write time, so it should
  always resolve.

## Mutability

A note's filename is its identity. `set` and `append` never rename a file:
changing a task's `--desc` or a follow-up's `--about` changes only the H1.

| type | identity (never changes) | `set` fields | `append` target |
|---|---|---|---|
| task | slug | `status`, `priority`, `area`, `owner`, `project`, `desc`, `week` | `## Notes` (dated line) |
| followup | slug | `status`, `about` | `## Updates` (dated line) |
| project | slug | `status`, `area` | `## Context` (prose), `## Milestones` (`- [ ]` lines) |
| repo | slug | `status`, `role`, `project`, `path`, `remote` | `## Activity Log` (dated line) |
| person | name | `org`, `role`, `email` | `## Notes` (dated line) |
| interview | candidate, role, date | `verdict`, `round` | `## Notes During Interview`, `## Assessment` |
| meeting | title, date | `project`, attendees | `## Summary` (prose), `## Decisions` |
| content | slug | `status` | `## Draft` (prose) |
| reference | slug | none | `## Notes` (prose) |
| daily | date | none | `## Work Log`, `## Brain Dump` (created if missing) |
| transcript | slug | none: transcripts are immutable | none |

- `set` mirrors a field into its body line (`**Owner:**`, `**Role:**`, …), so
  the two never disagree. `none` clears a nullable field.
- Task: `--status backlog` removes `week`; `this-week` needs the owner's own
  task and sets `week` (and the daily Priority Tasks line); `done` fills
  `week` if empty.
- Follow-up: going from `done` back to `waiting` sets `opened` to today.
- `--project` on a task or meeting must name an existing project note.
- Appending is idempotent: the same text twice adds it once.

## Links

Frontmatter wikilinks (`attendees`, `owner`, `source`, `transcript`, `who`)
must resolve to an existing note: an unresolved one is a lint **error**.
Unresolved wikilinks in the body are **warnings**. `brain doctor` also lists
orphans (notes nothing links to; daily notes are exempt).
