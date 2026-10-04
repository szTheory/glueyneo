# Bounded owned CPU decision

Disposition: **unqualified / GAPS_FOUND**. This decision establishes no backend
admission. Phase 01 remains open for a separate GSD verification step; Phase 02
is gated. CPU-01–04 remain Pending. CPU-05 has a reproducible bounded outcome,
but its canonical requirement remains Pending while the contract finding is
unresolved. A resource threshold alone neither accepts nor rejects the core.

## Current candidate scope — 2026-10-04, Plan 01-24

This section supersedes the active support and reproduction wording below;
all earlier observations, counts, findings and collection identifiers remain
historical evidence. The active candidate contract is the unchanged frozen
`CONTRACT.md` baseline SHA-256
`6ec5b901efb87618b2a03e348bd3fc068e28ae0fc24665a4c041067a1f0c2f73`
plus the single additive P01-C-14 / D1-14 amendment in
`illegal-reconciliation.json`, content SHA-256
`3728dc84fc27b2f51262ede8f916d755ff9340b80b069e53a731caea247b36ad`
and active identity
`27af8df79b55f83bffdef63981defc23984fff6b4e0002d10e99621310340419`.
The frozen baseline and its archived bytes are preserved, not regenerated.

Exact `0x4AFC`, after a successful opcode fetch, returns
`OWNED_CPU_UNSUPPORTED_OPCODE` with logical opcode PC/fault PC and fetched IR.
There is no vector-4 read, exception frame write, completed dispatch or guest
instruction/exception charge. Registers, SR, stack banks, previous PC, vector
marker, guest memory and event counters remain unchanged. Completed preceding
reset, IRQ and instruction events retain their separate charges. Failed opcode
fetch retains the terminal host-fault policy; odd fetch retains address-error
policy. Repeated rejection does not dispatch or advance past the opcode;
recovery requires an explicit caller action under the private API, never an
invented ILLEGAL exception or implicit resume.

Original MC68000 defines canonical ILLEGAL and vector 4; candidate exclusion is
a capability limit, not a hardware reinterpretation. Intentional ILLEGAL users
are incompatible with this candidate. D1-09/11/12/13/14 govern: original-silicon
saved PC remains unknown, with neither `$100` nor `$102` selected. F14-03 and
T-01-15-03 remain HIGH/open pending independent scope reconciliation review.

Retained selected forms are MOVEQ, ADDQ.L to Dn, MOVE.L Dn to absolute-long,
STOP, NOP, RESET, RTE short frame, TRAP #0, immediate MOVE to SR and
absolute-long MOVE.W to Dn, plus the named privilege, address-error, IRQ masking
and level-7 behavior in `SUBSET.md`. The original diagnostic stores remain
10 and 16, instruction clocks 36 and separate reset40. Private continuation
requires identical included source identity, cloned guest memory and fresh
destination bus/memory ownership; it does not promise cross-build restoration.
Same-instance overlap is unsupported; independent-instance evidence remains
bounded to the recorded cases.

The manifest identifies authored inputs and their MIT notice, pinned copied
Unity test sources/notices and fixture/oracle ancestry. Unity remains test-only;
only authored `cpu.c` belongs to the runtime archive. No new source was acquired;
no imported CPU core, FPU, SoftFloat implementation, generator, commercial
media or manual bytes enter the closure. Native-host evidence is limited to
the exact receipt's compiler/OS/architecture/configuration. CMake 3.20 execution,
other platforms, silicon/board/pin timing, full ISA, BIOS/game compatibility,
public ABI, public snapshot/replay/save compatibility and gameplay performance
remain unknown or excluded. Original expectation recipes and primary manual
references retain their documented ancestry; emulator agreement is not silicon
truth.

## Repaired continuation evidence and boundaries

The active profile is `owned-p01-c14-continuation-2`: fifteen named
ready-boundary checkpoints and six fresh-owner continuation calls per checkpoint
(90 calls). `owned-p01-c14-1` remains the historical 13/78 profile, and
pre-profile collections retain their original 12-CTest interpretation. The two
added checkpoints are guest-reachable. The restore validator therefore no
longer rejects an odd PC or odd selected A7 solely for alignment; it still
requires the active A7 to agree with the SR-selected USP/SSP and retains the
format, identity, required-field, range, and counter-invariant checks. The
malformed-record suite continues to reject invalid size/version/identity/masks,
invalid boolean or IRQ values, inconsistent active stack and event accounting,
and null inputs atomically, without bus effects. These checks do not treat a
reachable deferred-fault value as malformed.

