---
status: complete
phase: 01-cpu-acceptance-experiment
source: "01-01-SUMMARY.md, 01-02-SUMMARY.md, 01-03-SUMMARY.md, 01-04-SUMMARY.md, 01-05-SUMMARY.md, 01-06-SUMMARY.md, 01-07-SUMMARY.md, 01-08-SUMMARY.md, 01-09-SUMMARY.md, 01-10-SUMMARY.md, 01-11-SUMMARY.md, 01-12-SUMMARY.md, 01-13-SUMMARY.md, 01-14-SUMMARY.md, 01-15-SUMMARY.md, 01-16-SUMMARY.md, 01-17-SUMMARY.md, 01-18-SUMMARY.md, 01-19-SUMMARY.md, 01-20-SUMMARY.md, 01-21-SUMMARY.md, 01-22-SUMMARY.md, 01-23-SUMMARY.md, 01-24-SUMMARY.md, 01-25-SUMMARY.md, 01-26-SUMMARY.md, 01-27-SUMMARY.md"
started: 2026-10-03T23:16:26Z
updated: "2026-10-05T00:12:36Z"
---

**Routing supersession — 2026-10-04:** Row 44 preserves the README route check at its recorded source revision, when gap planning was the next step. That gap-planning attempt returned `PLANNING INCONCLUSIVE`; the old verification report is now marked stale. The current next step is `$gsd-execute-phase 01`, which resumes at verification because all plan summaries are present. Row 44 remains historical evidence for its recorded revision.

### Historical Plan 01-21 frontmatter (preserved verbatim)

```yaml
status: complete
phase: 01-cpu-acceptance-experiment
source: "01-01-SUMMARY.md, 01-02-SUMMARY.md, 01-03-SUMMARY.md, 01-04-SUMMARY.md, 01-05-SUMMARY.md, 01-06-SUMMARY.md, 01-07-SUMMARY.md, 01-08-SUMMARY.md, 01-09-SUMMARY.md, 01-10-SUMMARY.md, 01-11-SUMMARY.md, 01-12-SUMMARY.md, 01-13-SUMMARY.md, 01-14-SUMMARY.md, 01-15-SUMMARY.md, 01-16-SUMMARY.md, 01-17-SUMMARY.md, 01-18-SUMMARY.md, 01-19-SUMMARY.md, 01-20-SUMMARY.md, 01-21-SUMMARY.md"
started: 2026-10-03T23:16:26Z
updated: 2026-10-03T23:23:37Z
```

## Current Test

[testing complete]

## Tests


Historical Plan 01-21 scope: Rows 1–39 and their original evidence below are retained verbatim and apply only to the source ending at Plan 01-21. The former 39/39 complete and no-new-issues statements do not cover Plans 01-22–01-25 or establish success for CR-01, CR-02, WR-01, or WR-02.

### 1. Plan 01-01 D1 — Original guest and bounded private adapter (historical candidate)
expected: The active implementation and fresh behavioral evidence refer to the owned C17 core; imported-candidate results are not reused as proof of owned behavior.
result: pass
source: automated

### 2. Plan 01-01 D2 — Native source closure and budgets (historical candidate)
expected: Current closure and budgets refer to the owned core and its frozen contract, while old candidate records remain historical.
result: pass
source: automated

### 3. Plan 01-02 — Candidate isolation and cold lifecycle (historical candidate)
expected: Current instance-isolation claims are backed by owned-core tests, not the original candidate summary.
result: pass
source: automated

### 4. Plan 01-02 — Candidate allocation and fault containment (historical candidate)
expected: Current fault-containment claims are backed by owned-core tests, not the original candidate summary.
result: pass
source: automated

### 5. Plan 01-02 — Candidate sanitizer evidence (historical candidate)
expected: Fresh sanitizer evidence applies to the active owned-core source.
result: pass
source: automated

### 6. Plan 01-03 — Candidate timing and exception evidence (historical candidate)
expected: Current timing and exception claims are backed by owned-core tests, not the original candidate summary.
result: pass
source: automated

