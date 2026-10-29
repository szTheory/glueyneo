/* SPDX-License-Identifier: MIT */
#include "../support/portable_stdio.h"

#include "glueyneo/glueyneo.h"
#include "libretro.h"

#if defined(_WIN32)
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#else
#include <dlfcn.h>
#endif
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CONTENT_BYTES 602u
#define FRAME_WIDTH 320u
#define FRAME_HEIGHT 224u
#define FRAME_PITCH (FRAME_WIDTH * sizeof(uint32_t))
#define FRAME_BYTES (FRAME_PITCH * FRAME_HEIGHT)
#define SOUND_AUDIO_CAPACITY GN_MVS_AUDIO_CAPACITY_FRAMES_V1
#define SOUND_CONTENT_LIMIT (GN_MVS_MAX_MEDIA_BYTES + 16u + 8u * 12u)
#define MVS_SAVE_RAM_BYTES ((size_t)0x10000u)
#define MVS_WORK_RAM_BYTES ((size_t)0x10000u)
#define MVS_STATE_HEADER_BYTES 72u
#define MVS_STATE_MEMORY_SECTION 2u

size_t public_save_guest_size(void);
int public_save_guest_build(uint8_t *bundle, size_t capacity);

static uint8_t content[CONTENT_BYTES];
static uint32_t observed_pixels[FRAME_WIDTH * FRAME_HEIGHT];
static unsigned poll_calls;
static unsigned video_calls;
static unsigned audio_calls;
static unsigned audio_batch_calls;
static unsigned format_calls;
static unsigned right_state;
static bool reject_pixel_format;
static bool callback_frame_valid;
static bool sound_mode;
static uint16_t sound_buttons;
enum sound_batch_return_mode {
    SOUND_BATCH_FULL = 0,
    SOUND_BATCH_SHORT,
    SOUND_BATCH_ZERO,
    SOUND_BATCH_OVER
};
static enum sound_batch_return_mode sound_batch_return_mode;
static uint8_t *sound_content;
static size_t sound_content_size;
static int16_t observed_audio[SOUND_AUDIO_CAPACITY * 2u];
static size_t observed_audio_frames;
static size_t last_batch_offered_frames;
static size_t last_batch_reported_frames;
static size_t sound_total_submitted_frames;
static size_t sound_total_processed_frames;
static size_t sound_total_discarded_frames;
static size_t sound_total_unsubmitted_frames;
static size_t sound_total_generated_frames;
static uint32_t native_sound_pixels[FRAME_WIDTH * FRAME_HEIGHT];
static int16_t native_sound_audio[SOUND_AUDIO_CAPACITY * 2u];
static char log_lines[32][192];
static size_t log_line_count;
static unsigned failures;
static gn_instance *native_reference;
static uint64_t last_witness_elapsed_cycles;
static size_t last_witness_audio_frames;
static bool tap_output;
static unsigned tap_assertions;
static bool continuation_observer_output;

#define CHECK(condition, label) do { \
    const bool check_passed = (condition) ? true : false; \
    if (tap_output) { \
        ++tap_assertions; \
        fprintf(stdout, "%s %u - %s\n", check_passed ? "ok" : "not ok", \
                tap_assertions, label); \
    } else if (!check_passed) { \
        fprintf(stderr, "FAIL: %s\n", label); \
    } \
    if (!check_passed) ++failures; \
} while (0)

static void capture_log(enum retro_log_level level, const char *format, ...);

static bool environment_callback(unsigned command, void *data) {
    if (command == RETRO_ENVIRONMENT_GET_LOG_INTERFACE && data != NULL) {
        ((struct retro_log_callback *)data)->log = capture_log;
        return true;
    }
    if (command != RETRO_ENVIRONMENT_SET_PIXEL_FORMAT || data == NULL) return false;
    ++format_calls;
    if (*(enum retro_pixel_format *)data != RETRO_PIXEL_FORMAT_XRGB8888) return false;
    return !reject_pixel_format;
}

static void capture_log(enum retro_log_level level, const char *format, ...) {
    (void)level;
    if (continuation_observer_output) {
        char line[640];
        va_list arguments;
        va_start(arguments, format);
        const int length = vsnprintf(line, sizeof(line), format, arguments);
        va_end(arguments);
        static const char prefix[] = "glueyneo: continuation ";
        if (length > 0 && (size_t)length < sizeof(line) &&
            strncmp(line, prefix, sizeof(prefix) - 1u) == 0)
            (void)fputs(line, stdout);
        return;
    }
    if (log_line_count >= sizeof(log_lines) / sizeof(log_lines[0])) return;
    va_list arguments;
    va_start(arguments, format);
    (void)vsnprintf(log_lines[log_line_count], sizeof(log_lines[0]),
                    format, arguments);
    va_end(arguments);
    ++log_line_count;
}

static void video_callback(const void *data, unsigned width, unsigned height,
                           size_t pitch) {
    ++video_calls;
    callback_frame_valid = data != NULL && width == FRAME_WIDTH &&
        height == FRAME_HEIGHT && pitch == FRAME_PITCH;
    if (callback_frame_valid) memcpy(observed_pixels, data, FRAME_BYTES);
}

static void audio_callback(int16_t left, int16_t right) {
    if (sound_mode && observed_audio_frames < SOUND_AUDIO_CAPACITY) {
        observed_audio[observed_audio_frames * 2u] = left;
        observed_audio[observed_audio_frames * 2u + 1u] = right;
        ++observed_audio_frames;
        ++sound_total_submitted_frames;
        ++sound_total_processed_frames;
    }
    ++audio_calls;
}

static size_t audio_batch_callback(const int16_t *data, size_t frames) {
    size_t reported = frames;
    if (sound_mode) {
        last_batch_offered_frames = frames;
        last_batch_reported_frames = frames;
        if (data != NULL && frames <= SOUND_AUDIO_CAPACITY) {
            memcpy(observed_audio, data, frames * 2u * sizeof(int16_t));
            observed_audio_frames = frames;
        }
        sound_total_submitted_frames += frames;
        switch (sound_batch_return_mode) {
            case SOUND_BATCH_SHORT:
                reported = frames / 2u;
                break;
            case SOUND_BATCH_ZERO:
                reported = 0u;
                break;
            case SOUND_BATCH_OVER:
                reported = frames + 1u;
                break;
            case SOUND_BATCH_FULL:
            default:
                break;
        }
        last_batch_reported_frames = reported;
        const size_t processed = reported < frames ? reported : frames;
        sound_total_processed_frames += processed;
        sound_total_discarded_frames += frames - processed;
    }
    ++audio_batch_calls;
    return reported;
}

static void input_poll_callback(void) { ++poll_calls; }

static int16_t input_state_callback(unsigned port, unsigned device,
                                    unsigned index, unsigned id) {
    if (sound_mode) {
        CHECK(port == 0u && device == RETRO_DEVICE_JOYPAD && index == 0u,
              "sound input query uses player 1 RetroPad");
        if (id == RETRO_DEVICE_ID_JOYPAD_B ||
            id == RETRO_DEVICE_ID_JOYPAD_A)
            return (sound_buttons & (uint16_t)(UINT16_C(1) << id)) != 0u;
        if (id == RETRO_DEVICE_ID_JOYPAD_RIGHT)
            return right_state != 0u;
        return 0;
    }
    CHECK(port == 0u && device == RETRO_DEVICE_JOYPAD && index == 0u,
          "input query uses player 1 RetroPad");
    CHECK(id == RETRO_DEVICE_ID_JOYPAD_RIGHT,
          "input query uses RetroPad RIGHT");
    return id == RETRO_DEVICE_ID_JOYPAD_RIGHT ? (int16_t)right_state : 0;
}

static bool create_native_reference(void) {
    gn_manifest manifest;
    memset(&manifest, 0, sizeof(manifest));
    manifest.version = GN_MANIFEST_VERSION;
    manifest.profile = GN_PROFILE_PUBLIC_FIXTURE;
    manifest.region_count = 1u;
    manifest.regions[0] = (gn_region){
        0u, CONTENT_BYTES, content, sizeof(content), GN_REGION_ROM};
    if (gn_create(&native_reference) != GN_STATUS_OK) return false;
    if (gn_load(native_reference, &manifest) != GN_STATUS_OK) {
        gn_destroy(native_reference);
        native_reference = NULL;
        return false;
    }
    return true;
}

static bool advance_native_reference(uint32_t input, uint32_t *pixels) {
    const gn_frame_request request = {
        input, GN_PIXEL_XRGB8888, FRAME_WIDTH, FRAME_HEIGHT, FRAME_PITCH,
        (uint8_t *)pixels, FRAME_BYTES, NULL, 0u};
    gn_frame_result result;
    const gn_status status = gn_advance_frame(native_reference, &request, &result);
    return status == GN_STATUS_OK && result.reason == GN_RUN_STOPPED;
}

static bool read_content(const char *path) {
    FILE *file = gn_portable_fopen(path, "rb");
    if (file == NULL) return false;
    const size_t count = fread(content, 1u, sizeof(content), file);
    const int extra = fgetc(file);
    const int close_status = fclose(file);
    return count == sizeof(content) && extra == EOF && close_status == 0;
}

static void require_export(const char *name) {
#if defined(_WIN32)
    const HMODULE core = GetModuleHandleA("glueyneo_libretro.dll");
    CHECK(core != NULL && GetProcAddress(core, name) != NULL, name);
#else
    CHECK(dlsym(RTLD_DEFAULT, name) != NULL, name);
#endif
}

