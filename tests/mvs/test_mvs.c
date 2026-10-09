/* SPDX-License-Identifier: MIT */
#include "glueyneo/glueyneo.h"
#include "libretro.h"
#include "sdk_private.h"

#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <zlib.h>

int mvs_import_memory(const uint8_t *zip, size_t zip_size,
                      uint8_t **out_bundle, size_t *out_size);

enum { REGION_COUNT = 6 };
static unsigned pixel_requests;

static void put16le(uint8_t *p, uint16_t value) {
    p[0] = (uint8_t)value; p[1] = (uint8_t)(value >> 8);
}
static void put32le(uint8_t *p, uint32_t value) {
    p[0] = (uint8_t)value; p[1] = (uint8_t)(value >> 8);
    p[2] = (uint8_t)(value >> 16); p[3] = (uint8_t)(value >> 24);
}
static uint32_t get32be(const uint8_t *p) {
    return ((uint32_t)p[0] << 24) | ((uint32_t)p[1] << 16) |
           ((uint32_t)p[2] << 8) | p[3];
}
static uint64_t get64be(const uint8_t *p) {
    return ((uint64_t)get32be(p) << 32) | get32be(p + 4);
}
static bool environment(unsigned command, void *data) {
    if (command == RETRO_ENVIRONMENT_SET_PIXEL_FORMAT && data != NULL &&
        *(enum retro_pixel_format *)data == RETRO_PIXEL_FORMAT_XRGB8888) {
        ++pixel_requests;
        return true;
    }
    return false;
}

static void build_zip(uint8_t *zip, size_t capacity, size_t *out_size,
                      uint8_t *regions[REGION_COUNT],
                      size_t lengths[REGION_COUNT]) {
    static const char *const names[REGION_COUNT] = {
        "bios.bin", "program.bin", "fixed.bin", "audio.bin",
        "samples.bin", "sprites.bin"};
    static const size_t expected[REGION_COUNT] = {
        GN_MVS_BIOS_BYTES, GN_MVS_PROGRAM_BYTES, GN_MVS_FIXED_BYTES,
        GN_MVS_AUDIO_PROGRAM_BYTES, GN_MVS_SAMPLES_BYTES,
        GN_MVS_SPRITES_BYTES};
    for (size_t i = 0u; i < REGION_COUNT; ++i) {
        lengths[i] = expected[i];
        regions[i] = (uint8_t *)calloc(lengths[i], 1u);
        assert(regions[i] != NULL);
    }
    regions[1][0] = 0x12u;
    regions[1][1] = 0x34u;
    /* Reset vectors, then MOVEQ #$5a,D1; MOVE.W D1,$100000; STOP. */
    regions[0][0] = 0x00u; regions[0][1] = 0x10u;
    regions[0][2] = 0xffu; regions[0][3] = 0xfeu;
    regions[0][4] = 0x00u; regions[0][5] = 0x00u;
    regions[0][6] = 0x01u; regions[0][7] = 0x00u;
    const uint8_t program[] = {
        0x72u, 0x5au, 0x33u, 0xc1u, 0x00u, 0x10u, 0x00u, 0x00u,
        0x4eu, 0x72u, 0x27u, 0x00u};
    memcpy(regions[0] + 0x100u, program, sizeof(program));

    /* ZIP input uses the documented word-swapped CPU-region representation. */
    for (size_t byte = 0u; byte < lengths[1]; byte += 2u) {
        const uint8_t first = regions[1][byte];
        regions[1][byte] = regions[1][byte + 1u];
        regions[1][byte + 1u] = first;
    }

    uint32_t offsets[REGION_COUNT];
    uint32_t crcs[REGION_COUNT];
    size_t cursor = 0u;
    for (size_t i = 0u; i < REGION_COUNT; ++i) {
        offsets[i] = (uint32_t)cursor;
        const size_t name_length = strlen(names[i]);
        assert(cursor + 30u + name_length + lengths[i] <= capacity);
        uint8_t *record = zip + cursor;
        put32le(record, UINT32_C(0x04034b50)); put16le(record + 4u, 20u);
        put16le(record + 6u, 0u); put16le(record + 8u, 0u);
        crcs[i] = (uint32_t)crc32(0L, regions[i], (uInt)lengths[i]);
        put32le(record + 14u, crcs[i]); put32le(record + 18u, (uint32_t)lengths[i]);
        put32le(record + 22u, (uint32_t)lengths[i]);
        put16le(record + 26u, (uint16_t)name_length); put16le(record + 28u, 0u);
        memcpy(record + 30u, names[i], name_length);
        memcpy(record + 30u + name_length, regions[i], lengths[i]);
        cursor += 30u + name_length + lengths[i];
    }
    const size_t central_offset = cursor;
    for (size_t i = 0u; i < REGION_COUNT; ++i) {
        const size_t name_length = strlen(names[i]);
        assert(cursor + 46u + name_length <= capacity);
        uint8_t *record = zip + cursor;
        put32le(record, UINT32_C(0x02014b50)); put16le(record + 4u, 20u);
        put16le(record + 6u, 20u); put16le(record + 8u, 0u);
        put16le(record + 10u, 0u); put32le(record + 16u, crcs[i]);
        put32le(record + 20u, (uint32_t)lengths[i]);
        put32le(record + 24u, (uint32_t)lengths[i]);
        put16le(record + 28u, (uint16_t)name_length); put16le(record + 30u, 0u);
        put16le(record + 32u, 0u); put16le(record + 34u, 0u);
        put32le(record + 38u, 0u); put32le(record + 42u, offsets[i]);
        memcpy(record + 46u, names[i], name_length);
        cursor += 46u + name_length;
    }
    const size_t central_size = cursor - central_offset;
    assert(cursor + 22u <= capacity);
    uint8_t *eocd = zip + cursor;
    put32le(eocd, UINT32_C(0x06054b50)); put16le(eocd + 4u, 0u);
    put16le(eocd + 6u, 0u); put16le(eocd + 8u, REGION_COUNT);
    put16le(eocd + 10u, REGION_COUNT); put32le(eocd + 12u, (uint32_t)central_size);
    put32le(eocd + 16u, (uint32_t)central_offset); put16le(eocd + 20u, 0u);
    *out_size = cursor + 22u;
}

