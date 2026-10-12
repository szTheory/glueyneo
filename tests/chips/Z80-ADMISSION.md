# Z80 Candidate Admission

**Status: ADMITTED for the bounded Phase 04 admission workload.** This result
qualifies the pinned candidate and private adapter for the exact synthetic
instruction, bus, and interrupt sequences below. It does not claim complete
Z80 instruction coverage, private game sound-driver coverage, or original
silicon equivalence. The implementation remains isolated to the admission
test target; later integration must preserve this source identity and evidence.

## Source and license

The sole imported source is `third_party/chips/z80.h`, from `floooh/chips` at
immutable revision `9e88298ce56319953ac7a43213a1120359f7a3a6` (commit date
2026-09-26). Its SHA-256 is
`6ca70ffd91b1bdbaf00f7a41e7092b326145fd1c95dcdd7bb01183370de734f3`.
`third_party/chips/NOTICE.md` retains the full zlib/libpng license text.
`tests/chips/check_z80_source.py` checks that identity and required inventory.

## Source and state inventory

- **Transitive source:** `z80.h` is self-contained apart from `<stdint.h>`,
  `<stdbool.h>`, `<string.h>`, and `<assert.h>`. It does not include
  `chips_common.h` or another floooh/chips file. Only `z80.h` is vendored.
- **Mutable globals/statics:** no mutable file-scope or function-local static
  storage was found. `_z80_szp_flags[256]` and `_z80_indirect_table[256]` are
  file-scope `static const` lookup tables. `_z80_*` helpers are static inline
  functions with per-call locals.
- **Per-instance state:** the entire mutable candidate state is the public
  `z80_t`: decoder `step`; effective `addr`; `dlatch`, `opcode`, `hlx_idx`,
  `prefix_active`; `pins`, `int_bits`; `pc`; primary `af`, `bc`, `de`, `hl`,
  `ix`, `iy`; `wz`, `sp`, `ir`; shadow `af2`, `bc2`, `de2`, `hl2`; `im`,
  `iff1`, and `iff2`. The adapter must preserve both this value and current
  external bus pins at a supported continuation boundary.
- **Callbacks:** upstream declares no callbacks. The caller services memory,
  I/O and interrupt acknowledge pins synchronously; the private adapter's bus
  callback and userdata are per instance and borrowed for that instance's life.
- **Lazy initialization:** none found. `z80_init`/`z80_reset` zero the provided
  instance and initialize its registers directly. Lookup tables are compile-time
  constants.
- **Reset/failure paths:** `z80_init`, `z80_reset`, `z80_tick`,
  `z80_prefetch`, and `z80_opdone` assume a valid non-null `z80_t`; init asserts
  the pointer when assertions are enabled. The candidate has no error return or
  bus-failure mechanism. The adapter must validate pointers, bound tick work,
  latch callback failure, and require reset before resuming after bus failure.
- **Selected behavior:** this report only concerns the bounded instruction,
  interrupt, and bus sequences explicitly named in the admission test. It does
  not claim complete sound-program coverage or hardware compatibility.

## Test ancestry and evidence boundary

**Primary expected-result source:** ZiLOG, *Z80 Family CPU User Manual*,
document `UM008001-1000`, official PDF at
`https://www.zilog.com/docs/z80/z80cpu_um.pdf`, SHA-256
`7d75728aa57384b0cdc1e85ad86c2a4b176f1e7fffc61bb03459457e4ea89e7e` (downloaded
2026-10-07). The timing overview and instruction timing material supply the
7-T `LD A,n`, 13-T `LD (nn),A`, 8-T `IM 1`, 4-T `EI` and `NOP`, interrupt
sampling, and interrupt-acknowledge expectations. This is a primary CPU
specification, not a measurement of Glueyneo's target board or original CPU
silicon. The candidate reports its write pin callback on tick 19 of the
20-tick combined program; that identifies the adapter's sampled pin stage,
while the full instruction totals remain 7+13 T-states.

