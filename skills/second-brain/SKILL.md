---
name: second-brain
description: The user's second brain — two Obsidian vaults (work and personal) where everything the user asks to save is kept. Use for every "remember X", "note down / jot down / save / log / capture / write up X", "we decided X", "add a task", "remind me to X", "I'm waiting on X", "start / create / pause / finish a project", "register this repo / add this repo to the project", "what am I working on", "what's happening in this repo", "what's going on in the rest of this project", "what's on my plate", "who is X", and any change to something already saved ("mark it done", "make it high priority", "I'm no longer waiting on X", "update Sam's role", "add to my note on X", "archive this repo"), plus anything about notes, daily notes, meetings, interviews, transcripts, tasks, projects, repos, people or follow-ups. Also use to set up or update brain-kit.
metadata:
  version: "1.3.0"
---

# Second Brain

A CLI does every vault read and write. Your job is to turn the user's words into **one** command, run it, and relay its output.

## Find the CLI

The CLI is a file named `brain`. Use the first of these that exists:

1. `scripts/brain` in the directory that contains this SKILL.md (for example `~/.claude/skills/second-brain/` or `.agents/skills/second-brain/`).
2. Where the installer puts it: `${XDG_DATA_HOME:-$HOME/.local/share}/brain-kit/skills/second-brain/scripts/brain` on macOS and Linux, `%LOCALAPPDATA%\brain-kit\skills\second-brain\scripts\brain` on Windows.

Do not use a bare `brain` from PATH. Another tool can have that name.

Resolve the path to an absolute path once, then start every shell command with:

```
B="<absolute path>/scripts/brain"
```

Then call it as `python3 "$B" <command>`. Keep the quotes and the `python3`: they make the call work in bash and zsh, with spaces in the path, and without the file's executable bit.

