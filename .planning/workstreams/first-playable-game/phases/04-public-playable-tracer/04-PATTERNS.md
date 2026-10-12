# Phase 04: Public Playable Tracer - Pattern Map

**Mapped:** 2026-10-07  
**Files analyzed:** 6 gap-closure paths (including two planned test paths)
**Analogs found:** 4 / 5

Scope is limited to closing the QUAL-03 source identity defect and resolving the existing actual RetroArch smoke outcome. This map does not plan a Phase 04 rebuild. Preserve the Phase 04 limits: C-first and small dependencies; exact identity of inputs actually compiled; original public fixture only; private ROMs, BIOS, captures and outputs remain private; unknown frontend behavior stays unknown until directly observed. The existing report says the qualification runner records `HEAD` plus eight selected hashes while building from the live checkout, and RetroArch exited `-6` before its first screenshot (`04-VERIFICATION.md`, gaps and Human Verification Required).

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `tools/verify_playable.py` | utility / qualification runner | batch | `tools/verify_sdk.py` | role-match; different evidence contract |
| `tests/tools/test_verify_playable.py` (candidate path; no dedicated test currently exists) | test | transform / batch | `tests/sdk/test_evidence.py` | role-match; mutation-test shape |
| `docs/first-playable-build.md` | procedure / evidence documentation | batch | same file | exact; existing procedure needs source-identity and outcome updates |
| `tests/libretro/retroarch_smoke.py` | test / integration runner | event-driven | same file | exact; current actual frontend path and controls |
| `tests/libretro/test_retroarch_smoke.py` | test | transform / event-driven | `tests/workflow/test_public_content.py` | role-match; isolated `unittest` controls and subprocess/temp-path handling, different domain |
| `build/playable-qualification/receipt.json` (ignored generated evidence; if regenerated) | evidence artifact | batch | receipt assembly in `tools/verify_playable.py` | role-match; generated output, not tracked source |

All named source analogs were checked with `git ls-files`; each is tracked. No `.gsd/capabilities` mirror paths are used.

## Pattern Assignments

### `tools/verify_playable.py` (utility, batch)

**Analog:** `tools/verify_sdk.py`

**Imports and runner boundary** (`tools/verify_sdk.py`, lines 6-31):

```python
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
MAX_WORKERS = 2
CHILD_TIMEOUT_SECONDS = 600
FILTERED_ENVIRONMENT = {
    "CFLAGS", "CXXFLAGS", "CPPFLAGS", "LDFLAGS", "CMAKE_PREFIX_PATH",
    "CMAKE_MODULE_PATH", "CMAKE_TOOLCHAIN_FILE", "CMAKE_PROJECT_INCLUDE",
    "CMAKE_PROJECT_INCLUDE_BEFORE", "CMAKE_GENERATOR",
}
```

**Named lanes and fail-closed identity precedent** (`tools/verify_sdk.py`, lines 33-57; `tools/sdk_evidence.py`, lines 375-390, 416-425):

```python
SUITE_LABELS = {
    "contract": "sdk-contract",
    "diagnostic": "sdk-diagnostic",
    "run": "sdk-run",
    "controls": "sdk-controls",
}
```

```python
def relevant_source_rows(root: Path = ROOT) -> list[dict[str, Any]]:
    rows = []
    for relative in sorted(RELEVANT_FILES):
        path = root / relative
        require(path.is_file(), "missing-identity-row", f"required identity file is missing: {relative}")
        rows.append({"path": relative, "sha256": sha256_file(path), "bytes": path.stat().st_size})
    return rows

def public_source_identity(root: Path = ROOT, ...) -> dict[str, Any]:
    rows = relevant_source_rows(root)
    relevant_digest = sha256_bytes(canonical_bytes(rows))
    dirty = bool(_git("status", "--porcelain", "--untracked-files=all", "--", *RELEVANT_FILES))
```

