---
phase: 04-public-playable-tracer
plan: 03
subsystem: fixture-provenance
tags: [C17, CMake, Python, rights, oracle]
requires:
  - phase: 04-public-playable-tracer
    provides: GNFX v1 public guest, native input trace, and CMake fixture target
provides:
  - Exact source, generator, assertion, and generated artifact identities with affirmative MIT rights
  - Independent fixture expectations and CPU-manual ancestry separated from emulator comparisons
  - Deterministic rebuild, single-producer, shared-consumer-path, and mutation checks
affects: [04-public-playable-tracer, phase-07-qualification]
actuals:
  tokens: 7022
  tasks: 2
  commits: 2
commits: 2
plan_head_before: ce9ecf9d1ade200871f82251b9af98474abeb1fc
plan_head_after: 4c55ac2e9b764a2b9f8251c61f6f450e29fe3569
tech-stack:
  added: [Python standard library]
  patterns: [separate fixture rights manifest, digest-bound regeneration, explicit oracle limits]
key-files:
  created:
    - tests/fixture/rights-manifest.json
    - tests/fixture/check_fixture.py
  modified:
    - tests/fixture/ORACLE.md
    - docs/rights-inventory.md
    - docs/public-content.md
key-decisions:
  - "Affirmative redistribution is based on original Glueyneo authorship under MIT with LICENSE retained; a digest identifies bytes but does not prove rights."
  - "CPU manuals support only named 68000 instruction behavior and timing; community board references and MAME remain implementation/differential context, not hardware truth."
  - "The generated 602-byte artifact identity is SHA-256 59ed3645b156db15e20599ab71f40d416f870472078e8f6751d2174afe7a5cf0."
patterns-established:
  - "Fixture source, assertion source, generator target, and build output have separate recorded identities."
  - "Negative controls must fail at the recorded artifact digest, not merely at a path or invocation check."
requirements-completed: [TRAC-01, TRAC-03]
coverage:
  - id: D1
    description: Public fixture source, assertion ancestry, output identity, and affirmative redistribution basis are auditable.
    requirement: TRAC-01
    verification:
      - kind: integration
        ref: "python3 tests/fixture/check_fixture.py --source tests/fixture/public_guest.c --artifact build/sdk-debug/public-playable.bin --rights tests/fixture/rights-manifest.json"
        status: pass
      - kind: other
        ref: "public_content.validate_repository_inventory: 28 items, exact path/digest/notice coverage"
        status: pass
    human_judgment: false
  - id: D2
    description: A single named CMake target deterministically regenerates the same artifact for native and RetroArch consumers, and a byte mutation is rejected.
    requirement: TRAC-03
    verification:
      - kind: integration
        ref: "check_fixture.py --check-rebuild --negative-control: two 602-byte target regenerations match; one-byte mutation rejected by SHA-256"
        status: pass
      - kind: unit
        ref: "sdk-debug CTest: public_guest_contract, public_guest_trace, public_guest_negative_left, public_guest_negative_none, libretro_callback"
        status: pass
    human_judgment: false
duration: 16min
completed: 2026-10-07
status: complete
---

# Phase 04 Plan 03: Public Fixture Provenance Summary

**The 602-byte GNFX fixture now has a digest-bound source and rights record, independent assertion ancestry, and deterministic regeneration checks.**

## Performance

- **Duration:** 16 minutes
- **Started:** 2026-10-07T21:10:00Z
- **Completed:** 2026-10-07T21:26:15Z
- **Tasks:** 2
- **Files modified:** 5 implementation and evidence files

## Accomplishments

- Bound the tracked C recipe, assertion source, generator target, and generated 602-byte `build/sdk-debug/public-playable.bin` to separate identities. The output SHA-256 is `59ed3645b156db15e20599ab71f40d416f870472078e8f6751d2174afe7a5cf0`.
- Recorded affirmative rights for original Glueyneo source, seed, bitmap, and assertions under MIT with `LICENSE` retained. No game, BIOS, private capture, or third-party guest bytes are included; the generated binary remains build-only.
- Documented independent `NONE, RIGHT, RIGHT` coordinate and pixel expectations, LEFT/NONE negative controls, Motorola manual support for the named instruction forms, and the limited or uncertain status of community Neo Geo references, MAME comparisons, video behavior, and hardware claims.
- Added a standard-library checker for source/output digests and rights, the unique CMake producer and tracked dependencies, the common native/RetroArch artifact path, two forced target regenerations, and a one-byte mutation control.

