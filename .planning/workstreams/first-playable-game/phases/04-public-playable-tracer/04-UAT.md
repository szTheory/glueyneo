---
status: testing
phase: 04-public-playable-tracer
source: [04-01-SUMMARY.md, 04-02-SUMMARY.md, 04-03-SUMMARY.md, 04-04-SUMMARY.md, 04-05-SUMMARY.md, 04-06-SUMMARY.md, 04-07-SUMMARY.md, 04-08-SUMMARY.md, 04-09-SUMMARY.md, 04-10-SUMMARY.md, 04-11-SUMMARY.md, 04-12-SUMMARY.md, 04-13-SUMMARY.md, 04-14-SUMMARY.md, 04-15-SUMMARY.md, 04-16-SUMMARY.md, 04-17-SUMMARY.md, 04-18-SUMMARY.md, 04-19-SUMMARY.md, 04-20-SUMMARY.md, 04-21-SUMMARY.md, 04-22-SUMMARY.md]
started: 2026-10-10T11:38:03Z
updated: 2026-10-10T12:30:00Z
---

## Current Test
<!-- OVERWRITE each test - shows where we are -->

number: 4
name: Open security and review findings have your disposition
expected: |
  You decide how to handle the four high/open disclosure threats (T-04-11, T-04-15,
  T-04-18, T-04-20), the three medium/open threats (T-04-34, T-04-38, T-04-43) and the open
  review findings (WR-01, WR-06, WR-08, WR-09): run an independent security review and close
  what it proves, accept named risks, or keep them open. New related finding from this run:
  the full ignored qualification receipt records installed-tree object paths containing the
  local checkout path (the tracked summary drops them). Reply with your disposition, or
  "keep open" to leave them as they are.
awaiting: user response

## Tests

### 1. Pinned RetroArch plays the public fixture
expected: The direct smoke run opens pinned RetroArch 1.22.2 with the public fixture, shows the white guest marker, keeps it still with no input, moves it right on RIGHT without the LEFT control repeating that, unloads the content, quits normally, and leaves no RetroArch process.
result: pass
source: automated
evidence: \"Clean committed-snapshot receipt at 706516b5a60c (2026-10-10, agent-run): retroarch_smoke pass; marker [16,16] -> [47,16] on RIGHT; no-input frames stable; LEFT control did not move the marker; frontend_unloaded true; application quit path; no RetroArch left running. Summary tracked in 04-FRONTEND-RECEIPT.json. The user independently saw the window show a white square near the top left that moved right.\"
coverage_id: 04-02 P04-02-HOST; 04-06 D3; 04-08 D1; 04-09 P04-09-HOST-ROUTING; 04-12 P04-12-HOST; 04-18 D2; 04-19 D2; 04-21 D2
note: A direct smoke run is observation evidence only; it is not the committed-snapshot receipt (Test 2).

### 2. Clean committed-snapshot qualification receipt passes
expected: `python3 tools/verify_playable.py --retroarch /Applications/RetroArch.app --clean` builds a fresh archive of HEAD, passes every native, consumer and candidate lane, runs the pinned frontend lane, and writes a receipt with overall status pass and frontend status pass.
result: pass
source: automated
evidence: \"Rerun at 706516b5a60c after two in-session fixes passed every lane (status pass, retroarch_status pass).\"
history: \"First run at ea63b03 failed: Agent run at HEAD ea63b03 (2026-10-10): status fail, reason 'shared-build failed'; retroarch_status unknown, so the frontend lane never ran. A reproduction from `git archive HEAD` with BUILD_SHARED_LIBS=ON fails to link mvs_qualify: undefined symbol _gn_private_mvs_fetch_trace (hidden in libglueyneo.dylib). Fixed in e2d09a0 (mvs_qualify links a static production runtime; configure-time guard rejects private-header executables linking the public library). Second run then failed to open the installed shared core, which needed @rpath/libglueyneo.dylib with no rpath; fixed in 706516b (self-contained core in every build mode; package build check rejects a core depending on a Glueyneo library).\"
coverage_id: 04-08 D2; 04-15 D1; 04-15 D2; 04-19 D3; 04-21 D3

### 3. Status records follow the frontend evidence
expected: After a passing committed-snapshot receipt exists, REQUIREMENTS.md, 04-VALIDATION.md, docs/first-playable-build.md and the `--check-docs` gate all agree on the HOST-02 and frontend QUAL-03 status. Until that receipt exists, they keep it Pending/unknown and the docs gate rejects any affirmative frontend claim.
result: pass
source: automated
evidence: \"e5e3aac: --check-docs accepts Complete HOST-02/QUAL-03 only with a valid tracked receipt summary for a committed ancestor; test_verify_playable.py 31/31 including positive, invalid-summary and row-mismatch mutations. REQUIREMENTS.md, 04-VALIDATION.md, the build guide and STATE.md updated.\"
coverage_id: 04-17 D1; 04-19 D1; 04-22 D2

