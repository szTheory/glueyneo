/* SPDX-License-Identifier: MIT */
#ifndef GLUEYNEO_SDK_PRIVATE_H
#define GLUEYNEO_SDK_PRIVATE_H

#include "glueyneo/glueyneo.h"
#include "../experiments/owned_cpu/cpu.h"
#if defined(Z80_CANDIDATE_TEST_HOOKS)
#include "chips/z80_candidate.h"
#endif

typedef struct z80_candidate z80_candidate;
typedef struct ym2610_candidate ym2610_candidate;

/* Logical MVS frame budget: 264 lines * 768 main-CPU clocks. Raw gn_run_mvs
 * remains a minimum-cycle-budget API; this private consumer seam accounts for
 * instruction overshoot between successive logical frames. */
#define GN_MVS_FRAME_BUDGET_CYCLES UINT64_C(202752)
gn_status gn_mvs_run_frame_budget(gn_instance *instance, gn_run_result *out_result);

/* Render the current private MVS video state into caller-owned XRGB8888
 * storage. This is a pure observation of the loaded instance: it does not run
 * the guest or advance emulated time. */
gn_status gn_private_mvs_render_frame(const gn_instance *instance,
                                      uint32_t width, uint32_t height,
                                      size_t pitch_bytes, uint8_t *pixels,
                                      size_t pixel_capacity_bytes,
                                      size_t *out_pixels_produced);

/* Expose the retained mutable SRAM allocation only for a loaded MVS image.
 * The view owns no storage and remains valid only until content unload. */
gn_status gn_private_mvs_save_ram_view(gn_instance *instance,
                                       uint8_t **out_bytes,
                                       size_t *out_size);

#if defined(GLUEYNEO_SDK_TEST_HOOKS)
/* Adapter-local test access for the real per-instance restore/fault hooks. */
gn_instance *gn_test_libretro_instance(void);
#endif

/* Read-only, private snapshot of guest-produced video activity for local
 * qualification diagnostics. Counts and modeled controls only; no guest bytes
 * are copied and emulated time is not advanced. */
typedef struct {
    uint32_t nonzero_vram_words;
    uint32_t nonzero_fixed_tilemap_words;
    uint32_t nonzero_sprite_words;
    uint32_t nonzero_palette_entries;
    uint32_t visible_sprites;
    uint32_t visible_nonfull_y_zoom_samples;
    uint32_t frame_count;
    uint32_t frame_cycle;
    uint64_t frame_cycle_carry;
    uint8_t auto_animation_counter;
    uint8_t backdrop_palette_nonzero;
    uint16_t video_ram_offset;
    uint16_t video_ram_modulo;
    uint8_t palette_bank_selected;
    uint8_t screen_shadow;
    uint8_t video_auto_animation_speed;
    uint8_t video_auto_animation_disabled;
    uint8_t display_position_interrupt_control;
} gn_mvs_private_video_activity;

gn_status gn_private_mvs_video_activity(
    const gn_instance *instance, gn_mvs_private_video_activity *out_activity);

gn_status gn_private_mvs_fetch_trace(
    const gn_instance *instance, owned_cpu_fetch_trace_event *events,
    size_t capacity, size_t *out_count);

/* MVS BIOS-to-cartridge protocol trace, attract/start verdict and stall
 * diagnosis (plan 05-08, D-07). The contract is "Attract/start predicate" and
 * "Stall diagnosis" in docs/mvs-media.md, which cites the fetched sources S1-S7.
 * Everything below is private, per-instance and non-ABI; the observers only
 * record what guest instructions did and never change machine behavior. */
#define GN_MVS_BIOS_SYSTEM_MODE UINT32_C(0x10fd80)
#define GN_MVS_BIOS_USER_REQUEST UINT32_C(0x10fdae)
#define GN_MVS_BIOS_USER_MODE UINT32_C(0x10fdaf)
#define GN_MVS_BIOS_START_FLAG UINT32_C(0x10fdb4)
#define GN_MVS_USER_ENTRY UINT32_C(0x000122)
#define GN_MVS_PLAYER_START_ENTRY UINT32_C(0x000128)
#define GN_MVS_REQUEST_DEMO 2u
#define GN_MVS_REQUEST_TITLE 3u
#define GN_MVS_USER_MODE_TITLE_DEMO 1u
#define GN_MVS_PROTOCOL_TRACE_CAPACITY 64u
#define GN_MVS_POLLED_TABLE_CAPACITY 32u
#define GN_MVS_POLLED_REPORT_ROWS 8u
#define GN_MVS_SR_MASK_BUCKETS 8u
#define GN_MVS_PC_REGION_BUCKETS 5u

