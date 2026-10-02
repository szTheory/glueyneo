# Owned MC68000 implemented subset

Status: **implemented diagnostic slice; backend admission remains pending**.
This is a private authored C17 experiment for a narrow, manual-derived set of
MC68000 behaviors. It is not a complete CPU implementation or a Neo Geo timing
model.

## Instance and reset behavior

The opaque per-instance state owns registers, status, user/supervisor stack
banks, counters, stopped state, IRQ inputs, reset debt, and terminal host-fault
state. Bus and allocator callbacks plus userdata are bound per instance and
must outlive it. Calls on one instance must not overlap or reenter. Separate
instances have no mutable runtime globals. Test-only state/counter hooks are
compiled into the private experiment targets and are not product API.

Reset reads the initial SSP and PC as four ordered big-endian 16-bit transfers
from vector bytes 0 through 7. It sets supervisor SR to `0x2700`, retains a
single 40-cycle reset event for the next positive run request, and initializes
other registers to zero as deterministic test state. This does not claim those
registers have those values on physical reset. An odd initial SSP or PC returns
`OWNED_CPU_ADDRESS_ERROR`; reset does not build an exception frame.

The experiment now has a private same-build continuation record under
`OWNED_CPU_TEST_HOOKS`. It lists guest registers, status, IRQ edge/input state,
reset debt, diagnostics and event counters by field, with a fixed size, format
version, mandatory field mask and the full SHA-256 identity of `cpu.c`. Capture
requires a ready, idle, nonterminal instance. Restore validates into a temporary
named representation before changing the destination; it makes no bus calls
and keeps the destination's bus and allocator bindings. The caller must copy
guest memory separately. `ready` is reconstructed on success; `active` and
terminal `faulted` state are not stored. The full field disposition is in
[`state-inventory.json`](state-inventory.json).

Continuation is exercised after reset debt, each of the four original
diagnostic instructions (including STOP), a masked IRQ input, a pending level-7
edge after the pin is deasserted, IRQ entry, TRAP entry, ILLEGAL entry,
privilege-exception entry, address-error entry and RTE completion. For each
checkpoint, the test clones guest memory, restores into a separately bound
instance, destroys and overwrites the source owner, then compares six
instruction-boundary run calls against the uninterrupted baseline. It checks
named CPU fields, every guest-memory byte, ordered bus calls, run results,
elapsed/overshoot cycles and stop reasons.

This record is an in-process fixed C object. Its size check does not make an
arbitrary byte buffer safe to parse. Compatibility is limited to the exact
compiled core source identity. It does not define a public ABI, cross-build
compatibility, emulator snapshot, replay, durable save or guest-memory format.

## Supported operations

| Operation | Accepted encoding and effect | Cycles |
|---|---|---:|
| `MOVEQ #imm8,Dn` | All D0–D7; sign-extend to 32 bits; N/Z from result, V/C clear, X preserved | 4 |
| `ADDQ.L #1..8,Dn` | All D0–D7 direct; encoded zero means 8; modulo-2^32 result and N/Z/V/C/X | 8 |
| `MOVE.L Dn,(abs.L)` | All D0–D7 sources; high word then low word; N/Z from long value, V/C clear, X preserved | 20 |
| `NOP` | Exact opcode `0x4e71`; no register or SR change | 4 |
| `RESET` | Exact opcode `0x4e70`; supervisor only; records one external-reset-signal event, with no device callback | 132 |
| `RTE` | Exact opcode `0x4e73`; supervisor only; restores SR/PC from a six-byte short frame and switches USP/SSP when S changes | 20 |
| `TRAP #0` | Exact opcode `0x4e40`; vector 32; saves next PC and old SR on supervisor stack | 34 |
| `ILLEGAL` | Exact canonical word `0x4afc`; vector 4; saves faulting PC and old SR | 34 |
| `MOVE.W #imm16,SR` | Exact opcode `0x46fc`; supervisor only; replaces SR and switches stack banks when S changes | 12 |
| `MOVE.W (abs.L),Dn` | D0–D7 destination; replaces only low word; N/Z from 16-bit result, V/C clear, X preserved | 16 |
| `STOP #imm16` | Exact opcode `0x4e72`; supervisor only; loads SR and enters stopped state | 4 |