### 7. Plan 01-03 — Candidate continuation evidence (historical candidate)
expected: Current continuation claims are backed by owned-core tests, not the original candidate summary.
result: pass
source: automated

### 8. Plan 01-04 D1 — Accepted imported-candidate decision
expected: The old imported-candidate receipt remains historical; current acceptance reports the owned candidate as unqualified and not admitted.
result: pass
source: automated

### 9. Plan 01-04 D2 — Imported-candidate CPU admission suite
expected: Current owned-core checks report an unqualified, not-admitted disposition; imported-candidate admission is not reused.
result: pass
source: automated

### 10. Plan 01-05 — Rejected candidate and preserved history
expected: The imported candidate remains rejected, its consumed limits and historical receipts remain preserved, and no admission is inferred.
result: pass
source: automated

### 11. Plan 01-06 — Owned-core direction
expected: The active candidate is the private owned C17 core with no public admission claim.
result: pass
source: automated

### 12. Plan 01-07 — Frozen contract and budget
expected: The owned-core contract and budget validate, CPU-01–05 remain pending, and Phase 02 remains gated.
result: pass
source: automated

### 13. Plan 01-08 — Original diagnostic and instruction semantics
expected: The owned CPU runs the original diagnostic and passes its semantic boundaries and named wrong-result control.
result: pass
source: automated

### 14. Plan 01-09 — Timing and selected exception behavior
expected: Owned-core timing, exception, bus-boundary, and wrong-cycle controls pass within the documented subset.
result: pass
source: automated

### 15. Plan 01-10 — Isolation, cold starts, and host-fault containment
expected: Interleaved/concurrent instances, supervised cold processes, fault cases, and compiled-state inventory checks pass.
result: pass
source: automated

### 16. Plan 01-13 — Presets, inventory, and four-lane evidence
expected: Debug, Release, ASan/UBSan, and TSan configure/build/test presets pass with bounded parallelism and source inventory checks.
result: pass
source: automated

### 17. Plan 01-20 — Exact-source four-lane qualification
expected: Each owned-core preset passes all configured CTest cases on the current source tree.
result: pass
source: automated

### 18. Plan 01-11 D1 — Fresh-owner state continuation
expected: Supported saved state restores into a separately bound destination and continues identically at named boundaries.
result: pass
source: automated
coverage_id: D1

### 19. Plan 01-11 D2 — Malformed and incompatible state rejection
expected: Invalid state operations reject without unintended destination or bus changes.
result: pass
source: automated
coverage_id: D2

### 20. Plan 01-11 D3 — Pending level-7 and instruction-counter controls
expected: Named omission controls fail on their exact guest-result assertions.
result: pass
source: automated
coverage_id: D3

### 21. Plan 01-11 D4 — State and compile-closure inventory
expected: State fields, source identities, and the C17 compile closure match the reviewed inventory.
result: pass
source: automated
coverage_id: D4

### 22. Plan 01-12 R1 — Independent review evidence and claim limits
expected: The current independent review binds exact source, evidence denominators, oracle ancestry, and unsupported claims.
result: pass
source: automated
coverage_id: R1

### 23. Plan 01-12 R2 — Impossible state counter rejection
expected: Restore rejects the inconsistent instruction counter atomically.
result: pass
source: automated
coverage_id: R2

### 24. Plan 01-12 R3 — Malformed state sanitizer regression
expected: The malformed-state destination setup passes repeated ASan/UBSan execution.
result: pass
source: automated
coverage_id: R3

### 25. Plan 01-14 D1 — Receipt-integrity controls
expected: Wrong commands/configuration and hidden historical failures are rejected by the acceptance controls.
result: pass
source: automated
coverage_id: D1

### 26. Plan 01-14 D2 — Current independent review and deferred disposition
expected: The current candidate review is clean while backend admission remains explicitly deferred.
result: pass
source: automated
coverage_id: D2

