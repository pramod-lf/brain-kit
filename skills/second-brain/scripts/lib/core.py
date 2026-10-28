"""Vault resolution, schema constants, slug/date helpers."""

import datetime
import os
import re
import sys
import unicodedata
from pathlib import Path

FOLDERS = ["Daily", "Meetings", "Transcripts", "Interviews", "Projects", "Repos",
           "People", "Tasks", "Follow-ups", "Content", "Reference", "_templates"]

TYPE_BY_FOLDER = {
    "Daily": "daily", "Meetings": "meeting", "Transcripts": "transcript",
    "Interviews": "interview", "Projects": "project", "Repos": "repo",
    "People": "person", "Tasks": "task", "Follow-ups": "followup",
    "Content": "content", "Reference": "reference",
}

FOLDER_BY_TYPE = {v: k for k, v in TYPE_BY_FOLDER.items()}

ENUMS = {
    "task.status": {"backlog", "this-week", "done"},
    "task.area": {"client", "internal", "admin", "learning"},
    "task.priority": {"high", "medium", "low"},
    "interview.verdict": {"pending", "hire", "no-hire"},
    "person.org": {"internal", "external"},
    "followup.status": {"waiting", "done"},
    "project.status": {"active", "paused", "done"},
    "project.area": {"client", "internal", "admin", "learning"},
    "repo.status": {"active", "archived"},
    "content.status": {"draft", "published"},
}

# Frontmatter keys every note carries, in this order, before the type-specific
# fields. `tags` always contains the note type so Obsidian tag searches
# (#task, #meeting, #daily) work for every note.
#
# `title` is deliberately NOT a frontmatter field: the H1 is the title. Keeping
# a second copy in frontmatter would put free prose into the structured part of
# the note, where two slightly different phrasings of the same request would
# produce different bytes for the same artifact.
COMMON = ["type", "schema", "created", "tags"]

# type -> ordered list of type-specific required fields
REQUIRED = {
    "task": ["status", "owner", "project", "area", "priority", "source"],  # week conditional
    "meeting": ["date", "attendees", "project", "transcript"],
    "interview": ["candidate", "role", "round", "date", "verdict"],
    "person": ["org", "role", "email"],
    "followup": ["who", "about", "opened", "status"],
    "project": ["status", "area"],
    "repo": ["project", "status", "role", "path", "remote"],
    "content": ["status"],
    "daily": [], "transcript": [], "reference": [],
}

# fields that may be null
NULLABLE = {
    "task": {"project", "source"},
    "meeting": {"project", "transcript", "attendees"},
    "person": {"role", "email"},
    "repo": {"role", "path", "remote"},
    "project": set(), "followup": set(), "interview": set(), "content": set(),
}

# Body lines that mirror a frontmatter field: `**Label:** value`. `set` rewrites
# them with the field, and lint warns when they drift apart.
META_LINES = {
    "task": {"owner": "Owner", "source": "Source"},
    "person": {"role": "Role", "org": "Org", "email": "Email"},
    "followup": {"who": "Who", "about": "About"},
    "interview": {"role": "Role", "round": "Round", "verdict": "Verdict"},
    "meeting": {"date": "Date", "project": "Project", "attendees": "Attendees"},
    "repo": {"project": "Project", "role": "Role"},
}


def meta_value(ntype, field, fm):
    """What the body line for `field` should say; None means no line at all
    (only people omit empty fields; everything else shows an em dash)."""
    v = fm.get(field)
    if ntype in ("meeting", "repo") and field == "project":
        return f"[[Projects/{v}]]" if v else "\u2014"
    if ntype == "meeting" and field == "attendees":
        return ", ".join(v or []) or "\u2014"
    if v in (None, "", []):
        return None if ntype == "person" else "\u2014"
    return str(v).strip()


DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
WEEK_RE = re.compile(r"^\d{4}-W\d{2}$")
WIKILINK_RE = re.compile(r"^\[\[([^\]|#]+)(\|[^\]]*)?\]\]$")

# naming regexes on path relative to the folder
NAMING = {
    "Daily": re.compile(r"^\d{4}-\d{2}-\d{2}\.md$"),
    "Meetings": re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*-\d{4}-\d{2}-\d{2}\.md$"),
    "Transcripts": re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*-\d{4}-\d{2}-\d{2}-transcript\.md$"),
    "Interviews": re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*-\d{4}-\d{2}-\d{2}\.md$"),
    "Projects": re.compile(r"^[a-z0-9][a-z0-9\-]*(/[a-z0-9][a-z0-9\-]*)*\.md$"),
    "Repos": re.compile(r"^[a-z0-9][a-z0-9\-]*\.md$"),
    "People": re.compile(r"^[A-Z][A-Za-z]*(-[A-Z][A-Za-z]*)*\.md$"),
    "Tasks": re.compile(r"^[a-z0-9][a-z0-9\-]*\.md$"),
    "Follow-ups": re.compile(r"^[a-z0-9][a-z0-9\-]*\.md$"),
    "Content": re.compile(r"^[a-z0-9][a-z0-9\-]*\.md$"),
    "Reference": re.compile(r"^[a-z0-9][a-z0-9\-]*\.md$"),
}


