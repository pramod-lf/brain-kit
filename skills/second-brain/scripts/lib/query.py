"""brain query * — complete one-shot markdown answers."""

import re
import unicodedata
from pathlib import Path

from . import fmyaml
from .core import (FOLDER_BY_TYPE, REQUIRED, die, iso_week, owner_link,
                   parse_date, parse_week, self_words, slugify, today,
                   wikilink_target)
from .linter import vault_files
from .people import people_stems, resolve_stem
from .projects import project_rels
from .refs import clean_ref
from .repos import git_remote_url, normalize_remote
from .writer import section_text


def _notes(vault, folder=None, ntype=None):
    out = []
    for rel in vault_files(vault):
        if folder and not rel.startswith(folder + "/"):
            continue
        fm, body = fmyaml.parse((vault / rel).read_text(encoding="utf-8"))
        if ntype and fm.get("type") != ntype:
            continue
        out.append((rel, fm, body))
    return out


def _title(rel, body):
    m = re.search(r"^# (.+)$", body, re.MULTILINE)
    return m.group(1).strip() if m else Path(rel).stem


def _task_line(rel, fm, body):
    slug = Path(rel).stem
    bits = [f"priority: {fm.get('priority')}", f"area: {fm.get('area')}"]
    if fm.get("project"):
        bits.append(f"project: {fm['project']}")
    if fm.get("week"):
        bits.append(f"week: {fm['week']}")
    if fm.get("owner") not in (None, "", owner_link()):
        bits.append(f"owner: {fm['owner']}")
    return f"- [[Tasks/{slug}]] — {_title(rel, body)} ({', '.join(bits)})"


def _owner_name(fm):
    o = str(fm.get("owner") or owner_link() or "")
    return o.strip("[]").split("/")[-1].split("|")[0]


def mine(fm):
    """The owner's own tasks. `owner` is required; a hand-written task with no
    owner counts as theirs."""
    return fm.get("owner") in (None, "", owner_link())


def _owner_filter(tasks, owner):
    """--owner me|all|<name>. Default 'me' keeps other people's action items out
    of the backlog."""
    o = (owner or "me").strip().lower()
    if o == "all":
        return tasks
    if o in self_words():
        return [t for t in tasks if mine(t[1])]
    return [t for t in tasks if o in _owner_name(t[1]).lower().replace("-", " ")]


def _mentions_project(rel, body, tokens):
    hay = (Path(rel).stem + " " + _title(rel, body)).lower()
    return all(t in hay for t in tokens)


def cmd_tasks(vault, args):
    owner = getattr(args, "owner", "me")
    all_tasks = _owner_filter(_notes(vault, "Tasks", "task"), owner)
    tasks = all_tasks
    if getattr(args, "area", None):
        tasks = [t for t in tasks if t[1].get("area") == args.area]
    if getattr(args, "priority", None):
        tasks = [t for t in tasks if t[1].get("priority") == args.priority]
    if getattr(args, "week", None):
        week = parse_week(args.week)
        tasks = [t for t in tasks if t[1].get("week") == week]
    if args.status:
        tasks = [t for t in tasks if t[1].get("status") == args.status]
    scoped = tasks
    if args.project:
        scoped = [t for t in tasks if t[1].get("project") == args.project]
    who = "mine" if (owner or "me").lower() in self_words() else owner
    print(f"# Tasks ({len(scoped)}; owner: {who})")
    for status in ("this-week", "backlog", "done"):
        grp = [t for t in scoped if t[1].get("status") == status]
        if not grp:
            continue
        print(f"\n## {status} ({len(grp)})")
        for rel, fm, body in grp:
            print(_task_line(rel, fm, body))
    if args.project:
        # A task can name the project in its title while being filed under a
        # parent/umbrella project. The one-shot answer must surface those too:
        # query output is the complete answer, with no follow-up reads.
        toks = [t for t in args.project.split("-") if len(t) > 2]
        related = [t for t in tasks
                   if t[1].get("project") != args.project
                   and _mentions_project(t[0], t[2], toks)]
        print(f"\n## also mentioning '{args.project}' (filed under another project) "
              f"({len(related)})")
        for rel, fm, body in related:
            print(f"- [{fm.get('status')}] " + _task_line(rel, fm, body)[2:])


