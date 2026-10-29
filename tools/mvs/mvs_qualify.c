/* SPDX-License-Identifier: MIT */
#if !defined(_WIN32) && !defined(_POSIX_C_SOURCE)
#define _POSIX_C_SOURCE 200809L
#endif

#include "glueyneo/glueyneo.h"
#include "../../src/sdk_private.h"

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#if defined(_WIN32)
#include <windows.h>
#else
#include <sys/stat.h>
#endif

#define HEADER_BYTES 16u
#define REGION_HEADER_BYTES 12u
#define MAX_BUNDLE_BYTES (GN_MVS_MAX_MEDIA_BYTES + HEADER_BYTES + \
                          GN_MVS_V3_MAX_REGIONS * REGION_HEADER_BYTES)
#define MAX_RUN_CHUNKS 256u
#define MAX_INPUT_SCRIPT_FRAMES 1200u
#define SCRIPTED_COIN_HOLD_FRAMES 8u
#define MAX_ACTIVE_INPUT_EVENTS 64u
#define MAX_ACTIVE_FRAMES 3600u
#define MAX_CAPTURE_FRAMES 6u
#define MAX_ACTIVE_SCHEDULE_BYTES 4096u
#define MAX_SOUND_WINDOWS 4u
#define MAX_SOUND_WINDOW_FRAMES 120u
#define MAX_SOUND_WINDOW_NAME_BYTES 16u
#define MAX_VIDEO_ADVANCE_FRAMES UINT32_C(600)

typedef struct {
    uint32_t coin_frame;
    uint32_t start_frame;
} input_script;

typedef struct {
    uint32_t frame;
    uint32_t mask;
} active_input_event;

typedef struct {
    uint32_t frame;
    uint8_t chip_reset;
    uint64_t chip_clocks;
    uint64_t fm_key_on_writes;
    uint64_t fm_key_off_writes;
    uint64_t fm_register_writes;
    uint64_t ssg_register_writes;
    uint64_t ssg_volume_writes;
    uint64_t adpcm_a_register_writes;
    uint64_t adpcm_a_control_writes;
    uint64_t adpcm_a_reads;
    uint64_t adpcm_b_register_writes;
    uint64_t adpcm_b_control_writes;
    uint64_t adpcm_b_reads;
    uint64_t native_nonzero_frames;
} active_sound_chip_frame;

typedef struct {
    char name[MAX_SOUND_WINDOW_NAME_BYTES];
    uint32_t first_frame;
    uint32_t last_frame;
    uint32_t completed_frames;
    uint32_t input_masks[MAX_SOUND_WINDOW_FRAMES];
    uint64_t elapsed_cycles[MAX_SOUND_WINDOW_FRAMES];
    uint32_t audio_frames[MAX_SOUND_WINDOW_FRAMES];
    active_sound_chip_frame chip_frames[MAX_SOUND_WINDOW_FRAMES];
    gn_mvs_sound_chip_observation previous_chip_observation;
    uint64_t actual_cycles;
    uint64_t audio_frames_generated;
    uint64_t audio_frames_delivered;
    uint64_t audio_frames_discarded;
    uint64_t pcm_bytes;
    gn_mvs_sound_chip_observation chip_observation;
    gn_mvs_sound_board_observation board_observations[MAX_SOUND_WINDOW_FRAMES];
    FILE *pcm_file;
} active_sound_window;

typedef struct {
    uint32_t active_frames;
    size_t input_count;
    active_input_event inputs[MAX_ACTIVE_INPUT_EVENTS];
    size_t capture_count;
    uint32_t captures[MAX_CAPTURE_FRAMES];
    const char *capture_directory;
    size_t sound_window_count;
    active_sound_window sound_windows[MAX_SOUND_WINDOWS];
} active_schedule;

static void print_diagnosis(const gn_instance *instance);
static int active_sound_window_open(const active_schedule *schedule,
                                    active_sound_window *window);
static int active_sound_window_write(active_sound_window *window,
                                     const int16_t *samples, size_t frames);
static int active_sound_windows_close(active_schedule *schedule);
static int active_sound_window_contains(const active_sound_window *window,
                                        uint32_t frame);
static int active_sound_chip_frame_capture(
    active_sound_window *window, uint32_t frame,
    const gn_mvs_sound_chip_observation *chip);
static void print_active_sound_windows(const active_schedule *schedule);

typedef struct {
    uint32_t chunks;
    uint32_t stable_chunks;
    uint32_t output_transition_chunks;
    uint32_t video_transition_chunks;
    uint32_t bank_transition_chunks;
    uint32_t watchdog_pet_count;
    uint32_t watchdog_reset_count;
    uint8_t repeated_boundary_suffix;
} local_profile;

static int same_output_state(const gn_mvs_bus_fault_observation *left,
                             const gn_mvs_bus_fault_observation *right) {
    return left->mvs_output_data == right->mvs_output_data &&
           left->mvs_output_latch == right->mvs_output_latch &&
           left->mvs_cart_audio_selected == right->mvs_cart_audio_selected &&
           left->mvs_coin_lockout_mask == right->mvs_coin_lockout_mask &&
           left->mvs_save_ram_unlocked == right->mvs_save_ram_unlocked;
}

static int same_video_state(const gn_mvs_bus_fault_observation *left,
                            const gn_mvs_bus_fault_observation *right) {
    return left->video_ram_offset == right->video_ram_offset &&
           left->video_ram_modulo == right->video_ram_modulo &&
           left->video_auto_animation_speed == right->video_auto_animation_speed &&
           left->video_auto_animation_disabled == right->video_auto_animation_disabled &&
           left->display_position_interrupt_control ==
               right->display_position_interrupt_control;
}

static int same_bank_state(const gn_mvs_bus_fault_observation *left,
                           const gn_mvs_bus_fault_observation *right) {
    return left->mvs_palette_bank_selected == right->mvs_palette_bank_selected;
}

static void count_state_transition(local_profile *profile,
                                   const gn_mvs_bus_fault_observation *previous,
                                   const gn_mvs_bus_fault_observation *current) {
    int changed = 0;
    if (!same_output_state(previous, current)) {
        ++profile->output_transition_chunks;
        changed = 1;
    }
    if (!same_video_state(previous, current)) {
        ++profile->video_transition_chunks;
        changed = 1;
    }
    if (!same_bank_state(previous, current)) {
        ++profile->bank_transition_chunks;
        changed = 1;
    }
    if (!changed) ++profile->stable_chunks;
}

static int repeated_boundary_suffix(const uint32_t *boundaries, size_t count) {
    const size_t max_period = count / 2u < 8u ? count / 2u : 8u;
    for (size_t period = 1u; period <= max_period; ++period) {
        int matches = 1;
        for (size_t index = 0u; index < period; ++index) {
            if (boundaries[count - period + index] !=
                boundaries[count - 2u * period + index]) {
                matches = 0;
                break;
            }
        }
        if (matches) return 1;
    }
    return 0;
}

/* Print the attract_start result when the documented BIOS-to-cartridge protocol
 * transition (docs/mvs-media.md "Attract/start predicate") has been observed.
 * The checkpoint carries only the public request name, the chunk number and
 * whether the optional BIOS_USER_MODE corroboration was seen; it never names a
 * title, a program address or any program byte. */
static void print_attract_start(unsigned chunk,
                                const gn_mvs_attract_verdict *verdict,
                                uint32_t video_advance_frames,
                                uint32_t video_advance_completed,
                                int frame_output_written) {
    printf("{\"status\":\"attract_start\",\"guest_executed\":true,"
           "\"checkpoint\":{\"user_request\":\"%s\",\"chunk\":%u,"
           "\"user_mode_corroborated\":%s}",
           verdict->user_request == GN_MVS_REQUEST_TITLE ? "title" : "demo", chunk,
           verdict->user_mode_corroborated != 0u ? "true" : "false");
    if (video_advance_frames != 0u)
        printf(",\"video_advance_frames\":%u,\"video_advance_requested\":%u,"
               "\"video_advance_completed\":%u",
               video_advance_frames, video_advance_frames,
               video_advance_completed);
    if (frame_output_written != 0)
        printf(",\"frame_output_written\":true");
    puts("}");
}

static int get_attract_start(const gn_instance *instance,
                             gn_mvs_attract_verdict *out_verdict) {
    return gn_private_mvs_attract_verdict(instance, out_verdict) == GN_STATUS_OK &&
           out_verdict->accepted != 0u;
}

static int valid_frame_output_path(const char *path) {
    static const char prefix[] = "local/qualification/phase05-";
    static const char suffix[] = ".ppm";
    if (path == NULL) return 1;
    const size_t prefix_size = sizeof(prefix) - 1u;
    const size_t suffix_size = sizeof(suffix) - 1u;
    const size_t length = strlen(path);
    if (length != prefix_size + (size_t)32u + suffix_size ||
        memcmp(path, prefix, prefix_size) != 0 ||
        memcmp(path + prefix_size + (size_t)32u, suffix, suffix_size) != 0)
        return 0;
    for (size_t index = prefix_size; index < prefix_size + (size_t)32u;
         ++index) {
        const char value = path[index];
        if (!((value >= '0' && value <= '9') ||
              (value >= 'a' && value <= 'f'))) return 0;
    }
#if defined(_WIN32)
    const DWORD local_attributes = GetFileAttributesA("local");
    const DWORD qualification_attributes =
        GetFileAttributesA("local\\qualification");
    if (local_attributes == INVALID_FILE_ATTRIBUTES ||
        qualification_attributes == INVALID_FILE_ATTRIBUTES ||
        (local_attributes & FILE_ATTRIBUTE_DIRECTORY) == 0u ||
        (qualification_attributes & FILE_ATTRIBUTE_DIRECTORY) == 0u ||
        (local_attributes & FILE_ATTRIBUTE_REPARSE_POINT) != 0u ||
        (qualification_attributes & FILE_ATTRIBUTE_REPARSE_POINT) != 0u)
        return 0;
#else
    struct stat local_status;
    struct stat qualification_status;
    if (lstat("local", &local_status) != 0 ||
        lstat("local/qualification", &qualification_status) != 0 ||
        !S_ISDIR(local_status.st_mode) || S_ISLNK(local_status.st_mode) ||
        !S_ISDIR(qualification_status.st_mode) ||
        S_ISLNK(qualification_status.st_mode)) return 0;
#endif
    return 1;
}

static int valid_active_capture_directory(const char *path) {
    static const char prefix06[] = "local/qualification/phase06/run-";
    static const char prefix07[] = "local/qualification/phase07/run-";
    const char *prefix = NULL;
    size_t prefix_size = 0u;
    const size_t length = path == NULL ? 0u : strlen(path);
    if (path != NULL && length == sizeof(prefix06) - 1u + 32u &&
        memcmp(path, prefix06, sizeof(prefix06) - 1u) == 0) {
        prefix = prefix06;
        prefix_size = sizeof(prefix06) - 1u;
    } else if (path != NULL && length == sizeof(prefix07) - 1u + 32u &&
               memcmp(path, prefix07, sizeof(prefix07) - 1u) == 0) {
        prefix = prefix07;
        prefix_size = sizeof(prefix07) - 1u;
    }
    if (prefix == NULL) return 0;
    const char *phase_directory = prefix == prefix06
        ? "local\\qualification\\phase06" : "local\\qualification\\phase07";
#if !defined(_WIN32)
    phase_directory = prefix == prefix06
        ? "local/qualification/phase06" : "local/qualification/phase07";
#endif
    for (size_t index = prefix_size; index < prefix_size + 32u; ++index) {
        const char value = path[index];
        if (!((value >= '0' && value <= '9') ||
              (value >= 'a' && value <= 'f'))) return 0;
    }
#if defined(_WIN32)
    const char *components[] = {
        "local", "local\\qualification", phase_directory,
        path
    };
    for (size_t index = 0u; index < sizeof(components) / sizeof(components[0]);
         ++index) {
        const DWORD attributes = GetFileAttributesA(components[index]);
        if (attributes == INVALID_FILE_ATTRIBUTES ||
            (attributes & FILE_ATTRIBUTE_DIRECTORY) == 0u ||
            (attributes & FILE_ATTRIBUTE_REPARSE_POINT) != 0u) return 0;
    }
#else
    struct stat status;
    const char *components[] = {
        "local", "local/qualification", phase_directory, path
    };
    for (size_t index = 0u; index < sizeof(components) / sizeof(components[0]);
         ++index) {
        if (lstat(components[index], &status) != 0 ||
            !S_ISDIR(status.st_mode) || S_ISLNK(status.st_mode)) return 0;
    }
#endif
    return 1;
}

static int valid_active_capture_path(const char *path) {
    static const char marker[] = "/frame-";
    static const char suffix[] = ".ppm";
    if (path == NULL) return 0;
    const size_t length = strlen(path);
    const char *frame_marker = strstr(path, marker);
    if (frame_marker == NULL || length != (size_t)(frame_marker - path) +
                                          sizeof(marker) - 1u + 4u +
                                          sizeof(suffix) - 1u ||
        memcmp(path + length - (sizeof(suffix) - 1u), suffix,
               sizeof(suffix) - 1u) != 0) return 0;
    for (size_t index = 1u; index <= 4u; ++index) {
        if (frame_marker[sizeof(marker) - 2u + index] < '0' ||
            frame_marker[sizeof(marker) - 2u + index] > '9') return 0;
    }
    char directory[sizeof("local/qualification/phase07/run-") + 32u];
    const size_t directory_length = (size_t)(frame_marker - path);
    if (directory_length >= sizeof(directory)) return 0;
    memcpy(directory, path, directory_length);
    directory[directory_length] = '\0';
    return valid_active_capture_directory(directory);
}

