"""capture / promote / done commands — all built on writer.Plan."""

import re
import sys
from pathlib import Path

from .core import (die, default_org, iso_week, owner_link, owner_name, parse_date,
                   parse_week, person_filename, require_slug, self_words,
                   slug_key, slugify, today, wikilink_target)
from .people import AmbiguousPerson, people_stems, resolve_stem
from .projects import active_project_slugs, project_rels, require_project_slug
from .repos import git_remote_url
from .body import sync_meta
from .writer import Plan, ensure_line_in_section, render


def infer_project(plan, text):
    """Deterministic project inference: the model never picks a slug.
    Count how many words (2+ letters) of each ACTIVE project slug appear in
    `text`; the single slug with the strictly highest nonzero count wins, a tie
    or a zero yields None. Same input text -> same project, every session."""
    if not text:
        return None
    words = {w for w in slugify(text).split("-") if w}
    best, best_n, tied = None, 0, False
    for slug in sorted(active_project_slugs(plan.vault)):
        toks = [t for t in slug.split("-") if len(t) >= 2]
        if not toks:
            continue
        n = sum(1 for t in toks if t in words)
        if n > best_n:
            best, best_n, tied = slug, n, False
        elif n == best_n and n > 0:
            tied = True
    return None if (best_n == 0 or tied) else best


def note(text):
    """A deterministic hint on stderr: capture merges and never overwrites, so
    say so when a value the caller passed was not applied."""
    print(f"NOTE: {text}", file=sys.stderr)


def _base_fm(ntype, created):
    """Every note: type/schema/created/tags. The H1 in the body is the title,
    so there is no frontmatter title. See core.COMMON."""
    return {"type": ntype, "schema": "1", "created": created, "tags": [ntype]}


def _bullets(items):
    """Repeatable free-text flags -> a markdown bullet block ('' when none)."""
    return "\n".join(f"- {s.strip()}" for s in (items or []) if s.strip())


def _read_file(path, what):
    try:
        return Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        print(f"ERROR: cannot read {what} '{path}': {exc.strerror or exc}. "
              "Nothing was written.", file=sys.stderr)
        sys.exit(2)


def _read_optional(path_flag, stdin_flag, what="file"):
    if stdin_flag:
        return sys.stdin.read().strip()
    if path_flag:
        return _read_file(path_flag, what).strip()
    return None


def person_meta(org, role, email, seen):
    """Body meta block for a People note. A person stub must never be an empty
    file (a note with perfect structure and no content is useless), so whatever
    we know — org, job title, email, where we first met them — goes in the body
    as well as the frontmatter."""
    lines = []
    if role:
        lines.append(f"**Role:** {role.strip()}")
    if org:
        lines.append(f"**Org:** {org}")
    if email:
        lines.append(f"**Email:** {email.strip()}")
    if seen:
        lines.append(f"**First seen:** {seen}")
    return "\n".join(lines)


def flatten_headings(text):
    """A captured note's prose lives inside ONE wrapper section (`## Draft`,
    `## Notes`). Headings the author put inside that prose would close the
    wrapper and leave it empty, so they become bold lead-ins instead — every
    word is kept, the document outline stays H1 > wrapper, and the section a
    reader (or a check) opens actually contains the note."""
    out = []
    for line in (text or "").split("\n"):
        m = re.match(r"^\s{0,3}#{1,6}\s+(.*?)\s*#*\s*$", line)
        out.append(f"**{m.group(1).strip()}**" if m and m.group(1).strip() else line)
    return "\n".join(out)


def _merge_meta(body, meta):
    """Add any missing `**Label:** value` line directly under the H1."""
    if not meta:
        return body
    lines = body.split("\n")
    missing = [l for l in meta.split("\n")
               if l and l.split(":**")[0] + ":**" not in body]
    if not missing:
        return body
    at = 1 if lines and lines[0].startswith("# ") else 0
    while at < len(lines) and not lines[at].strip():
        at += 1
    return "\n".join(lines[:at] + missing + [""] + lines[at:])