### 27. Plan 01-15 D1 — Original-silicon saved-PC interpretation
expected: No original-silicon saved-PC value is claimed; the candidate's exact 0x4AFC boundary is separately defined.
result: pass
source: automated
coverage_id: D1

### 28. Plan 01-15 D2 — Frozen contract and historical accounting
expected: The frozen contract and historical budget entries remain preserved with append-only current charges.
result: pass
source: automated
coverage_id: D2

### 29. Plan 01-16 D1 — Exact closure and fresh bounded execution
expected: Current owned-core test lanes, source closure, and bounded receipts agree with the active contract.
result: pass
source: automated
coverage_id: D1

### 30. Plan 01-16 D2 — Original-silicon adjudication
expected: The candidate does not claim that emulator evidence resolves the original MC68000 saved PC.
result: pass
source: automated
coverage_id: D2

### 31. Plan 01-17 D1 — Finite evidence acquisition and history
expected: The bounded evidence record and protected historical files remain intact.
result: pass
source: automated
coverage_id: D1

### 32. Plan 01-17 D2 — Recorded scope decision and candidate boundary
expected: P01-C-14 is recorded; exact 0x4AFC is unsupported by the candidate with no frame/vector/dispatch/cycle effects, while hardware saved PC remains unknown.
result: pass
source: recorded-decision+automated
coverage_id: D2

### 33. Plan 01-18 D1 — Exact unsupported-opcode behavior
expected: The candidate reports exact 0x4AFC as unsupported with opcode-only callback behavior and no guest dispatch, frame, vector, or cycle changes.
result: pass
source: automated
coverage_id: D1

### 34. Plan 01-18 D2 — Amendment and frozen-history controls
expected: The active amendment identity and frozen-root/history tamper controls pass.
result: pass
source: automated
coverage_id: D2

### 35. Plan 01-19 D1 — Continuation boundaries
expected: All 13 fresh-owner continuation boundaries pass with exact semantic rejection behavior.
result: pass
source: automated
coverage_id: D1

### 36. Plan 01-19 D2 — Cycle/status negative controls
expected: The named one-case cycle/status controls detect the intended wrong result.
result: pass
source: automated
coverage_id: D2

### 37. Plan 01-19 D3 — Profile, amendment, and deferred-seal validation
expected: The active profile, amendment, preserved history, and deferred-admission receipt validate.
result: pass
source: automated
coverage_id: D3

### 38. Plan 01-21 D1 — Independent source and native security controls
expected: The exact candidate source review and applicable native security controls pass without a current high/critical finding.
result: pass
source: automated
coverage_id: D1

### 39. Plan 01-21 D2 — Deferred receipt and final security binding
expected: The exact deferred receipt and independent final security binding validate; admission remains deferred.
result: pass
source: automated
coverage_id: D2

### 40. Plan 01-25 CR-01 — Fresh-owner odd-PC/stack continuation
expected: The 15 named guest-reachable odd-PC/stack boundaries restore into fresh owners and continue with matching state, memory, frames, ordered bus events, and cycles; malformed, null, active, and terminal state guards remain atomic.
result: pass
source_revision: 9fba16b864cf74e3b8a9c97047bb27a5db544b59
command: `cmake -S . -B build/owned-review25 -G Ninja -DGLUEYNEO_CPU_EXPERIMENT=OFF -DGLUEYNEO_OWNED_CPU_EXPERIMENT=ON -DCMAKE_BUILD_TYPE=Debug -DGLUEYNEO_OWNED_CPU_OPTIMIZATION=NONE -DGLUEYNEO_OWNED_CPU_SANITIZER=NONE && cmake --build build/owned-review25 -j2 && ctest --test-dir build/owned-review25 -R '^owned_cpu_(timing|unsupported_negative|semantics|state)$' --output-on-failure --no-tests=error && build/owned-review25/experiments/owned_cpu/owned_cpu_state --continuation-only`
denominator: Independent reviewer build 22/22 steps; focused CTest 4/4; direct state 5/5 and continuation-only 1/1 with 15 boundaries/90 calls; malformed 15, null 4, counter mismatch 1. Separate assessor: targeted CTest 4/4, continuation-only 1/1 with 15/90, state 5/5.
evidence: `experiments/owned_cpu/REVIEW.md` (fresh `build/owned-review25`, collection `cb77285dd7b821993e1e12ec96e72ed5e13bbf57da7d6dd433f07b3940275738`, profile `owned-p01-c14-continuation-2`); `.planning/phases/01-cpu-acceptance-experiment/01-SECURITY.md` (separate `build/security-audit-plan25`); `.planning/phases/01-cpu-acceptance-experiment/01-22-SUMMARY.md`; `.planning/phases/01-cpu-acceptance-experiment/01-24-SUMMARY.md`.