**Upstream-test provenance:** `floooh/chips-test/tests/z80-zex.c` at immutable
revision `3785836e76c43922f78a50e1f8adfed259ab9672` (2026-10-04), file SHA-256
`917db9f097763b5dda2589923b7ce52e4f2747ee16fc2c3014574b05180b0e32`, is an
upstream conformance-harness reference. No upstream harness or ROM bytes are
copied or executed. Its result is not an oracle for this admission. Emulator
comparison alone does not establish original-hardware truth.

## Declared workload and results

The exact public admission workload is encoded in `tests/chips/test_z80.c`:

- `LD A,0x42` reads opcode address `0x0000` and operand `0x0001`, consumes 7
  candidate ticks, and leaves A=`0x42`.
- `LD A,0x5a; LD (0x4000),A` consumes 20 ticks total (7+13), writes `0x5a` to
  `0x4000`, and records the ordered read/write bus effects. The external write
  callback is observed at tick 19, during the final instruction's write
  machine cycle; the last tick completes the 20-T instruction sequence.
- `IM 1; EI; NOP; HALT` uses the documented 8+4+4-T instruction sequence. A
  one-tick INT pulse on the tick before the NOP completion edge is not
  acknowledged; a pulse on the completion tick is accepted, and the interrupt
  acknowledge pin event is reported at candidate tick 19. The mode-1 path
  pushes return PC `0x0004` to `0xfffe`/`0xfffd` and vectors to `0x0038`.
- Reset restores the candidate's documented initial register state and cycle
  counter without changing externally owned memory. A checkpoint after the
  `z80_opdone()` continuation boundary replays 13 ticks to identical CPU state,
  memory and ordered bus trace.
- Two programs with different register values and memory destinations match
  their isolated baselines under 96 ticks of alternating interleaving and 16
  repeated concurrent cold-instance pairs (96 ticks per instance per pair).
- A failed bus callback latches `BUS_FAILURE`, blocks further cycles and
  checkpoint restore until reset. A restored `UINT64_MAX` cycle count returns
  `CYCLE_LIMIT` without wrapping, ticking the CPU, or accessing the bus.

Eight Glueyneo-owned positive test cases pass. Five observation mutations
(cycle count, bus address, IRQ-ack tick, restored continuation state, and
instance owner) each fail their intended assertion; CTest registers each as an
expected-failure control. The bus-fault test caught a real adapter bug during
RED: restore cleared the error latch. The implementation now rejects restore
while failed and reset clears the latch.

## Admission gates

| Gate | Evidence | Result |
|---|---|---|
| Immutable source, full notice, transitive source and mutable-state inventory | `python3 tests/chips/check_z80_source.py` | PASS |
| Cycle totals and ordered bus effects | 2 fixed programs; Zilog manual identity above | PASS |
| Interrupt assertion, acceptance, and adjacent-tick boundary | One early pulse and one boundary pulse; Zilog timing/interrupt sections | PASS |
| Reset and supported-boundary continuation | Reset control plus restored CPU/pins, external memory and bus trace | PASS |
| Distinguishable independent instances | 2 isolated baselines, interleaved run, 16 concurrent pairs | PASS |
| Failure containment and bounded work | Bus-failure latch/reset and `UINT64_MAX` no-wrap test | PASS |
| Sanitizer run | `sdk-asan-ubsan` and `sdk-tsan`, 6 admission/mutation CTest cases each | PASS |
| Selected workload scope | Exact synthetic workload defined above; private game driver is outside this claim | PASS, bounded |

Admission commands:

```sh
python3 tests/chips/check_z80_source.py
cmake --preset sdk-debug
cmake --build --preset sdk-debug --target z80_admission_test
ctest --preset sdk-debug -R '^z80_admission' --output-on-failure --no-tests=error
cmake --preset sdk-asan-ubsan
cmake --build --preset sdk-asan-ubsan --target z80_admission_test
ctest --preset sdk-asan-ubsan -R '^z80_admission' --output-on-failure --no-tests=error
cmake --preset sdk-tsan
cmake --build --preset sdk-tsan --target z80_admission_test
ctest --preset sdk-tsan -R '^z80_admission' --output-on-failure --no-tests=error
```

SND-01 is admitted only for this named workload. New behavior required by a
private sound program must be added to the workload and re-qualified before
that program is claimed supported. No physical pin capture or complete sound
driver trace was produced here.
