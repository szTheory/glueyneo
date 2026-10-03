# Bounded owned CPU decision

Disposition: **unqualified / GAPS_FOUND**. This decision establishes no backend
admission. Phase 01 remains open for a separate GSD verification step; Phase 02
is gated. CPU-01–04 remain Pending. CPU-05 has a reproducible bounded outcome,
but its canonical requirement remains Pending while the contract finding is
unresolved. A resource threshold alone neither accepts nor rejects the core.

## Exact reviewed and executed identities

The core/evidence repair revision is
`ca79b00f368120a4087705d669eaa10de7e930ab`. Its initial repaired collection digest
is `3b31b169be64a09c68eed8600135e23566752819501740662dcf8b2ff5771380`,
with source-map digest
`8d78b6706d84cb469be849dd4ed0cd06a1e2f85ab1bb8f8cf6511edd04631cd8`.
The final collection additionally binds this acceptance report as an authored
distribution input. Its exact revision and digest are the last collection in
the machine-readable results and the final reviewed-revision section. This
report avoids naming its own containing collection digest recursively.
`acceptance-results.json` records exact command, compiler, configuration,
fixture/oracle, archive, executable and sanitized output identities.
`source-manifest.json` owns current distribution identities; the earlier state
inventory remains dated field/callback evidence. The runtime `cpu.c` identity
is unchanged from Plan 12:
`8ac6ded7859184651f6eb3fff8a87c073f8e24a98d66175b64c3d86f69cbd15f`.

The initial independent review and first counterexamples are preserved at
`a43b93e`; the distinct non-author repair is `ca79b00`. `REVIEW.md` records the
fresh independent repair review, all prior findings and the unresolved blocker.
All collections remain append-only, including the first collection digest
`a96c08b486ee48e960b98b058bb763d3c6b5067dd33b85c00e193897d9536fc9`.
No historical Musashi files, failed receipts or charges have been rewritten.

## Plan 01-15 unresolved reconciliation and Plan 01-16 qualification

The actual reconciliation branch is **unresolved**. Plan 01-15's authored
`illegal-reconciliation.json` records exact vendor PDF hashes, printed editions,
retrieval date, competing interpretations and the missing adjudication. Its
embedded base64 archive preserves the original contract bytes and code-start
SHA-256 `6ec5b901efb87618b2a03e348bd3fc068e28ae0fc24665a4c041067a1f0c2f73`.
No canonical supersession or runtime, validator, fixture or oracle repair was
justified. `SUBSET.md:61`, SHA-256
`435d0c1a8e991b32c59e732b590bc0d9ae23be2983e0d14eaaadd126e20d078d`,
remains read-only observed-behavior provenance, with no adjudicated supersession.

The preceding source reconciliation task revision is
`6a54e2c0b2747861276853c8e036bd3f2a42ed04`. Runtime, header and state inventory
retain their recorded exact hashes; private same-build state identity is
unchanged. Plan 01-16 includes the reconciliation record and this report in
the exact distributed closure and collects fresh native lanes for unchanged
behavior. These observations do not resolve the source rule or establish
silicon compliance. Final collection, independent review, seal revision and
budget identities live in the machine-readable receipts and `REVIEW.md`;
historical identities above remain historical.

The UM ninth edition/copyright1993 general pre-execution and next-unexecuted
language favors fault PC `$100`. Its ILLEGAL-specific trap/group wording leaves
a competing sequential-PC `$102` reading. PRM copyright1992 does not explicitly
select that saved value; PRMER Rev1/03-2007 lists no ILLEGAL correction, whose
absence proves neither interpretation. Historical catalog/retrieval labels
are not printed editions. Independent review must retain HIGH/open unless an
authoritative instruction-specific adjudication addresses the competing reading.
The new wrong-PC control and canonical repair remain withheld in this branch;
existing controls qualify only their named observations. All nine flagged
planning assumptions remain unresolved. CPU-01–05 remain Pending, Phase 01
open/GAPS_FOUND and Phase 02 gated. The next workflow command for retained
ambiguity is `$gsd-plan-phase 01 --gaps`; this plan runs no phase verification.

## Remaining blocker and next decision

**F14-03 remains open:** the frozen canonical `CONTRACT.md` requires ILLEGAL to
save the next PC; `cpu.c`, `SUBSET.md`, `ORACLE.md` and the direct timing test
save the faulting PC. Green tests prove the implemented observation, not
agreement with that contract. Reconcile the primary manual interpretation and
canonical contract through user-directed gap planning before admission. This
report does not infer a silicon defect or change runtime to satisfy conflicting
prose. Contract mutation is outside Plan 14's five-path repair scope and would
also invalidate the frozen contract identity.

