# Original arithmetic/store guest oracle

Original Glueyneo diagnostic, MIT; no BIOS, ROM or third-party fixture bytes.
The recipe in guest_fixture.c creates reset vectors and 14 instruction bytes.
No emulator output supplies expected values.

Primary references consulted 2026-10-01:

- Motorola M68000 Family Programmer's Reference Manual, 1992,
  https://www.nxp.com/docs/en/reference-manual/M68000PRM.pdf
- Motorola M68000 8-/16-/32-Bit Microprocessors User's Manual, ninth edition,
  1993, https://www.nxp.com/docs/en/reference-manual/MC68000UM.pdf

| Words at address $100 | Meaning | PRM printed pages | UM timing |
|---|---|---|---|
| 7007 | MOVEQ #7,D0; sign-extend immediate to 32 bits | 4-134 | Table 8-5 p.8-5: 4 |
| 5680 | ADDQ.L #3,D0; longword result 10 | 4-11–4-12 | Table 8-5 p.8-5: 8 |
| 23c0 0000 1000 | MOVE.L D0,($1000).L; big-endian store | 4-116–4-117, 2-18 | Table 8-3 p.8-3: 20 |
| 4e72 2700 | STOP #$2700; supervisor SR, stop at PC $10e | 6-85 | Table 8-12 p.8-10: 4 |

Scenario B substitutes 700b, 5a80, destination extension 0000 1004; expected
value is 16. MOVEQ uses register field 000 and an 8-bit immediate; ADDQ uses
immediate field 011/101, size 10 (long), and data-register EA 000000. MOVE uses
long size 0010, destination absolute-long mode/register 111/001 and source D0.
STOP is privileged and reset enters supervisor mode.

The 36-clock instruction total excludes reset, wait states, exceptions and
stopped time. Section 8 is MC68000 timing; section 7 is MC68008. This is a
manual-derived oracle, not measured hardware or Neo Geo board evidence.

UM section 6.3.1 pp.6-11–6-12 specifies supervisor mode, tracing off and
interrupt mask 7 on reset, with SSP and PC read from longwords at 0 and 4.
Vector bytes `00 00 20 00 00 00 01 00` select SSP $2000 and PC $100.
No other reset register contents are assumed. Reset does not save PC/SR and
differs from the RESET instruction. There are no external interrupts or reset
signals during this fixture. SR $2700 does not prevent every possible wakeup.

The negative control increments the executed MOVEQ operand while retaining
expected 10. It must fail the arithmetic/store assertion with actual 11 in a
supervised subprocess; crash, timeout and unrelated failure are rejected.
Backend reset accounting and prefetch behavior require separate timing tests.

## Plan 01-02 isolation extension

Original MIT extension in `isolation_fixture.h`, reviewed 2026-10-01 against
the same primary manuals: vector 31 at $7c points to $180. UM table 6-2
(printed p.6-7) gives the level-7 autovector; section 6.3.2 (pp.6-12–6-13)
describes the level-7 edge irrespective of the interrupt mask. The handler
words `5281 4e73` encode `ADDQ.L #1,D1; RTE`; ADDQ fields follow PRM
pp.4-11–4-12, and RTE's encoding/restoration follows PRM p.6-84. A second
`STOP #$2700` at $10e ends the resumed sequence. The test knows its initial
zeroed backend D1 as an implementation baseline, not a hardware reset promise.

Nine observations cover zero work, reset debt, each original instruction,
IRQ entry/handler addition, RTE and resumed STOP. Isolated execution supplies
ownership baselines for full trace/cycle comparisons; it is deliberately not
an independent hardware timing oracle. The explicit arithmetic effects and
swapped-owner failure make instance contamination consequential. Fault bytes
are original mutations of these fixtures, with no external firmware.

## Plan 01-03 timing contract

The same primary manuals were re-read on 2026-10-01. UM Table 8-14,
printed p.8-11: external reset recovery40, TRAP/illegal/privilege34,
autovector IRQ44 (four-clock acknowledge), address error50. Table8-12,
p.8-10: RESET instruction132, RTE20, STOP4. Reset40 starts after reset/halt
are sampled negated; it is not the RESET instruction's external signal.
PRM pp.6-83–6-85 defines RESET/RTE/STOP effects and encodings.

`test_timing.c` uses original words: TRAP#0=$4e40, ILLEGAL=$4afc,
MOVE #imm,SR=$46fc, MOVE.W ($1001).L,D0=$3039 $0000 $1001,
NOP=$4e71, RESET=$4e70 and the earlier ADDQ/RTE/STOP words. UM Fig6-5,
p.6-10 supplies the normal six-byte SR16/PC32 frame; Fig6-7 p.6-17 supplies
the address-error status16/address32/IR16/SR16/PC32 frame. Sections6.3.5/6.3.7
distinguish following PC for TRAP and faulting PC for privilege violation;
the illegal opcode also saves its own PC. Address-error saved PC is not
claimed to be a general restart address (§6.3.9.1).

Exact cycle expectations apply only to these original fixtures and configuration.
Signed requests 0..1000000 are accepted, others reject atomically. This bound
leaves signed-int headroom beyond qualified reset40+IRQ44+RESET132 work.
Zero consumes nothing; reset debt is consumed once as a whole. Requests39/40/41
therefore return40/40/44. STOP idle consumes the requested time with zero
instructions. Instruction counts count completed dispatches, including ordinary
instruction-triggered exceptions; an address-error longjmp does not complete
the dispatch and counts zero. Counters and elapsed outputs use uint64_t.

IRQ entry at a call boundary coalesces with the first handler instruction:
request1 returns44+8=52 and one completed ADDQ. Unmasking with MOVE to SR
returns16+44=60, at handler entry. These are documented backend boundaries,
not extra hardware exception clocks. Split40+12 and combined52 reach the same
guest boundary; arbitrary request partitions need not do so. Backend CCR at
creation is known fixture state, not a hardware guarantee for reset CCR.

The native Apple/BSD sigsetjmp path is compiled and tested. Its signature uses
the explicit context, and its exhausted-budget return now matches the generic
path: address error50 returns before executing the handler. Original nested
stack/vector host-fault and odd-IRQ regressions remain required. Callback bus
failure means terminal host fault, not a guest bus-error input; upstream's
68010 bus-error frame cannot establish 68000 fidelity. No arbitrary bus-cycle
suspension, board accuracy, original BIOS or game support is established.
