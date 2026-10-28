#!/bin/bash
# second-brain self-test. Exits nonzero on any assertion failure.
# All people, organizations, projects and topics below are invented.
# Set KEEP=1 to keep the scratch vaults in .selftest-root/ for inspection.
set -u
REPO="$(cd "$(dirname "$0")/.." && pwd)"
SKILL="$REPO/skills/second-brain"
export BRAIN_ROOT="$REPO/.selftest-root"
export BRAIN_OWNER="Maya Chen"
export BRAIN_TODAY=2026-08-15
export PYTHONDONTWRITEBYTECODE=1
# Keep the user's real config and state out of the test.
export XDG_CONFIG_HOME="$BRAIN_ROOT/xdg-config"
export XDG_STATE_HOME="$BRAIN_ROOT/xdg-state"
unset BRAIN_WORK_VAULT BRAIN_PERSONAL_VAULT BRAIN_STATE_DIR BRAIN_ORG_DOMAIN
BRAIN="$SKILL/scripts/brain"
FAILS=0
PASSES=0

cleanup() { [ "${KEEP:-0}" = 1 ] || rm -rf "$REPO/.selftest-root"; }
trap cleanup EXIT

fail() { echo "FAIL: $*"; FAILS=$((FAILS+1)); }
ok()   { echo "ok:   $*"; PASSES=$((PASSES+1)); }

assert_eq() { [ "$1" = "$2" ] && ok "$3" || fail "$3 (got '$1', want '$2')"; }
assert_contains() { echo "$1" | grep -qF -- "$2" && ok "$3" || fail "$3 (missing '$2')"; }
assert_file() { [ -f "$BRAIN_ROOT/$1" ] && ok "exists $1" || fail "missing file $1"; }
assert_exit() { [ "$1" -eq "$2" ] && ok "$3" || fail "$3 (exit $1, want $2)"; }
snapshot() { find "$1" -name '*.md' -exec cksum {} + | sort; }
# A path as the CLI prints it: Windows form under Git Bash, unchanged elsewhere.
native() { if command -v cygpath >/dev/null 2>&1; then cygpath -w "$1"; else printf '%s' "$1"; fi; }
section() { awk -v h="## $2" '$0==h{f=1;next} /^#/{f=0} f' "$1"; }

rm -rf "$REPO/.selftest-root"
mkdir -p "$BRAIN_ROOT/work" "$BRAIN_ROOT/personal"

# ---- status / mode ----------------------------------------------------------
OUT=$("$BRAIN" status)
assert_contains "$OUT" "second-brain " "status identifies the tool"
assert_contains "$("$BRAIN" --version)" "second-brain" "--version prints the tool name"
assert_contains "$OUT" "mode: work" "status default mode work"
assert_contains "$OUT" "week: 2026-W33" "status week"
assert_contains "$OUT" "owner: Maya Chen" "status shows the owner"
"$BRAIN" mode personal --because "switch to my personal brain" >/dev/null
assert_eq "$(cat "$BRAIN_ROOT/.brain-mode")" "personal" "mode file written"
"$BRAIN" mode work --because "switch back to my work brain" >/dev/null

# ---- capture meeting (full artifact set) -------------------------------------
printf 'raw transcript line 1\nline 2\n' > "$BRAIN_ROOT/tr.txt"
printf 'Reviewed the planting calendar.\n' > "$BRAIN_ROOT/sum.txt"
OUT=$("$BRAIN" capture meeting --title "Garden Club Planning" --date 2026-08-14 \
  --attendees "Sam Ortiz, Alex Moore" --project community-garden \
  --transcript-file "$BRAIN_ROOT/tr.txt" --summary-file "$BRAIN_ROOT/sum.txt" \
  --task "order seed packets|internal|high" --followup "Sam Ortiz|shed key copy")
assert_exit $? 0 "capture meeting exit 0"
for f in "work/Meetings/garden-club-planning-2026-08-14.md" \
         "work/Transcripts/garden-club-planning-2026-08-14-transcript.md" \
         "work/Tasks/internal-order-seed-packets.md" \
         "work/Follow-ups/sam-shed-key-copy.md" \
         "work/People/Sam-Ortiz.md" "work/People/Alex-Moore.md" \
         "work/Daily/2026-08-14.md"; do assert_file "$f"; done
assert_contains "$OUT" "WROTE work/Meetings/garden-club-planning-2026-08-14.md" "WROTE line printed"
M=$(cat "$BRAIN_ROOT/work/Meetings/garden-club-planning-2026-08-14.md")
assert_contains "$M" "[[Tasks/internal-order-seed-packets]]" "meeting links task"
assert_contains "$M" "Reviewed the planting calendar." "summary landed in meeting"
assert_contains "$(cat "$BRAIN_ROOT/work/Daily/2026-08-14.md")" \
  "[[Meetings/garden-club-planning-2026-08-14]]" "daily links meeting"
assert_contains "$(section "$BRAIN_ROOT/work/Daily/2026-08-14.md" "Waiting On")" \
  "[[Follow-ups/sam-shed-key-copy]]" "meeting --followup lands in the daily Waiting On"
grep -q "^org: internal" "$BRAIN_ROOT/work/People/Sam-Ortiz.md" \
  && ok "work-vault attendee defaults to org internal" || fail "work default org"
grep -q "^schema: 1" "$BRAIN_ROOT/work/Meetings/garden-club-planning-2026-08-14.md" \
  && ok "notes carry schema: 1" || fail "schema version"

# ---- idempotency: re-run identical capture -> byte-identical vault -----------
SNAP1=$(snapshot "$BRAIN_ROOT/work")
"$BRAIN" capture meeting --title "Garden Club Planning" --date 2026-08-14 \
  --attendees "Sam Ortiz, Alex Moore" --project community-garden \
  --transcript-file "$BRAIN_ROOT/tr.txt" --summary-file "$BRAIN_ROOT/sum.txt" \
  --task "order seed packets|internal|high" --followup "Sam Ortiz|shed key copy" >/dev/null
SNAP2=$(snapshot "$BRAIN_ROOT/work")
assert_eq "$SNAP2" "$SNAP1" "re-run capture meeting: vault byte-identical"
N=$(ls "$BRAIN_ROOT/work/Tasks" | wc -l | tr -d ' ')
assert_eq "$N" "1" "no duplicate task on re-run"
# a new attendee on a re-capture updates frontmatter AND the body line
"$BRAIN" capture meeting --title "Garden Club Planning" --date 2026-08-14 \
  --attendees "Sam Ortiz, Alex Moore, Lena Fox" >/dev/null
MF="$BRAIN_ROOT/work/Meetings/garden-club-planning-2026-08-14.md"
grep -q '^  - "\[\[People/Lena-Fox\]\]"' "$MF" && ok "new attendee in frontmatter" \
  || fail "new attendee frontmatter"
grep -q '^\*\*Attendees:\*\* \[\[People/Alex-Moore\]\], \[\[People/Lena-Fox\]\], \[\[People/Sam-Ortiz\]\]$' "$MF" \
  && ok "body attendee line matches frontmatter" || fail "body attendee line stale"

# ---- capture interview --------------------------------------------------------
"$BRAIN" capture interview --candidate "Iris Bell" --role "Pastry Chef" \
  --round technical --date 2026-08-15 >/dev/null
assert_file "work/Interviews/iris-bell-pastry-chef-2026-08-15.md"
assert_file "work/People/Iris-Bell.md"
assert_contains "$(cat "$BRAIN_ROOT/work/Daily/2026-08-15.md")" \
  "[[Interviews/iris-bell-pastry-chef-2026-08-15]]" "daily links interview"
grep -q "verdict: pending" "$BRAIN_ROOT/work/Interviews/iris-bell-pastry-chef-2026-08-15.md" \
  && ok "interview verdict pending" || fail "interview verdict"
grep -q "^org: external" "$BRAIN_ROOT/work/People/Iris-Bell.md" \
  && ok "candidate is org external" || fail "candidate org"

# ---- capture task / promote / done --------------------------------------------
"$BRAIN" capture task --desc "Write volunteer handbook" --area internal --priority high >/dev/null
T="$BRAIN_ROOT/work/Tasks/internal-write-volunteer-handbook.md"
assert_file "work/Tasks/internal-write-volunteer-handbook.md"
grep -q "status: backlog" "$T" && ok "new task backlog" || fail "new task status"
grep -q "priority: high" "$T" && ok "task priority" || fail "task priority"
"$BRAIN" promote --task internal-write-volunteer-handbook >/dev/null
grep -q "status: this-week" "$T" && ok "promote sets this-week" || fail "promote status"
grep -q "week: 2026-W33" "$T" && ok "promote sets week" || fail "promote week"
assert_contains "$(cat "$BRAIN_ROOT/work/Daily/2026-08-15.md")" \
  "[[Tasks/internal-write-volunteer-handbook]]" "promote noted in daily"
"$BRAIN" done --task internal-write-volunteer-handbook >/dev/null
grep -q "status: done" "$T" && ok "done sets done" || fail "done status"

# default priority medium
"$BRAIN" capture task --desc "No priority given" --area admin >/dev/null
grep -q "priority: medium" "$BRAIN_ROOT/work/Tasks/admin-no-priority-given.md" \
  && ok "default priority medium" || fail "default priority"

# ---- project ---------------------------------------------------------------------
"$BRAIN" capture project --name "Harbor Rewrite" --area client >/dev/null
assert_file "work/Projects/harbor-rewrite.md"
grep -q "status: active" "$BRAIN_ROOT/work/Projects/harbor-rewrite.md" \
  && ok "project is active" || fail "project not active"
