---
status: resolved
trigger: "04-50 clean re-qualification halts with snapshot-inventory-mismatch in create_snapshot (tools/verify_playable.py:352) before RetroArch launches"
created: 2026-10-10
updated: 2026-10-10
workstream: first-playable-game
phase: 04-public-playable-tracer
plan: 04-50
---

# Debug: snapshot-inventory-mismatch

## Symptoms

- **Expected:** `python3 tools/verify_playable.py --retroarch /Applications/RetroArch.app --clean --check-docs` at the qualified revision materializes the committed Git archive snapshot, the materialized inventory equals the archive member rows, and the run proceeds to the RetroArch qualification launch, refreshing `build/playable-qualification/receipt.json`.
- **Actual:** The runner fails before any RetroArch launch. Run log (`build/playable-qualification/04-50-run.log`): `{"reason": "snapshot-inventory-mismatch", "receipt": "build/playable-qualification/receipt.json", "retroarch_status": "unknown", "status": "fail"}`; exit 1 (`04-50-exit.txt`).
- **Error:** `SnapshotError("snapshot-inventory-mismatch", "materialized source inventory differs from archived member bytes")` raised in `create_snapshot` where `inventory_tree(destination) != archive_rows` (tools/verify_playable.py ~line 352).
- **Timeline:** First seen in plan 04-50 (round-4 gap closure) at revision a580e858232fc143c204aaf1980386368644e4c9 (qualified rev == start rev). Earlier rounds produced the existing (stale) receipt bound to 3d90990e5cd0, so the snapshot path worked at that revision. Round-4 plans 04-43..04-48 changed tooling (frontmatter/GFM scanners, verify_playable setup-error token and entry() exit handling, rollback cleanup, lane output, anchor descent, ID patterns, pid-record diagnostic) and 04-50 refreshed the rights inventory for changed test sources.
- **Reproduction:** At HEAD of `docs/first-playable-game-milestone`, run `python3 tools/verify_playable.py --retroarch /Applications/RetroArch.app --clean --check-docs`. The 04-50 executor's manual re-materialization of the same archive in a scratch directory produced 580 identical rows, so the mismatch may depend on the runner's actual destination path, inventory_tree behaviour on that destination (e.g. ignore rules, symlinks, extra/missing files, mode bits, umask, case/Unicode normalization), or something the runner writes into the destination before/while inventorying.

## Constraints

- Never launch more than one RetroArch instance; clean up leftover RetroArch processes before and after any launch (`pgrep -x RetroArch`). Prefer reproducing via `create_snapshot` directly without a RetroArch launch.
- Commercial ROMs/BIOS, private captures and private test outputs stay out of Git. Do not print secrets or dump environments. Do not commit personal absolute paths.
- Leave `.planning/preparation/2026-10-04-gsd-verification-loop.md` (modified) and `.planning/preparation/2026-10-09-sibling-lessons.md` (untracked) untouched and unstaged; leave the `local/qualification/phase05-safe-candidate` worktree alone.
- Do not close any security register row or flip any requirement status; that happens only via the phase workflows.
- Fixes require a failing regression test first, then the fix, in tools tests (match existing test style).

## Current Focus

round: 3 complete; human-verify confirmed at 2ac2097 (full clean qualification passed)
bug_class: Bohrbug
hypothesis: confirmed; see Resolution cause (3)
next_action: "none; session resolved and archived. 04-50 receipt/ledger/register updates belong to the next plan round"
reasoning_checkpoint:
  hypothesis: "run_script_entry ran the real snapshot tools/verify_playable.py __main__; main() does OUTPUT.mkdir(parents=True) for ROOT/build/playable-qualification before the patched mkdtemp, so full-sdk-ctest left empty source/build/playable-qualification dirs. inventory_tree skips directories, so verify_snapshot passed, but Runner.command's build_link.exists() check then raised generated-output-path-conflict"
  confirming_evidence:
    - "halted run snapshot clean-ujqpzqlx/source/build holds only an empty playable-qualification dir; so does the 04-50 snapshot clean-jjvaqtcz"
    - "regression RED: copied tools root gained build/ and build/playable-qualification after the entry child ran"
  falsification_test: "after the fix, a Runner replay on a HEAD snapshot through full ctest would still show new directories or source/build"
  fix_rationale: "the child now runs a test-owned copy, so its ROOT/OUTPUT resolve inside the test temp dir, never the checked source tree"
  blind_spots: "RetroArch smoke lane and the real ym2610 link lane not re-run here; verify_snapshot still cannot see added empty directories"
  candidate_causes:
    - "code: test child resolves ROOT from the real script path"
    - "code/design: inventory_tree is file-only, so verify_snapshot cannot detect new empty directories"
  and_gate: "yes: the stray mkdir needs the directory-blind inventory to slip past verify_snapshot; fixing the test removes the trigger"

