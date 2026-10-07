/* SPDX-License-Identifier: MIT */
#include "glueyneo/glueyneo.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "unity.h"

#define PUBLIC_WIDTH 320u
#define PUBLIC_HEIGHT 224u
#define PUBLIC_PITCH (PUBLIC_WIDTH * sizeof(uint32_t))
#define PUBLIC_PIXEL_BYTES (PUBLIC_PITCH * PUBLIC_HEIGHT)
#define PUBLIC_CONTENT_SIZE 602u

static gn_instance *instance;
static uint8_t content[PUBLIC_CONTENT_SIZE];
static uint8_t pixels[PUBLIC_PIXEL_BYTES + 1u];
static const char *fixture_path;

void setUp(void) {
    instance = NULL;
    memset(content, 0, sizeof(content));
    memset(pixels, 0xa5, sizeof(pixels));
}

void tearDown(void) {
    gn_destroy(instance);
    instance = NULL;
}

static uint32_t pixel_at(uint32_t x, uint32_t y) {
    uint32_t pixel = 0u;
    memcpy(&pixel, pixels + (size_t)y * PUBLIC_PITCH +
                       (size_t)x * sizeof(pixel), sizeof(pixel));
    return pixel;
}

static int read_fixture(const char *path) {
    FILE *file = fopen(path, "rb");
    if (file == NULL) return 0;
    const size_t count = fread(content, 1u, sizeof(content), file);
    const int extra = fgetc(file);
    const int close_status = fclose(file);
    return count == sizeof(content) && extra == EOF && close_status == 0;
}

static gn_status load_public_fixture(void) {
    gn_manifest manifest;
    memset(&manifest, 0, sizeof(manifest));
    manifest.version = GN_MANIFEST_VERSION;
    manifest.profile = GN_PROFILE_PUBLIC_FIXTURE;
    manifest.region_count = 1u;
    manifest.regions[0] = (gn_region){0u, PUBLIC_CONTENT_SIZE, content,
                                      sizeof(content), GN_REGION_ROM};
    gn_status status = gn_create(&instance);
    if (status != GN_STATUS_OK) return status;
    return gn_load(instance, &manifest);
}

static gn_status advance(uint32_t input, gn_frame_result *result) {
    const gn_frame_request request = {
        input, GN_PIXEL_XRGB8888, PUBLIC_WIDTH, PUBLIC_HEIGHT, PUBLIC_PITCH,
        pixels, PUBLIC_PIXEL_BYTES, NULL, 0u};
    return gn_advance_frame(instance, &request, result);
}

static void public_guest_fixed_right_trace_has_guest_state_and_pixels(void) {
    TEST_ASSERT_TRUE(read_fixture(fixture_path));
    TEST_ASSERT_EQUAL_INT(GN_STATUS_OK, load_public_fixture());
    static const uint32_t inputs[] = {0u, GN_INPUT_RIGHT, GN_INPUT_RIGHT};
    static const uint32_t expected_x[] = {16u, 17u, 18u};
    gn_frame_result frame;
    for (size_t index = 0u; index < 3u; ++index) {
        TEST_ASSERT_EQUAL_INT(GN_STATUS_OK, advance(inputs[index], &frame));
        TEST_ASSERT_EQUAL_UINT32(expected_x[index], frame.marker_x);
        TEST_ASSERT_EQUAL_UINT32(16u, frame.marker_y);
        TEST_ASSERT_EQUAL_UINT64(UINT64_C(200000), frame.requested_cycles);
        TEST_ASSERT_EQUAL_UINT64(UINT64_C(200000), frame.elapsed_cycles);
        TEST_ASSERT_EQUAL_INT(GN_RUN_STOPPED, frame.reason);
        TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x00000000), pixel_at(0u, 0u));
        TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x00ffffff), pixel_at(expected_x[index], 16u));
        TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x00ffffff), pixel_at(expected_x[index] + 7u, 16u));
        TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x00000000), pixel_at(expected_x[index] + 8u, 16u));
        if (index > 0u) {
            TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x00000000), pixel_at(expected_x[index] - 1u, 16u));
        }
    }
}