def ensure_person(plan, name, org=None, role=None, email=None, seen=None):
    """Resolve to an existing People note (same fuzzy rule as `query person`)
    or create a stub. Returns People/<Stem> rel target.
    `seen` is a wikilink to the note this person first showed up in."""
    stems = set(people_stems(plan.vault))
    stems |= {Path(r).stem for r in plan.pending if r.startswith("People/")}
    try:
        resolved = resolve_stem(name, stems, strict=True)
    except AmbiguousPerson as exc:
        cands = ", ".join(f"People/{c}" for c in exc.candidates)
        print(f"ERROR: '{exc.name}' matches {len(exc.candidates)} existing people: "
              f"{cands}. Re-run with the full name so the note links the right "
              f"person — creating a second note for one human splits their "
              f"backlinks. Nothing was written.", file=sys.stderr)
        sys.exit(2)
    if resolved:
        rel = f"People/{resolved}.md"
        existing = plan.load(rel)
        if existing is not None and (org or role or email):
            fm, body = existing
            changed = set()
            if org:
                fm["org"] = org
                changed.add("org")
            for key, val in (("role", role), ("email", email)):
                if not val:
                    continue
                if not fm.get(key):
                    fm[key] = val
                    changed.add(key)
                elif fm[key] != val.strip():
                    note(f"{rel} keeps {key}={fm[key]!r}; to change it run: "
                         f"brain set person {resolved} --{key} \"{val}\"")
            body = sync_meta("person", fm, body, fields=changed)
            plan.put(rel, fm, body)
        elif rel not in plan.pending:
            plan.linked.add(rel)
        return f"People/{resolved}"

    fname = person_filename(name)
    rel = f"People/{fname}.md"
    fm = _base_fm("person", today().isoformat())
    fm.update({"org": org or default_org(plan.mode, email),
               "role": role, "email": email})
    body = render("person", {
        "name": name.strip(),
        "meta": person_meta(fm["org"], role, email, seen)}, prune=True)
    plan.put(rel, fm, body)
    return f"People/{fname}"


def note_seen(plan, person_target, link):
    """Record provenance on a person note WE are creating in this same plan
    (never on one that already existed — that would widen the artifact set)."""
    rel = f"{person_target}.md"
    if rel not in plan.pending:
        return
    fm, body = plan.pending[rel]
    if "**First seen:**" in body:
        return
    plan.put(rel, fm, _merge_meta(body, f"**First seen:** {link}"))


def ensure_daily(plan, date, section, line):
    """A daily note always gets the full template body, so every daily has the
    same sections. A daily that would end up with no lines at all is dropped in
    Plan.execute()."""
    rel = f"Daily/{date}.md"
    existing = plan.load(rel)
    if existing is None:
        fm = _base_fm("daily", date)
        body = render("daily", {"date": date})
    else:
        fm, body = existing
    body = ensure_line_in_section(body, section, line)
    plan.put(rel, fm, body)


def resolve_owner(plan, owner):
    """--owner NAME -> '[[People/Stem]]', creating the stub if needed.
    Unset (or 'me') means the vault owner. Every task carries one: `owner` is
    required so other people's action items never pollute the backlog."""
    name = (owner or owner_name()).strip()
    if name.lower() in self_words():
        name = owner_name()
    return f"[[{ensure_person(plan, name)}]]"


