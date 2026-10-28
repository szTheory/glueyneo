# Native state field inventory

This inventory maps the live fields in the native diagnostic/MVS implementation
to the current public native-state codec. The diagnostic profile has its
canonical big-endian header, CPU section, and 4 KiB RAM section. MVS MSX now has
profile-specific CPU, memory, board, sound, and YM2610 sections; the field map
below identifies what is persisted, rebuilt, retained from the destination, or
cleared at a successful restore. The separate MVS save owner is lifecycle
metadata, not guest state; [`native-save.md`](native-save.md) defines its
durable-transfer contract, measured Darwin/APFS writer stages, and unqualified
host/power-loss boundaries. The byte map, compatibility rules, exact
fixture-size calculation, and derived staging/work bounds are in
[`native-state.md`](native-state.md). This is implementation evidence for the
bounded first-party fixture, not a broad hardware-fidelity claim.

## Classification key

| Class | Meaning in this inventory |
| --- | --- |
| Guest | Future-affecting emulated state. A completed codec must encode and validate it. |
| Immutable | Loaded media or configuration identity; retain/verify from a separately loaded owner rather than copying host pointers. |
| Rebuild | Derived mapping/cache that can be reconstructed from immutable media/configuration and guest controls. |
| Host | Allocation, callback, sink, or ownership binding. Preserve the destination binding; never serialize the pointer. |
| Observation | Diagnostic history/output that does not change guest execution. Reset it on restore only where the observer contract permits; document that reset. |
| Lifecycle | In-call or terminal host-failure state that controls API eligibility. It is not a resumable guest field. |

For diagnostic state, “CPU section” means the named 152-byte CPU payload and
“RAM section” means the 4,096-byte mapped RAM payload. For MVS, the “memory
section” contains live work, backup, palette, and big-endian video RAM; the
“board section” contains controls, counters, calendar, and protocol observer
continuation; “sound” contains Z80 and converter state; and “YM2610” contains
the checked private `GYM1` continuation. The parser validates all required
sections before staging or changing live guest state.

## Image and instance ownership (`src/instance.c`)

