/* SPDX-License-Identifier: MIT */
#include "glueyneo/glueyneo.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "unity.h"

#define PUBLIC_WIDTH 320u
#define PUBLIC_HEIGHT 224u
#define PUBLIC_PITCH (PUBLIC_WIDTH * sizeof(uint32_t))
#define PUBLIC_CONTENT_SIZE 602u

static gn_instance *instance;
static uint8_t content[PUBLIC_CONTENT_SIZE];
static uint32_t pixels[PUBLIC_WIDTH * PUBLIC_HEIGHT];
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
    memcpy(&pixel, (const uint8_t *)pixels + (size_t)y * PUBLIC_PITCH +
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
        (uint8_t *)pixels, sizeof(pixels)};
    return gn_advance_frame(instance, &request, result);
}

static void generated_guest_moves_guest_owned_marker(void) {
    TEST_ASSERT_TRUE(read_fixture(fixture_path));
    TEST_ASSERT_EQUAL_INT(GN_STATUS_OK, load_public_fixture());
    gn_frame_result frame;
    TEST_ASSERT_EQUAL_INT(GN_STATUS_OK, advance(0u, &frame));
    TEST_ASSERT_EQUAL_UINT32(16u, frame.marker_x);
    TEST_ASSERT_EQUAL_UINT32(16u, frame.marker_y);
    TEST_ASSERT_EQUAL_UINT64(UINT64_C(200000), frame.requested_cycles);
    TEST_ASSERT_EQUAL_UINT64(UINT64_C(200000), frame.elapsed_cycles);
    TEST_ASSERT_EQUAL_INT(GN_RUN_STOPPED, frame.reason);
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x00ffffff), pixel_at(16u, 16u));
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x00000000), pixel_at(24u, 16u));

    TEST_ASSERT_EQUAL_INT(GN_STATUS_OK, advance(GN_INPUT_RIGHT, &frame));
    TEST_ASSERT_EQUAL_UINT32(17u, frame.marker_x);
    TEST_ASSERT_EQUAL_UINT32(16u, frame.marker_y);
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x00000000), pixel_at(16u, 16u));
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x00ffffff), pixel_at(17u, 16u));
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x00ffffff), pixel_at(24u, 16u));
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x00000000), pixel_at(25u, 16u));
}

int main(int argc, char **argv) {
    if (argc == 3 && strcmp(argv[1], "--write-fixture") == 0) {
        extern int public_guest_write(const char *path);
        return public_guest_write(argv[2]) ? 0 : 1;
    }
    if (argc != 2) {
        (void)fprintf(stderr, "usage: %s <public-playable.bin> | --write-fixture <path>\n", argv[0]);
        return 2;
    }
    extern size_t public_guest_content_size(void);
    fixture_path = argv[1];
    UNITY_BEGIN();
    RUN_TEST(generated_guest_moves_guest_owned_marker);
    const int failures = UNITY_END();
    return failures;
}