User execution of `STOP`, `RESET`, `RTE`, or `MOVE.W #imm16,SR` raises vector 8
before the privileged operation takes effect. These instruction-triggered
exceptions count one completed dispatch and charge their 34 clocks to the
exception counter, not the ordinary instruction-cycle counter. Other valid
but unsupported encodings return `OWNED_CPU_UNSUPPORTED_OPCODE`; they are not
aliased to the canonical `ILLEGAL` instruction.

## Interrupts, frames, and bus effects

Level 1–6 is accepted at an instruction boundary when its level is greater
than the SR interrupt mask. Level 7 is accepted for a remembered low-to-7
transition regardless of mask; a held level 7 is also accepted when software
lowers the mask below 7. Deassertion does not cancel a pending level-7 edge.
The selected autovector is `24 + level`; acceptance saves the current next PC
and old SR, sets supervisor mode, clears T1, sets the interrupt mask, and
enters a stopped handler if one is not already stopped. IRQ entry is a separate
44-cycle event with zero completed instructions. The functional bus callbacks
show frame writes and vector reads; they do not model the interrupt-acknowledge
pin cycle.

Group-1/2 short frames contain SR16 then PC32 at increasing stack addresses.
Exception entry writes the PC high word, PC low word, then SR, and reads vector
high then low. The selected address-error frame is SSW16, fault-address32,
IR16, SR16, PC32 at increasing stack addresses. The SSW retains read/write,
instruction/data, and function-code fields. This implementation uses saved
faulting PC for its named address-error cases; Motorola describes that saved PC
as unpredictable, so it is not a restart guarantee.

Guest word accesses use ordered 16-bit callbacks and big-endian bytes. Logical
addresses remain 32-bit and callbacks receive the low 24 bits. Odd word/long
data accesses and odd instruction fetches are detected before an odd callback.
Address errors enter vector 3 and cost 50 clocks. A data/fetch dispatch that
enters an address-error frame counts zero completed instructions. A host
callback failure during normal work or exception entry is terminal until
reset/destruction; already completed bus writes remain visible. A failed or
odd exception stack/vector access never recursively attempts another guest
exception.

## Run and counter policy

`owned_cpu_run` accepts requests from 0 through 1,000,000 cycles. Zero and
out-of-range requests cause no callback or state change. For positive requests
the run processes one whole event at a time: pending reset40, eligible IRQ44,
one instruction/its exception, or stopped idle. It returns after an event
meets or exceeds the request. It never splits an instruction or exception and
does not combine IRQ entry with handler execution as one indivisible event.
If more requested cycles remain after a stopped CPU has no eligible IRQ, idle
time consumes exactly the remainder with no bus access.

The 64-bit counters are checked before event side effects and return
`OWNED_CPU_COUNTER_OVERFLOW` rather than wrapping. An instruction's opcode
fetch can already have occurred before its exact cycle counter preflight;
the architectural PC/registers and event counters remain uncommitted on that
overflow. `instructions` counts ordinary completed dispatches and
instruction-triggered TRAP/ILLEGAL/privilege exceptions. It excludes reset,
IRQ, idle, and address-error events. `instruction_cycles` counts ordinary
instruction clocks, including RESET; `exception_cycles` counts instruction
exceptions, IRQ entry, and address-error entry; `idle_cycles` counts stopped
time; and `total_cycles` includes reset debt, instruction, exception, and idle
events. `reset_cycles` records the fixed 40-cycle reset measurement separately.
An ordinary instruction can overshoot by at most 131 clocks; larger named
events have their own fixed bounds. No arbitrary partition-equivalence claim
is made.

## Evidence and exclusions

[`tests/owned_cpu/ORACLE.md`](../../tests/owned_cpu/ORACLE.md) records the exact
fixture expectations, separate architectural/bus/cycle claims, primary manual
references, and uncertainty. The earlier diagnostic remains byte-for-byte
unchanged: scenario A stores 10 at `0x1000`, scenario B stores 16 at `0x1004`,
then both stop at PC `0x10e` after 36 instruction clocks; reset40 is separate.

Not implemented or established: trace exception processing, guest bus-error
input, prefetch fidelity, wait states, arbitrary mid-instruction suspension,
physical interrupt acknowledge, external RESET device behavior, full ISA or
later CPU models, public or durable snapshots, BIOS/games, and Neo Geo board
timing. No prefetch or buffered guest state exists in this implementation.
An emulator's output is a comparison lead, not hardware truth. The experiment
still has not passed independent review or phase admission; CPU-01–05 remain
pending until the current roadmap's full gates are completed.