| Structure and fields | Class | Current encoding, validation, or reconstruction |
| --- | --- | --- |
| `gn_allocator.userdata`, `.allocate`, `.release` | Host | Instance/image allocation binding; destination-owned and never serialized. |
| `gn_memory_region.bytes`, `.base`, `.size` (`rom`, `ram`) | Host + immutable | `bytes` is an owned allocation pointer. ROM bytes/base/extent and effective initial RAM bytes/base/extent feed normalized diagnostic media identity. The diagnostic RAM's live contents are the RAM section; its allocation is retained by the owner. |
| `gn_mvs_owned_region.bytes`, `.size`, `.role` | Host + immutable/rebuild | Region pointers are owned allocations; role/size and loaded bytes define media identity and role lookup. Rebuild role-indexed lookup from the independently loaded manifest; never store addresses. |
| `gn_image.allocator` | Host | Preserved allocation binding. |
| `gn_image.rom`, `.ram`, `.ram_seed`, `.ram_seed_size` | Host + immutable | ROM/seed storage pointers are host-owned. Diagnostic normalized identity hashes ROM and all effective zero-filled initial RAM, plus source-prefix presence/length and guest extents. Current live mapped RAM bytes use the RAM section. |
| `gn_image.profile` | Immutable | Diagnostic or MVS MSX profile ID is in the envelope and compatibility gate; other profiles are rejected. |
| `gn_image.save_owner` | Host/non-owned ownership hook | Bound to the owning `gn_instance` only when the initialized image candidate is committed. It is not copied into snapshots or durable bytes; restore keeps the destination image link. |
| `gn_image.diagnostic_media_identity[32]`, `.diagnostic_media_identity_valid` | Immutable/cache + lifecycle | Cached SHA-256 identity is recomputed only at successful load and checked during restore; validity gates API use. Identity digest bytes are in header offset 32. |
| `gn_image.mvs_media_identity[32]`, `.mvs_media_identity_valid`, `.mvs_state_capacity` | Immutable/cache + lifecycle | MVS identity is SHA-256 over the domain/profile/configuration and each ascending role's presence, normalized extent, and effective transformed bytes. It is computed once after successful load. Exact capacity is derived from loaded memory extents, Z80 canonical size, and checked YM2610 payload size, then stays fixed across run/reset/restore and failed replacement. |
| `gn_image.diagnostic_guest_faulted`, `.mvs_failure`, `.mvs_bus_fault_valid`, `mvs_sound.failed` | Lifecycle | Raw status-OK guest fault, MVS execution/bus fault, or sound callback/device fault blocks capture until reset or a fully validated restore. These latches are not encoded as resumable state. A successful restore clears them after staging; a rejection preserves them. |
| `gn_image.frame_input`, `.mvs_inputs` | Guest | MVS board section preserves the current input latch and validates supported input bits; absent from diagnostic profile. |
| `gn_image.marker_tile[64]` | Rebuild/immutable | Diagnostic rendering marker comes from the diagnostic fixture/media. Reconstruct from loaded immutable image; it is not current guest-writable RAM. |
| `gn_image.mvs_regions[GN_MVS_V3_MAX_REGIONS]`, `.mvs_region_count` | Host + immutable/rebuild | Region pointers remain destination-owned. Role, effective size, presence, and bytes in ascending role order feed the cached media identity after layout transforms; independently loaded manifest validation rebuilds the destination role table. |
| `gn_image.mvs_work_ram`, `.mvs_work_ram_size`; `.mvs_save_ram`, `.mvs_save_ram_size`; `.mvs_palette_ram`, `.mvs_palette_ram_size`; `.mvs_video_ram`, `.mvs_video_ram_words` | Host + Guest | Pointers and extents remain destination-owned. GNST memory section copies exact work/save/palette bytes and explicit big-endian video words into those same allocations. GNSV separately exports only the 65,536 backup-RAM bytes. Successful and rejected restore preserve the backup-RAM address. |
| `mvs_mslugx_command`, `.mvs_mslugx_counter` | Guest | Protection command/counter are encoded in the board section as named 16-bit values. |
| `mvs_bus_fault_address`, `.mvs_bus_fault_access`, `.mvs_bus_fault_width`, `.mvs_bus_fault_valid` | Lifecycle/observation | Capture rejects a bus-fault latch. A validated successful restore clears the prior fault report; a rejected restore leaves it unchanged. |
| `mvs_program_bank` | Guest | The board section retains the bank selection; validation checks it against the loaded MVS program extent. |
| `mvs_mame_unmapped_write_count` | Observation | Serialized in the board section to preserve the existing report across continuation; saturation and reset semantics remain unchanged. |
| `mvs_watchdog_pet_count`, `.mvs_watchdog_reset_count` | Observation | Serialized in the board section so progress reports continue from the saved point; watchdog control/deadline is separately serialized. |
| `mvs_video_ram_offset`, `.mvs_video_ram_modulo`, `.mvs_video_ram_read_buffer` | Guest | Board section preserves video address/control pipeline state and validates the VRAM offset. |
| `mvs_video_auto_animation_speed`, `.mvs_video_auto_animation_disabled`, `.mvs_video_auto_animation_counter`, `.mvs_video_auto_animation_frame_counter` | Guest | Board section preserves sprite auto-animation configuration and phase used by later frames. |
| `mvs_display_position_interrupt_control`, `.mvs_irq_pending_mask` | Guest | Board section preserves raster interrupt control and pending IRQ bits, with domain checks before apply. |
| `mvs_frame_cycle`, `.mvs_frame_cycle_carry`, `.mvs_frame_count` | Guest | Board section retains executed-cycle position, instruction overshoot carry, and VBlank/frame count; bounds are checked against frame timing. |
| `mvs_output_data`, `.mvs_output_latch` | Guest | Board section preserves output register/latch state. |
| `mvs_use_cart_vectors`, `.mvs_cart_audio_selected` | Guest | Board section preserves vector/audio routing controls and validates boolean domains. |
| `mvs_memcard_lock1`, `.mvs_memcard_unlock2`, `.mvs_coin_lockout_mask`, `.mvs_save_ram_unlocked`, `.mvs_palette_bank_selected`, `.mvs_screen_shadow` | Guest | Board section preserves protection, save-RAM permission, palette-bank, coin lockout and video-shadow controls with per-field domain checks. |
| `mvs_watchdog_pet_generation`, `.mvs_watchdog_remaining_cycles` | Guest | Board section retains generation and emulated deadline. Remaining cycles are validated against the configured watchdog period. |
| `mvs_calendar` | Guest | Board section encodes all listed fields explicitly in fixed order; BCD, line, command and timer relations are validated before apply. |
| `mvs_sound` | Guest + Host + Observation | Sound section contains Z80 continuation, guest RAM/handshake/banks, PCM phase and both filter histories. Destination media/callback pointers and inactive output ownership remain on the live sound owner. YM state is a separate checked section. |
| `mvs_sound_step_cycles` | Guest | Board section retains the sound scheduler cycle phase. |
| `mvs_failure` | Lifecycle/observation | Capture rejects a failure latch, including raw `GN_RUN_FAULT` with status `GN_STATUS_OK`. Successful restore clears the old report after all validation; rejection preserves it. Tests witness raw guest-fault and sound-device-fault recovery by replacement staging, not resuming a failed callback. |
| `mvs_completed_main_instructions` | Observation | Board section preserves this bounded failure-evidence count; it saturates at `UINT64_MAX`. |
| `mvs_protocol` | Observation/continuation | Board section preserves protocol trace, verdict evidence, input correlation, and bounded stall counters. The transient `guest_active` call guard is always encoded as zero and rebuilt inactive. |
| `cpu` | Host + Guest + Observation | Pointer and bus/allocator bindings remain destination-owned; CPU continuation uses the named CPU section. Successful apply clears only CPU fetch trace history. |
| Test-only `test_fail_bus_callbacks`, `test_trace_count`, `test_trace_dropped`, `test_mutation`, `test_mvs_failure`, `test_trace[]` | Observation/test-only | Compiled only with `GLUEYNEO_SDK_TEST_HOOKS`; absent from consumer runtime and every production codec. |
| `gn_instance.allocator` | Host | Retained instance allocation binding; not serialized. |
| `gn_instance.image` | Host/ownership | Image pointer is the owning graph edge; keep the destination image and its allocation graph, never copy an address from a state buffer. |
| `gn_instance.mvs_save` (`scope[16]`, `load_generation`, `restore_branch`, `mutation_sequence`, `export_sequence`, `latest_receipt`, `scope_valid`, `dirty`, `baseline_known`, `startup_import_allowed`, `exhausted`, `receipt_valid`, `receipt_consumed`) | Host lifecycle/ownership | Per-instance save lineage, startup gate, and receipt-consumption state. Explicitly absent from GNST snapshots and GNSV durable bytes. A successful continuation restore updates this owner only after validated apply; rejected restore leaves it unchanged. |
| Test-only `gn_instance.state_resources` | Observation/test-only | Reset at each restore entry; counts fixed work stages, conservative schema/bulk-byte charges and actual YM span consumption. Private build-derived object-storage bounds include stack guest staging and C/C++ replacement graphs. Absent from consumer builds and canonical bytes; no lifetime counter. See `native-state.md` for equations and overhead exclusions. |

