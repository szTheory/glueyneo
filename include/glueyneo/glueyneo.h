/* SPDX-License-Identifier: MIT */
#ifndef GLUEYNEO_GLUEYNEO_H
#define GLUEYNEO_GLUEYNEO_H

#include <stddef.h>
#include <stdint.h>

#if defined(_WIN32) && defined(GLUEYNEO_SHARED)
#  if defined(GLUEYNEO_BUILDING)
#    define GN_API __declspec(dllexport)
#  else
#    define GN_API __declspec(dllimport)
#  endif
#elif defined(__GNUC__) || defined(__clang__)
#  define GN_API __attribute__((visibility("default")))
#else
#  define GN_API
#endif

#ifdef __cplusplus
extern "C" {
#endif

#define GN_MANIFEST_VERSION UINT32_C(1)
#define GN_PROFILE_DIAGNOSTIC UINT32_C(1)
#define GN_PROFILE_PUBLIC_FIXTURE UINT32_C(0x50554246)
#define GN_MVS_MANIFEST_VERSION_LEGACY UINT32_C(1)
#define GN_MVS_MANIFEST_VERSION UINT32_C(2)
#define GN_MVS_MANIFEST_VERSION_ZOOM UINT32_C(3)
#define GN_MVS_PROFILE_MSX UINT32_C(0x4d53584d)
#define GN_MVS_INPUT_COIN1 UINT32_C(0x00000001)
#define GN_MVS_INPUT_P1_START UINT32_C(0x00000002)
#define GN_MVS_INPUT_P1_UP UINT32_C(0x00000004)
#define GN_MVS_INPUT_P1_DOWN UINT32_C(0x00000008)
#define GN_MVS_INPUT_P1_LEFT UINT32_C(0x00000010)
#define GN_MVS_INPUT_P1_RIGHT UINT32_C(0x00000020)
#define GN_MVS_INPUT_P1_A UINT32_C(0x00000040)
#define GN_MVS_INPUT_P1_B UINT32_C(0x00000080)
#define GN_MVS_INPUT_P1_C UINT32_C(0x00000100)
#define GN_MVS_INPUT_P1_D UINT32_C(0x00000200)
#define GN_MVS_INPUT_SUPPORTED_MASK \
    (GN_MVS_INPUT_COIN1 | GN_MVS_INPUT_P1_START | GN_MVS_INPUT_P1_UP | \
     GN_MVS_INPUT_P1_DOWN | GN_MVS_INPUT_P1_LEFT | GN_MVS_INPUT_P1_RIGHT | \
     GN_MVS_INPUT_P1_A | GN_MVS_INPUT_P1_B | GN_MVS_INPUT_P1_C | \
     GN_MVS_INPUT_P1_D)
#define GN_MVS_LEGACY_REGIONS 6u
#define GN_MVS_MAX_REGIONS 7u
#define GN_MVS_V3_MAX_REGIONS 8u
#define GN_MVS_MAX_REGION_BYTES ((size_t)48u * 1024u * 1024u)
#define GN_MVS_MAX_MEDIA_BYTES ((size_t)64u * 1024u * 1024u)
#define GN_MVS_BIOS_BYTES ((size_t)0x80000u)
#define GN_MVS_PROGRAM_BYTES ((size_t)0x500000u)
#define GN_MVS_FIXED_BYTES ((size_t)0x20000u)
#define GN_MVS_AUDIO_PROGRAM_BYTES ((size_t)0x20000u)
#define GN_MVS_AUDIO_BIOS_BYTES ((size_t)0x20000u)
#define GN_MVS_Y_ZOOM_BYTES ((size_t)0x20000u)
#define GN_MVS_SAMPLES_BYTES ((size_t)0xa00000u)
#define GN_MVS_SPRITES_BYTES ((size_t)0x3000000u)
#define GN_MAX_REGIONS 2u
#define GN_MAX_MEDIA_BYTES ((size_t)1024u * (size_t)1024u)
#define GN_MAX_CYCLE_BUDGET UINT64_C(1000000)
#define GN_STATE_FORMAT_V1_VERSION UINT32_C(1)
#define GN_STATE_FORMAT_V1_ID UINT32_C(1)
#define GN_STATE_REPLAY_V1_ID UINT32_C(1)
#define GN_STATE_CONFIGURATION_DIAGNOSTIC_V1 UINT32_C(1)
#define GN_STATE_PUBLIC_ABI_V1_ID UINT32_C(1)
#define GN_STATE_HEADER_V1_SIZE ((size_t)72u)
#define GN_STATE_CPU_SECTION_V1_SIZE ((size_t)152u)
#define GN_STATE_RAM_SECTION_V1_SIZE ((size_t)4096u)
#define GN_STATE_MAX_SIZE_V1 \
    (GN_STATE_HEADER_V1_SIZE + (size_t)8u + GN_STATE_CPU_SECTION_V1_SIZE + \
     (size_t)8u + GN_STATE_RAM_SECTION_V1_SIZE)

typedef struct gn_instance gn_instance;

/* State tracer diagnostics are separate from gn_status so their numeric
 * categories can evolve without changing the established status ABI. */
typedef uint32_t gn_state_reason;
enum {
    GN_STATE_REASON_NONE = UINT32_C(0),
    GN_STATE_REASON_INVALID_ARGUMENT = UINT32_C(1),
    GN_STATE_REASON_INVALID_STATE = UINT32_C(2),
    GN_STATE_REASON_UNSUPPORTED_PROFILE = UINT32_C(3),
    GN_STATE_REASON_ACTIVE_CALL = UINT32_C(4),
    GN_STATE_REASON_GUEST_FAULT = UINT32_C(5),
    GN_STATE_REASON_CPU_STATE = UINT32_C(6),
    GN_STATE_REASON_CAPACITY = UINT32_C(7),
    GN_STATE_REASON_TRUNCATED = UINT32_C(8),
    GN_STATE_REASON_TRAILING_BYTES = UINT32_C(9),
    GN_STATE_REASON_FORMAT = UINT32_C(10),
    GN_STATE_REASON_SECTION = UINT32_C(11),
    GN_STATE_REASON_RESERVED = UINT32_C(12),
    GN_STATE_REASON_REPLAY_IDENTITY = UINT32_C(13),
    GN_STATE_REASON_PROFILE_IDENTITY = UINT32_C(14),
    GN_STATE_REASON_CONFIGURATION_IDENTITY = UINT32_C(15),
    GN_STATE_REASON_MEDIA_IDENTITY = UINT32_C(16),
    GN_STATE_REASON_ALIAS = UINT32_C(17)
};
#define GN_STATE_REASON_INSUFFICIENT_CAPACITY GN_STATE_REASON_CAPACITY
#define GN_STATE_REASON_TRAILING_DATA GN_STATE_REASON_TRAILING_BYTES
#define GN_STATE_REASON_UNSUPPORTED_FORMAT GN_STATE_REASON_FORMAT

typedef struct {
    uint32_t size;
    gn_state_reason reason;
    uint32_t section;
    uint32_t field;
    uint32_t offset;
} gn_state_detail_v1;

/* Compatibility identifiers are semantic IDs, not source hashes or an
 * authenticity claim. The media digest identifies normalized immutable input
 * bytes; durable-save identity is supported only by the bounded MVS save API. */
typedef struct {
    uint32_t size;
    uint32_t format_id;
    uint32_t replay_id;
    uint32_t durable_save_id;
    uint32_t public_abi_id;
    uint32_t profile_id;
    uint32_t configuration_id;
    uint8_t media_identity_sha256[32];
} gn_state_compatibility_info_v1;

#define GN_MVS_SAVE_FORMAT_V1_VERSION UINT32_C(1)
#define GN_MVS_SAVE_ID_V1 UINT32_C(1)
#define GN_MVS_SAVE_HEADER_V1_BYTES ((size_t)96u)
#define GN_MVS_SAVE_PAYLOAD_V1_BYTES ((size_t)65536u)
#define GN_MVS_SAVE_ENVELOPE_V1_BYTES \
    (GN_MVS_SAVE_HEADER_V1_BYTES + GN_MVS_SAVE_PAYLOAD_V1_BYTES)

typedef enum {
    GN_MVS_SAVE_REASON_NONE = UINT32_C(0),
    GN_MVS_SAVE_REASON_INVALID_ARGUMENT = UINT32_C(1),
    GN_MVS_SAVE_REASON_INVALID_STATE = UINT32_C(2),
    GN_MVS_SAVE_REASON_UNSUPPORTED_PROFILE = UINT32_C(3),
    GN_MVS_SAVE_REASON_CAPACITY = UINT32_C(4),
    GN_MVS_SAVE_REASON_FORMAT = UINT32_C(5),
    GN_MVS_SAVE_REASON_VERSION = UINT32_C(6),
    GN_MVS_SAVE_REASON_RESERVED = UINT32_C(7),
    GN_MVS_SAVE_REASON_DURABLE_ID = UINT32_C(8),
    GN_MVS_SAVE_REASON_PROFILE = UINT32_C(9),
    GN_MVS_SAVE_REASON_MEDIA_IDENTITY = UINT32_C(10),
    GN_MVS_SAVE_REASON_INTEGRITY = UINT32_C(11),
    GN_MVS_SAVE_REASON_SCOPE = UINT32_C(12),
    GN_MVS_SAVE_REASON_STALE_RECEIPT = UINT32_C(13),
    GN_MVS_SAVE_REASON_RECEIPT_CONSUMED = UINT32_C(14),
    GN_MVS_SAVE_REASON_STARTUP_CLOSED = UINT32_C(15),
    GN_MVS_SAVE_REASON_HOST_WORK_PENDING = UINT32_C(16),
    GN_MVS_SAVE_REASON_COUNTER_EXHAUSTED = UINT32_C(17),
    GN_MVS_SAVE_REASON_SCOPE_REUSED = UINT32_C(18)
} gn_mvs_save_reason;

typedef struct {
    uint32_t size;
    uint32_t reserved;
    uint8_t scope[16];
} gn_mvs_save_scope_v1;

typedef struct {
    uint32_t size;
    uint32_t reserved;
    uint8_t scope[16];
    uint64_t load_generation;
    uint64_t restore_branch;
    uint64_t mutation_sequence;
    uint64_t export_sequence;
} gn_mvs_save_receipt_v1;

typedef struct {
    uint32_t size;
    uint32_t supported;
    uint32_t save_id;
    uint32_t profile_id;
    uint8_t media_identity_sha256[32];
    uint32_t envelope_bytes;
    uint8_t dirty;
    uint8_t baseline_known;
    uint8_t scope_valid;
    uint8_t exhausted;
    uint8_t startup_import_allowed;
    uint8_t reserved[3];
} gn_mvs_save_info_v1;

typedef struct {
    uint32_t size;
    gn_mvs_save_reason reason;
    uint32_t field;
    uint32_t offset;
} gn_mvs_save_detail_v1;

typedef enum {
    GN_MVS_SAVE_LIFECYCLE_REQUIRE_RESOLVED = UINT32_C(1),
    GN_MVS_SAVE_LIFECYCLE_ALLOW_DISCARD = UINT32_C(2)
} gn_mvs_save_lifecycle_policy_v1;

typedef struct {
    uint32_t size;
    uint32_t discarded_pending;
} gn_mvs_save_lifecycle_result_v1;

typedef enum {
    GN_STATUS_OK = 0,
    GN_STATUS_INVALID_ARGUMENT,
    GN_STATUS_INVALID_STATE,
    GN_STATUS_INVALID_MEDIA,
    GN_STATUS_UNSUPPORTED_PROFILE,
    GN_STATUS_OUT_OF_MEMORY,
    GN_STATUS_CPU_FAILURE
} gn_status;

typedef enum {
    GN_REGION_ROM = 1,
    GN_REGION_RAM = 2
} gn_region_kind;

typedef struct {
    uint32_t guest_base;
    uint32_t mapped_size;
    const uint8_t *source;
    size_t source_size;
    gn_region_kind kind;
} gn_region;

typedef struct {
    uint32_t version;
    uint32_t profile;
    size_t region_count;
    gn_region regions[GN_MAX_REGIONS];
} gn_manifest;

/* Versioned MVS media contract. Region bytes are immutable ROM data in
 * byte-addressed, post-transform order. gn_load_mvs copies v1/v2 data before
 * returning and keeps that manifest layout stable; GNMV v3 uses the additive
 * gn_mvs_manifest_v3/gn_load_mvs_v3 path. Failed validation leaves the current
 * image intact. */
typedef enum {
    GN_MVS_REGION_BIOS = 1,
    GN_MVS_REGION_PROGRAM,
    GN_MVS_REGION_FIXED,
    GN_MVS_REGION_AUDIO_PROGRAM,
    GN_MVS_REGION_SAMPLES,
    GN_MVS_REGION_SPRITES,
    GN_MVS_REGION_AUDIO_BIOS,
    GN_MVS_REGION_Y_ZOOM
} gn_mvs_region_role;

typedef enum {
    GN_MVS_LAYOUT_LINEAR = 0,
    GN_MVS_LAYOUT_WORD_SWAP = 1
} gn_mvs_layout;

typedef struct {
    gn_mvs_region_role role;
    const uint8_t *source;
    size_t source_size;
    size_t mapped_size;
    gn_mvs_layout layout;
} gn_mvs_region;

#define GN_MVS_BUS_FAULT_OBSERVATION_VERSION UINT32_C(14)
typedef enum {
    GN_MVS_BUS_ACCESS_READ = 1,
    GN_MVS_BUS_ACCESS_WRITE = 2
} gn_mvs_bus_access;

typedef struct {
    uint32_t version;
    uint32_t address;
    gn_mvs_bus_access access;
    uint8_t width;
    uint8_t valid;
    uint32_t mame_unmapped_write_count;
    uint32_t mame_watchdog_pet_count;
    uint32_t mame_watchdog_reset_count;
    uint16_t video_ram_offset;
    uint8_t video_auto_animation_speed;
    uint8_t video_auto_animation_disabled;
    uint8_t display_position_interrupt_control;
    uint8_t mvs_output_data;
    uint8_t mvs_output_latch;
    uint8_t mvs_cart_audio_selected;
    uint8_t mvs_coin_lockout_mask;
    uint8_t mvs_save_ram_unlocked;
    uint8_t mvs_palette_bank_selected;
    uint16_t video_ram_modulo;
} gn_mvs_bus_fault_observation;

#define GN_MVS_PROGRESS_OBSERVATION_VERSION UINT32_C(1)
typedef struct {
    size_t size;
    uint32_t version;
    uint8_t attract_start_reached;
    uint8_t user_request;
    uint8_t player_start_entered;
    uint8_t player_start_with_p1_indication;
} gn_mvs_progress_observation;

typedef struct {
    uint32_t version;
    uint32_t profile;
    size_t region_count;
    gn_mvs_region regions[GN_MVS_MAX_REGIONS];
} gn_mvs_manifest;

/* GNMV v3 is additive: its separate type preserves the v1/v2 manifest ABI. */
typedef struct {
    uint32_t version;
    uint32_t profile;
    size_t region_count;
    gn_mvs_region regions[GN_MVS_V3_MAX_REGIONS];
} gn_mvs_manifest_v3;

typedef enum {
    GN_RUN_BUDGET = 0,
    GN_RUN_STOPPED,
    GN_RUN_FAULT,
    GN_RUN_ERROR
} gn_run_reason;

typedef struct {
    uint64_t requested_cycles;
    uint64_t elapsed_cycles;
    uint64_t overshoot_cycles;
    uint64_t instructions;
    gn_run_reason reason;
    uint32_t boundary_pc;
    uint32_t fault_pc;
    uint16_t instruction_register;
} gn_run_result;

typedef struct {
    uint32_t arithmetic_result;
    uint32_t initialized_result;
    uint32_t bss_result;
    uint8_t ready;
} gn_observations;

typedef enum {
    GN_PIXEL_XRGB8888 = 1
} gn_pixel_format;

typedef enum {
    GN_AUDIO_S16_INTERLEAVED_STEREO = 1
} gn_audio_format;

#define GN_INPUT_RIGHT UINT32_C(1)
#define GN_INPUT_LEFT UINT32_C(2)
#define GN_INPUT_SUPPORTED_MASK (GN_INPUT_RIGHT | GN_INPUT_LEFT)

typedef struct {
    uint32_t input_mask;
    gn_pixel_format pixel_format;
    uint32_t width;
    uint32_t height;
    size_t pitch_bytes;
    uint8_t *pixels;
    size_t pixel_capacity_bytes;
    int16_t *audio;
    size_t audio_capacity_frames;
} gn_frame_request;

typedef struct {
    uint64_t requested_cycles;
    uint64_t elapsed_cycles;
    uint64_t instructions;
    uint64_t frame_time_numerator;
    uint64_t frame_time_denominator;
    uint32_t machine_clock_hz_numerator;
    uint32_t machine_clock_hz_denominator;
    gn_audio_format audio_format;
    uint32_t audio_sample_rate;
    uint32_t audio_channels;
    size_t audio_frames_produced;
    size_t video_pixels_produced;
    uint32_t marker_x;
    uint32_t marker_y;
    gn_run_reason reason;
} gn_frame_result;

/* Additive native MVS PCM contract. These separate v1 request/result layouts
 * leave gn_frame_request and gn_frame_result unchanged. The request and result
 * sizes passed to gn_mvs_advance_frame_v1 must equal their v1 structure sizes. */
#define GN_MVS_FRAME_REQUEST_V1_VERSION UINT32_C(1)
#define GN_MVS_FRAME_RESULT_V1_VERSION UINT32_C(1)
#define GN_MVS_AUDIO_CAPACITY_FRAMES_V1 ((size_t)812u)
typedef struct {
    uint32_t version;
    uint32_t input_mask;
    gn_pixel_format pixel_format;
    uint32_t width;
    uint32_t height;
    size_t pitch_bytes;
    uint8_t *pixels;
    size_t pixel_capacity_bytes;
    int16_t *audio;
    size_t audio_capacity_frames;
} gn_mvs_frame_request_v1;

typedef struct {
    uint32_t version;
    uint64_t requested_cycles;
    uint64_t elapsed_cycles;
    uint64_t instructions;
    uint64_t frame_time_numerator;
    uint64_t frame_time_denominator;
    uint32_t machine_clock_hz_numerator;
    uint32_t machine_clock_hz_denominator;
    gn_run_reason reason;
    gn_audio_format audio_format;
    uint32_t audio_sample_rate;
    uint32_t audio_channels;
    size_t audio_frames_generated;
    size_t audio_frames_discarded;
    size_t audio_frames_delivered;
    size_t video_pixels_produced;
} gn_mvs_frame_result_v1;

/* All pointers in a manifest must reference readable caller storage for the
 * duration of gn_load. Successful loads copy every source byte. One instance
 * is single-threaded and non-reentrant; distinct instances may run in parallel.
 * The supported diagnostic maps 512-byte ROM at 0 and 4096-byte RAM at 0x1000.
 * RAM source bytes are an initialization prefix; the remainder is zero-filled. */
GN_API gn_status gn_create(gn_instance **out_instance);
GN_API gn_status gn_load(gn_instance *instance, const gn_manifest *manifest);
GN_API gn_status gn_load_mvs(gn_instance *instance,
                             const gn_mvs_manifest *manifest);
GN_API gn_status gn_load_mvs_v3(gn_instance *instance,
                                const gn_mvs_manifest_v3 *manifest);
GN_API gn_status gn_reset(gn_instance *instance);
GN_API gn_status gn_run(gn_instance *instance, uint64_t cycle_budget,
                        gn_run_result *out_result);
/* Native continuation state v1 for the supported diagnostic and source-bound
 * MVS profiles. Capacity stays stable for the loaded image lifetime and does
 * not depend on guest progress. Diagnostic capacity is GN_STATE_MAX_SIZE_V1;
 * MVS capacity is derived from its loaded memory extents and checked CPU/YM
 * state sizes. Capture writes exactly *out_written bytes and leaves the
 * remaining caller buffer untouched. On a failed capture, a non-aliased valid
 * out_written pointer is set to zero. The size_t count/capacity pointers and
 * sized records must have their natural alignment. detail may be NULL only
 * when detail_size is zero; otherwise detail_size must equal sizeof the v1
 * record. For compatibility output, info_size must equal sizeof the v1 record.
 *
 * All non-NULL pointers must refer to readable/writable host storage of their
 * advertised lengths for the complete call. Input/output records and payloads
 * must not overlap each other or live instance storage. Known live-owned ranges
 * are checked with overflow-safe arithmetic; arbitrary or dangling pointers
 * cannot be validated. Insufficient capture capacity is rejected before any
 * payload byte is changed. Restore consumes the bytes during the call and
 * retains no caller buffer. Capture/restore never execute the guest, perform
 * I/O, or consult host time. This is continuation state for the currently
 * supported source-derived profiles, not a durable backup-RAM save or a
 * general-purpose MVS game snapshot. */
GN_API gn_status gn_state_capacity_v1(const gn_instance *instance,
                                      size_t *out_capacity);
GN_API gn_status gn_state_capture_v1(gn_instance *instance, void *buffer,
                                     size_t capacity, size_t *out_written,
                                     gn_state_detail_v1 *detail,
                                     size_t detail_size);
GN_API gn_status gn_state_restore_v1(gn_instance *instance, const void *bytes,
                                     size_t length,
                                     gn_state_detail_v1 *detail,
                                     size_t detail_size);
GN_API gn_status gn_state_compatibility_v1(
    const gn_instance *instance, gn_state_compatibility_info_v1 *out_info,
    size_t info_size);
GN_API const char *gn_state_reason_string(gn_state_reason reason);
/* Durable MVS backup-RAM transfer. The caller owns all buffers and the core
 * performs no filesystem, device, network, or clock I/O. Scope values must be
 * nonzero and never reused by the host for another instance lifetime. Export
 * writes one exact GNSV v1 envelope and issues the latest receipt only after
 * all validation succeeds. ACK only after the host's complete commit protocol.
 * Baseline imports are authoritative startup operations and may be repeated
 * before the first guest instruction, while no guest or host work is pending.
 * The checked lifecycle calls take the host's resolution attestation; the core
 * cannot inspect host storage. Both policies require host_work_resolved=1;
 * REQUIRE_RESOLVED also refuses pending core SRAM. ALLOW_DISCARD drops pending
 * core SRAM only after a checked
 * replacement succeeds; discarded_pending reports that loss and makes no
 * durable-completion claim. */
GN_API gn_status gn_mvs_save_query_v1(
    const gn_instance *instance, gn_mvs_save_info_v1 *out_info,
    size_t info_size, gn_mvs_save_detail_v1 *detail, size_t detail_size);
GN_API gn_status gn_mvs_save_export_v1(
    gn_instance *instance, void *buffer, size_t capacity, size_t *out_written,
    gn_mvs_save_receipt_v1 *out_receipt, size_t receipt_size,
    gn_mvs_save_detail_v1 *detail, size_t detail_size);
GN_API gn_status gn_mvs_save_import_baseline_v1(
    gn_instance *instance, const void *bytes, size_t length,
    gn_mvs_save_detail_v1 *detail, size_t detail_size);
GN_API gn_status gn_mvs_save_ack_v1(
    gn_instance *instance, const gn_mvs_save_receipt_v1 *receipt,
    size_t receipt_size, gn_mvs_save_detail_v1 *detail, size_t detail_size);
GN_API gn_status gn_mvs_save_scope_renew_v1(
    gn_instance *instance, const gn_mvs_save_scope_v1 *scope,
    size_t scope_size, gn_mvs_save_detail_v1 *detail, size_t detail_size);
GN_API const char *gn_mvs_save_reason_string(gn_mvs_save_reason reason);
GN_API gn_status gn_load_mvs_v3_checked_v1(
    gn_instance *instance, const gn_mvs_manifest_v3 *manifest,
    gn_mvs_save_lifecycle_policy_v1 policy, uint32_t host_work_resolved,
    gn_mvs_save_lifecycle_result_v1 *out_result, size_t result_size,
    gn_mvs_save_detail_v1 *detail, size_t detail_size);
GN_API gn_status gn_unload_checked_v1(
    gn_instance *instance, gn_mvs_save_lifecycle_policy_v1 policy,
    uint32_t host_work_resolved,
    gn_mvs_save_lifecycle_result_v1 *out_result, size_t result_size,
    gn_mvs_save_detail_v1 *detail, size_t detail_size);
GN_API gn_status gn_destroy_checked_v1(
    gn_instance **inout_instance, gn_mvs_save_lifecycle_policy_v1 policy,
    uint32_t host_work_resolved,
    gn_mvs_save_lifecycle_result_v1 *out_result, size_t result_size,
    gn_mvs_save_detail_v1 *detail, size_t detail_size);
GN_API gn_status gn_run_mvs(gn_instance *instance, uint64_t cycle_budget,
                            gn_run_result *out_result);
/* MVS inputs belong to one instance, remain held until changed and clear on
 * successful MVS load or gn_reset. Coin1 and P1 Start keep their original bit
 * values; P1 direction and A-D bits are additive. All eight P1 lines are
 * active-low at the $300000 control byte (UP/DOWN/LEFT/RIGHT/A/B/C/D bits
 * 0-7). A diagnostic-profile image does not accept MVS inputs. */
GN_API gn_status gn_set_mvs_inputs(gn_instance *instance, uint32_t input_mask);
/* Reports only guest-observed protocol events. The caller owns the output
 * buffer; buffers shorter than the stable prefix through
 * player_start_with_p1_indication are rejected, and no more than out_observation_size
 * bytes are written. A response requires a guest fetch at PLAYER_START after
 * attract and ordered host coin/start edges, with a fresh BIOS-written P1
 * BIOS_START_FLAG indication after Start. This source-semantic observation
 * excludes an unindicated title timeout; it does not qualify selected media
 * or physical-board behavior. */
GN_API gn_status gn_observe_mvs_progress(
    const gn_instance *instance, gn_mvs_progress_observation *out_observation,
    size_t out_observation_size);
/* out_observation_size must describe the caller's writable buffer. The function
 * rejects buffers smaller than the stable prefix ending at `valid`, and writes
 * no more than the supplied size so older prefix-sized callers remain safe. */
GN_API gn_status gn_observe_mvs_bus_fault(
    const gn_instance *instance, gn_mvs_bus_fault_observation *out_observation,
    size_t out_observation_size);
GN_API gn_status gn_observe(const gn_instance *instance,
                            gn_observations *out_observations);
/* A public-fixture frame samples input_mask once at entry. RIGHT advances x;
 * LEFT is accepted but has no effect in this guest. The only supported video
 * request is 320x224 XRGB8888 (native-endian uint32_t 0x00RRGGBB). pitch_bytes
 * is bytes between rows and pixel_capacity_bytes must cover
 * (height - 1) * pitch_bytes + width * 4, checked before guest execution.
 * The pixel buffer must be non-null. Audio is fixed signed-16 interleaved
 * stereo at 48 kHz and produces zero frames; audio==NULL is valid only when
 * audio_capacity_frames is zero. Any non-null audio buffer is left untouched.
 * A successful frame advances exactly 200000 nominal machine cycles at 12 MHz.
 * frame_time_numerator / frame_time_denominator reports consumed cycles over
 * 12,000,000, so partial failure progress remains exact without rounding
 * drift; a complete frame is 200000/12000000 seconds (1/60). This is a fixture
 * contract, not qualified Neo Geo timing. The
 * fixture CPU restarts at its BIOS-free reset vector per frame while guest
 * RAM persists. Invalid requests fail before guest mutation. Once execution
 * begins, errors report consumed cycles and produced counts; retry starts at
 * the reset vector and retains any guest RAM writes already completed. Caller
 * buffers remain owned by the caller and are accessed only until return. One
 * instance is single-threaded and non-reentrant. */
GN_API gn_status gn_advance_frame(gn_instance *instance,
                                  const gn_frame_request *request,
                                  gn_frame_result *out_result);
/* Advances one logical MVS frame and returns caller-owned signed-16 interleaved
 * stereo PCM at 48 kHz. The native frame is 320x224 XRGB8888. Audio may be
 * discarded with audio == NULL and capacity == 0; the emulated YM2610 and
 * converter still advance. A non-null audio buffer must be naturally aligned
 * for int16_t and advertise at least the side-effect-free v1 capacity. Invalid
 * sizes, version, input, geometry, capacity, alignment, or aliased buffers are
 * rejected before guest input or emulation state changes and leave out_result
 * untouched. audio_frames_generated counts converter outputs during this call;
 * audio_frames_delivered counts frames written to audio; audio_frames_discarded
 * is the generated prefix that was not delivered. A NULL audio buffer delivers
 * zero frames and retains no pending queue. Runtime errors report actual CPU
 * progress and any valid PCM prefix already written. Reset and successful load
 * start a fresh converter history; unload releases it. This native source-derived
 * path does not claim private-game playback, device output, or silicon equivalence. */
GN_API gn_status gn_mvs_audio_capacity_v1(const gn_instance *instance,
                                         size_t *out_capacity_frames);
GN_API gn_status gn_mvs_advance_frame_v1(
    gn_instance *instance, const gn_mvs_frame_request_v1 *request,
    size_t request_size, gn_mvs_frame_result_v1 *out_result,
    size_t result_size);
GN_API gn_status gn_unload(gn_instance *instance);
GN_API void gn_destroy(gn_instance *instance);
GN_API const char *gn_status_string(gn_status status);

#ifdef __cplusplus
}
#endif

#endif