def die(msg):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(2)


def parse_date(value, flag="--date"):
    """Validate a YYYY-MM-DD flag value (a real calendar date). Returns the
    canonical ISO string, or exits 2 with a message naming the flag."""
    try:
        if not DATE_RE.match(value or ""):
            raise ValueError
        return datetime.date.fromisoformat(value).isoformat()
    except ValueError:
        die(f"{flag} must be a real date in YYYY-MM-DD form, got {value!r}. "
            "Nothing was written.")


def parse_week(value, flag="--week"):
    """Validate a YYYY-Www ISO week."""
    try:
        if not WEEK_RE.match(value or ""):
            raise ValueError
        y, w = value.split("-W")
        datetime.date.fromisocalendar(int(y), int(w), 1)
        return value
    except ValueError:
        die(f"{flag} must be an ISO week in YYYY-Www form, got {value!r}. "
            "Nothing was written.")


def require_slug(slug, flag, value):
    """A filename needs at least one Latin letter or digit."""
    if not slug:
        die(f"{flag} {value!r} has no letters or digits to build a filename "
            "from (names and titles must contain Latin letters or digits). "
            "Nothing was written.")
    return slug


CONFIG_KEYS = ("BRAIN_WORK_VAULT", "BRAIN_PERSONAL_VAULT", "BRAIN_ROOT",
               "BRAIN_STATE_DIR", "BRAIN_OWNER", "BRAIN_ORG_DOMAIN")


def write_text(path, text):
    """UTF-8 with LF line endings on every OS, so a vault synced between
    macOS, Linux and Windows stays byte-identical."""
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def config_path():
    """${XDG_CONFIG_HOME:-~/.config}/second-brain/config"""
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base).expanduser() / "second-brain" / "config"


def read_config(path=None):
    """KEY=VALUE lines; blank lines and `#` comments ignored; optional quotes
    around the value are stripped. Unknown keys are ignored."""
    path = path or config_path()
    out = {}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return out
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = (s.strip() for s in line.split("=", 1))
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "'\"":
            val = val[1:-1]
        if key in CONFIG_KEYS and val:
            out[key] = val
    return out


def write_config(values, path=None):
    path = path or config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# second-brain config. Environment variables override these."]
    lines += [f"{k}={values[k]}" for k in CONFIG_KEYS if values.get(k)]
    write_text(path, "\n".join(lines) + "\n")
    return path


_FILE_CONFIG = read_config()


def setting(key):
    """Environment wins over the config file."""
    val = os.environ.get(key, "").strip()
    return val or _FILE_CONFIG.get(key) or None


def _state_home():
    base = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    return Path(base).expanduser() / "second-brain"


class Ctx:
    """Resolved environment: the two vault paths + where the mode file lives.

    Vault resolution, first source that names any vault wins as a whole
    (so an environment override never mixes with half of a config file):
      1. environment, then 2. the config file. Within a source:
         BRAIN_WORK_VAULT / BRAIN_PERSONAL_VAULT (two independent paths, no
         common parent needed), falling back to BRAIN_ROOT/{work,personal}.
    Mode file: BRAIN_STATE_DIR/.brain-mode > BRAIN_ROOT/.brain-mode >
    ${XDG_STATE_HOME:-~/.local/state}/second-brain/.brain-mode. It lives
    outside the vaults so a synced vault never carries it.
    """

    def __init__(self, vaults, mode_file, source):
        self.vaults = vaults
        self.mode_file = mode_file
        self.source = source

    def vault(self, mode=None):
        mode = mode or current_mode(self)
        if mode not in self.vaults:
            die(f"no {mode} vault is configured. Run `brain init --{mode}-vault PATH`.")
        return self.vaults[mode]


def _vaults_from(get):
    vaults, src = {}, []
    for mode, var in (("work", "BRAIN_WORK_VAULT"),
                      ("personal", "BRAIN_PERSONAL_VAULT")):
        val = get(var)
        if val:
            vaults[mode] = Path(val).expanduser()
            src.append(var)
    root = get("BRAIN_ROOT")
    if root:
        r = Path(root).expanduser()
        for mode in ("work", "personal"):
            vaults.setdefault(mode, r / mode)
        src.append("BRAIN_ROOT")
    return vaults, src, root