## MVS save lineage and snapshot exclusion

| Owner item | Class | GNST snapshot bytes | GNSV durable bytes | Restore or lifecycle effect |
|---|---|---|---|---|
| `gn_instance.mvs_save` and its listed fields | Host lifecycle/ownership | No | No | Dirty/baseline status and nonrewinding receipt lineage remain on the instance; successful restore branches lineage after apply |
| `gn_image.save_owner` | Host non-owned hook | No | No | Candidate commit binds the destination instance; image restore retains its destination link |
| `gn_image.mvs_save_ram` contents | Guest SRAM | Yes, MVS memory section | Yes, exact 65,536-byte GNSV payload | Snapshot restore may restore historical SRAM and marks save state dirty; neither restore nor export is a host disk commit |

`save_owner` and `mvs_save` are not in the guest snapshot or durable format.
The SRAM contents themselves are future-affecting guest bytes, so continuation
includes them while the durable codec transfers them separately. See
[`native-save.md`](native-save.md) for the envelope and host publication rules.

## Owned 68000 (`experiments/owned_cpu/cpu.h`, `cpu.c`)

The production private `owned_cpu_state` is encoded by named CPU fields in the
diagnostic CPU section, never by C object representation. Private host bindings
and transient execution state stay on the destination CPU.

| Fields | Class | Mapping / validation |
| --- | --- | --- |
| `bus`, `allocator` (`userdata`, callbacks, allocation functions) | Host | Keep destination bindings. Apply invokes no callbacks and allocates nothing. |
| `data_registers[8]`, `address_registers[8]`, `pc`, `previous_pc`, `usp`, `ssp`, `fault_pc`, `sr`, `instruction_register`, `stopped`, `irq_level`, `irq7_pending`, `reset_pending`, `last_exception_vector`, `instructions`, `instruction_cycles`, `reset_cycles`, `exception_cycles`, `idle_cycles`, `total_cycles`, `reset_signal_events` | Guest | Named CPU section, fixed-width big-endian values. Validate domains, stack relation, reset debt and counter arithmetic before apply. `fault_pc`/instruction register and all counters are retained continuation fields, not omitted because they are also useful for diagnosis. |
| `ready` | Lifecycle | Reset/load readiness precondition; cannot make an uninitialized CPU restorable. |
| `faulted` | Lifecycle | Terminal host callback fault gate; capture fails and state cannot clear it except reset. Diagnostic raw guest fault has a separate image latch. |
| `active`, `bus_cycles` | Lifecycle/transient | Active execution is not a completed-call boundary. Capture is rejected while active; in-flight bus slots are not a legal snapshot boundary. |
| `fetch_trace_run_sequence`, `fetch_trace_count`, `fetch_trace_next`, `fetch_trace[]` (`prefetch_pc`, `resulting_cursor`, `fetched_word`, `run_sequence`, `total_cycles`) | Observation | Bounded instruction-fetch observer. Apply resets it; no guest behavior depends on its contents. Its public/private observer contract is a trace of post-restore execution, not historical replay. |
| Test seeds and faulted-state inspection | Test-only | `OWNED_CPU_TEST_HOOKS`; absent from production consumer builds and codec. |