SNAP=$(snapshot "$BRAIN_ROOT/work")
"$BRAIN" capture project --name "Harbor Rewrite" >/dev/null
assert_eq "$(snapshot "$BRAIN_ROOT/work")" "$SNAP" "capture project is idempotent"
"$BRAIN" capture task --desc "Draft Harbor rewrite plan" --area client >/dev/null
grep -q "project: harbor-rewrite" "$BRAIN_ROOT/work/Tasks/client-draft-harbor-rewrite-plan.md" \
  && ok "task infers new project" || fail "task did not infer new project"

# ---- person / followup / note --------------------------------------------------
"$BRAIN" capture person --name "Morgan Blake" --org external --email morgan@example.org >/dev/null
assert_file "work/People/Morgan-Blake.md"
"$BRAIN" capture followup --who "Morgan Blake" --about "library room booking" >/dev/null
assert_file "work/Follow-ups/morgan-library-room-booking.md"
printf 'Layer greens and browns; turn the pile weekly.\n' > "$BRAIN_ROOT/note.txt"
"$BRAIN" capture note --title "compost bin guide" --body-file "$BRAIN_ROOT/note.txt" >/dev/null
assert_file "work/Reference/compost-bin-guide.md"
printf 'Why a slow ferment makes better bread.\n' > "$BRAIN_ROOT/blog.txt"
"$BRAIN" capture note --title "Blog on sourdough" --folder Content --body-file "$BRAIN_ROOT/blog.txt" >/dev/null
grep -q "status: draft" "$BRAIN_ROOT/work/Content/blog-sourdough.md" \
  && ok "content draft default" || fail "content status"

# ---- slug_key: filename slugs are stopword-stripped and length-capped, so two
# ---- phrasings of the same request land on the SAME file.
"$BRAIN" capture task --desc "repaint the north fence panels near the gate before Friday" --area client >/dev/null
assert_file "work/Tasks/client-repaint-north-fence-panels.md"
"$BRAIN" capture task --desc "Repaint north fence panels near gate by Friday 2026-08-21" --area client >/dev/null
n=$(ls "$BRAIN_ROOT/work/Tasks" | grep -c "repaint-north-fence-panels")
[ "$n" = "1" ] && ok "slug_key collapses phrasing variants" || fail "slug_key variants ($n files)"
# A request that lands on an existing task is never dropped silently.
OUT=$("$BRAIN" capture task --desc "repaint the north fence panels near the gate before Friday" --area client)
case "$OUT" in *MATCHED*) fail "same wording prints no MATCHED line" ;; *) ok "same wording prints no MATCHED line" ;; esac
OUT=$("$BRAIN" capture task --desc "repaint north fence panels near gate by Monday" --area client)
assert_contains "$OUT" "MATCHED work/Tasks/client-repaint-north-fence-panels.md: same task as \"repaint the north fence panels near the gate before Friday\"" \
  "different wording prints a MATCHED line naming the existing task"
assert_contains "$OUT" "\"repaint north fence panels near gate by Monday\"" "MATCHED line quotes the new wording"
OUT=$("$BRAIN" capture task --desc "repaint the north fence panels near the gate before Friday" --area client --priority high)
assert_contains "$OUT" "UPDATED work/Tasks/client-repaint-north-fence-panels.md" "explicit priority updates the matched task"
grep -q "^priority: high" "$BRAIN_ROOT/work/Tasks/client-repaint-north-fence-panels.md" \
  && ok "matched task takes the explicit priority" || fail "matched task priority"
"$BRAIN" capture task --desc "repaint the north fence panels near the gate before Friday" --area client >/dev/null
grep -q "^priority: high" "$BRAIN_ROOT/work/Tasks/client-repaint-north-fence-panels.md" \
  && ok "omitted priority keeps the matched task's priority" || fail "omitted priority reset"
"$BRAIN" extract-tasks --task "repaint the north fence panels near the gate before Friday|client" >/dev/null
grep -q "^priority: high" "$BRAIN_ROOT/work/Tasks/client-repaint-north-fence-panels.md" \
  && ok "task spec without priority keeps the matched task's priority" || fail "spec priority reset"
printf 'Practising washes from a library book; paper in the hall cupboard.\n' > "$BRAIN_ROOT/paint.txt"
"$BRAIN" capture note --title "started learning watercolor" --body-file "$BRAIN_ROOT/paint.txt" >/dev/null
assert_file "work/Reference/started-learning-watercolor.md"

# ---- project inference and query tasks --project ----------------------------
"$BRAIN" capture task --desc "ship widget" --area internal --project alpha >/dev/null
mkproj() {
  mkdir -p "$BRAIN_ROOT/work/Projects/$1"
  printf -- '---\ntype: project\nschema: 1\ncreated: 2026-08-15\ntags: [project]\nstatus: active\narea: internal\n---\n\n# %s\n' \
    "$2" > "$BRAIN_ROOT/work/Projects/$1/$1.md"
}
mkproj lumen-launch "Lumen Launch"
mkproj harvest-fair-budget "Harvest Fair Budget"
mkproj harvest-fair-schedule "Harvest Fair Schedule"
"$BRAIN" capture task --desc "review the Lumen Launch press kit" --area internal >/dev/null
grep -q "^project: lumen-launch" "$BRAIN_ROOT/work/Tasks/internal-review-lumen-launch-press.md" \
  && ok "CLI infers project from desc" || fail "project inference"
"$BRAIN" capture task --desc "renew the library card" --area admin >/dev/null
grep -q "^project: null" "$BRAIN_ROOT/work/Tasks/admin-renew-library-card.md" \
  && ok "no project when nothing overlaps" || fail "project inference false positive"
"$BRAIN" capture meeting --title "Harvest Fair volunteer roster" --date 2026-08-15 >/dev/null
grep -q "^project: null" "$BRAIN_ROOT/work/Meetings/harvest-fair-volunteer-roster-2026-08-15.md" \
  && ok "tied project candidates -> null" || fail "project tie-break"

"$BRAIN" query tasks --project alpha | grep -q "also mentioning" \
  && ok "query tasks related section" || fail "query tasks related section"

# ---- queries (one-shot answers) -------------------------------------------------
OUT=$("$BRAIN" query tasks)
assert_contains "$OUT" "internal-order-seed-packets" "query tasks lists task"
OUT=$("$BRAIN" query tasks --status done)
assert_contains "$OUT" "internal-write-volunteer-handbook" "query tasks --status done"
OUT=$("$BRAIN" query waiting-on)
assert_contains "$OUT" "morgan-library-room-booking" "query waiting-on"
OUT=$("$BRAIN" query today)
assert_contains "$OUT" "2026-08-15" "query today"
OUT=$("$BRAIN" query person "Morgan Blake")
assert_contains "$OUT" "morgan@example.org" "query person"
assert_contains "$OUT" "role: —" "query person shows a dash for a missing role"
echo "$OUT" | grep -q "None" && fail "query person printed None" || ok "query person never prints None"
OUT=$("$BRAIN" query meetings --since 2026-08-01)
assert_contains "$OUT" "garden-club-planning-2026-08-14" "query meetings"
OUT=$("$BRAIN" query notes "compost bin")
assert_contains "$OUT" "## Note body" "query notes prints the single matching note"
OUT=$("$BRAIN" query notes)
assert_contains "$OUT" "compost-bin-guide" "query notes lists Reference notes"
OUT=$("$BRAIN" query notes "no such thing")
assert_contains "$OUT" "No Reference or Content note matches" "query notes reports no match"
OUT=$("$BRAIN" query working-on)
assert_contains "$OUT" "This-week tasks" "query working-on"

# ---- lint failure refusal --------------------------------------------------------
OUT=$("$BRAIN" capture meeting --title "Lint check" --date 2026-08-15 \
  --task "sweep the porch|bogus-area" 2>&1)
assert_exit $? 1 "invalid capture refused (exit 1)"
assert_contains "$OUT" "REFUSED" "refusal message"
[ -f "$BRAIN_ROOT/work/Meetings/lint-check-2026-08-15.md" ] && fail "refused file was written" \
  || ok "refused file not written"
for TITLE in "!!!" ""; do
  OUT=$("$BRAIN" capture meeting --title "$TITLE" --date 2026-08-15 2>&1)
  assert_exit $? 2 "meeting title with no letters refused: '$TITLE'"
done
[ -f "$BRAIN_ROOT/work/Meetings/-2026-08-15.md" ] && fail "empty-slug meeting written" \
  || ok "no empty-slug meeting file"

# ---- input validation: dates, empty slugs, person names -----------------------
for CMD in "capture meeting --title Planning --date 2026-02-30" \
           "capture meeting --title Planning --date 15/08/2026" \
           "capture interview --candidate Pat --role Baker --round 1 --date 2026-13-01" \
           "extract-tasks --task x --date tomorrow" \
           "query meetings --since 2026-8-1" \
           "promote --task internal-order-seed-packets --week 2026-W60"; do
  OUT=$("$BRAIN" $CMD 2>&1)
  assert_exit $? 2 "bad date refused: $CMD"
  assert_contains "$OUT" "must be" "bad date message: $CMD"
done
for CMD in "capture task --desc !!! --area internal" \
           "capture note --title @@@ --body-file $BRAIN_ROOT/note.txt" \
           "capture followup --who Sam --about ..." \
           "extract-tasks --title !!! --transcript-file $BRAIN_ROOT/tr.txt --task x"; do
  OUT=$("$BRAIN" $CMD 2>&1)
  assert_exit $? 2 "empty slug refused: $CMD"
done
ls "$BRAIN_ROOT/work/Tasks" | grep -q -- '-\.md$' && fail "empty-slug task written" \
  || ok "no empty-slug task file"
OUT=$("$BRAIN" capture person --name "李雷" 2>&1)
assert_exit $? 2 "non-Latin person name refused"
assert_contains "$OUT" "Latin letters" "non-Latin refusal explains the limit"
[ -f "$BRAIN_ROOT/work/People/.md" ] && fail "People/.md written" || ok "no People/.md"
"$BRAIN" capture person --name "anne-marie smith" >/dev/null