static void public_guest_left_control_fails_rightward_trace_safely(void) {
    TEST_ASSERT_TRUE(read_fixture(fixture_path));
    TEST_ASSERT_EQUAL_INT(GN_STATUS_OK, load_public_fixture());
    static const uint32_t inputs[] = {0u, GN_INPUT_LEFT, GN_INPUT_LEFT};
    static const uint32_t expected_right_x[] = {16u, 17u, 18u};
    gn_frame_result frame;
    int rightward_trace_matched = 1;
    for (size_t index = 0u; index < 3u; ++index) {
        TEST_ASSERT_EQUAL_INT(GN_STATUS_OK, advance(inputs[index], &frame));
        TEST_ASSERT_EQUAL_UINT32(16u, frame.marker_x);
        TEST_ASSERT_EQUAL_UINT32(16u, frame.marker_y);
        TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x00ffffff), pixel_at(16u, 16u));
        TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x00000000), pixel_at(24u, 16u));
        if (frame.marker_x != expected_right_x[index]) rightward_trace_matched = 0;
        if (index > 0u) {
            TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x00000000),
                                     pixel_at(expected_right_x[index] + 7u, 16u));
        }
    }
    TEST_ASSERT_FALSE(rightward_trace_matched);
}

static void public_guest_no_input_control_fails_rightward_trace_safely(void) {
    TEST_ASSERT_TRUE(read_fixture(fixture_path));
    TEST_ASSERT_EQUAL_INT(GN_STATUS_OK, load_public_fixture());
    static const uint32_t expected_right_x[] = {16u, 17u, 18u};
    gn_frame_result frame;
    int rightward_trace_matched = 1;
    for (size_t index = 0u; index < 3u; ++index) {
        TEST_ASSERT_EQUAL_INT(GN_STATUS_OK, advance(0u, &frame));
        TEST_ASSERT_EQUAL_UINT32(16u, frame.marker_x);
        TEST_ASSERT_EQUAL_UINT32(16u, frame.marker_y);
        TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x00ffffff), pixel_at(16u, 16u));
        TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x00000000), pixel_at(24u, 16u));
        if (frame.marker_x != expected_right_x[index]) rightward_trace_matched = 0;
        if (index > 0u) {
            TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x00000000),
                                     pixel_at(expected_right_x[index] + 7u, 16u));
        }
    }
    TEST_ASSERT_FALSE(rightward_trace_matched);
}

static void bounded_frame_metadata_and_canary_are_exact(void) {
    TEST_ASSERT_TRUE(read_fixture(fixture_path));
    TEST_ASSERT_EQUAL_INT(GN_STATUS_OK, load_public_fixture());
    memset(pixels, 0xa5, sizeof(pixels));
    pixels[PUBLIC_PIXEL_BYTES] = 0xa5u;
    memset(content, 0x5a, sizeof(content)); /* Successful gn_load owns code, seed, and tile bytes. */
    gn_frame_result frame;
    TEST_ASSERT_EQUAL_INT(GN_STATUS_OK, advance(0u, &frame));
    TEST_ASSERT_EQUAL_UINT64(UINT64_C(200000), frame.frame_time_numerator);
    TEST_ASSERT_EQUAL_UINT64(UINT64_C(12000000), frame.frame_time_denominator);
    TEST_ASSERT_EQUAL_UINT32(12000000u, frame.machine_clock_hz_numerator);
    TEST_ASSERT_EQUAL_UINT32(1u, frame.machine_clock_hz_denominator);
    TEST_ASSERT_EQUAL_INT(GN_AUDIO_S16_INTERLEAVED_STEREO, frame.audio_format);
    TEST_ASSERT_EQUAL_UINT32(48000u, frame.audio_sample_rate);
    TEST_ASSERT_EQUAL_UINT32(2u, frame.audio_channels);
    TEST_ASSERT_EQUAL_UINT(0u, frame.audio_frames_produced);
    TEST_ASSERT_EQUAL_UINT(PUBLIC_WIDTH * PUBLIC_HEIGHT, frame.video_pixels_produced);
    TEST_ASSERT_EQUAL_HEX8(0xa5u, pixels[PUBLIC_PIXEL_BYTES]);

    int16_t audio[4] = {INT16_C(0x1234), INT16_C(0x2345),
                        INT16_C(0x3456), INT16_C(0x4567)};
    gn_frame_request request = {0u, GN_PIXEL_XRGB8888, PUBLIC_WIDTH, PUBLIC_HEIGHT,
        PUBLIC_PITCH, pixels, PUBLIC_PIXEL_BYTES, audio, 2u};
    TEST_ASSERT_EQUAL_INT(GN_STATUS_OK, gn_advance_frame(instance, &request, &frame));
    TEST_ASSERT_EQUAL_INT16(INT16_C(0x1234), audio[0]);
    TEST_ASSERT_EQUAL_INT16(INT16_C(0x2345), audio[1]);
    TEST_ASSERT_EQUAL_INT16(INT16_C(0x3456), audio[2]);
    TEST_ASSERT_EQUAL_INT16(INT16_C(0x4567), audio[3]);
    TEST_ASSERT_EQUAL_UINT(0u, frame.audio_frames_produced);
}