typedef enum {
    GN_MVS_PROTOCOL_BIOS_VAR_WRITE = 1,
    GN_MVS_PROTOCOL_USER_ENTRY_FETCH = 2,
    GN_MVS_PROTOCOL_PLAYER_START_FETCH = 3
} gn_mvs_protocol_kind;

typedef enum {
    GN_MVS_PC_BIOS = 0,
    GN_MVS_PC_CART_FIXED,
    GN_MVS_PC_CART_BANKED,
    GN_MVS_PC_WORK_RAM,
    GN_MVS_PC_OTHER
} gn_mvs_pc_region;

typedef enum {
    GN_MVS_FAILURE_COMPONENT_NONE = 0,
    GN_MVS_FAILURE_COMPONENT_MAIN_CPU,
    GN_MVS_FAILURE_COMPONENT_SOUND_CPU,
    GN_MVS_FAILURE_COMPONENT_BOARD,
    GN_MVS_FAILURE_COMPONENT_INTERNAL
} gn_mvs_failure_component;

typedef enum {
    GN_MVS_FAILURE_STAGE_NONE = 0,
    GN_MVS_FAILURE_STAGE_OBSERVE,
    GN_MVS_FAILURE_STAGE_IRQ_UPDATE,
    GN_MVS_FAILURE_STAGE_EXECUTE,
    GN_MVS_FAILURE_STAGE_BUS_ACCESS,
    GN_MVS_FAILURE_STAGE_SOUND_CATCHUP,
    GN_MVS_FAILURE_STAGE_WATCHDOG_RESET,
    GN_MVS_FAILURE_STAGE_TIMING_ACCOUNTING
} gn_mvs_failure_stage;

typedef enum {
    GN_MVS_FAILURE_REASON_NONE = 0,
    GN_MVS_FAILURE_REASON_INTERNAL_FAILURE,
    GN_MVS_FAILURE_REASON_BUS_FAILURE,
    GN_MVS_FAILURE_REASON_CYCLE_LIMIT,
    GN_MVS_FAILURE_REASON_INVALID_STATE,
    GN_MVS_FAILURE_REASON_CLOCK_OVERFLOW,
    GN_MVS_FAILURE_REASON_ACCOUNTING_MISMATCH
} gn_mvs_failure_reason;

typedef enum {
    GN_MVS_FAILURE_SITE_UNKNOWN = 0,
    GN_MVS_FAILURE_SITE_MAIN_OBSERVE,
    GN_MVS_FAILURE_SITE_MAIN_IRQ_UPDATE,
    GN_MVS_FAILURE_SITE_MAIN_EXECUTION,
    GN_MVS_FAILURE_SITE_MAIN_BUS_READ,
    GN_MVS_FAILURE_SITE_MAIN_BUS_WRITE,
    GN_MVS_FAILURE_SITE_SOUND_MEMORY_READ,
    GN_MVS_FAILURE_SITE_SOUND_MEMORY_WRITE,
    GN_MVS_FAILURE_SITE_SOUND_IO_READ,
    GN_MVS_FAILURE_SITE_SOUND_IO_WRITE,
    GN_MVS_FAILURE_SITE_SOUND_INTERRUPT_ACK,
    GN_MVS_FAILURE_SITE_SOUND_TICK,
    GN_MVS_FAILURE_SITE_SOUND_RESET,
    GN_MVS_FAILURE_SITE_YM2610_SAMPLE_READ,
    GN_MVS_FAILURE_SITE_BOARD_WATCHDOG_RESET,
    GN_MVS_FAILURE_SITE_INTERNAL_TIMING
} gn_mvs_failure_site;

typedef enum {
    GN_MVS_FAILURE_CAUSE_UNKNOWN = 0,
    GN_MVS_FAILURE_CAUSE_MAIN_BUS_CALLBACK,
    GN_MVS_FAILURE_CAUSE_SOUND_BUS_CALLBACK,
    GN_MVS_FAILURE_CAUSE_Z80_TICK,
    GN_MVS_FAILURE_CAUSE_Z80_RESET,
    GN_MVS_FAILURE_CAUSE_YM2610_CALLBACK,
    GN_MVS_FAILURE_CAUSE_OWNED_CPU,
    GN_MVS_FAILURE_CAUSE_BOARD_RESET,
    GN_MVS_FAILURE_CAUSE_TIMING_ACCOUNTING
} gn_mvs_failure_cause;

