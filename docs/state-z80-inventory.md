# Z80 Candidate State Inventory

This inventory documents the private continuation codec for `z80_candidate`.
It records the exact pinned decoder source and its admissibility rules; it does
not qualify all Z80 behavior, MVS hardware, a durable save format, or a public
ABI.

## Source ancestry

The decoder is vendored unchanged from floooh/chips revision
`9e88298ce56319953ac7a43213a1120359f7a3a6` (2026-09-26), SHA-256
`6ca70ffd91b1bdbaf00f7a41e7092b326145fd1c95dcdd7bb01183370de734f3`.
The immutable source is [`third_party/chips/z80.h`](../third_party/chips/z80.h);
its full zlib/libpng license remains in
[`third_party/chips/NOTICE.md`](../third_party/chips/NOTICE.md). The private
adapter, validation, codec, and test failpoints are Glueyneo-owned code in
`src/chips/z80_candidate.c`; no local patch was made to the imported decoder.

The decoder-field map follows the `z80_t` declaration at `z80.h:337-366`.
The switch labels are mechanically checked from `z80_tick`'s step switch and
its named step definitions at `z80.h:401-431` by
[`tests/chips/check_z80_source.py`](../tests/chips/check_z80_source.py).
The decoder labels 0..1708 are contiguous, with no interior holes. The
codec rejects out-of-domain values; cross-field validation is needed because a
legal numeric label alone does not make its prefix, index, interrupt, or pin
state admissible.

Relevant source transitions:

| Source | State relation used by the codec |
| --- | --- |
| `z80.h:945-991` | `_z80_fetch` clears `hlx_idx` and `prefix_active`; chooses normal, IM0/1/2, or NMI entry; interrupt steps depend on `im`. |
| `z80.h:993-1030` | `_z80_fetch_cb/dd/fd/ed` selects prefix-step families; DD selects IX (`hlx_idx=1`), FD selects IY (`2`), CB/ED use index zero. The first DD/FD/CB/ED M1 step retains its prefix opcode. |
| `z80.h:1069-1071`, `z80.h:2684-2756` | Generated numeric cases cover base, CB, DDCB, and interrupt/NMI microsteps. |
| `z80.h:2759-2798` | Named DD/FD, CB, ED, and ordinary M1 continuation steps are 1685..1708. |
| `z80.h:2800-2810` | `cpu->pins` and `cpu->int_bits` are updated at each returned tick; INT is level-tracked and NMI is edge-latched. |

## Canonical schema

The **Z80 v1 canonical state** is exactly 76 bytes. It is a private chip-state
format used by checked staging. Multi-byte values are unsigned fixed-width
big-endian scalars; no `z80_t`, union, padding, pointer, or host struct bytes are
copied. `GZ80` plus version byte `01` identifies the schema. The two pin fields
are both retained because the chip's internal previous pins and the adapter's
post-callback data bus can differ in the data lines.

| Offset | Bytes | Field | Source field / meaning |
| ---: | ---: | --- | --- |
| 0 | 4 | `GZ80` | Private codec magic |
| 4 | 1 | version `1` | Schema version |
| 5 | 2 | `step` | `z80_t.step` |
| 7 | 2 | `addr` | `z80_t.addr` |
| 9 | 1 | `dlatch` | `z80_t.dlatch` |
| 10 | 1 | `opcode` | `z80_t.opcode` |
| 11 | 1 | `hlx_idx` | `z80_t.hlx_idx` |
| 12 | 1 | `prefix_active` | Canonical boolean `0` or `1` |
| 13 | 8 | `cpu.pins` | `z80_t.pins`, prior internal pin sample |
| 21 | 8 | `cpu.int_bits` | `z80_t.int_bits`, INT level and latched NMI edge |
| 29 | 2 | `pc` | Program counter union, encoded once |
| 31 | 2 | `af` | AF union, encoded once |
| 33 | 2 | `bc` | BC union, encoded once |
| 35 | 2 | `de` | DE union, encoded once |
| 37 | 2 | `hl` | HL union, encoded once |
| 39 | 2 | `ix` | IX view of the shared HL/IX/IY union |
| 41 | 2 | `iy` | IY view of the shared HL/IX/IY union |
| 43 | 2 | `wz` | WZ union, encoded once |
| 45 | 2 | `sp` | SP union, encoded once |
| 47 | 2 | `ir` | IR union, encoded once |
| 49 | 2 | `af2` | Shadow AF |
| 51 | 2 | `bc2` | Shadow BC |
| 53 | 2 | `de2` | Shadow DE |
| 55 | 2 | `hl2` | Shadow HL |
| 57 | 1 | `im` | Interrupt mode |
| 58 | 1 | `iff1` | Canonical boolean `0` or `1` |
| 59 | 1 | `iff2` | Canonical boolean `0` or `1` |
| 60 | 8 | `pins` | Adapter's returned pin sample after synchronous bus service |
| 68 | 8 | `cycles` | Adapter tick count |