`RTE_odd_PC` resumes from PC `$101`. Its next run detects an odd instruction
fetch before issuing an odd-address callback, builds the local vector-3 frame,
and returns to handler PC `$180`: 50 address-error clocks, zero completed
instructions, requested 1 / elapsed 50 / overshoot 49. The recorded functional
callback order is seven frame writes at `$2ffc,$2ffe,$2ffa,$2ff8,$2ff4,$2ff6,
$2ff2`, then vector reads at `$000c,$000e`. Increasing-address frame contents
are SSW `$0016`, fault address `$00000101`, IR `$0000`, SR `$2700`, and saved PC
`$00000101`. The source owner and restored fresh owner are compared for the
complete run result, architectural/private state, guest memory, and ordered
callbacks. The chosen saved PC is only this deterministic fixture behavior;
original-silicon saved PC remains unknown under P01-C-13.

`SR_switch_odd_USP` resumes at PC `$104` with user SR `$0000`, odd USP/A7
`$00002801`, and even inactive SSP `$00003000`. The next instruction is a
privileged MOVE-to-SR, so the observed next event is vector-8 privilege entry
using the even supervisor stack, not an address-error or host-fault event. Its
short frame at `$2ffa` contains old SR `$0000` and saved PC `$00000104`; the
functional trace fetches the opcode/extension at `$104/$106`, writes PC high,
PC low, then SR at `$2ffc/$2ffe/$2ffa`, and reads vector 8 at `$0020/$0022`.
It returns handler PC `$180` after 34 clocks (one completed privileged
dispatch; requested 1 / elapsed 34 / overshoot 33), preserving the odd USP.
The uninterrupted and restored owners are compared over the whole event and
subsequent six-call sequence. This documents continuation of the reachable
state and its actual next event; it does not claim that the inactive odd USP
causes a fault on this path or establish hardware restart accuracy.

Plan 01-22 changed no record layout or version and refreshed the private
`cpu.c` identity to
`f11a282d5f571a67fff687c08cc90a44f5b6ff54bb5334b9c21bf17a4abcbee7`.
`state-inventory.json` records the same identity and both historical/current
profiles. The private fixed C record remains same-build only; guest memory is
cloned separately, destination bus/allocator bindings remain owned by the new
instance, and no public ABI, arbitrary-byte parser, cross-build state, snapshot,
replay, durable save, or same-instance concurrency promise is introduced.

Plans 01-23 repaired CR-02/WR-01 by making the frozen budget validator monotonic across all four
cumulative churn counters and made budget sealing inclusive at the unchanged
caps: 115,200 active seconds, 28,800 diagnostic-gate seconds, 6,000 runtime
added/deleted lines, and 8,000 test/tool added/deleted lines. Exact-limit values
pass; a crossing, cumulative decrease, invalid value, or required active pause
does not. Ledger entries append measured or conservative effort and churn;
reverted work is still charged and never refunded. No threshold is reset or
raised by this repair.

Current reproduction uses the committed manifest closure and the profile
`owned-p01-c14-continuation-2`:

```sh
python3 tools/owned_cpu/contract.py validate
python3 tools/owned_cpu/contract.py budget
python3 tools/owned_cpu/acceptance.py collect --preset owned-debug --preset owned-release --preset owned-asan-ubsan --preset owned-tsan
python3 tools/owned_cpu/acceptance.py verify
python3 tools/owned_cpu/inventory.py check --build-dir build/owned-debug
```

The Plan 01-24 collection attempt is the first run with this new profile; lane
outcomes and counts belong to its appended receipt and are not implied by this
procedure. Collection appends exact source/build/input/output identities and
clears the active derived seal after its complete object is preserved in
`superseded_seals`. Inspect every lane status and actual nonzero denominator;
process exit alone does not qualify a lane. Existing build directories are
reused, so these whole-lane runs are not claimed as cold builds. The bounded
cold-process test remains a separate observation. Current profile checks fifteen
boundaries/90 calls, thirteen CTests per lane, five state Unity runners,
timing25/semantics17, the six named controls, isolation32/32, and cold16. The
versioned collector validates the applicable denominators.

Plan 01-25 owns the next independent source review/security reassessment, bound
to the exact latest collection and amendment. Only that plan may produce a new
deferred seal after its gates. Phase-goal verification is a separate workflow.
Results remain unqualified/GAPS_FOUND, CPU-01–05 Pending, Phase 01 open and
Phase 02 gated. No recursive containing collection digest is embedded in this
included report.

## Historical exact reviewed and executed identities

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