static int write_private_ppm(const char *path, const uint32_t *pixels,
                             size_t pixel_count) {
    if (path == NULL) return 1;
    static const char header[] = "P6\n320 224\n255\n";
    if (pixel_count != (size_t)320u * (size_t)224u ||
        (!valid_frame_output_path(path) &&
         !valid_active_capture_path(path))) return 0;
    FILE *file = fopen(path, "wbx");
    if (file == NULL) return 0;
    int ok = fwrite(header, 1u, sizeof(header) - 1u, file) ==
             sizeof(header) - 1u;
    uint8_t row[(size_t)320u * (size_t)3u];
    for (size_t y = 0u; ok != 0 && y < (size_t)224u; ++y) {
        for (size_t x = 0u; x < (size_t)320u; ++x) {
            const uint32_t color = pixels[y * (size_t)320u + x];
            row[x * 3u] = (uint8_t)(color >> 16);
            row[x * 3u + 1u] = (uint8_t)(color >> 8);
            row[x * 3u + 2u] = (uint8_t)color;
        }
        ok = fwrite(row, 1u, sizeof(row), file) == sizeof(row);
    }
    if (fclose(file) != 0) ok = 0;
    return ok;
}

static int render_local_frame(const gn_instance *instance,
                              const char *frame_output_path) {
    /* The attract checkpoint is a CPU/protocol result. Optional rendering can
     * fail on an unimplemented video feature, but a caller that requested no
     * pixels must not have that unrelated failure replace the checkpoint. */
    if (frame_output_path == NULL) return 1;
    const size_t pixel_count = (size_t)320u * (size_t)224u;
    uint32_t *pixels = (uint32_t *)malloc(pixel_count * sizeof(*pixels));
    if (pixels == NULL) return 0;
    size_t produced = 0u;
    const gn_status status = gn_private_mvs_render_frame(
        instance, 320u, 224u, (size_t)320u * sizeof(*pixels),
        (uint8_t *)pixels, pixel_count * sizeof(*pixels), &produced);
    const int rendered = status == GN_STATUS_OK && produced == pixel_count &&
        write_private_ppm(frame_output_path, pixels, produced);
    free(pixels);
    return rendered;
}

#if !defined(GN_MVS_QUALIFY_NO_MAIN)
static void print_private_video_activity(const gn_instance *instance) {
    gn_mvs_private_video_activity activity;
    if (gn_private_mvs_video_activity(instance, &activity) != GN_STATUS_OK) {
        fputs("{\"private_video_activity\":\"unavailable\"}\n", stderr);
        return;
    }
    fprintf(stderr,
            "{\"private_video_activity\":{\"nonzero_vram_words\":%u,"
            "\"fixed_tilemap_words\":%u,\"sprite_words\":%u,"
            "\"palette_entries\":%u,\"visible_sprites\":%u,"
            "\"visible_nonfull_y_zoom_samples\":%u,\"frame_count\":%u,"
            "\"backdrop_palette_nonzero\":%u,\"video_ram_offset\":%u,"
            "\"video_ram_modulo\":%u,\"palette_bank_selected\":%u,"
            "\"screen_shadow\":%u,\"video_auto_animation_speed\":%u,"
            "\"video_auto_animation_disabled\":%u,"
            "\"display_position_interrupt_control\":%u}}\n",
            (unsigned)activity.nonzero_vram_words,
            (unsigned)activity.nonzero_fixed_tilemap_words,
            (unsigned)activity.nonzero_sprite_words,
            (unsigned)activity.nonzero_palette_entries,
            (unsigned)activity.visible_sprites,
            (unsigned)activity.visible_nonfull_y_zoom_samples,
            (unsigned)activity.frame_count,
            (unsigned)activity.backdrop_palette_nonzero,
            (unsigned)activity.video_ram_offset,
            (unsigned)activity.video_ram_modulo,
            (unsigned)activity.palette_bank_selected,
            (unsigned)activity.screen_shadow,
            (unsigned)activity.video_auto_animation_speed,
            (unsigned)activity.video_auto_animation_disabled,
            (unsigned)activity.display_position_interrupt_control);
}
#endif

static int print_native_execution_error(const gn_instance *instance);
static int print_active_execution_error(const gn_instance *instance,
                                        const active_schedule *schedule,
                                        int start_observed, uint32_t completed,
                                        const uint32_t *captures, size_t count);
static void print_unsupported_guest_event(const gn_instance *instance,
                                         const gn_run_result *result,
                                         int fallback_guest_executed,
                                         int frame_output_written,
                                         uint32_t video_advance_requested,
                                         uint32_t video_advance_completed);

/* 0 means no checkpoint, 1 means a diagnostic result was reported, and -1
 * means native execution or local video output failed. */
static int report_attract_start(gn_instance *instance, unsigned chunk,
                                const char *frame_output_path,
                                uint32_t video_advance_frames) {
    gn_mvs_attract_verdict verdict;
    if (!get_attract_start(instance, &verdict)) return 0;
    for (uint32_t frame = 0u; frame < video_advance_frames; ++frame) {
        const gn_status input_status = gn_set_mvs_inputs(instance, 0u);
        gn_run_result result = {.reason = GN_RUN_ERROR};
        const gn_status run_status = input_status == GN_STATUS_OK
            ? gn_mvs_run_frame_budget(instance, &result)
            : input_status;
        if (run_status != GN_STATUS_OK || result.reason == GN_RUN_ERROR) {
            (void)print_native_execution_error(instance);
            return -1;
        }
        if (result.reason == GN_RUN_FAULT) {
            /* A bounded diagnostic continuation can still leave useful
             * guest-rendered pixels at the fault boundary. Save them only to
             * the caller's validated ignored local path; the guest-fault
             * status remains authoritative and this is not title acceptance. */
            if (frame_output_path != NULL &&
                !render_local_frame(instance, frame_output_path)) {
                puts("{\"status\":\"native_video_unavailable\"}");
                return -1;
            }
            print_unsupported_guest_event(instance, &result, 1,
                                          frame_output_path != NULL,
                                          video_advance_frames, frame);
            return 1;
        }
        if (result.reason == GN_RUN_STOPPED) {
            if (frame_output_path != NULL &&
                !render_local_frame(instance, frame_output_path)) {
                puts("{\"status\":\"native_video_unavailable\"}");
                return -1;
            }
            if (frame_output_path != NULL)
                printf("{\"status\":\"guest_stopped\",\"guest_executed\":true,"
                       "\"frame_output_written\":true");
            else
                printf("{\"status\":\"guest_stopped\",\"guest_executed\":true");
            if (video_advance_frames != 0u)
                printf(",\"video_advance_frames\":%u,"
                       "\"video_advance_requested\":%u,"
                       "\"video_advance_completed\":%u",
                       video_advance_frames, video_advance_frames, frame);
            puts("}");
            return 1;
        }
    }
    if (!render_local_frame(instance, frame_output_path)) {
        puts("{\"status\":\"native_video_unavailable\"}");
        return -1;
    }
    print_attract_start(chunk, &verdict, video_advance_frames,
                        video_advance_frames,
                        frame_output_path != NULL);
    return 1;
}

#ifndef GN_MVS_QUALIFY_NO_MAIN
static int parse_input_script(const char *text, input_script *out_script) {
    static const char prefix[] = "coin@";
    if (text == NULL || out_script == NULL ||
        strncmp(text, prefix, sizeof(prefix) - 1u) != 0) return 0;
    const char *cursor = text + sizeof(prefix) - 1u;
    uint32_t values[2] = {0u, 0u};
    for (size_t field = 0u; field < 2u; ++field) {
        if (*cursor < '0' || *cursor > '9') return 0;
        uint32_t value = 0u;
        do {
            const uint32_t digit = (uint32_t)(*cursor - '0');
            if (value > (MAX_INPUT_SCRIPT_FRAMES - digit) / 10u) return 0;
            value = value * 10u + digit;
            ++cursor;
        } while (*cursor >= '0' && *cursor <= '9');
        if (value == 0u || value > MAX_INPUT_SCRIPT_FRAMES) return 0;
        values[field] = value;
        if (field == 0u) {
            if (strncmp(cursor, ",start@", 7u) != 0) return 0;
            cursor += 7u;
        }
    }
    if (*cursor != '\0' || values[0] >= values[1]) return 0;
    out_script->coin_frame = values[0];
    out_script->start_frame = values[1];
    return 1;
}
#endif

static void print_scripted_start_indication(unsigned attract_chunk,
                                         const gn_mvs_attract_verdict *verdict,
                                         int observed,
                                         int frame_output_written) {
    printf("{\"status\":\"attract_start\",\"guest_executed\":true,"
           "\"checkpoint\":{\"user_request\":\"%s\",\"chunk\":%u,"
           "\"user_mode_corroborated\":%s},\"input_response\":\"%s\"",
           verdict->user_request == GN_MVS_REQUEST_TITLE ? "title" : "demo",
           attract_chunk,
           verdict->user_mode_corroborated != 0u ? "true" : "false",
           observed != 0 ? "observed" : "not_observed");
    if (frame_output_written != 0)
        printf(",\"frame_output_written\":true");
    puts("}");
}

static int scripted_frame_failure(const gn_instance *instance,
                                  gn_status status, const gn_run_result *result,
                                  const char *frame_output_path,
                                  int *out_exit_code) {
    if (status != GN_STATUS_OK || result->reason == GN_RUN_ERROR) {
        *out_exit_code = print_native_execution_error(instance);
        return 1;
    }
    if (result->reason == GN_RUN_FAULT) {
        if (!render_local_frame(instance, frame_output_path)) {
            puts("{\"status\":\"native_video_unavailable\"}");
            *out_exit_code = 1;
            return 1;
        }
        print_unsupported_guest_event(instance, result, 1,
                                      frame_output_path != NULL, 0u, 0u);
        *out_exit_code = 0;
        return 1;
    }
    return 0;
}

static void print_active_capture_frames(const uint32_t *frames, size_t count) {
    putchar('[');
    for (size_t index = 0u; index < count; ++index)
        printf("%s%u", index == 0u ? "" : ",", frames[index]);
    putchar(']');
}

static void print_active_input_events(const active_schedule *schedule) {
    putchar('[');
    for (size_t index = 0u; index < schedule->input_count; ++index)
        printf("%s{\"frame\":%u,\"mask\":%u}",
               index == 0u ? "" : ",", schedule->inputs[index].frame,
               schedule->inputs[index].mask);
    putchar(']');
}

static int print_native_failure_object(const gn_mvs_failure *failure);

static int active_capture_path(const active_schedule *schedule, uint32_t frame,
                               char *out_path, size_t capacity) {
    if (schedule == NULL || schedule->capture_directory == NULL ||
        out_path == NULL || capacity == 0u) return 0;
    const int length = snprintf(out_path, capacity, "%s/frame-%04u.ppm",
                                schedule->capture_directory, frame);
    return length > 0 && (size_t)length < capacity &&
           valid_active_capture_path(out_path);
}

static void print_active_guest_fault(const gn_instance *instance,
                                     const gn_run_result *result,
                                     int start_observed,
                                     uint32_t requested, uint32_t completed,
                                     const uint32_t *requested_captures,
                                     size_t requested_capture_count,
                                     const uint32_t *completed_captures,
                                     size_t completed_capture_count) {
    gn_mvs_failure failure;
    memset(&failure, 0, sizeof(failure));
    const int have_failure =
        gn_private_mvs_failure(instance, &failure) == GN_STATUS_OK &&
        failure.valid == 1u;
    const int guest_executed = have_failure != 0
        ? failure.guest_executed != 0u : 1;
    gn_mvs_bus_fault_observation observation;
    memset(&observation, 0, sizeof(observation));
    (void)gn_observe_mvs_bus_fault(instance, &observation, sizeof(observation));
    printf("{\"status\":\"unsupported_guest_event\",\"guest_executed\":%s,"
           "\"start_observed\":%s,"
           "\"active_frames_requested\":%u,\"active_frames_completed\":%u,"
           "\"capture_frames_requested\":",
           guest_executed != 0 ? "true" : "false",
           start_observed != 0 ? "true" : "false", requested, completed);
    print_active_capture_frames(requested_captures, requested_capture_count);
    printf(",\"capture_frames\":");
    print_active_capture_frames(completed_captures, completed_capture_count);
    if (result != NULL)
        printf(",\"first_unsupported_event\":{\"pc\":%u,\"opcode\":%u,"
               "\"mame_unmapped_write_count\":%u,"
               "\"mame_watchdog_pet_count\":%u,"
               "\"mame_watchdog_reset_count\":%u}",
               result->fault_pc, (unsigned)result->instruction_register,
               observation.mame_unmapped_write_count,
               observation.mame_watchdog_pet_count,
               observation.mame_watchdog_reset_count);
    if (have_failure != 0) (void)print_native_failure_object(&failure);
    puts("}");
}