def cmd_working_on(vault, args):
    print("# Working on")
    projects = [(r, f, b) for r, f, b in _notes(vault, "Projects", "project")
                if f.get("status") == "active"]
    print(f"\n## Active projects ({len(projects)})")
    for rel, fm, body in projects:
        print(f"- [[{rel[:-3]}]] — {_title(rel, body)} (area: {fm.get('area')})")
    tasks = [(r, f, b) for r, f, b in _notes(vault, "Tasks", "task")
             if f.get("status") == "this-week" and mine(f)]
    print(f"\n## This-week tasks ({len(tasks)})")
    for rel, fm, body in tasks:
        print(_task_line(rel, fm, body))


def cmd_waiting_on(vault, args):
    fus = [(r, f, b) for r, f, b in _notes(vault, "Follow-ups", "followup")
           if f.get("status") == "waiting"]
    print(f"# Waiting on\n\n## Open follow-ups ({len(fus)})")
    for rel, fm, body in fus:
        print(f"- [[Follow-ups/{Path(rel).stem}]] — {fm.get('who')} re: "
              f"{fm.get('about')} (opened {fm.get('opened')})")
    # Action items OTHER people owe — captured as tasks with owner != the vault owner so
    # they never pollute the backlog, but they are still things the owner is waiting
    # on and belong in the one-shot answer.
    owed = [(r, f, b) for r, f, b in _notes(vault, "Tasks", "task")
            if not mine(f) and f.get("status") != "done"]
    print(f"\n## Action items owed by others ({len(owed)})")
    for rel, fm, body in owed:
        print(f"- {_owner_name(fm)}: [[Tasks/{Path(rel).stem}]] — "
              f"{_title(rel, body)} (source: {fm.get('source') or '—'})")
    if not owed:
        print("- (none)")
    print("\n## Waiting On lines in recent daily notes")
    dailies = sorted(_notes(vault, "Daily", "daily"), reverse=True)[:14]
    any_line = False
    for rel, fm, body in dailies:
        sec = section_text(body, "Waiting On")
        lines = [l for l in sec.splitlines()
                 if l.strip().startswith("-") and l.strip() not in ("-", "- [ ]")]
        for l in lines:
            print(f"- {Path(rel).stem}: {l.strip().lstrip('- ').strip()}")
            any_line = True
    if not any_line:
        print("- (none)")


def cmd_today(vault, args):
    d = today().isoformat()
    rel = f"Daily/{d}.md"
    print(f"# Today — {d} ({iso_week()})")
    p = vault / rel
    if p.exists():
        _, body = fmyaml.parse(p.read_text(encoding="utf-8"))
        print(f"\n## Daily note ({rel})\n")
        print(body.strip())
    else:
        print(f"\n## Daily note\n\n(none yet — {rel} does not exist)")
    tasks = [(r, f, b) for r, f, b in _notes(vault, "Tasks", "task")
             if f.get("status") == "this-week" and mine(f)]
    print(f"\n## This-week tasks ({len(tasks)})")
    for r, f, b in tasks:
        print(_task_line(r, f, b))


def cmd_person(vault, args):
    name = args.name
    stem = resolve_stem(name, people_stems(vault))
    rel = f"People/{stem}.md" if stem else None
    if rel is None:
        print(f"# {name}\n\nNo People note found for '{name}'.")
        return
    fm, body = fmyaml.parse((vault / rel).read_text(encoding="utf-8"))
    stem = Path(rel).stem
    print(f"# {_title(rel, body)} ([[{rel[:-3]}]])\n")
    show = lambda k: fm.get(k) or "—"
    print(f"- org: {show('org')}  role: {show('role')}  email: {show('email')}")
    print(f"\n## Note body\n\n{body.strip()}")
    print("\n## Mentions")
    pat = re.compile(r"\[\[People/" + re.escape(stem) + r"(\]\]|\|)")
    hits = []
    for r in vault_files(vault):
        if r == rel:
            continue
        text = (vault / r).read_text(encoding="utf-8")
        if pat.search(text):
            hits.append(r)
    for h in hits:
        print(f"- [[{h[:-3]}]]")
    if not hits:
        print("- (none)")


