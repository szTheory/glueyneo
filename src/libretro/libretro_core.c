/* SPDX-License-Identifier: MIT */
#include "glueyneo/glueyneo.h"
#include "libretro.h"

#include <string.h>

#define GNFX_HEADER_SIZE 16u
#define GNFX_ROM_SIZE 512u
#define GNFX_RAM_SEED_SIZE 10u
#define GNFX_TILE_SIZE 64u
#define GNFX_PAYLOAD_SIZE (GNFX_ROM_SIZE + GNFX_RAM_SEED_SIZE + GNFX_TILE_SIZE)
#define GNFX_CONTENT_SIZE (GNFX_HEADER_SIZE + GNFX_PAYLOAD_SIZE)
#define GN_FRAME_WIDTH 320u
#define GN_FRAME_HEIGHT 224u
#define GN_FRAME_PITCH (GN_FRAME_WIDTH * sizeof(uint32_t))
#define GN_FRAME_BYTES (GN_FRAME_PITCH * GN_FRAME_HEIGHT)
#define GN_AUDIO_MAX_FRAMES 800u

static retro_environment_t environment_cb;
static retro_video_refresh_t video_cb;
static retro_audio_sample_t audio_cb;
static retro_audio_sample_batch_t audio_batch_cb;
static retro_input_poll_t input_poll_cb;
static retro_input_state_t input_state_cb;
static gn_instance *instance;
static uint32_t pixels[GN_FRAME_WIDTH * GN_FRAME_HEIGHT];
static int16_t audio_samples[GN_AUDIO_MAX_FRAMES * 2u];

static uint32_t read_u32_be(const uint8_t *bytes) {
    return ((uint32_t)bytes[0] << 24) | ((uint32_t)bytes[1] << 16) |
           ((uint32_t)bytes[2] << 8) | (uint32_t)bytes[3];
}

static void unload_instance(void) {
    if (instance != NULL) {
        (void)gn_unload(instance);
        gn_destroy(instance);
        instance = NULL;
    }
}

unsigned retro_api_version(void) { return RETRO_API_VERSION; }

void retro_set_environment(retro_environment_t callback) {
    environment_cb = callback;
}

void retro_set_video_refresh(retro_video_refresh_t callback) {
    video_cb = callback;
}

void retro_set_audio_sample(retro_audio_sample_t callback) {
    audio_cb = callback;
}

void retro_set_audio_sample_batch(retro_audio_sample_batch_t callback) {
    audio_batch_cb = callback;
}

void retro_set_input_poll(retro_input_poll_t callback) {
    input_poll_cb = callback;
}

void retro_set_input_state(retro_input_state_t callback) {
    input_state_cb = callback;
}

void retro_init(void) {}

void retro_deinit(void) {
    unload_instance();
    environment_cb = NULL;
    video_cb = NULL;
    audio_cb = NULL;
    audio_batch_cb = NULL;
    input_poll_cb = NULL;
    input_state_cb = NULL;
}

void retro_get_system_info(struct retro_system_info *info) {
    if (info == NULL) return;
    info->library_name = "Glueyneo";
    info->library_version = "0.1";
    info->valid_extensions = "bin|gnmv";
    info->need_fullpath = false;
    info->block_extract = false;
}

void retro_get_system_av_info(struct retro_system_av_info *info) {
    if (info == NULL) return;
    info->geometry.base_width = GN_FRAME_WIDTH;
    info->geometry.base_height = GN_FRAME_HEIGHT;
    info->geometry.max_width = GN_FRAME_WIDTH;
    info->geometry.max_height = GN_FRAME_HEIGHT;
    info->geometry.aspect_ratio = (float)GN_FRAME_WIDTH / (float)GN_FRAME_HEIGHT;
    info->timing.fps = 60.0;
    info->timing.sample_rate = 48000.0;
}

void retro_set_controller_port_device(unsigned port, unsigned device) {
    (void)port;
    (void)device;
}

void retro_reset(void) {
    if (instance != NULL) (void)gn_reset(instance);
}