Capture requires a healthy candidate and at least 76 bytes of output capacity;
it writes exactly 76 bytes. Stage requires exactly 76 input bytes, validates
magic, version, canonical booleans, fields, and relations, and only then makes
one staged allocation. It performs no bus callback or CPU tick. Bus callback
and userdata are omitted from bytes. Rebind copies the healthy destination's
existing borrowed callback/userdata to the staged object; apply is allocation-
free and callback-free, and its precondition is a successful rebind for that
same still-healthy destination. A callback failure makes its source candidate
ineligible for capture. A faulted destination is rejected by rebind.

## Source-derived admissibility

| Decoder steps | Required relation |
| --- | --- |
| 0..255 | `step == opcode`; `prefix_active` is true exactly when `hlx_idx` is nonzero. |
| 256..511 | ED table: `step == 256 + opcode`, prefix active, `hlx_idx == 0`. |
| 512..1611 | Generated instruction microsteps; `hlx_idx` is 0, 1, or 2 and a nonzero index requires an active DD/FD prefix. |
| 1612..1620 | CB/CBHL microsteps: active prefix, index zero. |
| 1621..1635 | DDCB/FDCB microsteps: active prefix, IX or IY index. |
| 1636..1641 | IM0 interrupt entry: prefix/index cleared and `im == 0`. |
| 1642..1654 | IM1 interrupt entry: prefix/index cleared and `im == 1`. |
| 1655..1673 | IM2 interrupt entry: prefix/index cleared and `im == 2`. |
| 1674..1684 | NMI entry: prefix/index cleared. |
| 1685..1699 | DD/FD continuation: active prefix and IX/IY index; at step 1685, opcode DD requires IX and FD requires IY. |
| 1700..1702 | CB M1 continuation: active prefix, index zero; step 1700 retains opcode CB. |
| 1703..1705 | ED M1 continuation: active prefix, index zero; step 1703 retains opcode ED. |
| 1706..1708 | Ordinary M1 continuation: prefix cleared and index zero. |

Opcode/index relations are validated at prefix entry: DD with IX, FD with IY,
CB at step 1700, and ED at step 1703.

All states also require `im <= 2`, `hlx_idx <= 2`, defined Z80 pin bits only,
`cpu.int_bits` containing only INT/NMI, and adapter/internal pin control bits
agreeing (the data byte may differ after a memory or I/O read). The internal INT
bit must agree with the current adapter INT pin. NMI remains edge-latched and is
not required to equal the current NMI pin. Out-of-domain steps are rejected;
this pinned revision has no interior step holes to enumerate.

The admission suite records 80 live cut points across DD/FD, DDCB, ED, CB,
ordinary fetch, HALT, and instruction microsteps, plus continuations captured at
IM1 step 1642 and NMI step 1674. It compares resumed bus traces, memory bytes,
cycles, pins, and completion flags on independently bound memory. Seventeen
malformed format/relationship cases cover exact lengths, magic/version,
noncanonical booleans, step domain, prefix/index, interrupt mode, interrupt
latch, and pin mismatch. These are focused synthetic continuations, not a
claim that every instruction or every possible decoder value was exercised.

## Allocation and failure ownership

Adapter construction and staged state each have one allocation. The explicit
`Z80_CANDIDATE_TEST_HOOKS` compile definition is attached only to
`z80_admission_test`; it exposes a caller-owned failpoint counter in the private
header for this test binary. This test-only hook is not part of the public
allocator/API. The candidate and staged object retain that counter only in the
hook-enabled test build. There is no process-global mutable failpoint. The
allocation-failure sweep fails the adapter allocation and the state allocation
in turn, checks allocation/free accounting, and compares destination/peer state
and future behavior after failed staging, and then observe a successful
allocation path. Invalid bytes are rejected before allocation. The published
consumer/runtime build does not compile these test hook declarations or fields.