def _project_notes(vault):
    return _notes(vault, "Projects", "project")


def cmd_project(vault, args):
    """One-shot project status: note fm + body + its tasks + recent meetings."""
    want = slugify(args.name)
    projects = _project_notes(vault)
    exact = [(r, f, b) for r, f, b in projects if Path(r).stem == want]
    matches = exact or [(r, f, b) for r, f, b in projects
                        if want in Path(r).stem or Path(r).stem in want]
    if not matches:
        print(f"# Project '{args.name}'\n\nNo project note matches '{want}'.")
        print("\n## All projects")
        for r, f, b in projects:
            print(f"- [[{r[:-3]}]] ({f.get('status')})")
        return
    if len(matches) > 1:
        print(f"# Project '{args.name}' — {len(matches)} matches\n")
        for r, f, b in matches:
            print(f"- [[{r[:-3]}]] — {_title(r, b)} (status: {f.get('status')}, "
                  f"area: {f.get('area')})")
        return
    rel, fm, body = matches[0]
    slug = Path(rel).stem
    print(f"# {_title(rel, body)} ([[{rel[:-3]}]])\n")
    print(f"- status: {fm.get('status')}  area: {fm.get('area')}")
    print(f"\n## Note body\n\n{body.strip()}")
    tasks = [(r, f, b) for r, f, b in _notes(vault, "Tasks", "task")
             if f.get("project") == slug and f.get("status") != "done"]
    print(f"\n## Open tasks ({len(tasks)})")
    for r, f, b in tasks:
        print(f"- [{f.get('status')}] " + _task_line(r, f, b)[2:])
    meetings = [(r, f, b) for r, f, b in _notes(vault, "Meetings", "meeting")
                if f.get("project") == slug]
    meetings.sort(key=lambda m: (str(m[1].get("date", "")), m[0]), reverse=True)
    print(f"\n## Meetings ({len(meetings)}, newest first)")
    for r, f, b in meetings[:10]:
        print(f"- {f.get('date')} [[{r[:-3]}]] — {_title(r, b)}")
    repos = sorted(((r, f, b) for r, f, b in _repo_notes(vault)
                    if f.get("project") == slug), key=lambda x: Path(x[0]).stem)
    print(f"\n## Repos ({len(repos)})")
    for r, f, b in repos:
        last = _last_log_line(b)
        print(f"- [[{r[:-3]}]] — {_title(r, b)} (role: {f.get('role') or '—'}; "
              f"status: {f.get('status')})" + (f" — last: {last}" if last else ""))
    if not repos:
        print("- (none)")


def cmd_meetings(vault, args):
    meetings = _notes(vault, "Meetings", "meeting")
    if args.since:
        args.since = parse_date(args.since, "--since")
        meetings = [m for m in meetings if str(m[1].get("date", "")) >= args.since]
    if getattr(args, "until", None):
        until = parse_date(args.until, "--until")
        meetings = [m for m in meetings if str(m[1].get("date", "")) <= until]
    if getattr(args, "project", None):
        meetings = [m for m in meetings if m[1].get("project") == args.project]
    if getattr(args, "attendee", None):
        meetings = [m for m in meetings
                    if _person_in(m[1].get("attendees") or [], args.attendee,
                                  people_stems(vault))]
    meetings.sort(key=lambda m: (str(m[1].get("date", "")), m[0]), reverse=True)
    print(f"# Meetings ({len(meetings)})")
    for rel, fm, body in meetings:
        att = ", ".join(fm.get("attendees") or [])
        proj = fm.get("project") or "—"
        print(f"- {fm.get('date')} [[{rel[:-3]}]] — {_title(rel, body)} "
              f"(project: {proj}; attendees: {att or '—'})")


