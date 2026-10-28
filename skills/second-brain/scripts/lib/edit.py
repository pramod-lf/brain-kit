"""brain set / brain append — change existing notes through the same Plan.

`set` edits structured fields (frontmatter plus the body lines that mirror
them). `append` adds prose to the one section each type designates. Neither
ever creates a note (except `append daily`), renames a file, or replaces prose.
"""

import re

from .capture import (_read_file, ensure_daily, ensure_person, flatten_headings,
                      promote_task, resolve_owner)
from .core import die, iso_week, owner_link, parse_week, today
from .people import people_stems, resolve_stem
from .projects import project_rels, require_project_slug
from .refs import resolve_ref
from .body import append_block, one_line, set_h1, sync_meta
from .writer import Plan, ensure_line_in_section

NONE_WORDS = {"none", "null", "-"}
EM = " \u2014 "


def _require_text(text, what):
    if not (text or "").strip():
        die(f"{what} is empty. Nothing was written.")
    return text.strip()


def _single(text, what):
    """A one-line field value: surrounding and inner whitespace (including
    newlines) collapse to single spaces, so it can never break the YAML or the
    H1/meta lines that mirror it."""
    return one_line(_require_text(text, what))


def _value(raw, nullable):
    """'none' clears a nullable field; anything else is the trimmed text."""
    v = one_line(raw)
    if v.lower() in NONE_WORDS:
        if not nullable:
            die("this field cannot be cleared. Nothing was written.")
        return None
    if not v:
        die("value is empty (use 'none' to clear a field). Nothing was written.")
    return v


def _project_slug(plan, raw):
    """A task/meeting project must be an existing project note."""
    v = _value(raw, nullable=True)
    if v is None:
        return None
    known = project_rels(plan.vault)
    if v not in known:
        near = ", ".join(sorted(known)) or "(no projects yet)"
        die(f"no such project: '{v}'. Known projects: {near}. Create one with "
            "`brain capture project`. Nothing was written.")
    return v


# ---- set ----------------------------------------------------------------------

def _set_task(plan, rel, fm, body, a):
    if a.status == "backlog" and a.week:
        die("--week cannot be combined with --status backlog. Nothing was written.")
    if a.week and (a.status or fm.get("status")) == "backlog":
        die(f"--week only applies to this-week or done tasks, and {rel} is in the "
            "backlog. Add --status this-week. Nothing was written.")
    if a.desc is not None:
        desc = _single(a.desc, "--desc")
        body = set_h1(body, lambda _: desc)
    if a.priority:
        fm["priority"] = a.priority
    if a.area:
        fm["area"] = a.area
    if a.owner:
        fm["owner"] = resolve_owner(plan, a.owner)
    if a.project is not None:
        fm["project"] = _project_slug(plan, a.project)
    if a.week:
        fm["week"] = parse_week(a.week)
    if a.status == "this-week":
        promote_task(plan, rel, fm, parse_week(a.week) if a.week else iso_week(),
                     today().isoformat())
    elif a.status == "done":
        fm["status"] = "done"
        if not fm.get("week"):
            fm["week"] = iso_week()
    elif a.status == "backlog":
        fm["status"] = "backlog"
        fm.pop("week", None)
    if fm.get("status") == "this-week" and fm.get("owner") != owner_link():
        die(f"{rel} is in this week's priorities, but its owner is now "
            f"{fm.get('owner')}. Only your own tasks belong there: add "
            "--status backlog to move it out. Nothing was written.")
    return fm, sync_meta("task", fm, body)


def _set_followup(plan, rel, fm, body, a):
    if a.about is not None:
        about = _single(a.about, "--about")
        fm["about"] = about
        body = set_h1(body, lambda old: old.split(EM)[0] + EM + about
                      if EM in old else about)
    if a.status:
        if a.status == "waiting" and fm.get("status") == "done":
            fm["opened"] = today().isoformat()  # reopened
        fm["status"] = a.status
    return fm, sync_meta("followup", fm, body)


def _set_project(plan, rel, fm, body, a):
    if a.status:
        fm["status"] = a.status
    if a.area:
        fm["area"] = a.area
    return fm, body


def _set_repo(plan, rel, fm, body, a):
    if a.status:
        fm["status"] = a.status
    changed = set()
    if a.role is not None:
        fm["role"] = _value(a.role, nullable=True)
        changed.add("role")
    if a.project is not None:
        fm["project"] = require_project_slug(plan.vault, _value(a.project, nullable=False))
        changed.add("project")
    if a.path is not None:
        fm["path"] = _value(a.path, nullable=True)
    if a.remote is not None:
        fm["remote"] = _value(a.remote, nullable=True)
    return fm, (sync_meta("repo", fm, body, fields=changed) if changed else body)


def _set_person(plan, rel, fm, body, a):
    if a.org:
        fm["org"] = a.org
    if a.role is not None:
        fm["role"] = _value(a.role, nullable=True)
    if a.email is not None:
        fm["email"] = _value(a.email, nullable=True)
    return fm, sync_meta("person", fm, body)


def _set_interview(plan, rel, fm, body, a):
    if a.round is not None:
        fm["round"] = _single(a.round, "--round")
        body = set_h1(body, lambda old: re.sub(
            r"( \u2014 round ).*?( \(\d{4}-\d{2}-\d{2}\))$",
            lambda m: m.group(1) + fm["round"] + m.group(2), old, count=1))
    if a.verdict:
        fm["verdict"] = a.verdict
    return fm, sync_meta("interview", fm, body)


