---
phase: 04-public-playable-tracer
reviewed: 2026-10-07T22:15:16Z
depth: standard
files_reviewed: 47
files_reviewed_list:
  - CMakeLists.txt
  - README.md
  - docs/first-playable-build.md
  - docs/public-content.md
  - docs/rights-inventory.md
  - experiments/owned_cpu/SUBSET.md
  - experiments/owned_cpu/cpu.c
  - include/glueyneo/glueyneo.h
  - src/chips/ym2610_candidate.cpp
  - src/chips/ym2610_candidate.h
  - src/chips/z80_candidate.c
  - src/chips/z80_candidate.h
  - src/instance.c
  - src/libretro/libretro_core.c
  - tests/chips/Z80-ADMISSION.md
  - tests/chips/check_ym2610.py
  - tests/chips/check_z80_source.py
  - tests/chips/test_ym2610.c
  - tests/chips/test_z80.c
  - tests/consumers/check_package.py
  - tests/consumers/test_exports.py
  - tests/consumers/test_playable_install.py
  - tests/fixture/ORACLE.md
  - tests/fixture/check_fixture.py
  - tests/fixture/public_guest.c
  - tests/fixture/rights-manifest.json
  - tests/fixture/test_public_guest.c
  - tests/libretro/callback_harness.c
  - tests/libretro/retroarch_smoke.py
  - tests/owned_cpu/ORACLE.md
  - tests/owned_cpu/test_semantics.c
  - third_party/chips/NOTICE.md
  - third_party/chips/z80.h
  - third_party/libretro/NOTICE.md
  - third_party/libretro/libretro.h
  - third_party/ymfm/LICENSE
  - third_party/ymfm/NOTICE.md
  - third_party/ymfm/src/ymfm.h
  - third_party/ymfm/src/ymfm_adpcm.cpp
  - third_party/ymfm/src/ymfm_adpcm.h
  - third_party/ymfm/src/ymfm_fm.h
  - third_party/ymfm/src/ymfm_fm.ipp
  - third_party/ymfm/src/ymfm_opn.cpp
  - third_party/ymfm/src/ymfm_opn.h
  - third_party/ymfm/src/ymfm_ssg.cpp
  - third_party/ymfm/src/ymfm_ssg.h
  - tools/verify_playable.py
findings:
  critical: 1
  warning: 0
  info: 0
  total: 1
status: issues_found
---

# Phase 04: Code Review Report

**Reviewed:** 2026-10-07T22:15:16Z  
**Depth:** standard  
**Files Reviewed:** 47  
**Status:** issues_found

## Summary

Reviewed the Phase 04 implementation, tests, build/package checks, and vendored dependency provenance at standard depth. The qualification runner can label artifacts with the current `HEAD` revision while building uncommitted runtime or dependency changes, and its source hash list omits those inputs. This makes a passing receipt insufficient to identify the source that was actually qualified. The recorded RetroArch smoke outcome remains unknown; this review does not treat it as passed.

## Critical Issues

### CR-01: [BLOCKER] Qualification receipt can identify the wrong source revision

**File:** `tools/verify_playable.py:170-175`

**Issue:** The receipt records `git rev-parse HEAD` as `source_revision` and hashes only eight selected files. The clean option creates fresh build/install directories; it does not check whether the worktree contains uncommitted or untracked build inputs. A change to `src/instance.c`, `src/libretro/libretro_core.c`, either candidate adapter, or a vendored dependency can therefore be compiled and pass the gates while the receipt names the unchanged `HEAD` and omits a hash of the changed file. The recorded qualification cannot be reliably tied to the implementation it tested.

**Fix:** Before building, fail qualification when any in-scope build, test, fixture, or dependency input differs from `HEAD`, or compute and record hashes for the complete set of inputs actually used. Keep generated files under ignored `build/` outside that source identity. Include the validated source identity in the receipt and make the build consume that same tree.

---

_Reviewed: 2026-10-07T22:15:16Z_  
_Reviewer: the agent (gsd-code-reviewer)_  
_Depth: standard_