static void run_and_compare(bool right_pressed, const char *label) {
    const unsigned old_polls = poll_calls;
    const unsigned old_videos = video_calls;
    right_state = right_pressed ? 1u : 0u;
    callback_frame_valid = false;
    retro_run();
    CHECK(poll_calls == old_polls + 1u, "one input poll per retro_run");
    CHECK(video_calls == old_videos + 1u, "one video callback per retro_run");
    CHECK(callback_frame_valid, "native pixel buffer valid during video callback");
    uint32_t expected[FRAME_WIDTH * FRAME_HEIGHT];
    CHECK(advance_native_reference(right_pressed ? GN_INPUT_RIGHT : 0u, expected),
          "independent native comparison frame is valid");
    if (callback_frame_valid) {
        CHECK(memcmp(observed_pixels, expected, FRAME_BYTES) == 0, label);
    }
}

static uint32_t sound_read_u32_be(const uint8_t *bytes) {
    return ((uint32_t)bytes[0] << 24) | ((uint32_t)bytes[1] << 16) |
           ((uint32_t)bytes[2] << 8) | (uint32_t)bytes[3];
}

static bool read_sound_content(const char *path) {
    FILE *file = gn_portable_fopen(path, "rb");
    if (file == NULL) return false;
    if (fseek(file, 0L, SEEK_END) != 0) {
        (void)fclose(file);
        return false;
    }
    const long measured = ftell(file);
    if (measured < 0L || (uint64_t)measured > SOUND_CONTENT_LIMIT ||
        fseek(file, 0L, SEEK_SET) != 0) {
        (void)fclose(file);
        return false;
    }
    sound_content_size = (size_t)measured;
    sound_content = (uint8_t *)malloc(sound_content_size);
    if (sound_content == NULL) {
        (void)fclose(file);
        return false;
    }
    const size_t count = fread(sound_content, 1u, sound_content_size, file);
    const int extra = fgetc(file);
    const int close_status = fclose(file);
    return count == sound_content_size && extra == EOF && close_status == 0;
}

static bool create_native_sound_reference(void) {
    if (sound_content == NULL || sound_content_size < 16u ||
        memcmp(sound_content, "GNMV", 4u) != 0 ||
        sound_read_u32_be(sound_content + 4u) != GN_MVS_MANIFEST_VERSION_ZOOM ||
        sound_read_u32_be(sound_content + 8u) != GN_MVS_PROFILE_MSX ||
        sound_read_u32_be(sound_content + 12u) != GN_MVS_V3_MAX_REGIONS)
        return false;
    gn_mvs_manifest_v3 manifest;
    memset(&manifest, 0, sizeof(manifest));
    manifest.version = GN_MVS_MANIFEST_VERSION_ZOOM;
    manifest.profile = GN_MVS_PROFILE_MSX;
    manifest.region_count = GN_MVS_V3_MAX_REGIONS;
    size_t cursor = 16u;
    for (size_t index = 0u; index < manifest.region_count; ++index) {
        if (cursor > sound_content_size || sound_content_size - cursor < 12u)
            return false;
        const uint32_t role = sound_read_u32_be(sound_content + cursor);
        const uint32_t high = sound_read_u32_be(sound_content + cursor + 4u);
        const uint32_t low = sound_read_u32_be(sound_content + cursor + 8u);
        cursor += 12u;
        if (high != 0u || low == 0u || (size_t)low > sound_content_size - cursor)
            return false;
        manifest.regions[index] = (gn_mvs_region){
            (gn_mvs_region_role)role, sound_content + cursor, (size_t)low,
            (size_t)low, GN_MVS_LAYOUT_LINEAR};
        cursor += (size_t)low;
    }
    if (cursor != sound_content_size || gn_create(&native_reference) != GN_STATUS_OK)
        return false;
    if (gn_load_mvs_v3(native_reference, &manifest) != GN_STATUS_OK) {
        gn_destroy(native_reference);
        native_reference = NULL;
        return false;
    }
    return true;
}

static void run_and_compare_sound_frame(bool fire_pressed, const char *label) {
    const unsigned old_polls = poll_calls;
    const unsigned old_videos = video_calls;
    const unsigned old_batches = audio_batch_calls;
    right_state = 0u;
    sound_buttons = fire_pressed
        ? (uint16_t)(UINT16_C(1) << RETRO_DEVICE_ID_JOYPAD_B) : 0u;
    callback_frame_valid = false;
    observed_audio_frames = 0u;
    memset(observed_audio, 0, sizeof(observed_audio));
    retro_run();
    CHECK(poll_calls == old_polls + 1u, "one sound input poll per retro_run");
    CHECK(video_calls == old_videos + 1u, "one sound video callback per retro_run");
    CHECK(callback_frame_valid, "sound frame pixels are valid during callback");

    const uint32_t input_mask = fire_pressed ? GN_MVS_INPUT_P1_A : 0u;
    const gn_mvs_frame_request_v1 request = {
        GN_MVS_FRAME_REQUEST_V1_VERSION, input_mask, GN_PIXEL_XRGB8888,
        FRAME_WIDTH, FRAME_HEIGHT, FRAME_PITCH,
        (uint8_t *)native_sound_pixels, FRAME_BYTES, native_sound_audio,
        SOUND_AUDIO_CAPACITY
    };
    gn_mvs_frame_result_v1 result;
    memset(&result, 0, sizeof(result));
    CHECK(gn_mvs_advance_frame_v1(native_reference, &request, sizeof(request),
                                  &result, sizeof(result)) == GN_STATUS_OK,
          "native comparison advances one bounded MVS frame");
    CHECK(result.audio_frames_delivered == result.audio_frames_generated,
          "native comparison receives every generated PCM frame");
    sound_total_generated_frames += result.audio_frames_generated;
    CHECK(audio_batch_calls == old_batches + 1u,
          "one batch callback receives each nonempty MVS audio block");
    CHECK(observed_audio_frames == result.audio_frames_delivered,
          "batch callback frame count matches the native result");
    if (callback_frame_valid) {
        CHECK(memcmp(observed_pixels, native_sound_pixels, FRAME_BYTES) == 0,
              "same sound guest and input produce identical native/libretro video");
    }
    if (observed_audio_frames == result.audio_frames_delivered) {
        CHECK(memcmp(observed_audio, native_sound_audio,
                     observed_audio_frames * 2u * sizeof(int16_t)) == 0,
              label);
    }
}

static size_t count_log_lines_containing(const char *needle) {
    size_t matches = 0u;
    for (size_t index = 0u; index < log_line_count; ++index)
        if (strstr(log_lines[index], needle) != NULL) ++matches;
    return matches;
}

static int write_save_fixture(const char *path) {
    const size_t size = public_save_guest_size();
    if (path == NULL || size == 0u || size > SOUND_CONTENT_LIMIT) return 2;
    uint8_t *bundle = (uint8_t *)malloc(size);
    if (bundle == NULL || !public_save_guest_build(bundle, size)) {
        free(bundle);
        return 2;
    }
    FILE *file = gn_portable_fopen(path, "wb");
    if (file == NULL) {
        free(bundle);
        return 2;
    }
    const bool wrote_all = fwrite(bundle, 1u, size, file) == size;
    const int close_status = fclose(file);
    free(bundle);
    return wrote_all && close_status == 0 ? 0 : 2;
}

static bool make_mvs_without_audio_bios(const uint8_t *input_content,
                                        size_t content_size,
                                        uint8_t **out_content,
                                        size_t *out_content_size) {
    if (out_content != NULL) *out_content = NULL;
    if (out_content_size != NULL) *out_content_size = 0u;
    if (input_content == NULL || out_content == NULL || out_content_size == NULL ||
        content_size < 16u || memcmp(input_content, "GNMV", 4u) != 0 ||
        sound_read_u32_be(input_content + 4u) != GN_MVS_MANIFEST_VERSION_ZOOM ||
        sound_read_u32_be(input_content + 8u) != GN_MVS_PROFILE_MSX ||
        sound_read_u32_be(input_content + 12u) != GN_MVS_V3_MAX_REGIONS)
        return false;

    size_t cursor = 16u;
    size_t audio_descriptor = 0u;
    size_t audio_extent = 0u;
    bool found_audio_bios = false;
    bool found_y_zoom = false;
    for (size_t index = 0u; index < GN_MVS_V3_MAX_REGIONS; ++index) {
        if (cursor > content_size || content_size - cursor < 12u)
            return false;
        const size_t descriptor = cursor;
        const uint32_t role = sound_read_u32_be(input_content + cursor);
        const uint32_t extent = sound_read_u32_be(input_content + cursor + 8u);
        cursor += 12u;
        if (extent == 0u || (size_t)extent > content_size - cursor)
            return false;
        if (role == (uint32_t)GN_MVS_REGION_AUDIO_BIOS) {
            audio_descriptor = descriptor;
            audio_extent = (size_t)extent;
            found_audio_bios = true;
        }
        if (role == (uint32_t)GN_MVS_REGION_Y_ZOOM) found_y_zoom = true;
        cursor += (size_t)extent;
    }
    if (cursor != content_size || !found_audio_bios || !found_y_zoom ||
        audio_descriptor == 0u ||
        audio_extent > SIZE_MAX - audio_descriptor - 12u ||
        audio_descriptor + 12u + audio_extent > content_size)
        return false;

    const size_t after_audio = audio_descriptor + 12u + audio_extent;
    const size_t removed_size = 12u + audio_extent;
    const size_t variant_size = content_size - removed_size;
    uint8_t *variant = (uint8_t *)malloc(variant_size);
    if (variant == NULL) return false;
    memcpy(variant, input_content, audio_descriptor);
    memcpy(variant + audio_descriptor, input_content + after_audio,
           content_size - after_audio);
    variant[12] = 0u;
    variant[13] = 0u;
    variant[14] = 0u;
    variant[15] = (uint8_t)(GN_MVS_V3_MAX_REGIONS - 1u);
    *out_content = variant;
    *out_content_size = variant_size;
    return true;
}

