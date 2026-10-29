/* SPDX-License-Identifier: MIT */
#include "../support/portable_stdio.h"

#include "glueyneo/glueyneo.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "unity.h"

enum {
    SOUND_HEADER_BYTES = 16u,
    SOUND_REGION_COUNT = 8u,
    SOUND_DESCRIPTOR_BYTES = 12u,
    SOUND_MAIN_ENTRY_OFFSET = 0x100u,
    SOUND_WIDTH = 320u,
    SOUND_HEIGHT = 224u
};

#define SOUND_PITCH ((size_t)SOUND_WIDTH * sizeof(uint32_t))
#define SOUND_PIXEL_BYTES (SOUND_PITCH * (size_t)SOUND_HEIGHT)

static gn_instance *instance;
static uint8_t *content;
static size_t content_size;
static uint32_t *pixels;
static int16_t *audio;
static size_t audio_capacity;
static const char *fixture_path;

/* Declared here to keep this original fixture's format private to its C consumer. */
size_t public_sound_guest_size(void);
int public_sound_guest_build(uint8_t *bundle, size_t capacity);
int public_sound_guest_write(const char *path);

void setUp(void) {
    instance = NULL;
    content = NULL;
    content_size = 0u;
    pixels = NULL;
    audio = NULL;
    audio_capacity = 0u;
}

void tearDown(void) {
    gn_destroy(instance);
    instance = NULL;
    free(content);
    free(pixels);
    free(audio);
    content = NULL;
    pixels = NULL;
    audio = NULL;
}

static uint32_t read_u32_be(const uint8_t *bytes) {
    return ((uint32_t)bytes[0] << 24) | ((uint32_t)bytes[1] << 16) |
           ((uint32_t)bytes[2] << 8) | (uint32_t)bytes[3];
}

static int read_fixture(void) {
    FILE *file = gn_portable_fopen(fixture_path, "rb");
    if (file == NULL) return 0;
    if (fseek(file, 0L, SEEK_END) != 0) {
        (void)fclose(file);
        return 0;
    }
    const long measured = ftell(file);
    if (measured < 0L || (uint64_t)measured != public_sound_guest_size() ||
        fseek(file, 0L, SEEK_SET) != 0) {
        (void)fclose(file);
        return 0;
    }
    content_size = (size_t)measured;
    content = (uint8_t *)malloc(content_size);
    if (content == NULL) {
        (void)fclose(file);
        return 0;
    }
    const size_t count = fread(content, 1u, content_size, file);
    const int extra = fgetc(file);
    const int close_status = fclose(file);
    return count == content_size && extra == EOF && close_status == 0;
}

static int load_fixture(gn_instance **out_instance) {
    if (content == NULL || content_size < SOUND_HEADER_BYTES ||
        memcmp(content, "GNMV", 4u) != 0 ||
        read_u32_be(content + 4u) != GN_MVS_MANIFEST_VERSION_ZOOM ||
        read_u32_be(content + 8u) != GN_MVS_PROFILE_MSX ||
        read_u32_be(content + 12u) != SOUND_REGION_COUNT) return 0;

    gn_mvs_manifest_v3 manifest;
    memset(&manifest, 0, sizeof(manifest));
    manifest.version = GN_MVS_MANIFEST_VERSION_ZOOM;
    manifest.profile = GN_MVS_PROFILE_MSX;
    manifest.region_count = SOUND_REGION_COUNT;
    size_t cursor = SOUND_HEADER_BYTES;
    for (size_t index = 0u; index < SOUND_REGION_COUNT; ++index) {
        if (cursor > content_size ||
            content_size - cursor < SOUND_DESCRIPTOR_BYTES) return 0;
        const uint32_t role = read_u32_be(content + cursor);
        const uint32_t high = read_u32_be(content + cursor + 4u);
        const uint32_t low = read_u32_be(content + cursor + 8u);
        cursor += SOUND_DESCRIPTOR_BYTES;
        if (high != 0u || low == 0u || (size_t)low > content_size - cursor)
            return 0;
        manifest.regions[index] = (gn_mvs_region){
            (gn_mvs_region_role)role, content + cursor, (size_t)low,
            (size_t)low, GN_MVS_LAYOUT_LINEAR};
        cursor += (size_t)low;
    }
    if (cursor != content_size || gn_create(out_instance) != GN_STATUS_OK)
        return 0;
    return gn_load_mvs_v3(*out_instance, &manifest) == GN_STATUS_OK;
}

