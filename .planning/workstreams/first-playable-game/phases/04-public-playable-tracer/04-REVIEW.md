---
phase: 04-public-playable-tracer
reviewed: 2026-10-10T00:00:00Z
depth: standard
reviewed_revision: 82a75795e24c5fd62ff79bd0af564d16fb9fe0da
files_reviewed: 13
files_reviewed_list:
  - CMakeLists.txt
  - docs/first-playable-build.md
  - docs/rights-inventory.md
  - experiments/owned_cpu/source-manifest.json
  - tests/consumers/check_package.py
  - tests/libretro/retroarch_smoke.py
  - tests/libretro/test_retroarch_smoke.py
  - tests/tools/check_security_register.py
  - tests/tools/test_check_security_register.py
  - tests/tools/test_private_paths.py
  - tests/tools/test_verify_playable.py
  - tools/private_paths.py
  - tools/verify_playable.py
findings:
  critical: 9
  warning: 9
  info: 4
  total: 22
status: issues_found
---

# Phase 04: Code Review Report

**Reviewed:** 2026-10-10
**Depth:** standard
**Files Reviewed:** 13
**Status:** issues_found

## Summary

Scope: Phase 04's own commits since the prior review (ea63b03 through 82a7579). Phase 05 hunks in `CMakeLists.txt` and the manifest were excluded. RetroArch was not run.

All six defects from the independent security review and Nyquist audit were re-derived from source. Each was reproduced with a small Python probe or confirmed by reading the code, and all six are confirmed (CR-01, CR-03, CR-04, CR-05, CR-06, CR-07). Three further blockers surfaced:

- **CR-02:** the final sink scan runs on `ensure_ascii` JSON, which defeats its own NFKC folding.
- **CR-08:** `main()` crashes with `AttributeError` on every early snapshot failure, so no receipt is written.
- **CR-09:** raw exception text is printed unredacted.

The rest are robustness and maintainability issues. The qualification tooling's central claims (fail-closed private-path scan, evidence-bound HOST-02 status) do not hold under the cases below.

## Structural Findings (fallow)

None provided.

## Narrative Findings (AI reviewer)

## Critical Issues

### CR-01: Private-path redaction and scan miss separator/encoding variants (confirmed)