typedef enum {
    GN_MVS_FAILURE_STATUS_UNKNOWN = 0,
    GN_MVS_FAILURE_STATUS_Z80_INVALID_ARGUMENT,
    GN_MVS_FAILURE_STATUS_Z80_OUT_OF_MEMORY,
    GN_MVS_FAILURE_STATUS_Z80_BUS_FAILURE,
    GN_MVS_FAILURE_STATUS_Z80_CYCLE_LIMIT,
    GN_MVS_FAILURE_STATUS_Z80_INVALID_SNAPSHOT,
    GN_MVS_FAILURE_STATUS_YM2610_INVALID_ARGUMENT,
    GN_MVS_FAILURE_STATUS_YM2610_NO_MEMORY,
    GN_MVS_FAILURE_STATUS_YM2610_CALLBACK_FAILURE,
    GN_MVS_FAILURE_STATUS_YM2610_EXCEPTION,
    GN_MVS_FAILURE_STATUS_YM2610_CAPACITY,
    GN_MVS_FAILURE_STATUS_YM2610_LIMIT,
    GN_MVS_FAILURE_STATUS_OWNED_CPU_INVALID_ARGUMENT,
    GN_MVS_FAILURE_STATUS_OWNED_CPU_ALLOCATION_FAILURE,
    GN_MVS_FAILURE_STATUS_OWNED_CPU_ADDRESS_ERROR,
    GN_MVS_FAILURE_STATUS_OWNED_CPU_HOST_FAULT,
    GN_MVS_FAILURE_STATUS_OWNED_CPU_UNSUPPORTED_OPCODE,
    GN_MVS_FAILURE_STATUS_OWNED_CPU_BUDGET,
    GN_MVS_FAILURE_STATUS_OWNED_CPU_COUNTER_OVERFLOW,
    GN_MVS_FAILURE_STATUS_OWNED_CPU_PRIVILEGE_VIOLATION
} gn_mvs_failure_status;

typedef enum {
    GN_MVS_FAILURE_BUS_UNKNOWN = 0,
    GN_MVS_FAILURE_BUS_READ,
    GN_MVS_FAILURE_BUS_WRITE,
    GN_MVS_FAILURE_BUS_INTERRUPT_ACK
} gn_mvs_failure_bus_operation;

typedef struct {
    gn_mvs_failure_component component;
    gn_mvs_failure_stage stage;
    gn_mvs_failure_reason reason;
    gn_mvs_failure_site site;
    gn_mvs_failure_cause device_cause;
    gn_mvs_failure_status underlying_status;
    gn_mvs_failure_bus_operation operation;
    uint8_t valid;
    uint8_t guest_executed;
    uint8_t site_valid;
    uint8_t device_cause_valid;
    uint8_t underlying_status_valid;
    uint8_t emulated_cycle_valid;
    uint8_t instruction_boundary_valid;
    uint8_t pc_valid;
    uint8_t opcode_valid;
    uint8_t bus_access_valid;
    uint8_t capture_pending;
    uint8_t bus_width;
    uint16_t opcode;
    uint32_t bus_address;
    uint32_t pc;
    uint64_t emulated_cycle;
    uint64_t completed_main_instructions;
} gn_mvs_failure;

void gn_mvs_failure_clear(gn_mvs_failure *failure);
void gn_mvs_failure_record(gn_mvs_failure *failure,
                           gn_mvs_failure_component component,
                           gn_mvs_failure_stage stage,
                           gn_mvs_failure_reason reason);

typedef struct {
    uint32_t address;
    uint8_t kind;
    uint8_t value;
    uint8_t writer_pc_region;
    uint8_t reserved;
    uint64_t total_cycles;
    uint64_t sequence;
    uint64_t input_sequence;
} gn_mvs_protocol_event;

typedef enum {
    GN_MVS_ATTRACT_NONE = 0,
    GN_MVS_ATTRACT_NO_REQUEST,
    GN_MVS_ATTRACT_WRONG_VALUE,
    GN_MVS_ATTRACT_WRONG_SOURCE,
    GN_MVS_ATTRACT_WRONG_ORDER,
    GN_MVS_ATTRACT_TRACE_OVERFLOW
} gn_mvs_attract_rejection;

