# SDK original diagnostic oracle and provenance

This fixture is an original Glueyneo work, licensed under the repository MIT
license. It contains no BIOS, game ROM, commercial data, or third-party guest
bytes. The C recipe is `guest_fixture.c`; the SDK runner and native test link
that single recipe. The generated binary is a build artifact and is not
committed.

## Independent CPU oracle

Expected effects are derived from the instruction encodings and MC68000
behavior in the Motorola/NXP primary manuals below. They are not copied from
the owned CPU output or another emulator. The manual timing tables describe
the selected MC68000 instruction forms; the mapped ROM/RAM callback ordering
is the project's functional diagnostic contract, not a physical Neo Geo bus
capture.

| Guest PC | Words | Manual-derived effect |
|---|---|---|
| `0x0100` | `7007` | `MOVEQ #7,D0` gives D0 = 7 |
| `0x0102` | `5680` | `ADDQ.L #3,D0` gives D0 = 10 |
| `0x0104` | `23c0 0000 1000` | Store D0 as a big-endian long at RAM `0x1000` |
| `0x010a` | `7200` | Clear D1 before the word load |
| `0x010c` | `3239 0000 1008` | Load initialized word `0x1234` into the low word of D1 |
| `0x0112` | `5681` | Add 3, giving D1 = `0x00001237` |
| `0x0114` | `23c1 0000 1004` | Store D1 as a big-endian long at RAM `0x1004` |
| `0x011a` | `7400` | Clear D2 before the BSS load |
| `0x011c` | `3439 0000 100a` | Load the zero-filled BSS word at `0x100a` |
| `0x0122` | `5282` | Add 1, giving D2 = 1 |
| `0x0124` | `23c2 0000 1010` | Store D2 as a big-endian long at RAM `0x1010` |
| `0x012a` | `4e72 2700` | Execute privileged `STOP #$2700`; next PC is `0x012e` |

The reset vectors are big-endian SSP `0x2000` and PC `0x0100`. The ROM is 512
bytes at guest address zero. RAM is 4096 bytes at `0x1000`; its ten-byte
initialization prefix has `0x1234` at offsets 8–9. All remaining RAM starts
at zero, so the word at `0x100a` is BSS. The CPU reads this source word,
increments it, and writes a separate named result at `0x1010`.

Scenario B keeps the same program topology but changes the first immediate
pair to `700b 5a80` (11 + 5 = 16) and the initialized word to `0x2345`
(result `0x2348`). It makes per-instance ownership comparisons distinguishable.

The instruction timings are 4, 8, 20, 4, 16, 8, 20, 4, 16, 8, 20, and 4
cycles respectively: 132 instruction cycles. The MC68000 external-reset
recovery is 40 cycles, for 172 cycles through the final STOP boundary. The
following cumulative boundaries were checked through the ordinary API:

| Cumulative guest cycles | Boundary PC | Completed instructions | Event |
|---:|---:|---:|---|
| 40 | `0x0100` | 0 | Reset recovery |
| 44 | `0x0102` | 1 | MOVEQ |
| 52 | `0x0104` | 2 | ADDQ.L |
| 72 | `0x010a` | 3 | MOVE.L store |
| 76 | `0x010c` | 4 | MOVEQ |
| 92 | `0x0112` | 5 | MOVE.W load |
| 100 | `0x0114` | 6 | ADDQ.L |
| 120 | `0x011a` | 7 | MOVE.L store |
| 124 | `0x011c` | 8 | MOVEQ |
| 140 | `0x0122` | 9 | MOVE.W load |
| 148 | `0x0124` | 10 | ADDQ.L |
| 168 | `0x012a` | 11 | MOVE.L store |
| 172 | `0x012e` | 12 | STOP |

At the terminal boundary, the public observations are arithmetic `10`,
initialized-data result `0x1237`, and BSS-derived result `1` for scenario A;
scenario B returns `16`, `0x2348`, and `1`. The run requests exactly 172
cycles and reports 172 elapsed, zero overshoot, 12 instructions and STOP. A
STOP result alone is not diagnostic success: the runner checks every named
result and the terminal run fields.

## Sources and limits

- Motorola, *M68000 Family Programmer's Reference Manual* (1992), printed
  pages 4-11–4-12 (`ADDQ`), 4-116–4-117 (`MOVE`), 4-134 (`MOVEQ`) and 6-85
  (`STOP`): <https://www.nxp.com/docs/en/reference-manual/M68000PRM.pdf>.
- Motorola, *M68000 8-/16-/32-Bit Microprocessors User's Manual*, ninth
  edition (1993), section 6.3.1 (reset vectors), tables 8-2, 8-3 and 8-5
  (instruction timings), table 8-12 (`STOP`) and table 8-14 (external reset
  recovery): <https://www.nxp.com/docs/en/reference-manual/MC68000UM.pdf>.