static bool create_native_mvs_reference(void) {
    if (sound_content == NULL || sound_content_size < 16u ||
        memcmp(sound_content, "GNMV", 4u) != 0 ||
        sound_read_u32_be(sound_content + 4u) != GN_MVS_MANIFEST_VERSION_ZOOM ||
        sound_read_u32_be(sound_content + 8u) != GN_MVS_PROFILE_MSX ||
        sound_read_u32_be(sound_content + 12u) != GN_MVS_V3_MAX_REGIONS)
        return false;
    gn_mvs_manifest_v3 manifest;
    memset(&manifest, 0, sizeof(manifest));
    manifest.version = GN_MVS_MANIFEST_VERSION_ZOOM;
    manifest.profile = GN_MVS_PROFILE_MSX;
    manifest.region_count = GN_MVS_V3_MAX_REGIONS;
    size_t cursor = 16u;
    for (size_t index = 0u; index < manifest.region_count; ++index) {
        if (cursor > sound_content_size || sound_content_size - cursor < 12u)
            return false;
        const uint32_t role = sound_read_u32_be(sound_content + cursor);
        const uint32_t reserved = sound_read_u32_be(sound_content + cursor + 4u);
        const uint32_t extent = sound_read_u32_be(sound_content + cursor + 8u);
        cursor += 12u;
        if (reserved != 0u || extent == 0u ||
            (size_t)extent > sound_content_size - cursor) return false;
        manifest.regions[index] = (gn_mvs_region){
            (gn_mvs_region_role)role, sound_content + cursor, (size_t)extent,
            (size_t)extent, GN_MVS_LAYOUT_LINEAR};
        cursor += (size_t)extent;
    }
    if (cursor != sound_content_size || gn_create(&native_reference) != GN_STATUS_OK)
        return false;
    if (gn_load_mvs_v3(native_reference, &manifest) != GN_STATUS_OK) {
        gn_destroy(native_reference);
        native_reference = NULL;
        return false;
    }
    return true;
}

static bool load_mvs_callback_fixture(const char *path) {
    if (!read_sound_content(path)) return false;
    sound_mode = true;
    sound_batch_return_mode = SOUND_BATCH_FULL;
    poll_calls = 0u;
    video_calls = 0u;
    audio_calls = 0u;
    audio_batch_calls = 0u;
    observed_audio_frames = 0u;
    sound_buttons = 0u;
    right_state = 0u;
    retro_set_environment(environment_callback);
    retro_set_video_refresh(video_callback);
    retro_set_audio_sample(audio_callback);
    retro_set_audio_sample_batch(audio_batch_callback);
    retro_set_input_poll(input_poll_callback);
    retro_set_input_state(input_state_callback);
    retro_init();
    struct retro_game_info game = {
        NULL, sound_content, sound_content_size, NULL};
    return retro_load_game(&game);
}

static bool mvs_state_memory(const uint8_t *bytes, size_t length,
                             const uint8_t **out_work_ram,
                             const uint8_t **out_save_ram) {
    if (out_work_ram != NULL) *out_work_ram = NULL;
    if (out_save_ram != NULL) *out_save_ram = NULL;
    if (bytes == NULL || out_work_ram == NULL || out_save_ram == NULL ||
        length < MVS_STATE_HEADER_BYTES || memcmp(bytes, "GNST", 4u) != 0 ||
        sound_read_u32_be(bytes + 8u) != MVS_STATE_HEADER_BYTES ||
        sound_read_u32_be(bytes + 12u) != length ||
        sound_read_u32_be(bytes + 24u) != GN_MVS_PROFILE_MSX ||
        sound_read_u32_be(bytes + 64u) != 5u) return false;
    size_t cursor = MVS_STATE_HEADER_BYTES;
    for (uint32_t section = 1u; section <= 5u; ++section) {
        if (cursor > length || length - cursor < 8u) return false;
        const uint32_t id = sound_read_u32_be(bytes + cursor);
        const size_t payload_size = (size_t)sound_read_u32_be(bytes + cursor + 4u);
        cursor += 8u;
        if (id != section || payload_size > length - cursor) return false;
        if (id == MVS_STATE_MEMORY_SECTION) {
            if (payload_size < MVS_WORK_RAM_BYTES + MVS_SAVE_RAM_BYTES)
                return false;
            *out_work_ram = bytes + cursor;
            *out_save_ram = bytes + cursor + MVS_WORK_RAM_BYTES;
            return true;
        }
        cursor += payload_size;
    }
    return false;
}

static uint8_t *capture_adapter_state(size_t expected_size,
                                      const char *label) {
    const size_t size = retro_serialize_size();
    CHECK(size > 0u && size == expected_size, label);
    if (size == 0u || size != expected_size) return NULL;
    uint8_t *state = (uint8_t *)malloc(size);
    CHECK(state != NULL, "adapter state buffer allocation succeeds");
    if (state == NULL) return NULL;
    if (!retro_serialize(state, size)) {
        CHECK(false, "adapter captures exact native GNST bytes");
        free(state);
        return NULL;
    }
    CHECK(true, "adapter captures exact native GNST bytes");
    return state;
}

static uint8_t *capture_native_state(gn_instance *owner, size_t expected_size,
                                    const char *label) {
    size_t size = 0u;
    const gn_status capacity_status = gn_state_capacity_v1(owner, &size);
    CHECK(capacity_status == GN_STATUS_OK && size == expected_size, label);
    if (capacity_status != GN_STATUS_OK || size == 0u ||
        size != expected_size) return NULL;
    uint8_t *state = (uint8_t *)malloc(size);
    CHECK(state != NULL, "native witness state buffer allocation succeeds");
    if (state == NULL) return NULL;
    size_t written = 0u;
    const gn_status capture_status = gn_state_capture_v1(
        owner, state, size, &written, NULL, 0u);
    if (capture_status != GN_STATUS_OK || written != size) {
        CHECK(false, "native witness captures its exact state");
        free(state);
        return NULL;
    }
    CHECK(true, "native witness captures its exact state");
    return state;
}

static void compare_state_bytes(const uint8_t *adapter_state,
                                const uint8_t *native_state, size_t size,
                                const char *label) {
    CHECK(adapter_state != NULL && native_state != NULL && size > 0u &&
              memcmp(adapter_state, native_state, size) == 0,
          label);
}

static void check_mvs_callback_boundaries(size_t capacity,
                                          const uint8_t *initial_state) {
    enum { CANARY_BYTES = 16 };
    CHECK(capacity > 0u && initial_state != NULL,
          "boundary checks receive a loaded MVS state and exact baseline");
    if (capacity == 0u || initial_state == NULL ||
        capacity > SIZE_MAX - CANARY_BYTES) return;

    uint8_t *short_buffer = (uint8_t *)malloc(capacity);
    uint8_t *exact_buffer = (uint8_t *)malloc(capacity);
    uint8_t *large_buffer = (uint8_t *)malloc(capacity + CANARY_BYTES);
    CHECK(short_buffer != NULL && exact_buffer != NULL && large_buffer != NULL,
          "callback boundary buffers allocate within the content bound");
    if (short_buffer == NULL || exact_buffer == NULL || large_buffer == NULL) {
        free(short_buffer);
        free(exact_buffer);
        free(large_buffer);
        return;
    }

    const unsigned polls_before = poll_calls;
    const unsigned videos_before = video_calls;
    const unsigned samples_before = audio_calls;
    const unsigned batches_before = audio_batch_calls;
    void *const retained_save_ram =
        retro_get_memory_data(RETRO_MEMORY_SAVE_RAM);
    const size_t retained_save_ram_size =
        retro_get_memory_size(RETRO_MEMORY_SAVE_RAM);
    memset(short_buffer, 0x5au, capacity);
    memset(exact_buffer, 0x6bu, capacity);
    memset(large_buffer, 0xa5u, capacity + CANARY_BYTES);

    CHECK(!retro_serialize(NULL, capacity),
          "capture rejects a null destination at the exact size");
    CHECK(!retro_serialize(short_buffer, 0u),
          "capture rejects a nonnull zero-size destination");
    CHECK(!retro_serialize(short_buffer, capacity - 1u),
          "capture rejects a destination one byte below exact capacity");
    bool short_buffer_untouched = true;
    for (size_t index = 0u; index < capacity; ++index)
        if (short_buffer[index] != 0x5au) short_buffer_untouched = false;
    CHECK(short_buffer_untouched,
          "rejected short captures leave the entire destination untouched");

    CHECK(retro_serialize(exact_buffer, capacity),
          "capture accepts the exact loaded GNST capacity");
    CHECK(retro_serialize(large_buffer, capacity + CANARY_BYTES),
          "capture accepts a larger frontend buffer");
    CHECK(memcmp(exact_buffer, initial_state, capacity) == 0 &&
              memcmp(large_buffer, initial_state, capacity) == 0,
          "exact and oversized captures contain identical loaded GNST bytes");
    bool suffix_untouched = true;
    for (size_t index = capacity; index < capacity + CANARY_BYTES; ++index)
        if (large_buffer[index] != 0xa5u) suffix_untouched = false;
    CHECK(suffix_untouched,
          "oversized capture leaves every byte beyond logical state untouched");

    CHECK(!retro_unserialize(NULL, capacity),
          "restore rejects a null source with exact logical length");
    CHECK(!retro_unserialize(initial_state, 0u),
          "restore rejects zero logical length");
    CHECK(!retro_unserialize(initial_state, capacity - 1u),
          "restore rejects a truncated logical input");
    CHECK(!retro_unserialize(large_buffer, capacity + CANARY_BYTES),
          "restore rejects a valid state with trailing bytes");
    CHECK(retro_serialize_size() == capacity,
          "loaded state size stays fixed after rejected boundary calls");
    CHECK(retro_get_memory_data(RETRO_MEMORY_SAVE_RAM) == retained_save_ram &&
              retro_get_memory_size(RETRO_MEMORY_SAVE_RAM) ==
                  retained_save_ram_size,
          "rejected restores retain the original SAVE_RAM view");

    uint8_t *after_rejections = (uint8_t *)malloc(capacity);
    CHECK(after_rejections != NULL,
          "post-rejection GNST comparison buffer allocates");
    if (after_rejections != NULL) {
        CHECK(retro_serialize(after_rejections, capacity),
              "state remains capturable after rejected boundary calls");
        CHECK(memcmp(after_rejections, initial_state, capacity) == 0,
              "rejected callback operations preserve guest counters and cycles");
    }

    CHECK(retro_unserialize(initial_state, capacity),
          "restore accepts the exact loaded GNST length");
    CHECK(retro_serialize_size() == capacity,
          "loaded state size stays fixed after exact restore");
    CHECK(retro_get_memory_data(RETRO_MEMORY_SAVE_RAM) == retained_save_ram &&
              retro_get_memory_size(RETRO_MEMORY_SAVE_RAM) ==
                  retained_save_ram_size,
          "successful exact restore retains the original SAVE_RAM view");
    if (after_rejections != NULL) {
        CHECK(retro_serialize(after_rejections, capacity),
              "state remains capturable after exact restore");
        CHECK(memcmp(after_rejections, initial_state, capacity) == 0,
              "repeated exact capture and restore are byte-identical");
    }
    CHECK(poll_calls == polls_before && video_calls == videos_before &&
              audio_calls == samples_before &&
              audio_batch_calls == batches_before,
          "capture and restore invoke no input, video, or audio callbacks");

    free(short_buffer);
    free(exact_buffer);
    free(large_buffer);
    free(after_rejections);
}