static int prepare_buffers(void) {
    pixels = (uint32_t *)malloc(SOUND_PIXEL_BYTES);
    if (pixels == NULL || instance == NULL ||
        gn_mvs_audio_capacity_v1(instance, &audio_capacity) != GN_STATUS_OK ||
        audio_capacity == 0u || audio_capacity > SIZE_MAX / (2u * sizeof(int16_t)))
        return 0;
    audio = (int16_t *)malloc(audio_capacity * 2u * sizeof(int16_t));
    return audio != NULL;
}

static int advance(uint32_t input_mask, gn_mvs_frame_result_v1 *result) {
    const gn_mvs_frame_request_v1 request = {
        GN_MVS_FRAME_REQUEST_V1_VERSION, input_mask, GN_PIXEL_XRGB8888,
        SOUND_WIDTH, SOUND_HEIGHT, SOUND_PITCH, (uint8_t *)pixels,
        SOUND_PIXEL_BYTES, audio, audio_capacity
    };
    memset(result, 0, sizeof(*result));
    return gn_mvs_advance_frame_v1(instance, &request, sizeof(request), result,
                                   sizeof(*result)) == GN_STATUS_OK;
}

static uint32_t pixel_at(size_t x, size_t y) {
    uint32_t pixel = 0u;
    memcpy(&pixel, (const uint8_t *)pixels + y * SOUND_PITCH +
                    x * sizeof(pixel), sizeof(pixel));
    return pixel;
}

static int has_square_tone_at_period(const int16_t *samples, size_t frames,
                                    size_t period_samples) {
    if (frames < 800u || period_samples < 2u) return 0;
    int64_t best = 0;
    for (size_t phase = 0u; phase < period_samples; ++phase) {
        int64_t correlation = 0;
        for (size_t frame = 32u; frame < 800u; ++frame) {
            const int sign = ((frame + phase) % period_samples) <
                    period_samples / 2u ? 1 : -1;
            if (samples[frame * 2u] != samples[frame * 2u + 1u]) return 0;
            correlation += (int64_t)samples[frame * 2u] * sign;
        }
        const int64_t magnitude = correlation < 0 ? -correlation : correlation;
        if (magnitude > best) best = magnitude;
    }
    return best / INT64_C(768) >= INT64_C(256);
}

static int has_source_derived_ssg_tone(const int16_t *samples, size_t frames) {
    return has_square_tone_at_period(samples, frames, 48u);
}

static int audio_is_silent(const int16_t *samples, size_t frames) {
    for (size_t frame = 0u; frame < frames; ++frame)
        if (samples[frame * 2u] != 0 || samples[frame * 2u + 1u] != 0)
            return 0;
    return 1;
}

static uint8_t *find_bundle_region(uint32_t target_role, size_t *out_size) {
    if (content == NULL || content_size < SOUND_HEADER_BYTES) return NULL;
    const uint32_t count = read_u32_be(content + 12u);
    size_t cursor = SOUND_HEADER_BYTES;
    for (uint32_t index = 0u; index < count; ++index) {
        if (cursor > content_size ||
            content_size - cursor < SOUND_DESCRIPTOR_BYTES) return NULL;
        const uint32_t role = read_u32_be(content + cursor);
        const uint32_t high = read_u32_be(content + cursor + 4u);
        const uint32_t low = read_u32_be(content + cursor + 8u);
        cursor += SOUND_DESCRIPTOR_BYTES;
        if (high != 0u || low == 0u || (size_t)low > content_size - cursor)
            return NULL;
        if (role == target_role) {
            if (out_size != NULL) *out_size = (size_t)low;
            return content + cursor;
        }
        cursor += (size_t)low;
    }
    return NULL;
}