## Z80 candidate (`src/chips/z80_candidate.c`, `third_party/chips/z80.h`)

Plan 04-02 implements the private `GZ80` v1 canonical codec for candidate
continuation. The complete byte map, source-derived decoder relations,
allocation/failure behavior, and exact source ancestry are in
[`state-z80-inventory.md`](state-z80-inventory.md). The MVS sound section nests
these bytes and rebinds them to a fresh healthy destination Z80 candidate before
the commit.

| Fields | Class | Mapping / validation |
| --- | --- | --- |
| `z80_candidate.bus`, `.userdata` | Host | Borrowed bus callback and owner context; rebind/preserve destination. |
| `z80_candidate.cpu` / `z80_t.step`, `addr`, `dlatch`, `opcode`, `hlx_idx`, `prefix_active`, `pins`, `int_bits`, `pc`, `af`, `bc`, `de`, `hl`, `ix`, `iy`, `wz`, `sp`, `ir`, `af2`, `bc2`, `de2`, `hl2`, `im`, `iff1`, `iff2` | Guest | Full decoder, temporary, pin/interrupt, primary/shadow register and interrupt-mode continuation. The private canonical schema encodes named fixed-width big-endian scalars and validates source-derived decoder relations. Unions are alternative views of the same bytes and are encoded once. See `state-z80-inventory.md` for offsets and criteria. |
| `z80_candidate.pins`, `.cycles`, `.bus_failed` | Guest + lifecycle | Current pin bus phase and cycle count affect the next tick; the canonical schema retains both. A latched callback failure is terminal: capture and destination rebind reject it. The separate `z80_t.pins` is the library's saved pin state; control bits agree with wrapper pins while read data may differ after bus service. |
| `z80_candidate_snapshot.version`, `.cpu`, `.pins`, `.cycles` | Legacy in-memory/test schema | Retained for internal adapter compatibility, with semantic validation. It is not the canonical byte format or a public/cross-build contract. Canonical bytes use the `z80_candidate_state_*` seams. |
| Candidate test-only allocator hooks | Observation/test-only | `Z80_CANDIDATE_TEST_HOOKS` is compiled only into `z80_admission_test`; these per-call counters are absent from consumer/runtime builds and canonical bytes. |