typedef struct {
    uint8_t accepted;
    uint8_t rejection;       /* gn_mvs_attract_rejection; NONE while pending */
    uint8_t user_request;    /* 2 demo or 3 title when accepted, else 0 */
    uint8_t user_mode_corroborated;
    uint64_t request_sequence;
    uint64_t entry_sequence;
    uint64_t entry_total_cycles;
} gn_mvs_attract_verdict;

typedef struct {
    uint32_t address;
    uint64_t reads;
} gn_mvs_polled_register;

/* Stall diagnosis (docs/mvs-media.md "Stall diagnosis"): counts and public
 * register addresses only, never program bytes or PCs. polled[] holds at most
 * the 8 most-read registers inside $300000-$3FFFFF and $2FFFE0-$2FFFFF. */
typedef struct {
    uint64_t interrupts_taken;
    uint64_t irq_ack_writes;
    uint64_t sr_mask_histogram[GN_MVS_SR_MASK_BUCKETS];
    uint64_t pc_region_histogram[GN_MVS_PC_REGION_BUCKETS];
    uint64_t low_program_window_reads;
    uint64_t unmapped_read_count;
    uint32_t polled_count;
    gn_mvs_polled_register polled[GN_MVS_POLLED_REPORT_ROWS];
    uint64_t polled_untracked_reads;
    uint8_t bios_system_mode;
    uint8_t bios_user_request;
    uint8_t bios_user_mode;
    uint8_t attract_rejection;
} gn_mvs_stall_diagnosis;

/* Power-on calendar seed: 2000-01-01 00:00:00 packed in the uPD4990A
 * time-counter field order (seconds, minutes, hours, day, month << 4 |
 * weekday, year; BCD except the month nibble). This is a deterministic
 * emulator choice, not hardware: a real board keeps battery-backed time, and
 * the value is not host time. The weekday nibble is 0 because no fetched
 * source states the weekday encoding. Defined only here (plan 05-21). */
#define GN_MVS_CALENDAR_EPOCH {0x00u, 0x00u, 0x00u, 0x01u, 0x10u, 0x00u}

/* uPD4990A calendar state (plan 05-21, docs/mvs-media.md "Input, status and
 * calendar"). Per instance; advanced only from executed 68000 clocks. */
typedef struct {
    uint8_t time_counter[6];   /* BCD seconds, minutes, hours, day; (month << 4) | weekday; year */
    uint8_t shift_reg[7];      /* 48-bit shift register plus the 4-bit serial command register */
    uint8_t data_in;           /* input line levels last written at $380051 */
    uint8_t clk;
    uint8_t stb;
    uint8_t command;           /* command latched at the last strobe rising edge */
    uint8_t data_out;          /* output pins before output-enable gating */
    uint8_t tp;
    uint8_t clock_running;     /* time counter, data-out and time-pulse timers enabled */
    uint8_t data_out_running;
    uint8_t tp_running;
    uint32_t tick_remainder;   /* 68000 clocks times 128 not yet worth one 32768 Hz chip tick */
    uint32_t clock_remaining;  /* chip ticks until the next time-counter increment */
    uint32_t data_out_remaining;
    uint32_t data_out_period;
    uint32_t tp_remaining;
    uint32_t tp_period;
} gn_mvs_calendar;

/* Narrow, per-instance boot sound handshake and native converter. The ROM is
 * borrowed from the owned MVS image; CPU, RAM, resampler history and optional
 * caller-owned sink are tied to this image's lifetime. Host audio stays out of
 * the core. */