def resolve_ctx():
    vaults, src, root = _vaults_from(lambda k: os.environ.get(k, "").strip() or None)
    origin = "environment"
    if not vaults:
        vaults, src, root = _vaults_from(_FILE_CONFIG.get)
        origin = str(config_path())
    if not vaults:
        die("no vault configured. Run `brain init --work-vault PATH "
            "--personal-vault PATH --owner \"Your Name\"` (or set "
            "BRAIN_WORK_VAULT / BRAIN_PERSONAL_VAULT, or BRAIN_ROOT).")
    if not any(p.is_dir() for p in vaults.values()):
        die("no configured vault directory exists: "
            + ", ".join(f"{m}={p}" for m, p in sorted(vaults.items()))
            + ". Run `brain init` to create the vault folders.")

    state = setting("BRAIN_STATE_DIR")
    if state:
        mf = Path(state).expanduser() / ".brain-mode"
    elif root:
        mf = Path(root).expanduser() / ".brain-mode"
    else:
        mf = _state_home() / ".brain-mode"
    return Ctx(vaults, mf, f"{'+'.join(src)} ({origin})")


def current_mode(ctx):
    if ctx.mode_file.exists():
        m = ctx.mode_file.read_text(encoding="utf-8").strip()
        if m in ("work", "personal"):
            return m
    return "work"


# Literal phrases that count as the user explicitly asking for the other vault.
# The active mode decides which vault every later write lands in, so it may
# only move on the user's own words. A model can decide to switch vaults before
# it has read the skill's rules; a check that lives in the CLI still applies in
# that case, where prose in SKILL.md cannot.
SWITCH_PHRASES = {
    "personal": ("personal brain", "personal vault", "personal side",
                 "my personal", "to personal", "in personal"),
    "work": ("work brain", "work vault", "work side",
             "my work", "to work", "in work"),
}


# Words that cancel a vault mention when they appear just before it:
# "not my personal one", "instead of the work vault".
NEGATIONS = {"not", "never", "dont", "don't", "no", "instead", "than", "without"}


def _has_plain_mention(mode, text):
    """True when at least one mention of `mode` has no negation in the 3 words
    before it."""
    words = re.findall(r"[a-z']+", text)
    return any(w == mode and not (NEGATIONS & set(words[max(0, i - 3):i]))
               for i, w in enumerate(words))


def switch_is_explicit(mode, because):
    """True when `because` (the user's verbatim words) explicitly names the
    vault being switched TO. Deterministic, no judgement: it must contain one
    of the target vault's literal phrases, and at least one mention of the
    target must not be negated ("not my personal one" does not count).
    Mentions of the other vault do not matter."""
    if not because:
        return False
    text = " ".join(str(because).lower().split())
    return (any(p in text for p in SWITCH_PHRASES[mode])
            and _has_plain_mention(mode, text))


def set_mode(ctx, mode, because=None):
    if mode not in ("work", "personal"):
        die("mode must be 'work' or 'personal'")
    if not switch_is_explicit(mode, because):
        die(f"refusing to switch to the {mode} vault. `brain mode {mode}` requires "
            f'--because "<the user\'s own words>", and those words must explicitly '
            f"name the {mode} brain/vault without negating it "
            f"(e.g. \"switch to my {mode} brain\", "
            f'"in my {mode} brain, ..."). The active mode is NEVER changed '
            f"implicitly — not by topic, not by content. If the user did not ask "
            f"for the other vault, do not switch: capture in the current mode "
            f"(`brain status` shows it). Nothing was changed.")
    if mode not in ctx.vaults:
        die(f"no {mode} vault is configured. Run `brain init --{mode}-vault PATH`.")
    ctx.mode_file.parent.mkdir(parents=True, exist_ok=True)
    write_text(ctx.mode_file, mode + "\n")


def vault_path(ctx, mode=None):
    return ctx.vault(mode)


def today():
    # BRAIN_TODAY=YYYY-MM-DD pins "today" so tests are reproducible.
    override = os.environ.get("BRAIN_TODAY")
    if override:
        return datetime.date.fromisoformat(override)
    return datetime.date.today()


def iso_week(d=None):
    d = d or today()
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def _ascii(text):
    """NFKD transliteration: 'Inés Peña' -> 'Ines Pena'."""
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()


def slugify(text):
    s = _ascii(text).strip().lower()
    s = re.sub(r"['’]", "", s)
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