def cmd_notes(vault, args):
    """Reference/ and Content/ notes. One match prints the whole note, so the
    answer needs no follow-up read. Title matches win over body matches."""
    notes = []
    if args.folder in (None, "Reference") and not args.status:
        notes += _notes(vault, "Reference", "reference")
    if args.folder in (None, "Content"):
        notes += _notes(vault, "Content", "content")
    if args.status:
        notes = [n for n in notes if n[1].get("status") == args.status]
    toks = [t for t in slugify(args.text or "").split("-") if t]
    if toks:
        hits = [n for n in notes if _mentions_project(n[0], n[2], toks)]
        if not hits:
            hits = [n for n in notes if all(t in n[2].lower() for t in toks)]
    else:
        hits = notes
    if len(hits) == 1 and toks:
        rel, fm, body = hits[0]
        print(f"# {_title(rel, body)} ([[{rel[:-3]}]])\n")
        status = f"  status: {fm['status']}" if fm.get("status") else ""
        print(f"- type: {fm.get('type')}  created: {fm.get('created') or '—'}{status}")
        print(f"\n## Note body\n\n{body.strip()}")
        return
    label = f" matching '{args.text}'" if toks else ""
    print(f"# Notes{label} ({len(hits)})")
    for rel, fm, body in sorted(hits):
        status = f" [{fm['status']}]" if fm.get("status") else ""
        print(f"- [[{rel[:-3]}]] — {_title(rel, body)}{status}")
    if toks and not hits:
        print(f"\nNo Reference or Content note matches '{args.text}'.")
        print(f"\n## All notes ({len(notes)})")
        for rel, fm, body in sorted(notes):
            print(f"- [[{rel[:-3]}]] — {_title(rel, body)}")


def _person_in(links, name, stems):
    """True when `name` (resolved like every other person lookup) is one of
    the People wikilinks in `links`."""
    stem = resolve_stem(name, stems)
    if stem:
        return f"[[People/{stem}]]" in links
    want = slugify(name)
    return any(want in slugify(l) for l in links)


def _since_until(args):
    since = parse_date(args.since, "--since") if getattr(args, "since", None) else None
    until = parse_date(args.until, "--until") if getattr(args, "until", None) else None
    return since, until


def _in_range(day, since, until):
    day = str(day or "")
    return (not since or day >= since) and (not until or day <= until)


def _field(fm, key):
    v = fm.get(key)
    if isinstance(v, list):
        v = ", ".join(v)
    return v if v not in (None, "", []) else "\u2014"


def cmd_show(vault, args):
    """Print one note in full: title, its fields, then the body."""
    ref = clean_ref(args.link)
    files = vault_files(vault)
    rel = ref + ".md"
    if rel not in files:
        hits = [f for f in files if Path(f).stem == Path(ref).stem
                and ("/" not in ref or f.startswith(ref.split("/")[0] + "/"))]
        if len(hits) > 1:
            die(f"'{args.link}' matches {len(hits)} notes: "
                + ", ".join(h[:-3] for h in hits) + ". Use Folder/stem.")
        if not hits:
            die(f"no such note: '{args.link}'. Use a Folder/stem printed by a "
                "query command.")
        rel = hits[0]
    fm, body = fmyaml.parse((vault / rel).read_text(encoding="utf-8"))
    print(f"# {_title(rel, body)} ([[{rel[:-3]}]])\n")
    ntype = fm.get("type")
    print(f"- type: {ntype}  created: {_field(fm, 'created')}")
    extra = [k for k in ("week",) if k in fm]
    for key in REQUIRED.get(ntype, []) + extra:
        print(f"- {key}: {_field(fm, key)}")
    print(f"\n## Note body\n\n{body.strip()}")