#define GN_MVS_SOUND_RAM_BYTES ((size_t)0x800u)
#define GN_MVS_PCM_FILTER_PHASES 12u
#define GN_MVS_PCM_FILTER_TAPS 80u
#define GN_MVS_PCM_MAX_OUTPUT_FRAMES 812u
typedef struct {
    const uint8_t *program;
    size_t program_size;
    const uint8_t *bios_program;
    size_t bios_program_size;
    uint8_t cart_selected;
    z80_candidate *cpu;
    ym2610_candidate *ym;
    const uint8_t *samples;
    size_t samples_size;
    uint8_t ym_irq;
    uint8_t ram[GN_MVS_SOUND_RAM_BYTES];
    uint8_t banks[4];
    uint8_t command;
    uint8_t reply;
    uint8_t command_pending;
    uint8_t nmi_enabled;
    uint8_t main_clock_remainder;
    int32_t pcm_history[GN_MVS_PCM_FILTER_TAPS];
    int32_t pcm_right_history[GN_MVS_PCM_FILTER_TAPS];
    size_t pcm_history_next;
    uint16_t pcm_output_phase;
    int16_t *pcm_active_sink;
    size_t pcm_active_capacity_frames;
    size_t pcm_call_generated_frames;
    size_t pcm_call_delivered_frames;
    uint8_t pcm_capture_active;
    uint8_t failed;
    uint8_t failure_stage;
    uint8_t failure_reason;
    gn_mvs_failure_status failure_status;
    uint8_t failure_site;
    uint8_t failure_cause;
    uint8_t failure_bus_valid;
    uint8_t failure_operation;
    uint8_t failure_width;
    uint32_t failure_address;
#if defined(GLUEYNEO_SDK_TEST_HOOKS)
    uint8_t test_fail_bus;
    uint8_t test_fail_tick_limit;
    uint64_t test_main_cycles_advanced;
    uint64_t test_ym_input_clocks;
    uint64_t test_native_samples;
    uint64_t test_irq_assertions;
    uint64_t test_irq_deassertions;
    uint64_t test_bank_changes;
    uint64_t test_timer_register_writes[3];
    uint8_t test_ym_selected_register;
#endif
} gn_mvs_sound;

/* Bounded local qualification diagnostics. These are private observations of
 * the existing per-instance sound and board state; they are not guest hooks
 * and clearing chip diagnostics does not alter the emulated machine. */
#define GN_MVS_SOUND_DIAGNOSTIC_EVENT_CAPACITY 32u
typedef struct {
    uint64_t clock;
    uint8_t port;
    uint8_t bank;
    uint8_t reg;
    uint8_t value;
    uint8_t family;
} gn_mvs_sound_register_event;

typedef struct {
    uint32_t version;
    uint32_t event_count;
    uint32_t event_dropped;
    uint64_t clocks;
    uint64_t register_writes;
    uint64_t ssg_register_writes;
    uint64_t ssg_volume_writes;
    uint64_t control_register_writes;
    uint64_t fm_register_writes;
    uint64_t fm_key_on_writes;
    uint64_t fm_key_off_writes;
    uint64_t fm_frequency_writes;
    uint64_t fm_level_writes;
    uint64_t fm_pan_writes;
    uint64_t adpcm_a_register_writes;
    uint64_t adpcm_a_control_writes;
    uint64_t adpcm_b_register_writes;
    uint64_t adpcm_b_control_writes;
    uint64_t adpcm_a_sample_reads;
    uint64_t adpcm_b_sample_reads;
    uint64_t timer_programs;
    uint64_t timer_expirations;
    uint64_t irq_assertions;
    uint64_t irq_deassertions;
    uint64_t native_frames;
    uint64_t native_nonzero_frames;
    uint64_t native_stereo_nonzero_frames;
    uint64_t native_ssg_nonzero_frames;
    uint32_t native_peak;
    gn_mvs_sound_register_event events[
        GN_MVS_SOUND_DIAGNOSTIC_EVENT_CAPACITY];
} gn_mvs_sound_chip_observation;

typedef struct {
    uint8_t cart_selected;
    uint8_t command;
    uint8_t reply;
    uint8_t command_pending;
    uint8_t nmi_enabled;
    uint8_t ym_irq;
    uint8_t banks[4];
    uint16_t sound_cpu_pc;
    uint64_t sound_cpu_cycles;
} gn_mvs_sound_board_observation;

typedef struct {
    gn_mvs_sound_chip_observation chip;
    gn_mvs_sound_board_observation board;
} gn_mvs_sound_observation;

gn_status gn_private_mvs_sound_diagnostics_clear(gn_instance *instance);
gn_status gn_private_mvs_sound_observe(
    const gn_instance *instance, gn_mvs_sound_observation *out_observation);

#if defined(GLUEYNEO_SDK_TEST_HOOKS)
#define GN_TEST_NATIVE_SHA256_HOOK 1
typedef struct {
    uint64_t main_cycles_advanced;
    uint64_t ym_input_clocks;
    uint64_t native_samples;
    uint64_t irq_assertions;
    uint64_t irq_deassertions;
    uint64_t bank_changes;
    uint64_t timer_register_writes[3];
    uint64_t filter_history_digest;
    uint16_t pcm_output_phase;
    uint16_t filter_history_next;
    uint8_t main_clock_remainder;
    uint8_t ym_clock_remainder;
    uint8_t ym_irq;
    uint8_t banks[4];
    uint8_t failed;
} gn_test_mvs_sound_state;