## YM2610 wrapper and pinned ymfm core

Plan 04-03 implemented a private, versioned `GYM1` YM2610 continuation seam with
checked canonical traversal, nested semantic validation, exact length checks,
staging, and destination callback rebinding. MVS places those bytes in its
required YM2610 section and rebinds callbacks to the retained destination sound
owner before swapping candidates. The default `ymfm_saved_state` visitor remains
the legacy zero-filling traversal for other consumers. See
[`state-ym-inventory.md`](state-ym-inventory.md) for the wire and field-level
contract.

| Owner and fields | Class | Mapping / validation |
| --- | --- | --- |
| `ym2610_candidate_callbacks.read/write/irq`, `.adpcm_a_size`, `.adpcm_b_size`, `.io_size`; candidate userdata | Host + immutable extents | Callback pointers and userdata remain bound to destination; sizes must agree with loaded sample/I/O regions. Never serialize pointers. |
| `candidate_interface.now_`, `busy_end_`, `timer_due_[2]`, `timer_active_[2]` | Guest | Emulated chip clock, busy endpoint, and timer deadlines are in private `GYM1` v1; an active deadline must be after `now_`. |
| `candidate_interface.failure_`, `callback_active_` | Lifecycle | A failed callback is not a live resumable chip; callback-active is an in-call reentrancy guard, so snapshots only occur at inactive call boundaries. |
| `candidate_interface.timer_programs_`, `timer_expirations_`, `adpcm_a_sample_reads_`, `adpcm_b_sample_reads_`, `irq_assertions_`, `irq_deassertions_` | Observation | Qualification counters copied to observation; do not drive chip behavior. Saturating increment semantics; diagnostics clear independently from guest reset. |
| `ym2610_candidate.clock_remainder`, `.total_clocks` | Guest | Wrapper-to-chip divider remainder and cumulative emulated input clock are in `GYM1` v1; remainder is `< 16` and equals `total_clocks % 16`, and `total_clocks == now_`. |
| `ym2610_candidate.chip` (`m_address`, `m_eos_status`, `m_flag_mask`; FM engine; SSG engine; SSG resampler; ADPCM-A and ADPCM-B engines) | Guest | The pinned traversal and Glueyneo held-output extension are encoded in exact order by private `GYM1` v1. Staging validates the actual nested fields; it never serializes the C++ object. Fidelity, channel mask and sample-rate setup are immutable candidate configuration. |
| YM FM engine/registers/channels/operators | Guest | Preserve `m_env_counter`, `m_status`, `m_clock_prescale`, `m_irq_mask`, `m_irq_state`, `m_timer_running[2]`, `m_total_clocks`; OPN `m_lfo_counter`, `m_lfo_am`, `m_regdata`; every channel's `m_feedback[2]` and `m_feedback_in`; every operator's `m_phase`, `m_env_attenuation`, `m_env_state`, `m_ssg_inverted`, `m_key_state`, `m_keyon_live`. Checked restore rebuilds derived operator/channel caches before subsequent output. |
| YM SSG registers/engine/resampler | Guest | Preserve SSG `m_regdata`, `m_tone_count[3]`, `m_tone_state[3]`, `m_envelope_count`, `m_envelope_state`, `m_noise_count`, `m_noise_state`; resampler `m_sampindex` and `m_last.data`. The SSG resampler's configured ratio/function pointer is reconstructed from immutable fidelity/clock configuration. |
| YM ADPCM-A/B registers and channels | Guest | Preserve both register arrays `m_regdata`; ADPCM-A channel `m_playing`, `m_curnibble`, `m_curbyte`, `m_curaddress`, `m_accumulator`, `m_step_index`; ADPCM-B channel `m_status`, `m_curnibble`, `m_curbyte`, `m_dummy_read`, `m_position`, `m_curaddress`, `m_accumulator`, `m_prev_accum`, `m_adpcm_step`. The staged chip validates source-derived address/decoder domains; the rebound callback wrapper checks each actual external access against the destination sample extent. |
| YMFM interface `m_engine`; engine references, register/channel/operator references | Host/rebuild | The callback-owner pointer and the C++ reference/`unique_ptr` graph are rebound/reconstructed within a destination chip; never encoded. |
| YM chip `m_fidelity`, `m_fm_mask`, `m_fm_samples_per_output`, `m_last_fm` | Immutable/rebuild + Guest | `m_fidelity` and `m_fm_mask` are constructor configuration; `m_fm_samples_per_output` is rebuilt by `update_prescale`. `m_last_fm.data` is held output consumed by later `generate` calls and is persisted by the private traversal extension because upstream `ym2610::save_restore` omits it. |
| `selected_register[2]` | Guest | Address latches select future data writes; encode and validate as two bytes. |
| YM wrapper `diagnostic_clocks`, `event_count`, `event_dropped`, register-family/write/sample/timer/IRQ/native-frame counters, `native_peak`, `events[]` | Observation | Bounded write/output diagnostics only. Clear on observer clear; must not reset chip registers, timers, phases, or sample state. |
| Test-only YM fault injection and probe hooks | Test-only | Compiled only for tests; not part of production schema. |