- The Phase 01 admission report independently records the bounded accepted
  C17 backend and corrects WR-01's old user-mode MOVE-to-SR prose. This
  fixture does not use that privileged sequence or alter its frozen receipts:
  `.planning/phases/01-cpu-acceptance-experiment/01-VERIFICATION.md` and
  `01-29-ADMISSION-REVIEW.md`.
- The backend source is the repository-owned MIT candidate accepted only for
  its bounded diagnostic subset. Its source identity used by this build is
  SHA-256 `f11a282d5f571a67fff687c08cc90a44f5b6ff54bb5334b9c21bf17a4abcbee7`.
- Test assertions use the retained Unity source at immutable commit
  `b6763fbd9cedfacaa89e2ad9fd00d615a234e355`. Its copied-file hashes and
  upstream MIT notice are recorded in `third_party/unity/PROVENANCE.md`;
  Unity is linked only into test executables, never the SDK runtime.

The manuals establish CPU instruction effects and the cited MC68000 timings,
not Neo Geo board behavior, original-silicon qualification, BIOS boot, game
compatibility, or bus-pin timing. The accepted backend's timing remains a
bounded candidate contract. A reference emulator is not this oracle's source.

## Bounded progress and integer edges

`gn_run` reports the backend's actual event charges. The native contract accepts
requests from 0 through 1,000,000 guest cycles. A zero request consumes nothing.
An outstanding external-reset recovery event costs 40 cycles as a whole, even
when the request is smaller: requests 1, 39, 40 and 41 therefore report
elapsed 40, 40, 40 and 44, with overshoots 39, 1, 0 and 3 respectively. The
41-cycle call completes the first 4-cycle `MOVEQ`. A request above the limit is
rejected before the CPU or guest RAM changes. After STOP, a later positive
request advances stopped idle time by that exact amount and dispatches no
instruction. Reaching STOP during a request can likewise consume the remaining
requested idle cycles; elapsed time is not clamped to the pre-STOP instruction
total. The cap does not turn host wall time into guest progress.

The diagnostic tests also alter only original legal instruction bytes while
keeping expected values independent: `MOVEQ #$7f,D0; ADDQ.L #3,D0` stores
`$00000082`; `MOVEQ #$80,D0; ADDQ.L #3,D0` stores `$ffffff83`; and
`MOVEQ #$ff,D0; ADDQ.L #3,D0` stores `$00000002`. Replacing the second opcode
with `ADDQ.L #1,D0` after `MOVEQ #$ff,D0` checks unsigned wrap to zero. The
results are read from the fixture's named arithmetic mailbox through
`gn_observe`; complete CPU registers remain private. These expected effects
follow the MOVEQ and ADDQ encodings and 32-bit result rules in the primary
Programmer's Reference Manual (printed pp. 4-11–4-12 and 4-134).

Unsupported candidate opcode `$4afc` reports the bounded fault PC and opcode;
it does not expose the register file. A callback host fault remains sticky until
reset, while reset restores the original fixture and permits a successful run.
The private test build also seeds a stopped instance's accounting counters at
the exact `uint64_t` limit and verifies that a rejected idle event leaves the
complete image/state digest unchanged. Host-fault and counter-overflow outcomes
map to the existing `GN_RUN_ERROR`/`GN_STATUS_CPU_FAILURE` pair; guest
address/privilege/unsupported-opcode faults use the existing `GN_RUN_FAULT`
reason, with unsupported instruction details populated when available. The
public result layout is unchanged.

These are bounded event-accounting and instruction-result claims for the
accepted candidate forms. They do not qualify arbitrary instruction streams,
mid-instruction suspension, wait states, a Neo Geo board bus, or physical
silicon. The earlier Phase 01 WR-01 wording about a `$106` extension read on a
user-mode MOVE-to-SR privilege path is explicitly superseded by the current
[Phase 01 verification](../../.planning/phases/01-cpu-acceptance-experiment/01-VERIFICATION.md):
the accepted candidate enters vector 8 after opcode `$104` without reading
`$106`. That historical sequence is unrelated to this fixture and is not
repeated as a hardware claim here.

## Functional callback trace and exact controls

The private test SDK records at most 256 successful numeric callback events
per instance. Each event is a 24-bit-masked guest address, 16-bit width, value,
and read/write direction. Storage is fixed inside the test image; no trace
allocation or process-global trace state is used. When full, the trace keeps
the first 256 records and increments an explicit dropped count. The ordinary
original-guest suite observes 35 records with zero drops: four reset-vector
reads at `$0000/$0002/$0004/$0006`, instruction/extension/data reads, and six
RAM word writes. It asserts every address, direction, width and value.