# ---- quotes and backslashes in frontmatter values round-trip exactly ---------
for i in 1 2 3; do
  OUT=$("$BRAIN" capture followup --who "Morgan Blake" --about 'the "big" plan' 2>&1)
  [ $i = 1 ] && S1=$(cksum < "$BRAIN_ROOT/work/Follow-ups/morgan-big-plan.md")
done
assert_contains "$OUT" "UNCHANGED work/Follow-ups/morgan-big-plan.md" "quoted --about rerun is UNCHANGED"
assert_eq "$(cksum < "$BRAIN_ROOT/work/Follow-ups/morgan-big-plan.md")" "$S1" "quoted --about stays byte-identical"
grep -qF 'about: "the \"big\" plan"' "$BRAIN_ROOT/work/Follow-ups/morgan-big-plan.md" \
  && ok "quote escaped exactly once" || fail "quote escaping"
for i in 1 2 3; do
  OUT=$("$BRAIN" capture person --name "Hugo Vance" --role 'Head of "Ops"' 2>&1)
  [ $i = 1 ] && S1=$(cksum < "$BRAIN_ROOT/work/People/Hugo-Vance.md")
done
assert_contains "$OUT" "UNCHANGED work/People/Hugo-Vance.md" "quoted --role rerun is UNCHANGED"
assert_eq "$(cksum < "$BRAIN_ROOT/work/People/Hugo-Vance.md")" "$S1" "quoted --role stays byte-identical"
for i in 1 2 3; do
  OUT=$("$BRAIN" capture person --name "Wren Hart" --role 'Lead \ "Night" shift' 2>&1)
done
assert_contains "$OUT" "UNCHANGED work/People/Wren-Hart.md" "backslash value rerun is UNCHANGED"
assert_contains "$("$BRAIN" query person "Wren Hart")" 'role: Lead \ "Night" shift' \
  "backslash and quotes read back exactly"
assert_file "work/People/Anne-Marie-Smith.md"

# ---- lint + fix-safe ---------------------------------------------------------------
"$BRAIN" lint >/dev/null; assert_exit $? 0 "lint clean exit 0"
python3 - "$BRAIN_ROOT/work/Reference/compost-bin-guide.md" <<'EOF'
import sys
p = sys.argv[1]
t = open(p).read().replace("schema: 1\n", "").replace("created: 2026-08-15\n", "")
open(p, "w").write(t)
EOF
"$BRAIN" lint >/dev/null 2>&1; assert_exit $? 1 "lint detects broken file"
OUT=$("$BRAIN" lint --fix-safe)
assert_contains "$OUT" "FIXED" "fix-safe applied"
"$BRAIN" lint >/dev/null; assert_exit $? 0 "lint clean after fix-safe"

# ---- unreadable input files -> clean error, nothing written ----------------------
OUT=$("$BRAIN" capture meeting --title "Ghost sync" --date 2026-08-13 \
  --summary-file "$BRAIN_ROOT/sum.txt" --transcript-file /nope-does-not-exist.md 2>&1)
assert_exit $? 2 "missing transcript-file exits 2"
assert_contains "$OUT" "ERROR: cannot read" "clean error, no traceback"
echo "$OUT" | grep -q "Traceback" && fail "raw traceback leaked" || ok "no traceback"
[ -f "$BRAIN_ROOT/work/Meetings/ghost-sync-2026-08-13.md" ] \
  && fail "ghost meeting written" || ok "nothing written on bad file"

# ---- unicode transliteration ----------------------------------------------------
"$BRAIN" capture person --name "Inés Peña" --org external >/dev/null
assert_file "work/People/Ines-Pena.md"
"$BRAIN" capture meeting --title "Crème brûlée tasting" --date 2026-08-13 >/dev/null
assert_file "work/Meetings/creme-brulee-tasting-2026-08-13.md"

# ---- write path reuses fuzzy person resolution -----------------------------------
"$BRAIN" capture person --name "Noor" >/dev/null   # first-name-only note exists
OUT=$("$BRAIN" capture meeting --title "Seed swap huddle" --date 2026-08-12 \
  --attendees "Noor Haddad")
[ -f "$BRAIN_ROOT/work/People/Noor-Haddad.md" ] \
  && fail "duplicate Noor-Haddad.md created" || ok "no duplicate person note"
assert_contains "$OUT" "LINKED work/People/Noor.md" "LINKED line printed"
grep -q '\[\[People/Noor\]\]' "$BRAIN_ROOT/work/Meetings/seed-swap-huddle-2026-08-12.md" \
  && ok "attendee links existing People/Noor" || fail "attendee wikilink wrong"

# two FULL names with different surnames are DIFFERENT people
"$BRAIN" capture person --name "Elena Park" >/dev/null
"$BRAIN" capture person --name "Elena Novak" >/dev/null
assert_file "work/People/Elena-Novak.md"
assert_file "work/People/Elena-Park.md"

# ---- follow-up dedupe + reopen ---------------------------------------------------
OUT=$("$BRAIN" capture followup --who "Sam Ortiz" --about "Spare Shed Key Copy" 2>&1)
assert_contains "$OUT" "UNCHANGED work/Follow-ups/sam-shed-key-copy.md" \
  "paraphrase dedupes to existing follow-up"
N=$(ls "$BRAIN_ROOT/work/Follow-ups" | grep -c '^sam-shed')
assert_eq "$N" "1" "no forked follow-up"
FU="$BRAIN_ROOT/work/Follow-ups/sam-shed-key-copy.md"
python3 - "$FU" <<'EOF'
import sys
p = sys.argv[1]
t = open(p).read().replace("status: waiting", "status: done")
open(p, "w").write(t)
EOF
OUT=$("$BRAIN" capture followup --who "Sam Ortiz" --about "shed key copy")
assert_contains "$OUT" "UPDATED work/Follow-ups/sam-shed-key-copy.md" \
  "done follow-up reopened (UPDATED)"
grep -q "status: waiting" "$FU" && ok "reopened -> waiting" || fail "reopen status"
grep -q "opened: 2026-08-15" "$FU" && ok "reopen refreshes opened date" || fail "reopen opened date"

# ---- query project / capture task --this-week / extract-tasks ---------------------
"$BRAIN" capture task --desc "Review Lumen pricing page" --area internal --this-week >/dev/null
grep -q "status: this-week" "$BRAIN_ROOT/work/Tasks/internal-review-lumen-pricing-page.md" \
  && ok "capture task --this-week" || fail "capture task --this-week"
assert_contains "$(cat "$BRAIN_ROOT/work/Daily/2026-08-15.md")" \
  "[[Tasks/internal-review-lumen-pricing-page]]" "this-week task in daily priorities"
printf 'action items...\n' > "$BRAIN_ROOT/tx.txt"
"$BRAIN" extract-tasks --title "Potluck planning" --date 2026-08-13 \
  --transcript-file "$BRAIN_ROOT/tx.txt" \
  --task "book the community hall|internal|high" --task "email Rosa about tables|client|" >/dev/null
assert_file "work/Transcripts/potluck-planning-2026-08-13-transcript.md"
assert_file "work/Tasks/internal-book-community-hall.md"
grep -q 'source: "\[\[Transcripts/potluck-planning-2026-08-13-transcript\]\]"' \
  "$BRAIN_ROOT/work/Tasks/internal-book-community-hall.md" \
  && ok "extract-tasks source = transcript" || fail "extract-tasks source"
OUT=$("$BRAIN" query project "lumen")
assert_contains "$OUT" "Lumen Launch" "query project answers"

# ---- set / append / query show: every entity is editable and readable through the CLI
ER="$BRAIN_ROOT/edit-root"
mkdir -p "$ER/work" "$ER/personal"
eb() { BRAIN_ROOT="$ER" "$BRAIN" "$@"; }
EW="$ER/work"
assert_file_in() { [ -f "$1" ] && ok "exists ${1#$ER/}" || fail "missing ${1#$ER/}"; }
esnap() { snapshot "$EW"; }
expect_refused() {  # expect_refused "<label>" <command...>: exit 2 and nothing changed
  local label="$1"; shift
  local before; before=$(esnap)
  OUT=$("$@" 2>&1); local code=$?
  assert_exit $code "${WANT:-2}" "$label: exit ${WANT:-2}"
  assert_eq "$(esnap)" "$before" "$label: nothing written"
}

eb capture project --name "Harbor Rewrite" --area client >/dev/null
OUT=$(eb capture project --name "Harbor Rewrite" --area admin 2>&1)
assert_contains "$OUT" "UNCHANGED work/Projects/harbor-rewrite.md" "re-capturing a project prints UNCHANGED (never silent)"
assert_contains "$OUT" "brain set project harbor-rewrite --area admin" "re-capture hints at set for a different area"
printf 'Why a slow ferment works.\n' > "$ER/ref.txt"
eb capture note --title "bread notes" --body-file "$ER/ref.txt" >/dev/null
OUT=$(eb capture note --title "bread notes" --body-file "$ER/ref.txt" 2>&1)
assert_contains "$OUT" "UNCHANGED work/Reference/bread-notes.md" "re-capturing a note prints UNCHANGED (never silent)"
assert_contains "$OUT" "brain append reference bread-notes" "re-capture note hints at append"

# followup lifecycle
eb capture followup --who "Sam Ortiz" --about "shed key copy" >/dev/null
OUT=$(eb set followup sam-shed-key-copy --status done)
assert_contains "$OUT" "UPDATED work/Follow-ups/sam-shed-key-copy.md" "set followup done"
assert_contains "$(eb query waiting-on)" "(0)" "closed follow-up leaves waiting-on"
assert_contains "$(eb query followups --status done --who Sam)" "sam-shed-key-copy" "query followups --status done --who"
assert_contains "$(eb set followup sam-shed-key-copy --status done)" "UNCHANGED" "set is idempotent"
eb set followup sam-shed-key-copy --status waiting >/dev/null
grep -q "^opened: 2026-08-15" "$EW/Follow-ups/sam-shed-key-copy.md" && ok "reopen keeps opened = today" || fail "reopen opened"
eb set followup sam-shed-key-copy --about "spare shed key" >/dev/null
grep -q "^about: spare shed key" "$EW/Follow-ups/sam-shed-key-copy.md" && grep -q '^\*\*About:\*\* spare shed key' "$EW/Follow-ups/sam-shed-key-copy.md" \
  && ok "set followup --about updates frontmatter and body line" || fail "followup about"