static int run_active_frames(gn_instance *instance,
                             const active_schedule *schedule,
                             int start_observed) {
    if (instance == NULL || schedule == NULL) return 1;
    active_schedule runtime_schedule = *schedule;
    schedule = &runtime_schedule;
    uint32_t held_mask = 0u;
    size_t next_input = 0u;
    size_t next_capture = 0u;
    uint32_t completed_captures[MAX_CAPTURE_FRAMES] = {0u};
    uint32_t completed = 0u;
    const size_t pixel_count = (size_t)320u * (size_t)224u;
    uint32_t *pixels = schedule->sound_window_count != 0u
        ? (uint32_t *)malloc(pixel_count * sizeof(*pixels)) : NULL;
    int16_t audio[GN_MVS_AUDIO_CAPACITY_FRAMES_V1 * 2u];
    if (schedule->sound_window_count != 0u && pixels == NULL) {
        puts("{\"status\":\"native_audio_capture_unavailable\",\"guest_executed\":false}");
        return 1;
    }
    for (size_t index = 0u; index < schedule->sound_window_count; ++index) {
        active_sound_window *window = &runtime_schedule.sound_windows[index];
        if (!active_sound_window_open(schedule, window)) {
            (void)active_sound_windows_close(&runtime_schedule);
            free(pixels);
            puts("{\"status\":\"native_audio_capture_unavailable\",\"guest_executed\":false}");
            return 1;
        }
    }
    if (gn_set_mvs_inputs(instance, held_mask) != GN_STATUS_OK) {
        (void)active_sound_windows_close(&runtime_schedule);
        free(pixels);
        return print_active_execution_error(instance, schedule, start_observed,
                                             completed, completed_captures,
                                             next_capture);
    }
    for (uint32_t frame = 0u; frame < schedule->active_frames; ++frame) {
        if (next_input < schedule->input_count &&
            schedule->inputs[next_input].frame == frame) {
            held_mask = schedule->inputs[next_input].mask;
            ++next_input;
        }
        if (gn_set_mvs_inputs(instance, held_mask) != GN_STATUS_OK) {
            (void)active_sound_windows_close(&runtime_schedule);
            free(pixels);
            return print_active_execution_error(instance, schedule, start_observed,
                                                 completed, completed_captures,
                                                 next_capture);
        }
        gn_run_result result;
        gn_status status = GN_STATUS_OK;
        gn_mvs_frame_result_v1 pcm_result;
        memset(&pcm_result, 0, sizeof(pcm_result));
        active_sound_window *selected_window = NULL;
        for (size_t index = 0u; index < schedule->sound_window_count; ++index) {
            if (active_sound_window_contains(&runtime_schedule.sound_windows[index],
                                             frame)) {
                selected_window = &runtime_schedule.sound_windows[index];
                break;
            }
        }
        if (selected_window != NULL) {
            if (selected_window->completed_frames == 0u &&
                gn_private_mvs_sound_diagnostics_clear(instance) != GN_STATUS_OK) {
                (void)active_sound_windows_close(&runtime_schedule);
                free(pixels);
                puts("{\"status\":\"native_sound_observation_unavailable\",\"guest_executed\":true}");
                return 1;
            }
            const gn_mvs_frame_request_v1 request = {
                GN_MVS_FRAME_REQUEST_V1_VERSION, held_mask, GN_PIXEL_XRGB8888,
                320u, 224u, (size_t)320u * sizeof(*pixels),
                (uint8_t *)pixels, pixel_count * sizeof(*pixels),
                audio, GN_MVS_AUDIO_CAPACITY_FRAMES_V1
            };
            status = gn_mvs_advance_frame_v1(instance, &request, sizeof(request),
                                             &pcm_result, sizeof(pcm_result));
            result.reason = pcm_result.reason;
            result.requested_cycles = pcm_result.requested_cycles;
            result.elapsed_cycles = pcm_result.elapsed_cycles;
            result.instructions = pcm_result.instructions;
            result.fault_pc = 0u;
            result.instruction_register = 0u;
        } else {
            status = gn_mvs_run_frame_budget(instance, &result);
        }
        if (status != GN_STATUS_OK || result.reason == GN_RUN_ERROR) {
            (void)active_sound_windows_close(&runtime_schedule);
            free(pixels);
            return print_active_execution_error(instance, schedule, start_observed,
                                                 completed, completed_captures,
                                                 next_capture);
        }
        if (result.reason == GN_RUN_FAULT) {
            print_active_guest_fault(instance, &result, start_observed,
                                     schedule->active_frames,
                                     completed, schedule->captures,
                                     schedule->capture_count,
                                     completed_captures, next_capture);
            (void)active_sound_windows_close(&runtime_schedule);
            free(pixels);
            return 0;
        }
        if (result.reason == GN_RUN_STOPPED) {
            printf("{\"status\":\"guest_stopped\",\"guest_executed\":true,"
                   "\"start_observed\":%s,\"active_frames_requested\":%u,"
                   "\"active_frames_completed\":%u,"
                   "\"capture_frames_requested\":",
                   start_observed != 0 ? "true" : "false",
                   schedule->active_frames, completed);
            print_active_capture_frames(schedule->captures,
                                        schedule->capture_count);
            printf(",\"capture_frames\":");
            print_active_capture_frames(completed_captures, next_capture);
            (void)active_sound_windows_close(&runtime_schedule);
            print_active_sound_windows(schedule);
            free(pixels);
            puts("}");
            return 0;
        }
        ++completed;
        if (selected_window != NULL) {
            const uint32_t observation_index = selected_window->completed_frames;
            gn_mvs_sound_observation sound_observation;
            if (observation_index >= MAX_SOUND_WINDOW_FRAMES ||
                pcm_result.audio_frames_delivered >
                    GN_MVS_AUDIO_CAPACITY_FRAMES_V1 ||
                pcm_result.audio_frames_generated !=
                    pcm_result.audio_frames_delivered ||
                pcm_result.video_pixels_produced != pixel_count ||
                UINT64_MAX - selected_window->actual_cycles <
                    pcm_result.elapsed_cycles ||
                UINT64_MAX - selected_window->audio_frames_generated <
                    pcm_result.audio_frames_generated ||
                UINT64_MAX - selected_window->audio_frames_delivered <
                    pcm_result.audio_frames_delivered ||
                UINT64_MAX - selected_window->audio_frames_discarded <
                    pcm_result.audio_frames_discarded ||
                !active_sound_window_write(selected_window, audio,
                                           pcm_result.audio_frames_delivered) ||
                gn_private_mvs_sound_observe(instance, &sound_observation) !=
                    GN_STATUS_OK ||
                sound_observation.chip.version != 1u ||
                sound_observation.chip.event_count >
                    GN_MVS_SOUND_DIAGNOSTIC_EVENT_CAPACITY ||
                !active_sound_chip_frame_capture(
                    selected_window, frame, &sound_observation.chip)) {
                (void)active_sound_windows_close(&runtime_schedule);
                free(pixels);
                puts("{\"status\":\"native_audio_capture_inconsistent\",\"guest_executed\":true}");
                return 1;
            }
            selected_window->input_masks[observation_index] = held_mask;
            selected_window->elapsed_cycles[observation_index] =
                pcm_result.elapsed_cycles;
            selected_window->audio_frames[observation_index] =
                (uint32_t)pcm_result.audio_frames_delivered;
            ++selected_window->completed_frames;
            selected_window->actual_cycles += pcm_result.elapsed_cycles;
            selected_window->audio_frames_generated +=
                pcm_result.audio_frames_generated;
            selected_window->audio_frames_delivered +=
                pcm_result.audio_frames_delivered;
            selected_window->audio_frames_discarded +=
                pcm_result.audio_frames_discarded;
            selected_window->chip_observation = sound_observation.chip;
            selected_window->board_observations[observation_index] =
                sound_observation.board;
        }
        if (next_capture < schedule->capture_count &&
            schedule->captures[next_capture] == frame) {
            char path[160];
            const int capture_ok = active_capture_path(schedule, frame, path,
                                                       sizeof(path)) &&
                (pixels != NULL ? write_private_ppm(path, pixels, pixel_count)
                                : render_local_frame(instance, path));
            if (!capture_ok) {
                printf("{\"status\":\"native_video_unavailable\","
                       "\"guest_executed\":true,\"start_observed\":%s,"
                       "\"active_frames_requested\":%u,"
                       "\"active_frames_completed\":%u,"
                       "\"capture_frames_requested\":",
                       start_observed != 0 ? "true" : "false",
                       schedule->active_frames, completed);
                print_active_capture_frames(schedule->captures,
                                            schedule->capture_count);
                printf(",\"capture_frames\":");
                print_active_capture_frames(completed_captures, next_capture);
                (void)active_sound_windows_close(&runtime_schedule);
                free(pixels);
                puts("}");
                return 1;
            }
            completed_captures[next_capture] = frame;
            ++next_capture;
        }
    }
    printf("{\"status\":\"active_frames_completed\","
           "\"guest_executed\":true,\"start_observed\":%s,"
           "\"active_frames_requested\":%u,"
           "\"active_frames_completed\":%u,\"capture_frames_requested\":",
           start_observed != 0 ? "true" : "false",
           schedule->active_frames, completed);
    print_active_capture_frames(schedule->captures, schedule->capture_count);
    printf(",\"capture_frames\":");
    print_active_capture_frames(completed_captures, next_capture);
    printf(",\"sampled_inputs\":");
    print_active_input_events(schedule);
    if (!active_sound_windows_close(&runtime_schedule)) {
        free(pixels);
        puts("{\"status\":\"native_audio_capture_inconsistent\",\"guest_executed\":true}");
        return 1;
    }
    print_active_sound_windows(schedule);
    free(pixels);
    puts("}");
    return 0;
}

static int run_scripted_start(gn_instance *instance, unsigned attract_chunk,
                              const gn_mvs_attract_verdict *verdict,
                              const input_script *script,
                              const char *frame_output_path,
                              const active_schedule *active) {
    for (uint32_t frame = 1u; frame <= MAX_INPUT_SCRIPT_FRAMES; ++frame) {
        uint32_t inputs = 0u;
        /* Keep Coin available for a delayed BIOS poll, then release it so
         * guest credit/debounce logic can progress while Start remains held. */
        if (frame >= script->coin_frame &&
            frame - script->coin_frame < SCRIPTED_COIN_HOLD_FRAMES)
            inputs |= GN_MVS_INPUT_COIN1;
        if (frame >= script->start_frame) inputs |= GN_MVS_INPUT_P1_START;
        if (gn_set_mvs_inputs(instance, inputs) != GN_STATUS_OK) {
            if (active != NULL)
                return print_active_execution_error(instance, active, 0, 0u,
                                                     NULL, 0u);
            (void)print_native_execution_error(instance);
            return 1;
        }
        gn_run_result result;
        const gn_status status = gn_mvs_run_frame_budget(instance, &result);
        if (active != NULL) {
            if (status != GN_STATUS_OK || result.reason == GN_RUN_ERROR)
                return print_active_execution_error(instance, active, 0, 0u,
                                                     NULL, 0u);
            if (result.reason == GN_RUN_FAULT) {
                print_active_guest_fault(instance, &result, 0,
                    active->active_frames, 0u, active->captures,
                    active->capture_count, NULL, 0u);
                return 0;
            }
        }
        int failure_exit_code = 0;
        if (scripted_frame_failure(instance, status, &result, frame_output_path,
                                   &failure_exit_code)) return failure_exit_code;
        gn_mvs_progress_observation progress;
        memset(&progress, 0, sizeof(progress));
        if (gn_observe_mvs_progress(instance, &progress, sizeof(progress)) !=
            GN_STATUS_OK) {
            if (active != NULL)
                return print_active_execution_error(instance, active, 0, 0u,
                                                     NULL, 0u);
            (void)print_native_execution_error(instance);
            return 1;
        }
        if (progress.player_start_with_p1_indication != 0u) {
            if (active != NULL)
                return run_active_frames(instance, active, 1);
            if (!render_local_frame(instance, frame_output_path)) {
                puts("{\"status\":\"native_video_unavailable\"}");
                return 1;
            }
            print_scripted_start_indication(attract_chunk, verdict, 1,
                                            frame_output_path != NULL);
            return 0;
        }
        if (result.reason == GN_RUN_STOPPED) break;
    }
    if (active != NULL) {
        gn_mvs_bus_fault_observation final_observation;
        memset(&final_observation, 0, sizeof(final_observation));
        (void)gn_observe_mvs_bus_fault(instance, &final_observation,
                                       sizeof(final_observation));
        gn_mvs_progress_observation final_progress;
        memset(&final_progress, 0, sizeof(final_progress));
        (void)gn_observe_mvs_progress(instance, &final_progress,
                                      sizeof(final_progress));
        printf("{\"status\":\"start_input_not_observed\","
               "\"guest_executed\":true,\"start_observed\":false,"
               "\"player_start_entered\":%s,"
               "\"p1_start_indication\":%s,"
               "\"watchdog_pets\":%u,"
               "\"watchdog_resets\":%u,"
               "\"active_frames_requested\":%u,"
               "\"active_frames_completed\":0,"
               "\"capture_frames_requested\":",
               final_progress.player_start_entered != 0u ? "true" : "false",
               final_progress.player_start_with_p1_indication != 0u ?
                   "true" : "false",
               final_observation.mame_watchdog_pet_count,
               final_observation.mame_watchdog_reset_count,
               active->active_frames);
        print_active_capture_frames(active->captures, active->capture_count);
        printf(",\"capture_frames\":[],");
        print_diagnosis(instance);
        puts("}");
        return 0;
    }
    if (!render_local_frame(instance, frame_output_path)) {
        puts("{\"status\":\"native_video_unavailable\"}");
        return 1;
    }
    print_scripted_start_indication(attract_chunk, verdict, 0,
                                    frame_output_path != NULL);
    return 0;
}

/* Privacy-safe stall diagnosis for a budget-exhausted run (docs/mvs-media.md
 * "Stall diagnosis"), emitted as the report key "diagnosis": counts, public register addresses inside the two public
 * windows, and public BIOS protocol values. No PCs, words or program bytes. */
static void print_histogram(const char *name, const uint64_t *values, size_t count) {
    printf("\"%s\":[", name);
    for (size_t index = 0u; index < count; ++index)
        printf("%s%llu", index == 0u ? "" : ",", (unsigned long long)values[index]);
    printf("],");
}