### 41. Plan 01-25 CR-02 — Cumulative effort cannot decrease or erase threshold crossings
expected: Each cumulative churn category is monotonic and a prior cap crossing cannot be hidden by a lower later total; equality and increasing histories pass.
result: pass
source_revision: 9fba16b864cf74e3b8a9c97047bb27a5db544b59
command: `python3 -m unittest discover -s tests/owned_cpu -p test_contract.py && python3 -O -m unittest discover -s tests/owned_cpu -p test_contract.py && python3 tools/owned_cpu/contract.py budget`
denominator: Contract controls 27/27 normal and 27/27 under `-O`; four cumulative decrease probes rejected; prior-threshold/lower-final probe rejected; budget gate passed with no pause.
evidence: `experiments/owned_cpu/REVIEW.md` (independent normal/optimized controls and temporary-root reproducers); `.planning/phases/01-cpu-acceptance-experiment/01-23-SUMMARY.md`; `.planning/phases/01-cpu-acceptance-experiment/01-24-SUMMARY.md`; `experiments/owned_cpu/budget-ledger.json` (42-entry prefix before Plan 01-25 closeout).

### 42. Plan 01-25 WR-01 — Inclusive caps and active-pause rejection
expected: Exact frozen caps pass inclusively; cap-plus-one, invalid totals, active pause, and pause-for-review controls reject in both interpreter modes.
result: pass
source_revision: 9fba16b864cf74e3b8a9c97047bb27a5db544b59
command: `python3 -m unittest discover -s tests/owned_cpu -p test_acceptance.py && python3 -O -m unittest discover -s tests/owned_cpu -p test_acceptance.py && python3 tools/owned_cpu/contract.py validate`
denominator: Acceptance controls 22/22 normal and 22/22 under `-O`; all three exact category caps pass; each cap-plus-one and active-pause/invalid-total control rejects; contract validation passes.
evidence: `experiments/owned_cpu/REVIEW.md` (fresh normal/optimized suite and direct exact/plus-one probes); `.planning/phases/01-cpu-acceptance-experiment/01-23-SUMMARY.md`; `.planning/phases/01-cpu-acceptance-experiment/01-24-SUMMARY.md`; `.planning/phases/01-cpu-acceptance-experiment/01-SECURITY.md` (T-01-49).

### 43. Plan 01-25 WR-02 — README status and local navigation
expected: README accurately states unadmitted implementation, pending CPU requirements, open Phase 01, gated Phase 02, unknown original-silicon saved PC, and the separate next verification step; all local Markdown links resolve and the stale gap-resume instruction is absent.
result: pass
source_revision: 9fba16b864cf74e3b8a9c97047bb27a5db544b59
command: `python3 -c 'from pathlib import Path; import re; s=Path("README.md").read_text(); links=re.findall(r"\[[^\]]+\]\(([^)]+)\)",s); local=[x for x in links if not re.match(r"(?:https?:|mailto:)",x) and not x.startswith("#")]; missing=[x for x in local if not Path(x.split("#",1)[0]).exists()]; good=(len(links)==19 and len(local)==19 and not missing and "$gsd-verify-work 01" in s and "$gsd-execute-phase 01 --gaps-only" not in s and "CPU-01–05 remain Pending" in s and "saved PC remains unknown" in s); print({"markdown_links":len(links),"local_resolved":len(local)-len(missing),"missing":missing,"next_step_present":"$gsd-verify-work 01" in s,"stale_gap_resume_absent":"$gsd-execute-phase 01 --gaps-only" not in s,"valid":good}); raise SystemExit(0 if good else 1)'`
denominator: 19/19 local Markdown links resolve; README control returns `valid: true`; independent reviewer separately resolves 19/19 local links; `git diff --check` passes.
evidence: `README.md` working-tree document inspection after update; `.planning/phases/01-cpu-acceptance-experiment/01-REVIEW.md` (WR-02 follow-up); `experiments/owned_cpu/REVIEW.md` (independent updated-README check); `.planning/phases/01-cpu-acceptance-experiment/01-SECURITY.md` (T-01-50).