The callback sequence proves only the selected functional mapping contract.
For example, event indices 9–10 write `$0000` then `$000a` at `$1000/$1002`;
20–21 write `$0000` then `$1237` at `$1004/$1006`; and 31–32 write `$0000`
then `$0001` at `$1010/$1012`. Reads at `$1008` and `$100a` return initialized
`$1234` and zero-filled zero. These are callback values/order in this native
implementation, excluding physical pins, prefetch, wait states and Neo Geo
board timing.

The supervisor in `tests/sdk/controls.py` leaves expected values fixed and
requires each child to exit normally with code 1, exactly one Unity failure,
one exact assertion ID and expected/observed wrong value, a positive assertion
denominator, and a valid one-case failure summary/result. Crashes, signals,
timeouts, unrelated or multiple failures, unchanged values, missing records,
and zero denominators are rejected. Eight self-controls exercise those reject
paths. The eight consequential mutations and their fixed assertions are:

| Mutation | Intended assertion | Fixed expected | Mutated observed |
|---|---|---:|---:|
| MOVEQ input changes 7 to 8 | `sdk.observe.arithmetic` | 10 | 11 |
| Initialized word changes `$1234` to `$1235` | `sdk.observe.initialized` | 4663 | 4664 |
| BSS read adapter returns 1 | `sdk.observe.bss` | 1 | 2 |
| Run result adapter increments instruction count | `sdk.run.instructions` | 12 | 13 |
| Run result adapter increments elapsed cycles | `sdk.run.elapsed-cycles` | 172 | 173 |
| Run result adapter changes STOP to budget | `sdk.run.reason-stopped` | 1 | 0 |
| Observation adapter reverses arithmetic byte order | `sdk.observe.arithmetic-byte-order` | 10 | 167772160 |
| Trace adapter swaps the first two vector reads | `sdk.bus.event.00.address` | 0 | 2 |

Input mutations alter only fixture bytes before load. Adapter mutations are
guarded by `GLUEYNEO_SDK_TEST_HOOKS` and stored with the corresponding instance
image. The installed/public runtime is compiled without these declarations,
fields, trace functions or mutation branches. `sdk-controls` runs the normal
counted test, all eight controls, and four independent public-runner processes:
two for scenario A and two for scenario B. The supervisor writes each JSON
record to a distinct temporary result path and requires exact, matching named
outputs and run fields. A STOP result alone is insufficient.

## Equal-boundary instance determinism

Scenario A (`10`, `$1237`, `1`) and scenario B (`16`, `$2348`, `1`) first run
through the ordinary public API in separate instances to create owner-specific
baselines. The split schedule is `40,4,8,20,4,16,8,20,4,16,8,20,4`, with
cumulative guest-cycle boundaries `40,44,52,72,76,92,100,120,124,140,148,168,172`.
At all 13 boundaries the comparison includes public named observations, guest
PC, run reason, cumulative elapsed cycles, completed instructions, cumulative
overshoot, per-call requested/elapsed/overshoot/instruction fields, a
pointer-free image digest, and the private ordered-trace digest/count/drop
count. Each split call lands exactly on a selected event boundary and reports
zero per-call overshoot; the comparison does not generalize to arbitrary
budget partitions.

The `sdk-isolation` suite repeats each split sequence after reset, compares a
single 172-cycle call at the terminal boundary, interleaves 16 A/B instance
pairs, and runs 16 barrier-started concurrent A/B pairs. Every concurrent
owner also attempts a replacement that fails at its first allocation, checks
the pointer-free ROM/RAM/CPU-state digest and allocator live counts remain
unchanged, resets and resumes through the first instruction, then unloads and
destroys with no live allocation. The supervisor's two additional controls
require exact failures: `control-swapped-owner` must fail
`sdk.isolation.owner.arithmetic` (`10` expected, `16` observed), and
`control-altered-split-progress` must fail
`sdk.isolation.split-progress` (`40` expected, `41` observed).

The separate `sdk_cold` host supervisor starts eight fresh `sdk_diagnostic
cold` processes. Each process creates two distinct instances concurrently
before either worker proceeds, loads A/B, runs the same 13 split boundaries,
exercises one candidate replacement failure per owner, resets and resumes,
then unloads and destroys. Across the eight children this is eight concurrent
pairs, 16 owner executions, 16 candidate-failure paths, 16 reset recoveries,
and zero teardown leaks. A finite process timeout exists only in the host
supervisor; it never contributes guest progress or changes core semantics.

### Mutable state and concurrency inventory