# task edits
eb capture task --desc "Draft rewrite plan" --area client --project harbor-rewrite >/dev/null
T=client-draft-rewrite-plan
eb set task $T --priority high --status this-week >/dev/null
grep -q "^priority: high" "$EW/Tasks/$T.md" && grep -q "^week: 2026-W33" "$EW/Tasks/$T.md" \
  && ok "set task priority + this-week (week set)" || fail "set task priority/status"
grep -q "\[\[Tasks/$T\]\]" "$EW/Daily/2026-08-15.md" && ok "this-week lands in the daily Priority Tasks" || fail "daily priority line"
eb set task $T --status backlog >/dev/null
grep -q "^week:" "$EW/Tasks/$T.md" && fail "backlog keeps week" || ok "set task backlog drops week"
eb set task $T --status done >/dev/null
grep -q "^week: 2026-W33" "$EW/Tasks/$T.md" && ok "set task done fills week" || fail "done week"
eb set task $T --status backlog --owner "Sam Ortiz" >/dev/null
grep -q '^owner: "\?\[\[People/Sam-Ortiz\]\]' "$EW/Tasks/$T.md" && grep -q '^\*\*Owner:\*\* \[\[People/Sam-Ortiz\]\]' "$EW/Tasks/$T.md" \
  && ok "set task owner updates frontmatter and body line" || fail "task owner"
expect_refused "other people's tasks cannot enter the week" eb set task $T --status this-week
eb set task $T --owner me --desc "Draft the rewrite plan v2" >/dev/null
grep -q "^# Draft the rewrite plan v2" "$EW/Tasks/$T.md" && ok "set task --desc rewrites the H1, slug stays" || fail "task desc"
eb set task $T --project none >/dev/null
grep -q "^project: null" "$EW/Tasks/$T.md" && ok "set task --project none clears" || fail "project none"
expect_refused "unknown project" eb set task $T --project nope
expect_refused "unknown task" eb set task no-such-task --priority high
expect_refused "bad enum" eb set task $T --priority urgent
expect_refused "nothing to set" eb set task $T
expect_refused "wrong folder in ref" eb set task Follow-ups/sam-shed-key-copy --priority low
eb set task "[[Tasks/$T]]" --priority low >/dev/null && ok "ref accepts [[Folder/stem]]" || fail "wikilink ref"

# vault-level duplicate title is refused at write time
WANT=1 expect_refused "same title in another area is a duplicate task (lint refusal)" \
  eb capture task --desc "Draft the rewrite plan v2" --area internal --priority high
eb capture task --desc "Draft rewrite plan v3" --area client >/dev/null
OUT=$(eb capture task --desc "Draft rewrite plan v3" --area client --priority high 2>&1)
assert_contains "$OUT" "UPDATED work/Tasks/client-draft-rewrite-plan-v3.md" "an explicit priority updates the matched task"
OUT=$(eb capture task --desc "Draft rewrite plan v3" --area client --owner "Sam Ortiz" 2>&1)
assert_contains "$OUT" "keeps owner=" "capture task hints when an owner was not applied"
assert_contains "$OUT" "brain set task client-draft-rewrite-plan-v3 --owner" "hint names the exact set command"

# project lifecycle
eb set project harbor-rewrite --status paused >/dev/null
assert_contains "$(eb query projects --status paused)" "harbor-rewrite" "query projects --status paused"
assert_contains "$(eb query working-on)" "Active projects (0)" "paused project leaves working-on"
eb set project harbor --status active >/dev/null && ok "project ref accepts a unique substring" || fail "project substring"
eb set project harbor-rewrite --area admin >/dev/null
assert_contains "$(eb query projects --area admin)" "harbor-rewrite" "query projects --area"

# person edits keep body in step
eb capture person --name "Sam Ortiz" --role Plumber --email sam@example.org >/dev/null
OUT=$(eb capture person --name "Sam Ortiz" --role Director 2>&1)
assert_contains "$OUT" "keeps role='Plumber'" "capture person hints when role differs"
eb set person Sam --role Director --email none --org external >/dev/null
P="$EW/People/Sam-Ortiz.md"
grep -q "^role: Director" "$P" && grep -q "^email: null" "$P" && grep -q "^org: external" "$P" \
  && ok "set person frontmatter" || fail "set person frontmatter"
grep -q '^\*\*Role:\*\* Director' "$P" && grep -q '^\*\*Org:\*\* external' "$P" && ! grep -q '^\*\*Email:' "$P" \
  && ok "set person rewrites body lines (no drift)" || fail "person body drift"
eb capture person --name "Samira Khan" >/dev/null
expect_refused "ambiguous single-name person" eb set person Sam --role Boss

# interview edits and the round guard
eb capture interview --candidate "Ana Ruiz" --role "Staff Engineer" --round 1 --note "strong on systems" >/dev/null
I=ana-ruiz-staff-engineer-2026-08-15
expect_refused "a different round on the same day is refused" \
  eb capture interview --candidate "Ana Ruiz" --role "Staff Engineer" --round 2
eb set interview $I --verdict hire --round 2 >/dev/null
grep -q '^\*\*Verdict:\*\* hire' "$EW/Interviews/$I.md" && grep -q '^# Ana Ruiz — Staff Engineer — round 2' "$EW/Interviews/$I.md" \
  && ok "set interview verdict + round keep body in step" || fail "interview body drift"
eb capture interview --candidate "Ana Ruiz" --role "Staff Engineer" --round 2 --verdict no-hire >/dev/null
grep -q '^\*\*Verdict:\*\* no-hire' "$EW/Interviews/$I.md" && ok "capture interview --verdict updates the body line too" || fail "capture verdict drift"
assert_contains "$(eb query interviews --verdict no-hire)" "$I" "query interviews --verdict"
assert_contains "$(eb query interviews --candidate ana --role staff)" "$I" "query interviews --candidate --role"

# content publishing
printf 'A draft about ferments.\n' > "$ER/blog.txt"
eb capture note --title "Blog on ferments" --folder Content --body-file "$ER/blog.txt" >/dev/null
eb set content blog-ferments --status published >/dev/null
assert_contains "$(eb query notes --status published)" "blog-ferments" "query notes --status published"
assert_contains "$(eb query notes --folder Reference)" "bread-notes" "query notes --folder Reference"

# meeting edits
eb capture meeting --title "Harbor kickoff" --attendees "Sam Ortiz" --decision "ship Friday" >/dev/null
M=harbor-kickoff-2026-08-15
eb set meeting $M --add-attendee "Ana Ruiz" --remove-attendee "Sam Ortiz" --project harbor-rewrite >/dev/null
grep -q '^project: harbor-rewrite' "$EW/Meetings/$M.md" && grep -q '^\*\*Attendees:\*\* \[\[People/Ana-Ruiz\]\]$' "$EW/Meetings/$M.md" \
  && grep -q '^\*\*Project:\*\* \[\[Projects/harbor-rewrite\]\]' "$EW/Meetings/$M.md" \
  && ok "set meeting attendees/project keep body in step" || fail "set meeting"
expect_refused "removing a non-attendee" eb set meeting $M --remove-attendee "Sam Ortiz"
assert_contains "$(eb query meetings --project harbor-rewrite --attendee Ana)" "$M" "query meetings --project --attendee"
assert_contains "$(eb query meetings --until 2026-08-14)" "(0)" "query meetings --until"

# append: one fixed section per type, idempotent
printf 'Second thought: add salt.\n\n## Heading in prose\nmore\n' > "$ER/more.txt"
OUT=$(eb append reference bread-notes --file "$ER/more.txt")
assert_contains "$OUT" "UPDATED work/Reference/bread-notes.md" "append reference"
assert_contains "$(eb append reference bread-notes --file "$ER/more.txt")" "UNCHANGED" "append is idempotent"
grep -q '^\*\*Heading in prose\*\*' "$EW/Reference/bread-notes.md" && ok "append flattens headings like capture note" || fail "append headings"
eb append person "Sam Ortiz" --text "prefers async" >/dev/null
grep -q "^- 2026-08-15: prefers async" "$P" && ok "append person dated line" || fail "append person"
eb append followup sam-shed-key-copy --text "he called back" >/dev/null
grep -q "^## Updates" "$EW/Follow-ups/sam-shed-key-copy.md" && grep -q "he called back" "$EW/Follow-ups/sam-shed-key-copy.md" && ok "append followup" || fail "append followup"
eb append project harbor-rewrite --milestone "Kickoff" --text "Rewrite the harbor tooling." >/dev/null
grep -q "^- \[ \] Kickoff" "$EW/Projects/harbor-rewrite.md" && grep -q "Rewrite the harbor tooling" "$EW/Projects/harbor-rewrite.md" && ok "append project context + milestone" || fail "append project"
eb append meeting $M --decision "no scope creep" >/dev/null
assert_contains "$(eb query show Meetings/$M)" "no scope creep" "append meeting decision"
eb append interview $I --note "asked about oncall" >/dev/null
grep -q "asked about oncall" "$EW/Interviews/$I.md" && ok "append interview note" || fail "append interview"
eb append task $T --text "blocked on API" >/dev/null
grep -q "blocked on API" "$EW/Tasks/$T.md" && ok "append task" || fail "append task"
eb append content blog-ferments --text "One more paragraph." >/dev/null
grep -q "One more paragraph" "$EW/Content/blog-ferments.md" && ok "append content" || fail "append content"
eb append daily --log "worked on the harbor" --dump "idea: tide chart" >/dev/null
eb append daily 2026-08-14 --log "yesterday" >/dev/null
assert_file_in "$EW/Daily/2026-08-14.md"
grep -q "worked on the harbor" "$EW/Daily/2026-08-15.md" && grep -q "idea: tide chart" "$EW/Daily/2026-08-15.md" && ok "append daily --log/--dump" || fail "append daily"
expect_refused "append with no text" eb append reference bread-notes
expect_refused "append to a missing note" eb append reference no-such-note --text "x"
expect_refused "append to a transcript is not offered" eb append transcript x --text y
printf '' > "$ER/empty.txt"
expect_refused "append of an empty file" eb append reference bread-notes --file "$ER/empty.txt"