## Calendar, sound scheduler, PCM converter, and MVS protocol

| Owner and fields | Class | Mapping / validation |
| --- | --- | --- |
| `gn_mvs_calendar.time_counter[6]`, `shift_reg[7]`, `data_in`, `clk`, `stb`, `command`, `data_out`, `tp`, `clock_running`, `data_out_running`, `tp_running`, `tick_remainder`, `clock_remaining`, `data_out_remaining`, `data_out_period`, `tp_remaining`, `tp_period` | Guest | Board section encodes each field explicitly. Restore validates BCD/calendar command and line domains, divider remainder, and timer/clock relations. Fixed epoch/configuration is deterministic emulator state, not host clock. |
| `gn_mvs_sound.program`, `.program_size`, `.bios_program`, `.bios_program_size`, `.samples`, `.samples_size` | Host + immutable | Retained media pointers/extents. Verify immutable program/BIOS/sample identity against independently loaded media; no pointer bytes in a section. |
| `gn_mvs_sound.cart_selected`, `.ym_irq`, `.ram[0x800]`, `.banks[4]`, `.command`, `.reply`, `.command_pending`, `.nmi_enabled`, `.main_clock_remainder`, `.failed`, `.failure_stage`, `.failure_reason`, `.failure_status`, `.failure_site`, `.failure_cause`, `.failure_bus_valid`, `.failure_operation`, `.failure_width`, `.failure_address` | Guest/lifecycle | Sound section preserves guest handshake/RAM/banks/IRQ/divider values and validates boolean/index domains. Failure fields are excluded: capture rejects the latch, and a fully staged success clears prior fault evidence; a rejected restore leaves it unchanged. |
| `gn_mvs_sound.cpu`, `.ym` | Host pointer + Guest | Preserve destination chip owners and restore their named guest continuation via their independently validated schema. |
| `pcm_history[80]`, `pcm_right_history[80]`, `pcm_history_next`, `pcm_output_phase` | Guest | Sound section preserves converter history and phase because they affect future samples. Restore validates history index and output phase. |
| `pcm_active_sink`, `.pcm_active_capacity_frames` | Host + lifecycle | Caller-owned per-call output buffer and capacity; valid only during synchronous rendering call. Do not persist or restore. |
| `pcm_call_generated_frames`, `.pcm_call_delivered_frames`, `.pcm_capture_active` | Lifecycle/observation | Per-call accounting and active guard; snapshots only at a completed boundary. No later output can depend on past reported counts. |
| Test-only sound counters/failure injections | Observation/test-only | `test_fail_bus`, `test_fail_tick_limit`, `test_main_cycles_advanced`, `test_ym_input_clocks`, `test_native_samples`, `test_irq_assertions`, `test_irq_deassertions`, `test_bank_changes`, `test_timer_register_writes[3]`, `test_ym_selected_register`; absent from consumer schema. |
| `gn_mvs_protocol.events[64]`, `.count`, `.dropped`, `.sequence`, `.cycle_base`, `.input_sequence`, attract/coin/start/player-start/BIOS-P1 input sequence fields | Observation/continuation | Board section encodes the bounded trace and input-correlation metadata so diagnostics continue from the saved boundary. Count is bounded before apply; saturation/drop accounting is retained. |
| `gn_mvs_protocol.guest_active`, `.decided`, `.corroborated`, `.attract_start_reached`, `.user_request`, `.player_start_entered`, `.player_start_with_p1_indication` | Observation/continuation | Board section preserves derived verdict evidence except `guest_active`, which is a transient call guard forced to zero. Boolean and request enums are validated. |
| `gn_mvs_protocol.polled[32]`, `.polled_count`, `.polled_untracked_reads`, `.interrupts_taken`, `.irq_ack_writes`, `.sr_mask_histogram[8]`, `.pc_region_histogram[5]`, `.low_program_window_reads`, `.unmapped_read_count` | Observation/continuation | Board section preserves bounded stall diagnosis rows and counters; counts/addresses are validated and saturating semantics remain unchanged. |
| `gn_mvs_failure` fields: `component`, `stage`, `reason`, `site`, `device_cause`, `underlying_status`, `operation`, `valid`, `guest_executed`, `site_valid`, `device_cause_valid`, `underlying_status_valid`, `emulated_cycle_valid`, `instruction_boundary_valid`, `pc_valid`, `opcode_valid`, `bus_access_valid`, `capture_pending`, `bus_width`, `opcode`, `bus_address`, `pc`, `emulated_cycle`, `completed_main_instructions` | Observation/lifecycle | Bounded failure report; flags qualify fields. It never claims complete guest state. Captures and codecs must reject unresolved failed device state rather than invent a resume point. |

