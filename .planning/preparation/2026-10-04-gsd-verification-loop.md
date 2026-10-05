# GSD Phase Verification Loop Diagnosis

**Recorded:** 2026-10-04 (local; 2026-10-05 UTC)  
**Scope:** Glueyneo Phase 01 closeout; installed `@opengsd/gsd-core` 1.14.0  
**Status:** Workaround active; Phase 01 still requires a fresh whole-phase verdict.

## Observed state

- Phase 01 has 27 matching plan summaries. Plans 01-01–01-16 and 01-18–01-27 are execution-complete; Plan 01-17 is an answered checkpoint and remains incomplete. The live execute-phase index reports no runnable plans.
- UAT contains 49/49 automated checks. This closes its recorded machine-observable scope; it does not establish the phase goal or CPU admission.
- `01-VERIFICATION.md` was last generated before Plan 01-27 and still identifies the sealed security-report binding that Plan 01-27 later repaired. Its status remains `gaps_found`.
- `query verification.status` returns `gaps_found` and `$gsd-plan-phase 01 --gaps`. In installed 1.14.0, its implementation returns `gaps_found` before evaluating the covered-input fingerprint, so a failed report does not become `stale` after a repair summary changes.
- The no-runnable-plans branch in `execute-phase.md` special-cases only `stale` and `missing`; another existing status with an incomplete roadmap is treated as evidence that verification gates already ran and resumes at roadmap update. It skips a fresh assessment, though it does not turn `gaps_found` into `passed`. Thus `$gsd-execute-phase 01` is not a reliable refresh route for this report.
- `$gsd-verify-work 01` handles UAT and uses the same status routing; it is not a phase-goal verifier.

These behaviors explain the contradictory next commands: the status query routes the old negative verdict back to planning, while execute-phase can skip the verifier and resume at roadmap update. They do not establish that all prior plans were waste: several recorded implementation, evidence and bounded repair work. The avoidable process failure is allowing a known old gap/status to drive another plan before refreshing the verifier.

## Durable operating rule

1. After a gap-closure plan changes covered files or adds a plan/summary, run one fresh whole-phase `gsd-verifier` pass against current implementation, reports, plans and summaries before creating any further `--gaps` plan.
2. Compare the fresh report with the prior one. Do not repeat a gap already closed by current evidence, and do not infer phase completion from passing UAT or from the number of completed summaries.
3. Plan another repair only for a fresh, actionable, in-scope repository finding, with a direct acceptance check and explicit stop condition. Classify external/physical evidence, deferrals, and verifier/tooling errors separately; preserve them as narrow blockers rather than spawning repeated plans or repeating a finite search.
4. Keep UAT checks automated at the earliest useful seam and rerun only checks affected by relevant source or acceptance changes. Hand off only evidence that cannot be obtained in the current environment or a decision only the owner can make.
5. Until the installed GSD router is corrected or upgraded and verified, handle this exact `gaps_found`/no-runnable-plans state by directly dispatching `gsd-verifier` once. Never edit report status or digests to force a route. Recheck the runtime behavior after upgrade before retiring this workaround.

## Current next step

Dispatch `gsd-verifier` once for Phase 01. Then pause at the verification boundary. If the fresh result is `passed`, update canonical phase state according to the GSD workflow. If it still has gaps, classify them under the rule above before planning. The original-silicon saved PC remains unknown; no hardware result is inferred from this process repair.