# edge cases found in review: refs, whitespace, prose safety, search folding
eb capture project --name "The Mobile Apps for Clients" >/dev/null
eb set project "The Mobile Apps for Clients" --status paused >/dev/null && ok "project ref works with the project's own name" || fail "project name ref"
expect_refused "junk project ref never matches" eb set project "???" --status done
expect_refused "a longer name does not fuzzy-match a shorter project" eb append project "Harbor Rewrite Extra Words" --milestone x
eb set project "mobile apps clients" --status active >/dev/null
printf 'Harbor\n' > "$ER/h.txt"
assert_contains "$(eb append project harbor-rewrite --text "Harbor")" "UPDATED" "append dedupes only within its own section (title text does not block it)"
eb set interview $I --round '2\' >/dev/null && ok "set interview round accepts a backslash" || fail "round backslash"
grep -q '^# Ana Ruiz — Staff Engineer — round 2\\ (2026-08-15)' "$EW/Interviews/$I.md" && ok "round rewrite touches only the round" || fail "round H1"
eb set interview $I --round 2 >/dev/null
eb capture interview --candidate "Lee Wu" --role "Playground Designer" --round 1 --note x >/dev/null
eb set interview lee-wu-playground-designer-2026-08-15 --round 2 >/dev/null
grep -q '^# Lee Wu — Playground Designer — round 2 (2026-08-15)' "$EW/Interviews/lee-wu-playground-designer-2026-08-15.md" \
  && ok "round rewrite leaves a role like 'Playground' alone" || fail "playground role"
eb set followup sam-shed-key-copy --about $'send keys\nand badge' >/dev/null
grep -q '^about: send keys and badge$' "$EW/Follow-ups/sam-shed-key-copy.md" && ok "newlines in a set value collapse to a space" || fail "newline about"
eb set followup sam-shed-key-copy --about "spare shed key" >/dev/null
eb capture task --desc "review budget" --area admin --this-week >/dev/null
expect_refused "reassigning a this-week task away from you needs --status backlog" eb set task admin-review-budget --owner "Sam Ortiz"
eb set task admin-review-budget --owner "Sam Ortiz" --status backlog >/dev/null && ok "reassign + backlog together works" || fail "reassign backlog"
expect_refused "--week on a backlog task" eb set task admin-review-budget --week 2026-W40
printf '\n## Notes\n\n**Email:** prefers Slack, not email\n\n```\nline a\n\n\n\nline b\n```\n' >> "$P"
assert_contains "$(eb lint)" "lint: clean" "prose that looks like a meta line below a section heading is not drift"
BEFORE_P=$(cat "$P")
eb lint --fix-safe >/dev/null
eb set person "Sam Ortiz" --email sam@example.org >/dev/null
grep -q 'prefers Slack, not email' "$P" && grep -q 'line a$' "$P" && grep -qx '' "$P" && ok "prose below headings survives set and --fix-safe" || fail "prose clobbered"
awk '/^```$/{f=!f; next} f' "$P" | tr '\n' '|' | grep -q '^line a||||line b|$' && ok "set does not collapse blank lines inside prose" || fail "blank lines collapsed"
printf 'The café menu and Zürich office.\n' > "$ER/acc.txt"
eb capture note --title "Office tour" --body-file "$ER/acc.txt" >/dev/null
assert_contains "$(eb query search café)" "Reference/office-tour" "query search finds accented words"
assert_contains "$(eb query search zurich)" "Reference/office-tour" "query search folds accents both ways"
eb append reference office-tour --text '#followup ask about the lease' >/dev/null
eb append reference office-tour --text 'Second paragraph.' >/dev/null
awk '/^## Notes/{f=1} f' "$EW/Reference/office-tour.md" | grep -n "" | grep -q 'Second paragraph' \
  && [ "$(grep -n 'Second paragraph' "$EW/Reference/office-tour.md" | cut -d: -f1)" -gt "$(grep -n '#followup' "$EW/Reference/office-tour.md" | cut -d: -f1)" ] \
  && ok "append keeps order when an earlier block starts with a #tag" || fail "tag ordering"

# round-2 review: whole-word project refs, paragraph dedupe, apostrophes, one-line capture flags
eb capture project --name "Rapid Prototyping" >/dev/null
expect_refused "a fragment of a word is not a project ref" eb append project api --milestone "v1"
eb set project prototyping --status active >/dev/null && ok "a whole word of the slug is a project ref" || fail "whole-word ref"
eb append project harbor-rewrite --text "Harbor Rewrite kickoff notes" >/dev/null
assert_contains "$(eb append project harbor-rewrite --text "kickoff")" "UPDATED" "text inside a longer line is still appended"
assert_contains "$(eb append project harbor-rewrite --text "kickoff")" "UNCHANGED" "a whole paragraph already there is not repeated"
printf "O'Brien's don't-list\n" > "$ER/ap.txt"
eb capture note --title "apostrophe list" --body-file "$ER/ap.txt" >/dev/null
assert_contains "$(eb query search "O'Brien")" "apostrophe-list" "query search handles apostrophes"
eb capture person --name "Cy Dee" --role $'Lead\nDev' >/dev/null
grep -q '^role: Lead Dev$' "$EW/People/Cy-Dee.md" && ok "capture collapses newlines in one-line flags" || fail "capture newline"

# one-note reads and new listings
OUT=$(eb query show Tasks/$T)
assert_contains "$OUT" "blocked on API" "query show prints the whole note"
assert_contains "$OUT" "- priority:" "query show lists the fields"
assert_contains "$(eb query show Daily/2026-08-14)" "yesterday" "query show a past daily note"
assert_contains "$(eb query show $T)" "# Draft the rewrite plan v2" "query show accepts a bare unique stem"
expect_refused "query show of nothing" eb query show Tasks/nope
assert_contains "$(eb query dailies --since 2026-08-15)" "Daily/2026-08-15" "query dailies --since"
assert_contains "$(eb query people --org external --text director)" "Sam-Ortiz" "query people --org --text"
assert_contains "$(eb query tasks --area client --priority low)" "$T" "query tasks --area --priority"
assert_contains "$(eb query tasks --week 2026-W33 --owner all)" "(0" "query tasks --week"
OUT=$(eb query search "scope creep")
assert_contains "$OUT" "Meetings/$M" "query search finds a decision"
assert_contains "$(eb query search "scope creep" --type task)" "(0)" "query search --type"
assert_contains "$(eb query transcripts)" "Transcripts (0)" "query transcripts (none yet)"

# ---- repo: multi-repo project tracking ---------------------------------------
RD="$ER/repo-dirs"
mkdir -p "$RD/harbor-api" "$RD/harbor-web" "$RD/unrelated"
# Each scratch dir is its own git repo boundary (as a real tracked repo would
# be) and carries no remote, so `git remote get-url origin` reports none
# rather than walking up and finding brain-kit's OWN remote.
for d in harbor-api harbor-web unrelated; do git init -q "$RD/$d"; done
(cd "$RD/harbor-api" && eb capture repo --name api --project harbor-rewrite --role api) >/dev/null
(cd "$RD/harbor-web" && eb capture repo --name web --project harbor-rewrite --role frontend) >/dev/null
assert_file_in "$EW/Repos/harbor-rewrite-api.md"
grep -q "^project: harbor-rewrite" "$EW/Repos/harbor-rewrite-api.md" \
  && ok "capture repo records its project" || fail "repo project field"
grep -qF -- "$(native "$RD/harbor-api")" "$EW/Repos/harbor-rewrite-api.md" \
  && ok "capture repo defaults path to cwd" || fail "repo path default"

expect_refused "capture repo with an unknown project" eb capture repo --name ghost --project no-such-project

# re-capturing merges without changing anything already set
BEFORE_API=$(cat "$EW/Repos/harbor-rewrite-api.md")
(cd "$RD/harbor-api" && eb capture repo --name api --project harbor-rewrite --role api) >/dev/null
assert_eq "$(cat "$EW/Repos/harbor-rewrite-api.md")" "$BEFORE_API" "re-capturing an unchanged repo is idempotent"

eb append repo harbor-rewrite-api --text "wired up the auth endpoint" >/dev/null
grep -q "wired up the auth endpoint" "$EW/Repos/harbor-rewrite-api.md" \
  && ok "append repo logs to Activity Log" || fail "append repo"
assert_contains "$(eb append repo harbor-rewrite-api --text "wired up the auth endpoint")" "UNCHANGED" \
  "append repo is idempotent"

# cwd auto-detect: path match, including a sibling's own activity log line
OUT=$(cd "$RD/harbor-api" && eb query repo)
assert_contains "$OUT" "[[Repos/harbor-rewrite-api]]" "query repo auto-detects by path"
assert_contains "$OUT" "harbor-rewrite-web" "query repo lists sibling repos"
assert_contains "$OUT" "wired up the auth endpoint" "query repo shows its own activity log"
OUT=$(cd "$RD/harbor-web" && eb query repo)
assert_contains "$OUT" "wired up the auth endpoint" "query repo shows a sibling's last activity line"