### 44. Current verification routing in README
expected: README records the completed 44/44 automated UAT, the current `gaps_found` phase-goal status, and `$gsd-plan-phase 01 --gaps` as the next separate step; it no longer points to the completed `$gsd-verify-work 01` step.
result: pass
source: automated
source_revision: 56b6b3a53c553b639d24a9fe5ff3143169161761
command: `python3 -c 'from pathlib import Path; import re; s=Path("README.md").read_text(); links=re.findall(r"\[[^\]]+\]\(([^)]+)\)",s); local=[x for x in links if not re.match(r"(?:https?:|mailto:)",x) and not x.startswith("#")]; missing=[x for x in local if not Path(x.split("#",1)[0]).exists()]; good=(len(links)==19 and len(local)==19 and not missing and "44/44 automated checks passing" in s and "`$gsd-plan-phase 01 --gaps`" in s and "`$gsd-verify-work 01`" not in s and "CPU-01–05 remain Pending" in s and "saved PC remains unknown" in s); print({"markdown_links":len(links),"local_resolved":len(local)-len(missing),"missing":missing,"current_next_step_present":"`$gsd-plan-phase 01 --gaps`" in s,"completed_verify_step_absent":"`$gsd-verify-work 01`" not in s,"valid":good}); raise SystemExit(0 if good else 1)'`
denominator: 19/19 local Markdown links and current status/routing assertions.


### 45. Plan 01-26 GATE — Canonical admission wording
expected: The unchanged contract accepts the canonical admission wording while CPU-01–05 remain Pending and Phase 02 remains gated.
result: pass
source: automated
coverage_id: GATE
source_revision: 83de9e95e3fdaf62bf732fe682d32a06bae733e2
command: PYTHONPATH=. python3 tests/owned_cpu/test_contract.py ContractControls.test_frozen_subject_and_pending_gate_validate
denominator: 1/1 targeted regression; contract validate status pass.

### 46. Plan 01-26 REPRODUCTION — Current read-only decision checks
expected: Current read-only contract and acceptance checks pass with the candidate unqualified, requirements Pending, Phase 02 gated, and original-silicon saved PC unknown.
result: pass
source: automated
coverage_id: REPRODUCTION
source_revision: 83de9e95e3fdaf62bf732fe682d32a06bae733e2
command: python3 tools/owned_cpu/contract.py validate; python3 tools/owned_cpu/acceptance.py verify
denominator: Contract validator status pass; acceptance verifier status pass, six collections, zero lane blockers, disposition unqualified.

### 47. Plan 01-27 D1 — Stale-binding archive and history preservation
expected: The six archived payloads validate, the captured stale-binding rejection remains recoverable, all six collections and the original 45-entry ledger prefix remain intact, and the current deferred seal is present.
result: pass
source: automated
coverage_id: D1
source_revision: 83de9e95e3fdaf62bf732fe682d32a06bae733e2
command: Corrected archive assertion in 01-27-PLAN.md Task 1 verify; final receipt/ledger preservation comparison recorded below.
denominator: Six archived payload SHA-256 digests match; the captured exit-1 acceptance result records the expected stale security binding in stderr; all six collections match; prior receipt fields match; the former seal is preserved as the newest superseded seal; 45/45 original ledger entries and frozen ledger policy are preserved; current deferred seal budget passes.
correction: The original planned assertion parsed the rejection JSON from stdout. Its archived process record has empty stdout and the expected JSON in stderr. The plan now checks stderr; the corrected assertion passed. No acceptance behavior or expected result changed.