### 4. Open security and review findings have your disposition
expected: You have decided how to handle the four high/open disclosure threats (T-04-11, T-04-15, T-04-18, T-04-20), the three medium/open threats (T-04-34, T-04-38, T-04-43) and the open review findings (WR-01, WR-06, WR-08, WR-09): close them after an independent security review, accept them, or keep them open. Until then they stay open, and the evidence-map checker reconciles them exactly.
result: [pending]
coverage_id: 04-16 D1; 04-16 D2; 04-17 D2; 04-20 D1; 04-20 D2

### 5. Phase closeout batching rule
expected: You agree that future phase closeouts collect one evidence batch, write one consolidated plan for the repository gaps, and execute all its waves in a single run, as recorded in Plan 04-22.
result: pass
source: recorded-policy
evidence: \".planning/METHODOLOGY.md 'Phase closeout batch and default execution pace' already records this rule as current methodology; the user's 2026-10-10 automate/reduce-toil direction is consistent with it.\"
coverage_id: 04-22 D3

### 6. Original generated public guest loads through gn_load and draws a guest-state marker.
expected: Original generated public guest loads through gn_load and draws a guest-state marker.
result: pass
source: automated
coverage_id: 04-01 D1

### 7. Native frames validate caller video/audio buffers and report exact cycle-based progress.
expected: Native frames validate caller video/audio buffers and report exact cycle-based progress.
result: pass
source: automated
coverage_id: 04-01 D2

### 8. Right input moves the guest marker and wrong-direction/no-input controls fail the expected trace.
expected: Right input moves the guest marker and wrong-direction/no-input controls fail the expected trace.
result: pass
source: automated
coverage_id: 04-01 D3

### 9. The Libretro bridge runs one native fixture frame and forwards input and pixels through the callback ABI.
expected: The Libretro bridge runs one native fixture frame and forwards input and pixels through the callback ABI.
result: pass
source: automated
coverage_id: 04-02 P04-02-CALLBACK

### 10. The exported opted-out symbols resolve and return the specified safe values; callbacks and native frames agree.
expected: The exported opted-out symbols resolve and return the specified safe values; callbacks and native frames agree.
result: pass
source: automated
coverage_id: 04-02 P04-02-ABI

### 11. Public fixture source, assertion ancestry, output identity, and affirmative redistribution basis are auditable.
expected: Public fixture source, assertion ancestry, output identity, and affirmative redistribution basis are auditable.
result: pass
source: automated
coverage_id: 04-03 D1

### 12. A single named CMake target deterministically regenerates the same artifact for native and RetroArch consumers, and a byte mutation is rejected.
expected: A single named CMake target deterministically regenerates the same artifact for native and RetroArch consumers, and a byte mutation is rejected.
result: pass
source: automated
coverage_id: 04-03 D2

### 13. Pinned Z80 candidate admitted for the named synthetic instruction, bus, IRQ, reset, continuation, bounded-work and instance workload.
expected: Pinned Z80 candidate admitted for the named synthetic instruction, bus, IRQ, reset, continuation, bounded-work and instance workload.
result: pass
source: automated
coverage_id: 04-04 D1

### 14. Pinned ymfm YM2610 candidate passes source/state, deterministic clock/sample, isolation, reset/continuation, callback/exception/bounds, and installed static/shared C-consumer admission gates.
expected: Pinned ymfm YM2610 candidate passes source/state, deterministic clock/sample, isolation, reset/continuation, callback/exception/bounds, and installed static/shared C-consumer admission gates.
result: pass
source: automated
coverage_id: 04-05 D1

### 15. Fresh static/shared native installs and real out-of-tree C consumers pass.
expected: Fresh static/shared native installs and real out-of-tree C consumers pass.
result: pass
source: automated
coverage_id: 04-06 D1

### 16. The generated public fixture and full clean CTest suite pass with recorded identities.
expected: The generated public fixture and full clean CTest suite pass with recorded identities.
result: pass
source: automated
coverage_id: 04-06 D2

### 17. The pinned Z80 candidate passes the documented synthetic workload.
expected: The pinned Z80 candidate passes the documented synthetic workload.
result: pass
source: automated
coverage_id: 04-06 D4