def cmd_projects(vault, args):
    projects = [(r, f, b) for r, f, b in _notes(vault, "Projects", "project")
                if args.status in ("all", f.get("status"))
                and (not args.area or f.get("area") == args.area)]
    tasks = _notes(vault, "Tasks", "task")
    print(f"# Projects ({len(projects)})")
    for status in ("active", "paused", "done"):
        grp = sorted(p for p in projects if p[1].get("status") == status)
        if not grp:
            continue
        print(f"\n## {status} ({len(grp)})")
        for rel, fm, body in grp:
            slug = Path(rel).stem
            open_n = sum(1 for t in tasks if t[1].get("project") == slug
                         and t[1].get("status") != "done")
            print(f"- [[{rel[:-3]}]] \u2014 {_title(rel, body)} "
                  f"(area: {fm.get('area')}; open tasks: {open_n})")
    if not projects:
        print("- (none)")


def _repo_notes(vault):
    return _notes(vault, "Repos", "repo")


def _last_log_line(body):
    """Most recent `## Activity Log` entry (dated lines are appended in
    chronological order, so the last one is the newest), or None."""
    lines = [l.strip() for l in section_text(body, "Activity Log").splitlines()
             if l.strip().startswith("-")]
    return lines[-1][2:].strip() if lines else None


def _repo_known_list(vault):
    out = []
    for r, f, b in sorted(_repo_notes(vault)):
        out.append(f"[[Repos/{Path(r).stem}]] (project: {f.get('project')}, "
                   f"status: {f.get('status')}, path: {f.get('path') or '—'})")
    return out


def _detect_cwd_repo(vault):
    """cwd -> ([(rel, fm, body), ...], stage_name). Three ordered stages —
    path, git remote, directory basename — each stage's own hits decide the
    outcome: ambiguity at a stage is terminal and never falls through to a
    weaker later signal. ([], None) when nothing matches anywhere."""
    cwd = Path.cwd().resolve()
    repos = _repo_notes(vault)

    by_path = [r for r in repos if r[1].get("path")
               and Path(r[1]["path"]).expanduser().resolve() == cwd]
    if by_path:
        return by_path, "path"

    remote = git_remote_url(cwd)
    if remote:
        norm = normalize_remote(remote)
        by_remote = [r for r in repos if r[1].get("remote")
                     and normalize_remote(r[1]["remote"]) == norm]
        if by_remote:
            return by_remote, "git remote"

    base = slugify(cwd.name)
    by_name = [r for r in repos if base and slugify(_title(r[0], r[2])) == base]
    if by_name:
        return by_name, "directory name"

    return [], None


def cmd_repo(vault, args):
    """One-shot repo status: note fm + body, its project's context, and its
    sibling repos in the same project (what else is going on in this
    project). With no name, auto-detects the repo from the current directory
    (`_detect_cwd_repo`) instead of requiring it to be typed every time."""
    repos = _repo_notes(vault)
    name = getattr(args, "name", None)
    if name:
        want = slugify(name)
        exact = [(r, f, b) for r, f, b in repos
                 if Path(r).stem == want or slugify(_title(r, b)) == want]
        matches = exact or [(r, f, b) for r, f, b in repos
                            if want in Path(r).stem or Path(r).stem in want]
        if not matches:
            print(f"# Repo '{name}'\n\nNo repo note matches '{want}'.")
            print("\n## All repos")
            for line in _repo_known_list(vault):
                print(f"- {line}")
            return
        if len(matches) > 1:
            print(f"# Repo '{name}' — {len(matches)} matches\n")
            for r, f, b in matches:
                print(f"- [[{r[:-3]}]] — {_title(r, b)} (project: "
                      f"{f.get('project')}, status: {f.get('status')})")
            return
        rel, fm, body = matches[0]
    else:
        hits, stage = _detect_cwd_repo(vault)
        if not hits:
            print(f"# Repo (auto-detect)\n\nNo repo note matches the current "
                  f"directory ({Path.cwd()}).")
            print("\nPass the name explicitly, or register this directory "
                  "with `brain capture repo --name NAME --project SLUG`.")
            print("\n## Known repos")
            for line in _repo_known_list(vault):
                print(f"- {line}")
            return
        if len(hits) > 1:
            print(f"# Repo (auto-detect) — {len(hits)} repos share the same "
                  f"{stage} as the current directory\n")
            for r, f, b in hits:
                print(f"- [[{r[:-3]}]] — {_title(r, b)} (project: {f.get('project')})")
            print("\nPass the name explicitly.")
            return
        rel, fm, body = hits[0]

    slug = Path(rel).stem
    project_slug = fm.get("project")
    print(f"# {_title(rel, body)} ([[{rel[:-3]}]])\n")
    print(f"- project: {project_slug}  role: {fm.get('role') or '—'}  "
          f"status: {fm.get('status')}")
    print(f"\n## Note body\n\n{body.strip()}")

    proj = next(((r, f, b) for r, f, b in _project_notes(vault)
                 if Path(r).stem == project_slug), None)
    if proj:
        pr, pf, pb = proj
        ctx = section_text(pb, "Context").strip()
        print(f"\n## Project context ([[{pr[:-3]}]])\n")
        print(ctx or "(no context yet)")

    siblings = sorted((r for r in repos
                       if r[1].get("project") == project_slug
                       and Path(r[0]).stem != slug),
                      key=lambda r: Path(r[0]).stem)
    print(f"\n## Other repos in this project ({len(siblings)})")
    for r, f, b in siblings:
        last = _last_log_line(b)
        print(f"- [[{r[:-3]}]] — {_title(r, b)} (role: {f.get('role') or '—'}; "
              f"status: {f.get('status')})" + (f" — last: {last}" if last else ""))
    if not siblings:
        print("- (none)")


