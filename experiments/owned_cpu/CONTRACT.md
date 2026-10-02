# Owned MC68000 diagnostic contract

Status: **proposed acceptance contract; no owned implementation is admitted**.
This is the only current owned-core scope. It supersedes the active
Musashi-only direction for replacement planning; the Musashi source, receipts,
failures and accounting remain historical and immutable.

## Product and backend boundary

Implement an owned C17 MC68000 subset for the existing original diagnostic,
behind one private whole-CPU seam. The model is the original MC68000 with its
16-bit external data bus and 24-bit physical address bus. Select the complete
backend statically for a build/test run. Do not dispatch individual opcodes to
another engine, convert live backend state, or expose a public CPU/plugin ABI.
Each instance owns every mutable CPU field and receives its bus, interrupt
inputs, and bounded execution request explicitly. No process-global current
instance, TLS routing, global execution lock, filesystem, environment, clock,
network, host process exit, compulsory thread, or device callback is allowed.

The private interface must cover create/destroy, reset from guest vectors,
bounded run, IRQ level/edge input, explicit result/error reporting, test-only
observation, and private state save/restore into a fresh destination. A run
must make bounded instruction-boundary progress or return a named status.
State inventory must include all instance-owned and transient execution state;
continuation must be exercised after restoration and independent-instance
behavior must be tested. Host pointers and host-only bookkeeping are not guest
state.

## First executable diagnostic

Run the byte-for-byte instruction recipe in `tests/cpu/guest_fixture.c`; do not
copy or adapt its source. Reset vectors load SSP `0x00002000` and PC `0x00000100`.
The initial instruction subset is exactly:

| Instruction | Supported encoding/addressing form | Architectural result |
|---|---|---|
| `MOVEQ #imm8,Dn` | `0111 ddd 0 iiiiiiii`; all D0–D7, signed 8-bit immediate sign-extended to 32 bits | Set N/Z from 32-bit result, clear V/C, preserve X. |
| `ADDQ.L #1..8,Dn` | `0101 qqq 0 10 000 ddd`; data-register direct destination only; encoded `qqq=000` means 8 | Add modulo 2^32; set N/Z/V/C and X according to 32-bit addition. |
| `MOVE.L Dn,(abs.L)` | Long MOVE with D0–D7 source and absolute-long destination only; two extension words | Store high word before low word; preserve Dn; set N/Z from value, clear V/C, preserve X. |
| `STOP #imm16` | Opcode `0x4e72`, one immediate word; supervisor-only | Load the specified SR and enter stopped state. A qualifying interrupt may wake the instance. |

Scenario A computes 10 and stores big-endian `00 00 00 0a` at `0x1000`.
Scenario B computes 16 and stores `00 00 00 10` at `0x1004`. After the four
completed instructions, PC is `0x10e`, the instance is stopped, and instruction
cycles total 36; reset cycles are recorded separately and excluded from 36.
The named wrong-behavior control mutates the original fixture's first
immediate, and must fail the exact expected store assertion.

## Required admission cases after the first diagnostic

The first diagnostic is not the admission suite. Before CPU-01–04 can be
considered complete, implement and test these additional exact operations and
boundaries:

| Case | Required scope |
|---|---|
| `NOP` | Exact opcode `0x4e71`; no register/SR change; 4 instruction cycles. |
| `RESET` instruction | Exact opcode `0x4e70`; supervisor-only; 132 instruction cycles; named reset side effect and bus observation must be explicit. |
| `RTE` | Exact opcode `0x4e73`; supervisor-only; restore SR and PC from the MC68000 short frame, including USP/SSP switching; 20 instruction cycles for the supported short frame. |
| `TRAP #0` | Exact opcode `0x4e40`; vector 32; stack old SR and next PC on supervisor stack; enter supervisor mode and fetch handler PC. |
| `ILLEGAL` | Exact canonical illegal instruction word `0x4afc`; vector 4; stack old SR and next PC. Other unsupported encodings must report `UNSUPPORTED_OPCODE`, not be treated as this instruction. |
| `MOVE.W #imm16,SR` | Exact opcode `0x46fc` and one immediate word; supervisor-only; replace SR and switch active stack correctly. |
| `MOVE.W (abs.L),Dn` | Long absolute address extension and D0–D7 data-register destination; replace only the low word and set N/Z, clear V/C, preserve X. Odd operand address takes address-error exception. |
| Level-3 IRQ masking | A level-3 request is not accepted while SR mask is 3 or higher; acceptance occurs at an instruction boundary when unmasked; vector is autovector 27. |
| Level-7 edge IRQ | A low-to-high transition is latched and accepted regardless of SR mask; a continuously high level does not create repeated interrupts; vector is autovector 31. |
| Privilege violation | User-mode execution of `STOP`, `RESET`, `RTE`, or `MOVE.W #imm,SR` raises vector 8 before the privileged operation takes effect. |
| Address error | Odd word/long data access and odd instruction fetch are checked before invoking an aligned bus transaction. Use the MC68000 address-error frame and halt on a nested exception-frame fault. Do not claim restart fidelity: the MC68000 manual calls the saved PC for bus/address error unpredictable. |

`RESET`, `TRAP`, `ILLEGAL`, `RTE`, privilege, and address-error outcomes are
derived from the MC68000 manual references below. Save old SR before changing
supervisor/trace/interrupt bits. Group-1/2 exception frames save the next
unexecuted PC for the named instruction exceptions. The address-error frame
records the manual-described context; it does not promise an address-error
restart address. No guest bus-error frame, prefetch fidelity, wait states,
arbitrary mid-instruction bus suspension, or board-cycle claim is in scope.