### 18. The pinned YM2610 candidate passes source, direct and installed static/shared C consumer gates.
expected: The pinned YM2610 candidate passes source, direct and installed static/shared C consumer gates.
result: pass
source: automated
coverage_id: 04-06 D5

### 19. Qualification source identity is bound to a full Git commit and a complete fail-closed tree inventory.
expected: Qualification source identity is bound to a full Git commit and a complete fail-closed tree inventory.
result: pass
source: automated
coverage_id: 04-07 D1

### 20. The qualification guide explains snapshot inputs, receipt fields, and historical frontend evidence.
expected: The qualification guide explains snapshot inputs, receipt fields, and historical frontend evidence.
result: pass
source: automated
coverage_id: 04-07 D2

### 21. Generated public fixture rebuild and native consumer checks remain covered by the final clean qualification.
expected: Generated public fixture rebuild and native consumer checks remain covered by the final clean qualification.
result: pass
source: automated
coverage_id: 04-08 D3

### 22. The native fixed-input fixture controls and wrong-input assertions remain covered by the SDK regression suite.
expected: The native fixed-input fixture controls and wrong-input assertions remain covered by the SDK regression suite.
result: pass
source: automated
coverage_id: 04-08 D4

### 23. Qualification and frontend diagnostic sinks remove complete private paths while preserving bounded status details.
expected: Qualification and frontend diagnostic sinks remove complete private paths while preserving bounded status details.
result: pass
source: automated
coverage_id: 04-10 D1

### 24. Direct smoke accepts the generated fixture identity and rejects same-size modified bytes before Popen.
expected: Direct smoke accepts the generated fixture identity and rejects same-size modified bytes before Popen.
result: pass
source: automated
coverage_id: 04-10 D2

### 25. Both normal and cleanup quit requests accept only the pinned bundle identifier and use bounded fixed-shape AppleScript.
expected: Both normal and cleanup quit requests accept only the pinned bundle identifier and use bounded fixed-shape AppleScript.
result: pass
source: automated
coverage_id: 04-10 D3

### 26. Repository-backed receipt validation rejects forged file and symlink rows even after aggregate digest recomputation.
expected: Repository-backed receipt validation rejects forged file and symlink rows even after aggregate digest recomputation.
result: pass
source: automated
coverage_id: 04-11 D1

### 27. The validation map records observed focused results and checks that security and frontend blockers remain explicit.
expected: The validation map records observed focused results and checks that security and frontend blockers remain explicit.
result: pass
source: automated
coverage_id: 04-11 D2

### 28. Boolean byte/count fields reject against a committed one-byte fixture after aggregate recomputation.
expected: Boolean byte/count fields reject against a committed one-byte fixture after aggregate recomputation.
result: pass
source: automated
coverage_id: 04-12 P04-12-RECEIPT

### 29. Complete ambiguous private spans and temporary descendants are removed from retained diagnostics.
expected: Complete ambiguous private spans and temporary descendants are removed from retained diagnostics.
result: pass
source: automated
coverage_id: 04-12 P04-12-PRIVACY

### 30. Current evidence map requires three open security threats and five unresolved review dispositions.
expected: Current evidence map requires three open security threats and five unresolved review dispositions.
result: pass
source: automated
coverage_id: 04-12 P04-12-MAP

### 31. Current source/state identity and owned-target build evidence pass with corruption controls intact.
expected: Current source/state identity and owned-target build evidence pass with corruption controls intact.
result: pass
source: automated
coverage_id: 04-12 P04-12-INVENTORY

### 32. Current security and review evidence reconciles with severity-aware counts and source-faithful mutations.
expected: Current security and review evidence reconciles with severity-aware counts and source-faithful mutations.
result: pass
source: automated
coverage_id: 04-18 D1

### 33. Evidence-map, qualification, frontend-contract, and docs gates reject the targeted false claims and reconcile current test counts.
expected: Evidence-map, qualification, frontend-contract, and docs gates reject the targeted false claims and reconcile current test counts.
result: pass
source: automated
coverage_id: 04-21 D1

### 34. Exact independent-review path and revision provenance is enforced by the evidence-map gate.
expected: Exact independent-review path and revision provenance is enforced by the evidence-map gate.
result: pass
source: automated
coverage_id: 04-22 D1

## Summary

total: 34
passed: 33
issues: 0
pending: 1
skipped: 0
blocked: 0

## Gaps

[none open — G-04-2 (shared-build link failure blocking the receipt) was found and fixed in this session; see Test 2 history]