## Observation consumers, overflow, and reset semantics

`gn_observe_mvs_progress` exposes the MAME unmapped-write, watchdog-pet, and
watchdog-reset counts. They saturate at `UINT32_MAX`, are preserved by MVS
continuation, and MVS reset clears them. The completed-main-instruction count is
exposed inside failure evidence, saturates at `UINT64_MAX`, and is preserved.
`gn_observe_mvs_bus_fault` exposes only bounded last-fault fields, guarded by
validity bits. Capture rejects an active bus fault; successful restore clears
the old fault report only after commit is guaranteed.

The private protocol trace and stall diagnosis use bounded event/polled arrays;
64 trace entries and 32 polled-register entries cannot grow. Full trace capacity
sets the dropped/overflow signal, and numeric read/interrupt histograms use
saturating increments. MVS continuation preserves these observer outputs while
forcing its in-call `guest_active` guard inactive. YM2610 register/audio counters
and its bounded 32-event history are diagnostic state outside `GYM1`; staged YM
replacement resets those candidate observations, while chip registers, clocks,
timers, phases and held output continue. Test-only counters/injections are not
serialized. Owned CPU fetch-trace history clears on successful state apply;
subsequent entries describe fetches after that API boundary. PCM per-call
sink/capture guards remain destination lifecycle state and capture/restore are
rejected during an active call.