static void frame_preflight_rejections_do_not_mutate_guest_or_touch_canary(void) {
    TEST_ASSERT_TRUE(read_fixture(fixture_path));
    TEST_ASSERT_EQUAL_INT(GN_STATUS_OK, load_public_fixture());
    memset(pixels, 0xa5, sizeof(pixels));
    pixels[PUBLIC_PIXEL_BYTES - 1u] = 0xa5u;
    gn_frame_result frame;
    gn_frame_request request = {0u, GN_PIXEL_XRGB8888, PUBLIC_WIDTH, PUBLIC_HEIGHT,
        PUBLIC_PITCH, pixels, PUBLIC_PIXEL_BYTES - 1u, NULL, 0u};
    TEST_ASSERT_EQUAL_INT(GN_STATUS_INVALID_ARGUMENT,
                          gn_advance_frame(instance, &request, &frame));
    TEST_ASSERT_EQUAL_HEX8(0xa5u, pixels[PUBLIC_PIXEL_BYTES - 1u]);

    request.input_mask = GN_INPUT_RIGHT;
    request.pixel_capacity_bytes = PUBLIC_PIXEL_BYTES;
    request.pixels = NULL;
    TEST_ASSERT_EQUAL_INT(GN_STATUS_INVALID_ARGUMENT,
                          gn_advance_frame(instance, &request, &frame));
    request.pixels = pixels;
    request.audio_capacity_frames = 1u;
    TEST_ASSERT_EQUAL_INT(GN_STATUS_INVALID_ARGUMENT,
                          gn_advance_frame(instance, &request, &frame));
    request.audio_capacity_frames = 0u;
    request.pixel_format = (gn_pixel_format)99;
    TEST_ASSERT_EQUAL_INT(GN_STATUS_INVALID_ARGUMENT,
                          gn_advance_frame(instance, &request, &frame));
    request.pixel_format = GN_PIXEL_XRGB8888;
    request.width = PUBLIC_WIDTH - 1u;
    TEST_ASSERT_EQUAL_INT(GN_STATUS_INVALID_ARGUMENT,
                          gn_advance_frame(instance, &request, &frame));
    request.width = PUBLIC_WIDTH;
    request.height = PUBLIC_HEIGHT - 1u;
    TEST_ASSERT_EQUAL_INT(GN_STATUS_INVALID_ARGUMENT,
                          gn_advance_frame(instance, &request, &frame));
    request.height = PUBLIC_HEIGHT;
    request.pitch_bytes = SIZE_MAX;
    request.pixel_capacity_bytes = SIZE_MAX;
    TEST_ASSERT_EQUAL_INT(GN_STATUS_INVALID_ARGUMENT,
                          gn_advance_frame(instance, &request, &frame));
    request.pitch_bytes = PUBLIC_PITCH;
    request.pixel_capacity_bytes = PUBLIC_PIXEL_BYTES;
    request.input_mask = UINT32_C(0x8000);
    TEST_ASSERT_EQUAL_INT(GN_STATUS_INVALID_ARGUMENT,
                          gn_advance_frame(instance, &request, &frame));

    request.input_mask = GN_INPUT_RIGHT;
    TEST_ASSERT_EQUAL_INT(GN_STATUS_OK, gn_advance_frame(instance, &request, &frame));
    TEST_ASSERT_EQUAL_UINT32(17u, frame.marker_x);
}