def make_task(plan, desc, area, priority, project, source, date,
              owner=None, context=None, explicit=False):
    project = project or infer_project(plan, desc)
    owner_link = resolve_owner(plan, owner)
    slug = f"{area}-{require_slug(slug_key(desc, 4), '--desc', desc)}"
    rel = f"Tasks/{slug}.md"
    existing = plan.load(rel)
    if existing is None:
        fm = _base_fm("task", date)
        fm.update({"status": "backlog", "owner": owner_link,
                   "project": project or None,
                   "area": area, "priority": priority or "medium",
                   "source": source or None})
        # Body carries the SOURCE CONTEXT, never a repeat of the title.
        body = render("task", {
            "title": desc.strip(), "owner_link": owner_link,
            "source_display": source or "—",
            "context": (context or "").strip()}, prune=True)
        plan.put(rel, fm, body)
        note_seen(plan, owner_link.strip("[]"), f"[[Tasks/{slug}]]")
    else:
        # Phrasing variants share a slug on purpose, so this request is the
        # existing task. Never drop what the user said without saying so: an
        # explicit priority is applied, and different wording is reported.
        fm, body = existing
        if priority and fm.get("priority") != priority:
            fm["priority"] = priority
        if explicit:
            for key, val in (("project", project), ("owner", owner_link)):
                if val and fm.get(key) not in (None, "", val):
                    note(f"{rel} keeps {key}={fm[key]}; to change it run: "
                         f"brain set task {slug} --{key} "
                         f"{str(val).strip('[]').split('/')[-1]}")
        title = next((l[2:].strip() for l in body.split("\n")
                      if l.startswith("# ")), "")
        if slug_key(title, None) != slug_key(desc, None):
            plan.notice(rel, f'same task as "{title}"; not added as a new '
                             f'task: "{desc.strip()}"')
        if fm.get("project") in (None, "") and project:
            fm["project"] = project
        if fm.get("source") in (None, "") and source:
            fm["source"] = source
        if fm.get("owner") in (None, ""):
            fm["owner"] = owner_link
        plan.put(rel, fm, body)
    return slug


_TOPIC_STOP = {"a", "an", "the", "for", "of", "on", "to", "and", "with", "re",
               "about", "from", "in", "at", "by", "follow", "up", "followup"}


def _topic_tokens(about):
    return [t for t in slugify(about).split("-") if t and t not in _TOPIC_STOP]


def _find_followup(plan, who_target, about):
    """Dedupe by (who, topic): same who + one topic token-set contains the
    other. Returns rel of the lexicographically first match, else None."""
    new_toks = set(_topic_tokens(about))
    d = plan.vault / "Follow-ups"
    rels = sorted(f"Follow-ups/{f.name}" for f in d.glob("*.md")) if d.is_dir() else []
    rels += sorted(r for r in plan.pending if r.startswith("Follow-ups/"))
    for rel in sorted(set(rels)):
        fm, body = plan.load(rel)
        if wikilink_target(fm.get("who") or "") != who_target:
            continue
        old_toks = set(_topic_tokens(str(fm.get("about") or "")))
        if not old_toks or not new_toks:
            continue
        if old_toks <= new_toks or new_toks <= old_toks:
            return rel
    return None


def make_followup(plan, who, about, date):
    who_target = ensure_person(plan, who)
    existing_rel = _find_followup(plan, who_target, about)
    if existing_rel:
        fm, body = plan.load(existing_rel)
        if fm.get("status") == "done":  # re-raised -> reopen
            fm["status"] = "waiting"
            fm["opened"] = date
        plan.put(existing_rel, fm, body)  # prints UPDATED or UNCHANGED
        return Path(existing_rel).stem
    topic = require_slug("-".join(_topic_tokens(about)[:4]) or slug_key(about, 4),
                         "--about", about)
    slug = f"{slugify(who.split()[0])}-{topic}"
    rel = f"Follow-ups/{slug}.md"
    title = f"{who.strip()} — {about.strip()}"
    fm = _base_fm("followup", date)
    fm.update({"who": f"[[{who_target}]]", "about": about.strip(),
               "opened": date, "status": "waiting"})
    body = render("followup", {
        "title": title, "who_link": f"[[{who_target}]]",
        "about": about.strip()}, prune=True)
    plan.put(rel, fm, body)
    note_seen(plan, who_target, f"[[Follow-ups/{slug}]]")
    return slug


def _task_spec(spec):
    """'desc|area|priority|owner' -> (desc, area, priority, owner). Only the
    first field is required; the rest default. An omitted priority stays
    None so it never overrides an existing task's priority."""
    parts = [p.strip() for p in spec.split("|")]
    desc = parts[0]
    area = parts[1] if len(parts) > 1 and parts[1] else "internal"
    prio = parts[2] if len(parts) > 2 and parts[2] else None
    owner = parts[3] if len(parts) > 3 and parts[3] else None
    return desc, area, prio, owner


