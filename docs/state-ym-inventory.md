# YM2610 candidate state inventory

This document describes the private, in-process continuation format implemented by
`src/chips/ym2610_candidate.cpp` over the pinned YMFM YM2610 traversal. It is not a
public emulator snapshot format, save-file ABI, replay compatibility promise, or
hardware-fidelity claim. The state seam is compiled only for internal/native tests;
the installed candidate API does not export it.

## Format and atomicity

Version 1 begins with `GYM1` and a big-endian `u32` version value of 1. Every
multi-byte integer is canonical big-endian; signed values are encoded as fixed-width
two's-complement bit patterns; booleans are exactly one byte (`0` or `1`). The
checked visitor retains the historical little-endian behavior for other YMFM users,
reports sticky underflow/invalid-value/trailing errors with byte offsets, and requires
the complete traversal to consume exactly the input length.

The private wrapper prefix is 53 bytes:

| Byte range | Field | Validation / meaning |
|---|---|---|
| 0–3 | `GYM1` | Exact magic. |
| 4–7 | Version | Exactly 1. |
| 8–15 | `now` | Wrapper chip-clock count. |
| 16–23 | `busy_end` | Busy deadline; expired values are valid. A future value may be at most 192 clocks after `now`, checked by `check_wrapper_chip_relation` (`state.ym.busy-end-beyond-window`). |
| 24–39 | `timer_due[2]` | Timer A and B deadlines. Active deadlines must be in `(now, now + 147456]` and `(now, now + 589824]`, respectively; traversal checks the lower bound and `check_wrapper_chip_relation` checks the upper bound (`state.ym.timer-due-beyond-period`). |
| 40–41 | `timer_active[2]` | Canonical booleans; each must match the staged chip's timer-running flag in both directions, checked by `check_wrapper_chip_relation` (`state.ym.timer-running-without-active`, `state.ym.timer-active-without-running`). |
| 42 | `clock_remainder` | Less than 16 and equal to `total_clocks % 16`. |
| 43–50 | `total_clocks` | Must equal `now`; overflow is rejected by the clock API. |
| 51–52 | `selected_register[2]` | Last selected YM register for each port bank. |

The chip traversal follows the order in `ymfm::ym2610::save_restore`: YM2610
address/EOS/mask fields, FM, SSG, SSG resampler, ADPCM-A, and ADPCM-B. Glueyneo
then appends the held FM output (`m_last_fm.data`) because the candidate can capture
between MAX-fidelity output ticks. The exact byte count is measured from this pinned
traversal rather than duplicated as a handwritten constant. A future schema or
dependency change must review the version, order, limits, tests, inventory, and
NOTICE together.

Capture first builds the full state in a bounded local vector and copies into the
caller's buffer only after traversal succeeds. Staging builds a separate candidate
with no-op callbacks, restores and validates it, and returns no candidate on failure.
The caller must rebind destination-owned callbacks before replacing its live
candidate. Rebind is a plain callback-table/userdata assignment and performs no
allocation or callback. Capture requires no callback to be active and a candidate
without a latched failure. Diagnostics, failure/reentry flags, callback pointers,
callback userdata, and external ROM/sample ownership are intentionally not serialized;
diagnostics restart empty and the destination owner supplies its own bindings.

## Field map and validation sources