static gn_mvs_manifest bundle_manifest(const uint8_t *bundle, size_t size,
                                       uint8_t *copies[REGION_COUNT]) {
    assert(size >= 16u && memcmp(bundle, "GNMV", 4u) == 0);
    assert(get32be(bundle + 4u) == 1u);
    assert(get32be(bundle + 8u) == GN_MVS_PROFILE_MSX);
    assert(get32be(bundle + 12u) == REGION_COUNT);
    gn_mvs_manifest manifest;
    memset(&manifest, 0, sizeof(manifest));
    manifest.version = GN_MVS_MANIFEST_VERSION;
    manifest.profile = GN_MVS_PROFILE_MSX;
    manifest.region_count = REGION_COUNT;
    size_t cursor = 16u;
    for (size_t i = 0u; i < REGION_COUNT; ++i) {
        const uint32_t role = get32be(bundle + cursor);
        const uint64_t length = get64be(bundle + cursor + 4u);
        cursor += 12u;
        assert(length <= size - cursor);
        if (copies != NULL) {
            copies[i] = (uint8_t *)malloc((size_t)length);
            assert(copies[i] != NULL);
            memcpy(copies[i], bundle + cursor, (size_t)length);
        }
        manifest.regions[i] = (gn_mvs_region){
            (gn_mvs_region_role)role, bundle + cursor, (size_t)length,
            (size_t)length, GN_MVS_LAYOUT_LINEAR};
        cursor += (size_t)length;
    }
    assert(cursor == size);
    return manifest;
}

