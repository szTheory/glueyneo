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
#define GN_MVS_MANIFEST_VERSION UINT32_C(1)
#define GN_MVS_PROFILE_MSX UINT32_C(0x4d53584d)
#define GN_MVS_MAX_REGIONS 6u
#define GN_MVS_MAX_REGION_BYTES ((size_t)48u * 1024u * 1024u)
#define GN_MVS_MAX_MEDIA_BYTES ((size_t)64u * 1024u * 1024u)
#define GN_MVS_BIOS_BYTES ((size_t)0x80000u)
#define GN_MVS_PROGRAM_BYTES ((size_t)0x500000u)
#define GN_MVS_FIXED_BYTES ((size_t)0x20000u)
#define GN_MVS_AUDIO_PROGRAM_BYTES ((size_t)0x20000u)
#define GN_MVS_SAMPLES_BYTES ((size_t)0xa00000u)
#define GN_MVS_SPRITES_BYTES ((size_t)0x3000000u)
#define GN_MAX_REGIONS 2u
#define GN_MAX_MEDIA_BYTES ((size_t)1024u * (size_t)1024u)
#define GN_MAX_CYCLE_BUDGET UINT64_C(1000000)

typedef struct gn_instance gn_instance;

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
 * byte-addressed, post-transform order. gn_load_mvs copies all data before
 * returning and leaves the current image intact when validation fails. */
typedef enum {
    GN_MVS_REGION_BIOS = 1,
    GN_MVS_REGION_PROGRAM,
    GN_MVS_REGION_FIXED,
    GN_MVS_REGION_AUDIO_PROGRAM,
    GN_MVS_REGION_SAMPLES,
    GN_MVS_REGION_SPRITES
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

typedef struct {
    uint32_t version;
    uint32_t profile;
    size_t region_count;
    gn_mvs_region regions[GN_MVS_MAX_REGIONS];
} gn_mvs_manifest;

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

/* All pointers in a manifest must reference readable caller storage for the
 * duration of gn_load. Successful loads copy every source byte. One instance
 * is single-threaded and non-reentrant; distinct instances may run in parallel.
 * The supported diagnostic maps 512-byte ROM at 0 and 4096-byte RAM at 0x1000.
 * RAM source bytes are an initialization prefix; the remainder is zero-filled. */
GN_API gn_status gn_create(gn_instance **out_instance);
GN_API gn_status gn_load(gn_instance *instance, const gn_manifest *manifest);
GN_API gn_status gn_load_mvs(gn_instance *instance,
                             const gn_mvs_manifest *manifest);
GN_API gn_status gn_reset(gn_instance *instance);
GN_API gn_status gn_run(gn_instance *instance, uint64_t cycle_budget,
                        gn_run_result *out_result);
GN_API gn_status gn_run_mvs(gn_instance *instance, uint64_t cycle_budget,
                            gn_run_result *out_result);
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
GN_API gn_status gn_unload(gn_instance *instance);
GN_API void gn_destroy(gn_instance *instance);
GN_API const char *gn_status_string(gn_status status);

#ifdef __cplusplus
}
#endif

#endif