def cmd_capture_meeting(ctx, mode, args):
    date = parse_date(args.date) if args.date else today().isoformat()
    # A meeting note built from a source must carry prose, not empty headings.
    if args.transcript_file and not (args.summary_file or args.summary_stdin):
        print("ERROR: --transcript-file requires --summary-file (or "
              "--summary-stdin). A meeting note built from a source must carry a "
              "3-6 bullet summary; pass --decision \"...\" for each literal "
              "decision too. Nothing was written.", file=sys.stderr)
        sys.exit(2)
    plan = Plan(ctx, mode)
    if not args.project:
        args.project = infer_project(plan, args.title)
    slug = require_slug(slug_key(args.title, 6), "--title", args.title)
    meeting_rel = f"Meetings/{slug}-{date}.md"
    meeting_target = f"Meetings/{slug}-{date}"

    attendees = []
    if args.attendees:
        names = [n.strip() for n in args.attendees.split(",") if n.strip()]
        for n in sorted(names, key=str.lower):
            attendees.append(
                f"[[{ensure_person(plan, n, seen=f'[[{meeting_target}]]')}]]")
    attendees = sorted(set(attendees))

    transcript_link = None
    if args.transcript_file:
        t_rel = f"Transcripts/{slug}-{date}-transcript.md"
        t_body = _read_file(args.transcript_file, "--transcript-file").strip()
        t_fm = _base_fm("transcript", date)
        body = render("transcript", {
            "title": args.title.strip(),
            "meeting_line": f"**Meeting:** [[{meeting_target}]]",
            "transcript_body": t_body})
        if plan.load(t_rel) is None:
            plan.put(t_rel, t_fm, body)
        transcript_link = f"[[Transcripts/{slug}-{date}-transcript]]"

    summary = _read_optional(args.summary_file, args.summary_stdin, "--summary-file")
    decisions = _bullets(args.decision)

    task_links, followup_links = [], []
    for spec in args.task or []:
        desc, area, prio, owner = _task_spec(spec)
        tslug = make_task(plan, desc, area, prio, args.project,
                          f"[[{meeting_target}]]", date, owner=owner)
        task_links.append(f"[[Tasks/{tslug}]]")
    for spec in args.followup or []:
        parts = [p.strip() for p in spec.split("|")]
        who, about = parts[0], parts[1] if len(parts) > 1 else "follow up"
        fslug = make_followup(plan, who, about, date)
        followup_links.append(f"[[Follow-ups/{fslug}]]")
        ensure_daily(plan, date, "Waiting On", f"- [[Follow-ups/{fslug}]]")

    existing = plan.load(meeting_rel)
    if existing is None:
        fm = _base_fm("meeting", date)
        fm.update({"date": date, "attendees": attendees,
                   "project": args.project or None,
                   "transcript": transcript_link})
        body = render("meeting", {
            "title": args.title.strip(), "date": date,
            "project_display": f"[[Projects/{args.project}]]" if args.project else "—",
            "attendees_display": ", ".join(attendees) or "—",
            "summary": summary or "", "decisions": decisions},
            prune=True, keep=("Action Items",))
    else:
        fm, body = existing
        fm["attendees"] = sorted(set(fm.get("attendees") or []) | set(attendees))
        # Keep the body's attendee line in step with the frontmatter.
        shown = ", ".join(fm["attendees"]) or "—"
        body = re.sub(r"(?m)^\*\*Attendees:\*\* .*$",
                      lambda _: f"**Attendees:** {shown}", body, count=1)
        if transcript_link:
            fm["transcript"] = transcript_link
        if args.project and not fm.get("project"):
            fm["project"] = args.project
        if summary and summary not in body:
            body = ensure_line_in_section(body, "Summary", summary)
        for d in decisions.split("\n") if decisions else []:
            body = ensure_line_in_section(body, "Decisions", d)

    for link in sorted(task_links):
        body = ensure_line_in_section(body, "Action Items", f"- [ ] {link}")
    for link in sorted(followup_links):
        body = ensure_line_in_section(body, "Action Items", f"- [ ] waiting: {link}")
    plan.put(meeting_rel, fm, body)

    ensure_daily(plan, date, "Meetings", f"- [[{meeting_target}]]")
    plan.execute()