## Bus, time, errors, and observations

Guest address arithmetic is checked before applying the MC68000 24-bit bus
mask. Guest words are big-endian 16-bit bus transfers. Long reads and writes
are high-word first, then low-word, with each observed 16-bit transfer kept in
order. The ordinary transaction sequence is this implementation's explicit
contract; agreement with Musashi/MAME is a comparison result, not hardware
truth. Odd word/long guest addresses take the documented address-error path,
never host undefined behavior or a rounded address.

Each run accepts a finite cycle/instruction budget and returns elapsed guest
cycles, completed instruction count, final PC, stop/error reason, and fault PC
and IR when decode fails. An unsupported model/configuration is rejected before
execution. Unsupported opcode or addressing form returns
`UNSUPPORTED_OPCODE` with the faulting PC and IR; it must not masquerade as
guest `ILLEGAL`, NOP, a completed instruction, or success. Invalid host
arguments, inaccessible host buffers, and nested exception faults return
explicit host-safe errors without process termination or out-of-bounds access.

Architectural state, ordered bus effects, and guest cycle counts are separate
observations. Cycle precision is instruction-boundary only. The first
diagnostic's 36 cycles are compared to its exact recipe; cycle accuracy is not
inferred from another emulator's coalesced callbacks and is not a Neo Geo board
timing result.

## Explicit exclusions

No commercial ROM or BIOS, FPU, SoftFloat, MMU, runtime opcode generator,
generated runtime source, imported runtime CPU, external engine, JIT, dynamic
loader, general CPU framework, full instruction-set claim, board bus-error
recovery, prefetch fidelity, arbitrary wait-state suspension, or Neo Geo
hardware timing claim. Keep runtime dependencies in C17 and do not add a new
runtime dependency. Preserve Unity as a test-only pinned dependency.

## Evidence and oracle ancestry

Primary references are Motorola/NXP *M68000 8-/16-/32-Bit Microprocessors
User's Manual*, document MC68000UM, Rev 9.1 (2006-01-25), especially §§2, 5,
and 6.3 and Figures 6-5 and 6-7; and Motorola *M68000 Family Programmer's
Reference Manual*, document M68000PRM (2000-07-01), instruction descriptions
and encoding tables for MOVEQ, ADDQ, MOVE, STOP, NOP, RESET, RTE, TRAP, ILLEGAL,
and SR operations. Check the 68K Programmer's Reference Manual Errata,
M68000PRMER (2007-03-26), where applicable. Official documents:
[MC68000UM](https://www.nxp.com/docs/en/reference-manual/MC68000UM.pdf),
[M68000PRM](https://www.nxp.com/docs/en/reference-manual/M68000PRM.pdf), and
[M68000PRMER](https://www.nxp.com/docs/en/reference-manual/M68000PRMER.pdf).
These manuals define CPU behavior, not Neo Geo board behavior.

The original guest input and asserted values are tracked in
`tests/cpu/ORACLE.md`; that fixture's authorial recipe and manual-derived
expectations are the primary oracle for the first slice. Musashi, MAME,
SingleStepTests and emulator-generated outputs may locate disagreements but
their shared ancestry must be recorded and cannot independently establish
truth. Pin exact local source/fixture/tool identities in later evidence.

## Frozen effort, diagnostic, and churn gates

The separate owned-core budget is 32 cumulative active hours across all agents,
including this governance plan, implementation, debugging, qualification,
independent reviews, repairs, retests, and documentation. Count concurrent
agents by summed active intervals. Charge failed and reverted work; there are
no refunds and no substantive-attempt counter. The first owned runtime or
behavioral-test change starts a separate 8-hour diagnostic gate. It stops only
after the original guest and its named wrong-behavior control both execute.
Plan 01-07 effort belongs in the 32-hour budget but not the diagnostic clock.

Review thresholds are 6,000 cumulative added/deleted nonblank authored runtime
lines and 8,000 cumulative added/deleted nonblank test/tool lines. Record the
exact category and churn. Crossing a threshold pauses mutation and requires
user-controlled scope review; a threshold alone does not accept or reject the
core. Reserve effort for independent review, in-scope repair, regressions, and
re-review. Over-cap, over-threshold, or unsupported outcomes remain explicit
`GAPS_FOUND`; no automatic budget increase or backend substitution is allowed.

`tools/owned_cpu/contract.py` supplies `validate`, `budget`, `record`, and
`self-test`. Its checks use explicit conditions and named failures, never
Python `assert` for factual validation. `record --stage NAME --build-dir PATH`
also requires explicit agent intervals; it records summed active effort,
cumulative Git added/deleted nonblank churn by category, exact commit/build/
fixture identities, and nonempty actual stage test results. The validator
checks immutable historical hashes and contract fields used by admission; it
does not change scope. Effort logs are maintainer evidence, not independently
provable clock truth, so conservative charges and independent review remain
required.

## Change control

This contract does not accept an implementation. Keep CPU-01 through CPU-04
Pending and Phase 02 gated until fresh evidence and phase verification admit
the replacement. Changing the supported opcode set, model, host boundary,
dependency set, effort cap, or churn limits requires a new user-reviewed
decision before mutation.