## Source ancestry

The owned CPU classification follows the private `struct owned_cpu` and named
`owned_cpu_state` in `experiments/owned_cpu/cpu.c` and `cpu.h`. The Z80 field map
follows the vendored `third_party/chips/z80.h` `z80_t` declaration and its
Glueyneo wrapper. YM2610 field names follow the selected vendored ymfm source
closure at upstream revision
`81aec25ccbb98f4873a255f7551ac4dadac59b4a`, reviewed 2026-10-07; see
[`third_party/ymfm/NOTICE.md`](../third_party/ymfm/NOTICE.md) for local patch,
license, and per-file byte identities. The selected upstream `ym2610::save_restore`
traversal omits held `m_last_fm`; the private 04-03 traversal persists that
future-affecting value.

## Current schema boundary and downstream obligations

The header stores independent format/replay/profile/configuration IDs and a
normalized media digest. Diagnostic state retains its two required sections.
MVS state has five required sections in canonical order: CPU, memory, board,
sound, and YM2610. The MVS memory section contains work RAM, backup RAM, palette
RAM, and big-endian video words. Board state includes protection, input, raster,
watchdog, calendar, scheduler, counters, and protocol history. Sound state
nests the `GZ80` v1 bytes and PCM converter state; YM state nests `GYM1` v1.
Apply preserves destination ownership and retained memory addresses, and clears
only documented host fault/call/CPU/YM-observer state.

The phase-level sequence that supplied these integrated codecs is:

| Plan | Required continuation work |
| --- | --- |
| 04-02 | Checked canonical Z80 decoder/pin/cycle schema; validate before rebinding destination bus ownership. |
| 04-03 | Completed private checked YM2610/ymfm schema, timer continuation, and derived-cache rebuild; does not add an MVS public section. |
| 04-04 | Integrated board/calendar/raster/video/protection/input/memory/sound sections with atomic retained-address apply and MVS continuation witnesses. |

These entries describe the implemented bounded native schema and its source
ancestry. State bytes remain separate from durable saves and replay files; the
media digest is not authenticity proof, and continuation does not claim unknown
hardware behavior or broad cross-build compatibility.

## Measured fixture size and unmeasured staging

For the public synthetic MVS fixture generated by `public_sound_test
--write-fixture`, the current `sdk-debug` MVS envelope capacity is 224,113
bytes. The calculation is a 72-byte header + five 8-byte section headers +
152-byte CPU payload + 217,088-byte memory payload + 2,794-byte board payload,
plus 2,781-byte sound payload and 1,186-byte `GYM1` payload. Memory is 65,536 bytes
of work RAM + 65,536 bytes of backup RAM + 16,384 bytes of palette RAM + 34,816
big-endian video words. Z80 and YM sizes come from their checked codecs at
successful load; the YM length is specific to this fixture and source
revision.

Peak aggregate restore staging allocation across C and C++ candidates has not
been measured. This remains a blocking bound for downstream qualification;
the serialized capacity is not a staging-memory limit. The test allocator
observes zero image-allocator attempts during no-fail apply, but it does not
instrument all C++ YMFM heap allocations and does not prove aggregate peak
memory. Do not infer or publish a peak number from the envelope size.