The runtime sources `src/instance.c` and `experiments/owned_cpu/cpu.c` have no
mutable file-scope machine state. Each `gn_instance` owns its allocator
callbacks/userdata and `gn_image *`. Each `gn_image` owns its allocator,
ROM/RAM region byte storage and base/size metadata, RAM reset seed and size,
and `owned_cpu *`. Under `GLUEYNEO_SDK_TEST_HOOKS` only, that image also owns
the bounded trace array/count/drop count, one-shot callback failure count,
and mutation selector; those fields and hooks are absent from the production
library.

Each `owned_cpu` owns its bus/allocator callbacks and userdata, D0–D7 and
A0–A7 arrays, PC/previous PC, USP/SSP/fault PC, SR/instruction register,
stopped/IRQ/ready/fault/active/reset/exception state, and instruction,
instruction-cycle, reset-cycle, exception-cycle, idle-cycle, total-cycle and
reset-signal counters. The fixture recipe and boundary schedule are immutable.
In the test process, the selected-suite pointer is set before execution and is
read-only during worker activity; Unity and SDK assertion/case/failpoint
counters are touched only by the main test thread. Each worker uses a separate
stack-owned instance, allocator, result slot and worker argument, and workers
do not call Unity. The CMake `Threads::Threads` dependency and POSIX thread
primitives apply to the test executable only; this toolchain does not provide
the C17 `<threads.h>` header, so the test harness uses its available native
thread API. These checks cover distinct-instance access and do not qualify
concurrent calls on one instance, arbitrary host schedules, physical bus
timing, or original hardware.

## Reproduction and exact identities

From the repository root:

```sh
cmake --preset sdk-debug
cmake --build --preset sdk-debug
ctest --preset sdk-debug -L 'sdk-provenance|sdk-diagnostic' --output-on-failure --no-tests=error
ctest --preset sdk-debug -L sdk-run --output-on-failure --no-tests=error
ctest --preset sdk-debug -L sdk-controls --output-on-failure --no-tests=error
ctest --preset sdk-debug -L sdk-isolation --output-on-failure --no-tests=error
build/sdk-debug/glueyneo-diagnostic
build/sdk-debug/glueyneo-diagnostic --scenario-b
build/sdk-debug/glueyneo-diagnostic --write-fixture build/sdk-debug/diagnostic-original-a.bin
build/sdk-debug/glueyneo-diagnostic --check-fixture build/sdk-debug/diagnostic-original-a.bin
build/sdk-debug/glueyneo-diagnostic --write-fixture build/sdk-debug/diagnostic-original-b.bin --scenario-b
build/sdk-debug/glueyneo-diagnostic --check-fixture build/sdk-debug/diagnostic-original-b.bin --scenario-b
```

The fixture file is exactly `ROM[512] || RAM_INITIALIZATION[10]`; no runtime
archive/parser or firmware is involved. SHA-256 identities measured from the
generated scenario files are:

| Item | Length | SHA-256 |
|---|---:|---|
| Scenario A ROM + RAM prefix | 522 bytes | `495eb195089d0ee7e73f4090514980b47a5fd4a55869d9e7f46376bce1646948` |
| Scenario B ROM + RAM prefix | 522 bytes | `be1d769bc7c89530a5e09ac60f8cd89858454b0ae604dd0fe506dcd52b154855` |
| Recipe source `tests/sdk/guest_fixture.c` | — | `bf647458d5bb8e362d66876432f30c774924600de44c7ac97a4110d57174d8cb` |
| Recipe interface `tests/sdk/guest_fixture.h` | — | `09811d20d1556a2a356ee0ee86afeb1b811ff8b3f764a160e76c2de94f1865a1` |

The output digest uses no C struct layout, padding, or host byte order. Encode
the following fields in this order as three big-endian `u32`, four big-endian
`u64`, then two big-endian `u32`: arithmetic result, initialized result, BSS
result, requested cycles, elapsed cycles, overshoot cycles, instruction
count, terminal PC, and numeric STOP reason (`1`). The resulting 52-byte
scenario A record hashes to
`e0cb8ba07f599ed85a8217d196f577e539cddbba86f2c930da0ed5f468a806bf`; scenario
B hashes to
`b551afb0fd32171001a3155599f3ee51521a95b7994b4f94fdbb1861790c0cfb`.

The recorded execution environment was Darwin arm64, AppleClang
21.0.0.21000101, CMake 4.4.3, Ninja 1.13.2, schema-2 `sdk-debug` preset and
Debug configuration. CMake 3.20 is the retained provisional minimum and was
not exercised here. These identities describe the local diagnostic run;
they are not a supported-platform matrix or gameplay performance claim.