| Traversal | Persisted state | Checked constraints and unsafe-use boundary |
|---|---|---|
| `ym2610` | Address, EOS status, EOS mask | Address `<= 0x1ff`; EOS status `<= 0x7f`; mask is a subset of `EOS_FLAGS_MASK` (`0xbf`). These fields select register banks and status behavior. |
| OPN-A registers | LFO counter/amplitude and `0x200` register bytes | Raw bytes are retained; their widths are the hardware register representation. |
| FM engine | Envelope counter, status, prescale, IRQ mask/state, two timer-running flags, total clocks; FM registers; six channels; 24 operators | Prescale is 2, 3, or 6; status has only TIMER-A/TIMER-B/BUSY/IRQ bits; IRQ mask has only timer bits; IRQ/timer booleans are 0/1. |
| FM operators | Phase, envelope attenuation/state, SSG inversion, key state, live key-on bits | Attenuation `<= 0x3ff`; YM2610 envelope state is ATTACK, DECAY, SUSTAIN, or RELEASE; inversion/key `<= 1`; live key-on `<= 7`. The checked visitor rejects invalid enum and raw boolean encodings before staging can be used. |
| FM channels | Two feedback samples and next feedback input | Each signed value lies in `[-8191, 8191]`, matching the pinned 13-bit attenuation conversion domain. |
| SSG engine | `0x10` register bytes; three tone counts/states; envelope count/state; noise count/state | Tone count `<= 0xfff`, tone state `<= 1`, envelope count `<= 0xffff`, envelope state `<= 63`, noise count `<= 0x3f`, noise state `<= 0x1ffff`. |
| SSG resampler | Sample index and three held output values | The full `u32` sample index is preserved because its low bits/modulo select future resampling phase. Each held output must lie in `0..16382`, the range of `ssg_engine::output()`'s amplitude table; larger values are unreachable and would overflow the signed resampler sums. The ratio and resampler function pointer are reconstructed from the candidate's fixed MAX-fidelity configuration. |
| ADPCM-A | `0x30` register bytes and six channels: playing, nibble, current byte/address, accumulator, step index | Playing/nibble are 0/1; byte is `<= 0xff`; address is `<= 0x1000000` (the pinned 8-bit-shift one-past-end sentinel); accumulator is `0..0xfff`; step index is `0..48`. |
| ADPCM-B | `0x11` register bytes and channel status, nibble, byte, dummy-read count, position/address, current/previous accumulator, step | Status uses only EOS/BRDY/PLAYING bits; nibble `<= 1`; dummy-read `<= 2`; position `<= 0xffff`; address `<= 0xffffff`; accumulators are signed 16-bit; step is within pinned `STEP_MIN..STEP_MAX` (`127..24576`). |
| Held YM2610 FM output | Output lanes in `m_last_fm.data` | Preserved because it can be consumed by the next output call even when no new FM sample is generated at the capture point. |
| Candidate wrapper | Clock/timer/register state above | `total_clocks == now`; remainder is `< 16` and equals total clocks modulo 16. Traversal requires each active deadline to be after `now`; `check_wrapper_chip_relation` enforces the timer-specific upper bounds and matches wrapper active flags to chip timer-running in both directions. Future `busy_end` is bounded to 192 clocks. |

## Relation enforcement map

| Claim | Check | Recipe |
|---|---|---|
| `sound.ym_irq` equals the staged chip IRQ state. | `gn_state_mvs_ym_irq_relation_valid` | `state.sound.ym-irq-mismatch` |
| The chip timer is running while the wrapper's `timer_active` is false. | `check_wrapper_chip_relation` | `state.ym.timer-running-without-active` |
| The wrapper's `timer_active` is true while the chip timer is not running. | `check_wrapper_chip_relation` | `state.ym.timer-active-without-running` |
| A future active timer deadline does not exceed its source-derived maximum: 147456 clocks for A and 589824 for B. | `check_wrapper_chip_relation` | `state.ym.timer-due-beyond-period` |
| A future `busy_end` is no more than 192 clocks after `now`; expired values are accepted. | `check_wrapper_chip_relation` | `state.ym.busy-end-beyond-window` |

The YM relation validators run on the staged candidate before live state is
changed. The cross-section IRQ check compares `sound.ym_irq` with the staged
chip state exposed through the read-only YMFM accessor added in plan 04-09.

## Source-derived bounds and assumptions

- **A1 — timer active/running relation:** `ymfm_fm.ipp` `update_timer()` sets
  the chip running flag when it schedules a timer and clears it when it cancels
  one. `engine_timer_expired()` clears and then re-arms the timer. The wrapper
  timer callback state and chip flag therefore track the same scheduled timer;
  restore checks both mismatch directions in the map above (source lines
  1500–1552).