static size_t find_pattern_offsets(const uint8_t *bytes, size_t size,
                                   const uint8_t *pattern,
                                   size_t pattern_size,
                                   size_t *offsets, size_t capacity) {
    size_t found = 0u;
    if (bytes == NULL || pattern == NULL || pattern_size == 0u ||
        pattern_size > size) return 0u;
    for (size_t index = 0u; index <= size - pattern_size; ++index) {
        if (memcmp(bytes + index, pattern, pattern_size) != 0) continue;
        if (found < capacity && offsets != NULL) offsets[found] = index;
        ++found;
    }
    return found;
}

static int reload_fixture_instance(void) {
    gn_destroy(instance);
    instance = NULL;
    return load_fixture(&instance);
}

static int capture_fire_burst(int16_t *neutral, int16_t *fire,
                              int16_t *released, size_t *out_frames) {
    if (!reload_fixture_instance()) return 0;
    gn_mvs_frame_result_v1 result;
    if (!advance(0u, &result)) return 0;
    const size_t frames = result.audio_frames_delivered;
    if (frames == 0u || frames > GN_MVS_AUDIO_CAPACITY_FRAMES_V1) return 0;
    if (!advance(0u, &result) || result.audio_frames_delivered != frames)
        return 0;
    memcpy(neutral, audio, frames * 2u * sizeof(int16_t));
    if (!advance(GN_MVS_INPUT_P1_A, &result) ||
        result.audio_frames_delivered != frames) return 0;
    memcpy(fire, audio, frames * 2u * sizeof(int16_t));
    if (!advance(0u, &result) || result.audio_frames_delivered != frames)
        return 0;
    memcpy(released, audio, frames * 2u * sizeof(int16_t));
    *out_frames = frames;
    return 1;
}

static size_t different_frames_in_channel(const int16_t *left,
                                          const int16_t *right,
                                          size_t frames, size_t channel,
                                          size_t first_frame) {
    size_t different = 0u;
    for (size_t frame = first_frame; frame < frames; ++frame)
        if (left[frame * 2u + channel] != right[frame * 2u + channel])
            ++different;
    return different;
}

static size_t different_stereo_balance_frames(const int16_t *left,
                                             const int16_t *right,
                                             size_t frames,
                                             size_t first_frame) {
    size_t different = 0u;
    for (size_t frame = first_frame; frame < frames; ++frame) {
        const int32_t left_balance = (int32_t)left[frame * 2u] -
                                     (int32_t)left[frame * 2u + 1u];
        const int32_t right_balance = (int32_t)right[frame * 2u] -
                                      (int32_t)right[frame * 2u + 1u];
        if (left_balance != right_balance) ++different;
    }
    return different;
}

static size_t different_audio_frames(const int16_t *left, const int16_t *right,
                                    size_t frames) {
    size_t different = 0u;
    for (size_t frame = 0u; frame < frames; ++frame) {
        if (left[frame * 2u] != right[frame * 2u] ||
            left[frame * 2u + 1u] != right[frame * 2u + 1u]) ++different;
    }
    return different;
}