static void padded_pixel_pitch_and_supported_left_input_are_safe(void) {
    TEST_ASSERT_TRUE(read_fixture(fixture_path));
    TEST_ASSERT_EQUAL_INT(GN_STATUS_OK, load_public_fixture());
    const size_t pitch = PUBLIC_PITCH + 16u;
    const size_t required = pitch * (PUBLIC_HEIGHT - 1u) + PUBLIC_PITCH;
    uint8_t guarded[PUBLIC_PIXEL_BYTES + 16u * PUBLIC_HEIGHT + 1u];
    memset(guarded, 0xa5, sizeof(guarded));
    guarded[required] = 0x5au;
    gn_frame_request request = {GN_INPUT_LEFT, GN_PIXEL_XRGB8888,
        PUBLIC_WIDTH, PUBLIC_HEIGHT, pitch, guarded, required, NULL, 0u};
    gn_frame_result frame;
    TEST_ASSERT_EQUAL_INT(GN_STATUS_OK, gn_advance_frame(instance, &request, &frame));
    TEST_ASSERT_EQUAL_UINT32(16u, frame.marker_x);
    TEST_ASSERT_EQUAL_HEX8(0x5au, guarded[required]);
    uint32_t pixel = UINT32_MAX;
    memcpy(&pixel, guarded + (size_t)16u * pitch + (size_t)16u * sizeof(pixel),
           sizeof(pixel));
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x00ffffff), pixel);
}

static void public_fixture_rejects_bad_envelopes_and_keeps_live_image(void) {
    TEST_ASSERT_TRUE(read_fixture(fixture_path));
    TEST_ASSERT_EQUAL_INT(GN_STATUS_OK, load_public_fixture());
    uint8_t malformed[PUBLIC_CONTENT_SIZE];
    memcpy(malformed, content, sizeof(malformed));
    malformed[7] = 2u; /* Unsupported version in the strict GNFX v1 envelope. */
    gn_manifest manifest;
    memset(&manifest, 0, sizeof(manifest));
    manifest.version = GN_MANIFEST_VERSION;
    manifest.profile = GN_PROFILE_PUBLIC_FIXTURE;
    manifest.region_count = 1u;
    manifest.regions[0] = (gn_region){0u, PUBLIC_CONTENT_SIZE, malformed,
                                      sizeof(malformed), GN_REGION_ROM};
    TEST_ASSERT_EQUAL_INT(GN_STATUS_INVALID_MEDIA, gn_load(instance, &manifest));
    gn_frame_result frame;
    TEST_ASSERT_EQUAL_INT(GN_STATUS_OK, advance(GN_INPUT_RIGHT, &frame));
    TEST_ASSERT_EQUAL_UINT32(17u, frame.marker_x);
}

int main(int argc, char **argv) {
    if (argc == 3 && strcmp(argv[1], "--write-fixture") == 0) {
        extern int public_guest_write(const char *path);
        return public_guest_write(argv[2]) ? 0 : 1;
    }
    if (argc != 2 && argc != 3) {
        (void)fprintf(stderr, "usage: %s <public-playable.bin> [trace|negative-left|negative-none] | --write-fixture <path>\n", argv[0]);
        return 2;
    }
    extern size_t public_guest_content_size(void);
    fixture_path = argv[1];
    UNITY_BEGIN();
    if (argc == 2 || strcmp(argv[2], "trace") == 0) {
        RUN_TEST(public_guest_fixed_right_trace_has_guest_state_and_pixels);
    }
    if (argc == 2) {
        RUN_TEST(bounded_frame_metadata_and_canary_are_exact);
        RUN_TEST(frame_preflight_rejections_do_not_mutate_guest_or_touch_canary);
        RUN_TEST(padded_pixel_pitch_and_supported_left_input_are_safe);
        RUN_TEST(public_guest_left_control_fails_rightward_trace_safely);
        RUN_TEST(public_guest_no_input_control_fails_rightward_trace_safely);
        RUN_TEST(public_fixture_rejects_bad_envelopes_and_keeps_live_image);
    } else if (strcmp(argv[2], "negative-left") == 0) {
        RUN_TEST(public_guest_left_control_fails_rightward_trace_safely);
    } else if (strcmp(argv[2], "negative-none") == 0) {
        RUN_TEST(public_guest_no_input_control_fails_rightward_trace_safely);
    } else if (strcmp(argv[2], "trace") != 0) {
        (void)fprintf(stderr, "unknown public fixture test case: %s\n", argv[2]);
        return 2;
    }
    const int failures = UNITY_END();
    return failures;
}