static const size_t save_guest_offsets[6] = {
    0u, 1u, 0x1234u, 0x1235u, 0xfffeu, 0xffffu};
static const uint8_t save_guest_a[6] = {
    0x12u, 0x34u, 0x56u, 0x78u, 0x9au, 0xbcu};
static const uint8_t save_guest_b[6] = {
    0xa1u, 0xb2u, 0xc3u, 0xd4u, 0xe5u, 0xf6u};

static void check_sram_values(const uint8_t *save_ram,
                             const uint8_t values[6], const char *prefix) {
    CHECK(save_ram != NULL, "MVS state exposes parsed SRAM bytes");
    if (save_ram == NULL) return;
    for (size_t index = 0u; index < 6u; ++index) {
        const bool matches = save_ram[save_guest_offsets[index]] == values[index];
        if (tap_output) {
            ++tap_assertions;
            fprintf(stdout, "%s %u - %s SRAM byte %zu\n",
                    matches ? "ok" : "not ok", tap_assertions, prefix, index);
        } else if (!matches) {
            fprintf(stderr, "FAIL: %s SRAM byte %zu\n", prefix, index);
        }
        if (!matches) ++failures;
    }
}

static void check_guest_read_values(const uint8_t *work_ram,
                                   const uint8_t *save_ram,
                                   const uint8_t *expected_save_ram,
                                   const char *prefix) {
    CHECK(work_ram != NULL && save_ram != NULL && expected_save_ram != NULL,
          "MVS GNST exposes work RAM and backup RAM payloads");
    if (work_ram == NULL || save_ram == NULL || expected_save_ram == NULL) return;
    for (size_t index = 0u; index < 6u; ++index) {
        const bool matches =
            work_ram[index] == expected_save_ram[save_guest_offsets[index]] &&
            save_ram[save_guest_offsets[index]] ==
                expected_save_ram[save_guest_offsets[index]];
        if (tap_output) {
            ++tap_assertions;
            fprintf(stdout, "%s %u - %s guest-read byte %zu\n",
                    matches ? "ok" : "not ok", tap_assertions, prefix, index);
        } else if (!matches) {
            fprintf(stderr, "FAIL: %s guest-read byte %zu\n", prefix, index);
        }
        if (!matches) ++failures;
    }
}

static bool run_mvs_adapter_and_witness(gn_instance *witness,
                                       uint32_t input_mask,
                                       const char *label) {
    const unsigned old_polls = poll_calls;
    const unsigned old_videos = video_calls;
    const unsigned old_batches = audio_batch_calls;
    const unsigned old_samples = audio_calls;
    sound_buttons = 0u;
    if ((input_mask & GN_MVS_INPUT_P1_A) != 0u)
        sound_buttons |= (uint16_t)(UINT16_C(1) << RETRO_DEVICE_ID_JOYPAD_B);
    if ((input_mask & GN_MVS_INPUT_P1_B) != 0u)
        sound_buttons |= (uint16_t)(UINT16_C(1) << RETRO_DEVICE_ID_JOYPAD_A);
    right_state = (input_mask & GN_MVS_INPUT_P1_RIGHT) != 0u ? 1u : 0u;
    callback_frame_valid = false;
    observed_audio_frames = 0u;
    memset(observed_audio, 0, sizeof(observed_audio));
    retro_run();
    CHECK(poll_calls == old_polls + 1u,
          "one MVS input poll occurs for each retro_run");
    CHECK(video_calls == old_videos + 1u && callback_frame_valid,
          "one valid raw MVS frame is submitted for each retro_run");

    const gn_mvs_frame_request_v1 request = {
        GN_MVS_FRAME_REQUEST_V1_VERSION, input_mask, GN_PIXEL_XRGB8888,
        FRAME_WIDTH, FRAME_HEIGHT, FRAME_PITCH,
        (uint8_t *)native_sound_pixels, FRAME_BYTES, native_sound_audio,
        SOUND_AUDIO_CAPACITY};
    gn_mvs_frame_result_v1 result;
    memset(&result, 0, sizeof(result));
    const gn_status status = gn_mvs_advance_frame_v1(
        witness, &request, sizeof(request), &result, sizeof(result));
    CHECK(status == GN_STATUS_OK, "independent native witness advances one frame");
    if (status != GN_STATUS_OK) return false;
    last_witness_elapsed_cycles = result.elapsed_cycles;
    last_witness_audio_frames = result.audio_frames_delivered;
    CHECK(result.reason == GN_RUN_BUDGET && result.elapsed_cycles > 0u,
          "native witness reaches the requested frame budget with guest cycles");
    CHECK(result.audio_frames_generated == result.audio_frames_delivered,
          "native witness delivers its complete exact core PCM block");
    const unsigned expected_batches = result.audio_frames_delivered > 0u ? 1u : 0u;
    CHECK(audio_batch_calls == old_batches + expected_batches,
          "libretro submits exactly the native PCM block");
    CHECK(audio_calls == old_samples,
          "MVS PCM uses the registered batch callback only");
    CHECK(observed_audio_frames == result.audio_frames_delivered,
          "raw PCM callback count matches the independent native witness");
    if (callback_frame_valid) {
        CHECK(memcmp(observed_pixels, native_sound_pixels, FRAME_BYTES) == 0,
              label);
    }
    if (observed_audio_frames == result.audio_frames_delivered &&
        observed_audio_frames > 0u) {
        CHECK(memcmp(observed_audio, native_sound_audio,
                     observed_audio_frames * 2u * sizeof(int16_t)) == 0,
              "exact submitted PCM matches the independent native witness");
    }
    return result.reason == GN_RUN_BUDGET;
}

static int finish_mvs_tap(void) {
    printf("1..%u\n", tap_assertions);
    printf("# assertions: %u; failures: %u\n", tap_assertions, failures);
    return failures == 0u ? 0 : 1;
}