static void public_sound_guest_runs_sustained_tone_and_fire_burst(void) {
    TEST_ASSERT_TRUE(read_fixture());
    TEST_ASSERT_TRUE(load_fixture(&instance));
    TEST_ASSERT_TRUE(prepare_buffers());

    gn_mvs_frame_result_v1 result;
    TEST_ASSERT_TRUE(advance(0u, &result));
    TEST_ASSERT_EQUAL_UINT32(GN_MVS_FRAME_RESULT_V1_VERSION, result.version);
    TEST_ASSERT_EQUAL_UINT32(48000u, result.audio_sample_rate);
    TEST_ASSERT_EQUAL_UINT32(2u, result.audio_channels);
    TEST_ASSERT_TRUE(result.audio_frames_generated >= 800u);
    TEST_ASSERT_TRUE(result.audio_frames_generated <= audio_capacity);
    TEST_ASSERT_EQUAL_UINT(result.audio_frames_generated,
                           result.audio_frames_delivered);
    TEST_ASSERT_EQUAL_UINT((SOUND_WIDTH * SOUND_HEIGHT),
                           result.video_pixels_produced);
    TEST_ASSERT_EQUAL_UINT64(result.elapsed_cycles, result.frame_time_numerator);
    TEST_ASSERT_EQUAL_UINT64(UINT64_C(12000000), result.frame_time_denominator);
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x00000000), pixel_at(0u, 0u));
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x00ffffff), pixel_at(1u, 0u));

    TEST_ASSERT_TRUE(advance(0u, &result));
    TEST_ASSERT_TRUE(has_source_derived_ssg_tone(audio,
                                                result.audio_frames_delivered));

    int16_t neutral[GN_MVS_AUDIO_CAPACITY_FRAMES_V1 * 2u];
    const size_t neutral_frames = result.audio_frames_delivered;
    memcpy(neutral, audio, neutral_frames * 2u * sizeof(int16_t));
    TEST_ASSERT_TRUE(advance(GN_MVS_INPUT_P1_A, &result));
    TEST_ASSERT_TRUE(result.audio_frames_delivered >= 800u);
    TEST_ASSERT_TRUE(different_audio_frames(neutral, audio,
                                           result.audio_frames_delivered) > 0u);
}