static void print_diagnosis(const gn_instance *instance) {
    gn_mvs_stall_diagnosis diagnosis;
    memset(&diagnosis, 0, sizeof(diagnosis));
    (void)gn_private_mvs_stall_diagnosis(instance, &diagnosis);
    printf("\"diagnosis\":{\"interrupts_taken\":%llu,\"irq_ack_writes\":%llu,",
           (unsigned long long)diagnosis.interrupts_taken,
           (unsigned long long)diagnosis.irq_ack_writes);
    print_histogram("sr_mask_histogram", diagnosis.sr_mask_histogram,
                    GN_MVS_SR_MASK_BUCKETS);
    print_histogram("pc_region_histogram", diagnosis.pc_region_histogram,
                    GN_MVS_PC_REGION_BUCKETS);
    printf("\"low_program_window_reads\":%llu,\"unmapped_read_count\":%llu,"
           "\"polled_registers\":[",
           (unsigned long long)diagnosis.low_program_window_reads,
           (unsigned long long)diagnosis.unmapped_read_count);
    for (uint32_t index = 0u; index < diagnosis.polled_count; ++index)
        printf("%s{\"address\":\"0x%06x\",\"reads\":%llu}", index == 0u ? "" : ",",
               (unsigned)diagnosis.polled[index].address,
               (unsigned long long)diagnosis.polled[index].reads);
    printf("],\"polled_untracked_reads\":%llu,"
           "\"bios_variables\":{\"system_mode\":%u,\"user_request\":%u,"
           "\"user_mode\":%u},\"attract_rejection\":\"%s\"}",
           (unsigned long long)diagnosis.polled_untracked_reads,
           (unsigned)diagnosis.bios_system_mode,
           (unsigned)diagnosis.bios_user_request,
           (unsigned)diagnosis.bios_user_mode,
           gn_private_mvs_attract_rejection_name(diagnosis.attract_rejection));
}

static const char *failure_component_name(gn_mvs_failure_component value) {
    switch (value) {
        case GN_MVS_FAILURE_COMPONENT_MAIN_CPU: return "main_cpu";
        case GN_MVS_FAILURE_COMPONENT_SOUND_CPU: return "sound_cpu";
        case GN_MVS_FAILURE_COMPONENT_BOARD: return "board";
        case GN_MVS_FAILURE_COMPONENT_INTERNAL: return "internal";
        default: return NULL;
    }
}

static const char *failure_stage_name(gn_mvs_failure_stage value) {
    switch (value) {
        case GN_MVS_FAILURE_STAGE_OBSERVE: return "observe";
        case GN_MVS_FAILURE_STAGE_IRQ_UPDATE: return "irq_update";
        case GN_MVS_FAILURE_STAGE_EXECUTE: return "execute";
        case GN_MVS_FAILURE_STAGE_BUS_ACCESS: return "bus_access";
        case GN_MVS_FAILURE_STAGE_SOUND_CATCHUP: return "sound_catchup";
        case GN_MVS_FAILURE_STAGE_WATCHDOG_RESET: return "watchdog_reset";
        case GN_MVS_FAILURE_STAGE_TIMING_ACCOUNTING: return "timing_accounting";
        default: return NULL;
    }
}

static const char *failure_reason_name(gn_mvs_failure_reason value) {
    switch (value) {
        case GN_MVS_FAILURE_REASON_INTERNAL_FAILURE: return "internal_failure";
        case GN_MVS_FAILURE_REASON_BUS_FAILURE: return "bus_failure";
        case GN_MVS_FAILURE_REASON_CYCLE_LIMIT: return "cycle_limit";
        case GN_MVS_FAILURE_REASON_INVALID_STATE: return "invalid_state";
        case GN_MVS_FAILURE_REASON_CLOCK_OVERFLOW: return "clock_overflow";
        case GN_MVS_FAILURE_REASON_ACCOUNTING_MISMATCH: return "accounting_mismatch";
        default: return NULL;
    }
}

static const char *failure_site_name(gn_mvs_failure_site value) {
    switch (value) {
        case GN_MVS_FAILURE_SITE_UNKNOWN: return "unknown";
        case GN_MVS_FAILURE_SITE_MAIN_OBSERVE: return "main_observe";
        case GN_MVS_FAILURE_SITE_MAIN_IRQ_UPDATE: return "main_irq_update";
        case GN_MVS_FAILURE_SITE_MAIN_EXECUTION: return "main_execution";
        case GN_MVS_FAILURE_SITE_MAIN_BUS_READ: return "main_bus_read";
        case GN_MVS_FAILURE_SITE_MAIN_BUS_WRITE: return "main_bus_write";
        case GN_MVS_FAILURE_SITE_SOUND_MEMORY_READ: return "sound_memory_read";
        case GN_MVS_FAILURE_SITE_SOUND_MEMORY_WRITE: return "sound_memory_write";
        case GN_MVS_FAILURE_SITE_SOUND_IO_READ: return "sound_io_read";
        case GN_MVS_FAILURE_SITE_SOUND_IO_WRITE: return "sound_io_write";
        case GN_MVS_FAILURE_SITE_SOUND_INTERRUPT_ACK: return "sound_interrupt_ack";
        case GN_MVS_FAILURE_SITE_SOUND_TICK: return "sound_tick";
        case GN_MVS_FAILURE_SITE_SOUND_RESET: return "sound_reset";
        case GN_MVS_FAILURE_SITE_YM2610_SAMPLE_READ: return "ym2610_sample_read";
        case GN_MVS_FAILURE_SITE_BOARD_WATCHDOG_RESET: return "board_watchdog_reset";
        case GN_MVS_FAILURE_SITE_INTERNAL_TIMING: return "internal_timing";
        default: return NULL;
    }
}

static const char *failure_cause_name(gn_mvs_failure_cause value) {
    switch (value) {
        case GN_MVS_FAILURE_CAUSE_UNKNOWN: return "unknown";
        case GN_MVS_FAILURE_CAUSE_MAIN_BUS_CALLBACK: return "main_bus_callback";
        case GN_MVS_FAILURE_CAUSE_SOUND_BUS_CALLBACK: return "sound_bus_callback";
        case GN_MVS_FAILURE_CAUSE_Z80_TICK: return "z80_tick";
        case GN_MVS_FAILURE_CAUSE_Z80_RESET: return "z80_reset";
        case GN_MVS_FAILURE_CAUSE_YM2610_CALLBACK: return "ym2610_callback";
        case GN_MVS_FAILURE_CAUSE_OWNED_CPU: return "owned_cpu";
        case GN_MVS_FAILURE_CAUSE_BOARD_RESET: return "board_reset";
        case GN_MVS_FAILURE_CAUSE_TIMING_ACCOUNTING: return "timing_accounting";
        default: return NULL;
    }
}

static const char *failure_status_name(gn_mvs_failure_status value) {
    switch (value) {
        case GN_MVS_FAILURE_STATUS_UNKNOWN: return "unknown";
        case GN_MVS_FAILURE_STATUS_Z80_INVALID_ARGUMENT: return "z80_invalid_argument";
        case GN_MVS_FAILURE_STATUS_Z80_OUT_OF_MEMORY: return "z80_out_of_memory";
        case GN_MVS_FAILURE_STATUS_Z80_BUS_FAILURE: return "z80_bus_failure";
        case GN_MVS_FAILURE_STATUS_Z80_CYCLE_LIMIT: return "z80_cycle_limit";
        case GN_MVS_FAILURE_STATUS_Z80_INVALID_SNAPSHOT: return "z80_invalid_snapshot";
        case GN_MVS_FAILURE_STATUS_YM2610_INVALID_ARGUMENT: return "ym2610_invalid_argument";
        case GN_MVS_FAILURE_STATUS_YM2610_NO_MEMORY: return "ym2610_no_memory";
        case GN_MVS_FAILURE_STATUS_YM2610_CALLBACK_FAILURE: return "ym2610_callback_failure";
        case GN_MVS_FAILURE_STATUS_YM2610_EXCEPTION: return "ym2610_exception";
        case GN_MVS_FAILURE_STATUS_YM2610_CAPACITY: return "ym2610_capacity";
        case GN_MVS_FAILURE_STATUS_YM2610_LIMIT: return "ym2610_limit";
        case GN_MVS_FAILURE_STATUS_OWNED_CPU_INVALID_ARGUMENT: return "owned_cpu_invalid_argument";
        case GN_MVS_FAILURE_STATUS_OWNED_CPU_ALLOCATION_FAILURE: return "owned_cpu_allocation_failure";
        case GN_MVS_FAILURE_STATUS_OWNED_CPU_ADDRESS_ERROR: return "owned_cpu_address_error";
        case GN_MVS_FAILURE_STATUS_OWNED_CPU_HOST_FAULT: return "owned_cpu_host_fault";
        case GN_MVS_FAILURE_STATUS_OWNED_CPU_UNSUPPORTED_OPCODE: return "owned_cpu_unsupported_opcode";
        case GN_MVS_FAILURE_STATUS_OWNED_CPU_BUDGET: return "owned_cpu_budget";
        case GN_MVS_FAILURE_STATUS_OWNED_CPU_COUNTER_OVERFLOW: return "owned_cpu_counter_overflow";
        case GN_MVS_FAILURE_STATUS_OWNED_CPU_PRIVILEGE_VIOLATION: return "owned_cpu_privilege_violation";
        default: return NULL;
    }
}

static const char *failure_operation_name(gn_mvs_failure_bus_operation value) {
    switch (value) {
        case GN_MVS_FAILURE_BUS_UNKNOWN: return "unknown";
        case GN_MVS_FAILURE_BUS_READ: return "read";
        case GN_MVS_FAILURE_BUS_WRITE: return "write";
        case GN_MVS_FAILURE_BUS_INTERRUPT_ACK: return "interrupt_ack";
        default: return NULL;
    }
}

static int failure_tokens_are_valid(const gn_mvs_failure *failure) {
    if (failure->component == GN_MVS_FAILURE_COMPONENT_MAIN_CPU) {
        return ((failure->stage == GN_MVS_FAILURE_STAGE_OBSERVE ||
                 failure->stage == GN_MVS_FAILURE_STAGE_IRQ_UPDATE ||
                 failure->stage == GN_MVS_FAILURE_STAGE_EXECUTE) &&
                failure->reason == GN_MVS_FAILURE_REASON_INTERNAL_FAILURE) ||
               (failure->stage == GN_MVS_FAILURE_STAGE_BUS_ACCESS &&
                failure->reason == GN_MVS_FAILURE_REASON_BUS_FAILURE);
    }
    if (failure->component == GN_MVS_FAILURE_COMPONENT_SOUND_CPU) {
        return (failure->stage == GN_MVS_FAILURE_STAGE_BUS_ACCESS &&
                failure->reason == GN_MVS_FAILURE_REASON_BUS_FAILURE) ||
               (failure->stage == GN_MVS_FAILURE_STAGE_SOUND_CATCHUP &&
                (failure->reason == GN_MVS_FAILURE_REASON_INTERNAL_FAILURE ||
                 failure->reason == GN_MVS_FAILURE_REASON_CYCLE_LIMIT ||
                 failure->reason == GN_MVS_FAILURE_REASON_INVALID_STATE ||
                 failure->reason == GN_MVS_FAILURE_REASON_CLOCK_OVERFLOW));
    }
    if (failure->component == GN_MVS_FAILURE_COMPONENT_BOARD)
        return failure->stage == GN_MVS_FAILURE_STAGE_WATCHDOG_RESET &&
               failure->reason == GN_MVS_FAILURE_REASON_INTERNAL_FAILURE;
    if (failure->component == GN_MVS_FAILURE_COMPONENT_INTERNAL)
        return failure->stage == GN_MVS_FAILURE_STAGE_TIMING_ACCOUNTING &&
               failure->reason == GN_MVS_FAILURE_REASON_ACCOUNTING_MISMATCH;
    return 0;
}

static int failure_status_is_z80(gn_mvs_failure_status status) {
    return status >= GN_MVS_FAILURE_STATUS_Z80_INVALID_ARGUMENT &&
           status <= GN_MVS_FAILURE_STATUS_Z80_INVALID_SNAPSHOT;
}

static int failure_status_is_ym2610(gn_mvs_failure_status status) {
    return status >= GN_MVS_FAILURE_STATUS_YM2610_INVALID_ARGUMENT &&
           status <= GN_MVS_FAILURE_STATUS_YM2610_LIMIT;
}