# no signal at all -> a clear, deterministic error naming known repos
OUT=$(cd "$RD/unrelated" && eb query repo 2>&1)
assert_contains "$OUT" "No repo note matches the current directory" "query repo: no auto-detect signal"
assert_contains "$OUT" "harbor-rewrite-api" "query repo: no-match error lists known repos"

# ambiguity: two repo notes sharing a path is a terminal error, never a
# silent fall-through to the (weaker) basename stage
eb capture repo --name docs --project harbor-rewrite --path "$RD/harbor-web" >/dev/null
OUT=$(cd "$RD/harbor-web" && eb query repo 2>&1)
assert_contains "$OUT" "share the same path" "query repo: ambiguous path is a terminal error"
eb set repo harbor-rewrite-docs --path none >/dev/null  # clear the collision

# explicit name lookup, set, and project/repos aggregation
assert_contains "$(eb query repo api)" "harbor-rewrite-api" "query repo <name> exact match"
eb set repo harbor-rewrite-web --status archived >/dev/null
assert_contains "$(eb query repos --status archived)" "harbor-rewrite-web" "query repos --status archived"
assert_contains "$(eb query repos --status active)" "harbor-rewrite-api" "query repos --status active"
OUT=$(eb query project harbor-rewrite)
assert_contains "$OUT" "## Repos (3)" "query project aggregates its repos"
assert_contains "$OUT" "harbor-rewrite-api" "query project lists a repo"

assert_contains "$(eb lint)" "lint: clean" "vault lints clean after repo tests"

# determinism: the same write twice leaves the vault byte-identical
BEFORE=$(esnap)
eb set task $T --priority low >/dev/null
eb set person Sam --role Director >/dev/null
eb append person "Sam Ortiz" --text "prefers async" >/dev/null
eb append daily --log "worked on the harbor" >/dev/null
assert_eq "$(esnap)" "$BEFORE" "repeating set/append changes nothing"

# lint stays clean after all of the above; drift is warned and fixable
assert_contains "$(eb lint)" "lint: clean" "vault lints clean after set/append"
sed -i.bak 's/^\*\*Role:\*\* Director/**Role:** Janitor/' "$P" && rm -f "$P.bak"
assert_contains "$(eb lint)" "disagrees with frontmatter role" "lint warns on body/frontmatter drift"
eb lint --fix-safe >/dev/null
grep -q '^\*\*Role:\*\* Director' "$P" && ok "lint --fix-safe repairs drift" || fail "fix-safe drift"
mkdir -p "$EW/Tasks"
printf -- '---\ntype: task\nschema: 1\ncreated: 2026-08-15\ntags:\n  - task\nstatus: backlog\nowner: "[[People/Sam-Ortiz]]"\nproject: ghost-project\narea: admin\npriority: low\nsource: null\n---\n\n# Ghost task\n\n**Owner:** [[People/Sam-Ortiz]]\n**Source:** —\n' > "$EW/Tasks/admin-ghost-task.md"
assert_contains "$(eb lint)" "no project note for 'ghost-project'" "lint warns on a task naming a missing project"
rm -f "$EW/Tasks/admin-ghost-task.md"

# ---- personal vault mode ------------------------------------------------------------
"$BRAIN" mode personal --because "in my personal brain, ..." >/dev/null
"$BRAIN" capture task --desc "Read pruning guide" --area learning >/dev/null
assert_file "personal/Tasks/learning-read-pruning-guide.md"
"$BRAIN" capture person --name "Cara Diaz" >/dev/null
grep -q "^org: external" "$BRAIN_ROOT/personal/People/Cara-Diaz.md" \
  && ok "personal-vault person defaults to org external" || fail "personal default org"
"$BRAIN" mode work --because "back to my work brain" >/dev/null

# ---- frontmatter policy: tags on every note, no frontmatter title -----------
for f in "work/Tasks/internal-order-seed-packets.md" "work/Daily/2026-08-15.md" \
         "work/Reference/compost-bin-guide.md" "work/People/Morgan-Blake.md" \
         "work/Follow-ups/morgan-library-room-booking.md"; do
  grep -q "^tags:" "$BRAIN_ROOT/$f" && ok "tags on $f" || fail "tags missing on $f"
  grep -q "^title:" "$BRAIN_ROOT/$f" && fail "frontmatter title on $f (H1 is the title)" \
    || ok "no frontmatter title on $f"
  grep -q "^# " "$BRAIN_ROOT/$f" && ok "H1 on $f" || fail "no H1 on $f"
done
python3 - "$BRAIN_ROOT/work/Reference/compost-bin-guide.md" <<'EOF'
import sys
p = sys.argv[1]
t = open(p).read().replace("tags:", "title: Some Prose Title\ntags:", 1)
open(p, "w").write(t)
EOF
"$BRAIN" lint >/dev/null 2>&1; assert_exit $? 1 "lint rejects a frontmatter title"
"$BRAIN" lint --fix-safe >/dev/null
"$BRAIN" lint >/dev/null; assert_exit $? 0 "fix-safe removes the frontmatter title"

# capture note refuses to write a title-only note
OUT=$("$BRAIN" capture note --title "Title only note" 2>&1)
assert_exit $? 2 "capture note without --body-file refused"
: > "$BRAIN_ROOT/blank.txt"
OUT2=$("$BRAIN" capture note --title "Blank body note" --body-file "$BRAIN_ROOT/blank.txt" 2>&1)
assert_exit $? 2 "capture note with an EMPTY --body-file refused"
assert_contains "$OUT2" "is empty" "empty-body refusal explains itself"
[ -f "$BRAIN_ROOT/work/Reference/blank-body-note.md" ] && fail "blank note written" \
  || ok "no blank note written"
assert_contains "$OUT" "requires --body-file" "body-file requirement explained"
[ -f "$BRAIN_ROOT/work/Reference/title-only-note.md" ] && fail "title-only note written" \
  || ok "no title-only note written"
grep -q "  - task" "$BRAIN_ROOT/work/Tasks/internal-order-seed-packets.md" \
  && ok "tags carries the note type" || fail "tags type value"

# ---- task owner: required, defaults to the vault owner, can be someone else ----
grep -q 'owner: "\[\[People/Maya-Chen\]\]"' "$BRAIN_ROOT/work/Tasks/internal-order-seed-packets.md" \
  && ok "meeting task defaults to the vault owner" || fail "default owner"
assert_file "work/People/Maya-Chen.md"
"$BRAIN" capture task --desc "bring the folding tables" --area internal \
  --owner "Jordan Hale" >/dev/null
PT="$BRAIN_ROOT/work/Tasks/internal-bring-folding-tables.md"
grep -q 'owner: "\[\[People/Jordan-Hale\]\]"' "$PT" \
  && ok "--owner files the task under someone else" || fail "--owner"
assert_file "work/People/Jordan-Hale.md"
grep -q "^\*\*Owner:\*\* \[\[People/Jordan-Hale\]\]" "$PT" \
  && ok "task body shows owner" || fail "task body owner line"
grep -q "^\*\*Source:\*\*" "$BRAIN_ROOT/work/Tasks/internal-order-seed-packets.md" \
  && ok "task body carries a source line, not a title repeat" || fail "task source line"
N=$(grep -c "order seed packets" "$BRAIN_ROOT/work/Tasks/internal-order-seed-packets.md")
assert_eq "$N" "1" "task body does not repeat the title as prose (H1 only)"

# owner-scoped queries: other people's action items stay out of the backlog
OUT=$("$BRAIN" query tasks)
echo "$OUT" | grep -q "internal-bring-folding-tables" \
  && fail "someone else's task leaked into the backlog" || ok "backlog is owner-scoped"
OUT=$("$BRAIN" query tasks --owner all)
assert_contains "$OUT" "internal-bring-folding-tables" "--owner all shows everything"
OUT=$("$BRAIN" query waiting-on)
assert_contains "$OUT" "Action items owed by others" "waiting-on has an owed-by-others section"
assert_contains "$OUT" "internal-bring-folding-tables" "waiting-on lists the owed item"
OUT=$("$BRAIN" promote --task internal-bring-folding-tables 2>&1)
assert_exit $? 2 "promoting someone else's task is refused"
assert_contains "$OUT" "owned by" "refusal names the owner"

# ---- a note built from a source must carry prose ----------------------------
OUT=$("$BRAIN" capture meeting --title "Empty sync" --date 2026-08-11 \
  --transcript-file "$BRAIN_ROOT/tr.txt" 2>&1)
assert_exit $? 2 "--transcript-file without --summary-file refused"
assert_contains "$OUT" "requires --summary-file" "summary requirement explained"
[ -f "$BRAIN_ROOT/work/Meetings/empty-sync-2026-08-11.md" ] \
  && fail "summary-less meeting written" || ok "nothing written when the summary is missing"
OUT=$("$BRAIN" capture interview --candidate "Pat Quinn" --role "Pastry Chef" \
  --round 2 --date 2026-08-11 --transcript-file "$BRAIN_ROOT/tr.txt" 2>&1)
assert_exit $? 2 "interview --transcript-file without assessment refused"
assert_contains "$OUT" "--assessment-file" "assessment requirement explained"

# repeatable --decision lands under ## Decisions
printf 'Raised 420 dollars across two tables.\n' > "$BRAIN_ROOT/sum2.txt"
"$BRAIN" capture meeting --title "Bake sale review" --date 2026-08-11 \
  --transcript-file "$BRAIN_ROOT/tr.txt" --summary-file "$BRAIN_ROOT/sum2.txt" \
  --decision "Use reusable cups from now on" \
  --decision "Next sale on the first Saturday of October" >/dev/null
