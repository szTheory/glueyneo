# Phase 03: Distributable release qualification - Pattern Map

**Mapped:** 2026-10-06  
**Files analyzed:** 12 proposed implementation files/locations (including grouped test and workflow files)  
**Analogs found:** 9 / 12; hosted workflow orchestration has no current in-repository analog

Scope comes from `03-CONTEXT.md` decisions/integration points and the proposed structure, requirements, and validation map in `03-RESEARCH.md`. Proposed files are not present and are not evidence of implemented behavior. Paths below are scoped recommendations where the artifacts do not prescribe a literal filename. Every analog named below is tracked source (`git ls-files` verified); no runtime mirror paths are used.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `.github/workflows/ci.yml` (name/location proposed) | config / CI orchestration | event-driven, batch | none; use local verification seam `tools/verify_sdk.py` | no workflow analog |
| `.github/workflows/release.yml` (name/location proposed) | config / release orchestration | event-driven, batch, file-I/O | `tools/verify_sdk.py` and `tests/consumers/check_package.py` for gates only | partial; hosted authority absent |
| `tools/public_content.py` | utility / scanner | file-I/O, batch, transform | `tools/sdk_evidence.py` privacy, hashing, canonical JSON helpers | role-match |
| `tools/release_manifest.py` | utility / release inventory | file-I/O, transform | `tools/sdk_evidence.py` canonical JSON and SHA-256 | role-match |
| `CMakeLists.txt` (modify: manifest-derived project/package version) | config / build and install | transform, file-I/O | current `CMakeLists.txt` install/package contract | exact |
| `tools/sdk_evidence.py` (modify: matrix identities/outcomes) | utility / evidence model | transform, batch | itself; `docs/evidence-schema.md` is its contract | exact |
| `tools/verify_sdk.py` (modify: new release/policy suites) | utility / controller | request-response, batch, file-I/O | itself; package dispatch to `tests/consumers/check_package.py` | exact |
| `tests/consumers/check_package.py` (modify: Windows exports and downloaded relocation) | test / package consumer | file-I/O, request-response | itself | exact |
| `tests/consumers/` new release-consumer cases | test | file-I/O, request-response | `tests/consumers/check_package.py` | role-match |
| `tests/workflow/` new classifier/aggregate/recovery controls | test | event-driven, batch, transform | `tests/workflow/test_phase01_docs.py` | role-match |
| `docs/evidence-schema.md`, `docs/testing.md` (modify) | documentation / contract | transform | same tracked documents | exact |

The research validation map also calls for scanner canary, classifier, release-recovery, and matrix evidence suites via `tools/verify_sdk.py --suite ...`; it does not fix their test filenames. Place their tests alongside the existing `tests/workflow/`, `tests/sdk/`, and `tests/consumers/` modules and follow their naming/runner conventions rather than assuming additional top-level frameworks. `CMakePresets.json` is an existing floor/configuration reference (schema 2, CMake 3.20); no context decision requires changing it.

## Pattern Assignments

### `.github/workflows/ci.yml` (config, event-driven/batch)

**Analog:** none in the tracked repository. Context explicitly states `.github` workflows and hosted CI are not configured. Use the local gate as the contract, not an invented existing workflow.

**Local verification seam** (`tools/verify_sdk.py`, lines 941-958):

```python
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--suite", choices=("evidence", "provenance", "baseline", "all"), default="all")
args = parser.parse_args()
try:
    if args.suite == "evidence":
        report = suite_evidence()
    elif args.suite == "provenance":
        report = suite_provenance()
    elif args.suite == "baseline":
        report = suite_baseline()
    else:
        report = suite_all()
    report["duration_seconds"] = round(time.monotonic() - start, 6)
    evidence.scan_public_value(report)
    print("SDK_VERIFY " + json.dumps(report, sort_keys=True, separators=(",", ":")))
    return 1 if report.get("outcome") == "fail" else 0
```

Apply: run the canonical entrypoint from CI and extend its explicit selectors; ensure the required aggregate starts for all relevant events and checks lane denominators itself. This excerpt shows the actual suite selection/report path; it is a local CLI shape, not hosted trigger, permissions, or protection evidence.

### `.github/workflows/release.yml` (config, event-driven/file-I/O)

**Analog:** no release workflow. Reuse gates from `tools/verify_sdk.py` and `tests/consumers/check_package.py`; D-05/D-08/D-11/D-12 require separation of untrusted PR execution, trusted App credentials, staging, verification, and publication. No current repo evidence establishes App scope, draft event behavior, protected branches, or actual hosted release authority. Workflow SHA pins and schema/config pins must be chosen and tested by implementation; the research recommendations are not current configuration.