static int failure_tuple_is_valid(const gn_mvs_failure *failure) {
    const int has_bus = failure->bus_access_valid != 0u;
    if (failure->component == GN_MVS_FAILURE_COMPONENT_MAIN_CPU) {
        if (failure->stage == GN_MVS_FAILURE_STAGE_OBSERVE ||
            failure->stage == GN_MVS_FAILURE_STAGE_IRQ_UPDATE ||
            failure->stage == GN_MVS_FAILURE_STAGE_EXECUTE) {
            const gn_mvs_failure_site site =
                failure->stage == GN_MVS_FAILURE_STAGE_OBSERVE
                    ? GN_MVS_FAILURE_SITE_MAIN_OBSERVE
                    : failure->stage == GN_MVS_FAILURE_STAGE_IRQ_UPDATE
                        ? GN_MVS_FAILURE_SITE_MAIN_IRQ_UPDATE
                        : GN_MVS_FAILURE_SITE_MAIN_EXECUTION;
            const int execution_status_valid =
                failure->underlying_status == GN_MVS_FAILURE_STATUS_UNKNOWN ||
                failure->underlying_status == GN_MVS_FAILURE_STATUS_OWNED_CPU_INVALID_ARGUMENT ||
                failure->underlying_status == GN_MVS_FAILURE_STATUS_OWNED_CPU_ALLOCATION_FAILURE ||
                failure->underlying_status == GN_MVS_FAILURE_STATUS_OWNED_CPU_ADDRESS_ERROR ||
                failure->underlying_status == GN_MVS_FAILURE_STATUS_OWNED_CPU_PRIVILEGE_VIOLATION ||
                failure->underlying_status == GN_MVS_FAILURE_STATUS_OWNED_CPU_HOST_FAULT ||
                failure->underlying_status == GN_MVS_FAILURE_STATUS_OWNED_CPU_UNSUPPORTED_OPCODE ||
                failure->underlying_status == GN_MVS_FAILURE_STATUS_OWNED_CPU_COUNTER_OVERFLOW;
            return failure->reason == GN_MVS_FAILURE_REASON_INTERNAL_FAILURE &&
                   failure->site == site &&
                   failure->device_cause == GN_MVS_FAILURE_CAUSE_OWNED_CPU &&
                   !has_bus &&
                   (failure->stage == GN_MVS_FAILURE_STAGE_EXECUTE
                        ? execution_status_valid
                        : failure->underlying_status == GN_MVS_FAILURE_STATUS_UNKNOWN);
        }
        if (failure->stage == GN_MVS_FAILURE_STAGE_BUS_ACCESS) {
            const int read = failure->site == GN_MVS_FAILURE_SITE_MAIN_BUS_READ;
            const int write = failure->site == GN_MVS_FAILURE_SITE_MAIN_BUS_WRITE;
            return failure->reason == GN_MVS_FAILURE_REASON_BUS_FAILURE &&
                   (read || write) &&
                   failure->device_cause == GN_MVS_FAILURE_CAUSE_MAIN_BUS_CALLBACK &&
                   failure->underlying_status == GN_MVS_FAILURE_STATUS_UNKNOWN &&
                   failure->operation == (read ? GN_MVS_FAILURE_BUS_READ
                                               : GN_MVS_FAILURE_BUS_WRITE) &&
                   (failure->bus_width == 1u || failure->bus_width == 2u) && has_bus;
        }
        return 0;
    }

    if (failure->component == GN_MVS_FAILURE_COMPONENT_SOUND_CPU) {
        if (failure->stage == GN_MVS_FAILURE_STAGE_BUS_ACCESS &&
            failure->reason == GN_MVS_FAILURE_REASON_BUS_FAILURE) {
            if (failure->site == GN_MVS_FAILURE_SITE_SOUND_TICK) {
                return failure->device_cause == GN_MVS_FAILURE_CAUSE_Z80_TICK &&
                       failure->underlying_status ==
                           GN_MVS_FAILURE_STATUS_Z80_BUS_FAILURE && !has_bus;
            }
            if (failure->device_cause == GN_MVS_FAILURE_CAUSE_SOUND_BUS_CALLBACK &&
                failure->underlying_status == GN_MVS_FAILURE_STATUS_Z80_BUS_FAILURE) {
                gn_mvs_failure_bus_operation operation = GN_MVS_FAILURE_BUS_UNKNOWN;
                switch (failure->site) {
                    case GN_MVS_FAILURE_SITE_SOUND_MEMORY_READ:
                    case GN_MVS_FAILURE_SITE_SOUND_IO_READ:
                        operation = GN_MVS_FAILURE_BUS_READ;
                        break;
                    case GN_MVS_FAILURE_SITE_SOUND_MEMORY_WRITE:
                    case GN_MVS_FAILURE_SITE_SOUND_IO_WRITE:
                        operation = GN_MVS_FAILURE_BUS_WRITE;
                        break;
                    case GN_MVS_FAILURE_SITE_SOUND_INTERRUPT_ACK:
                        operation = GN_MVS_FAILURE_BUS_INTERRUPT_ACK;
                        break;
                    default:
                        break;
                }
                return operation != GN_MVS_FAILURE_BUS_UNKNOWN &&
                       failure->operation == operation && failure->bus_width == 1u &&
                       has_bus;
            }
            if (failure->device_cause == GN_MVS_FAILURE_CAUSE_YM2610_CALLBACK &&
                failure_status_is_ym2610(failure->underlying_status)) {
                const int read = failure->site == GN_MVS_FAILURE_SITE_SOUND_IO_READ;
                const int write = failure->site == GN_MVS_FAILURE_SITE_SOUND_IO_WRITE;
                return (read || write) &&
                       failure->operation == (read ? GN_MVS_FAILURE_BUS_READ
                                                   : GN_MVS_FAILURE_BUS_WRITE) &&
                       failure->bus_width == 1u && has_bus;
            }
            return 0;
        }

        if (failure->stage != GN_MVS_FAILURE_STAGE_SOUND_CATCHUP || has_bus)
            return 0;
        if (failure->site == GN_MVS_FAILURE_SITE_SOUND_TICK &&
            failure->device_cause == GN_MVS_FAILURE_CAUSE_Z80_TICK) {
            if (failure->reason == GN_MVS_FAILURE_REASON_CYCLE_LIMIT)
                return failure->underlying_status ==
                       GN_MVS_FAILURE_STATUS_Z80_CYCLE_LIMIT;
            if (failure->reason == GN_MVS_FAILURE_REASON_CLOCK_OVERFLOW)
                return failure->underlying_status == GN_MVS_FAILURE_STATUS_UNKNOWN;
            return failure->reason == GN_MVS_FAILURE_REASON_INVALID_STATE &&
                   (failure->underlying_status ==
                        GN_MVS_FAILURE_STATUS_Z80_INVALID_ARGUMENT ||
                    failure->underlying_status ==
                        GN_MVS_FAILURE_STATUS_Z80_OUT_OF_MEMORY ||
                    failure->underlying_status ==
                        GN_MVS_FAILURE_STATUS_Z80_INVALID_SNAPSHOT);
        }
        if (failure->site == GN_MVS_FAILURE_SITE_SOUND_TICK &&
            failure->device_cause == GN_MVS_FAILURE_CAUSE_YM2610_CALLBACK) {
            return failure->reason == GN_MVS_FAILURE_REASON_INTERNAL_FAILURE &&
                   failure_status_is_ym2610(failure->underlying_status);
        }
        if (failure->site == GN_MVS_FAILURE_SITE_YM2610_SAMPLE_READ) {
            return failure->reason == GN_MVS_FAILURE_REASON_INTERNAL_FAILURE &&
                   failure->device_cause == GN_MVS_FAILURE_CAUSE_YM2610_CALLBACK &&
                   failure->underlying_status ==
                       GN_MVS_FAILURE_STATUS_YM2610_CALLBACK_FAILURE;
        }
        if (failure->site == GN_MVS_FAILURE_SITE_SOUND_RESET &&
            failure->device_cause == GN_MVS_FAILURE_CAUSE_Z80_RESET) {
            return failure->reason == GN_MVS_FAILURE_REASON_INVALID_STATE &&
                   failure_status_is_z80(failure->underlying_status);
        }
        if (failure->site == GN_MVS_FAILURE_SITE_SOUND_RESET &&
            failure->device_cause == GN_MVS_FAILURE_CAUSE_YM2610_CALLBACK) {
            return failure->reason == GN_MVS_FAILURE_REASON_INTERNAL_FAILURE &&
                   failure_status_is_ym2610(failure->underlying_status);
        }
        return 0;
    }

    if (failure->component == GN_MVS_FAILURE_COMPONENT_BOARD) {
        return failure->stage == GN_MVS_FAILURE_STAGE_WATCHDOG_RESET &&
               failure->reason == GN_MVS_FAILURE_REASON_INTERNAL_FAILURE &&
               failure->site == GN_MVS_FAILURE_SITE_BOARD_WATCHDOG_RESET &&
               failure->device_cause == GN_MVS_FAILURE_CAUSE_BOARD_RESET &&
               failure->underlying_status == GN_MVS_FAILURE_STATUS_UNKNOWN && !has_bus;
    }
    if (failure->component == GN_MVS_FAILURE_COMPONENT_INTERNAL) {
        return failure->stage == GN_MVS_FAILURE_STAGE_TIMING_ACCOUNTING &&
               failure->reason == GN_MVS_FAILURE_REASON_ACCOUNTING_MISMATCH &&
               failure->site == GN_MVS_FAILURE_SITE_INTERNAL_TIMING &&
               failure->device_cause == GN_MVS_FAILURE_CAUSE_TIMING_ACCOUNTING &&
               failure->underlying_status == GN_MVS_FAILURE_STATUS_UNKNOWN && !has_bus;
    }
    return 0;
}

static int failure_details_are_valid(const gn_mvs_failure *failure) {
    if (failure == NULL || failure->valid != 1u ||
        failure->guest_executed > 1u || failure->site_valid > 1u ||
        failure->device_cause_valid > 1u ||
        failure->underlying_status_valid > 1u ||
        failure->emulated_cycle_valid > 1u ||
        failure->instruction_boundary_valid > 1u || failure->pc_valid > 1u ||
        failure->opcode_valid > 1u || failure->bus_access_valid > 1u ||
        failure->capture_pending != 0u ||
        failure->site < GN_MVS_FAILURE_SITE_UNKNOWN ||
        failure->site > GN_MVS_FAILURE_SITE_INTERNAL_TIMING ||
        failure->device_cause < GN_MVS_FAILURE_CAUSE_UNKNOWN ||
        failure->device_cause > GN_MVS_FAILURE_CAUSE_TIMING_ACCOUNTING ||
        failure->underlying_status < GN_MVS_FAILURE_STATUS_UNKNOWN ||
        failure->underlying_status > GN_MVS_FAILURE_STATUS_OWNED_CPU_PRIVILEGE_VIOLATION ||
        failure->operation < GN_MVS_FAILURE_BUS_UNKNOWN ||
        failure->operation > GN_MVS_FAILURE_BUS_INTERRUPT_ACK) return 0;
    const int has_bus = failure->bus_access_valid != 0u;
    if ((failure->site_valid != 0u) !=
            (failure->site != GN_MVS_FAILURE_SITE_UNKNOWN) ||
        (failure->device_cause_valid != 0u) !=
            (failure->device_cause != GN_MVS_FAILURE_CAUSE_UNKNOWN) ||
        (failure->underlying_status_valid != 0u) !=
            (failure->underlying_status != GN_MVS_FAILURE_STATUS_UNKNOWN)) return 0;
    if ((failure->emulated_cycle_valid == 0u && failure->emulated_cycle != 0u) ||
        (failure->instruction_boundary_valid == 0u &&
         failure->completed_main_instructions != 0u) ||
        failure->guest_executed !=
            (failure->completed_main_instructions != 0u ? 1u : 0u) ||
        (failure->pc_valid == 0u && failure->pc != 0u) ||
        (failure->opcode_valid == 0u && failure->opcode != 0u)) return 0;
    const int bus_details_valid = has_bus
        ? failure->operation != GN_MVS_FAILURE_BUS_UNKNOWN && failure->bus_width != 0u
        : failure->operation == GN_MVS_FAILURE_BUS_UNKNOWN &&
          failure->bus_address == 0u && failure->bus_width == 0u;
    return bus_details_valid && failure_tuple_is_valid(failure);
}

static int print_native_failure_object(const gn_mvs_failure *failure) {
    if (failure == NULL) return 0;
    const char *component = failure_component_name(failure->component);
    const char *stage = failure_stage_name(failure->stage);
    const char *reason = failure_reason_name(failure->reason);
    const char *site = failure_site_name(failure->site);
    const char *cause = failure_cause_name(failure->device_cause);
    const char *underlying_status = failure_status_name(failure->underlying_status);
    const char *operation = failure_operation_name(failure->operation);
    if (failure->valid == 1u && failure_tokens_are_valid(failure) &&
        failure_details_are_valid(failure) && component != NULL && stage != NULL &&
        reason != NULL && site != NULL && cause != NULL &&
        underlying_status != NULL && operation != NULL) {
        printf(",\"native_failure\":{\"component\":\"%s\",\"stage\":\"%s\","
               "\"reason\":\"%s\",\"site\":\"%s\",\"site_valid\":%s,"
               "\"device_cause\":\"%s\",\"device_cause_valid\":%s,"
               "\"underlying_status\":\"%s\",\"underlying_status_valid\":%s,"
               "\"emulated_cycle\":%llu,\"emulated_cycle_valid\":%s,"
               "\"completed_main_instructions\":%llu,"
               "\"instruction_boundary_valid\":%s,\"pc\":%u,\"pc_valid\":%s,"
               "\"opcode\":%u,\"opcode_valid\":%s,"
               "\"operation\":\"%s\",\"address\":%u,\"width\":%u,"
               "\"bus_access_valid\":%s}",
               component, stage, reason, site,
               failure->site_valid != 0u ? "true" : "false", cause,
               failure->device_cause_valid != 0u ? "true" : "false",
               underlying_status,
               failure->underlying_status_valid != 0u ? "true" : "false",
               (unsigned long long)failure->emulated_cycle,
               failure->emulated_cycle_valid != 0u ? "true" : "false",
               (unsigned long long)failure->completed_main_instructions,
               failure->instruction_boundary_valid != 0u ? "true" : "false",
               failure->pc, failure->pc_valid != 0u ? "true" : "false",
               (unsigned)failure->opcode,
               failure->opcode_valid != 0u ? "true" : "false", operation,
               failure->bus_address, (unsigned)failure->bus_width,
               failure->bus_access_valid != 0u ? "true" : "false");
        return 1;
    }
    return 0;
}