typedef struct {
    uint32_t frame_count;
    uint32_t frame_cycle;
    uint64_t frame_cycle_carry;
    uint32_t watchdog_pet_count;
    uint32_t watchdog_reset_count;
    uint64_t watchdog_remaining_cycles;
    uint8_t irq_pending_mask;
    uint8_t animation_counter;
    uint8_t animation_frame_counter;
    uint8_t animation_speed;
    uint8_t animation_disabled;
} gn_test_mvs_machine_state;

gn_status gn_test_mvs_run_with_pcm_capture(
    gn_instance *instance, uint64_t cycle_budget, int16_t *audio,
    size_t audio_capacity_frames, gn_run_result *out_result,
    size_t *out_delivered_frames);
gn_status gn_test_mvs_sound_state_read(
    const gn_instance *instance, gn_test_mvs_sound_state *out_state);
gn_status gn_test_mvs_machine_state_read(
    const gn_instance *instance, gn_test_mvs_machine_state *out_state);
uintptr_t gn_test_mvs_save_ram_address(const gn_instance *instance);
typedef struct {
    uint64_t load_generation;
    uint64_t restore_branch;
    uint64_t mutation_sequence;
    uint64_t export_sequence;
    uint8_t scope_valid;
    uint8_t dirty;
    uint8_t baseline_known;
    uint8_t startup_import_allowed;
    uint8_t exhausted;
    uint8_t receipt_valid;
    uint8_t receipt_consumed;
} gn_test_save_observation;
gn_status gn_test_save_seed_lineage(
    gn_instance *instance, uint64_t load_generation, uint64_t restore_branch,
    uint64_t mutation_sequence, uint64_t export_sequence);
gn_status gn_test_save_observe(
    const gn_instance *instance, gn_test_save_observation *out_observation);
gn_status gn_test_save_stale_clean_bypass_arm(gn_instance *instance);
#endif

gn_status gn_mvs_sound_create(gn_mvs_sound *sound, const uint8_t *program,
                              size_t program_size);
gn_status gn_mvs_sound_prepare_state_rebind(
    gn_mvs_sound *sound, ym2610_candidate *staged_ym,
#if defined(Z80_CANDIDATE_TEST_HOOKS)
    z80_candidate_test_failpoint *failpoint,
#endif
    z80_candidate **out_healthy_cpu);
void gn_mvs_sound_destroy(gn_mvs_sound *sound);
gn_status gn_mvs_sound_reset(gn_mvs_sound *sound);
gn_status gn_mvs_sound_advance(gn_mvs_sound *sound, uint64_t main_cycles);
int gn_mvs_sound_write_command(gn_mvs_sound *sound, uint32_t address,
                               uint8_t command);
int gn_mvs_sound_read_reply(const gn_mvs_sound *sound, uint32_t address,
                            uint8_t *reply);

/* Per-instance mutable state, embedded in the instance image. */
typedef struct {
    gn_mvs_protocol_event events[GN_MVS_PROTOCOL_TRACE_CAPACITY];
    uint32_t count;
    uint32_t dropped;
    uint64_t sequence;
    uint64_t cycle_base;
    uint64_t input_sequence;
    uint64_t attract_input_sequence;
    uint64_t coin_input_sequence;
    uint64_t start_input_sequence;
    uint64_t player_start_input_sequence;
    uint64_t bios_p1_start_input_sequence;
    uint8_t guest_active;
    uint8_t decided;
    uint8_t corroborated;
    uint8_t attract_start_reached;
    uint8_t user_request;
    uint8_t player_start_entered;
    uint8_t player_start_with_p1_indication;
    gn_mvs_polled_register polled[GN_MVS_POLLED_TABLE_CAPACITY];
    uint32_t polled_count;
    uint64_t polled_untracked_reads;
    uint64_t interrupts_taken;
    uint64_t irq_ack_writes;
    uint64_t sr_mask_histogram[GN_MVS_SR_MASK_BUCKETS];
    uint64_t pc_region_histogram[GN_MVS_PC_REGION_BUCKETS];
    uint64_t low_program_window_reads;
    uint64_t unmapped_read_count;
} gn_mvs_protocol;

