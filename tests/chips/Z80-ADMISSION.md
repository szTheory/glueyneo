# Z80 Candidate Admission

**Status: NOT ADMITTED — execution evidence pending.** The candidate remains
private to the admission test target and is not part of the playable runtime.

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

**Upstream-test provenance:** the upstream `chips-test` `z80-zex.c` harness is
identified in the accepted Phase 04 research as candidate-conformance
provenance.

No upstream harness or
ROM bytes are copied into this repository. Upstream emulator results alone do
not establish original-hardware truth. Glueyneo-owned expected values are
derived from the documented Z80 instruction and bus-cycle specifications for
the short named sequences; the report must state exact references and any
uncertain interrupt boundary. Emulator comparison can be supplemental only.

## Admission gates

| Gate | Evidence | Result |
|---|---|---|
| Immutable source, full notice, transitive source and mutable-state inventory | Source checker and this inventory | Pending |
| Cycle and ordered bus effects | Glueyneo-owned fixed programs | Pending |
| Interrupt assertion, acceptance, and adjacent-tick boundary | Glueyneo-owned boundary probes with named expected timing source | Pending |
| Reset and supported-boundary continuation | Captured candidate state plus external bus pins and memory | Pending |
| Distinguishable independent instances | Isolated baselines plus repeated interleaved execution | Pending |
| Failure containment and bounded work | Bus-failure latch and checked tick/cycle limit | Pending |
| Sanitizer run | `sdk-asan` or equivalent supported sanitizer configuration | Pending |

Admission requires every gate to pass with a nonzero denominator. Any missing,
failed, unsupported, or oracle-ambiguous selected-workload behavior keeps SND-01
open and requires bounded replanning before phase completion.