def cmd_repos(vault, args):
    repos = [(r, f, b) for r, f, b in _repo_notes(vault)
             if args.status in ("all", f.get("status"))
             and (not args.project or f.get("project") == args.project)]
    print(f"# Repos ({len(repos)})")
    for status in ("active", "archived"):
        grp = sorted((r for r in repos if r[1].get("status") == status),
                     key=lambda r: Path(r[0]).stem)
        if not grp:
            continue
        print(f"\n## {status} ({len(grp)})")
        for rel, fm, body in grp:
            last = _last_log_line(body)
            print(f"- [[{rel[:-3]}]] — {_title(rel, body)} (project: "
                  f"{fm.get('project')}; role: {fm.get('role') or '—'})"
                  + (f" — last: {last}" if last else ""))
    if not repos:
        print("- (none)")


def cmd_followups(vault, args):
    fus = _notes(vault, "Follow-ups", "followup")
    if args.status != "all":
        fus = [f for f in fus if f[1].get("status") == args.status]
    if args.who:
        stems = people_stems(vault)
        fus = [f for f in fus if _person_in([f[1].get("who") or ""], args.who, stems)]
    fus.sort(key=lambda f: (str(f[1].get("opened", "")), f[0]), reverse=True)
    label = {"waiting": "open", "done": "closed", "all": "all"}[args.status]
    print(f"# Follow-ups, {label} ({len(fus)})")
    for rel, fm, body in fus:
        state = f" [{fm.get('status')}]" if args.status == "all" else ""
        print(f"-{state} [[{rel[:-3]}]] \u2014 {fm.get('who')} re: {fm.get('about')} "
              f"(opened {fm.get('opened')})")
    if not fus:
        print("- (none)")


def cmd_interviews(vault, args):
    items = _notes(vault, "Interviews", "interview")
    since = parse_date(args.since, "--since") if args.since else None
    if args.verdict:
        items = [i for i in items if i[1].get("verdict") == args.verdict]
    if args.candidate:
        want = slugify(args.candidate)
        items = [i for i in items if want in slugify(str(i[1].get("candidate")))]
    if args.role:
        toks = [t for t in slugify(args.role).split("-") if t]
        items = [i for i in items
                 if all(t in slugify(str(i[1].get("role"))) for t in toks)]
    items = [i for i in items if _in_range(i[1].get("date"), since, None)]
    items.sort(key=lambda i: (str(i[1].get("date", "")), i[0]), reverse=True)
    print(f"# Interviews ({len(items)})")
    for rel, fm, body in items:
        print(f"- {fm.get('date')} [[{rel[:-3]}]] \u2014 {fm.get('candidate')}, "
              f"{fm.get('role')} (round {fm.get('round')}; verdict: {fm.get('verdict')})")
    if not items:
        print("- (none)")