gn_mvs_pc_region gn_mvs_classify_pc(uint32_t pc);
void gn_mvs_protocol_reset(gn_mvs_protocol *protocol);
void gn_mvs_protocol_note_write(gn_mvs_protocol *protocol, uint32_t address,
                                unsigned width_bytes, uint16_t value,
                                gn_mvs_pc_region writer_region);
void gn_mvs_protocol_note_user_entry(gn_mvs_protocol *protocol);
void gn_mvs_protocol_note_input_change(gn_mvs_protocol *protocol,
                                       uint32_t previous_mask,
                                       uint32_t next_mask);
void gn_mvs_protocol_note_player_start(gn_mvs_protocol *protocol);
void gn_mvs_protocol_note_read(gn_mvs_protocol *protocol, uint32_t address);
void gn_mvs_protocol_note_read_fault(gn_mvs_protocol *protocol);
void gn_mvs_protocol_note_irq_ack(gn_mvs_protocol *protocol);
void gn_mvs_protocol_note_step(gn_mvs_protocol *protocol, unsigned sr_mask,
                               gn_mvs_pc_region pc_region,
                               uint64_t instructions, int interrupt_taken);
gn_mvs_attract_verdict gn_mvs_protocol_verdict(const gn_mvs_protocol *protocol);
void gn_mvs_protocol_diagnose(const gn_mvs_protocol *protocol,
                              gn_mvs_stall_diagnosis *out);
const char *gn_private_mvs_attract_rejection_name(unsigned rejection);

gn_status gn_private_mvs_protocol_trace(
    const gn_instance *instance, gn_mvs_protocol_event *events,
    size_t capacity, size_t *out_count, uint32_t *out_dropped);
gn_status gn_private_mvs_attract_verdict(const gn_instance *instance,
                                         gn_mvs_attract_verdict *out);
gn_status gn_private_mvs_stall_diagnosis(const gn_instance *instance,
                                         gn_mvs_stall_diagnosis *out);
gn_status gn_private_mvs_failure(const gn_instance *instance,
                                 gn_mvs_failure *out);

#if defined(GLUEYNEO_SDK_TEST_HOOKS)
/* Per-invocation accounting: bytes are conservative charges for admitted
 * schema passes/bulk copies, not elapsed time or retired instructions. */
typedef struct {
    size_t input_bytes;
    size_t stack_staging_bytes;
    size_t heap_staging_bytes;
    size_t staging_bytes;
    size_t byte_work_limit;
    size_t byte_work;
    size_t ym_bytes_read;
    size_t ym_bytes_limit;
    size_t phase_limit;
    size_t phases;
    uint32_t phase_mask;
    uint32_t repeated_phase;
} gn_test_state_resources;
gn_status gn_test_state_resources_read(const gn_instance *instance,
                                       gn_test_state_resources *out);

/* Test assertion helper expands only in test translation units. */
#define STATE_RESOURCE_CHECK(instance) do { \
    gn_test_state_resources resource_check; \
    SDK_CHECK_STATUS("sdk.state.resources.read", GN_STATUS_OK, \
        gn_test_state_resources_read((instance), &resource_check)); \
    SDK_CHECK_TRUE("sdk.state.resources.aggregate-includes-stack", \
        resource_check.stack_staging_bytes > 0u && \
        resource_check.staging_bytes == resource_check.stack_staging_bytes + \
                                        resource_check.heap_staging_bytes); \
    SDK_CHECK_TRUE("sdk.state.resources.byte-work-bounded", \
        resource_check.byte_work <= resource_check.byte_work_limit); \
    SDK_CHECK_TRUE("sdk.state.resources.phase-work-bounded", \
        resource_check.phases <= resource_check.phase_limit && \
        resource_check.repeated_phase == 0u); \
    SDK_CHECK_TRUE("sdk.state.resources.ym-span-work-bounded", \
        resource_check.ym_bytes_read <= resource_check.ym_bytes_limit); \
} while (0)

typedef struct {
    size_t fail_at;
    size_t attempts;
    size_t total_attempts;
    size_t live_allocations;
    size_t live_bytes;
} gn_test_allocator;

typedef struct {
    size_t fail_at;
    size_t attempts;
    size_t allocations;
    size_t frees;
    size_t live_bytes;
    size_t high_water_bytes;
    uint32_t failed_site;
} gn_test_state_failpoint_info;

enum {
    GN_TEST_STATE_BYPASS_Z80_VALIDATOR = 1u,
    GN_TEST_STATE_BYPASS_YM_IRQ_RELATION = 2u
};