M=$(cat "$BRAIN_ROOT/work/Meetings/bake-sale-review-2026-08-11.md")
assert_contains "$M" "## Decisions" "## Decisions section written"
assert_contains "$M" "- Use reusable cups from now on" "decision 1 present"
assert_contains "$M" "- Next sale on the first Saturday of October" "decision 2 present"
assert_contains "$M" "Raised 420 dollars across two tables." "summary present"
echo "$M" | grep -q "^## Links$" && fail "empty ## Links section kept" \
  || ok "empty template sections omitted"

# interview: --note / --assessment-file / --verdict
printf 'Calm under pressure; invite back for a trial shift.\n' > "$BRAIN_ROOT/assess.txt"
"$BRAIN" capture interview --candidate "Elena Novak" --role "Pastry Chef" \
  --round 2 --date 2026-08-11 --transcript-file "$BRAIN_ROOT/tr.txt" \
  --note "Plated a three-course tasting menu" \
  --note "Slow on laminated dough" \
  --assessment-file "$BRAIN_ROOT/assess.txt" --verdict hire >/dev/null
I=$(cat "$BRAIN_ROOT/work/Interviews/elena-novak-pastry-chef-2026-08-11.md")
assert_contains "$I" "verdict: hire" "verdict set from an explicit recommendation"
assert_contains "$I" "## Assessment" "## Assessment section written"
assert_contains "$I" "invite back for a trial shift" "assessment prose present"
assert_contains "$I" "- Slow on laminated dough" "--note bullets present"

# ---- daily notes: full template body, never empty ----------------------------
rm -f "$BRAIN_ROOT/work/Daily/2026-08-10.md"
"$BRAIN" extract-tasks --title "Potluck notes" --date 2026-08-10 \
  --transcript-file "$BRAIN_ROOT/tx.txt" --task "confirm the dessert list" >/dev/null
D=$(cat "$BRAIN_ROOT/work/Daily/2026-08-10.md")
assert_contains "$D" "## Brain Dump" "extract-tasks daily has the template body"
assert_contains "$D" "[[Tasks/internal-confirm-dessert-list]]" "extract-tasks daily links its task"
assert_contains "$D" "## Waiting On" "daily has a Waiting On section"

# project inference is identical on the meeting path and the extract-tasks path
"$BRAIN" extract-tasks --title "Lumen Launch sync" --date 2026-08-10 \
  --task "draft the Lumen summary" >/dev/null
grep -q "^project: lumen-launch" "$BRAIN_ROOT/work/Tasks/internal-draft-lumen-summary.md" \
  && ok "extract-tasks infers project from --title like capture meeting" \
  || fail "extract-tasks project inference"

# ---- two-vault env resolution (no common parent required) ---------------------
TWO="$BRAIN_ROOT/two"
rm -rf "$TWO"; mkdir -p "$TWO/a/vault-work" "$TWO/b/some other place/vault-personal" "$TWO/state"
twoenv() {
  env -u BRAIN_ROOT BRAIN_WORK_VAULT="$TWO/a/vault-work" \
    BRAIN_PERSONAL_VAULT="$TWO/b/some other place/vault-personal" \
    BRAIN_STATE_DIR="$TWO/state" "$BRAIN" "$@"
}
OUT=$(twoenv status 2>&1)
assert_exit $? 0 "two-vault env resolves with no common parent"
assert_contains "$OUT" "$(native "$TWO/a/vault-work")" "work vault path reported"
assert_contains "$OUT" "vault-personal" "personal vault path reported"
assert_contains "$OUT" "config: BRAIN_WORK_VAULT+BRAIN_PERSONAL_VAULT" "config source reported"
twoenv mode personal --because "use my personal vault" >/dev/null
assert_eq "$(cat "$TWO/state/.brain-mode")" "personal" "mode file honours BRAIN_STATE_DIR"
twoenv capture task --desc "two vault write" --area internal >/dev/null 2>&1
assert_file "two/b/some other place/vault-personal/Tasks/internal-two-vault-write.md"
OUT=$(env -u BRAIN_ROOT BRAIN_WORK_VAULT="$TWO/nope-a" \
  BRAIN_PERSONAL_VAULT="$TWO/nope-b" "$BRAIN" status 2>&1)
assert_exit $? 2 "no existing vault directory -> clean error"
assert_contains "$OUT" "brain init" "missing-vault error points to brain init"
OUT=$(env -u BRAIN_ROOT "$BRAIN" status 2>&1)
assert_exit $? 2 "no vault configured at all -> clean error"
assert_contains "$OUT" "brain init" "unconfigured error points to brain init"
assert_contains "$OUT" "BRAIN_WORK_VAULT" "unconfigured error names the env vars"
OUT=$(env -u BRAIN_OWNER "$BRAIN" capture task --desc "x" --area internal 2>&1)
assert_exit $? 2 "write without an owner refused"
assert_contains "$OUT" "brain init --owner" "missing-owner error points to brain init"

# ---- captured prose lands INSIDE the wrapper section --------------------------
printf '## Why it matters\nPeople came back when we labelled every packet.\n\n## What changed\nWe sorted seeds by season first.\n' > "$BRAIN_ROOT/draft.md"
"$BRAIN" capture note --title "lessons from our first seed swap" --folder Content \
  --body-file "$BRAIN_ROOT/draft.md" >/dev/null
C=$(cat "$BRAIN_ROOT/work/Content/lessons-first-seed-swap.md")
assert_contains "$C" "## Draft" "content note keeps its wrapper section"
assert_contains "$C" "**Why it matters**" "body headings flattened to bold leads"
echo "$C" | awk '/^## Draft/{f=1;next} /^#/{f=0} f' | grep -q "People came back" \
  && ok "prose sits inside ## Draft" || fail "prose escaped the wrapper section"
echo "$C" | grep -q "^## Why it matters" && fail "body heading still closes the wrapper" \
  || ok "no competing ## heading in the body"

# ---- the mode gate: no implicit switch, ever --------------------------------
"$BRAIN" mode work --because "back to my work brain" >/dev/null 2>&1
OUT=$("$BRAIN" mode personal 2>&1)
assert_exit $? 2 "mode switch without --because refused"
assert_contains "$OUT" "requires --because" "refusal explains the requirement"
assert_eq "$("$BRAIN" mode)" "mode: work" "mode unchanged after refusal"
# a --because that does not name the target vault is not an explicit request
OUT=$("$BRAIN" mode personal --because "get a blog draft started in my brain" 2>&1)
assert_exit $? 2 "--because that never names the personal vault is refused"
assert_eq "$("$BRAIN" mode)" "mode: work" "mode unchanged after a self-justified switch"
OUT=$("$BRAIN" mode personal --because "this feels like a personal topic" 2>&1)
assert_exit $? 2 "topic-flavoured justification refused"
# a quote whose only mention of the target vault is negated is refused
for Q in "put this in my work brain, not my personal one" \
         "not my personal brain" \
         "never in my personal vault"; do
  OUT=$("$BRAIN" mode personal --because "$Q" 2>&1)
  assert_exit $? 2 "negated quote refused: $Q"
  assert_eq "$("$BRAIN" mode)" "mode: work" "mode unchanged: $Q"
done
"$BRAIN" mode personal --because "switch to my personal brain" >/dev/null 2>&1
"$BRAIN" mode work --because "put this in my work brain, not my personal one" >/dev/null 2>&1
assert_eq "$("$BRAIN" mode)" "mode: work" "negated other vault does not block the target"
"$BRAIN" mode personal --because "switch to personal, I'm done with my work for today" >/dev/null 2>&1
assert_eq "$("$BRAIN" mode)" "mode: personal" "mentioning the other vault does not block the target"
"$BRAIN" mode work --because "back to my work brain" >/dev/null 2>&1
for Q in "switch to my personal brain" "in my personal brain, add a note" \
         "put this in my personal vault" "switch to personal"; do
  "$BRAIN" mode work --because "back to my work brain" >/dev/null 2>&1
  "$BRAIN" mode personal --because "$Q" >/dev/null 2>&1
  assert_eq "$("$BRAIN" mode)" "mode: personal" "explicit switch works: $Q"
done
for Q in "switch back to my work brain" "in my work brain" "switch to work"; do
  "$BRAIN" mode personal --because "switch to my personal brain" >/dev/null 2>&1
  "$BRAIN" mode work --because "$Q" >/dev/null 2>&1
  assert_eq "$("$BRAIN" mode)" "mode: work" "explicit switch back works: $Q"
done
OUT=$("$BRAIN" mode work 2>&1)
assert_exit $? 0 "re-asserting the active mode is a no-op"
assert_contains "$OUT" "already active" "no-op is announced"

# ---- single-token names never fork a person ---------------------------------
"$BRAIN" capture person --name "Taylor Brooks" --org internal >/dev/null
OUT=$("$BRAIN" capture followup --who "Taylor" --about "raffle prize list" 2>&1)
assert_exit $? 0 "single-token --who resolves to the existing full-name note"
[ -f "$BRAIN_ROOT/work/People/Taylor.md" ] && fail "single-name People/Taylor.md forked" \
  || ok "no forked single-name person note"
grep -q 'who: "\[\[People/Taylor-Brooks\]\]"' \
  "$BRAIN_ROOT/work/Follow-ups/taylor-raffle-prize-list.md" \
  && ok "follow-up links the existing person" || fail "follow-up who wikilink"
"$BRAIN" capture person --name "Taylor Reed" --org internal >/dev/null
OUT=$("$BRAIN" capture task --desc "update the gate code" --area internal \
  --owner "Taylor" 2>&1)
assert_exit $? 2 "ambiguous single-token name refused"
assert_contains "$OUT" "People/Taylor-Brooks" "refusal lists candidate 1"
assert_contains "$OUT" "People/Taylor-Reed" "refusal lists candidate 2"
assert_contains "$OUT" "Nothing was written" "ambiguous refusal writes nothing"
[ -f "$BRAIN_ROOT/work/Tasks/internal-update-gate-code.md" ] \
  && fail "task written despite ambiguous owner" || ok "nothing written on ambiguity"