- **A2 — timer deadline maxima:** `update_timer()` derives Timer A's maximum
  period from 1024 and Timer B's from 4096, then multiplies by the 24 FM
  operators and prescale. Using the maximum supported prescale of 6 gives
  conservative wrapper-clock maxima of `1024 × 24 × 6 = 147456` and
  `4096 × 24 × 6 = 589824` (`ymfm_fm.ipp` lines 1505–1513). Timer B's
  adjustment is at most 15 clocks (`ymfm_fm.ipp` lines 1613–1614); it does not
  exceed these maxima.
- **A3 — cross-section YM IRQ equality:** the sound wrapper is updated by the
  YM IRQ callback as `m_irq_state` changes. `engine_check_interrupts()` computes
  that chip state (`ymfm_fm.ipp` lines 1562–1576); both sides start clear on
  reset, and staging traversal does not call that method. Plan 04-09 added a
  read-only accessor for the staged chip state and enforces equality before
  live rebind. This claim compares the two serialized sections; it does not
  recompute the chip-internal formula.
- **A6 — YM busy deadline maximum:** both YM2610 data-register paths set busy
  time to `32 × prescale`; prescale is at most 6, yielding 192 clocks
  (`ymfm_opn.cpp` `ym2610::write_data()` lines 2021–2057 and
  `ym2610::write_data_hi()` lines 2078–2096). There is no lower bound: reset
  uses zero and expired deadlines remain valid. The check uses subtraction
  for future values to avoid overflow.

Not enforced: the staged chip's `m_irq_state` is not recomputed from its
internal status, interrupt-enable, and status-mask fields, and an inactive
timer's `timer_due` is not checked against chip state. The map covers only the
cross-section and wrapper/chip relations named there.

The ranges are taken from the pinned engine's `save_restore` implementation and
consumer operations, not inferred from the width of the serialized scalar. The
checked read validates all serialized values on the private staged candidate before
the caller can execute it. Address bounds for external sample callbacks remain the
candidate owner's responsibility and are enforced again by the callback wrapper.

## Reconstructed state, lifetime, and limits

FM `opdata_cache`, active-channel mask, modified-channel mask, and prepare-sweep
counter are derived from fixed register/configuration inputs. Canonical capture does
not invalidate or otherwise mutate these caches. Restore invalidates FM caches so
channel/operator mappings and derived rates are rebuilt before subsequent output.
The SSG resampler function pointer is also derived from fixed configuration; its
sample index and held output are persisted. The YMFM interface pointer and all host
callbacks are rebound to destination-owned values.

Test-only allocation failpoints cover candidate allocation, all nested chip-object
allocations reached by candidate/stage construction, and every growth of the state
capture vector. The test run on Apple Clang 21.0.0.21000101 / Debug observed 38
construction allocation points per candidate or stage and 12 capture-vector growth
points on this runtime; vector growth count is an implementation/runtime observation,
not a format guarantee. Partial construction is checked for balanced object
lifetimes, and every injected failure is checked through the C status boundary.

The current continuation test proves deterministic bytes, nonzero future FM output,
future PCM/timer/IRQ equivalence after staging/rebinding, source-owner destruction,
every truncated prefix and extension length rejection, hostile scalar/range rejection,
and allocation-failure containment. This bounded diagnostic slice does not establish
game compatibility, a durable snapshot contract, arbitrary YMFM configuration
compatibility, physical-chip timing, or whole-emulator continuation. Future public
snapshot work must define separate identity/versioning, compatibility, ownership,
and persistence rules.

## Source ancestry

Implementation constraints are checked against the selected YMFM files listed in
`third_party/ymfm/NOTICE.md`, including `ymfm_opn.cpp` (`ym2610::save_restore`,
SSG resampler traversal), `ymfm_fm.ipp` (operator/channel/FM traversal),
`ymfm_ssg.cpp`, and `ymfm_adpcm.cpp`. This map is source-backed and revision-specific;
review it against a pinned source update before carrying the format forward.