#define GN_TEST_TRACE_CAPACITY 256u

typedef enum {
    GN_TEST_BUS_READ = 0,
    GN_TEST_BUS_WRITE = 1
} gn_test_bus_direction;

typedef struct {
    uint32_t address;
    uint16_t value;
    uint8_t width_bits;
    uint8_t direction;
} gn_test_bus_event;

typedef enum {
    GN_TEST_MUTATION_NONE = 0,
    GN_TEST_MUTATION_BSS_READ,
    GN_TEST_MUTATION_RUN_ELAPSED,
    GN_TEST_MUTATION_RUN_INSTRUCTIONS,
    GN_TEST_MUTATION_RUN_STOP_REASON,
    GN_TEST_MUTATION_OBSERVATION_BYTE_ORDER,
    GN_TEST_MUTATION_TRACE_ORDER
} gn_test_mutation;

typedef enum {
    GN_TEST_MVS_FAILURE_NONE = 0,
    GN_TEST_MVS_FAILURE_SOUND_BUS,
    GN_TEST_MVS_FAILURE_SOUND_TICK_LIMIT,
    GN_TEST_MVS_FAILURE_MAIN_OBSERVE,
    GN_TEST_MVS_FAILURE_MAIN_IRQ_UPDATE,
    GN_TEST_MVS_FAILURE_MAIN_EXECUTE,
    GN_TEST_MVS_FAILURE_MAIN_AFTER_INSTRUCTION,
    GN_TEST_MVS_FAILURE_MAIN_AFTER_INSTRUCTION_THEN_SOUND_TICK_LIMIT,
    GN_TEST_MVS_FAILURE_SOUND_BEFORE_MAIN_PROGRESS,
    GN_TEST_MVS_FAILURE_FIRST_ERROR_PRECEDENCE
} gn_test_mvs_failure;

void gn_test_allocator_init(gn_test_allocator *allocator);
void gn_test_allocator_arm(gn_test_allocator *allocator, size_t fail_at);
void gn_test_allocator_disarm(gn_test_allocator *allocator);
gn_status gn_test_state_failpoint_arm(gn_instance *instance, size_t fail_at);
gn_status gn_test_state_failpoint_disarm(gn_instance *instance);
gn_status gn_test_state_failpoint_read(
    const gn_instance *instance, gn_test_state_failpoint_info *out_failpoint);
gn_status gn_test_state_validation_bypass_arm(gn_instance *instance,
                                               uint32_t validator);
gn_status gn_test_create(gn_test_allocator *allocator,
                         gn_instance **out_instance);
gn_status gn_test_validate_region_layout(const gn_manifest *manifest);
gn_status gn_test_sha256(const uint8_t *bytes, size_t length,
                         uint8_t out_digest[32]);
gn_status gn_test_image_digest(const gn_instance *instance, uint64_t *out_digest);
gn_status gn_test_seed_counters(gn_instance *instance, uint64_t instructions,
                                uint64_t instruction_cycles,
                                uint64_t exception_cycles,
                                uint64_t idle_cycles, uint64_t total_cycles);
gn_status gn_test_fail_next_bus_callback(gn_instance *instance);
gn_status gn_test_set_mutation(gn_instance *instance, gn_test_mutation mutation);
gn_status gn_test_mvs_set_failure(gn_instance *instance,
                                  gn_test_mvs_failure failure);
gn_status gn_test_trace_clear(gn_instance *instance);
gn_status gn_test_trace_read(const gn_instance *instance,
                             gn_test_bus_event *events, size_t capacity,
                             size_t *out_count, size_t *out_dropped);
gn_status gn_test_mvs_read_work_ram(const gn_instance *instance,
                                   uint32_t address, uint16_t *out_value);
gn_status gn_test_mvs_read_bus(const gn_instance *instance,
                               uint32_t address, uint16_t *out_value);
gn_status gn_test_mvs_read_bus8(const gn_instance *instance,
                                uint32_t address, uint8_t *out_value);
gn_status gn_test_mvs_write_bus8(gn_instance *instance, uint32_t address,
                                uint8_t value);
gn_status gn_test_mvs_calendar(const gn_instance *instance, gn_mvs_calendar *out);
gn_status gn_test_mvs_system_latch_output3(const gn_instance *instance,
                                           uint8_t *out_value);
gn_status gn_test_mvs_system_latch_output2(const gn_instance *instance,
                                           uint8_t *out_value);
#endif

#endif
