# Owned MC68000 implemented subset

Status: **implemented diagnostic slice; backend admission remains pending**.
This document separates behavior implemented in Plan 01-08 from the contracted
work in later plans. It does not claim complete MC68000 compatibility or
hardware qualification.

## Implemented now

The private `owned_cpu` target is authored C17. Its opaque instance owns all
CPU registers, status, counters, stop/IRQ inputs and execution flags. Bus and
allocator callbacks plus their userdata are supplied per instance. Callback
bindings must outlive the instance. Reentry or concurrent calls on the same
instance are unsupported; separate instances share no mutable runtime state.

Reset reads the initial SSP and PC as four ordered, big-endian 16-bit transfers
from vector bytes 0 through 7. It enters supervisor mode with SR `0x2700` and
reports 40 reset cycles separately. An odd reset PC or stack pointer returns
`OWNED_CPU_ADDRESS_ERROR`; no exception frame is attempted. Other data and
address register values are initialized to zero by this implementation, which
is deterministic state initialization rather than a claim about their
hardware reset values.

| Operation | Accepted encoding and effect | MC68000 instruction cycles |
|---|---|---:|
| `MOVEQ #imm8,Dn` | `0111 ddd 0 iiiiiiii`; all D0–D7; signed 8-bit immediate sign-extended to 32 bits; N/Z from result, V/C clear, X preserved | 4 |
| `ADDQ.L #1..8,Dn` | `0101 qqq 0 10 000 ddd`; all D0–D7; data register direct only; encoded `qqq=000` means 8; modulo-2^32 sum; N/Z/V/C/X updated | 8 |
| `MOVE.L Dn,(abs.L)` | `0010 001 111 000 ddd`; all D0–D7 sources; absolute-long destination only; high word is written before low word; N/Z from value, V/C clear, X preserved | 20 |
| `STOP #imm16` | Exact opcode `0x4e72`, followed by one immediate word; supervisor-only; loads SR, applies stack-bank switching, and enters stopped state | 4 |

Instruction fetches and guest word accesses use 16-bit bus callbacks. Guest PC
and effective addresses remain 32-bit and are masked to the MC68000's 24-bit
physical bus only for callbacks. Address additions use defined 32-bit unsigned
wrap before that mask. Odd logical word/long addresses are rejected before a
bus callback. A longword write performs the high-word transfer first and
low-word transfer second. If the second callback fails, the first successful
write is retained and the instance enters terminal host-fault state.

`owned_cpu_run` accepts cycle budgets from 0 through 1,000,000. Zero performs
no callback or state change. Nonzero work completes whole instructions; a
request shorter than the next instruction can overshoot by that instruction's
remaining cycles. Results distinguish budget exhaustion, STOP, unsupported
opcode, privilege violation, odd-address error, and host callback failure, and
include PC/IR at decode failures. Unsupported instructions do not increment
the completed instruction count and leave PC at the unsupported opcode.

`STOP` privilege is checked explicitly. A user-mode STOP reports
`OWNED_CPU_PRIVILEGE_VIOLATION` without fabricating a vector frame; full guest
exception processing remains later work. IRQ level inputs and a transition to
level 7 are retained per instance, but this slice does not accept, vector, or
wake on interrupts.

The original guest in `tests/cpu/guest_fixture.c` is linked unchanged. Scenario
A computes 10 and writes `00 00 00 0a` to `0x1000`; scenario B computes 16 and
writes `00 00 00 10` to `0x1004`. After four completed instructions, PC is
`0x10e`, the CPU is stopped, and instruction cycles total 36, excluding reset
cycles. `tests/owned_cpu/test_diagnostic.c` checks both scenarios, zero-work
behavior, final state, the exact cycle total, and high-word-first writes.

The test target also compiles a guarded private hook that seeds a D register so
ADDQ signed overflow can be tested at `0x7fffffff` without hundreds of millions
of guest instructions. This hook is enabled only for the owned experiment's
test build and is not part of a consumer or product target.

## Explicitly unsupported or not yet established

- NOP, RESET instruction, RTE, TRAP, ILLEGAL exception, MOVE-to-SR, absolute
  word load, interrupt acceptance/wakeup, and exception frames.
- Guest-visible address-error exception handling. Odd reset vectors and odd
  instruction/data accesses return an explicit host-facing address status;
  odd-address recovery frames are not built.
- Guest bus-error input, nested exception recovery, instruction prefetch,
  wait states, arbitrary mid-instruction bus suspension, and board timing.
- Register reset values beyond the initial SSP, PC, and SR behavior above.
- Later MC680x0 models, FPU/SoftFloat, generated or imported runtime code,
  JIT, BIOS, commercial games, and public/durable state compatibility.

An unsupported opcode or addressing form returns its exact fault PC and IR as
`OWNED_CPU_UNSUPPORTED_OPCODE`. Even the canonical `0x4afc` ILLEGAL word is
reported as unsupported in this first slice: it is not yet a guest exception.
Host callback failure is terminal until reset or destruction. A reset can
retry after the host repairs its callback or mapping. No `setjmp`, process
termination, filesystem access, wall clock, environment lookup, or hidden
engine is used by the runtime.

## Oracle and limits

The initial instruction encodings, results and timing come from the primary
Motorola *M68000 Family Programmer's Reference Manual* and *M68000 User's
Manual* references and page mapping in [`tests/cpu/ORACLE.md`](../../tests/cpu/ORACLE.md).
The User's Manual's Table 8-5 gives MOVEQ=4 and ADDQ.L-to-Dn=8 clocks; Table
8-3 gives MOVE.L Dn-to-absolute-long=20; Table 8-12 gives STOP=4. The original
guest's 36-clock total is the sum for this exact recipe. It is not a measured
hardware result or Neo Geo board timing claim.

The behavioral scope, work caps, and named negative control remain governed by
[`CONTRACT.md`](CONTRACT.md). Passing the first guest and its mutation control
only opens the next reviewed work gate; it does not admit the backend.