### 48. Plan 01-27 D2 — Independent bindings and deferred seal
expected: The exact current REVIEW/SECURITY bindings validate and the candidate remains unqualified with admission deferred.
result: pass
source: automated
coverage_id: D2
source_revision: 83de9e95e3fdaf62bf732fe682d32a06bae733e2
command: PYTHONPATH=. python3 tests/owned_cpu/test_acceptance.py AcceptanceControls.test_deferred_seal_binds_review_security_and_never_admits; same targeted test under python3 -O; acceptance.py review-check at the receipt seal revision; contract validate; acceptance verify; contract budget.
denominator: Acceptance control 1/1 normal and 1/1 optimized; independent review check clean at C2 revision e65ea35fe36a0d9cbcbd2f938142f247f3bbf3e2; contract, acceptance, and budget statuses pass.


### 49. Current README verification route and UAT count
expected: README shows the current 49/49 automated UAT, links resolve, the separate phase-goal verification command is current, and the open/pending/unknown status remains accurate.
result: pass
source: automated
coverage_id: README-verify-route
source_revision: 83de9e95e3fdaf62bf732fe682d32a06bae733e2
command: Current README assertion: 19 Markdown links and 19 local links resolve; 49/49 UAT, $gsd-execute-phase 01, Pending CPU requirements, unknown saved PC, and removal of the completed $gsd-verify-work route are checked.
denominator: 19/19 local Markdown links resolve; all current status/routing assertions pass.

## Summary

Current automated UAT aggregate (49 rows):

total: 49
passed: 49
issues: 0
pending: 0
skipped: 0
blocked: 0

Historical Plan 01-21 aggregate (rows 1–39, preserved):

total: 39
passed: 39
issues: 0
pending: 0
skipped: 0
blocked: 0

## Current Verification Evidence

- Native independent reviewer: fresh Debug build `build/owned-review25` completed 22/22 build steps; full CTest passed 13/13 and focused timing/unsupported/semantics/state CTest passed 4/4. Direct continuation-only passed 1/1 with 15 boundaries/90 calls; full state passed 5/5 with malformed 15, null 4, counter mismatch 1. The independent assessor used separate `build/security-audit-plan25` and independently passed its targeted 4/4 CTest and direct continuation/state/timing/semantics/fault denominators.
- Fresh Python evidence: contract controls 27/27 normal and optimized; acceptance controls 22/22 normal and optimized. Four churn-decrease probes, prior-crossing/lower-final control, exact caps, plus-one and active-pause controls have the outcomes recorded in rows 41–42.
- WR-02 checks the README at the Plan 01-25 source identity: 19 Markdown links and 19 local links resolved, status and then-current next-step assertions passed. The independent reviewer repeated the local link scan and `git diff --check`.
- Test 44 reran the README link/status check at its recorded revision and confirmed `$gsd-plan-phase 01 --gaps` as the next route at that time. This updated navigation only; the phase-goal report then remained `gaps_found`. The later gap-planning attempt returned inconclusive, so that route is superseded by the stale-verification gate documented above.
- Reviewer build/source identity: base source commit `9fba16b864cf74e3b8a9c97047bb27a5db544b59`, current profile `owned-p01-c14-continuation-2`, collection `cb77285dd7b821993e1e12ec96e72ed5e13bbf57da7d6dd433f07b3940275738`, map `be6e2c45f9590425a227bb9d6622d7629d080cca778eba29d5304bef3bd13a6d`, amendment `3728dc84fc27b2f51262ede8f916d755ff9340b80b069e53a731caea247b36ad`. Review/security final revision binding and deferred seal pass; candidate admission remains deferred pending phase-goal verification.
- Candidate disposition stays unqualified and not admitted. CPU-01–05 remain Pending, Phase 01 remains incomplete with stale phase-goal verification, Phase 02 remains gated, and original-silicon saved PC for `0x4AFC` remains unknown.