static int print_active_execution_error(const gn_instance *instance,
                                        const active_schedule *schedule,
                                        int start_observed, uint32_t completed,
                                        const uint32_t *captures, size_t count) {
    gn_mvs_failure failure;
    memset(&failure, 0, sizeof(failure));
    if (gn_private_mvs_failure(instance, &failure) != GN_STATUS_OK) {
        /* Preserve the legacy no-active observation when detail is unavailable. */
        if (schedule == NULL) {
            puts("{\"status\":\"native_execution_error\"}");
            return 1;
        }
    }
    const int guest_bus_fault = failure.valid == 1u &&
        failure.component == GN_MVS_FAILURE_COMPONENT_MAIN_CPU &&
        failure.stage == GN_MVS_FAILURE_STAGE_BUS_ACCESS &&
        failure.reason == GN_MVS_FAILURE_REASON_BUS_FAILURE;
    const char *status = guest_bus_fault != 0
        ? "unsupported_guest_event" : "native_execution_error";
    printf("{\"status\":\"%s\",\"guest_executed\":%s", status,
           failure.guest_executed != 0u ? "true" : "false");
    if (schedule != NULL) {
        printf(",\"start_observed\":%s,\"active_frames_requested\":%u,"
               "\"active_frames_completed\":%u,\"capture_frames_requested\":",
               start_observed != 0 ? "true" : "false",
               schedule->active_frames, completed);
        print_active_capture_frames(schedule->captures, schedule->capture_count);
        printf(",\"capture_frames\":");
        print_active_capture_frames(captures, count);
    }
    (void)print_native_failure_object(&failure);
    puts("}");
    return 1;
}

static int print_native_execution_error(const gn_instance *instance) {
    return print_active_execution_error(instance, NULL, 0, 0u, NULL, 0u);
}

static void print_unsupported_guest_event(const gn_instance *instance,
                                         const gn_run_result *result,
                                         int fallback_guest_executed,
                                         int frame_output_written,
                                         uint32_t video_advance_requested,
                                         uint32_t video_advance_completed) {
    gn_mvs_failure failure;
    memset(&failure, 0, sizeof(failure));
    const int have_failure =
        gn_private_mvs_failure(instance, &failure) == GN_STATUS_OK &&
        failure.valid == 1u;
    const int guest_executed = have_failure != 0
        ? failure.guest_executed != 0u : fallback_guest_executed != 0;
    printf("{\"status\":\"unsupported_guest_event\",\"guest_executed\":%s",
           guest_executed != 0 ? "true" : "false");
    if (frame_output_written != 0)
        printf(",\"frame_output_written\":true");
    if (video_advance_requested != 0u)
        printf(",\"video_advance_frames\":%u,"
               "\"video_advance_requested\":%u,"
               "\"video_advance_completed\":%u",
               video_advance_requested, video_advance_requested,
               video_advance_completed);
    if (result != NULL) {
        gn_mvs_bus_fault_observation observation;
        memset(&observation, 0, sizeof(observation));
        (void)gn_observe_mvs_bus_fault(instance, &observation,
                                        sizeof(observation));
        printf(",\"first_unsupported_event\":{\"pc\":%u,\"opcode\":%u,"
               "\"mame_unmapped_write_count\":%u,"
               "\"mame_watchdog_pet_count\":%u,"
               "\"mame_watchdog_reset_count\":%u}",
               result->fault_pc, (unsigned)result->instruction_register,
               observation.mame_unmapped_write_count,
               observation.mame_watchdog_pet_count,
               observation.mame_watchdog_reset_count);
    }
    if (have_failure != 0) (void)print_native_failure_object(&failure);
    puts("}");
}

static uint32_t read32be(const uint8_t *p) {
    return ((uint32_t)p[0] << 24) | ((uint32_t)p[1] << 16) |
           ((uint32_t)p[2] << 8) | p[3];
}
static uint64_t read64be(const uint8_t *p) {
    return ((uint64_t)read32be(p) << 32) | read32be(p + 4u);
}

int gn_mvs_qualify_parse_bundle(const uint8_t *bytes, size_t size,
                                gn_mvs_manifest *manifest) {
    if (bytes == NULL || manifest == NULL || size < HEADER_BYTES ||
        memcmp(bytes, "GNMV", 4u) != 0 ||
        read32be(bytes + 8u) != GN_MVS_PROFILE_MSX) return 0;
    const uint32_t version = read32be(bytes + 4u);
    const uint32_t region_count = read32be(bytes + 12u);
    if (!((version == GN_MVS_MANIFEST_VERSION_LEGACY &&
           region_count == GN_MVS_LEGACY_REGIONS) ||
          (version == GN_MVS_MANIFEST_VERSION &&
           region_count == GN_MVS_MAX_REGIONS))) return 0;
    memset(manifest, 0, sizeof(*manifest));
    manifest->version = version;
    manifest->profile = GN_MVS_PROFILE_MSX;
    manifest->region_count = region_count;
    size_t cursor = HEADER_BYTES;
    for (size_t i = 0u; i < manifest->region_count; ++i) {
        if (cursor > size || size - cursor < REGION_HEADER_BYTES) return 0;
        const uint32_t role = read32be(bytes + cursor);
        const uint64_t length = read64be(bytes + cursor + 4u);
        cursor += REGION_HEADER_BYTES;
        if (length > SIZE_MAX || length > size - cursor) return 0;
        manifest->regions[i] = (gn_mvs_region){
            (gn_mvs_region_role)role, bytes + cursor, (size_t)length,
            (size_t)length, GN_MVS_LAYOUT_LINEAR};
        cursor += (size_t)length;
    }
    return cursor == size;
}

#if !defined(GN_MVS_QUALIFY_NO_MAIN)
static int gn_mvs_qualify_parse_bundle_v3(
    const uint8_t *bytes, size_t size, gn_mvs_manifest_v3 *manifest) {
    if (bytes == NULL || manifest == NULL || size < HEADER_BYTES ||
        memcmp(bytes, "GNMV", 4u) != 0 ||
        read32be(bytes + 4u) != GN_MVS_MANIFEST_VERSION_ZOOM ||
        read32be(bytes + 8u) != GN_MVS_PROFILE_MSX) return 0;
    const uint32_t region_count = read32be(bytes + 12u);
    if (region_count != GN_MVS_V3_MAX_REGIONS - 1u &&
        region_count != GN_MVS_V3_MAX_REGIONS) return 0;
    memset(manifest, 0, sizeof(*manifest));
    manifest->version = GN_MVS_MANIFEST_VERSION_ZOOM;
    manifest->profile = GN_MVS_PROFILE_MSX;
    manifest->region_count = region_count;
    size_t cursor = HEADER_BYTES;
    for (size_t index = 0u; index < region_count; ++index) {
        if (cursor > size || size - cursor < REGION_HEADER_BYTES) return 0;
        const uint32_t role = read32be(bytes + cursor);
        const uint64_t length = read64be(bytes + cursor + 4u);
        cursor += REGION_HEADER_BYTES;
        if (length > SIZE_MAX || length > size - cursor) return 0;
        manifest->regions[index] = (gn_mvs_region){
            (gn_mvs_region_role)role, bytes + cursor, (size_t)length,
            (size_t)length, GN_MVS_LAYOUT_LINEAR};
        cursor += (size_t)length;
    }
    return cursor == size;
}
#endif

static int gn_mvs_qualify_execute_with_script(gn_instance *instance,
                                               const input_script *script,
                                               const active_schedule *active,
                                               const char *frame_output_path,
                                               uint32_t video_advance_frames) {
    if (instance == NULL) return 1;
    uint32_t last_pc = 0u;
    uint16_t last_opcode = 0u;
    uint64_t total_instructions = 0u;
    uint64_t total_cycles = 0u;
    local_profile profile = {0};
    uint32_t chunk_boundaries[MAX_RUN_CHUNKS] = {0};
    gn_mvs_bus_fault_observation previous_observation;
    memset(&previous_observation, 0, sizeof(previous_observation));
    int have_previous_observation =
        gn_observe_mvs_bus_fault(instance, &previous_observation,
                                 sizeof(previous_observation)) == GN_STATUS_OK;
    for (size_t iteration = 0u; iteration < MAX_RUN_CHUNKS; ++iteration) {
        gn_run_result result;
        const gn_status status = gn_run_mvs(instance, GN_MAX_CYCLE_BUDGET, &result);
        if (status != GN_STATUS_OK || result.reason == GN_RUN_ERROR) {
            if (active != NULL)
                return print_active_execution_error(instance, active, 0, 0u,
                                                     NULL, 0u);
            return print_native_execution_error(instance);
        }
        last_pc = result.boundary_pc;
        last_opcode = result.instruction_register;
        chunk_boundaries[profile.chunks++] = result.boundary_pc;
        total_instructions += result.instructions;
        total_cycles += result.elapsed_cycles;
        gn_mvs_bus_fault_observation current_observation;
        memset(&current_observation, 0, sizeof(current_observation));
        if (gn_observe_mvs_bus_fault(instance, &current_observation,
                                     sizeof(current_observation)) == GN_STATUS_OK) {
            if (have_previous_observation != 0)
                count_state_transition(&profile, &previous_observation,
                                       &current_observation);
            previous_observation = current_observation;
            have_previous_observation = 1;
        }
        if (script != NULL) {
            gn_mvs_attract_verdict verdict;
            if (get_attract_start(instance, &verdict))
                return run_scripted_start(instance, profile.chunks, &verdict,
                                          script, frame_output_path, active);
        } else {
            const int attract_status = report_attract_start(
                instance, profile.chunks, frame_output_path,
                video_advance_frames);
            if (attract_status < 0) return 1;
            if (attract_status > 0) return 0;
        }
        if (result.reason == GN_RUN_FAULT) {
            if (active != NULL) {
                print_active_guest_fault(instance, &result, 0,
                    active->active_frames, 0u, active->captures,
                    active->capture_count, NULL, 0u);
                return 0;
            }
            print_unsupported_guest_event(instance, &result,
                                          total_instructions != 0u, 0, 0u, 0u);
            return 0;
        }
        if (result.reason == GN_RUN_STOPPED) {
            puts("{\"status\":\"guest_stopped\",\"guest_executed\":true}");
            return 0;
        }
    }
    gn_mvs_bus_fault_observation observation;
    memset(&observation, 0, sizeof(observation));
    (void)gn_observe_mvs_bus_fault(instance, &observation, sizeof(observation));
    profile.watchdog_pet_count = observation.mame_watchdog_pet_count;
    profile.watchdog_reset_count = observation.mame_watchdog_reset_count;
    profile.repeated_boundary_suffix =
        (uint8_t)repeated_boundary_suffix(chunk_boundaries, profile.chunks);
    owned_cpu_fetch_trace_event fetches[OWNED_CPU_FETCH_TRACE_CAPACITY];
    size_t fetch_count = 0u;
    (void)gn_private_mvs_fetch_trace(instance, fetches,
                                     OWNED_CPU_FETCH_TRACE_CAPACITY, &fetch_count);
    printf("{\"status\":\"guest_instruction_budget_exhausted\",\"guest_executed\":true,"
           "\"profile\":{\"chunks\":%u,\"stable_chunks\":%u,"
           "\"output_transition_chunks\":%u,\"video_transition_chunks\":%u,"
           "\"bank_transition_chunks\":%u,\"watchdog_pet_count\":%u,"
           "\"watchdog_reset_count\":%u,\"repeated_boundary_suffix\":%s},"
           "\"last_execution\":{\"pc\":%u,\"opcode\":%u,\"instructions\":%llu,"
           "\"elapsed_cycles\":%llu,\"mame_watchdog_reset_count\":%u},"
           "\"recent_fetches\":[",
           profile.chunks, profile.stable_chunks,
           profile.output_transition_chunks, profile.video_transition_chunks,
           profile.bank_transition_chunks, profile.watchdog_pet_count,
           profile.watchdog_reset_count,
           profile.repeated_boundary_suffix != 0u ? "true" : "false",
           last_pc, (unsigned)last_opcode, (unsigned long long)total_instructions,
           (unsigned long long)total_cycles,
           observation.mame_watchdog_reset_count);
    for (size_t index = 0u; index < fetch_count; ++index) {
        printf("%s{\"pc\":%u,\"word\":%u,\"cursor\":%u,\"run\":%llu,\"cycles\":%llu}",
               index == 0u ? "" : ",", fetches[index].prefetch_pc,
               (unsigned)fetches[index].fetched_word,
               fetches[index].resulting_cursor,
               (unsigned long long)fetches[index].run_sequence,
               (unsigned long long)fetches[index].total_cycles);
    }
    printf("],");
    print_diagnosis(instance);
    puts("}");
    return 0;
}

int gn_mvs_qualify_execute(gn_instance *instance) {
    return gn_mvs_qualify_execute_with_script(instance, NULL, NULL, NULL, 0u);
}

#if defined(GLUEYNEO_SDK_TEST_HOOKS) && defined(GN_MVS_QUALIFY_NO_MAIN)
/* Test-only entry points exercise the real loops and runtime, without adding
 * failure injection or alternate execution behavior to the shipping runner. */
int gn_mvs_qualify_test_active(gn_instance *instance, int phase,
                              const char *capture_directory) {
    const input_script script = {1u, 2u};
    active_schedule active;
    memset(&active, 0, sizeof(active));
    active.active_frames = 3u;
    active.input_count = 2u;
    active.inputs[0].frame = 0u;
    active.inputs[0].mask = 0u;
    active.inputs[1].frame = 1u;
    active.inputs[1].mask = GN_MVS_INPUT_P1_RIGHT;
    active.capture_count = 2u;
    active.captures[0] = 0u;
    active.captures[1] = 1u;
    active.capture_directory = capture_directory;
    if (phase == 0)
        return gn_mvs_qualify_execute_with_script(instance, &script, &active,
                                                 NULL, 0u);
    if (phase == 1) {
        const gn_mvs_attract_verdict verdict = {0};
        return run_scripted_start(instance, 0u, &verdict, &script, NULL, &active);
    }
    return run_active_frames(instance, &active, 1);
}
#endif

