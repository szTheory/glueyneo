# CPU candidate acceptance experiment

Status: not accepted; implementation and all CPU evidence pending.

## Frozen admission contract

<!-- freeze:start -->
Candidate: Musashi commit `313ebf1bd9f4d0d93341eb5ce21fd8a119e9dbdd` only.
Starting project revision: `3977c3bfbfdc752e1b43443aa3911c7012678177`.
No candidate adaptation preceded this contract.

Hard limits, with equality permitted and any excess requiring rejection:

| Resource | Maximum |
|---|---:|
| Substantive adaptation attempts | 2 |
| Active engineer/agent effort, cumulative | 16 hours |
| Active effort per attempt | 8 hours |
| Changed handwritten upstream files | 6 |
| Cumulative handwritten added plus deleted lines | 5,000 |
| Semantic repair lines, included in handwritten total | 500 |
| Adaptation helper/shim lines, included in handwritten total | 600 |
| Regenerated output files | 2 |
| Generated output lines, combined | 50,000 |
| Generated output bytes, combined | 2,097,152 |

The only editable handwritten upstream inputs are `m68k.h`, `m68kcpu.h`,
`m68kcpu.c`, `m68kconf.h`, `m68k_in.c` and `m68kmake.c`. The only generated
outputs are `m68kops.h` and `m68kops.c`; hand editing them is prohibited.
Count normal added/deleted lines against pristine inputs without whitespace
exemptions. Include moved/replaced code and adaptation support regardless of
path. Carry cumulative work and attempt maxima forward; neither a fresh file
nor a second attempt resets the allowance. Test, fixture and documentation
classification cannot conceal adaptation. Semantic repairs change instruction,
exception, error or cycle behavior; context/signature plumbing is counted in
the main total. Generated output is accounted separately.

Attempt 1 implements explicit contexts, minimal 68000 closure and one guest.
Attempt 2 may repair recorded concrete counterexamples inside the same total
caps. Stop immediately on exhaustion or an unrepairable rights, host-safety,
isolation or selected timing/state incompatibility. Preserve the failed patch
and counterexample, record rejection and halt dependent implementation. Do not
raise these limits, weaken the oracle or mark CPU-01 through CPU-04 complete.
A rejection may fulfill CPU-05's decision obligation but cannot admit Phase 2
or complete Phase 1. Replacement investigation requires a separate plan.

No global current-instance pointer, TLS routing, context swapping or global
execution lock qualifies. Runtime is C, uses explicit per-instance state and
host-owned bus/allocator bindings, and has no ambient host I/O, clock or process
termination. FPU/MMU/SoftFloat exclusion requires compiled and distributed
closure evidence. Timing is instruction-boundary qualified, not board timing.
<!-- freeze:end -->

## Execution ledger

The freeze commit is the first commit containing this file, identifiable by
`git log --reverse -- experiments/cpu/ACCEPTANCE.md`. Its exact identity will be
recorded below after committing, without changing the frozen section.

- Preparation began 2026-10-01T16:16:00Z; source adaptation has not started.
- Attempts started: 0. Upstream churn: 0. Helpers: 0. Semantic repairs: 0.
- Generated output admitted: none. No CPU tests have run.