F14-01 and F14-02 were evidence-tool defects: a rehashed receipt could retain
green logs with wrong lane commands/configuration, and accepted read-only
verification could omit the historical failure guard. The non-author fixer
added direct rejection regressions and strict command/configuration/status,
output and artifact checks plus the historical guard. Fresh independent
re-review is required and recorded in `REVIEW.md`; repaired findings do not
erase their original counterexamples. No further runtime repair is authorized
by this bounded outcome.

## Reproduction and results

Run from the repository root with the recorded toolchain. These commands use
only original/public-rights fixtures, local builds and explicit CPU callbacks:

```sh
python3 tools/owned_cpu/contract.py validate
python3 tools/owned_cpu/inventory.py check --build-dir build/owned-debug
python3 -O tools/owned_cpu/acceptance.py self-test
python3 -m unittest discover -s tests/owned_cpu -p test_acceptance.py
python3 -O -m unittest discover -s tests/owned_cpu -p test_acceptance.py
python3 tools/owned_cpu/acceptance.py collect --preset owned-debug --preset owned-release --preset owned-asan-ubsan --optional-preset owned-tsan
python3 tools/owned_cpu/acceptance.py review-check --review experiments/owned_cpu/REVIEW.md --revision HEAD
python3 tools/owned_cpu/acceptance.py seal
python3 tools/owned_cpu/acceptance.py verify
python3 tools/owned_cpu/contract.py budget
```

Collection appends a new receipt and clears its seal; it does not silently
update review or admit a backend. Review-check intentionally fails with
`blocking review finding` while F14-03 is open. Ordinary seal and read-only
verify pass for this honest unqualified record; `--require-accepted` is not
appropriate. Use the sealed revision for review-check after later metadata
commits: the report remains bound to exact source, not a moving branch name.

The repaired collection passes 12/12 CTest cases in each of Debug, Release/O2,
ASan+UBSan and optional TSan, 48/48 total. Per lane, Unity cases are diagnostic
2, semantics 17, timing 23, isolation 4, faults 5 and state 5. Each lane observes
13 continuation checkpoints, 32 interleaved pairs, 32 concurrent pairs, 16
cold processes and five named negative controls. Collector unit tests pass
14/14 normally and under `-O`; self-tests pass six rejection and two
classification controls in both modes. All denominators are nonzero.

## Supported observations and limits

Only the exact forms in `SUBSET.md` are implemented: MOVEQ, ADDQ.L to Dn,
MOVE.L Dn to absolute-long, STOP, NOP, RESET, RTE short frame, TRAP #0,
canonical ILLEGAL, immediate MOVE to SR and absolute-long MOVE.W to Dn.
The original two diagnostic stores are 10 and 16, with 36 instruction clocks
and separate reset40. Named privilege, level-3 masking, level-7 edge/held-level,
odd-address, terminal host-fault and whole-event budget cases are observed.
The ILLEGAL saved-PC observation is explicitly disputed by the canonical
contract. Continuation is private, same-source, fresh-owner and guest-memory
cloned; restore-over-ready remains unclaimed. Same-instance overlap is
unsupported. Runtime archive closure contains only authored `cpu.c`, with
explicit bus/allocator bindings and no mutable machine globals; Unity is
test-only and pinned with retained MIT notice.

Actual host evidence: Darwin 25.6.0 arm64, AppleClang 21.0.0.21000101, SDK26.5,
Python3.14.4, CMake4.4.3 and Ninja1.13.2. The CMake3.20 provisional floor and
schema2 presets remain unchanged; execution at exactly3.20 is **unknown**.
No other platform/compiler is qualified. There is no silicon capture, full
ISA, Neo Geo board timing, BIOS/game, public ABI, cross-build state, durable
save, replay or gameplay performance claim. RESET has an observed signal event
without physical device behavior; bus traces implement a functional contract,
not pin timing, wait states or prefetch fidelity.

Motorola/NXP primary manual citations and oracle ancestry live in `CONTRACT.md`
and both `ORACLE.md` files. Original authored recipe expectations are separate
from emulator comparisons; Musashi/MAME/SingleStepTests/Rocket68 agreement is
not independent hardware truth. No commercial media or manual bytes are
distributed. Descriptive diagnostic cost receipts are single startup-dominated
process samples with elapsed and child CPU deltas; peak memory is unknown and
these values establish no gameplay throughput baseline.

## Accounting

`budget-ledger.json` is the authoritative append-only cumulative effort and
Git added/deleted nonblank churn register. It charges all agents, including
review, failed regressions, repair, retest and closeout, with conservative
interval allowances when an exact spawn clock was unavailable. Frozen caps
remain 115,200 active seconds, 28,800 diagnostic seconds, 6,000 runtime churn
and 8,000 test/tool churn. The diagnostic gate remains passed at2,565 seconds;
no attempt counter, refund or threshold-only rejection is introduced. Final
totals are in the seal's budget snapshot and Plan14 summary; a later metadata
charge is appended rather than rewriting earlier entries.