For the gap fix, use these as evidence-format and fail-closed precedents only. The SDK's hand-maintained relevant-file allowlist is not sufficient evidence of a *complete* Phase 04 build input set. Bind the actual CMake inputs, generated fixture inputs, test/check scripts, dependency revisions and notices to the source identity; either reject any relevant dirty/untracked input before configure, or build a recorded clean source snapshot and digest its complete input inventory. Keep receipt generation and lane outcomes in the existing runner. It already provides bounded child timeouts, sanitized logs, exact app/core/fixture hashes, and makes a failed or missing actual smoke aggregate as fail (`verify_playable.py`, lines 58-80, 126-142, 169-182, 199-240, 244-298). `--clean` currently means new build/install directories only (`verify_playable.py`, lines 159-167, 199-215); do not treat it as a source-cleanliness check.

**Shared identity safeguards:** the repo's evidence model rejects dirty passing evidence and records sorted source rows with per-file hashes and byte lengths (`tools/sdk_evidence.py`, lines 169-178, 375-390, 461-483). Reuse canonical ordering, explicit unknowns, sanitized logs, and exact identities. Do not broaden the Phase 04 claim to other configurations or treat a hash alone as rights evidence.

---

### `tests/tools/test_verify_playable.py` (candidate test, transform / batch)

**Analog:** `tests/sdk/test_evidence.py`

There is no existing dedicated test module for `verify_playable.py`; this is a suggested gap-plan path, not an existing file. Use small, named negative controls modeled on `expect_rejection` (`tests/sdk/test_evidence.py`, lines 123-131):

```python
def expect_rejection(name, action, expected_reason):
    try:
        action()
    except evidence.EvidenceError as error:
        if error.reason != expected_reason:
            raise AssertionError(...) from error
        return {"case_id": name, "outcome": "pass", ...}
    raise AssertionError(f"{name}: malformed evidence was accepted")
```

Exercise at least a dirty tracked input, an untracked build input, a modified generated-fixture recipe/input, and a stale or incomplete receipt identity. Verify each fails before CMake consumes the mutable checkout, or that the clean snapshot digest names exactly what CMake consumes. Include a positive clean-tree case and ensure failure receipts preserve the reason. Prefer isolated temporary Git trees/fixtures so controls do not mutate this checkout. Do not create or commit test outputs containing private media or local machine paths.

---

### `docs/first-playable-build.md` and `build/playable-qualification/receipt.json` (procedure / generated evidence, batch)

**Analog:** `docs/first-playable-build.md` for the existing procedure; `tools/verify_playable.py` for the generated receipt schema and writer.

**Procedure command and evidence boundary** (`docs/first-playable-build.md`, lines 5-19, 36-48):

```markdown
python3 tools/verify_playable.py --retroarch /Applications/RetroArch.app --clean
```

```markdown
A frontend process exit before the first screenshot is `unknown` for HOST-02, not a pass.
```

Retain a single maintainer command, explain what `--clean` guarantees after its semantics are corrected, and describe exact source snapshot/identity behavior. The current guide says “fresh checkout directory” while the runner configures from `ROOT`; reconcile that procedural claim with actual behavior. Regenerate the ignored receipt from the corrected runner and retain pass/fail/unknown distinctions, OS/compiler/SDK/frontend and artifact identities, and unsupported configurations. A successful build or callback harness cannot change HOST-02 from unknown. The existing documentation keeps the public GNFX fixture original and excludes game ROMs/BIOS/private media (`docs/first-playable-build.md`, lines 21-25); preserve that boundary and keep screenshots/logs in temporary or ignored locations, with path redaction.

---

### `tests/libretro/retroarch_smoke.py` (integration test / actual frontend runner, event-driven)

**Analog:** `tests/libretro/retroarch_smoke.py` (exact current path; frontend result remains unresolved).

**Pinned inputs and source-independent identity checks** (`tests/libretro/retroarch_smoke.py`, lines 183-219):

```python
if sys.platform != "darwin":
    raise SmokeBlocked("identity", "actual frontend smoke is supported only on macOS")
...
if version != EXPECTED_VERSION:
    raise SmokeBlocked("identity", ...)
executable_hash = sha256(executable)
if executable_hash != EXPECTED_EXECUTABLE_SHA256:
    raise SmokeBlocked("identity", ...)
...
identity = {
    "retroarch_version": version,
    "retroarch_executable_sha256": executable_hash,
    "core_sha256": sha256(core),
    "fixture_sha256": hashlib.sha256(fixture).hexdigest(),
    ...
}
```