**File:** `tools/private_paths.py:34-53, 69-99`
**Issue:** `_forms` only generates `/`, `\/`, `\`, single-pass `quote()` and slashless variants. NFKC folds U+FF0F (fullwidth solidus) but not U+2215 (division slash) or U+2044 (fraction slash). Probed with a non-home root `/opt/ci/work/glueyneo` passed as an extra root, then with `$HOME` (the local home directory):

| Variant | `redact` | `scan_public` |
|---|---|---|
| U+2215 separators | survives | SURVIVES for non-home roots; caught for `$HOME` only by the bare-username token check |
| U+2044 separators | survives | same as U+2215 |
| `%252F` (double percent) | survives | SURVIVES |
| dash-mangled, with and without leading `-` | survives | SURVIVES |
| `_`-mangled, `.`-mangled | survives | SURVIVES |
| `/` escape text | survives | SURVIVES |
| NBSP separators | survives | SURVIVES |
| `/tmp/` with U+2215 | survives | SURVIVES |

The username token check at lines 96-99 is the only reason `$HOME` variants are caught on this host. The checkout, temp and run roots are not protected by it.
**Fix:** Stop enumerating encodings. Canonicalize before matching:
- Percent-decode repeatedly to a fixpoint.
- Decode `\uXXXX` and `\/` escapes.
- Map every non-alphanumeric run, including `∕`, `⁄`, NBSP, `.`, `_` and `-`, to a single separator.
- Compare against the same canonical form of each root.

Add the table above as regression cases, including the non-home root. Today `BYPASSES` covers only home-derived roots.

### CR-02: `scan_public` is applied to `ensure_ascii` JSON, which defeats NFKC folding at every sink

**File:** `tools/verify_playable.py:863-872, 669`; `tests/libretro/retroarch_smoke.py:115-117`
**Issue:** `json.dumps(...)` defaults to `ensure_ascii=True`, so non-ASCII characters become literal `\uXXXX` text. `_fold` cannot unfold those. Probe: `scan_public("／tmp／x")` is caught raw, but `scan_public(json.dumps({"k": "／tmp／x"}))` SURVIVES. The same holds for `/opt/ci/work/glueyneo` with U+FF0F separators.

The sinks that scan json-dumped text are `_write_receipt` (`text` and `summary`), `validate_frontend_evidence` and `public_json`. `public_json` has no prior `redact` pass over its values, so for it the scan is the only control. `tests/tools/test_private_paths.py` scans raw strings, so it hides this.
**Fix:** Serialize with `ensure_ascii=False` for scanning, or scan the pre-serialization string values and keys directly. Add a test that scans `json.dumps` output of every `BYPASSES` entry.

### CR-03: Frontend-evidence inventory binding is skipped when `.git` is absent, including the documented `--clean --check-docs` path (confirmed)

**File:** `tools/verify_playable.py:712-724, 1105-1109`
**Issue:** The merge-base and `create_snapshot` digest binding sits inside `if (source_root / ".git").exists():`. With `--clean --check-docs`, `check_docs(source_root)` runs against the extracted archive, which never contains `.git`. The ancestor check and the inventory-digest-to-revision binding therefore never run on the command `docs/first-playable-build.md` presents as the gate. The guide (the last paragraph of the evidence section) claims `--check-docs` verifies both.

The summary is hand-writable JSON. Its `inventory_sha256` can be computed from any commit, so a forged summary passes unbound. `core_sha256`, `os` and `input_mapping` are never validated.

Secondary: the `git merge-base` subprocess (713) uses the caller's full environment (user and system git config, `GIT_*` variables) and has no timeout.
**Fix:** When `.git` is absent, either raise (cannot verify evidence) or bind via the original `ROOT`. Pass `ROOT` into the snapshot-side `check_docs`, or run the evidence binding only from the live checkout and have the snapshot-side check verify the digest against `snapshot.commit`'s ancestry. Run git with `clean_environment()` and a timeout.

### CR-04: `check_docs` passes affirmative success prose outside the generated status block (confirmed)

**File:** `tools/verify_playable.py:766-782`
**Issue:** The guide is checked only for (a) exactly one status block equal to the generated text and (b) a handful of trivial substrings (`"unsupported"`, `"unknown"`, `"RetroArch"`, `"macOS"`, ...). Anything else may say anything. The current guide already contradicts the evidence and the gate passes:
- Prose: "the clean committed-snapshot receipt at `706516b5a60c` passed every lane".
- Block and evidence: `aaf3f093ab0f`.

The docs state "The gate does not pattern-match prose for claims", which means a false "HOST-02 Complete" sentence elsewhere is accepted.
**Fix:** Keep generated claims in the block only. Reject claim-bearing vocabulary (`Complete`, `Pass`, `HOST-02`, `QUAL-03`, revision-like hex) outside the block, or remove dated receipt prose from the guide and link to the evidence file. Delete the stale 706516b5a60c paragraph.

### CR-05: Crosswalk "Existing Threat Scope" accepts any non-empty text, including nonexistent paths (confirmed)

**File:** `tools/verify_playable.py:791-798`
**Issue:** `scope.strip()` is only checked for non-emptiness. A crosswalk row whose scope names a path or threat that does not exist, or is `n/a`, passes. The error message also conflates three distinct failures (duplicate ID, empty scope, bad state), so triage is hard.
**Fix:** Validate that each scope resolves to a threat ID present in the phase `*-SECURITY.md`, or to an existing repo-relative path (`(source_root / path).exists()`). Report each failure separately.

### CR-06: `check_security_register.py` reads only the first `threats_open` and only the first threat table (confirmed)

**File:** `tests/tools/check_security_register.py:32, 38-47`
**Issue:**
- `re.search` takes the first `^threats_open:` anywhere in the file, not specifically in frontmatter. A body line suffices when frontmatter is absent.
- The loop `break`s after the first `| Threat ID |` table (line 47). Probe: a second table with an `open`/`critical` row and a duplicate ID returned `[]` (clean). Real files already contain a second `| Threat ID |` table (the ASVS table in `04-SECURITY.md:228`).
- A cell containing `` `a \| b` `` is split on the escaped pipe and gives a spurious "malformed" error.

`tests/tools/test_check_security_register.py` has no mutation for any of these.
**Fix:**
- Parse YAML frontmatter only (between the first two `---` lines).
- Require exactly one `threats_open`.
- Collect rows from every table whose header starts with `Threat ID` that has Severity and Status, or fail if more than one such table exists.
- Split on unescaped pipes.
- Add mutation tests for each.

### CR-07: Outer timeout orphans the `start_new_session` RetroArch child; no pre-launch instance check (confirmed)

**File:** `tests/libretro/retroarch_smoke.py:558-561, 699-705, 461-465, 515-523`; `tools/verify_playable.py:1079-1083, 505-507`
**Issue:**
- `verify_playable` runs the smoke via `subprocess.run(..., timeout=180)`. On expiry it SIGKILLs only the smoke Python process, so the smoke's `finally: request_frontend_quit` never runs. RetroArch is in its own session, so nothing else signals it. An orphaned RetroArch survives the run. The smoke installs no SIGTERM handler either.
- Neither mode (`run_smoke` or `--diagnose` `run_launch_probe`) checks for an existing RetroArch before launch.
- `inject_key` targets `process "RetroArch"` by name, and the quit uses `tell application id "com.libretro.dist.RetroArch" to quit`. Both act on any instance, including a user's interactive one. The hotkeys (F8, arrows) go to whichever instance is frontmost.
- Crash-report attribution (`find_recent_crash_reason`) can also pick up another instance's report.
- This contradicts the project's single-instance rule.

**Fix:**
- Before launch, enumerate RetroArch processes (`pgrep -x RetroArch`) and refuse to start if any exist (blocked or unknown, stage `pre-launch`).
- Run the child in its own process group and handle SIGTERM/SIGINT in the smoke by `killpg`.
- In the runner, replace `subprocess.run(timeout=...)` for this lane with `Popen(start_new_session=True)`, then `communicate(timeout)`, and on timeout `killpg` the group and run a post-lane assertion that no RetroArch process remains.
- Prefer quitting by PID (`kill -TERM`) rather than by bundle ID.

### CR-08: `main()` raises `AttributeError` on any early failure, so no receipt is written

**File:** `tools/verify_playable.py:1056, 1075-1076`
**Issue:** `runner` is assigned only after `create_snapshot`, `verify_snapshot` and the runner-source check succeed (line 957). On any earlier failure (git error, `runner-source-mismatch`, unsafe tree) `runner` is `None`. The receipt dict literal then evaluates `runner.lanes` and raises `AttributeError`. The guard at line 1075 (`if runner is None: receipt["lanes"] = {}`) is unreachable. Reproduced by patching `create_snapshot` to raise `SnapshotError`: result `CRASH AttributeError 'NoneType' object has no attribute 'lanes'`.

The user gets a raw traceback instead of the documented "writes a failed receipt with `runner-source-mismatch`". The traceback is unredacted and unscanned. This is the "unredacted runner None traceback" already listed under T-04-11.
**Fix:** Use `"lanes": runner.lanes if runner is not None else {}`. Add a test that drives `main` with a failing `create_snapshot` and asserts a `fail` receipt with the named reason.

### CR-09: Raw exception text is printed unredacted from `--record-frontend-evidence` and `--check-docs`

**File:** `tools/verify_playable.py:896-913`
**Issue:** `OSError` messages embed absolute paths, for example `[Errno 2] No such file or directory: '<checkout>/build/playable-qualification/receipt.json'`. Lines 899 and 904 print `{error}` to stderr, and 912 prints `str(error)`, with no `redact` or `scan_public`. `check_docs` can also raise `OSError` or `UnicodeDecodeError` on a missing guide or validation file. Neither is caught at 909-913 (only `RuntimeError`), so a traceback with paths results. This contradicts the guide's statement that the runner and smoke stdout pass through `private_paths`.
**Fix:** Route all user-facing error text through a single `emit_error(text)` that calls `redact` then `scan_public`. Catch `OSError`/`UnicodeError` alongside `RuntimeError`.

## Warnings

### WR-01: `write_frontend_records` is non-atomic and writes before validating its targets

**File:** `tools/verify_playable.py:748-763`
**Issue:** The evidence JSON is written at line 750 before the guide status block (755) and the validation row (762) are verified to exist. If either lookup raises, the tree is left with new evidence but stale guide and map, and `check_docs` then fails. There are no temp-file and rename semantics.
**Fix:** Read and validate all three targets and compute all three new contents first, then write them via temp-and-rename.

### WR-02: `validate_frontend_evidence` does not type-check nested fields it later dereferences

**File:** `tools/verify_playable.py:649-651, 734-737`
**Issue:**
- `summary.get("retroarch") or {}` assumes a dict. A string raises `AttributeError`, which is not a `RuntimeError`, so callers skip their handlers.
- `os`, `core_sha256` and `input_mapping` are never validated, yet `os` is interpolated into the generated claim. A missing value renders "on None" and still matches itself between block and row.
- `bool` passes the `isinstance(value, int)` marker checks.

**Fix:** Validate that `retroarch` is a dict and that `os` is a non-empty string. Validate `core_sha256` as 64 hex characters and `input_mapping` against the expected constant. Reject `bool` in the marker check.

### WR-03: `Runner.command` timeout kills only the direct child

**File:** `tools/verify_playable.py:505-512`
**Issue:** `subprocess.run(timeout=...)` kills `cmake`/`ctest` but not their descendants (ninja, compilers, test executables). They continue to run, write into the snapshot or output tree, and can race the following `verify_snapshot`. The partial output is replaced by the exception string, so the log is lost.
**Fix:** Use `Popen(start_new_session=True)`, then on timeout `os.killpg`, drain the output, and keep it in the log.

### WR-04: Screenshot handling is racy and can raise uncaught non-`SmokeBlocked` exceptions

**File:** `tests/libretro/retroarch_smoke.py:208-213, 303-364, 797-832`
**Issue:**
- `select_fresh_screenshot` returns a PNG as soon as it appears, with no size or mtime stability check, so it can hand `decode_png` a half-written file. `path.stat()` can also race a deleted file.
- `decode_png` can raise `struct.error` (truncated chunk or IHDR), `zlib.error` or `IndexError`. `main` only catches `SmokeBlocked`, so the run ends with a traceback and no JSON result. The error is classified "unknown" by the runner and the real stage is lost.
- IDAT inflation is unbounded (`zlib.decompress`, with no check of `width*height` before decompressing).

**Fix:** Require two identical `(size, mtime)` samples or a trailing IEND chunk before accepting a capture. Wrap decode errors into `SmokeBlocked("video", ...)`. Use `zlib.decompressobj().decompress(data, expected + 1)` after validating dimensions.

### WR-05: Unbounded read of non-GNMV content before the size check

**File:** `tests/libretro/retroarch_smoke.py:663-666`
**Issue:** `content.read_bytes()` loads the entire file, whatever its size, before the `len(fixture) != 602` check. `--content` can point at a multi-GB file.
**Fix:** Check `content.stat().st_size == 602` first, then read.

### WR-06: `private_paths` fails closed on benign text (self-inflicted false positives)

**File:** `tools/private_paths.py:27, 94-99`
**Issue:**
- Generic roots `/tmp/`, `/home/`, `/var/` match as plain substrings anywhere. `redact("see docs/tmp/notes")` gives `docs[redacted-path]`, and truncates the rest of the value.
- Receipts embed every archived repo path (`snapshot_record` entries). Any tracked path containing `/tmp/` or `/home/` (for example, committing the currently untracked `.planning/tmp/`) makes every receipt `private-path-survived`.
- The bare-username check rejects any token equal to `Path.home().name`. On a host whose user is `runner` or `build`, ordinary prose in receipts and reasons (for example "runner") fails the scan.
- `Path.home()` can raise `RuntimeError` when HOME is unset and the uid has no passwd entry, which crashes every sink.

**Fix:** Scope generic-root matches to path starts (start of string or preceded by a separator or quote). Scan repo-relative inventory entries separately, or exempt them. Make the username check optional or context-sensitive, and guard `Path.home()`.

### WR-07: Product CTest couples to planning state and a hard-coded workstream; `block_on` is brittle

**File:** `CMakeLists.txt:872-879`; `tests/tools/check_security_register.py:24-26, 76-78`
**Issue:**
- `planning_security_register` is registered in `GLUEYNEO_BUILD_TESTS` with the literal workstream `first-playable-game`. It fails in any source archive that omits `.planning/`, and after the workstream is archived or renamed.
- `block_on` reads only the root `.planning/config.json`. A missing file raises `FileNotFoundError` and an unknown severity raises `KeyError`, both as tracebacks. Per-workstream config (the untracked `workstreams/first-playable-game/config.json`) is ignored.
- `workstream[0]` is interpolated into a glob without validation.

**Fix:** Register the check only when `.planning/` exists, or drive the workstream from a variable. Validate the severity string and the workstream name. Return exit 1 with a message instead of a traceback.

### WR-08: `glueyneo_runtime_static` duplicates runtime state and the configure-time guard is heuristic

**File:** `CMakeLists.txt:155-183, 485-486, 885-911`
**Issue:**
- In shared builds, `libretro_callback_test` links `glueyneo_libretro` (which embeds its own private runtime copy) together with `Glueyneo::glueyneo`. That is two copies of the runtime and its static or global state in one process. `AGENTS.md` requires an audit of mutable globals, and no instance-isolation test covers this combination.
- The guard only inspects direct `.c`/`.cpp` sources for the literal `sdk_private.h`. It misses transitive includes and generator-expression entries in `LINK_LIBRARIES`. It also covers only targets from the top-level directory.
- It is enforced even for static builds, where the comment says such links work.

**Fix:** Have the callback test link only one runtime copy, or add a test proving the copies share no mutable globals. Document or relax the guard, and drive it from actual link failures, or note that it is best-effort.

### WR-09: Local `git` invocations use the caller's environment

**File:** `tools/verify_playable.py:713` (see also CR-03)
**Issue:** The ancestor check runs git with `os.environ` (`GIT_DIR`, `GIT_CONFIG_*`, hooks-adjacent variables) while all other git calls use `clean_environment()`. The same module therefore has two trust models for the same data.
**Fix:** Use `_git()` for this call.

## Info

### IN-01: Stale and contradictory guide text

**File:** `docs/first-playable-build.md` (section "Previous qualification observation" and the "2026-10-10 qualification" paragraph)
**Issue:**
- "Plan 04-08 regenerates the receipt" is stale.
- The 2026-10-10 paragraph names `706516b5a60c` while the generated block names `aaf3f093ab0f` (see CR-04).
- Two "historical" sections repeat each other.

**Fix:** Collapse into one historical section and remove the revision claim outside the generated block.

### IN-02: Dead or redundant code in `retroarch_smoke.py`

**File:** `tests/libretro/retroarch_smoke.py:88, 634-637`
**Issue:** `cursor > len(content)` is subsumed by the next test. The bundle-id regex is redundant after the equality check against `EXPECTED_BUNDLE_IDENTIFIER`.
**Fix:** Remove both.

### IN-03: Minor issues in `check_package.py`

**File:** `tests/consumers/check_package.py:311, 437`
**Issue:**
- Line 311: `line.split()[0]` truncates `otool -L` dependency paths that contain spaces.
- Line 437: formatting nit, `exports =shared_exports(...)`.
- `check_core_self_contained` only rejects `glueyneo*` dependencies. It does not assert that the core has no unexpected third-party dependents.

**Fix:** Parse `otool` lines with a regex `^\s*(.+?) \(compatibility`. Fix the formatting. Optionally allowlist system dependencies.

### IN-04: Test-oracle gaps that let the confirmed defects through

**File:** `tests/tools/test_private_paths.py:27-52`; `tests/tools/test_check_security_register.py:46-66`; `tests/tools/test_verify_playable.py`
**Issue:** The reviewed tests:
- Scan raw strings, never `json.dumps` output (CR-02).
- Use only home-derived roots, which hides CR-01 because of the username token.
- Have no mutations for a second table or second `threats_open` (CR-06).
- Have no `check_docs` negative case for prose claims, a nonexistent scope path or an absent `.git` (CR-03/04/05).
- Have no test that a failing snapshot yields a failed receipt (CR-08).

**Fix:** Add one failing-first test per confirmed defect before fixing the code.

---

_Reviewed: 2026-10-10_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