#ifndef GN_MVS_QUALIFY_NO_MAIN
static int parse_decimal_u32(const char **cursor, uint32_t *out_value) {
    if (cursor == NULL || *cursor == NULL || out_value == NULL ||
        **cursor < '0' || **cursor > '9') return 0;
    uint32_t value = 0u;
    do {
        const uint32_t digit = (uint32_t)(**cursor - '0');
        if (value > (UINT32_MAX - digit) / 10u) return 0;
        value = value * 10u + digit;
        ++*cursor;
    } while (**cursor >= '0' && **cursor <= '9');
    *out_value = value;
    return 1;
}

static int parse_active_inputs(const char *text, active_schedule *schedule) {
    if (text == NULL || schedule == NULL || *text == '\0' ||
        strlen(text) > MAX_ACTIVE_SCHEDULE_BYTES) return 0;
    const char *cursor = text;
    uint32_t previous_frame = 0u;
    int have_previous = 0;
    while (*cursor != '\0') {
        if (schedule->input_count == MAX_ACTIVE_INPUT_EVENTS) return 0;
        uint32_t frame = 0u;
        if (!parse_decimal_u32(&cursor, &frame) || *cursor != ':') return 0;
        ++cursor;
        if (frame >= schedule->active_frames ||
            (have_previous != 0 && frame <= previous_frame) ||
            cursor[0] != '0' || cursor[1] != 'x') return 0;
        cursor += 2;
        if (*cursor == '\0') return 0;
        uint32_t mask = 0u;
        size_t digits = 0u;
        while (*cursor != '\0' && *cursor != ',') {
            uint32_t digit;
            if (*cursor >= '0' && *cursor <= '9') digit = (uint32_t)(*cursor - '0');
            else if (*cursor >= 'a' && *cursor <= 'f') digit = (uint32_t)(*cursor - 'a') + 10u;
            else if (*cursor >= 'A' && *cursor <= 'F') digit = (uint32_t)(*cursor - 'A') + 10u;
            else return 0;
            if (mask > (UINT32_MAX - digit) / 16u) return 0;
            mask = mask * 16u + digit;
            ++cursor;
            ++digits;
        }
        if (digits == 0u || (mask & ~GN_MVS_INPUT_SUPPORTED_MASK) != 0u)
            return 0;
        schedule->inputs[schedule->input_count++] =
            (active_input_event){frame, mask};
        previous_frame = frame;
        have_previous = 1;
        if (*cursor == ',') {
            ++cursor;
            if (*cursor == '\0') return 0;
        }
    }
    return schedule->input_count != 0u;
}

static int parse_capture_frames(const char *text, active_schedule *schedule) {
    if (text == NULL || schedule == NULL || *text == '\0' ||
        strlen(text) > MAX_ACTIVE_SCHEDULE_BYTES) return 0;
    const char *cursor = text;
    uint32_t previous_frame = 0u;
    int have_previous = 0;
    while (*cursor != '\0') {
        if (schedule->capture_count == MAX_CAPTURE_FRAMES) return 0;
        uint32_t frame = 0u;
        if (!parse_decimal_u32(&cursor, &frame) ||
            frame >= schedule->active_frames ||
            (have_previous != 0 && frame <= previous_frame)) return 0;
        schedule->captures[schedule->capture_count++] = frame;
        previous_frame = frame;
        have_previous = 1;
        if (*cursor == ',') {
            ++cursor;
            if (*cursor == '\0') return 0;
        } else if (*cursor != '\0') {
            return 0;
        }
    }
    return schedule->capture_count != 0u;
}

static int sound_window_name_valid(const char *name, size_t size) {
    static const char *const allowed[] = {
        "music", "fire", "control", "release"
    };
    for (size_t index = 0u; index < sizeof(allowed) / sizeof(allowed[0]); ++index) {
        if (strlen(allowed[index]) == size &&
            memcmp(name, allowed[index], size) == 0) return 1;
    }
    return 0;
}

static int parse_sound_windows(const char *text, active_schedule *schedule) {
    if (text == NULL || schedule == NULL || *text == '\0' ||
        strlen(text) > MAX_ACTIVE_SCHEDULE_BYTES) return 0;
    const char *cursor = text;
    while (*cursor != '\0') {
        if (schedule->sound_window_count == MAX_SOUND_WINDOWS) return 0;
        const char *name_start = cursor;
        while ((*cursor >= 'a' && *cursor <= 'z') || *cursor == '_') ++cursor;
        const size_t name_size = (size_t)(cursor - name_start);
        if (name_size == 0u || name_size >= MAX_SOUND_WINDOW_NAME_BYTES ||
            *cursor != ':' || !sound_window_name_valid(name_start, name_size))
            return 0;
        for (size_t index = 0u; index < schedule->sound_window_count; ++index) {
            if (strlen(schedule->sound_windows[index].name) == name_size &&
                memcmp(schedule->sound_windows[index].name,
                       name_start, name_size) == 0) return 0;
        }
        ++cursor;
        uint32_t first = 0u, last = 0u;
        if (!parse_decimal_u32(&cursor, &first) || *cursor != '-') return 0;
        ++cursor;
        if (!parse_decimal_u32(&cursor, &last) || last < first ||
            last - first >= MAX_SOUND_WINDOW_FRAMES ||
            last >= schedule->active_frames ||
            (*cursor != '\0' && *cursor != ',')) return 0;
        active_sound_window *window =
            &schedule->sound_windows[schedule->sound_window_count++];
        memcpy(window->name, name_start, name_size);
        window->name[name_size] = '\0';
        window->first_frame = first;
        window->last_frame = last;
        if (*cursor == ',') {
            ++cursor;
            if (*cursor == '\0') return 0;
        }
    }
    return schedule->sound_window_count != 0u;
}

#endif

static int active_sound_window_path(const active_schedule *schedule,
                                    const active_sound_window *window,
                                    char *out_path, size_t capacity) {
    if (schedule == NULL || window == NULL || schedule->capture_directory == NULL ||
        out_path == NULL || capacity == 0u) return 0;
    const int length = snprintf(out_path, capacity, "%s/sound-%s.s16le",
                                schedule->capture_directory, window->name);
    return length > 0 && (size_t)length < capacity;
}

static int active_sound_window_open(const active_schedule *schedule,
                                    active_sound_window *window) {
    char path[192];
    if (!active_sound_window_path(schedule, window, path, sizeof(path))) return 0;
#if defined(_MSC_VER)
    window->pcm_file = NULL;
    if (fopen_s(&window->pcm_file, path, "wbx") != 0) return 0;
#else
    window->pcm_file = fopen(path, "wbx");
#endif
    return window->pcm_file != NULL;
}

static int active_sound_window_write(active_sound_window *window,
                                     const int16_t *samples,
                                     size_t frames) {
    if (window == NULL || window->pcm_file == NULL ||
        (frames != 0u && samples == NULL) ||
        frames > GN_MVS_AUDIO_CAPACITY_FRAMES_V1 ||
        window->pcm_bytes > UINT64_MAX - (uint64_t)frames * UINT64_C(4))
        return 0;
    uint8_t bytes[GN_MVS_AUDIO_CAPACITY_FRAMES_V1 * 2u * sizeof(int16_t)];
    const size_t values = frames * (size_t)2u;
    for (size_t index = 0u; index < values; ++index) {
        const uint16_t sample = (uint16_t)samples[index];
        bytes[index * 2u] = (uint8_t)sample;
        bytes[index * 2u + 1u] = (uint8_t)(sample >> 8);
    }
    const size_t byte_count = values * sizeof(int16_t);
    if (byte_count != 0u && fwrite(bytes, 1u, byte_count, window->pcm_file) != byte_count)
        return 0;
    window->pcm_bytes += byte_count;
    return 1;
}

static int active_sound_windows_close(active_schedule *schedule) {
    if (schedule == NULL) return 0;
    int ok = 1;
    for (size_t index = 0u; index < schedule->sound_window_count; ++index) {
        active_sound_window *window = &schedule->sound_windows[index];
        if (window->pcm_file != NULL) {
            if (fclose(window->pcm_file) != 0) ok = 0;
            window->pcm_file = NULL;
        }
    }
    return ok;
}

static int active_sound_window_contains(const active_sound_window *window,
                                        uint32_t frame) {
    return window != NULL && window->first_frame <= frame &&
           frame <= window->last_frame;
}

static int active_sound_chip_frame_capture(
        active_sound_window *window, uint32_t frame,
        const gn_mvs_sound_chip_observation *chip) {
    if (window == NULL || chip == NULL ||
        window->completed_frames >= MAX_SOUND_WINDOW_FRAMES) return 0;
    const gn_mvs_sound_chip_observation *previous =
        &window->previous_chip_observation;
    const int chip_reset =
        chip->clocks < previous->clocks ||
        chip->fm_key_on_writes < previous->fm_key_on_writes ||
        chip->fm_key_off_writes < previous->fm_key_off_writes ||
        chip->fm_register_writes < previous->fm_register_writes ||
        chip->ssg_register_writes < previous->ssg_register_writes ||
        chip->ssg_volume_writes < previous->ssg_volume_writes ||
        chip->adpcm_a_register_writes < previous->adpcm_a_register_writes ||
        chip->adpcm_a_control_writes < previous->adpcm_a_control_writes ||
        chip->adpcm_a_sample_reads < previous->adpcm_a_sample_reads ||
        chip->adpcm_b_register_writes < previous->adpcm_b_register_writes ||
        chip->adpcm_b_control_writes < previous->adpcm_b_control_writes ||
        chip->adpcm_b_sample_reads < previous->adpcm_b_sample_reads ||
        chip->native_nonzero_frames < previous->native_nonzero_frames;
    active_sound_chip_frame *entry =
        &window->chip_frames[window->completed_frames];
    entry->frame = frame;
    entry->chip_reset = (uint8_t)(chip_reset != 0);
#define ACTIVE_SOUND_COUNTER_DELTA(field) \
    (chip_reset != 0 ? chip->field : chip->field - previous->field)
    entry->chip_clocks = ACTIVE_SOUND_COUNTER_DELTA(clocks);
    entry->fm_key_on_writes = ACTIVE_SOUND_COUNTER_DELTA(fm_key_on_writes);
    entry->fm_key_off_writes = ACTIVE_SOUND_COUNTER_DELTA(fm_key_off_writes);
    entry->fm_register_writes = ACTIVE_SOUND_COUNTER_DELTA(fm_register_writes);
    entry->ssg_register_writes = ACTIVE_SOUND_COUNTER_DELTA(ssg_register_writes);
    entry->ssg_volume_writes = ACTIVE_SOUND_COUNTER_DELTA(ssg_volume_writes);
    entry->adpcm_a_register_writes =
        ACTIVE_SOUND_COUNTER_DELTA(adpcm_a_register_writes);
    entry->adpcm_a_control_writes =
        ACTIVE_SOUND_COUNTER_DELTA(adpcm_a_control_writes);
    entry->adpcm_a_reads = ACTIVE_SOUND_COUNTER_DELTA(adpcm_a_sample_reads);
    entry->adpcm_b_register_writes =
        ACTIVE_SOUND_COUNTER_DELTA(adpcm_b_register_writes);
    entry->adpcm_b_control_writes =
        ACTIVE_SOUND_COUNTER_DELTA(adpcm_b_control_writes);
    entry->adpcm_b_reads = ACTIVE_SOUND_COUNTER_DELTA(adpcm_b_sample_reads);
    entry->native_nonzero_frames =
        ACTIVE_SOUND_COUNTER_DELTA(native_nonzero_frames);
#undef ACTIVE_SOUND_COUNTER_DELTA
    window->previous_chip_observation = *chip;
    return 1;
}