# Filename-slug stopwords. Dropped before a filename slug is built so that two
# sessions phrasing the same thing slightly differently ("review the deck" vs
# "review deck") land on the SAME file. Body text keeps the full wording.
SLUG_STOP = {
    "a", "an", "the", "this", "that", "these", "those", "my", "our", "your",
    "their", "his", "her", "its", "and", "or", "but", "of", "for", "to", "in",
    "on", "at", "by", "with", "from", "into", "about", "as", "is", "are", "am",
    "be", "been", "was", "were", "will", "shall", "would", "should", "can",
    "could", "just", "please", "also", "then", "so", "we", "i", "he", "she",
    "they", "it", "me", "us", "them", "him", "s", "re",
    # intent verbs that one session states and another drops
    "want", "wants", "need", "needs", "like", "decide", "decides", "decided",
}

# Default significant-token budget for a filename slug.
SLUG_TOKENS = 5


def _stem(token):
    """Collapse the one verb-form split that costs determinism: the past tense
    of a long -ize/-ate style verb ('standardized' -> 'standardize'). Deliberately
    narrow (>=8 chars, '-ed' only) so ordinary nouns keep their spelling."""
    if len(token) >= 8 and token.endswith("ed"):
        return token[:-1]
    return token


def slug_key(text, max_tokens=SLUG_TOKENS):
    """Deterministic filename slug: slugify, drop stopwords, keep the first
    `max_tokens` significant tokens. Trailing embellishment a model might add
    ("… by Friday 2026-08-21", "… next weekend Aug 22-23") falls off the end,
    so the artifact path is stable across sessions. `max_tokens=None` keeps
    every significant token, for comparing two phrasings in full."""
    toks = [_stem(t) for t in slugify(text).split("-") if t]
    sig = [t for t in toks if t and t not in SLUG_STOP]
    if not sig:
        sig = toks
    return "-".join(sig[:max_tokens])


def name_parts(name):
    """Capitalised Latin-letter parts of a person's name: each word and each
    hyphen-separated part gets a capital first letter; the rest is kept.
    Accents are transliterated first. Empty when nothing Latin is left."""
    parts = []
    for word in re.split(r"[\s_]+", _ascii(name or "").strip()):
        for sub in word.split("-"):
            sub = re.sub(r"[^A-Za-z]", "", sub)
            if sub:
                parts.append(sub[:1].upper() + sub[1:])
    return parts


def person_filename(name):
    """'maya chen' / 'Inés Peña' / 'anne-marie smith' ->
    'Maya-Chen' / 'Ines-Pena' / 'Anne-Marie-Smith'. Names with no Latin
    letters (after transliteration) are refused."""
    parts = name_parts(name)
    if not parts:
        die(f"person name {name!r} has no Latin letters. People notes are "
            "named Firstname-Lastname in Latin script; pass the name in Latin "
            "letters (e.g. a romanized spelling). Nothing was written.")
    return "-".join(parts)


def default_org(mode, email=None):
    """`internal` = the owner's own organization. An email at BRAIN_ORG_DOMAIN
    is internal; otherwise work-vault people default to internal and
    personal-vault people to external."""
    domain = (setting("BRAIN_ORG_DOMAIN") or "").strip().lower().lstrip("@")
    if email and domain:
        return "internal" if email.strip().lower().endswith("@" + domain) else "external"
    return "internal" if mode == "work" else "external"


def wikilink_target(value):
    """'[[People/Maya|Maya]]' -> 'People/Maya' ; non-wikilink -> None"""
    if not isinstance(value, str):
        return None
    m = WIKILINK_RE.match(value.strip())
    return m.group(1).strip() if m else None


# The vault owner: the person whose brain this is. Their own tasks carry
# `owner: [[People/<owner>]]`; everyone else's action items carry that person's
# link. Set once per install (BRAIN_OWNER, the People-note name, e.g.
# "Maya Chen"); there is no default person. Read lazily, so a bad value never
# stops `--help`, `status` or `init` from running.
def owner_name():
    return (setting("BRAIN_OWNER") or "").strip()


def owner_problem():
    """None when the configured owner is usable, else a short reason."""
    name = owner_name()
    if not name:
        return "unset"
    if not name_parts(name):
        return "has no Latin letters"
    return None


def owner_link():
    """'[[People/Maya-Chen]]', or None when the owner is unset or invalid."""
    if owner_problem():
        return None
    return f"[[People/{'-'.join(name_parts(owner_name()))}]]"


def self_words():
    """Words that mean the vault owner in --owner / --who."""
    name = owner_name()
    return {"me", "self", "myself", "i"} | ({name.lower()} if name else set())


def require_owner():
    problem = owner_problem()
    if problem == "unset":
        die("no owner configured. Run `brain init --owner \"Your Name\"` "
            "(or set BRAIN_OWNER) to your People-note name.")
    if problem:
        die(f"the configured owner {owner_name()!r} {problem}. Run "
            "`brain init --owner \"Your Name\"` with your name in Latin letters.")
