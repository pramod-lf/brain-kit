# Changelog

All notable changes to brain-kit. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/).

## [1.3.0] - 2026-10-28

Multi-repo projects: a project can now span several git repos, each with its
own persistent context, and brain-kit pulls in the other repos' status
whichever one you're working in.

### Added
- A new `repo` note type (`Repos/`): `brain capture repo --name NAME
  --project SLUG [--role R] [--path PATH] [--remote URL] [--purpose TEXT]`
  registers a repo under a project. Run from inside the repo's checkout with
  no `--path`/`--remote` and both default to the current directory and its
  git remote — a one-command way to register "this repo."
- `brain query repo [NAME]` — with no name, auto-detects which repo note
  matches the current directory (by stored path, then git remote, then
  directory name) and prints that repo's own context, its project's
  `## Context`, and a live list of its sibling repos in the same project
  (each with their most recent activity-log line) — the "what's going on
  elsewhere in this project" view. `brain query repos [--project SLUG]
  [--status active|archived]` lists every repo.
- `brain set repo REF [--status active|archived] [--role R] [--project SLUG]
  [--path PATH] [--remote URL]` and `brain append repo REF --text "…"` (logs
  a dated line to `## Activity Log`).
- `brain query project NAME` now also lists the project's repos.
- `lint` treats a repo whose `project` does not resolve to an existing
  project note as an error (task/meeting treat the same situation as a
  warning, since their `project` is inferred and advisory; a repo's is
  required and validated at write time).

## [1.2.0] - 2026-10-27

The CLI now captures, edits and reads every kind of note, so nothing has to
be edited by hand.

### Added
- `brain capture project --name NAME [--area A] [--context-file F]` creates an
  active project note. Tasks and meetings infer the new project from their
  titles. Re-running with the same name changes nothing.
- `brain set <type> REF …` changes fields and status of an existing note:
  task (status, priority, area, owner, project, desc, week), follow-up
  (status, about), project (status, area), person (org, role, email),
  interview (verdict, round), content (status) and meeting (project,
  attendees). It rewrites the body lines that mirror a field, so the note and
  its frontmatter never disagree. Closing a follow-up, pausing a project and
  publishing a draft were impossible before.
- `brain append <type> REF …` adds prose to the one section each type
  designates (Reference/Content text, person notes, follow-up updates, project
  context and milestones, meeting decisions, interview notes, task notes, and
  the daily Work Log / Brain Dump). It never replaces text, and repeating a
  command changes nothing.
- `brain query show FOLDER/STEM` prints any one note in full, including past
  daily notes. New listings: `query projects`, `followups`, `interviews`,
  `people`, `dailies`, `transcripts` and `search WORDS`. `query tasks`,
  `meetings` and `notes` gained filters.
- `lint` warns when a task or meeting names a project that has no note, and
  when a body line (`**Owner:**`, `**Role:**`, …) disagrees with its
  frontmatter. `lint --fix-safe` repairs the second kind.

### Fixed
- Re-running `capture project` or `capture note` on an existing note printed
  nothing and silently dropped the new text. It now prints `UNCHANGED` plus a
  `NOTE:` on stderr that names the `set` or `append` command to use. Other
  captures print the same `NOTE:` when a value they were given was not applied
  (a task's project or owner, a person's role or email).
- A task request that maps to an existing task's filename is no longer
  dropped silently. An explicit priority (`--priority`, or the third field of
  `--task`) now updates the existing task, and different wording prints a
  `MATCHED` line naming the existing task. Before this, both cases printed
  `UNCHANGED`. A `--task` spec with no priority no longer resets an existing
  task to `medium`.
- The same task title under a different `--area` wrote a duplicate task file;
  only `lint` caught it afterwards. The write is now refused.
- `capture interview --verdict` and `capture person --org` updated the
  frontmatter but left the old value in the note body.
- A round-2 interview on the same day merged into the round-1 note. It is now
  refused with a pointer to `set interview --round` or `--date`.
- `brain doctor` counted every warning as a broken link; it now reports
  warnings separately.

## [1.1.0] - 2026-10-27

### Added
- `brain query notes [TEXT]` finds notes in `Reference/` and `Content/`.
  Before this, `capture note` wrote these notes but no query read them, and
  the skill forbids direct vault reads. One match prints the whole note.

## [1.0.1] - 2026-10-27

### Changed
- The installers (`install.sh`, `install.ps1`) now install the **latest
  GitHub release** instead of the `main` branch. Pin a version with
  `BRAIN_KIT_REF=v1.0.1` (or `sh -s v1.0.1`). If the latest release cannot be
  found, the installer stops with an error. It never falls back to `main`.
- The installers print a `source:` line naming the release they installed.

### Added
- `brain update` installs the latest release in place. `brain update --check`
  only reports whether one exists. `brain update --to <tag>` installs a
  specific release (pin or roll back). This is the only command that uses the
  network, and it runs only when you ask.
- The installers write a receipt, `install.json`, next to the installed skill
  (version, source, method, date).
- `metadata.version` in the SKILL.md frontmatter.
- This changelog. CI checks that the CLI version, `metadata.version`, the
  newest changelog entry and the release tag all agree.

## [1.0.0] - 2026-10-27

### Added
- First release: the `second-brain` skill and its CLI, installers for macOS,
  Linux and Windows, and CI on all three.

[1.1.0]: https://github.com/RobusGauli/brain-kit/compare/v1.0.1...v1.1.0
[1.0.1]: https://github.com/RobusGauli/brain-kit/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/RobusGauli/brain-kit/releases/tag/v1.0.0