static int run_mvs_state_contract(const char *path) {
    tap_output = true;
    sound_mode = true;
    (void)puts("TAP version 13");
    CHECK(load_mvs_callback_fixture(path),
          "original MVS save guest loads through libretro");
    CHECK(create_native_mvs_reference(),
          "separately loaded native MVS witness accepts the same fixture");
    const size_t capacity = retro_serialize_size();
    CHECK(capacity > 0u,
          "MVS state capacity is positive before the first guest run");
    size_t native_capacity = 0u;
    const gn_status capacity_status =
        gn_state_capacity_v1(native_reference, &native_capacity);
    CHECK(capacity_status == GN_STATUS_OK && native_capacity == capacity,
          "libretro reports the exact loaded native GNST capacity");
    void *const retained_save_ram = retro_get_memory_data(RETRO_MEMORY_SAVE_RAM);
    const size_t retained_save_ram_size =
        retro_get_memory_size(RETRO_MEMORY_SAVE_RAM);
    CHECK(retained_save_ram != NULL && retained_save_ram_size == MVS_SAVE_RAM_BYTES,
          "loaded MVS SAVE_RAM exposes its retained 65,536-byte allocation");

    uint8_t *initial_adapter = capture_adapter_state(
        capacity, "initial loaded state has its cached capacity");
    uint8_t *initial_native = capture_native_state(
        native_reference, capacity, "initial native capacity matches libretro");
    compare_state_bytes(initial_adapter, initial_native, capacity,
                        "load-bound GNST capture matches an independent native witness");
    check_mvs_callback_boundaries(capacity, initial_adapter);
    free(initial_adapter);
    free(initial_native);

    CHECK(run_mvs_adapter_and_witness(native_reference, GN_MVS_INPUT_P1_A,
                                      "guest A continuation has identical raw video"),
          "original save guest executes its SRAM-A path");
    CHECK(retro_serialize_size() == capacity,
          "loaded state size stays fixed after the first guest run");
    uint8_t *state_a = capture_adapter_state(
        capacity, "state A capture succeeds with the content-bound size");
    uint8_t *native_a = capture_native_state(
        native_reference, capacity, "native state A capture keeps exact capacity");
    compare_state_bytes(state_a, native_a, capacity,
                        "guest-written SRAM-A state matches native capture");
    const uint8_t *work_ram = NULL;
    const uint8_t *state_save_ram = NULL;
    CHECK(mvs_state_memory(state_a, capacity, &work_ram, &state_save_ram),
          "state A has the bounded MVS memory section");
    check_sram_values(state_save_ram, save_guest_a,
                      "guest A writes the original expected values");

    retro_reset();
    const gn_status reset_status = gn_reset(native_reference);
    CHECK(reset_status == GN_STATUS_OK, "native witness resets with libretro");
    CHECK(retro_serialize_size() == capacity,
          "loaded state capacity remains fixed through reset");
    CHECK(retro_get_memory_data(RETRO_MEMORY_SAVE_RAM) == retained_save_ram &&
              retro_get_memory_size(RETRO_MEMORY_SAVE_RAM) == retained_save_ram_size,
          "retained SRAM pointer and extent remain fixed through reset");
    CHECK(run_mvs_adapter_and_witness(native_reference, GN_MVS_INPUT_P1_B,
                                      "guest B continuation has identical raw video"),
          "original save guest executes its SRAM-B path after reset");
    uint8_t *state_b = capture_adapter_state(
        capacity, "state B capture succeeds with unchanged capacity");
    const uint8_t *work_b = NULL;
    const uint8_t *save_b = NULL;
    CHECK(mvs_state_memory(state_b, capacity, &work_b, &save_b),
          "state B has the bounded MVS memory section");
    check_sram_values(save_b, save_guest_b,
                      "guest B replaces the six known SRAM values");

    const bool adapter_restored = state_a != NULL &&
        retro_unserialize(state_a, capacity);
    CHECK(adapter_restored,
          "direct native GNST restore reinstates historical SRAM-A state");
    const gn_status witness_restore = state_a == NULL
        ? GN_STATUS_INVALID_ARGUMENT
        : gn_state_restore_v1(native_reference, state_a, capacity, NULL, 0u);
    CHECK(witness_restore == GN_STATUS_OK,
          "native witness restores the exact adapter-captured GNST payload");
    CHECK(retro_serialize_size() == capacity,
          "loaded state capacity remains fixed through restore");
    CHECK(retro_get_memory_data(RETRO_MEMORY_SAVE_RAM) == retained_save_ram &&
              retro_get_memory_size(RETRO_MEMORY_SAVE_RAM) == retained_save_ram_size,
          "successful restore preserves the retained SRAM pointer and extent");
    if (retained_save_ram != NULL) {
        for (size_t index = 0u; index < 6u; ++index) {
            const bool matches =
                ((const uint8_t *)retained_save_ram)[save_guest_offsets[index]] ==
                    save_guest_a[index];
            if (tap_output) {
                ++tap_assertions;
                fprintf(stdout, "%s %u - restore restores SRAM-A byte %zu\n",
                        matches ? "ok" : "not ok", tap_assertions, index);
            } else if (!matches) {
                fprintf(stderr, "FAIL: restore restores SRAM-A byte %zu\n", index);
            }
            if (!matches) ++failures;
        }
    }
    CHECK(run_mvs_adapter_and_witness(native_reference, 0u,
                                      "restored continuation has identical raw video"),
          "restored adapter and fresh native state continue at the same guest boundary");
    uint8_t *continued_adapter = capture_adapter_state(
        capacity, "post-restore state capture keeps the loaded size");
    uint8_t *continued_native = capture_native_state(
        native_reference, capacity, "post-restore native witness keeps the loaded size");
    compare_state_bytes(continued_adapter, continued_native, capacity,
                        "restored guest effects and deterministic cycles match the native witness");
    const bool repeated_adapter_restore = state_a != NULL &&
        retro_unserialize(state_a, capacity);
    CHECK(repeated_adapter_restore,
          "a repeated restore accepts the same exact historical state");
    const gn_status repeated_native_restore = state_a == NULL
        ? GN_STATUS_INVALID_ARGUMENT
        : gn_state_restore_v1(native_reference, state_a, capacity, NULL, 0u);
    CHECK(repeated_native_restore == GN_STATUS_OK,
          "native witness replays the exact state for repeated continuation");
    CHECK(retro_serialize_size() == capacity,
          "loaded state size stays fixed after repeated restore");
    CHECK(run_mvs_adapter_and_witness(native_reference, 0u,
                                      "replayed continuation has identical raw video"),
          "repeated restore reproduces future guest, video, PCM, and cycles");
    uint8_t *repeated_adapter = capture_adapter_state(
        capacity, "repeated continuation keeps the exact loaded capacity");
    uint8_t *repeated_native = capture_native_state(
        native_reference, capacity,
        "replayed native witness keeps the exact loaded capacity");
    compare_state_bytes(repeated_adapter, repeated_native, capacity,
                        "repeated restore matches future guest state and cycles");

    free(state_a);
    free(native_a);
    free(state_b);
    free(continued_adapter);
    free(continued_native);
    free(repeated_adapter);
    free(repeated_native);
    retro_unload_game();
    gn_destroy(native_reference);
    native_reference = NULL;
    CHECK(retro_serialize_size() == 0u,
          "state capacity clears when the loaded MVS content unloads");
    retro_deinit();
    free(sound_content);
    sound_content = NULL;
    sound_content_size = 0u;
    return finish_mvs_tap();
}