- Plans 01-26 and 01-27 coverage classifiers each report all entries auto-covered and no human-judgment checkpoint. Rows 45–48 record those four coverage entries as automated.
- Current checks ran against HEAD 83de9e95e3fdaf62bf732fe682d32a06bae733e2. No runtime, test, tool, collection, or acceptance source changed; the existing uncommitted 01-VERIFICATION.md edit was left untouched and is outside the scoped acceptance inputs. The corrected Plan 01-27 archive assertion passed.
- Legacy commit reconciliation: all 27 summaries lack an explicit commits field, so the workflow classified them as warnings, not mismatches. Eighteen recorded bases were available for measurement, eight plan windows could be bounded by plan_head_after, one historical base object was unavailable, and eight summaries had no base revision. No claimed commit count was contradicted.
- No human UAT checkpoint remains for machine-observable Phase 01 claims. Original-silicon saved PC remains unknown and is not converted into an emulator pass.
- README now records 49/49 automated checks and the current separate phase-goal verification route; row 49 checks all 19 local links and status assertions.
- Verify-post security check: the current SECURITY report is ASVS L1, verified with `threats_open: 0`; its Plan 01-27 C2 binding matches the active receipt, and `acceptance.py verify` passes. The report bytes were preserved because no security source or claim changed.

## Historical Plan 01-21 Verification Evidence (preserved verbatim)

- Tested workspace base revision: `5ab5e41e50f55fd67d304b1a121f3325ea624942`. Changes during this run were limited to `.planning` documentation/configuration; owned C sources and tests were not modified.
- `cmake --preset owned-debug`, `owned-release`, `owned-asan-ubsan`, and `owned-tsan`; each matching `cmake --build --preset ...` and `ctest --preset ...` completed successfully: 13/13 per lane, 52/52 total.
- `python3 -m unittest discover -s tests/owned_cpu -p 'test_*.py'` and the same command under `python3 -O`: 54/54 each.
- `contract.py validate`, `contract.py budget`, `contract.py self-test`, `acceptance.py verify`, `acceptance.py self-test`, `inventory.py check --build-dir build/owned-debug`, and `acceptance.py review-check --review experiments/owned_cpu/REVIEW.md --revision 931e2f0` passed.
- The installed GSD phase predicate confirms all 39 UAT rows pass; it blocks phase completion only on the existing `01-VERIFICATION.md` status. The workflow's `--uat-only` example is unsupported by this installed CLI, so it was not retried.
- The receipt reports `unqualified` and `not-admitted`; CPU-01–05 remain pending and Phase 02 remains gated. The original-silicon saved PC for 0x4AFC remains unknown. No broad CPU, board, BIOS, game, or cross-platform claim is made.
- The nine historical imported-candidate rows are evaluated only for the current observable contract: they are not reused as owned-core evidence. The unavailable original-silicon oracle is recorded as unknown, and the owner-approved candidate exclusion is directly tested.

## Historical Plan 01-21 Gaps

No new UAT issues were observed. The canonical phase verifier remains `gaps_found`; this UAT result does not admit the backend or complete Phase 01.