## Evidence

- timestamp: 2026-10-10
  checked: create_snapshot(ROOT, a580e85, scratch) + verify_snapshot directly
  found: succeeds, 580 rows
  implication: failure is not in create_snapshot; the debug trigger misattributed the raise site (verify_snapshot shares the reason token)
- timestamp: 2026-10-10
  checked: build/playable-qualification/receipt.json (04-50 run)
  found: 12 lanes pass through consumer-shared-check; no full-sdk-ctest lane recorded; documentation reason "materialized source inventory changed after archive creation"
  implication: Runner.command post-lane verify_snapshot after full-sdk-ctest raised
- timestamp: 2026-10-10
  checked: scratch repro (snapshot, shared Debug build, install, full ctest under clean_environment), inventory diff
  found: single added path tools/__pycache__/private_paths.cpython-314.pyc
  implication: a CTest test writes bytecode into the snapshot
- timestamp: 2026-10-10
  checked: per-test ctest -R bisection
  found: only qualification_runner writes it; tests/tools/test_verify_playable.py run_script_entry uses [sys.executable, "-I", "-c", code] (f4961f3, 04-44)
  implication: -I ignores PYTHONDONTWRITEBYTECODE set by clean_environment
- timestamp: 2026-10-10
  checked: qualification_runner output inside snapshot
  found: FAILED (errors=10) in ReviewProvenanceTest ("reviewed revision ... is not a committed ancestor of the checked head") - snapshot has no .git
  implication: separate defect; the full-sdk-ctest lane will still fail after the bytecode fix

- timestamp: 2026-10-10
  checked: regression test test_entry_child_writes_no_bytecode_into_the_source_tools before fix
  found: FAILS (tools/ gains __pycache__) even with PYTHONDONTWRITEBYTECODE=1 in the parent; passes after adding -B
  implication: test reproduces the mechanism and bites on revert
- timestamp: 2026-10-10
  checked: in-repo snapshot of the fixed HEAD (under build/playable-qualification/), qualification_runner run directly
  found: snapshot unchanged, but 1 error - check_docs "review round file 04-REVIEW-GAPS.md for GWR-01 is not committed at the checked head"
  implication: second, independent lane blocker (AND-gate): ReviewProvenanceTest uses ROOT (the snapshot) as the Git repository; _review_round_anchor's repo-relative pathspec is resolved under the -C subdirectory. Production passes repository=ROOT of the real checkout and is unaffected. 8 such tests lack the suite's existing skipUnless((ROOT / ".git").exists()) guard.
- timestamp: 2026-10-10
  checked: real Runner.command replay on an in-repo HEAD (a872c5a) snapshot: shared configure/build/install, full-sdk-ctest, z80-source, ym2610-source, check_docs, verify_snapshot after each
  found: all pass (full-sdk-ctest exit 0), snapshot inventory unchanged; no RetroArch launched (pgrep before/after empty)
  implication: the runner now gets past the point where 04-50 halted; only the RetroArch smoke and ym2610-installed-linkages lanes remain unexercised by this replay

- timestamp: 2026-10-10
  checked: manager full run at a872c5a and the leftover snapshots clean-ujqpzqlx/source and clean-jjvaqtcz/source
  found: both contain build/playable-qualification as empty directories; all lanes through ym2610-source passed, then the ym2610-installed-linkages overlay raised generated-output-path-conflict
  implication: something mkdirs ROOT/build/playable-qualification inside the snapshot; inventory_tree skips directories so verify_snapshot cannot see it
- timestamp: 2026-10-10
  checked: tests/tools/test_verify_playable.py run_script_entry + tools/verify_playable.py main()
  found: the child runs the real script via runpy; main() calls OUTPUT.mkdir(parents=True) before the patched tempfile.mkdtemp
  implication: each entry test creates ROOT/build/playable-qualification under whatever tree hosts the script (a no-op in the checkout, where build/ already exists)
- timestamp: 2026-10-10
  checked: extended regression test_entry_child_writes_nothing_into_the_source_tree before/after the fix
  found: RED before (extra build, build/playable-qualification); GREEN after; full suite 102 OK
  implication: the test reproduces the mechanism and fails on revert
- timestamp: 2026-10-10
  checked: real Runner.command replay on an in-repo snapshot of 2ac2097: shared configure/build/install, full ctest, then an overlay-probe lane with source_build_overlay
  found: ctest exit 0; no new directories in the snapshot; no source/build; overlay lane passes and the link is removed afterwards; no RetroArch launched
  implication: the generated-output-path-conflict trigger is gone