static void check_media_contract(const uint8_t *bundle, size_t size) {
    gn_mvs_manifest manifest;
    uint8_t *recovery_regions[REGION_COUNT] = {0};
    manifest = bundle_manifest(bundle, size, recovery_regions);
    gn_instance *instance = NULL;
    gn_test_allocator allocator;
    gn_test_allocator_init(&allocator);
    assert(gn_test_create(&allocator, &instance) == GN_STATUS_OK);
    gn_test_allocator_arm(&allocator, 2u);
    assert(gn_load_mvs(instance, &manifest) == GN_STATUS_OUT_OF_MEMORY);
    gn_test_allocator_disarm(&allocator);
    assert(gn_load_mvs(instance, &manifest) == GN_STATUS_OK);
    uint16_t program_word = 0u;
    assert(gn_test_mvs_read_bus(instance, UINT32_C(0x200000), &program_word) ==
           GN_STATUS_OK);
    assert(program_word == UINT16_C(0x1234));
    memset((void *)manifest.regions[0].source, 0, manifest.regions[0].source_size);
    assert(gn_test_mvs_read_bus(instance, UINT32_C(0x200000), &program_word) ==
           GN_STATUS_OK && program_word == UINT16_C(0x1234));
    gn_mvs_manifest invalid = manifest;
    invalid.region_count = REGION_COUNT - 1u;
    assert(gn_load_mvs(instance, &invalid) == GN_STATUS_INVALID_MEDIA);
    assert(gn_test_mvs_read_bus(instance, UINT32_C(0x200000), &program_word) ==
           GN_STATUS_OK && program_word == UINT16_C(0x1234));
    for (size_t i = 0u; i < REGION_COUNT; ++i)
        manifest.regions[i].source = recovery_regions[i];
    assert(gn_load_mvs(instance, &manifest) == GN_STATUS_OK);
    gn_destroy(instance);
    assert(allocator.live_allocations == 0u);
    for (size_t i = 0u; i < REGION_COUNT; ++i) free(recovery_regions[i]);
}

static void check_boot_checkpoint(const uint8_t *bundle, size_t size) {
    gn_mvs_manifest manifest;
    manifest = bundle_manifest(bundle, size, NULL);
    gn_instance *instance = NULL;
    assert(gn_create(&instance) == GN_STATUS_OK);
    assert(gn_load_mvs(instance, &manifest) == GN_STATUS_OK);
    gn_run_result run;
    assert(gn_run_mvs(instance, 1000u, &run) == GN_STATUS_OK);
    assert(run.reason == GN_RUN_STOPPED);
    assert(run.instructions == 3u);
    uint16_t sentinel = 0u;
    assert(gn_test_mvs_read_work_ram(instance, UINT32_C(0x100000), &sentinel) ==
           GN_STATUS_OK);
    assert(sentinel == UINT16_C(0x005a));
    gn_destroy(instance);
}

static void check_callbacks(const uint8_t *bundle, size_t bundle_size) {
    retro_set_environment(environment);
    struct retro_game_info game = {NULL, bundle, bundle_size, NULL};
    assert(retro_load_game(&game));
    retro_unload_game();
    assert(retro_load_game(&game));
    retro_unload_game();
    assert(pixel_requests == 2u);
}

int main(int argc, char **argv) {
    const size_t zip_capacity = (size_t)64u * 1024u * 1024u;
    uint8_t *zip = (uint8_t *)malloc(zip_capacity);
    assert(zip != NULL);
    uint8_t *regions[REGION_COUNT] = {0};
    size_t lengths[REGION_COUNT] = {0};
    size_t zip_size = 0u;
    build_zip(zip, zip_capacity, &zip_size, regions, lengths);
    uint8_t *bundle = NULL;
    size_t bundle_size = 0u;
    assert(mvs_import_memory(zip, zip_size, &bundle, &bundle_size) == 0);
    free(zip);
    for (size_t i = 0u; i < REGION_COUNT; ++i) free(regions[i]);

    if (argc == 1) {
        check_callbacks(bundle, bundle_size);
        check_boot_checkpoint(bundle, bundle_size);
        check_media_contract(bundle, bundle_size);
    } else if (strcmp(argv[1], "--media-contract") == 0) {
        check_media_contract(bundle, bundle_size);
    } else if (strcmp(argv[1], "--boot-checkpoint") == 0) {
        check_boot_checkpoint(bundle, bundle_size);
    } else if (strcmp(argv[1], "--callback-contract") == 0) {
        check_callbacks(bundle, bundle_size);
    }
    assert(argc == 1 || argc == 2);
    assert(argc == 1 || strcmp(argv[1], "--media-contract") == 0 ||
           strcmp(argv[1], "--boot-checkpoint") == 0 ||
           strcmp(argv[1], "--callback-contract") == 0);
    free(bundle);
    puts("MVS selected contract passed");
    return 0;
}