**Relevant gate contract** (`docs/evidence-schema.md`, lines 24-32):

```text
Every suite/case preserves one of `pass`, `fail`, `skipped`, `unsupported`, or
`unknown`. A passing behavioral lane requires at least one named case and a
positive assertion denominator. ... Required lanes must pass;
an all-skipped/empty aggregate fails closed. Failure records are retained
instead of being replaced by a later favorable rerun.
```

Use explicit same-workflow job dependencies and inspect an existing draft on retry regardless of the release tool's “created” output, per D-11. This state-machine behavior has no existing local analog and requires dedicated fake-state/API controls plus a hosted qualification receipt.

### `tools/public_content.py` (utility, batch/file-I/O)

**Analog:** `tools/sdk_evidence.py`.

**Imports/hash and deterministic record pattern** (`tools/sdk_evidence.py`, lines 6-16, 107-123):

```python
import hashlib
import json
from pathlib import Path
import re
from typing import Any

def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()

def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=True, sort_keys=True,
                       separators=(",", ":")) + "\n").encode()
```

**Privacy/error pattern** (`tools/sdk_evidence.py`, lines 87-104): current regex checks cover personal absolute paths, email, and obvious machine/serial fields; `EvidenceError(reason, message)` and `require(...)` give stable rejection reasons. The new scanner must broaden inputs to bounded source/history/log/archive content and redact matched values. Do not copy the present regex coverage as a claim of complete secret detection. Add explicit fail-closed archive member/count/size validation and inventory/notices, which the current evidence helper does not implement.

### `tools/release_manifest.py` (utility, file-I/O/transform)

**Analog:** `tools/sdk_evidence.py`, lines 107-141 above. Reuse canonical sorted JSON, lowercase SHA-256, unique-key rejection, and stable machine-readable rejection codes. Record artifact identity and exact allowlisted asset names; a digest establishes byte equality only, not provenance or rights. No release-asset manifest generator currently exists.

### `CMakeLists.txt` (config, transform/file-I/O)

**Analog:** `CMakeLists.txt` itself (tracked), lines 164-200:

```cmake
install(TARGETS glueyneo
  EXPORT GlueyneoTargets
  ARCHIVE DESTINATION "${CMAKE_INSTALL_LIBDIR}"
  LIBRARY DESTINATION "${CMAKE_INSTALL_LIBDIR}"
  RUNTIME DESTINATION "${CMAKE_INSTALL_BINDIR}"
  INCLUDES DESTINATION "${CMAKE_INSTALL_INCLUDEDIR}"
)
install(TARGETS glueyneo-diagnostic RUNTIME DESTINATION "${CMAKE_INSTALL_BINDIR}")
install(DIRECTORY include/glueyneo DESTINATION "${CMAKE_INSTALL_INCLUDEDIR}")
install(FILES LICENSE DESTINATION "${CMAKE_INSTALL_DATADIR}/licenses/Glueyneo")
install(FILES "${GLUEYNEO_DIAGNOSTIC_FIXTURE}"
  DESTINATION "${CMAKE_INSTALL_DATADIR}/glueyneo")
```

The current declaration at lines 1-2 is `cmake_minimum_required(VERSION 3.20)` and `project(Glueyneo VERSION 0.1.0 LANGUAGES C)`. D-09 changes version ownership: parse/validate the root release-please manifest before `project()` and feed that one value to package metadata. Keep install/export targets rather than adding a parallel copy system. Preserve CMake 3.20/preset schema 2 unless exercised requirements prove a floor change.

### `tools/sdk_evidence.py` (utility, transform/batch)

**Analog:** same file, tracked; identity/outcome structure at lines 43-51, 102-123, 176-184, and 213-242. Existing identities include revision, dirty state, compiler, CMake, generator, SDK, OS, architecture, configuration, flags, and artifact hashes. Extend the established identity with actual matrix/lane outcome and denominator data; never infer absent rows as support. The current identity is a local SDK build receipt, not hosted matrix qualification.

### `tools/verify_sdk.py` (utility/controller, batch/request-response)

**Analog:** same file, with the canonical entrypoint excerpt above. It bounds child jobs/workers (`MAX_WORKERS = 2`, timeout constants), uses explicit suite maps, retains output digests and validates observed denominators. Existing package dispatch is at `tools/verify_sdk.py` lines 575-588; suite selector/entrypoint is at 941-957. Add focused suites for `matrix`, `ci-policy`, `release-recovery`, `release-consumer`, and `public-content` as specified by research, keeping the existing all-suites path useful. Do not make a passing suite with zero cases/assertions.

### `tests/consumers/check_package.py` (test, file-I/O/request-response)

**Analog:** same file, tracked and directly on the installed consumer path.