"$BRAIN" capture task --desc "update the gate code" --area internal \
  --owner "Taylor Reed" >/dev/null
grep -q 'owner: "\[\[People/Taylor-Reed\]\]"' \
  "$BRAIN_ROOT/work/Tasks/internal-update-gate-code.md" \
  && ok "full name disambiguates" || fail "full-name owner"
"$BRAIN" lint >/dev/null; assert_exit $? 0 "vault lints after the person guards"

# ---- doctor -------------------------------------------------------------------
OUT=$("$BRAIN" doctor --vault work)
assert_exit $? 0 "doctor exit 0 on clean vault"
assert_contains "$OUT" "doctor: healthy" "doctor reports healthy"
printf -- '---\ntype: reference\nschema: 1\ncreated: 2026-08-15\ntags: [reference]\n---\n# Lonely\n\nSee [[Nowhere-Note]].\n' \
  > "$BRAIN_ROOT/work/Reference/lonely.md"
OUT=$("$BRAIN" doctor --vault work)
assert_contains "$OUT" "ORPHAN Reference/lonely.md" "doctor flags orphan"
assert_contains "$OUT" "BROKEN Reference/lonely.md" "doctor flags broken link"
rm "$BRAIN_ROOT/work/Reference/lonely.md"

# ---- brain init + config file + org domain ------------------------------------
# Runs with no vault/owner env at all, so everything comes from the config file.
CFGHOME="$BRAIN_ROOT/init-config"
STATEHOME="$BRAIN_ROOT/init-state"
IV="$(cd "$BRAIN_ROOT" && pwd -P)/init-vaults"  # init stores resolved paths
CFG="$CFGHOME/second-brain/config"
cb() {
  env -u BRAIN_ROOT -u BRAIN_OWNER -u BRAIN_WORK_VAULT -u BRAIN_PERSONAL_VAULT \
    -u BRAIN_STATE_DIR -u BRAIN_ORG_DOMAIN \
    XDG_CONFIG_HOME="$CFGHOME" XDG_STATE_HOME="$STATEHOME" "$BRAIN" "$@"
}
OUT=$(cb init 2>&1)
assert_exit $? 2 "init with no vault refused"
OUT=$(cb init --work-vault "$IV/work" --personal-vault "$IV/personal" \
  --owner "Maya Chen" --org-domain example.com 2>&1)
assert_exit $? 0 "init exit 0"
[ -f "$CFG" ] && ok "init writes the config file" || fail "config file missing"
C=$(cat "$CFG")
assert_contains "$C" "BRAIN_WORK_VAULT=$(native "$IV/work")" "config has the work vault"
assert_contains "$C" "BRAIN_PERSONAL_VAULT=$(native "$IV/personal")" "config has the personal vault"
assert_contains "$C" "BRAIN_OWNER=Maya Chen" "config has the owner"
assert_contains "$C" "BRAIN_ORG_DOMAIN=example.com" "config has the org domain"
for d in Daily Meetings Transcripts Interviews Projects People Tasks Follow-ups \
         Content Reference _templates; do
  [ -d "$IV/work/$d" ] && [ -d "$IV/personal/$d" ] && ok "init created $d/ in both vaults" \
    || fail "init missing $d/"
done
for f in README.md Tasks.base _templates/Task.md _templates/Person.md; do
  [ -f "$IV/work/$f" ] && ok "init wrote work/$f" || fail "init missing work/$f"
done
grep -q '\[\[People/Maya-Chen\]\]' "$IV/work/Tasks.base" \
  && ok "Tasks.base carries the owner link" || fail "Tasks.base owner"
grep -q "^org: internal" "$IV/work/_templates/Person.md" \
  && ok "work Person template defaults to internal" || fail "work Person template org"
grep -q "^org: external" "$IV/personal/_templates/Person.md" \
  && ok "personal Person template defaults to external" || fail "personal Person template org"
grep -q "^schema: 1" "$IV/work/_templates/Task.md" \
  && ok "templates carry schema: 1" || fail "template schema"
OUT=$(cb status)
assert_exit $? 0 "status works from the config file alone"
assert_contains "$OUT" "owner: Maya Chen" "owner read from config file"
assert_contains "$OUT" "org domain: example.com" "org domain read from config file"
assert_contains "$OUT" "($(native "$CFG"))" "status names the config file as the source"
cb lint >/dev/null; assert_exit $? 0 "freshly initialised vaults lint clean"

# org domain: emails at the domain are internal, others external
cb capture person --name "Ana Ruiz" --email ana@example.com >/dev/null
grep -q "^org: internal" "$IV/work/People/Ana-Ruiz.md" \
  && ok "email at BRAIN_ORG_DOMAIN -> internal" || fail "org domain internal"
cb capture person --name "Ben Cole" --email ben@example.org >/dev/null
grep -q "^org: external" "$IV/work/People/Ben-Cole.md" \
  && ok "email at another domain -> external" || fail "org domain external"
cb mode personal --because "switch to my personal brain" >/dev/null
[ -f "$STATEHOME/second-brain/.brain-mode" ] && ok "mode file lives in XDG_STATE_HOME" \
  || fail "mode file location"
cb capture person --name "Dev Shah" --email dev@example.com >/dev/null
grep -q "^org: internal" "$IV/personal/People/Dev-Shah.md" \
  && ok "org domain applies in the personal vault too" || fail "personal org domain"
cb mode work --because "back to my work brain" >/dev/null

# env overrides the file
OUT=$(env -u BRAIN_ROOT XDG_CONFIG_HOME="$CFGHOME" XDG_STATE_HOME="$STATEHOME" \
  BRAIN_OWNER="Sam Ortiz" "$BRAIN" status)
assert_contains "$OUT" "owner: Sam Ortiz" "BRAIN_OWNER env overrides the config file"

# init without an owner leaves a placeholder; a later init with an owner
# fills it in, but never touches a file the user edited
PV="$(cd "$BRAIN_ROOT" && pwd -P)/ph-vaults"
PH="$BRAIN_ROOT/ph-config"
ph() {
  env -u BRAIN_ROOT -u BRAIN_OWNER -u BRAIN_WORK_VAULT -u BRAIN_PERSONAL_VAULT \
    -u BRAIN_STATE_DIR XDG_CONFIG_HOME="$PH" XDG_STATE_HOME="$STATEHOME" "$BRAIN" "$@"
}
OUT=$(ph init --work-vault "$PV/work" 2>&1)
assert_contains "$OUT" "no usable owner" "init without owner warns"
grep -qF '[[People/OWNER]]' "$PV/work/Tasks.base" && ok "placeholder before owner is known" \
  || fail "placeholder missing"
echo "# my edit" >> "$PV/work/_templates/Follow-up.md"
ph init --owner "Maya Chen" >/dev/null
for f in Tasks.base _templates/Task.md README.md; do
  grep -qF '[[People/OWNER]]' "$PV/work/$f" && fail "placeholder left in $f" \
    || ok "owner filled into $f"
done
grep -qF '[[People/Maya-Chen]]' "$PV/work/Tasks.base" && ok "Tasks.base has the owner link" \
  || fail "Tasks.base owner link"
grep -qF '[[People/OWNER]]' "$PV/work/_templates/Follow-up.md" \
  && ok "user-edited file left untouched" || fail "edited file was rewritten"

# a non-Latin owner is refused before anything is written, and a bad value
# already in the config never blocks --help, status or init
NL="$BRAIN_ROOT/nl-config"
nl() {
  env -u BRAIN_ROOT -u BRAIN_OWNER -u BRAIN_WORK_VAULT -u BRAIN_PERSONAL_VAULT \
    -u BRAIN_STATE_DIR XDG_CONFIG_HOME="$NL" XDG_STATE_HOME="$STATEHOME" "$BRAIN" "$@"
}
OUT=$(nl init --work-vault "$PV/work" --owner "李雷" 2>&1)
assert_exit $? 2 "init --owner with no Latin letters refused"
assert_contains "$OUT" "Nothing was written" "non-Latin owner refusal writes nothing"
[ -f "$NL/second-brain/config" ] && fail "config written despite bad owner" \
  || ok "no config written for a bad owner"
mkdir -p "$NL/second-brain"
printf 'BRAIN_WORK_VAULT=%s\nBRAIN_OWNER=李雷\n' "$(native "$PV/work")" > "$NL/second-brain/config"
nl --help >/dev/null 2>&1; assert_exit $? 0 "--help works with a bad owner in config"
OUT=$(nl status 2>&1)
assert_exit $? 0 "status works with a bad owner in config"
assert_contains "$OUT" "INVALID" "status flags the bad owner"
OUT=$(nl capture task --desc "water the ferns" --area internal 2>&1)
assert_exit $? 2 "writes refused with a bad owner"
assert_contains "$OUT" "brain init --owner" "bad-owner error points to brain init"
nl init --owner "Maya Chen" >/dev/null 2>&1; assert_exit $? 0 "init can overwrite a bad owner"
assert_contains "$(nl status)" "owner: Maya Chen" "owner fixed by init"

# re-running init merges into the config and never overwrites vault files
echo "my own notes" >> "$IV/work/README.md"
OUT=$(cb init --org-domain example.net 2>&1)
assert_exit $? 0 "re-run init exit 0"
C=$(cat "$CFG")
assert_contains "$C" "BRAIN_WORK_VAULT=$(native "$IV/work")" "re-run init keeps the vault paths"
assert_contains "$C" "BRAIN_ORG_DOMAIN=example.net" "re-run init updates the given key"
grep -q "my own notes" "$IV/work/README.md" \
  && ok "re-run init leaves existing files alone" || fail "init overwrote README"

echo
if [ "$FAILS" -eq 0 ]; then
  echo "SELFTEST PASS ($PASSES assertions)"
  exit 0
else
  echo "SELFTEST FAIL ($FAILS failures, $PASSES passed)"
  exit 1
fi