static int run_mvs_save_ram_contract(const char *path) {
    tap_output = true;
    sound_mode = true;
    (void)puts("TAP version 13");
    CHECK(load_mvs_callback_fixture(path),
          "original MVS save guest loads for external SRAM copy capture");
    const size_t capacity = retro_serialize_size();
    CHECK(capacity > 0u,
          "MVS state capacity is available before the first guest call");
    uint8_t *const retained_save_ram =
        (uint8_t *)retro_get_memory_data(RETRO_MEMORY_SAVE_RAM);
    const size_t retained_save_ram_size =
        retro_get_memory_size(RETRO_MEMORY_SAVE_RAM);
    CHECK(retained_save_ram != NULL &&
              retained_save_ram_size == MVS_SAVE_RAM_BYTES,
          "SAVE_RAM exposes exactly the retained 65,536-byte MVS allocation");
    CHECK(retro_get_memory_data(RETRO_MEMORY_SYSTEM_RAM) == NULL &&
              retro_get_memory_size(RETRO_MEMORY_SYSTEM_RAM) == 0u,
          "unsupported system RAM ID remains unavailable");
    CHECK(retro_get_memory_data(RETRO_MEMORY_RTC) == NULL &&
              retro_get_memory_size(RETRO_MEMORY_RTC) == 0u,
          "unsupported RTC ID remains unavailable");
    CHECK(retro_get_memory_data(RETRO_MEMORY_VIDEO_RAM) == NULL &&
              retro_get_memory_size(RETRO_MEMORY_VIDEO_RAM) == 0u,
          "unsupported video RAM ID remains unavailable");

    uint8_t *pattern_p = (uint8_t *)malloc(MVS_SAVE_RAM_BYTES);
    uint8_t *pattern_q = (uint8_t *)malloc(MVS_SAVE_RAM_BYTES);
    CHECK(pattern_p != NULL && pattern_q != NULL,
          "external P/Q patterns allocate within the fixed SRAM bound");
    if (pattern_p != NULL && pattern_q != NULL) {
        for (size_t index = 0u; index < MVS_SAVE_RAM_BYTES; ++index) {
            pattern_p[index] = (uint8_t)(index * 37u + 0x2du);
            pattern_q[index] = (uint8_t)(pattern_p[index] ^ UINT8_C(0xa5));
        }
        if (retained_save_ram != NULL &&
            retained_save_ram_size == MVS_SAVE_RAM_BYTES) {
            memcpy(retained_save_ram, pattern_p, MVS_SAVE_RAM_BYTES);
            CHECK(memcmp(retained_save_ram, pattern_p, MVS_SAVE_RAM_BYTES) == 0,
                  "external P copy reaches the retained frontend pointer");
        }
    }

    uint8_t *captured_p = capture_adapter_state(
        capacity, "external P snapshot captures before any guest call");
    const uint8_t *initial_work = NULL;
    const uint8_t *initial_save = NULL;
    CHECK(mvs_state_memory(captured_p, capacity, &initial_work, &initial_save),
          "external P snapshot contains the loaded MVS memory section");
    CHECK(initial_save != NULL && pattern_p != NULL &&
              memcmp(initial_save, pattern_p, MVS_SAVE_RAM_BYTES) == 0,
          "external P bytes are included in GNST before guest execution");

    CHECK(create_native_mvs_reference(),
          "fresh independently loaded native witness accepts the save guest");
    const gn_status witness_restore = captured_p == NULL
        ? GN_STATUS_INVALID_ARGUMENT
        : gn_state_restore_v1(native_reference, captured_p, capacity, NULL, 0u);
    CHECK(witness_restore == GN_STATUS_OK,
          "fresh native witness restores the exact external-P capture");
    if (retained_save_ram != NULL && pattern_q != NULL &&
        retained_save_ram_size == MVS_SAVE_RAM_BYTES) {
        memcpy(retained_save_ram, pattern_q, MVS_SAVE_RAM_BYTES);
        CHECK(memcmp(retained_save_ram, pattern_q, MVS_SAVE_RAM_BYTES) == 0,
              "external Q copy is established before adapter restore");
    }
    const bool restored_p = captured_p != NULL &&
        retro_unserialize(captured_p, capacity);
    CHECK(restored_p,
          "adapter restores captured P through the native GNST API");
    CHECK(retro_get_memory_data(RETRO_MEMORY_SAVE_RAM) == retained_save_ram &&
              retro_get_memory_size(RETRO_MEMORY_SAVE_RAM) == retained_save_ram_size,
          "P/Q restore preserves the original SAVE_RAM pointer and extent");
    CHECK(retained_save_ram != NULL && pattern_p != NULL &&
              memcmp(retained_save_ram, pattern_p, MVS_SAVE_RAM_BYTES) == 0,
          "restored original pointer exposes captured P instead of Q");
    if (retained_save_ram != NULL && pattern_p != NULL &&
        retained_save_ram_size == MVS_SAVE_RAM_BYTES) {
        memcpy(retained_save_ram, pattern_p, MVS_SAVE_RAM_BYTES);
        memcpy(retained_save_ram, pattern_p, MVS_SAVE_RAM_BYTES);
    }
    CHECK(retained_save_ram != NULL && pattern_p != NULL &&
              memcmp(retained_save_ram, pattern_p, MVS_SAVE_RAM_BYTES) == 0,
          "repeated quiescent same-value SRAM copies remain guest-visible");

    CHECK(run_mvs_adapter_and_witness(native_reference, 0u,
                                      "P/Q guest read has identical raw video"),
          "guest reads restored P before either A/B store path");
    uint8_t *after_p_adapter = capture_adapter_state(
        capacity, "post-P-read adapter state remains capturable");
    uint8_t *after_p_native = capture_native_state(
        native_reference, capacity, "post-P-read native state remains capturable");
    compare_state_bytes(after_p_adapter, after_p_native, capacity,
                        "P guest effects and deterministic cycles match a fresh native witness");
    const uint8_t *read_work = NULL;
    const uint8_t *read_save = NULL;
    CHECK(mvs_state_memory(after_p_adapter, capacity, &read_work, &read_save),
          "post-read state retains the MVS work and save memory sections");
    check_guest_read_values(read_work, read_save, pattern_p,
                            "separately counted external P/Q snapshot case");
    CHECK(retained_save_ram != NULL && pattern_p != NULL &&
              memcmp(retained_save_ram, pattern_p, MVS_SAVE_RAM_BYTES) == 0,
          "read-before-write guest continuation leaves the P allocation intact");
    (void)puts("# external SRAM P/Q snapshot capture/restore cases: 1");
    (void)puts("# repeated same-value frontend SRAM copy cases: 1");

    free(pattern_p);
    free(pattern_q);
    free(captured_p);
    free(after_p_adapter);
    free(after_p_native);
    retro_unload_game();
    CHECK(retro_get_memory_data(RETRO_MEMORY_SAVE_RAM) == NULL &&
              retro_get_memory_size(RETRO_MEMORY_SAVE_RAM) == 0u,
          "SAVE_RAM pointer and extent clear after content unload");
    CHECK(retro_serialize_size() == 0u,
          "state capacity clears after SAVE_RAM content unload");
    gn_destroy(native_reference);
    native_reference = NULL;

    uint8_t *replacement_content = NULL;
    size_t replacement_content_size = 0u;
    const bool replacement_built = make_mvs_without_audio_bios(
        sound_content, sound_content_size, &replacement_content,
        &replacement_content_size);
    CHECK(replacement_built && replacement_content_size < sound_content_size,
          "replacement fixture has a smaller admitted seven-region manifest");
    if (replacement_built) {
        const struct retro_game_info replacement = {
            NULL, replacement_content, replacement_content_size, NULL};
        CHECK(retro_load_game(&replacement),
              "different-sized MVS content loads after unload");
        const size_t replacement_capacity = retro_serialize_size();
        CHECK(replacement_capacity > 0u,
              "replacement MVS load establishes a fresh positive state size");
        CHECK(retro_serialize_size() == replacement_capacity,
              "replacement state size remains fixed before its first run");
        CHECK(retro_get_memory_data(RETRO_MEMORY_SAVE_RAM) != NULL &&
                  retro_get_memory_size(RETRO_MEMORY_SAVE_RAM) ==
                      MVS_SAVE_RAM_BYTES,
              "replacement content exposes its own retained SAVE_RAM allocation");
        retro_unload_game();
        CHECK(retro_serialize_size() == 0u &&
                  retro_get_memory_data(RETRO_MEMORY_SAVE_RAM) == NULL &&
                  retro_get_memory_size(RETRO_MEMORY_SAVE_RAM) == 0u,
              "replacement unload clears state size and SAVE_RAM view");
    }
    free(replacement_content);
    retro_deinit();
    free(sound_content);
    sound_content = NULL;
    sound_content_size = 0u;
    return finish_mvs_tap();
}

static void run_sound_delivery_case(bool fire_pressed,
                                    enum sound_batch_return_mode return_mode,
                                    bool use_batch, bool use_sample_callback,
                                    const char *label) {
    const unsigned old_polls = poll_calls;
    const unsigned old_videos = video_calls;
    const unsigned old_batches = audio_batch_calls;
    const unsigned old_samples = audio_calls;
    const size_t old_submitted = sound_total_submitted_frames;
    const size_t old_processed = sound_total_processed_frames;
    const size_t old_discarded = sound_total_discarded_frames;
    const size_t old_unsubmitted = sound_total_unsubmitted_frames;
    right_state = 0u;
    sound_buttons = fire_pressed
        ? (uint16_t)(UINT16_C(1) << RETRO_DEVICE_ID_JOYPAD_B) : 0u;
    sound_batch_return_mode = return_mode;
    last_batch_offered_frames = 0u;
    last_batch_reported_frames = 0u;
    observed_audio_frames = 0u;
    memset(observed_audio, 0, sizeof(observed_audio));
    retro_set_audio_sample(use_sample_callback ? audio_callback : NULL);
    retro_set_audio_sample_batch(use_batch ? audio_batch_callback : NULL);
    callback_frame_valid = false;
    retro_run();

    CHECK(poll_calls == old_polls + 1u,
          "one sound input poll for each callback-consumption case");
    CHECK(video_calls == old_videos + 1u,
          "one video frame for each callback-consumption case");
    CHECK(callback_frame_valid,
          "callback-consumption frame pixels are valid");

    const uint32_t input_mask = fire_pressed ? GN_MVS_INPUT_P1_A : 0u;
    const gn_mvs_frame_request_v1 request = {
        GN_MVS_FRAME_REQUEST_V1_VERSION, input_mask, GN_PIXEL_XRGB8888,
        FRAME_WIDTH, FRAME_HEIGHT, FRAME_PITCH,
        (uint8_t *)native_sound_pixels, FRAME_BYTES, native_sound_audio,
        SOUND_AUDIO_CAPACITY
    };
    gn_mvs_frame_result_v1 result;
    memset(&result, 0, sizeof(result));
    CHECK(gn_mvs_advance_frame_v1(native_reference, &request, sizeof(request),
                                  &result, sizeof(result)) == GN_STATUS_OK,
          "native frame advances once for callback-consumption control");
    CHECK(result.audio_frames_generated == result.audio_frames_delivered,
          "native control captures all generated frames");
    sound_total_generated_frames += result.audio_frames_generated;

    const size_t expected_batches = use_batch ? 1u : 0u;
    CHECK(audio_batch_calls == old_batches + expected_batches,
          "MVS submits each produced block once to the selected batch path");
    const size_t expected_sample_calls = use_batch || !use_sample_callback
        ? 0u : result.audio_frames_delivered;
    CHECK(audio_calls == old_samples + expected_sample_calls,
          "sample fallback runs only when the batch callback is absent");
    CHECK(observed_audio_frames == (use_batch || use_sample_callback
              ? result.audio_frames_delivered : 0u),
          "callback captures the exact submitted frame count");
    if (use_batch) {
        size_t expected_report = result.audio_frames_delivered;
        if (return_mode == SOUND_BATCH_SHORT)
            expected_report /= 2u;
        else if (return_mode == SOUND_BATCH_ZERO)
            expected_report = 0u;
        else if (return_mode == SOUND_BATCH_OVER)
            ++expected_report;
        const size_t expected_processed = expected_report <
                result.audio_frames_delivered
            ? expected_report : result.audio_frames_delivered;
        CHECK(last_batch_offered_frames == result.audio_frames_generated,
              "batch submission equals the native generated block");
        CHECK(last_batch_reported_frames == expected_report,
              "frontend return scenario is applied to the submitted block");
        CHECK(sound_total_processed_frames - old_processed == expected_processed,
              "processed count is bounded by submitted frames");
        CHECK(sound_total_discarded_frames - old_discarded ==
                  result.audio_frames_delivered - expected_processed,
              "only the unprocessed suffix is discarded");
        CHECK(sound_total_submitted_frames - old_submitted ==
                  result.audio_frames_generated,
              "submitted count matches one native output block");
        CHECK(sound_total_unsubmitted_frames == old_unsubmitted,
              "a callback-present block is not classified as unsubmitted");
        CHECK(observed_audio_frames == result.audio_frames_delivered &&
                  memcmp(observed_audio, native_sound_audio,
                         observed_audio_frames * 2u * sizeof(int16_t)) == 0,
              label);
    } else if (use_sample_callback) {
        CHECK(sound_total_processed_frames - old_processed ==
                  result.audio_frames_delivered,
              "void sample callbacks process the full submitted frame");
        CHECK(sound_total_discarded_frames == old_discarded,
              "per-sample fallback has no unprocessed suffix");
        CHECK(sound_total_submitted_frames - old_submitted ==
                  result.audio_frames_generated,
              "per-sample path submits exactly the native block size");
        CHECK(observed_audio_frames == result.audio_frames_delivered &&
                  memcmp(observed_audio, native_sound_audio,
                         observed_audio_frames * 2u * sizeof(int16_t)) == 0,
              label);
    } else {
        sound_total_unsubmitted_frames += result.audio_frames_generated;
        CHECK(sound_total_unsubmitted_frames - old_unsubmitted ==
                  result.audio_frames_generated,
              "missing callbacks discard this bounded block after execution");
    }
    CHECK(memcmp(observed_pixels, native_sound_pixels, FRAME_BYTES) == 0,
          "callback outcome does not change guest frame time or video");
}

