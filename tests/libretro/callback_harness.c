/* SPDX-License-Identifier: MIT */
#include "glueyneo/glueyneo.h"
#include "libretro.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#if defined(_WIN32)
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#else
#include <dlfcn.h>
#endif

#define CONTENT_BYTES 602u
#define FRAME_WIDTH 320u
#define FRAME_HEIGHT 224u
#define FRAME_PITCH (FRAME_WIDTH * sizeof(uint32_t))
#define FRAME_BYTES (FRAME_PITCH * FRAME_HEIGHT)

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
static unsigned failures;
static gn_instance *native_reference;

#define CHECK(condition, label) do { \
    if (!(condition)) { \
        fprintf(stderr, "FAIL: %s\n", label); \
        ++failures; \
    } \
} while (0)

static bool environment_callback(unsigned command, void *data) {
    if (command != RETRO_ENVIRONMENT_SET_PIXEL_FORMAT || data == NULL) return false;
    ++format_calls;
    if (*(enum retro_pixel_format *)data != RETRO_PIXEL_FORMAT_XRGB8888) return false;
    return !reject_pixel_format;
}

static void video_callback(const void *data, unsigned width, unsigned height,
                           size_t pitch) {
    ++video_calls;
    callback_frame_valid = data != NULL && width == FRAME_WIDTH &&
        height == FRAME_HEIGHT && pitch == FRAME_PITCH;
    if (callback_frame_valid) memcpy(observed_pixels, data, FRAME_BYTES);
}

static void audio_callback(int16_t left, int16_t right) {
    (void)left;
    (void)right;
    ++audio_calls;
}

static size_t audio_batch_callback(const int16_t *data, size_t frames) {
    (void)data;
    (void)frames;
    ++audio_batch_calls;
    return frames;
}

static void input_poll_callback(void) { ++poll_calls; }

static int16_t input_state_callback(unsigned port, unsigned device,
                                    unsigned index, unsigned id) {
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
    FILE *file = fopen(path, "rb");
    if (file == NULL) return false;
    const size_t count = fread(content, 1u, sizeof(content), file);
    const int extra = fgetc(file);
    const int close_status = fclose(file);
    return count == sizeof(content) && extra == EOF && close_status == 0;
}

static void require_export(const char *name) {
#if defined(_WIN32)
    static HMODULE module;
    if (module == NULL) module = GetModuleHandleA("glueyneo_libretro.dll");
    CHECK(module != NULL, "libretro shared library is loaded");
    CHECK(module != NULL && GetProcAddress(module, name) != NULL, name);
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

int main(int argc, char **argv) {
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
    CHECK(retro_get_memory_data(RETRO_MEMORY_SYSTEM_RAM) == NULL,
          "raw memory data is unavailable");
    CHECK(retro_get_memory_size(RETRO_MEMORY_SYSTEM_RAM) == 0u,
          "raw memory size is zero");
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
    const unsigned old_polls = poll_calls;
    const unsigned old_videos = video_calls;
    retro_run();
    CHECK(poll_calls == old_polls && video_calls == old_videos,
          "run after unload does not access the destroyed instance");

    CHECK(retro_load_game(&game), "same content reloads after unload");
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
