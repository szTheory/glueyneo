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