## Task Commits

1. **Task 1: Audit source, output and oracle ancestry** — `b096b98` (`docs`)
2. **Task 2: Check deterministic rebuild and single output producer** — `4c55ac2` (`test`)

## Files Created/Modified

- `tests/fixture/ORACLE.md` — separate fixture expectations, primary CPU references, community references, and hardware-truth limits.
- `tests/fixture/rights-manifest.json` — exact fixture identities and affirmative rights record.
- `tests/fixture/check_fixture.py` — identity, producer, rebuild, consumer-path, rights, and mutation checks.
- `docs/rights-inventory.md` — exact path and digest coverage for fixture and current Libretro test tooling; corrected the owned CPU oracle digest.
- `docs/public-content.md` — documents the public fixture identity and rights gate.

## Decisions Made

- The fixture's own expected coordinates and selected pixels are the assertion contract; test output, MAME, and emulator agreement do not supply hardware truth.
- Affirmative rights are based on first-party authorship and the repository MIT license. Hashes bind byte identity and do not establish ownership or permission by themselves.
- The 68000 evidence remains limited to the already accepted diagnostic subset and the two named guest instruction forms. General MVS/video behavior, BIOS boot, physical hardware behavior, and commercial compatibility remain unsupported or unknown.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical functionality] Completed exact rights coverage for current public test files**

- **Found during:** Task 1 (source, output, and oracle audit)
- **Issue:** The repository-wide rights gate had no affirmative rows for the preceding Phase 04 Libretro callback harness and smoke runner, and the current owned CPU oracle digest differed from its inventory record.
- **Fix:** Added exact path, SHA-256, provenance, immutable source revision, and MIT notice records for the two Libretro files and corrected the oracle row to the current digest.
- **Files modified:** `docs/rights-inventory.md`
- **Verification:** `public_content.validate_repository_inventory()` passed with 28 exact inventory items.
- **Committed in:** `b096b98`

**Total deviations:** 1 auto-fixed (Rule 2).
**Impact on plan:** These corrections were necessary for the required rights audit to pass against the current tracked public fixture/test set.

## Validation

- `python3 tests/fixture/check_fixture.py --source tests/fixture/public_guest.c --artifact build/sdk-debug/public-playable.bin --rights tests/fixture/rights-manifest.json --check-rebuild --negative-control` passed. Both forced named-target builds matched the recorded digest and 602-byte length; the mutated copy was rejected at the digest check.
- `python3 -m py_compile tests/fixture/check_fixture.py` passed.
- Repository rights validation passed for all 28 listed fixture/dependency items, with exact paths, digests, affirmative status, and retained notices.
- `cmake --build --preset sdk-debug --target public_guest_test glueyneo-public-fixture` completed; the deterministic checker had already forced both generations.
- Full `sdk-debug` CTest ran 27 tests: 25 passed and 2 failed. The failures are the known `sdk_package_docs_readme` and `sdk_package_capabilities` checks for the root README's missing flat `.planning/phases/01-cpu-acceptance-experiment/01-VERIFICATION.md` link. The verification file remains in the sibling diagnostic workstream; this issue was already recorded in Phase 04 `deferred-items.md` and was not changed or hidden.

## User Setup Required

None.

## Next Phase Readiness

Plan 04-03 is complete and the public fixture provenance gate is reproducible. Phase 04 itself is not complete: Plans 04-04 through 04-06 and sound-candidate admission remain. HOST-02 remains blocked/unknown because the pinned RetroArch process exited before a screenshot in Plan 04-02; this plan adds no real-frontend or physical-hardware evidence.

## Self-Check: PASSED

- The summary exists at the required workstream phase path.
- Task commits `b096b98` and `4c55ac2` are ancestors of the current plan head.
- The persisted plan ledger measures 2 commits from `ce9ecf9` through `4c55ac2`, matching the frontmatter.

---
*Phase: 04-public-playable-tracer*
*Completed: 2026-10-07*