static void generated_sound_fixture_matches_its_tracked_recipe(void) {
    TEST_ASSERT_TRUE(read_fixture());

    TEST_ASSERT_EQUAL_UINT8('G', content[0]);
    TEST_ASSERT_EQUAL_UINT8('N', content[1]);
    TEST_ASSERT_EQUAL_UINT8('M', content[2]);
    TEST_ASSERT_EQUAL_UINT8('V', content[3]);
    TEST_ASSERT_EQUAL_UINT32(GN_MVS_MANIFEST_VERSION_ZOOM,
                             read_u32_be(content + 4u));
    TEST_ASSERT_EQUAL_UINT32(GN_MVS_PROFILE_MSX, read_u32_be(content + 8u));
    TEST_ASSERT_EQUAL_UINT32(SOUND_REGION_COUNT, read_u32_be(content + 12u));

    static const gn_mvs_region_role roles[SOUND_REGION_COUNT] = {
        GN_MVS_REGION_BIOS, GN_MVS_REGION_PROGRAM, GN_MVS_REGION_FIXED,
        GN_MVS_REGION_AUDIO_PROGRAM, GN_MVS_REGION_SAMPLES,
        GN_MVS_REGION_SPRITES, GN_MVS_REGION_AUDIO_BIOS,
        GN_MVS_REGION_Y_ZOOM
    };
    static const size_t sizes[SOUND_REGION_COUNT] = {
        GN_MVS_BIOS_BYTES, GN_MVS_PROGRAM_BYTES, GN_MVS_FIXED_BYTES,
        GN_MVS_AUDIO_PROGRAM_BYTES, GN_MVS_SAMPLES_BYTES,
        GN_MVS_SPRITES_BYTES, GN_MVS_AUDIO_BIOS_BYTES,
        GN_MVS_Y_ZOOM_BYTES
    };
    size_t cursor = SOUND_HEADER_BYTES;
    for (size_t index = 0u; index < SOUND_REGION_COUNT; ++index) {
        TEST_ASSERT_TRUE(cursor <= content_size);
        TEST_ASSERT_TRUE(content_size - cursor >= SOUND_DESCRIPTOR_BYTES);
        TEST_ASSERT_EQUAL_UINT32(roles[index], read_u32_be(content + cursor));
        TEST_ASSERT_EQUAL_UINT32(0u, read_u32_be(content + cursor + 4u));
        TEST_ASSERT_EQUAL_UINT32(sizes[index],
                                 read_u32_be(content + cursor + 8u));
        cursor += SOUND_DESCRIPTOR_BYTES;
        TEST_ASSERT_TRUE(sizes[index] <= content_size - cursor);
        cursor += sizes[index];
    }
    TEST_ASSERT_EQUAL_UINT(content_size, cursor);
    TEST_ASSERT_EQUAL_UINT(67108976u, content_size);

    /* These are fixture launch instructions in the BIOS role, not a BIOS. */
    static const uint8_t launch_vectors[] = {
        0x00u, 0x10u, 0xffu, 0xfeu, 0x00u, 0xc0u, 0x01u, 0x00u
    };
    size_t main_region_size = 0u;
    uint8_t *main_region = find_bundle_region(GN_MVS_REGION_BIOS,
                                              &main_region_size);
    TEST_ASSERT_NOT_NULL(main_region);
    TEST_ASSERT_TRUE(main_region_size >= SOUND_MAIN_ENTRY_OFFSET);
    TEST_ASSERT_EQUAL_MEMORY(launch_vectors, main_region,
                             sizeof(launch_vectors));
    static const uint8_t initial_music_command[] = {
        0x13u, 0xfcu, 0x00u, 0x3cu, 0x00u, 0x32u, 0x00u, 0x00u
    };
    TEST_ASSERT_EQUAL_UINT(2u, find_pattern_offsets(
        main_region, main_region_size, initial_music_command,
        sizeof(initial_music_command), NULL, 0u));
    static const uint8_t active_low_fire_poll[] = {
        0x10u, 0x39u, 0x00u, 0x30u, 0x00u, 0x00u,
        0x0cu, 0x00u, 0x00u, 0xefu
    };
    TEST_ASSERT_EQUAL_UINT(1u, find_pattern_offsets(
        main_region, main_region_size, active_low_fire_poll,
        sizeof(active_low_fire_poll), NULL, 0u));

    static const uint8_t sound_boot[] = {
        0x31u, 0xffu, 0xffu, 0x3eu, 0x00u, 0xd3u,
        0x08u, 0xfbu, 0x76u, 0x18u, 0xfdu
    };
    size_t sound_region_size = 0u;
    uint8_t *sound_region = find_bundle_region(GN_MVS_REGION_AUDIO_BIOS,
                                                &sound_region_size);
    TEST_ASSERT_NOT_NULL(sound_region);
    TEST_ASSERT_TRUE(sound_region_size >= 0x68u);
    TEST_ASSERT_EQUAL_MEMORY(sound_boot, sound_region, sizeof(sound_boot));
    static const uint8_t music_dispatch[] = {0xfeu, 0x3cu};
    static const uint8_t action_dispatch[] = {0xfeu, 0xa5u};
    TEST_ASSERT_EQUAL_UINT(1u, find_pattern_offsets(
        sound_region + 0x66u, sound_region_size - 0x66u,
        music_dispatch, sizeof(music_dispatch), NULL, 0u));
    TEST_ASSERT_EQUAL_UINT(1u, find_pattern_offsets(
        sound_region + 0x66u, sound_region_size - 0x66u,
        action_dispatch, sizeof(action_dispatch), NULL, 0u));
    static const uint8_t adpcm_b_fixture_program[] = {
        0x3eu, 0x11u, 0xd3u, 0x04u, 0x3eu, 0xc0u, 0xd3u, 0x05u,
        0x3eu, 0x12u, 0xd3u, 0x04u, 0x3eu, 0x00u, 0xd3u, 0x05u,
        0x3eu, 0x13u, 0xd3u, 0x04u, 0x3eu, 0x00u, 0xd3u, 0x05u,
        0x3eu, 0x14u, 0xd3u, 0x04u, 0x3eu, 0x00u, 0xd3u, 0x05u,
        0x3eu, 0x15u, 0xd3u, 0x04u, 0x3eu, 0x00u, 0xd3u, 0x05u,
        0x3eu, 0x19u, 0xd3u, 0x04u, 0x3eu, 0xffu, 0xd3u, 0x05u,
        0x3eu, 0x1au, 0xd3u, 0x04u, 0x3eu, 0xffu, 0xd3u, 0x05u,
        0x3eu, 0x1bu, 0xd3u, 0x04u, 0x3eu, 0xffu, 0xd3u, 0x05u,
        0x3eu, 0x10u, 0xd3u, 0x04u, 0x3eu, 0x80u, 0xd3u, 0x05u
    };
    TEST_ASSERT_EQUAL_UINT(1u, find_pattern_offsets(
        sound_region + 0x66u, sound_region_size - 0x66u,
        adpcm_b_fixture_program, sizeof(adpcm_b_fixture_program), NULL, 0u));

    size_t fixed_size = 0u;
    uint8_t *fixed = find_bundle_region(GN_MVS_REGION_FIXED, &fixed_size);
    TEST_ASSERT_NOT_NULL(fixed);
    TEST_ASSERT_TRUE(fixed_size >= 0x39u);
    static const size_t original_tile_offsets[] = {
        0x20u, 0x28u, 0x30u, 0x38u
    };
    static const uint8_t original_tile_rows[] = {0x05u, 0x07u, 0x20u, 0x03u};
    for (size_t row = 0u; row < sizeof(original_tile_rows); ++row)
        TEST_ASSERT_EQUAL_UINT8(original_tile_rows[row],
                                fixed[original_tile_offsets[row]]);

    size_t sample_region_size = 0u;
    uint8_t *sample = find_bundle_region(GN_MVS_REGION_SAMPLES,
                                         &sample_region_size);
    TEST_ASSERT_NOT_NULL(sample);
    TEST_ASSERT_TRUE(sample_region_size >= 256u);
    for (size_t index = 0u; index < 256u; ++index) {
        const uint8_t high = (uint8_t)((index * 3u + 5u) & 0x0fu);
        const uint8_t low = (uint8_t)((index * 7u + 2u) & 0x0fu);
        TEST_ASSERT_EQUAL_UINT8((uint8_t)((uint8_t)(high << 4) | low),
                                sample[index]);
    }
    for (size_t index = 256u; index < sample_region_size; ++index)
        TEST_ASSERT_EQUAL_UINT8(0u, sample[index]);

    uint8_t *rebuilt = (uint8_t *)malloc(content_size);
    TEST_ASSERT_NOT_NULL(rebuilt);
    TEST_ASSERT_TRUE(public_sound_guest_build(rebuilt, content_size));
    TEST_ASSERT_EQUAL_MEMORY(content, rebuilt, content_size);
    free(rebuilt);
}