**Real load, observations, controls and unload** (`tests/libretro/retroarch_smoke.py`, lines 224-319):

```python
process = subprocess.Popen(
    [str(executable), "--verbose", "--config", str(config),
     "-L", str(core), str(content)],
    stdout=log_stream, stderr=subprocess.STDOUT, start_new_session=True,
)
first = request_screenshot(process, screenshots, {}, args.timeout)
...
if second_marker != first_marker:
    raise SmokeBlocked("input", "no-input control changed the guest marker")
...
if wrong_marker != first_marker:
    raise SmokeBlocked("input", "Left Arrow wrong-input control moved the guest marker")
...
if right_marker[0] <= first_marker[0]:
    raise SmokeBlocked("input", "mapped Right Arrow did not move the guest marker")
...
process.wait(timeout=args.timeout)
if process.returncode != 0:
    raise SmokeBlocked("unload", ...)
```

Keep the pinned macOS app invocation, same generated fixture, semantic screenshot checks, no-input stability, wrong-direction control, mapped direction and clean unload. Preserve temporary config/screenshot locations and bounded waits. The smoke itself reports an early app exit as a frontend failure (`lines 147-161`); the qualification wrapper intentionally reports that as `unknown` for the capability claim (`verify_playable.py`, lines 263-280). The observed `-6` before screenshot remains unknown until a new run completes all actual app observations. A callback harness, successful install, executable digest or relaunch without a complete observation cannot substitute.

### `tests/libretro/test_retroarch_smoke.py` (test, isolated process/screenshot controls)

**Analog:** `tests/workflow/test_public_content.py`

Use its standard-library `unittest` structure, temporary-directory isolation, subprocess boundary and mocked external conditions as the closest existing Python test pattern (`tests/workflow/test_public_content.py`, tracked). Keep tests focused on deterministic helper behavior: stage/reason classification, fresh capture/config paths, stale screenshot rejection, bounded process handling and path redaction. Tests must not launch the pinned GUI or claim HOST-02; actual-app invocation remains the separate acceptance step in the smoke runner.

## Shared Patterns

### Exact source identity

**Sources:** `tools/verify_playable.py` lines 169-175 and `tools/sdk_evidence.py` lines 375-390, 461-483. Make the qualification identity cover all inputs actually consumed and ensure the build runs from those identified bytes. Fail closed on dirty/untracked relevant inputs or snapshot first; retain sorted path/hash/size rows plus a canonical aggregate digest. Record environment and built artifact digests alongside source identity.

### Evidence outcomes and privacy

**Sources:** `tools/verify_playable.py` lines 244-298; `docs/first-playable-build.md` lines 19, 36, 46-48; `tests/libretro/retroarch_smoke.py` lines 224-254. Keep each lane's reason and exact identity, redact local paths, store reports/logs under ignored `build/`, and use only the public original fixture. Unknown frontend behavior stays unknown. Do not put BIOS, commercial ROMs, private captures, or private test output into the repository or public evidence.

### Actual frontend qualification

**Source:** `tests/libretro/retroarch_smoke.py` lines 183-219, 255-319. The app must consume the pinned core and generated public fixture through its normal command path, produce inspectable software output, demonstrate stable/no-input and wrong/right controls, and unload cleanly. Synthetic callback checks remain integration diagnostics, not HOST-02 evidence.

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `tests/tools/test_verify_playable.py` | test | transform / batch | No dedicated qualification-runner tests exist. `tests/sdk/test_evidence.py` is the closest mutation/rejection style, but its SDK evidence schema is not the playable receipt contract. |

## Metadata

**Analog search scope:** qualification tooling, SDK evidence helpers/tests, installed-consumer checks, Libretro smoke and build procedure.

**Files scanned:** 9 tracked analog candidates.
**Pattern extraction date:** 2026-10-07
