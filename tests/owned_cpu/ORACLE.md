# Owned CPU timing and exception oracle

This ledger covers only the named `owned_cpu_timing` fixture. Expected
architectural state and frame contents come from the cited primary manuals;
the callback order below is an explicit functional-bus contract checked by the
original fixtures. Neither kind of evidence establishes per-pin timing or
Neo Geo board behavior.

## Primary references

- Motorola, *M68000 8-/16-/32-Bit Microprocessors User's Manual*, MC68000UM,
  Rev. 9.1 (NXP-hosted copy, 2006-01-25). [Official PDF](https://www.nxp.com/docs/en/reference-manual/MC68000UM.pdf).
  Section 6.2.4 / Fig. 6-5 describes the ordinary SR16/PC32 frame; §6.3.2
  describes interrupt masking and level 7; §6.3.9.1 and §6.3.10 / Fig. 6-7
  describe odd-address exceptions and the extended frame. Section 6.3.1
  distinguishes the RESET instruction's external signal from reset recovery.
- Motorola, *M68000 Family Programmer's Reference Manual*, M68000PRM
  (NXP-hosted copy of the 1992 manual). [Official PDF](https://www.nxp.com/docs/en/reference-manual/M68000PRM.pdf).
  Instruction entries and opcode tables define the exact encodings for NOP,
  RESET, RTE, STOP, MOVE, TRAP, ILLEGAL and MOVE to SR.

The User's Manual is the behavior and timing source for MC68000 exception
frames and clock totals. The PRM is the encoding and operation source. Existing
emulator outputs and the historic adapter timing tests are comparison oracles
only. No original silicon capture is available. The implementation's choice to
use the faulting instruction PC in its address-error fixture is local and
deterministic; the manual calls that saved PC unpredictable, so it is not a
restart guarantee.

## Timing table and accounting limits

| Fixture operation | Expected clocks | Primary source |
|---|---:|---|
| reset recovery event | 40 | UM Table 8-14, printed p. 8-11 |
| NOP | 4 | UM Table 8-12, printed p. 8-10 |
| RESET instruction | 132 | UM Table 8-12, printed p. 8-10 |
| RTE | 20 | UM Table 8-12, printed p. 8-10 |
| STOP | 4 | UM Table 8-12, printed p. 8-10 |
| MOVE.W absolute-long to Dn | 16 | UM Table 8-2, absolute-long source / data-register destination |
| TRAP, privilege exception | 34 | UM Table 8-14, printed p. 8-11 |
| Exact `0x4afc` candidate rejection | 0 | P01-C-14 owner-defined capability boundary, not hardware timing |
| autovector IRQ | 44 | UM Table 8-14, printed p. 8-11 |
| address error | 50 | UM Table 8-14, printed p. 8-11 |
| MOVE.W immediate to SR | 12 | UM Table 8-12, printed p. 8-10 |

Those per-operation expectations are checked as separate completed events.
The core intentionally accounts reset, IRQ, exception, instruction, and STOP
idle events independently. It has no instruction-prefetch queue or
cycle-by-cycle bus model; consequently this ledger does not claim an arbitrary
whole-program run total is a hardware pin trace. The qualified 76-cycle
reset-plus-four-instruction result is specifically the declared event policy:
reset40 + MOVEQ4 + ADDQ.L8 + MOVE.L20 + STOP4.

## Named fixture outcomes

| Test case | Expected architectural result | Bus/frame assertions | Cycle/count assertion |
|---|---|---|---|
| `reset_debt_is_consumed_once_and_nop_executes` | Reset debt remains pending through zero work, then PC remains `$100`; NOP advances to `$102` | Zero-work/reset-debt events call no bus; NOP reads `$100` | Reset40 once; NOP4 for a request1, overshoot3 |
| `reset_and_four_named_guest_instructions_total_seventy_six_cycles` | MOVEQ gives D0=10, ADDQ gives16, stored long is `$00000010`, STOP PC `$10e` | MOVE.L writes high word then low word | reset40 + instruction36 = total76; four dispatches |
| `reset_instruction_is_distinct_and_observable` | RESET advances PC `$100` to `$102`, SR stays `$2700` | Only opcode fetch; one reset-signal event is observed without a device callback | RESET132, one dispatch |
| `trap_stacks_next_pc_then_addq_rte_resumes_stop` | TRAP vector32 to `$180`; handler increments D1, RTE restores PC `$102` and supervisor SP | Short frame at `$2ffa`: SR `$2700`, PC `$102`; exception entry writes PC high/low then SR, reads vector high/low | TRAP34, ADDQ8, RTE20, STOP4 |
| `canonical_unsupported_has_only_opcode_fetch` | Exact `$4afc` returns unsupported with logical PC/fault PC `$100` and fetched IR | Exactly one successful opcode read; all observation fields and memory unchanged, even with failing vector/stack and odd stack; repeatable | Zero clocks, overshoot and completed dispatches |
| `canonical_rejection_retains_prior_reset_irq_and_instruction_charges` | Rejection after reset, IRQ and NOP retains their completed work | IRQ frame/vector effects belong to the preceding IRQ; rejection has only its fetch | reset40, IRQ44, NOP4 remain separately charged |
| `canonical_failed_opcode_fetch_remains_a_host_fault` | Inaccessible opcode remains terminal host fault | One failed read; later run adds no callback | Zero clocks |
| `move_to_sr_switches_to_user_stack` | MOVE.W `#$0000,SR` switches S=1 to S=0 and activates USP `$3800` | Immediate word follows opcode; SSP `$3000` retained | 12 clocks |
| `rte_restores_user_stack_bank_from_short_frame` | RTE restores user SR0/PC`$200`, switches to USP `$3800`, retains SSP`$3006` | Reads opcode `$100`, then SR/PC words at `$3000/$3002/$3004` | 20 clocks |
| `move_word_absolute_long_loads_every_data_register` | All D0–D7 retain their high word and receive low word `$8001`; N set, V/C clear, X retained | Opcode, two address extension words, then one data word at `$200` | 16 clocks and one dispatch each |
| `odd_word_source_stacks_manual_derived_address_error_frame` | Vector3; deterministic local saved PC`$100` | SSW `$001d` (supervisor data read), fault address `$201`, IR`$3039`, SR`$2700`, PC`$100`; final increasing-address layout: SSW, address, IR, SR, PC | 50 clocks, zero completed dispatches |
| `odd_long_destination_stacks_a_write_address_error` | Vector3 before any destination write | SSW `$000d` (supervisor data write), destination `$201`, IR`$23c0` | 50 clocks, zero completed dispatches |
| `odd_instruction_fetch_enters_group_zero_without_an_odd_bus_read` | Odd PC`$101` selects vector3 | No callback uses an odd address; SSW `$0016` (supervisor program read), address`$101`, IR0 | 50 clocks, zero completed dispatches |
| `irq3_stays_masked_until_move_to_sr_then_enters_as_its_own_event` | IRQ3 stays masked at reset SR`$2700`, then unmask instruction allows vector27; handler returns to STOP | Frame saves SR`$2000`, PC`$106`; handler ADDQ/RTE runs as later events | NOP4, MOVE SR12, IRQ44 with zero completed instructions, ADDQ8, RTE20, STOP4 |
| `irq7_edge_is_unmasked_and_held_level_waits_for_mask_change` | Rising level7 selects vector31 despite mask7; held level7 does not immediately retrigger at mask7, then does after handler lowers mask; deasserting a later edge does not cancel it | Vector31 frame and handler PC`$180` are observed | Each IRQ44, zero dispatches; named handler instructions are charged separately |
| `user_mode_privileged_instructions_raise_vector_eight` | User STOP, RESET, RTE, and MOVE-to-SR each select vector8 before taking effect | Old user SR0/PC`$100` saved on SSP; USP`$3800` retained; supervisor stack becomes active | Each privilege exception34 and one dispatch |
| `stopped_cpu_idles_to_the_exact_request_without_bus_access` | STOP remains set | No callback during nine idle clocks | STOP4; idle9; total53 including reset40 |
| `reset_request_boundaries_never_split_the_reset_event` | Requests39/40/41 yield PC`$100`/`$100`/`$102` | Reset callback debt is consumed only once | Elapsed40/40/44; overshoot1/0/3 |
| `event_limits_and_counter_overflow_are_explicit` | Zero and oversize requests preserve state; maximum budget is accepted; overflow does not wrap counters or commit PC | Invalid requests issue no callback; counter overflow may fetch exactly the next opcode before refusing dispatch | Request range0..1,000,000; a STOP fixture consumes exactly1,000,000 including idle |
| `inaccessible_rte_frame_read_is_terminal_without_return_commit` | A failed read of the saved PC does not commit RTE's new PC or stack pointer | Opcode and SR read succeed; PC high-word callback fails; later run makes no callback | No instruction or cycle event is committed |
| `independent_counter_boundaries_do_not_block_other_event_kinds` | NOP remains executable when exception-cycle counter is already `UINT64_MAX` | No wrapping or spurious counter mutation | Instruction cycles reach `UINT64_MAX`; exception cycles remain there; total advances to44 |
| `twenty_four_bit_bus_address_wrap_is_explicit` | D0 `$aabbccdd` is written through absolute address `$01000000` | Bus sees `$000000` then `$000002`, high word first | MOVE.L20 |
| `failed_second_word_write_keeps_first_word_and_becomes_terminal` | Host fault is terminal | Successful high word remains; failed low word is not fabricated; later run adds no callback | No instruction/event counter is committed for failed host work |
| `nested_vector_callback_failure_is_terminal_without_recursion` | Failed vector32 fetch returns host fault | Trap frame writes already completed remain; failed vector read does not start another exception | Subsequent run is terminal without more callbacks |
| `odd_exception_stack_fault_is_terminal_without_recursive_entry` | Odd stack blocks exception entry and returns host fault | Opcode fetch is the only aligned bus callback; no recursive vector/frame attempt | No guest exception event is committed |

## Deliberate wrong-cycle control

P01-C-14 supersedes the historical canonical ILLEGAL frame assertion and its
local fault-PC choice, preserved through Git. P01-C-13 and Plan 01-17 retain
unknown original-silicon saved PC; this candidate exclusion does not resolve it.
The frozen CONTRACT and additive amendment define candidate scope. Current
timing tests do not qualify downstream semantic fixtures, continuation or the
full backend. Plans 01-19–01-21 own that remaining evidence.

`--mutate-unsupported` runs only `canonical_unsupported_wrong_status_expectation`,
which deliberately expects the former `OWNED_CPU_BUDGET` success status. It must
fail exactly the named result-status assertion, with one case and one failure.
Plan 01-19 supplies the consequential-control verifier.

The C harness's `--mutate-cycle` branch expects 49 instead of the documented
address-error 50 clocks. `negative_timing.py` requires the exact
`address_error_wrong_cycle_expectation` assertion, one Unity failure, a
nonzero test exit, and a one-case denominator. A crash, timeout, missing
assertion, extra failure, or zero denominator does not qualify.