static int run_sound_contract(const char *path) {
    sound_mode = true;
    sound_batch_return_mode = SOUND_BATCH_FULL;
    sound_total_submitted_frames = 0u;
    sound_total_processed_frames = 0u;
    sound_total_discarded_frames = 0u;
    sound_total_unsubmitted_frames = 0u;
    sound_total_generated_frames = 0u;
    log_line_count = 0u;
    if (!read_sound_content(path)) {
        fprintf(stderr, "could not read generated public sound fixture\n");
        return 2;
    }
    retro_set_environment(environment_callback);
    retro_set_video_refresh(video_callback);
    retro_set_audio_sample(audio_callback);
    retro_set_audio_sample_batch(audio_batch_callback);
    retro_set_input_poll(input_poll_callback);
    retro_set_input_state(input_state_callback);
    retro_init();

    struct retro_game_info game = {NULL, sound_content, sound_content_size, NULL};
    CHECK(retro_load_game(&game), "ordinary libretro load accepts generated GNMV v3");
    CHECK(create_native_sound_reference(), "native control loads the same GNMV bytes");
    if (native_reference != NULL) {
        run_and_compare_sound_frame(false,
            "neutral-frame libretro PCM matches native output");
        run_and_compare_sound_frame(false,
            "sustained-tone libretro PCM matches native output");
        run_and_compare_sound_frame(true,
            "fire-burst libretro PCM matches native output");
        run_and_compare_sound_frame(false,
            "released-fire libretro PCM matches native output");
        run_sound_delivery_case(false, SOUND_BATCH_SHORT, true, true,
            "short batch submission preserves the exact offered PCM block");
        run_sound_delivery_case(false, SOUND_BATCH_ZERO, true, true,
            "zero batch return drops only this block");
        run_sound_delivery_case(false, SOUND_BATCH_OVER, true, true,
            "over-reported batch return is bounded to the submitted block");
        run_sound_delivery_case(true, SOUND_BATCH_FULL, false, true,
            "per-sample fallback matches native fire-burst PCM");
        run_sound_delivery_case(false, SOUND_BATCH_FULL, false, false,
            "no callback still advances guest and discards one bounded block");
        retro_set_audio_sample(audio_callback);
        retro_set_audio_sample_batch(audio_batch_callback);
        sound_batch_return_mode = SOUND_BATCH_FULL;
        run_sound_delivery_case(false, SOUND_BATCH_FULL, true, true,
            "full callback after discard has no stale queued audio");
        CHECK(count_log_lines_containing(
                  "MVS audio callback left PCM unprocessed") > 0u,
              "short and zero callbacks produce a bounded drop diagnostic");
        CHECK(count_log_lines_containing(
                  "MVS audio callback count exceeded submitted frames") > 0u,
              "impossible callback count is diagnosed");
        CHECK(sound_total_processed_frames + sound_total_discarded_frames ==
                  sound_total_submitted_frames,
              "processed and discarded frames account for every submission");
        CHECK(sound_total_submitted_frames + sound_total_unsubmitted_frames ==
                  sound_total_generated_frames,
              "generated frames are submitted or deliberately discarded");

        retro_reset();
        CHECK(gn_reset(native_reference) == GN_STATUS_OK,
              "native reference reset clears its converter state");
        run_sound_delivery_case(false, SOUND_BATCH_FULL, true, true,
            "reset frame PCM starts from clean per-instance state");
        const size_t partial_warnings_before_reset = count_log_lines_containing(
            "MVS audio callback left PCM unprocessed");
        run_sound_delivery_case(false, SOUND_BATCH_SHORT, true, true,
            "reset short callback drops only its new suffix");
        CHECK(count_log_lines_containing(
                  "MVS audio callback left PCM unprocessed") ==
                  partial_warnings_before_reset + 1u,
              "reset clears the one-time audio drop diagnostic state");

        retro_unload_game();
        CHECK(retro_load_game(&game), "MVS content reloads after audio discard");
        CHECK(gn_reset(native_reference) == GN_STATUS_OK,
              "native control reload starts with clean converter history");
        run_sound_delivery_case(false, SOUND_BATCH_FULL, true, true,
            "unload and reload leave no stale audio suffix");
    }
    retro_unload_game();
    gn_destroy(native_reference);
    native_reference = NULL;
    retro_deinit();
    free(sound_content);
    sound_content = NULL;
    return failures == 0u ? 0 : 1;
}

static int run_continuation_observer_contract(const char *content_path,
                                              const char *state_path) {
    static const uint32_t future_inputs[] = {
        0u, GN_MVS_INPUT_P1_A, GN_MVS_INPUT_P1_B, GN_MVS_INPUT_P1_RIGHT};
    continuation_observer_output = true;
    sound_mode = true;
    sound_batch_return_mode = SOUND_BATCH_FULL;
    CHECK(load_mvs_callback_fixture(content_path),
          "instrumented adapter loads the public sound fixture");
    CHECK(create_native_sound_reference(),
          "native reference loads the same public sound fixture");
    if (native_reference == NULL || retro_serialize_size() == 0u) goto done;

    CHECK(run_mvs_adapter_and_witness(native_reference, GN_MVS_INPUT_P1_A,
              "pre-capture adapter video and PCM match native output"),
          "pre-capture witness frame completes");
    CHECK(run_mvs_adapter_and_witness(native_reference, 0u,
              "second pre-capture adapter video and PCM match native output"),
          "second pre-capture witness frame completes");

    const size_t capacity = retro_serialize_size();
    uint8_t *const state = capture_adapter_state(
        capacity, "observer checkpoint captures the exact GNST state");
    if (state == NULL) goto done;
    FILE *const output = gn_portable_fopen(state_path, "wb");
    bool wrote_state = false;
    if (output != NULL) {
        wrote_state = fwrite(state, 1u, capacity, output) == capacity;
        if (fclose(output) != 0) wrote_state = false;
    }
    CHECK(wrote_state, "observer checkpoint is available to fresh process");
    if (!wrote_state) {
        free(state);
        goto done;
    }

    CHECK(run_mvs_adapter_and_witness(native_reference, GN_MVS_INPUT_P1_B,
              "distinguishing branch video and PCM match native output"),
          "branch advances beyond the saved boundary");
    const bool adapter_restored = retro_unserialize(state, capacity);
    CHECK(adapter_restored, "adapter restores its saved GNST checkpoint");
    const gn_status native_restored = gn_state_restore_v1(
        native_reference, state, capacity, NULL, 0u);
    CHECK(native_restored == GN_STATUS_OK,
          "native witness restores the same GNST checkpoint");
    for (size_t index = 0u; index < sizeof(future_inputs) / sizeof(future_inputs[0]);
         ++index) {
        CHECK(run_mvs_adapter_and_witness(native_reference,
                  future_inputs[index],
                  "post-restore callback video and PCM match native output"),
              "post-restore adapter and witness frame complete");
    }
    free(state);

done:
    retro_unload_game();
    if (native_reference != NULL) {
        gn_destroy(native_reference);
        native_reference = NULL;
    }
    retro_deinit();
    free(sound_content);
    sound_content = NULL;
    return failures == 0u ? 0 : 1;
}

static bool harness_write_u32be(FILE *file, uint32_t value) {
    const uint8_t bytes[4] = {(uint8_t)(value >> 24),
        (uint8_t)(value >> 16), (uint8_t)(value >> 8), (uint8_t)value};
    return fwrite(bytes, 1u, sizeof(bytes), file) == sizeof(bytes);
}

static bool harness_write_u64be(FILE *file, uint64_t value) {
    return harness_write_u32be(file, (uint32_t)(value >> 32)) &&
           harness_write_u32be(file, (uint32_t)value);
}

static bool harness_read_state(const char *path, uint8_t **out_state,
                               size_t *out_size) {
    *out_state = NULL;
    *out_size = 0u;
    FILE *const file = gn_portable_fopen(path, "rb");
    if (file == NULL) return false;
    bool ok = fseek(file, 0L, SEEK_END) == 0;
    const long measured = ok ? ftell(file) : -1L;
    if (!ok || measured < 72L || measured > 1024L * 1024L ||
        fseek(file, 0L, SEEK_SET) != 0) {
        (void)fclose(file);
        return false;
    }
    const size_t size = (size_t)measured;
    uint8_t *const state = (uint8_t *)malloc(size);
    bool valid = state != NULL;
    if (valid) valid = fread(state, 1u, size, file) == size;
    if (valid) valid = fgetc(file) == EOF;
    if (fclose(file) != 0) valid = false;
    if (valid) valid = memcmp(state, "GNST", 4u) == 0;
    if (!valid) {
        if (state != NULL) { memset(state, 0xa5, size); free(state); }
        return false;
    }
    *out_state = state;
    *out_size = size;
    return true;
}