- timestamp: 2026-10-10
  checked: session-manager full clean qualification at HEAD 2ac2097 (`python3 tools/verify_playable.py --retroarch /Applications/RetroArch.app --clean --check-docs`), `pgrep -x RetroArch` empty before and after
  found: exit 0; final line {"reason": "", "retroarch_status": "pass", "status": "pass", "fixture_sha256": "59ed3645b156db15e20599ab71f40d416f870472078e8f6751d2174afe7a5cf0"}; build/playable-qualification/receipt.json refreshed (log kept in a scratch directory outside the repo)
  implication: original symptom gone end to end, including the RetroArch smoke and ym2610-installed-linkages lanes the replays did not exercise

## Eliminated

- hypothesis: create_snapshot materialization mismatch (destination path, mode bits, symlinks, normalization)
  evidence: direct create_snapshot + verify_snapshot at a580e85 pass with 580 rows; the raise came from verify_snapshot after the full-sdk-ctest lane
  timestamp: 2026-10-10
- hypothesis: rights-inventory refresh in a580e85 changed archived paths
  evidence: a580e85 only edits docs/rights-inventory.md hashes; inventory diff shows only an added .pyc
  timestamp: 2026-10-10

## Resolution

- root_cause: (1) run_script_entry ran `python -I -c ...`. -I ignores PYTHONDONTWRITEBYTECODE, so the child wrote tools/__pycache__ into the snapshot during full-sdk-ctest and verify_snapshot raised snapshot-inventory-mismatch. (2) Eight ReviewProvenanceTest cases read ROOT's Git history and fail inside the snapshot. (3) run_script_entry ran the real snapshot tools/verify_playable.py __main__. main() does OUTPUT.mkdir(parents=True) before the patched mkdtemp, which created empty build/playable-qualification directories in the snapshot. inventory_tree is file-only, so verify_snapshot passed, but the ym2610-installed-linkages overlay raised generated-output-path-conflict.
- fix: -B on the child (2f5e771); skipUnless .git guard on the eight tests (157b49d); run_script_entry copies verify_playable.py and private_paths.py into its temporary root and runs that copy, and the regression asserts the source tree gains nothing (9ca1fbe); rights-inventory refreshes (9b710de, a872c5a, 2ac2097).
- oracle_type: specified (the source tree hosting the entry modules is byte- and path-identical after the child runs)
- verification: regression RED before / GREEN after; test_verify_playable.py 102 OK; Runner replay on a 2ac2097 snapshot: full ctest passes, no new directories, overlay lane passes; public_content rights inventory passes. Human-verify: session-manager full clean qualification at 2ac2097 exit 0, status pass, retroarch_status pass, fixture_sha256 59ed3645b156db15e20599ab71f40d416f870472078e8f6751d2174afe7a5cf0, single RetroArch instance (pgrep empty before/after), receipt.json refreshed (untracked build output; 04-50 receipt/ledger/register artifacts deferred to the next plan round).
- guardrail_verdict: accepted
- follow_up: (not changed in this session) verify_snapshot cannot detect added empty directories (inventory_tree skips dirs). A directory-set check would catch this class at the offending lane instead of at the later overlay. Not changed here (minimal fix).
- files_changed: [tests/tools/test_verify_playable.py, docs/rights-inventory.md]

## Prevention (blameless postmortem)

Branching 5-Whys (AND-gate fired; three contributing causes):

- Why did 04-50 halt? verify_snapshot after full-sdk-ctest found an extra tools/__pycache__ .pyc.
  - Why was bytecode written? The entry test child ran `python -I`, and -I ignores PYTHONDONTWRITEBYTECODE, which clean_environment relied on.
    - Why not caught? The test suite had only ever run inside the Git checkout, where stray bytecode is ignored; no test asserted the hosting tree stays unchanged.
- Why would the lane still fail after that? Eight ReviewProvenanceTest cases read Git history from ROOT, and the snapshot has no .git.
  - Why not caught? The suite already had a skipUnless((ROOT / ".git").exists()) pattern, but new tests did not adopt it, and no gate ran the suite from a snapshot before qualification.
- Why did the next run halt at the overlay? The entry child ran the real script's main(), which mkdirs ROOT/build/playable-qualification in whatever tree hosts it.
  - Why did verify_snapshot miss it? inventory_tree records files only, so empty directories are invisible; the conflict surfaced two lanes later as generated-output-path-conflict.

Why not caught (gate): no gate existed for this class. Tests were exercised only from the checkout. The snapshot integrity check is file-only.

Recurrence guards:
- tests/tools/test_verify_playable.py: test_entry_child_writes_nothing_into_the_source_tree (asserts the tree hosting the entry modules gains no files or directories, bytecode included)
- `-B` on the entry child and a test-owned copy of verify_playable.py/private_paths.py
- skipUnless .git guard on the eight ReviewProvenanceTest cases
- Follow-up (open, not implemented): add a directory-set comparison to verify_snapshot so the offending lane fails at once