def cmd_capture_interview(ctx, mode, args):
    date = parse_date(args.date) if args.date else today().isoformat()
    # An interview note built from a transcript must carry an assessment.
    if args.transcript_file and not (args.assessment_file or args.note):
        print("ERROR: --transcript-file requires --assessment-file (or one or "
              "more --note \"...\"). An interview note built from a source must "
              "carry the assessment; set --verdict when the source states an "
              "explicit recommendation. Nothing was written.", file=sys.stderr)
        sys.exit(2)
    plan = Plan(ctx, mode)
    cand_slug = require_slug(slugify(args.candidate), "--candidate", args.candidate)
    require_slug(slugify(args.role), "--role", args.role)
    rel = f"Interviews/{cand_slug}-{slugify(args.role)}-{date}.md"
    target = rel[:-3]
    cand_link = ensure_person(plan, args.candidate, org="external",
                              role=args.role.strip(), seen=f"[[{target}]]")
    notes = _bullets(args.note) or \
        _read_optional(args.summary_file, args.summary_stdin, "--summary-file") or ""
    assessment = _read_optional(args.assessment_file, False, "--assessment-file") or ""
    verdict = args.verdict or "pending"

    if args.transcript_file:
        t_rel = f"Transcripts/{cand_slug}-{slugify(args.role)}-{date}-transcript.md"
        t_body = _read_file(args.transcript_file, "--transcript-file").strip()
        if plan.load(t_rel) is None:
            plan.put(t_rel, _base_fm("transcript", date),
                     render("transcript", {
                         "title": f"{args.candidate} — {args.role}",
                         "meeting_line": f"**Interview:** [[{target}]]",
                         "transcript_body": t_body}))

    existing = plan.load(rel)
    if existing is None:
        fm = _base_fm("interview", date)
        fm.update({"candidate": args.candidate.strip(), "role": args.role.strip(),
                   "round": args.round.strip(), "date": date, "verdict": verdict})
        body = render("interview", {
            "candidate": args.candidate.strip(), "role": args.role.strip(),
            "candidate_link": f"[[{cand_link}]]",
            "round": args.round.strip(), "date": date, "verdict": verdict,
            "notes": notes, "assessment": assessment}, prune=True)
        plan.put(rel, fm, body)
    else:
        fm, body = existing
        if str(fm.get("round")) != args.round.strip():
            die(f"{rel} is round {fm.get('round')}, not round {args.round.strip()}. "
                "Use --date for a different day's interview, or change this "
                f"one with: brain set interview {Path(rel).stem} --round "
                f"{args.round.strip()}. Nothing was written.")
        if args.verdict:
            fm["verdict"] = verdict
            body = sync_meta("interview", fm, body, fields={"verdict"})
        if notes and notes not in body:
            body = ensure_line_in_section(body, "Notes During Interview", notes)
        if assessment and assessment not in body:
            body = ensure_line_in_section(body, "Assessment", assessment)
        plan.put(rel, fm, body)
    ensure_daily(plan, date, "Interviews", f"- [[{target}]]")
    plan.execute()


def cmd_capture_task(ctx, mode, args):
    date = today().isoformat()
    plan = Plan(ctx, mode)
    slug = make_task(plan, args.desc, args.area, args.priority, args.project,
                     args.source, date, owner=args.owner, context=args.context,
                     explicit=True)
    if getattr(args, "this_week", False):
        rel = f"Tasks/{slug}.md"
        fm, body = plan.load(rel)
        fm["status"] = "this-week"
        fm["week"] = iso_week()
        plan.put(rel, fm, body)
        ensure_daily(plan, date, "Priority Tasks", f"- [ ] [[Tasks/{slug}]]")
    else:
        ensure_daily(plan, date, "Brain Dump", f"- Captured task [[Tasks/{slug}]]")
    plan.execute()