### 50. Plan 01-28 current documentation gate and canonical navigation
expected: The unchanged validator reproduces the deferred decision, README points to canonical STATE navigation, and mutation controls reject recurring document defects.
result: pass
source: automated
coverage_id: DOC-GATE-NAVIGATION
source_revision: 612c24558d010eef2cbc14958a7d34e1b8b208ef
command: PYTHONPATH=. python3 tests/owned_cpu/test_contract.py ContractControls.test_frozen_subject_and_pending_gate_validate; python3 tools/owned_cpu/contract.py validate; python3 tools/owned_cpu/acceptance.py verify; PYTHONPATH=. python3 tests/workflow/test_phase01_docs.py
denominator: Contract control 1/1; validate status pass, 24 markers, 10 historical files, 47 budget records and all five CPU requirements Pending; acceptance status pass, six collections, zero lane blockers and disposition unqualified; docs controls 5/5 (one current-checkout test plus four mutation controls), 20/20 local Markdown links resolve. All four commands exit 0, including the post-commit tracer gate.
identities: README.md SHA-256 af232fc95070a16ad9cd995820ad0fb46fce6fe96e60caf460970e580861b8f8; .planning/ROADMAP.md SHA-256 0cac1b97c86a17dfec9d327626302499c32979696a7a012171e30538cfd2b19c; tests/workflow/test_phase01_docs.py SHA-256 9191750df1def589c317297a8b0255e7968596a0bded54db4dda63b0126d424e.
initial_failure: At base b0b3b7aa123b2b18e0caf651624547b77cb7176c, the contract control ran 1 test with one pending_gate error (exit 1), validate rejected pending_gate (exit 2), acceptance rejected the same admission gate (exit 1), and the newly added docs module ran 5 tests with four failures (exit 1). Isolated in-memory probes also rejected the missing STATE link and stale fixed execution route. After repair, all four mutation controls detect their named defect.
scope: This row validates documentation and reproduces existing evidence; it grants no CPU admission. CPU-01–05 remain Pending, candidate unqualified/admission deferred, Phase 01 open, Phase 02 gated and original-silicon saved PC unknown.

### 51. Plan 01-28 code-review hardening — Markdown reference links
expected: The contributor-navigation regression resolves inline and reference-style links, honors case/whitespace-normalized labels and the first matching definition, and rejects broken destinations.
result: pass
source: automated
coverage_id: DOC-REFERENCE-LINKS
source_revision: 73a422dc7dd7149bb5c7cb8b1cde9528cc20338f
command: PYTHONPATH=. python3 tests/workflow/test_phase01_docs.py
denominator: 8/8 tests pass; 20/20 local links in the current README resolve. The suite includes six negative controls, a positive existing reference target, current-document validation, and first-definition duplicate-label behavior.
identity: tests/workflow/test_phase01_docs.py SHA-256 48f0638aaa2aded2c8c7dd52cd4d9310d1209090a8a76293c26fef27cc29b6c7.
review: Standard-depth code review is clean; the two reference-link findings and fixes are retained in 01-REVIEW.md.
scope: This review-driven hardening closes test-coverage defects only. It changes no README, validator, candidate, receipt, security report, CPU requirement or admission state.

## Current Supersession — 2026-10-05 Plan 01-28

Earlier route statements, including row 49 and prior Current Verification Evidence, are historical at their recorded identities. Rows 1–49 and all earlier aggregates remain verbatim and were not rerun. The 2026-10-05 whole-phase report is 8/9 `gaps_found`, closing the former report-binding gap; its document finding predates this repair. Row 50 records the initial repair checks; row 51 records the review-driven reference-link regression hardening. Follow `.planning/STATE.md` for the next action: one separate fresh whole-phase `gsd-verifier` before more gap planning or admission.

Active recorded UAT aggregate (51 rows; 49 historical passes plus two current documentation passes):

total: 51
passed: 51
issues: 0
pending: 0
skipped: 0
blocked: 0

This aggregate is not 50 current-revision checks and does not complete Phase 01.

Final Plan 01-28 bookkeeping follow-up: ROADMAP plan-status/count prose changed after Task 1. On working-tree base ed35fb118cc4f6cb74cd350cd4e14bdfca085f13, the same four affected commands above again exited 0, with unchanged 1/1 contract and 5/5 docs tests, 20/20 resolved links, validate pass and six unqualified collections/no lane blockers. Final ROADMAP SHA-256: f5db0e06851b2b59e48e47b57bbb6fe285922ebb3b2d493b633f20205069b563. README and test SHA-256 identities remain as in row 50; its original tested revision is preserved. Post-review hardening is separately recorded at row 51: the committed regression passes 8/8 at 73a422dc7dd7149bb5c7cb8b1cde9528cc20338f.
