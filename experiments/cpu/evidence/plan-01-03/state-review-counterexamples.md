# State-review counterexamples

Independent read-only review identified inconsistent pending-reset records and
the zero-request counter-headroom ordering. Before repair, native `cpu_state`
reported six tests, two failures (CTest exit8): malformed_atomicity expected
INVALID_ARGUMENT1 but received OK0 for reset debt in user mode;
zero_near_counter_limit expected BUDGET5 but received INVALID_ARGUMENT1.
The latter restores the highest admitted instruction counter, executes one
instruction, then requests zero cycles. The zero call must consume no work.

Fix validation of reset supervisor/trace/mask/counter invariants and perform
positive-request counter-headroom validation after the zero-work return.
These private adapter repairs consume the same cumulative helper/semantic caps.

An earlier state fixture incorrectly expected instr_mode8 after RTE. Actual
68000 template explicitly restores INSTRUCTION_YES0/RUN_MODE_NORMAL0. The
fixture now independently checks mode8 at illegal-exception entry and mode0
after RTE. No backend edit was made for that test-oracle correction.
