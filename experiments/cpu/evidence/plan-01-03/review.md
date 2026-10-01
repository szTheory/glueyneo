# Independent timing and state review

Read-only review consulted MC68000UM ninth edition Tables8-12/8-14,
Figures6-5/6-7 and sections6.3.1–6.3.9, plus PRM pp.6-83–6-85.
Exact references and supported claims are in `tests/cpu/ORACLE.md`.

The initial review confirmed reset-debt and stale-NMI counterexamples and
the BSD address-error exhausted-budget discrepancy. IRQ entry still shares
its existing backend boundary with the first handler instruction; tests and
documentation explicitly separate that52-clock call from the44-clock IRQ.

The codec review checked raw flags (full arithmetic intermediates, not merely
architectural bits), all retained guest fields, destination-only bindings,
source destruction, active guards, invariant-zero inactive fields and cycle
scratch normalization. It found inconsistent reset records and zero-work
counter validation order; preserved failures precede the adapter corrections.
The follow-up confirmed these fixes and required independent malformed-case
isolation by clearing the instruction count before testing reset flags.

Actual 68000 RTE clears instruction/run modes. A preliminary concern about
surviving modes was withdrawn after inspecting the current template; tests
cover exception entry and post-RTE normal modes separately. A preliminary
pending-mutation concern assumed an IRQ-only boundary that was never installed;
it was withdrawn after reading current execute code and the intended control.

Additive effort charges: primary review300 seconds, codec review180 seconds,
follow-up35 seconds, total515 seconds. No reviewer edited files. No remaining
runtime correctness blocker was identified by this scoped review. This is not
the final phase acceptance review or a platform/hardware qualification.
