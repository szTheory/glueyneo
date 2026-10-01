# Final-attempt timing repair scope

Before repair, native `cpu_timing` on the 63b67d4 adapter plus the added tests
failed these Unity assertions (CTest exit 8, three tests, three failures):

```
request_rejected: Expected 1 Was 4:out-of-range request must reject
reset_debit: Expected 44 Was 4:reset40 plus MOVEQ4
reset_clears_pending_nmi: Expected 0 Was 1:reset clears stale NMI edge
```

Plan 01-03 attempt-2 ownership amendment: edit `third_party/musashi/m68kcpu.c`
and its reproducible recipe `tools/cpu/adapt.py` for these concrete reset bugs.
Keep the original six-input set and both generated outputs; regenerate and
verify them without hand edits. No new attempt or cap change. Count reset work
in the original execution pool and discard a stale pre-reset NMI edge, matching
the private reset operation that already clears the interrupt line/bitmap.
The signed adapter request change is private and rejects instead of clamping.

IRQ entry may share its call boundary with the first handler instruction.
This existing backend boundary is retained and measured explicitly; it is not
an independently suspendable bus-cycle or exception-entry API.

Further native timing counterexample before repair: `address_error` expected
50 elapsed but observed 58 (8 tests, 2 failures, CTest exit8). The BSD trap
macro resumes handler execution after exhausting the budget, unlike the
existing generic macro. Scope additionally includes `m68kcpu.h` and its recipe
to reproduce the generic early return after the 50-cycle exception. Preserve
the sigsetjmp/siglongjmp branch and corrected context-bearing signature.
The other failure was a test-oracle error: reset does not specify CCR, and the
zeroed backend's inverted Z representation exposes SR $2704. Save pre-exception
SR and compare against it; do not assume reset clears CCR. No runtime change
is needed for that failure.