static void print_active_sound_windows(const active_schedule *schedule) {
    printf(",\"sound_windows\":[");
    if (schedule == NULL) {
        puts("]");
        return;
    }
    for (size_t index = 0u; index < schedule->sound_window_count; ++index) {
        const active_sound_window *window = &schedule->sound_windows[index];
        char path[192];
        const int path_valid = active_sound_window_path(
            schedule, window, path, sizeof(path));
        printf("%s{\"name\":\"%s\",\"first_frame\":%u,"
               "\"last_frame\":%u,\"completed_frames\":%u,"
               "\"actual_cycles\":%llu,\"audio_frames_generated\":%llu,"
               "\"audio_frames_delivered\":%llu,\"audio_frames_discarded\":%llu,"
               "\"pcm_bytes\":%llu,\"pcm_file\":\"sound-%s.s16le\","
               "\"frame_observations\":[",
               index == 0u ? "" : ",", window->name, window->first_frame,
               window->last_frame, window->completed_frames,
               (unsigned long long)window->actual_cycles,
               (unsigned long long)window->audio_frames_generated,
               (unsigned long long)window->audio_frames_delivered,
               (unsigned long long)window->audio_frames_discarded,
               (unsigned long long)window->pcm_bytes, window->name);
        (void)path_valid;
        for (uint32_t frame_index = 0u;
             frame_index < window->completed_frames; ++frame_index) {
            printf("%s{\"frame\":%u,\"input_mask\":%u,"
                   "\"elapsed_cycles\":%llu,\"audio_frames\":%u}",
                   frame_index == 0u ? "" : ",",
                   window->first_frame + frame_index,
                   window->input_masks[frame_index],
                   (unsigned long long)window->elapsed_cycles[frame_index],
                   window->audio_frames[frame_index]);
        }
        printf("],\"chip_frames\":[");
        for (uint32_t frame_index = 0u;
             frame_index < window->completed_frames; ++frame_index) {
            const active_sound_chip_frame *entry =
                &window->chip_frames[frame_index];
            printf("%s{\"frame\":%u,\"chip_reset\":%s,"
                   "\"chip_clocks\":%llu,"
                   "\"fm_key_on_writes\":%llu,\"fm_key_off_writes\":%llu,"
                   "\"fm_register_writes\":%llu,"
                   "\"ssg_register_writes\":%llu,\"ssg_volume_writes\":%llu,"
                   "\"adpcm_a_register_writes\":%llu,"
                   "\"adpcm_a_control_writes\":%llu,\"adpcm_a_reads\":%llu,"
                   "\"adpcm_b_register_writes\":%llu,"
                   "\"adpcm_b_control_writes\":%llu,\"adpcm_b_reads\":%llu,"
                   "\"native_nonzero_frames\":%llu}",
                   frame_index == 0u ? "" : ",", entry->frame,
                   entry->chip_reset != 0u ? "true" : "false",
                   (unsigned long long)entry->chip_clocks,
                   (unsigned long long)entry->fm_key_on_writes,
                   (unsigned long long)entry->fm_key_off_writes,
                   (unsigned long long)entry->fm_register_writes,
                   (unsigned long long)entry->ssg_register_writes,
                   (unsigned long long)entry->ssg_volume_writes,
                   (unsigned long long)entry->adpcm_a_register_writes,
                   (unsigned long long)entry->adpcm_a_control_writes,
                   (unsigned long long)entry->adpcm_a_reads,
                   (unsigned long long)entry->adpcm_b_register_writes,
                   (unsigned long long)entry->adpcm_b_control_writes,
                   (unsigned long long)entry->adpcm_b_reads,
                   (unsigned long long)entry->native_nonzero_frames);
        }
        printf("],\"chip_observation\":{");
        const gn_mvs_sound_chip_observation *chip = &window->chip_observation;
        printf("\"version\":%u,\"clocks\":%llu,"
               "\"register_writes\":%llu,\"ssg_register_writes\":%llu,"
               "\"ssg_volume_writes\":%llu,\"control_register_writes\":%llu,"
               "\"fm_register_writes\":%llu,"
               "\"fm_key_on_writes\":%llu,\"fm_key_off_writes\":%llu,"
               "\"fm_frequency_writes\":%llu,\"fm_level_writes\":%llu,"
               "\"fm_pan_writes\":%llu,"
               "\"adpcm_a_register_writes\":%llu,"
               "\"adpcm_a_control_writes\":%llu,"
               "\"adpcm_b_register_writes\":%llu,"
               "\"adpcm_b_control_writes\":%llu,"
               "\"adpcm_a_reads\":%llu,\"adpcm_b_reads\":%llu,"
               "\"timer_programs\":%llu,\"timer_expirations\":%llu,"
               "\"irq_assertions\":%llu,\"irq_deassertions\":%llu,"
               "\"native_frames\":%llu,\"native_nonzero_frames\":%llu,"
               "\"native_stereo_nonzero_frames\":%llu,"
               "\"native_ssg_nonzero_frames\":%llu,\"native_peak\":%u,"
               "\"event_dropped\":%u,\"register_events\":[",
               chip->version, (unsigned long long)chip->clocks,
               (unsigned long long)chip->register_writes,
               (unsigned long long)chip->ssg_register_writes,
               (unsigned long long)chip->ssg_volume_writes,
               (unsigned long long)chip->control_register_writes,
               (unsigned long long)chip->fm_register_writes,
               (unsigned long long)chip->fm_key_on_writes,
               (unsigned long long)chip->fm_key_off_writes,
               (unsigned long long)chip->fm_frequency_writes,
               (unsigned long long)chip->fm_level_writes,
               (unsigned long long)chip->fm_pan_writes,
               (unsigned long long)chip->adpcm_a_register_writes,
               (unsigned long long)chip->adpcm_a_control_writes,
               (unsigned long long)chip->adpcm_b_register_writes,
               (unsigned long long)chip->adpcm_b_control_writes,
               (unsigned long long)chip->adpcm_a_sample_reads,
               (unsigned long long)chip->adpcm_b_sample_reads,
               (unsigned long long)chip->timer_programs,
               (unsigned long long)chip->timer_expirations,
               (unsigned long long)chip->irq_assertions,
               (unsigned long long)chip->irq_deassertions,
               (unsigned long long)chip->native_frames,
               (unsigned long long)chip->native_nonzero_frames,
               (unsigned long long)chip->native_stereo_nonzero_frames,
               (unsigned long long)chip->native_ssg_nonzero_frames,
               chip->native_peak, chip->event_dropped);
        for (uint32_t event_index = 0u;
             event_index < chip->event_count; ++event_index) {
            const gn_mvs_sound_register_event *event = &chip->events[event_index];
            printf("%s{\"clock\":%llu,\"port\":%u,\"bank\":%u,"
                   "\"register\":%u,\"value\":%u,\"family\":%u}",
                   event_index == 0u ? "" : ",",
                   (unsigned long long)event->clock, event->port, event->bank,
                   event->reg, event->value, event->family);
        }
        printf("]},\"board_observations\":[");
        for (uint32_t frame_index = 0u;
             frame_index < window->completed_frames; ++frame_index) {
            const gn_mvs_sound_board_observation *board =
                &window->board_observations[frame_index];
            const int sound_cpu_reset = frame_index != 0u &&
                board->sound_cpu_cycles <
                    window->board_observations[frame_index - 1u].sound_cpu_cycles;
            printf("%s{\"frame\":%u,\"sound_cpu_reset\":%s,"
                   "\"cart_selected\":%u,"
                   "\"command\":%u,\"reply\":%u,\"command_pending\":%u,"
                   "\"nmi_enabled\":%u,\"ym_irq\":%u,\"banks\":[%u,%u,%u,%u],"
                   "\"sound_cpu_pc\":%u,\"sound_cpu_cycles\":%llu}",
                   frame_index == 0u ? "" : ",",
                   window->first_frame + frame_index,
                   sound_cpu_reset ? "true" : "false", board->cart_selected,
                   board->command, board->reply, board->command_pending,
                   board->nmi_enabled, board->ym_irq, board->banks[0],
                   board->banks[1], board->banks[2], board->banks[3],
                   board->sound_cpu_pc,
                   (unsigned long long)board->sound_cpu_cycles);
        }
        printf("]}");
    }
    printf("]");
}

#ifndef GN_MVS_QUALIFY_NO_MAIN
static int parse_video_advance_frames(const char *text, uint32_t *out_frames) {
    if (text == NULL || out_frames == NULL || *text == '\0') return 0;
    uint32_t value = 0u;
    for (const char *cursor = text; *cursor != '\0'; ++cursor) {
        if (*cursor < '0' || *cursor > '9') return 0;
        const uint32_t digit = (uint32_t)(*cursor - '0');
        if (digit > MAX_VIDEO_ADVANCE_FRAMES ||
            value > (MAX_VIDEO_ADVANCE_FRAMES - digit) / 10u) return 0;
        value = value * 10u + digit;
    }
    if (value == 0u || value > MAX_VIDEO_ADVANCE_FRAMES) return 0;
    *out_frames = value;
    return 1;
}

int main(int argc, char **argv) {
    if (argc < 2 || argv[1] == NULL || argv[1][0] == '\0') return 2;
    input_script script;
    const input_script *script_pointer = NULL;
    active_schedule active;
    memset(&active, 0, sizeof(active));
    const active_schedule *active_pointer = NULL;
    const char *frame_inputs_text = NULL;
    const char *capture_frames_text = NULL;
    const char *sound_windows_text = NULL;
    const char *frame_output_path = NULL;
    uint32_t video_advance_frames = 0u;
    int video_advance_frames_set = 0;
    int video_state_diagnostic = 0;
    for (int index = 2; index < argc; ++index) {
        if (strcmp(argv[index], "--input-script") == 0 &&
            index + 1 < argc && script_pointer == NULL) {
            if (!parse_input_script(argv[++index], &script)) return 2;
            script_pointer = &script;
        } else if (strcmp(argv[index], "--frame-output") == 0 &&
                   index + 1 < argc && frame_output_path == NULL) {
            frame_output_path = argv[++index];
            if (!valid_frame_output_path(frame_output_path)) return 2;
        } else if (strcmp(argv[index], "--video-advance-frames") == 0 &&
                   index + 1 < argc && video_advance_frames_set == 0) {
            if (!parse_video_advance_frames(argv[++index],
                                            &video_advance_frames)) return 2;
            video_advance_frames_set = 1;
        } else if (strcmp(argv[index], "--active-frames") == 0 &&
                   index + 1 < argc && active.active_frames == 0u) {
            const char *text = argv[++index];
            if (!parse_decimal_u32(&text, &active.active_frames) ||
                *text != '\0' || active.active_frames == 0u ||
                active.active_frames > MAX_ACTIVE_FRAMES) return 2;
            active_pointer = &active;
        } else if (strcmp(argv[index], "--frame-inputs") == 0 &&
                   index + 1 < argc && frame_inputs_text == NULL) {
            frame_inputs_text = argv[++index];
        } else if (strcmp(argv[index], "--capture-frames") == 0 &&
                   index + 1 < argc && capture_frames_text == NULL) {
            capture_frames_text = argv[++index];
        } else if (strcmp(argv[index], "--capture-directory") == 0 &&
                   index + 1 < argc && active.capture_directory == NULL) {
            active.capture_directory = argv[++index];
        } else if (strcmp(argv[index], "--sound-windows") == 0 &&
                   index + 1 < argc && sound_windows_text == NULL) {
            sound_windows_text = argv[++index];
        } else if (strcmp(argv[index], "--video-state-diagnostic") == 0 &&
                   video_state_diagnostic == 0) {
            video_state_diagnostic = 1;
        } else {
            return 2;
        }
    }
    if ((frame_inputs_text != NULL || capture_frames_text != NULL ||
         sound_windows_text != NULL || active.capture_directory != NULL) &&
        active_pointer == NULL) return 2;
    if (active_pointer != NULL) {
        if (frame_inputs_text != NULL &&
            !parse_active_inputs(frame_inputs_text, &active)) return 2;
        if (capture_frames_text != NULL && active.capture_directory == NULL)
            return 2;
        if (active.capture_directory != NULL &&
            !valid_active_capture_directory(active.capture_directory)) return 2;
        if (capture_frames_text != NULL &&
            !parse_capture_frames(capture_frames_text, &active)) return 2;
        if (sound_windows_text != NULL &&
            (active.capture_directory == NULL ||
             !parse_sound_windows(sound_windows_text, &active))) return 2;
    }
    if ((script_pointer != NULL && video_advance_frames_set != 0) ||
        (active_pointer != NULL &&
         (script_pointer == NULL || video_advance_frames_set != 0 ||
          frame_output_path != NULL || video_state_diagnostic != 0)) ||
        (video_state_diagnostic != 0 && frame_output_path == NULL)) return 2;
    FILE *file = fopen(argv[1], "rb");
    if (file == NULL || fseek(file, 0, SEEK_END) != 0) {
        if (file != NULL) fclose(file);
        puts("{\"status\":\"normalized_bundle_unavailable\"}");
        return 1;
    }
    const long length = ftell(file);
    if (length < 0 || (unsigned long)length > MAX_BUNDLE_BYTES ||
        fseek(file, 0, SEEK_SET) != 0) {
        fclose(file); puts("{\"status\":\"normalized_bundle_out_of_bounds\"}"); return 1;
    }
    uint8_t *bytes = (uint8_t *)malloc((size_t)length);
    if (bytes == NULL || fread(bytes, 1u, (size_t)length, file) != (size_t)length) {
        free(bytes); fclose(file);
        puts("{\"status\":\"normalized_bundle_read_failed\"}"); return 1;
    }
    fclose(file);
    gn_mvs_manifest manifest;
    gn_mvs_manifest_v3 manifest_v3;
    const uint32_t bundle_version = (size_t)length >= HEADER_BYTES
        ? read32be(bytes + 4u) : 0u;
    const int is_v3 = bundle_version == GN_MVS_MANIFEST_VERSION_ZOOM;
    if ((is_v3 && !gn_mvs_qualify_parse_bundle_v3(
                       bytes, (size_t)length, &manifest_v3)) ||
        (!is_v3 && !gn_mvs_qualify_parse_bundle(
                        bytes, (size_t)length, &manifest))) {
        free(bytes); puts("{\"status\":\"normalized_bundle_malformed\"}"); return 1;
    }
    gn_instance *instance = NULL;
    if (gn_create(&instance) != GN_STATUS_OK || instance == NULL) {
        free(bytes); puts("{\"status\":\"native_instance_unavailable\"}"); return 1;
    }
    const gn_status load_status = is_v3
        ? gn_load_mvs_v3(instance, &manifest_v3)
        : gn_load_mvs(instance, &manifest);
    free(bytes);
    if (load_status != GN_STATUS_OK) {
        gn_destroy(instance); puts("{\"status\":\"normalized_profile_rejected\"}"); return 1;
    }
    if (bundle_version == GN_MVS_MANIFEST_VERSION_LEGACY) {
        /* Legacy bundles can load safely, but the board resets to the audio
         * BIOS source and that sixth-region contract has no audio-BIOS bytes.
         * Report the missing source before guest execution instead of
         * substituting cartridge bytes or turning the stop into a CPU error. */
        gn_destroy(instance);
        puts("{\"status\":\"missing_audio_region\"}");
        return 0;
    }
    const int result = gn_mvs_qualify_execute_with_script(
        instance, script_pointer, active_pointer, frame_output_path,
        video_advance_frames);
    if (video_state_diagnostic != 0)
        print_private_video_activity(instance);
    gn_destroy(instance);
    return result;
}
#endif