def cmd_extract_tasks(ctx, mode, args):
    """Atomic tasks-only capture (e.g. action items mined from a transcript).
    Optionally stores the transcript note and uses it as each task's source.
    Use ONLY when the user asks for tasks and nothing else — a request that logs
    a meeting is always a single `capture meeting`."""
    date = parse_date(args.date) if args.date else today().isoformat()
    plan = Plan(ctx, mode)
    source = args.source
    if args.transcript_file:
        if not args.title:
            print("ERROR: --transcript-file requires --title", file=sys.stderr)
            sys.exit(2)
        slug = require_slug(slug_key(args.title, 6), "--title", args.title)
        t_rel = f"Transcripts/{slug}-{date}-transcript.md"
        t_body = _read_file(args.transcript_file, "--transcript-file").strip()
        if plan.load(t_rel) is None:
            plan.put(t_rel, _base_fm("transcript", date),
                     render("transcript", {
                         "title": args.title.strip(), "meeting_line": "",
                         "transcript_body": t_body}))
        source = f"[[Transcripts/{slug}-{date}-transcript]]"
    # Project inference must be IDENTICAL to the `capture meeting` path: infer
    # from the title first, so the same source yields the same provenance
    # whichever command the user's phrasing selected.
    project = args.project or (infer_project(plan, args.title) if args.title else None)
    for spec in args.task:
        desc, area, prio, owner = _task_spec(spec)
        tslug = make_task(plan, desc, area, prio, project, source, date,
                          owner=owner)
        ensure_daily(plan, date, "Brain Dump", f"- Captured task [[Tasks/{tslug}]]")
    plan.execute()


def cmd_capture_note(ctx, mode, args):
    date = today().isoformat()
    plan = Plan(ctx, mode)
    folder = args.folder or "Reference"
    if folder not in ("Reference", "Content"):
        print("ERROR: --folder must be Reference or Content", file=sys.stderr)
        sys.exit(2)
    if not args.body_file:
        print("ERROR: capture note requires --body-file. A title with no content "
              "is a useless note: write the prose to a file and pass it. "
              "Nothing was written.", file=sys.stderr)
        sys.exit(2)
    slug = require_slug(slug_key(args.title, 5), "--title", args.title)
    rel = f"{folder}/{slug}.md"
    body_text = flatten_headings(_read_file(args.body_file, "--body-file").strip())
    if not body_text.strip():
        print(f"ERROR: --body-file '{args.body_file}' is empty. Write the note's "
              "content to the file first, then pass it. Nothing was written.",
              file=sys.stderr)
        sys.exit(2)
    if plan.load(rel) is None:
        if folder == "Content":
            fm = _base_fm("content", date)
            fm["status"] = "draft"
            body = render("content", {"title": args.title.strip(),
                                      "body": body_text},
                          prune=True, keep=("Draft",))
        else:
            fm = _base_fm("reference", date)
            body = render("reference", {"title": args.title.strip(),
                                        "body": body_text},
                          prune=True, keep=("Notes",))
        plan.put(rel, fm, body)
    else:
        plan.touch(rel)
        note(f"{rel} already exists and was not changed; to add text run: "
             f"brain append {folder.lower()} {slug} --file <file>")
    plan.execute()


def cmd_capture_person(ctx, mode, args):
    plan = Plan(ctx, mode)
    ensure_person(plan, args.name, org=args.org, role=args.role, email=args.email)
    plan.execute()


def cmd_capture_project(ctx, mode, args):
    plan = Plan(ctx, mode)
    slug = require_slug(slug_key(args.name, 5), "--name", args.name)
    known = project_rels(plan.vault)
    if slug in known:
        rel = known[slug]
        plan.touch(rel)
        fm, _ = plan.load(rel)
        if args.area and args.area != fm.get("area"):
            note(f"{rel} keeps area={fm.get('area')}; to change it run: "
                 f"brain set project {slug} --area {args.area}")
        if args.context_file:
            note(f"{rel} already exists; its context was not changed. To add "
                 f"text run: brain append project {slug} --file {args.context_file}")
    else:
        fm = _base_fm("project", today().isoformat())
        fm.update({"status": "active", "area": args.area or "internal"})
        context = _read_file(args.context_file, "--context-file").strip() \
            if args.context_file else ""
        body = render("project", {"name": args.name.strip(),
                                  "context": flatten_headings(context)},
                      prune=True, keep=("Context", "Milestones"))
        plan.put(f"Projects/{slug}.md", fm, body)
    plan.execute()