static int run_continuation_production_contract(const char *content_path,
                                                const char *state_path,
                                                const char *trace_path) {
    static const uint32_t future_inputs[] = {
        0u, GN_MVS_INPUT_P1_A, GN_MVS_INPUT_P1_B, GN_MVS_INPUT_P1_RIGHT};
    sound_mode = true;
    sound_batch_return_mode = SOUND_BATCH_FULL;
    CHECK(load_mvs_callback_fixture(content_path),
          "production adapter loads the public sound fixture");
    CHECK(create_native_sound_reference(),
          "production native reference loads the same public sound fixture");
    uint8_t *state = NULL;
    size_t state_size = 0u;
    CHECK(harness_read_state(state_path, &state, &state_size),
          "production adapter receives a bounded GNST checkpoint");
    if (state != NULL && native_reference != NULL) {
        CHECK(state_size == retro_serialize_size(),
              "production adapter checkpoint size matches the loaded content");
        CHECK(retro_unserialize(state, state_size),
              "production adapter restores the instrumented run checkpoint");
        CHECK(gn_state_restore_v1(native_reference, state, state_size,
                  NULL, 0u) == GN_STATUS_OK,
              "production native reference restores the same checkpoint");
    }
    FILE *const trace = state != NULL && native_reference != NULL
        ? gn_portable_fopen(trace_path, "wb") : NULL;
    static const uint8_t header[12] = {
        'G', 'N', 'F', 'O', 0u, 0u, 0u, 1u, 0u, 0u, 0u, 4u};
    CHECK(trace != NULL && fwrite(header, 1u, sizeof(header), trace) == sizeof(header),
          "production callback trace opens with a bounded frame header");
    for (size_t index = 0u; trace != NULL && native_reference != NULL &&
         index < sizeof(future_inputs) / sizeof(future_inputs[0]); ++index) {
        CHECK(run_mvs_adapter_and_witness(native_reference, future_inputs[index],
                  "production callback video and PCM match native output"),
              "production continuation frame completes");
        const size_t video_bytes = sizeof(observed_pixels);
        const size_t audio_bytes = last_witness_audio_frames * 2u * sizeof(int16_t);
        const bool wrote = observed_audio_frames == last_witness_audio_frames &&
            harness_write_u32be(trace, future_inputs[index]) &&
            harness_write_u64be(trace, last_witness_elapsed_cycles) &&
            harness_write_u32be(trace, (uint32_t)last_witness_audio_frames) &&
            harness_write_u32be(trace, (uint32_t)video_bytes) &&
            harness_write_u32be(trace, (uint32_t)audio_bytes) &&
            fwrite(observed_pixels, 1u, video_bytes, trace) == video_bytes &&
            fwrite(observed_audio, 1u, audio_bytes, trace) == audio_bytes;
        CHECK(wrote, "production raw callback trace records exact bounded bytes");
    }
    bool trace_closed = true;
    if (trace != NULL && fclose(trace) != 0) trace_closed = false;
    CHECK(trace_closed, "production raw callback trace closes successfully");
    if (state != NULL) { memset(state, 0xa5, state_size); free(state); }
    retro_unload_game();
    if (native_reference != NULL) {
        gn_destroy(native_reference);
        native_reference = NULL;
    }
    retro_deinit();
    free(sound_content);
    sound_content = NULL;
    return failures == 0u ? 0 : 1;
}

int main(int argc, char **argv) {
    if (argc == 3 && strcmp(argv[1], "--write-save-fixture") == 0)
        return write_save_fixture(argv[2]);
    if (argc == 3 && strcmp(argv[1], "--mvs-state") == 0)
        return run_mvs_state_contract(argv[2]);
    if (argc == 3 && strcmp(argv[1], "--mvs-save-ram") == 0)
        return run_mvs_save_ram_contract(argv[2]);
    if (argc == 3 && strcmp(argv[1], "--sound") == 0)
        return run_sound_contract(argv[2]);
    if (argc == 4 && strcmp(argv[1], "--continuation-observations") == 0)
        return run_continuation_observer_contract(argv[2], argv[3]);
    if (argc == 5 && strcmp(argv[1], "--continuation-production") == 0)
        return run_continuation_production_contract(argv[2], argv[3], argv[4]);
    if (argc != 2 || !read_content(argv[1])) {
        fprintf(stderr, "usage: libretro_callback_test <generated-content>\n");
        return 2;
    }

    const char *opted_out[] = {
        "retro_load_game_special", "retro_serialize_size", "retro_serialize",
        "retro_unserialize", "retro_get_memory_data", "retro_get_memory_size",
        "retro_cheat_reset", "retro_cheat_set"};
    for (size_t index = 0u; index < sizeof(opted_out) / sizeof(opted_out[0]); ++index) {
        require_export(opted_out[index]);
    }

    retro_set_environment(environment_callback);
    retro_set_video_refresh(video_callback);
    retro_set_audio_sample(audio_callback);
    retro_set_audio_sample_batch(audio_batch_callback);
    retro_set_input_poll(input_poll_callback);
    retro_set_input_state(input_state_callback);
    retro_init();

    struct retro_system_info system_info;
    memset(&system_info, 0, sizeof(system_info));
    retro_get_system_info(&system_info);
    CHECK(system_info.need_fullpath == false, "in-memory content is requested");

    CHECK(!retro_load_game(NULL), "no-content load is rejected");
    struct retro_game_info game = {NULL, content, CONTENT_BYTES, NULL};
    game.size = CONTENT_BYTES - 1u;
    CHECK(!retro_load_game(&game), "truncated content is rejected");
    game.size = CONTENT_BYTES;
    content[7] = 2u;
    CHECK(!retro_load_game(&game), "unsupported content version is rejected");
    content[7] = 1u;
    content[16u + 0x100u] ^= 1u;
    CHECK(!retro_load_game(&game), "native fixture validation failure is rejected");
    content[16u + 0x100u] ^= 1u;
    reject_pixel_format = true;
    CHECK(!retro_load_game(&game), "unsupported pixel format is rejected");
    reject_pixel_format = false;
    CHECK(retro_load_game(&game), "valid generated content loads");
    CHECK(format_calls == 3u, "pixel format negotiation runs for native, rejected, and valid loads");

    struct retro_system_av_info av_info;
    memset(&av_info, 0, sizeof(av_info));
    retro_get_system_av_info(&av_info);
    CHECK(av_info.geometry.base_width == FRAME_WIDTH &&
          av_info.geometry.base_height == FRAME_HEIGHT &&
          av_info.timing.fps == 60.0 && av_info.timing.sample_rate == 48000.0,
          "fixed fixture geometry and nominal rates are reported");

    CHECK(!retro_load_game_special(0u, NULL, 0u),
          "special-content loading is opted out");
    CHECK(retro_serialize_size() == 0u, "serialization size is zero");
    CHECK(!retro_serialize(NULL, 0u), "serialization is opted out");
    CHECK(!retro_unserialize(NULL, 0u), "unserialization is opted out");
    CHECK(!retro_serialize(content, sizeof(content)) &&
              !retro_unserialize(content, sizeof(content)),
          "GNFX serialization and restore remain opted out");
    CHECK(retro_get_memory_data(RETRO_MEMORY_SAVE_RAM) == NULL &&
              retro_get_memory_size(RETRO_MEMORY_SAVE_RAM) == 0u,
          "GNFX SAVE_RAM remains unavailable");
    CHECK(retro_get_memory_data(RETRO_MEMORY_SYSTEM_RAM) == NULL &&
              retro_get_memory_size(RETRO_MEMORY_SYSTEM_RAM) == 0u,
          "GNFX system RAM remains unavailable");
    CHECK(retro_get_memory_data(RETRO_MEMORY_RTC) == NULL &&
              retro_get_memory_size(RETRO_MEMORY_RTC) == 0u,
          "GNFX RTC remains unavailable");
    CHECK(retro_get_memory_data(RETRO_MEMORY_VIDEO_RAM) == NULL &&
              retro_get_memory_size(RETRO_MEMORY_VIDEO_RAM) == 0u,
          "GNFX video RAM remains unavailable");
    retro_cheat_reset();
    retro_cheat_set(0u, true, "fixture-no-op");

    CHECK(create_native_reference(), "independent native instance loads same content");
    run_and_compare(false, "no-input callback pixels match native output");
    run_and_compare(true, "RIGHT callback pixels match native output");
    CHECK(observed_pixels[16u * FRAME_WIDTH + 16u] == 0u &&
          observed_pixels[16u * FRAME_WIDTH + 24u] == UINT32_C(0x00ffffff),
          "RIGHT moves the guest marker by one pixel");
    run_and_compare(false, "no-RIGHT control pixels match native output");
    CHECK(audio_calls == 0u && audio_batch_calls == 0u,
          "zero produced audio frames do not invoke audio callbacks");

    retro_unload_game();
    gn_destroy(native_reference);
    native_reference = NULL;
    CHECK(retro_serialize_size() == 0u &&
              retro_get_memory_data(RETRO_MEMORY_SAVE_RAM) == NULL &&
              retro_get_memory_size(RETRO_MEMORY_SAVE_RAM) == 0u,
          "unloaded GNFX state and memory callbacks remain empty");
    const unsigned old_polls = poll_calls;
    const unsigned old_videos = video_calls;
    retro_run();
    CHECK(poll_calls == old_polls && video_calls == old_videos,
          "run after unload does not access the destroyed instance");

    CHECK(retro_load_game(&game), "same content reloads after unload");
    CHECK(retro_serialize_size() == 0u &&
              retro_get_memory_data(RETRO_MEMORY_SAVE_RAM) == NULL &&
              retro_get_memory_size(RETRO_MEMORY_SAVE_RAM) == 0u,
          "reloaded GNFX profile still has no state or SAVE_RAM view");
    gn_destroy(native_reference);
    native_reference = NULL;
    CHECK(create_native_reference(), "native control instance reloads content");
    run_and_compare(false, "wrong-input control remains equal to native output");
    CHECK(observed_pixels[16u * FRAME_WIDTH + 16u] == UINT32_C(0x00ffffff) &&
          observed_pixels[16u * FRAME_WIDTH + 24u] == 0u,
          "no-RIGHT control does not satisfy the RIGHT movement expectation");

    retro_unload_game();
    gn_destroy(native_reference);
    native_reference = NULL;
    retro_deinit();
    return failures == 0u ? 0 : 1;
}