bool retro_load_game(const struct retro_game_info *game) {
    if (instance != NULL || game == NULL || game->data == NULL ||
        environment_cb == NULL) {
        return false;
    }

    const uint8_t *content = (const uint8_t *)game->data;
    if (game->size >= 16u && memcmp(content, "GNMV", 4u) == 0) {
        const uint32_t version = read_u32_be(content + 4u);
        const uint32_t profile = read_u32_be(content + 8u);
        const uint32_t count = read_u32_be(content + 12u);
        if (version != 1u || profile != GN_MVS_PROFILE_MSX ||
            count != GN_MVS_MAX_REGIONS ||
            game->size > GN_MVS_MAX_MEDIA_BYTES + 16u +
                         GN_MVS_MAX_REGIONS * 12u) return false;
        gn_mvs_manifest manifest;
        memset(&manifest, 0, sizeof(manifest));
        manifest.version = GN_MVS_MANIFEST_VERSION;
        manifest.profile = profile;
        manifest.region_count = count;
        size_t cursor = 16u;
        for (size_t index = 0u; index < count; ++index) {
            if (cursor > game->size || game->size - cursor < 12u) return false;
            const uint32_t role = read_u32_be(content + cursor);
            const uint32_t high = read_u32_be(content + cursor + 4u);
            const uint32_t low = read_u32_be(content + cursor + 8u);
            if (high != 0u) return false;
            const size_t region_size = (size_t)low;
            cursor += 12u;
            if (region_size == 0u || region_size > game->size - cursor) return false;
            manifest.regions[index] = (gn_mvs_region){
                (gn_mvs_region_role)role, content + cursor, region_size,
                region_size, GN_MVS_LAYOUT_LINEAR};
            cursor += region_size;
        }
        if (cursor != game->size) return false;
        enum retro_pixel_format pixel_format = RETRO_PIXEL_FORMAT_XRGB8888;
        if (!environment_cb(RETRO_ENVIRONMENT_SET_PIXEL_FORMAT, &pixel_format))
            return false;
        if (gn_create(&instance) != GN_STATUS_OK) { instance = NULL; return false; }
        if (gn_load_mvs(instance, &manifest) != GN_STATUS_OK) {
            unload_instance();
            return false;
        }
        return true;
    }
    if (game->size != (size_t)GNFX_CONTENT_SIZE) return false;
    if (memcmp(content, "GNFX", 4u) != 0 || read_u32_be(content + 4u) != 1u ||
        read_u32_be(content + 8u) != GNFX_PAYLOAD_SIZE ||
        read_u32_be(content + 12u) != GNFX_HEADER_SIZE) {
        return false;
    }

    enum retro_pixel_format pixel_format = RETRO_PIXEL_FORMAT_XRGB8888;
    if (!environment_cb(RETRO_ENVIRONMENT_SET_PIXEL_FORMAT, &pixel_format)) {
        return false;
    }

    gn_manifest manifest;
    memset(&manifest, 0, sizeof(manifest));
    manifest.version = GN_MANIFEST_VERSION;
    manifest.profile = GN_PROFILE_PUBLIC_FIXTURE;
    manifest.region_count = 1u;
    manifest.regions[0] = (gn_region){
        0u, GNFX_CONTENT_SIZE, content, game->size, GN_REGION_ROM};

    if (gn_create(&instance) != GN_STATUS_OK) {
        instance = NULL;
        return false;
    }
    if (gn_load(instance, &manifest) != GN_STATUS_OK) {
        unload_instance();
        return false;
    }
    return true;
}

bool retro_load_game_special(unsigned game_type,
                             const struct retro_game_info *info,
                             size_t num_info) {
    (void)game_type;
    (void)info;
    (void)num_info;
    return false;
}

void retro_unload_game(void) { unload_instance(); }

void retro_run(void) {
    if (instance == NULL || input_poll_cb == NULL || input_state_cb == NULL ||
        video_cb == NULL) {
        return;
    }

    input_poll_cb();
    uint32_t input_mask = 0u;
    if (input_state_cb(0u, RETRO_DEVICE_JOYPAD, 0u,
                       RETRO_DEVICE_ID_JOYPAD_RIGHT) != 0) {
        input_mask |= GN_INPUT_RIGHT;
    }

    const gn_frame_request request = {
        input_mask, GN_PIXEL_XRGB8888, GN_FRAME_WIDTH, GN_FRAME_HEIGHT,
        GN_FRAME_PITCH, (uint8_t *)pixels, GN_FRAME_BYTES, audio_samples,
        GN_AUDIO_MAX_FRAMES};
    gn_frame_result result;
    if (gn_advance_frame(instance, &request, &result) != GN_STATUS_OK ||
        result.reason != GN_RUN_STOPPED ||
        result.video_pixels_produced != GN_FRAME_WIDTH * GN_FRAME_HEIGHT) {
        /* Libretro permits a NULL frame to repeat the previous valid image. */
        video_cb(NULL, GN_FRAME_WIDTH, GN_FRAME_HEIGHT, GN_FRAME_PITCH);
        return;
    }

    video_cb(pixels, GN_FRAME_WIDTH, GN_FRAME_HEIGHT, GN_FRAME_PITCH);
    if (result.audio_frames_produced > 0u) {
        if (audio_batch_cb != NULL) {
            (void)audio_batch_cb(audio_samples, result.audio_frames_produced);
        } else if (audio_cb != NULL) {
            for (size_t frame = 0u; frame < result.audio_frames_produced; ++frame) {
                audio_cb(audio_samples[frame * 2u], audio_samples[frame * 2u + 1u]);
            }
        }
    }
}

size_t retro_serialize_size(void) { return 0u; }

bool retro_serialize(void *data, size_t len) {
    (void)data;
    (void)len;
    return false;
}

bool retro_unserialize(const void *data, size_t len) {
    (void)data;
    (void)len;
    return false;
}

unsigned retro_get_region(void) { return RETRO_REGION_NTSC; }

void *retro_get_memory_data(unsigned id) {
    (void)id;
    return NULL;
}

size_t retro_get_memory_size(unsigned id) {
    (void)id;
    return 0u;
}

void retro_cheat_reset(void) {}

void retro_cheat_set(unsigned index, bool enabled, const char *code) {
    (void)index;
    (void)enabled;
    (void)code;
}