def cmd_people(vault, args):
    people = _notes(vault, "People", "person")
    if args.org:
        people = [p for p in people if p[1].get("org") == args.org]
    if args.text:
        toks = [t for t in slugify(args.text).split("-") if t]
        people = [p for p in people
                  if all(t in slugify(Path(p[0]).stem + " " + str(p[1].get("role") or ""))
                         for t in toks)]
    print(f"# People ({len(people)})")
    for rel, fm, body in sorted(people):
        print(f"- [[{rel[:-3]}]] \u2014 {_title(rel, body)} "
              f"(org: {_field(fm, 'org')}; role: {_field(fm, 'role')})")
    if not people:
        print("- (none)")


def _bullets_in(body, section):
    return sum(1 for l in section_text(body, section).splitlines()
               if l.strip().startswith("-") and l.strip() not in ("-", "- [ ]"))


def cmd_dailies(vault, args):
    since, until = _since_until(args)
    days = [d for d in _notes(vault, "Daily", "daily")
            if _in_range(Path(d[0]).stem, since, until)]
    days.sort(reverse=True)
    print(f"# Daily notes ({len(days)})")
    for rel, fm, body in days:
        counts = ", ".join(f"{label}: {_bullets_in(body, sec)}" for label, sec in
                           (("meetings", "Meetings"), ("priority", "Priority Tasks"),
                            ("waiting", "Waiting On"), ("log", "Work Log"),
                            ("dump", "Brain Dump")))
        print(f"- [[{rel[:-3]}]] \u2014 {counts}")
    if not days:
        print("- (none)")


def cmd_transcripts(vault, args):
    since, _ = _since_until(args)
    items = [t for t in _notes(vault, "Transcripts", "transcript")
             if _in_range(t[1].get("created"), since, None)]
    items.sort(key=lambda t: (str(t[1].get("created", "")), t[0]), reverse=True)
    print(f"# Transcripts ({len(items)})")
    for rel, fm, body in items:
        m = re.search(r"^\*\*(?:Meeting|Interview):\*\* (\[\[[^\]]+\]\])", body, re.M)
        source = m.group(1) if m else "\u2014"
        print(f"- {fm.get('created')} [[{rel[:-3]}]] \u2014 {_title(rel, body)} "
              f"(source: {source})")
    if not items:
        print("- (none)")


def _fold(text):
    """Lowercase and strip accents, matching how search words are slugified."""
    folded = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return folded.lower().replace("'", "")


def cmd_search(vault, args):
    toks = [t for t in slugify(args.text).split("-") if t]
    if not toks:
        die("search needs at least one word with letters or digits.")
    since = parse_date(args.since, "--since") if args.since else None
    title_hits, body_hits = [], []
    for rel, fm, body in _notes(vault, None, args.type):
        day = fm.get("date") or fm.get("opened") or fm.get("created")
        if not _in_range(day, since, None):
            continue
        title = _title(rel, body)
        head = slugify(Path(rel).stem + " " + title)
        text = _fold(body)
        if all(t in head for t in toks):
            title_hits.append((rel, title, body))
        elif all(t in text or t in head for t in toks):
            body_hits.append((rel, title, body))
    hits = sorted(title_hits) + sorted(body_hits)
    print(f"# Search '{args.text}' ({len(hits)})")
    for rel, title, body in hits:
        line = next((l.strip() for l in body.splitlines()
                     if l.strip() and not l.startswith("#")
                     and any(t in _fold(l) for t in toks)), "")
        snippet = f" \u2014 {line[:120]}" if line else ""
        print(f"- [[{rel[:-3]}]] \u2014 {title}{snippet}")
    if not hits:
        print("- (none)")