static void public_sound_guest_controls_are_falsifiable(void) {
    TEST_ASSERT_TRUE(read_fixture());
    TEST_ASSERT_TRUE(load_fixture(&instance));
    TEST_ASSERT_TRUE(prepare_buffers());

    gn_mvs_frame_result_v1 result;
    TEST_ASSERT_TRUE(advance(0u, &result));
    TEST_ASSERT_TRUE(advance(0u, &result));
    TEST_ASSERT_TRUE(has_source_derived_ssg_tone(audio,
                                                result.audio_frames_delivered));

    size_t audio_bios_size = 0u;
    uint8_t *audio_bios = find_bundle_region(GN_MVS_REGION_AUDIO_BIOS,
                                              &audio_bios_size);
    TEST_ASSERT_NOT_NULL(audio_bios);

    static const uint8_t ssg_period_write[] = {
        0x3eu, 0x00u, 0xd3u, 0x04u, 0x3eu, 0x7du, 0xd3u, 0x05u};
    size_t pitch_offsets[2] = {0u, 0u};
    TEST_ASSERT_EQUAL_UINT(2u, find_pattern_offsets(
        audio_bios, audio_bios_size, ssg_period_write,
        sizeof(ssg_period_write), pitch_offsets,
        sizeof(pitch_offsets) / sizeof(pitch_offsets[0])));
    audio_bios[pitch_offsets[0] + 5u] = 0x3eu;
    audio_bios[pitch_offsets[1] + 5u] = 0x3eu;
    TEST_ASSERT_TRUE(reload_fixture_instance());
    TEST_ASSERT_TRUE(advance(0u, &result));
    TEST_ASSERT_TRUE(advance(0u, &result));
    TEST_ASSERT_TRUE(has_square_tone_at_period(
        audio, result.audio_frames_delivered, 24u));
    TEST_ASSERT_FALSE(has_source_derived_ssg_tone(
        audio, result.audio_frames_delivered));
    audio_bios[pitch_offsets[0] + 5u] = 0x7du;
    audio_bios[pitch_offsets[1] + 5u] = 0x7du;

    static const uint8_t wrong_sound_command[] = {0xfeu, 0x3cu};
    size_t command_offset = 0u;
    TEST_ASSERT_EQUAL_UINT(1u, find_pattern_offsets(
        audio_bios, audio_bios_size, wrong_sound_command,
        sizeof(wrong_sound_command), &command_offset, 1u));
    audio_bios[command_offset + 1u] = 0x55u;
    TEST_ASSERT_TRUE(reload_fixture_instance());
    TEST_ASSERT_TRUE(advance(0u, &result));
    TEST_ASSERT_TRUE(advance(0u, &result));
    TEST_ASSERT_TRUE(audio_is_silent(audio, result.audio_frames_delivered));
    audio_bios[command_offset + 1u] = 0x3cu;

    size_t main_bios_size = 0u;
    uint8_t *main_bios = find_bundle_region(GN_MVS_REGION_BIOS,
                                             &main_bios_size);
    TEST_ASSERT_NOT_NULL(main_bios);
    static const uint8_t initial_music_command[] = {
        0x13u, 0xfcu, 0x00u, 0x3cu, 0x00u, 0x32u, 0x00u, 0x00u};
    size_t main_command_offset = 0u;
    TEST_ASSERT_EQUAL_UINT(2u, find_pattern_offsets(
        main_bios, main_bios_size, initial_music_command,
        sizeof(initial_music_command), NULL, 0u));
    TEST_ASSERT_TRUE(find_pattern_offsets(
        main_bios, main_bios_size, initial_music_command,
        sizeof(initial_music_command), &main_command_offset, 1u) >= 1u);
    static const uint8_t no_op_sequence[] = {
        0x4eu, 0x71u, 0x4eu, 0x71u, 0x4eu, 0x71u, 0x4eu, 0x71u};
    uint8_t saved_command[sizeof(initial_music_command)];
    memcpy(saved_command, main_bios + main_command_offset,
           sizeof(saved_command));
    main_bios[main_command_offset + 3u] = 0x00u; /* Sound key-off command. */
    TEST_ASSERT_TRUE(reload_fixture_instance());
    TEST_ASSERT_TRUE(advance(0u, &result));
    TEST_ASSERT_TRUE(advance(0u, &result));
    TEST_ASSERT_TRUE(audio_is_silent(audio, result.audio_frames_delivered));
    memcpy(main_bios + main_command_offset, saved_command,
           sizeof(saved_command));

    memcpy(main_bios + main_command_offset, no_op_sequence,
           sizeof(no_op_sequence));
    TEST_ASSERT_TRUE(reload_fixture_instance());
    TEST_ASSERT_TRUE(advance(0u, &result));
    TEST_ASSERT_TRUE(advance(0u, &result));
    TEST_ASSERT_TRUE(audio_is_silent(audio, result.audio_frames_delivered));
    memcpy(main_bios + main_command_offset, saved_command,
           sizeof(saved_command));

    int16_t neutral[GN_MVS_AUDIO_CAPACITY_FRAMES_V1 * 2u];
    int16_t fire[GN_MVS_AUDIO_CAPACITY_FRAMES_V1 * 2u];
    int16_t released[GN_MVS_AUDIO_CAPACITY_FRAMES_V1 * 2u];
    int16_t variant_neutral[GN_MVS_AUDIO_CAPACITY_FRAMES_V1 * 2u];
    int16_t variant_fire[GN_MVS_AUDIO_CAPACITY_FRAMES_V1 * 2u];
    int16_t variant_released[GN_MVS_AUDIO_CAPACITY_FRAMES_V1 * 2u];
    size_t frames = 0u;
    size_t variant_frames = 0u;
    TEST_ASSERT_TRUE(capture_fire_burst(neutral, fire, released, &frames));
    TEST_ASSERT_TRUE(different_audio_frames(neutral, fire, frames) > 0u);
    TEST_ASSERT_TRUE(has_source_derived_ssg_tone(released, frames));
    for (size_t frame = 0u; frame < frames; ++frame)
        TEST_ASSERT_EQUAL_INT16(fire[frame * 2u], fire[frame * 2u + 1u]);

    static const uint8_t adpcm_pan_write[] = {
        0x3eu, 0x11u, 0xd3u, 0x04u, 0x3eu, 0xc0u, 0xd3u, 0x05u};
    size_t pan_offset = 0u;
    TEST_ASSERT_EQUAL_UINT(1u, find_pattern_offsets(
        audio_bios, audio_bios_size, adpcm_pan_write,
        sizeof(adpcm_pan_write), &pan_offset, 1u));
    audio_bios[pan_offset + 5u] = 0x80u; /* Original sample routed left only. */
    TEST_ASSERT_TRUE(capture_fire_burst(variant_neutral, variant_fire,
                                        variant_released, &variant_frames));
    TEST_ASSERT_EQUAL_UINT(frames, variant_frames);
    TEST_ASSERT_TRUE(different_stereo_balance_frames(
        variant_neutral, variant_fire, frames, 32u) > 0u);
    TEST_ASSERT_TRUE(different_frames_in_channel(
        variant_neutral, variant_fire, frames, 0u, 32u) > 0u);
    for (size_t frame = 32u; frame < frames; ++frame)
        TEST_ASSERT_EQUAL_INT16(variant_released[frame * 2u],
                                variant_released[frame * 2u + 1u]);
    audio_bios[pan_offset + 5u] = 0xc0u;

    size_t sample_size = 0u;
    uint8_t *sample = find_bundle_region(GN_MVS_REGION_SAMPLES, &sample_size);
    TEST_ASSERT_NOT_NULL(sample);
    TEST_ASSERT_TRUE(sample_size >= 256u);
    uint8_t original_sample[256u];
    memcpy(original_sample, sample, sizeof(original_sample));
    memset(sample, 0, sizeof(original_sample));
    TEST_ASSERT_TRUE(capture_fire_burst(variant_neutral, variant_fire,
                                        variant_released, &variant_frames));
    TEST_ASSERT_EQUAL_UINT(frames, variant_frames);
    TEST_ASSERT_TRUE(different_audio_frames(fire, variant_fire, frames) > 0u);
    memcpy(sample, original_sample, sizeof(original_sample));
}

int main(int argc, char **argv) {
    if (argc == 3 && strcmp(argv[1], "--write-fixture") == 0)
        return public_sound_guest_write(argv[2]) ? 0 : 1;
    if (argc != 2) {
        (void)fprintf(stderr,
            "usage: %s <public-sound-mvs.bin> | --write-fixture <path>\n", argv[0]);
        return 2;
    }
    fixture_path = argv[1];
    UNITY_BEGIN();
    RUN_TEST(public_sound_guest_runs_sustained_tone_and_fire_burst);
    RUN_TEST(generated_sound_fixture_matches_its_tracked_recipe);
    RUN_TEST(public_sound_guest_controls_are_falsifiable);
    return UNITY_END();
}