def _set_content(plan, rel, fm, body, a):
    if a.status:
        fm["status"] = a.status
    return fm, body


def _set_meeting(plan, rel, fm, body, a):
    if a.project is not None:
        fm["project"] = _project_slug(plan, a.project)
    attendees = list(fm.get("attendees") or [])
    for name in a.remove_attendee or []:
        stem = resolve_stem(name, people_stems(plan.vault))
        link = f"[[People/{stem}]]" if stem else None
        if link not in attendees:
            die(f"'{name}' is not an attendee of {rel}. Nothing was written.")
        attendees.remove(link)
    for name in a.add_attendee or []:
        attendees.append(f"[[{ensure_person(plan, name)}]]")
    fm["attendees"] = sorted(set(attendees))
    return fm, sync_meta("meeting", fm, body, fields={"project", "attendees"})


SET_HANDLERS = {
    "task": (_set_task, ("status", "priority", "area", "owner", "project", "desc",
                         "week")),
    "followup": (_set_followup, ("status", "about")),
    "project": (_set_project, ("status", "area")),
    "repo": (_set_repo, ("status", "role", "project", "path", "remote")),
    "person": (_set_person, ("org", "role", "email")),
    "interview": (_set_interview, ("verdict", "round")),
    "content": (_set_content, ("status",)),
    "meeting": (_set_meeting, ("project", "add_attendee", "remove_attendee")),
}


def cmd_set(ctx, mode, args):
    handler, flags = SET_HANDLERS[args.type]
    if all(getattr(args, f, None) in (None, []) for f in flags):
        die(f"nothing to set. Pass at least one of: "
            + ", ".join("--" + f.replace("_", "-") for f in flags)
            + ". Nothing was written.")
    plan = Plan(ctx, mode)
    rel = resolve_ref(plan.vault, args.type, args.ref)
    fm, body = plan.load(rel)
    fm, body = handler(plan, rel, fm, body, args)
    plan.put(rel, fm, body)
    plan.execute()


# ---- append -------------------------------------------------------------------

def _text(a):
    """--text / --file -> stripped prose, or None when neither was given."""
    if a.text and a.file:
        die("pass --text or --file, not both. Nothing was written.")
    if a.file:
        return _require_text(_read_file(a.file, "--file"), "--file")
    if a.text is not None:
        return _require_text(a.text, "--text")
    return None


def _dated_line(text):
    return f"- {today().isoformat()}: {one_line(text)}"


def _append_prose(section):
    def run(plan, rel, fm, body, a):
        text = _text(a)
        if text is None:
            die("pass --text or --file. Nothing was written.")
        return fm, append_block(body, section, flatten_headings(text))
    return run


def _append_log(section):
    def run(plan, rel, fm, body, a):
        text = _text(a)
        if text is None:
            die("pass --text or --file. Nothing was written.")
        return fm, ensure_line_in_section(body, section, _dated_line(text))
    return run


def _append_project(plan, rel, fm, body, a):
    text = _text(a)
    if text is None and not a.milestone:
        die("pass --text, --file or --milestone. Nothing was written.")
    if text is not None:
        body = append_block(body, "Context", flatten_headings(text))
    for m in a.milestone or []:
        body = ensure_line_in_section(body, "Milestones",
                                      f"- [ ] {one_line(_require_text(m, '--milestone'))}")
    return fm, body


def _append_meeting(plan, rel, fm, body, a):
    text = _text(a)
    if text is None and not a.decision:
        die("pass --text, --file or --decision. Nothing was written.")
    if text is not None:
        body = append_block(body, "Summary", flatten_headings(text))
    for d in a.decision or []:
        body = ensure_line_in_section(body, "Decisions",
                                      f"- {one_line(_require_text(d, '--decision'))}")
    return fm, body


def _append_interview(plan, rel, fm, body, a):
    text = _text(a)
    if text is None and not a.note:
        die("pass --file/--text (assessment) or --note. Nothing was written.")
    if text is not None:
        body = append_block(body, "Assessment", flatten_headings(text))
    for n in a.note or []:
        body = ensure_line_in_section(body, "Notes During Interview",
                                      f"- {one_line(_require_text(n, '--note'))}")
    return fm, body


APPEND_HANDLERS = {
    "reference": _append_prose("Notes"),
    "content": _append_prose("Draft"),
    "person": _append_log("Notes"),
    "followup": _append_log("Updates"),
    "task": _append_log("Notes"),
    "project": _append_project,
    "repo": _append_log("Activity Log"),
    "meeting": _append_meeting,
    "interview": _append_interview,
}


def cmd_append(ctx, mode, args):
    plan = Plan(ctx, mode)
    if args.type == "daily":
        return _append_daily(plan, args)
    rel = resolve_ref(plan.vault, args.type, args.ref)
    fm, body = plan.load(rel)
    fm, body = APPEND_HANDLERS[args.type](plan, rel, fm, body, args)
    plan.put(rel, fm, body)
    plan.execute()


def _append_daily(plan, args):
    date = resolve_ref(plan.vault, "daily", args.ref or today().isoformat())[6:-3]
    if not (args.log or args.dump):
        die("pass --log and/or --dump. Nothing was written.")
    for section, items in (("Work Log", args.log), ("Brain Dump", args.dump)):
        for item in items or []:
            ensure_daily(plan, date, section,
                         f"- {one_line(_require_text(item, '--' + section.split()[0].lower()))}")
    plan.execute()