def cmd_capture_repo(ctx, mode, args):
    """Register a repo under a project. Run from inside the repo's checkout
    with no --path/--remote and both default from cwd — the one-command
    affordance that makes `query repo` (no name) auto-detect it later."""
    plan = Plan(ctx, mode)
    project = require_project_slug(plan.vault, args.project.strip())
    name_slug = require_slug(slug_key(args.name, 5), "--name", args.name)
    slug = f"{project}-{name_slug}"
    rel = f"Repos/{slug}.md"
    role = args.role.strip() if args.role else None
    path = str(Path(args.path).expanduser().resolve()) if args.path else None
    remote = args.remote.strip() if args.remote else None

    existing = plan.load(rel)
    if existing is None:
        if path is None:
            path = str(Path.cwd().resolve())
        if remote is None:
            remote = git_remote_url(Path.cwd())
        fm = _base_fm("repo", today().isoformat())
        fm.update({"project": project, "status": args.status or "active",
                   "role": role, "path": path, "remote": remote})
        body = render("repo", {
            "name": args.name.strip(),
            "project_display": f"[[Projects/{project}]]",
            "role_display": role or "—",
            "purpose": flatten_headings((args.purpose or "").strip())})
        plan.put(rel, fm, body)
    else:
        fm, body = existing
        changed = set()
        if fm.get("project") != project:
            note(f"{rel} belongs to project={fm.get('project')}; to move it "
                 f"run: brain set repo {slug} --project {project}")
        if args.status and args.status != fm.get("status"):
            note(f"{rel} keeps status={fm.get('status')}; to change it run: "
                 f"brain set repo {slug} --status {args.status}")
        if role:
            if not fm.get("role"):
                fm["role"] = role
                changed.add("role")
            elif fm["role"] != role:
                note(f"{rel} keeps role={fm['role']!r}; to change it run: "
                     f"brain set repo {slug} --role \"{role}\"")
        filled = False
        if path and not fm.get("path"):
            fm["path"] = path
            filled = True
        if remote and not fm.get("remote"):
            fm["remote"] = remote
            filled = True
        if args.purpose:
            note(f"{rel} already exists; its purpose was not changed. To add "
                 f"text run: brain append repo {slug} --text \"...\"")
        if changed:
            plan.put(rel, fm, sync_meta("repo", fm, body, fields=changed))
        elif filled:
            plan.put(rel, fm, body)
        else:
            plan.touch(rel)
    plan.execute()


def cmd_capture_followup(ctx, mode, args):
    date = today().isoformat()
    plan = Plan(ctx, mode)
    slug = make_followup(plan, args.who, args.about, date)
    ensure_daily(plan, date, "Waiting On", f"- [[Follow-ups/{slug}]]")
    plan.execute()


def promote_task(plan, rel, fm, week, date):
    """backlog/done -> this-week for the owner's own task (shared with
    `brain promote`)."""
    me = owner_link()
    if fm.get("owner") not in (None, "", me):
        die(f"{rel} is owned by {fm['owner']}, not {me}. Only your own tasks "
            "can be promoted; track someone else's with `query waiting-on`. "
            "Nothing was written.")
    fm["status"] = "this-week"
    fm["week"] = week
    ensure_daily(plan, date, "Priority Tasks", f"- [ ] [[{rel[:-3]}]]")



def _load_task(plan, slug):
    rel = f"Tasks/{slug}.md"
    got = plan.load(rel)
    if got is None:
        print(f"ERROR: no such task: Tasks/{slug}.md", file=sys.stderr)
        sys.exit(2)
    return rel, got


def cmd_promote(ctx, mode, args):
    plan = Plan(ctx, mode)
    week = iso_week() if (not args.week or args.week == "auto") else parse_week(args.week)
    date = today().isoformat()
    for slug in args.task:
        rel, (fm, body) = _load_task(plan, slug)
        promote_task(plan, rel, fm, week, date)
        plan.put(rel, fm, body)
    plan.execute()


def cmd_done(ctx, mode, args):
    plan = Plan(ctx, mode)
    for slug in args.task:
        rel, (fm, body) = _load_task(plan, slug)
        fm["status"] = "done"
        if not fm.get("week"):
            fm["week"] = iso_week()
        plan.put(rel, fm, body)
    plan.execute()
