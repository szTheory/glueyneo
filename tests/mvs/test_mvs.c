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

enum { REGION_COUNT = 6, ZIP_CAPACITY = 4096 };
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

static void build_zip(uint8_t *zip, size_t capacity, size_t *out_size) {
    static const char *const names[REGION_COUNT] = {
        "bios.bin", "program.bin", "fixed.bin", "audio.bin",
        "samples.bin", "sprites.bin"};
    uint8_t regions[REGION_COUNT][512];
    size_t lengths[REGION_COUNT];
    memset(regions, 0, sizeof(regions));
    lengths[0] = sizeof(regions[0]);
    for (size_t i = 1u; i < REGION_COUNT; ++i) lengths[i] = 16u;
    /* Reset vectors, then MOVEQ #$5a,D1; MOVE.W D1,$100000; STOP. */
    regions[0][0] = 0x00u; regions[0][1] = 0x10u;
    regions[0][2] = 0xffu; regions[0][3] = 0xfeu;
    regions[0][4] = 0x00u; regions[0][5] = 0x00u;
    regions[0][6] = 0x01u; regions[0][7] = 0x00u;
    const uint8_t program[] = {
        0x72u, 0x5au, 0x33u, 0xc1u, 0x00u, 0x10u, 0x00u, 0x00u,
        0x4eu, 0x72u, 0x27u, 0x00u};
    memcpy(regions[0] + 0x100u, program, sizeof(program));

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

static void check_bundle_api_and_guest(const uint8_t *bundle, size_t size) {
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
        manifest.regions[i] = (gn_mvs_region){
            (gn_mvs_region_role)role, bundle + cursor, (size_t)length,
            (size_t)length, GN_MVS_LAYOUT_LINEAR};
        cursor += (size_t)length;
    }
    assert(cursor == size);
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

int main(void) {
    uint8_t zip[ZIP_CAPACITY];
    memset(zip, 0, sizeof(zip));
    size_t zip_size = 0u;
    build_zip(zip, sizeof(zip), &zip_size);
    uint8_t *bundle = NULL;
    size_t bundle_size = 0u;
    assert(mvs_import_memory(zip, zip_size, &bundle, &bundle_size) == 0);
    check_bundle_api_and_guest(bundle, bundle_size);

    retro_set_environment(environment);
    struct retro_game_info game = {NULL, bundle, bundle_size, NULL};
    assert(retro_load_game(&game));
    assert(pixel_requests == 1u);
    retro_unload_game();
    free(bundle);
    puts("MVS synthetic importer, owned guest, and Libretro callback passed");
    return 0;
}