**Isolation/error pattern** (lines 27-85): clean inherited build variables, execute commands with explicit working directory/environment/timeout, and fail with a named `CheckError` code. `installed_layout()` (lines 114-148) requires one package config, version/targets/header/license/fixture/runner and one library variant. `build_package()` (lines 284-335) creates isolated producer/install paths, uses offline CMake, checks metadata, runs installed diagnostic, and records compiler identity.

**Windows export extension point** (lines 200-233): current `shared_exports()` selects `nm -gU` on Darwin and `nm -D --defined-only` on Linux; all other platforms raise `CheckError`. Preserve fail-closed behavior while adding a Windows COFF/DLL inspector and exact expected public set/private denylist with fixture-backed parsing. Do not silently skip. BUILD-03 additionally needs a downloaded archive path that can rebuild offline, then run after original source/build/install locations are unavailable.

### `tests/consumers/` release consumer tests (test, file-I/O/request-response)

**Analog:** `tests/consumers/check_package.py`, especially `installed_layout`, `verify_fixture_digest`, `inspect_exports`, and isolated `build_package`. Test digest mismatch, missing/extra asset, changed package location, source archive rebuild without network, removal of old locations, and the real installed diagnostic. Preserve exact expected-vs-observed checks and bounded commands.

### `tests/workflow/` policy/recovery tests (test, event-driven/batch)

**Analog:** `tests/workflow/test_phase01_docs.py`, lines 1-13, 37-58, 60-105. It uses `unittest`, repository-relative paths, stable expected contract constants, and adversarial mutations that must be rejected. Mirror that structure for conservative path classification (unknown/error means full set), aggregate missing/failed/cancelled/zero-denominator states, and release retry/draft mismatches. Existing workflow tests validate docs only; they do not simulate GitHub or prove hosted permissions.

### `docs/evidence-schema.md` and `docs/testing.md` (documentation, transform)

**Analog:** same tracked docs. `docs/evidence-schema.md` lines 11-32 defines canonical JSON, identity, outcomes, positive denominators, retained failures, and privacy boundaries. Lines 93-96 explicitly limit the existing local gate and reserve hosted CI/release qualification to Phase 03. Update these contracts to say what is actually measured, retain unsupported/unknown states, and document scanner limitations and unresolved rights as unknown. Do not convert proposed matrix or release claims into current support statements.

## Shared Patterns

### Exact identity and outcomes
**Sources:** `tools/sdk_evidence.py`; `docs/evidence-schema.md`. Use canonical deterministic records and explicit `pass`, `fail`, `skipped`, `unsupported`, `unknown`; positive assertion denominators are required. Bind release assets to exact commit, version, platform/build identity and expected digests.

### Bounded fail-closed subprocess and package checks
**Source:** `tests/consumers/check_package.py` lines 27-85, 284-335; `tools/verify_sdk.py`. Strip inherited build variables, cap workers/time, capture output, keep failures actionable, and reject unavailable required inspectors/inputs.

### Public privacy and rights
**Sources:** `tools/sdk_evidence.py` lines 87-104; `fixtures/diagnostic/manifest.json`; `third_party/unity/PROVENANCE.md`; `LICENSE`. Preserve notices/provenance and publish only inventoried content with established rights. Scanner-clean means only that configured detectors found no match in inspected bytes; it cannot establish absent secrets or redistribution permission.

### CI/release trust boundary
**Source:** no local workflow analog; D-05 through D-12 in context and patterns in research. PR code gets read-only/no-secret execution. Trusted App token use belongs in separate trusted jobs and must not consume unchecked PR-produced bytes. Same-workflow dependencies support the release flow; actual branch rules, App events, fork approval, and publishing remain unqualified until exercised against the configured repository.

## No Analog Found

| File/Capability | Role | Data Flow | Reason |
|---|---|---|---|
| `.github/workflows/ci.yml` and release workflow | config | event-driven/batch | Checkout has no `.github/workflows` files or configured hosted CI. |
| Release retry/draft state machine | utility/workflow | event-driven/file-I/O | No release manifest/draft automation exists; implement explicit validation and fake-state recovery controls. |
| GitHub authority/rules/App behavior | hosted control plane | event-driven | No remote, branch protection, App installation, or hosted event receipts are established. |

## Metadata

**Analog search scope:** tracked `CMakeLists.txt`, `cmake/`, `tools/`, `tests/consumers/`, `tests/workflow/`, `tests/sdk/`, and `docs/`; no `.github/workflows/` source exists.  
**Files scanned:** 9 close local analogs/contracts; search stopped after the relevant package, evidence, verification, and workflow-test matches.  
**Pattern extraction date:** 2026-10-06