On Windows, `python3` often does not exist. Use `py -3` in its place (or the command on the installer's `python:` line). The `B=` form works in Git Bash, which Claude Code uses. In PowerShell, write `$B = "<absolute path>\scripts\brain"`, then `py -3 $B <command>`.

## Install it if it is missing

If neither path exists (for example, you read this file from a URL), install it. The command takes one line and needs no configuration:

```bash
curl -fsSL https://raw.githubusercontent.com/RobusGauli/brain-kit/main/install.sh | sh
```

On Windows, run this in PowerShell, not in Git Bash:

```powershell
irm https://raw.githubusercontent.com/RobusGauli/brain-kit/main/install.ps1 | iex
```

From Git Bash (Claude Code's shell on Windows), call it as `powershell -NoProfile -Command "irm https://raw.githubusercontent.com/RobusGauli/brain-kit/main/install.ps1 | iex"`.

Both need Python 3.9 or newer. The installer gets the latest release (not the `main` branch). It copies the skill to `~/.local/share/brain-kit/` (`%LOCALAPPDATA%\brain-kit\` on Windows) and links it into the skill folders of Claude Code, Codex, Cursor and Kiro. It does not touch vaults or config. Use the path on its `cli:` line as `$B`. The output ends with `done.`. If that line is missing, the install failed: show the user the output. To update later, use `python3 "$B" update` (see the router), not the installer.

## First check what is already true

```bash
python3 "$B" status
```

If `owner:` and both vault paths are set, setup is done. Go to the router.

If the owner or a vault is unset, ask the user for these three things in one message:

1. the folder of their **work** vault,
2. the folder of their **personal** vault,
3. their full name, as it should appear on their People note.

Their company email domain is optional (it marks colleagues as `internal`). If they have no Obsidian vaults yet, offer `~/Obsidian/Work` and `~/Obsidian/Personal`, and use them only when they agree. Never pick paths yourself. Then run:

```bash
python3 "$B" init --work-vault "<work>" --personal-vault "<personal>" --owner "<Full Name>" [--org-domain example.com]
python3 "$B" status
```

`init` never overwrites existing notes and is safe to run again. After it succeeds, tell the user that setup is done and give three things they can say: "add a task to …", "log this meeting: …", "what am I waiting on?"

A write command creates every file the request needs in one step (note, tasks, follow-ups, people, daily links) and lints the result. Its `WROTE` / `UPDATED` / `UNCHANGED` / `LINKED` lines are your confirmation — relay them. A `MATCHED` line means the request landed on an existing task with different wording, so no new task was made: tell the user which task it matched. If lint fails, the CLI writes nothing and prints `file:field:problem`. Fix the flags and run again.

## Router

| The user says… | Run |
|---|---|
| "what am I working on" / "my projects" | `python3 "$B" query working-on` |
| "where are we with X" / "status of X" | `python3 "$B" query project "<name>"` |
| "what's happening in this repo" / "repo status" / "where are we in this repo" | `python3 "$B" query repo` (no name — auto-detects the repo from the current directory) |
| "status of repo X" / "what's happening in <repo>" (naming a DIFFERENT repo than the one you're in) | `python3 "$B" query repo "<name>"` |
| "what's going on in the rest of this project" / "other repos" | same `python3 "$B" query repo` call — its output already lists sibling repos |
| "all repos" / "repos in project X" / "archived repos" | `python3 "$B" query repos [--project <slug>] [--status active\|archived]` |
| "my tasks" / "backlog" / "what's on my plate" | `python3 "$B" query tasks [--status this-week] [--project <slug>]` |
| "what am I waiting on" / "open follow-ups" | `python3 "$B" query waiting-on` |
| "what's today look like" / "today's note" | `python3 "$B" query today` |
| "who is X" / "my history with X" | `python3 "$B" query person "<name>"` |
| "recent meetings" / "meetings since June" | `python3 "$B" query meetings [--since YYYY-MM-DD]` |
| "find my note on X" / "what did I save about X" / "my reference notes" | `python3 "$B" query notes ["<words>"]` |
| "log / write up this meeting" | `python3 "$B" capture meeting --title "T" [--date D] [--attendees "A, B"] [--transcript-file F --summary-file S] [--decision "…"]... [--task "…"]... [--followup "…"]...` |
| "I interviewed X for role Y" | `python3 "$B" capture interview --candidate "Name" --role "R" --round N [--date D] [--transcript-file F --assessment-file A] [--note "…"]... [--verdict hire]` |
| "add a task …" / "remind me to …" | `python3 "$B" capture task --desc "D" --area <area> [--owner "Name"] [--priority P] [--this-week]` |
| "just pull the action items out of this file" | `python3 "$B" extract-tasks --title "T" --date D --transcript-file F --task "…"...` |
| "note down / save / remember / we decided X" | `python3 "$B" capture note --title "T" --body-file F` |
| "save my notes at FILE" | `python3 "$B" capture note --title "T" --body-file FILE` — one note, nothing else |
| "draft a blog post about X" | `python3 "$B" capture note --title "T" --folder Content --body-file F` |
| "show me the meeting / task / note X" / "what was in yesterday's note" | `python3 "$B" query show <Folder/stem>` |
| "all my projects" / "paused projects" | `python3 "$B" query projects [--status active\|paused\|done]` |
| "what am I waiting on from Sam" / "closed follow-ups" | `python3 "$B" query followups [--who "Sam"] [--status all]` |
| "my candidates" / "pending verdicts" | `python3 "$B" query interviews [--verdict pending]` |
| "who do I know at X" / "list people" | `python3 "$B" query people [--org external] [--text "words"]` |
| "what did we decide about X" / "search my notes for X" | `python3 "$B" query search "<words>" [--type T]` |
| "I heard back from X" / "close that follow-up" / "no longer waiting on X" | `python3 "$B" set followup <slug> --status done` |
| "pause / finish / reactivate project X" | `python3 "$B" set project "<name>" --status paused\|done\|active` |
| "archive / reactivate repo X" / "move repo X to project Y" | `python3 "$B" set repo <slug> [--status active\|archived] [--project <slug>] [--role R]` |
| "make X high priority" / "move X back to backlog" / "reopen X" / "X is Sam's now" | `python3 "$B" set task <slug> [--priority P] [--status S] [--owner "Name"]` |
| "X's role / email / company changed" | `python3 "$B" set person "<name>" [--role R] [--email E] [--org external]` |
| "hire / no-hire for X" | `python3 "$B" set interview <slug> --verdict hire\|no-hire` |
| "I published X" | `python3 "$B" set content <slug> --status published` |
| "add Sam to that meeting" / "that meeting was for project X" | `python3 "$B" set meeting <slug> [--add-attendee "Name"] [--project SLUG]` |
| "add to my note on X" / "note about Sam: …" / "update on follow-up X" / "add a milestone" | `python3 "$B" append <type> <ref> --text "…"` (or `--file F`, `--milestone "…"`, `--decision "…"`) |
| "log that I worked on X today" / "put X in my brain dump" | `python3 "$B" append daily [YYYY-MM-DD] --log "…"` (or `--dump "…"`) |
| "start / create a project" / "new project X" | `python3 "$B" capture project --name "X" [--area client\|internal\|admin\|learning]` |
| "register this repo" / "add this repo to project X" / "this repo is part of project X" | `python3 "$B" capture repo --name "X" --project <slug> [--role R] [--path .] [--remote <git-remote-url>]` (run from inside the repo's checkout; `--path`/`--remote` default to the current directory) |
| "log what I did in this repo" / "note progress here" / "what I worked on in this repo today" | `python3 "$B" append repo <slug> --text "…"` |
| "remember <person>" / "met a new person" | `python3 "$B" capture person --name "Name" [--org external] [--role R] [--email E]` |
| "I'm waiting on X for Y" / "chase X about Y" | `python3 "$B" capture followup --who "Name" --about "Y"` |
| "move task X to this week" | `python3 "$B" promote --task <slug>...` |
| "mark X done" | `python3 "$B" done --task <slug>...` |
| "switch to my personal / work brain" | `python3 "$B" mode personal --because "<the user's sentence, verbatim>"` (or `work`) |
| "which brain am I in" | `python3 "$B" status` |
| "is there a new version of brain-kit" | `python3 "$B" update --check` |
| "update brain-kit" | `python3 "$B" update` |
| "check the vault" | `python3 "$B" lint [--fix-safe]` |

Every `<slug>`, `<ref>` and `<Folder/stem>` comes from an earlier `query` output line (`query tasks`, `query followups`, `query projects`, …). Never build one by hand. `set` and `append` never create the note they edit (except `append daily`); to start something new, use `capture`. A new person named in `--owner` or `--add-attendee` gets a People stub, as with `capture`.

## Pick exactly one row

1. **A meeting to log is always one `capture meeting`**, with or without a transcript. Put its tasks in `--task` and its follow-ups in `--followup` on that same command. Never add `extract-tasks` or a second command.
2. **`extract-tasks` only** when the user wants the tasks and nothing else.
3. **Changing something that already exists is `set` (fields and status) or `append` (more prose), never `capture`.** `capture` creates or merges and never overwrites a value; if it prints `NOTE: … keeps …`, nothing was changed, so run the `set` command the note gives.
4. **Otherwise the user's verb decides**, not the content. "note down / jot down / save / remember / write up" → `capture note` (`capture person` for a person). "add a task / remind me to" → `capture task`. "I want to" and "I need to" are not task verbs: "jot down that I want to visit the botanical garden" is a note titled "visit the botanical garden".

## Fill the flags

Two sessions given the same words must produce the same command. So every flag comes from a rule, never from your judgment. When a rule says omit, omit — a missing optional flag is better than a guess.

- **`--title` / `--desc` are the user's own words.** Remove only the leading request phrase — everything through the last of: log, capture, record, note down (that), jot down (that), write up, save, remember, add a task (to), remind me to, I want to, I need to, we decided to. Stop at the first comma, period or em dash (—). Keep hyphenated words whole. Copy the rest character for character: no new, dropped, reordered, shortened or expanded words, and no tense changes. "Note down that we decided to move book club to Thursdays, starting next month" → `--title "move book club to Thursdays"`.
- **A meeting title is the topic only** — the words after "about", "on" or "re:". Never include "meeting" or an attendee's name. With no topic, use the source file's heading. With no file either, use `"<First name> sync"`.
- **A blog title is the words after "about"**, to the first comma, period or em dash (—). The body file is the finished draft: at least three paragraphs of real prose, no headings-only outline, no `[[wikilinks]]`.
- **Omit unless the user says it:**
  - `--this-week`: only for "today", "this week" or "priorities".
  - `--priority`: only for high, urgent, critical, top, low or whenever. A deadline is not a priority — it stays in the `--desc` text.
  - `--org external`: only when an organization other than the user's own is named. `internal` is the default in the work vault.
  - `--date`: turn "today", "yesterday" or "last Tuesday" into YYYY-MM-DD. With no date, omit it (the CLI uses today).
- **Never pass `--project` to `capture`.** The CLI infers it from the title. `set task|meeting --project` is for when the user names the project to move it to. **`capture repo` is the one exception: `--project` is required and must name an existing project note** — a repo has no title to infer it from, so ask for the project if the user did not name one.
- **`set` flags:** pass only the fields the user changed, one flag each. `none` clears a nullable field (`--project none`, `--role none`). `--status done` on a task is "mark done"; `--status backlog` is "reopen" or "move back".
- **`append` text:** a short line goes in `--text`; anything longer goes in a temp file under `/tmp` and `--file`. Write what the user said, no headings. Append never replaces: to correct a mistake, append the correction.
- **Names exactly as written.** If the user wrote "Maya", pass `Maya`. Never add a surname. The CLI matches short names to People notes.
- **`--area`** (standalone `capture task` only): a client engagement → `client`. Study, reading or courses → `learning`. Visa, HR, expenses, travel or bookings → `admin`. Otherwise → `internal`.
- **`--role`** on `person`/`interview` is the job title only: "VP of Engineering at Acme" → `--role "VP of Engineering" --org external`. On `capture repo`/`set repo`, `--role` instead means the repo's part in the project (e.g. `api`, `frontend`, `infra`) — pass the word the user used, omit it when they didn't say.
- **Prose goes in a temp file** under `/tmp`, passed with `--body-file`, `--summary-file` or `--assessment-file`. A `capture note` always needs `--body-file` with finished prose, not empty headings.
- **Flag formats:** `--task "desc|area|priority|owner"` and `--followup "Who|about"`. Only the first field is required. Omit the owner for the user's own tasks.

## Source files

**When the request names a file** (a transcript or notes), read that file. Then read [references/sources.md](references/sources.md) **before you build the command.** It defines the title, date and attendees, the summary and decisions, which lines become tasks, who owns them, and follow-up direction.

## Mode

The active vault stays until the user changes it. Switch only when the user's own sentence names the other vault ("switch to my personal brain", "in my personal brain, …"). Pass that sentence in `--because`. The CLI refuses a switch whose quote does not name the target vault. Never switch because content feels personal or work-related. If the answer lives in the other vault, say so.

## When something is wrong

- **`python3: command not found` or "needs 3.9 or newer"**: the user must install Python 3.9+. Then run the same command again.
- **`owner: (unset …)` or no vault**: do the setup in "First check what is already true".
- **`skipped: … already exists`** from the installer: a different file or folder already uses that name. The installer did not change it. Tell the user, and keep using the `cli:` path.
- **Lint failure (`file:field:problem`)**: nothing was written. Fix the flag the line names and run the command again.

## Never

- Notes the user asks to save go in the vault through the CLI, not in your own memory. "Remember X" is a `capture` command.
- Never write or edit vault files directly — not with Write, Edit, `sed`, `echo` or Python. Only the CLI writes.
- Never read, `ls`, `grep` or `cat` vault files. The `query` output is the answer.
- Never ask a clarifying question when a rule gives a default. Ask only when a required fact is missing, such as a candidate's name.
- Never edit transcripts or `_templates/`.
