/* SPDX-License-Identifier: MIT */
#include "glueyneo/glueyneo.h"
#include "libretro.h"
#include "sdk_private.h"

#include <assert.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <zlib.h>

int mvs_import_memory(const uint8_t *zip, size_t zip_size,
                      uint8_t **out_bundle, size_t *out_size);

enum { REGION_COUNT = 6 };
#define MAME_MVS_WATCHDOG_CPU_CYCLES UINT64_C(1622015)
static unsigned pixel_requests;

static void run_mvs_in_bounded_chunks(gn_instance *instance, uint64_t cycles,
                                      gn_run_result *result) {
    while (cycles != 0u) {
        const uint64_t chunk = cycles > GN_MAX_CYCLE_BUDGET
            ? GN_MAX_CYCLE_BUDGET : cycles;
        assert(gn_run_mvs(instance, chunk, result) == GN_STATUS_OK);
        cycles -= chunk;
    }
}

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
    regions[0][4] = 0x00u; regions[0][5] = 0xc0u;
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

static void check_high_bios_mirror(const uint8_t *bundle, size_t size);

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
    check_high_bios_mirror(bundle, size);
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

static void check_mvs_bus_fault_observation(uint8_t *bundle, size_t size) {
    gn_mvs_manifest manifest = bundle_manifest(bundle, size, NULL);
    uint8_t *bios = (uint8_t *)manifest.regions[0].source;
    memset(bios + 0x100u, 0, 16u);
    const uint8_t mapped_byte_write[] = {
        0x70u, 0x5au, 0x13u, 0xc0u, 0x00u, 0x10u, 0x00u, 0x01u};
    memcpy(bios + 0x100u, mapped_byte_write, sizeof(mapped_byte_write));
    gn_instance *mapped = NULL;
    assert(gn_create(&mapped) == GN_STATUS_OK);
    assert(gn_load_mvs(mapped, &manifest) == GN_STATUS_OK);
    gn_run_result run;
    assert(gn_run_mvs(mapped, 1u, &run) == GN_STATUS_OK);
    assert(run.reason == GN_RUN_BUDGET && run.elapsed_cycles == 64u);
    const gn_status mapped_status = gn_run_mvs(mapped, 16u, &run);
    if (mapped_status != GN_STATUS_OK) fprintf(stderr, "mapped synthetic status=%u reason=%u\n", (unsigned)mapped_status, (unsigned)run.reason);
    assert(mapped_status == GN_STATUS_OK);
    assert(run.reason == GN_RUN_BUDGET && run.elapsed_cycles == 16u);
    uint16_t written_word = 0u;
    assert(gn_test_mvs_read_bus(mapped, UINT32_C(0x100000), &written_word) ==
           GN_STATUS_OK && written_word == UINT16_C(0x005a));
    const uint8_t unmapped_low_byte_writes[] = {
        0x72u, 0x5au, 0x13u, 0xc0u, 0x00u, 0x00u, 0x00u, 0x20u,
        0x13u, 0xc0u, 0x00u, 0x00u, 0x01u, 0x00u};
    memcpy(bios + 0x100u, unmapped_low_byte_writes, sizeof(unmapped_low_byte_writes));
    assert(gn_load_mvs(mapped, &manifest) == GN_STATUS_OK);
    assert(gn_run_mvs(mapped, 1u, &run) == GN_STATUS_OK);
    assert(run.reason == GN_RUN_BUDGET && run.elapsed_cycles == 64u);
    assert(gn_run_mvs(mapped, 28u, &run) == GN_STATUS_OK);
    assert(run.reason == GN_RUN_BUDGET && run.elapsed_cycles == 28u);
    gn_mvs_bus_fault_observation observation;
    assert(gn_observe_mvs_bus_fault(mapped, &observation, sizeof(observation)) == GN_STATUS_OK);
    assert(observation.valid == 0u);
    assert(observation.mame_unmapped_write_count == 2u);
    typedef struct {
        uint32_t version;
        uint32_t address;
        gn_mvs_bus_access access;
        uint8_t width;
        uint8_t valid;
    } observation_prefix;
    struct {
        observation_prefix prefix;
        uint8_t canary[8];
    } short_observation;
    memset(&short_observation, 0xa5, sizeof(short_observation));
    assert(gn_observe_mvs_bus_fault(mapped,
        (gn_mvs_bus_fault_observation *)(void *)&short_observation.prefix,
        sizeof(short_observation.prefix)) == GN_STATUS_OK);
    assert(short_observation.prefix.version ==
           GN_MVS_BUS_FAULT_OBSERVATION_VERSION);
    for (size_t index = 0u; index < sizeof(short_observation.canary); ++index)
        assert(short_observation.canary[index] == 0xa5u);
    assert(gn_observe_mvs_bus_fault(mapped, &observation,
        offsetof(gn_mvs_bus_fault_observation, valid)) ==
        GN_STATUS_INVALID_ARGUMENT);
    assert(gn_reset(mapped) == GN_STATUS_OK);
    assert(gn_observe_mvs_bus_fault(mapped, &observation, sizeof(observation)) == GN_STATUS_OK);
    assert(observation.valid == 0u && observation.mame_unmapped_write_count == 0u);
    gn_destroy(mapped);

    memset(bios + 0x100u, 0, 16u);
    /* MOVE.W $00900000,D0 attempts a read outside the modeled MVS map. */
    const uint8_t program[] = {0x30u, 0x39u, 0x00u, 0x90u, 0x00u, 0x00u};
    memcpy(bios + 0x100u, program, sizeof(program));

    gn_instance *faulting = NULL, *isolated = NULL;
    assert(gn_create(&faulting) == GN_STATUS_OK);
    assert(gn_create(&isolated) == GN_STATUS_OK);
    assert(gn_load_mvs(faulting, &manifest) == GN_STATUS_OK);
    assert(gn_load_mvs(isolated, &manifest) == GN_STATUS_OK);
    assert(gn_run_mvs(faulting, 1000u, &run) == GN_STATUS_CPU_FAILURE);
    assert(run.reason == GN_RUN_ERROR);

    assert(gn_observe_mvs_bus_fault(faulting, &observation, sizeof(observation)) == GN_STATUS_OK);
    assert(observation.version == GN_MVS_BUS_FAULT_OBSERVATION_VERSION);
    assert(observation.valid == 1u);
    assert(observation.address == UINT32_C(0x900000));
    assert(observation.access == GN_MVS_BUS_ACCESS_READ);
    assert(observation.width == 2u);
    assert(gn_observe_mvs_bus_fault(isolated, &observation, sizeof(observation)) == GN_STATUS_OK);
    assert(observation.valid == 0u);
    assert(gn_reset(faulting) == GN_STATUS_OK);
    assert(gn_observe_mvs_bus_fault(faulting, &observation, sizeof(observation)) == GN_STATUS_OK);
    assert(observation.valid == 0u);

    const uint8_t write_program[] = {
        0x72u, 0x5au, 0x33u, 0xc1u, 0x00u, 0x90u, 0x00u, 0x00u};
    memcpy(bios + 0x100u, write_program, sizeof(write_program));
    assert(gn_load_mvs(faulting, &manifest) == GN_STATUS_OK);
    assert(gn_run_mvs(faulting, 1000u, &run) == GN_STATUS_CPU_FAILURE);
    assert(gn_observe_mvs_bus_fault(faulting, &observation, sizeof(observation)) == GN_STATUS_OK);
    assert(observation.valid == 1u);
    assert(observation.address == UINT32_C(0x900000));
    assert(observation.access == GN_MVS_BUS_ACCESS_WRITE);
    assert(observation.width == 2u);
    const uint8_t byte_write_program[] = {
        0x72u, 0x5au, 0x13u, 0xc1u, 0x00u, 0x90u, 0x00u, 0x00u};
    memcpy(bios + 0x100u, byte_write_program, sizeof(byte_write_program));
    assert(gn_load_mvs(faulting, &manifest) == GN_STATUS_OK);
    assert(gn_run_mvs(faulting, 1000u, &run) == GN_STATUS_CPU_FAILURE);
    assert(gn_observe_mvs_bus_fault(faulting, &observation, sizeof(observation)) == GN_STATUS_OK);
    assert(observation.valid == 1u);
    assert(observation.access == GN_MVS_BUS_ACCESS_WRITE);
    assert(observation.width == 1u);
    assert(observation.mame_unmapped_write_count == 0u);

    /* Pinned MAME neogeo_main_map maps 0x3e0000-0x3fffff only as
     * unmapped reads; byte writes fall through the default dropped-write path. */
    const uint8_t dropped_video_gap_byte_writes[] = {
        0x13u, 0xfcu, 0x00u, 0x5au, 0x00u, 0x3eu, 0x00u, 0x00u,
        0x13u, 0xfcu, 0x00u, 0xa5u, 0x00u, 0x3fu, 0xffu, 0xffu};
    memcpy(bios + 0x100u, dropped_video_gap_byte_writes,
           sizeof(dropped_video_gap_byte_writes));
    assert(gn_load_mvs(faulting, &manifest) == GN_STATUS_OK);
    assert(gn_run_mvs(faulting, 1u, &run) == GN_STATUS_OK);
    assert(run.reason == GN_RUN_BUDGET && run.elapsed_cycles == 64u);
    assert(gn_run_mvs(faulting, 40u, &run) == GN_STATUS_OK);
    assert(run.reason == GN_RUN_BUDGET && run.elapsed_cycles == 40u);
    assert(gn_observe_mvs_bus_fault(faulting, &observation, sizeof(observation)) == GN_STATUS_OK);
    assert(observation.valid == 0u);
    assert(observation.mame_unmapped_write_count == 2u);

    /* A mapped but unsupported neighboring video-register write still faults. */
    const uint8_t mapped_video_register_control[] = {
        0x13u, 0xfcu, 0x00u, 0x5au, 0x00u, 0x3cu, 0x00u, 0x08u};
    memcpy(bios + 0x100u, mapped_video_register_control,
           sizeof(mapped_video_register_control));
    assert(gn_load_mvs(faulting, &manifest) == GN_STATUS_OK);
    assert(gn_run_mvs(faulting, 1u, &run) == GN_STATUS_OK);
    assert(gn_run_mvs(faulting, 20u, &run) == GN_STATUS_CPU_FAILURE);
    assert(gn_observe_mvs_bus_fault(faulting, &observation, sizeof(observation)) == GN_STATUS_OK);
    assert(observation.valid == 1u);
    assert(observation.access == GN_MVS_BUS_ACCESS_WRITE);
    assert(observation.width == 1u);
    assert(observation.mame_unmapped_write_count == 0u);

    /* Other unsupported MVS reads remain faults. */
    const uint8_t unsupported_mvs_read[] = {
        0x30u, 0x39u, 0x00u, 0x90u, 0x00u, 0x00u};
    memcpy(bios + 0x100u, unsupported_mvs_read,
           sizeof(unsupported_mvs_read));
    assert(gn_load_mvs(faulting, &manifest) == GN_STATUS_OK);
    assert(gn_run_mvs(faulting, 1u, &run) == GN_STATUS_OK);
    assert(gn_run_mvs(faulting, 1000u, &run) == GN_STATUS_CPU_FAILURE);
    assert(gn_observe_mvs_bus_fault(faulting, &observation, sizeof(observation)) == GN_STATUS_OK);
    assert(observation.valid == 1u);
    assert(observation.access == GN_MVS_BUS_ACCESS_READ);
    assert(observation.width == 2u);
    gn_destroy(faulting);
    gn_destroy(isolated);

    /* The system-latch vector-select output is encoded in MAME's address
     * offset through hc259_device::write_a3, not in the write data byte. */
    gn_mvs_manifest vector_manifest = bundle_manifest(bundle, size, NULL);
    uint8_t *vector_bios = NULL;
    uint8_t *vector_program = NULL;
    for (size_t index = 0u; index < vector_manifest.region_count; ++index) {
        if (vector_manifest.regions[index].role == GN_MVS_REGION_BIOS)
            vector_bios = (uint8_t *)vector_manifest.regions[index].source;
        if (vector_manifest.regions[index].role == GN_MVS_REGION_PROGRAM)
            vector_program = (uint8_t *)vector_manifest.regions[index].source;
    }
    assert(vector_bios != NULL && vector_program != NULL);
    vector_bios[0] = 0x56u;
    vector_bios[1] = 0x78u;
    vector_program[0] = 0x12u;
    vector_program[1] = 0x34u;
    gn_instance *vectors = NULL;
    assert(gn_create(&vectors) == GN_STATUS_OK);
    assert(gn_load_mvs(vectors, &vector_manifest) == GN_STATUS_OK);
    uint16_t vector_word = 0u;
    assert(gn_test_mvs_read_bus(vectors, 0u, &vector_word) == GN_STATUS_OK);
    assert(vector_word == UINT16_C(0x5678));
    assert(gn_test_mvs_read_bus(vectors, UINT32_C(0xc00000), &vector_word) == GN_STATUS_OK);
    assert(vector_word == UINT16_C(0x5678));

    const uint8_t select_cart_vectors[] = {
        0x13u, 0xfcu, 0x00u, 0xffu, 0x00u, 0x3au, 0x00u, 0x13u};
    memcpy(vector_bios + 0x100u, select_cart_vectors, sizeof(select_cart_vectors));
    assert(gn_load_mvs(vectors, &vector_manifest) == GN_STATUS_OK);
    assert(gn_run_mvs(vectors, 1u, &run) == GN_STATUS_OK);
    assert(gn_run_mvs(vectors, 20u, &run) == GN_STATUS_OK);
    assert(gn_test_mvs_read_bus(vectors, 0u, &vector_word) == GN_STATUS_OK);
    assert(vector_word == UINT16_C(0x1234));
    assert(gn_test_mvs_read_bus(vectors, UINT32_C(0xc00000), &vector_word) == GN_STATUS_OK);
    assert(vector_word == UINT16_C(0x5678));

    const uint8_t clear_cart_vectors[] = {
        0x13u, 0xfcu, 0x00u, 0xffu, 0x00u, 0x3au, 0x00u, 0x03u};
    memcpy(vector_bios + 0x100u, clear_cart_vectors, sizeof(clear_cart_vectors));
    assert(gn_load_mvs(vectors, &vector_manifest) == GN_STATUS_OK);
    assert(gn_run_mvs(vectors, 1u, &run) == GN_STATUS_OK);
    assert(gn_run_mvs(vectors, 20u, &run) == GN_STATUS_OK);
    assert(gn_test_mvs_read_bus(vectors, 0u, &vector_word) == GN_STATUS_OK);
    assert(vector_word == UINT16_C(0x5678));

    const uint8_t wrong_latch_output[] = {
        0x13u, 0xfcu, 0x00u, 0xffu, 0x00u, 0x3au, 0x00u, 0x11u};
    memcpy(vector_bios + 0x100u, wrong_latch_output, sizeof(wrong_latch_output));
    assert(gn_load_mvs(vectors, &vector_manifest) == GN_STATUS_OK);
    assert(gn_run_mvs(vectors, 1u, &run) == GN_STATUS_OK);
    assert(gn_run_mvs(vectors, 20u, &run) == GN_STATUS_CPU_FAILURE);
    const uint8_t select_cart_audio[] = {
        0x13u, 0xfcu, 0x00u, 0xffu, 0x00u, 0x3au, 0x00u, 0x1bu};
    memcpy(vector_bios + 0x100u, select_cart_audio, sizeof(select_cart_audio));
    assert(gn_load_mvs(vectors, &vector_manifest) == GN_STATUS_OK);
    assert(gn_run_mvs(vectors, 1u, &run) == GN_STATUS_OK);
    assert(gn_run_mvs(vectors, 20u, &run) == GN_STATUS_OK);
    assert(gn_observe_mvs_bus_fault(vectors, &observation, sizeof(observation)) == GN_STATUS_OK);
    assert(observation.mvs_cart_audio_selected == 1u);

    const uint8_t clear_cart_audio[] = {
        0x13u, 0xfcu, 0x00u, 0xffu, 0x00u, 0x3au, 0x00u, 0x0bu};
    memcpy(vector_bios + 0x100u, clear_cart_audio, sizeof(clear_cart_audio));
    assert(gn_load_mvs(vectors, &vector_manifest) == GN_STATUS_OK);
    assert(gn_run_mvs(vectors, 1u, &run) == GN_STATUS_OK);
    assert(gn_run_mvs(vectors, 20u, &run) == GN_STATUS_OK);
    assert(gn_observe_mvs_bus_fault(vectors, &observation, sizeof(observation)) == GN_STATUS_OK);
    assert(observation.mvs_cart_audio_selected == 0u);

    const uint8_t set_coin1_lockout[] = {
        0x13u, 0xfcu, 0x00u, 0xffu, 0x00u, 0x38u, 0x00u, 0xe5u};
    memcpy(vector_bios + 0x100u, set_coin1_lockout, sizeof(set_coin1_lockout));
    assert(gn_load_mvs(vectors, &vector_manifest) == GN_STATUS_OK);
    assert(gn_run_mvs(vectors, 1u, &run) == GN_STATUS_OK);
    assert(gn_run_mvs(vectors, 20u, &run) == GN_STATUS_OK);
    assert(gn_observe_mvs_bus_fault(vectors, &observation, sizeof(observation)) == GN_STATUS_OK);
    assert(observation.valid == 0u && observation.mvs_coin_lockout_mask == 1u);

    const uint8_t clear_coin1_lockout[] = {
        0x13u, 0xfcu, 0x00u, 0xffu, 0x00u, 0x38u, 0x00u, 0x65u};
    memcpy(vector_bios + 0x100u, clear_coin1_lockout, sizeof(clear_coin1_lockout));
    assert(gn_load_mvs(vectors, &vector_manifest) == GN_STATUS_OK);
    assert(gn_run_mvs(vectors, 1u, &run) == GN_STATUS_OK);
    assert(gn_run_mvs(vectors, 20u, &run) == GN_STATUS_OK);
    assert(gn_observe_mvs_bus_fault(vectors, &observation, sizeof(observation)) == GN_STATUS_OK);
    assert(observation.valid == 0u && observation.mvs_coin_lockout_mask == 0u);

    const uint8_t set_coin2_lockout[] = {
        0x13u, 0xfcu, 0x00u, 0xffu, 0x00u, 0x38u, 0x00u, 0xe7u};
    memcpy(vector_bios + 0x100u, set_coin2_lockout, sizeof(set_coin2_lockout));
    assert(gn_load_mvs(vectors, &vector_manifest) == GN_STATUS_OK);
    assert(gn_run_mvs(vectors, 1u, &run) == GN_STATUS_OK);
    assert(gn_run_mvs(vectors, 20u, &run) == GN_STATUS_OK);
    assert(gn_observe_mvs_bus_fault(vectors, &observation, sizeof(observation)) == GN_STATUS_OK);
    assert(observation.valid == 0u && observation.mvs_coin_lockout_mask == 2u);

    const uint8_t clear_coin2_lockout[] = {
        0x13u, 0xfcu, 0x00u, 0xffu, 0x00u, 0x38u, 0x00u, 0x67u};
    memcpy(vector_bios + 0x100u, clear_coin2_lockout, sizeof(clear_coin2_lockout));
    assert(gn_load_mvs(vectors, &vector_manifest) == GN_STATUS_OK);
    assert(gn_run_mvs(vectors, 1u, &run) == GN_STATUS_OK);
    assert(gn_run_mvs(vectors, 20u, &run) == GN_STATUS_OK);
    assert(gn_observe_mvs_bus_fault(vectors, &observation, sizeof(observation)) == GN_STATUS_OK);
    assert(observation.valid == 0u && observation.mvs_coin_lockout_mask == 0u);

    const uint8_t unsupported_coin_counter[] = {
        0x13u, 0xfcu, 0x00u, 0xffu, 0x00u, 0x38u, 0x00u, 0x63u};
    memcpy(vector_bios + 0x100u, unsupported_coin_counter,
           sizeof(unsupported_coin_counter));
    assert(gn_load_mvs(vectors, &vector_manifest) == GN_STATUS_OK);
    assert(gn_run_mvs(vectors, 1u, &run) == GN_STATUS_OK);
    assert(gn_run_mvs(vectors, 20u, &run) == GN_STATUS_CPU_FAILURE);
    assert(gn_observe_mvs_bus_fault(vectors, &observation, sizeof(observation)) == GN_STATUS_OK);
    assert(observation.mvs_coin_lockout_mask == 0u);

    const uint8_t unlock_saveram[] = {
        0x13u, 0xfcu, 0x00u, 0xffu, 0x00u, 0x3au, 0x00u, 0x1du};
    memcpy(vector_bios + 0x100u, unlock_saveram, sizeof(unlock_saveram));
    assert(gn_load_mvs(vectors, &vector_manifest) == GN_STATUS_OK);
    assert(gn_run_mvs(vectors, 1u, &run) == GN_STATUS_OK);
    assert(gn_run_mvs(vectors, 20u, &run) == GN_STATUS_OK);
    assert(gn_observe_mvs_bus_fault(vectors, &observation, sizeof(observation)) == GN_STATUS_OK);
    assert(observation.valid == 0u && observation.mvs_save_ram_unlocked == 1u);

    const uint8_t wrong_saveram_latch_output[] = {
        0x13u, 0xfcu, 0x00u, 0xffu, 0x00u, 0x3au, 0x00u, 0x07u};
    memcpy(vector_bios + 0x100u, wrong_saveram_latch_output,
           sizeof(wrong_saveram_latch_output));
    assert(gn_load_mvs(vectors, &vector_manifest) == GN_STATUS_OK);
    assert(gn_run_mvs(vectors, 1u, &run) == GN_STATUS_OK);
    assert(gn_run_mvs(vectors, 20u, &run) == GN_STATUS_CPU_FAILURE);
    assert(gn_observe_mvs_bus_fault(vectors, &observation, sizeof(observation)) == GN_STATUS_OK);
    assert(observation.mvs_save_ram_unlocked == 0u);

    const uint8_t saveram_guest_round_trip[] = {
        0x13u, 0xfcu, 0x00u, 0xffu, 0x00u, 0x3au, 0x00u, 0x1du,
        0x33u, 0xfcu, 0x12u, 0x34u, 0x00u, 0xd0u, 0x00u, 0x20u,
        0x13u, 0xfcu, 0x00u, 0xffu, 0x00u, 0x3au, 0x00u, 0x0du,
        0x33u, 0xfcu, 0x56u, 0x78u, 0x00u, 0xd0u, 0x00u, 0x20u,
        0x32u, 0x39u, 0x00u, 0xd0u, 0x00u, 0x20u,
        0x33u, 0xc1u, 0x00u, 0x10u, 0x00u, 0x00u,
        0x4eu, 0x72u, 0x27u, 0x00u};
    memcpy(vector_bios + 0x100u, saveram_guest_round_trip,
           sizeof(saveram_guest_round_trip));
    assert(gn_load_mvs(vectors, &vector_manifest) == GN_STATUS_OK);
    assert(gn_run_mvs(vectors, 1u, &run) == GN_STATUS_OK);
    assert(gn_run_mvs(vectors, 200u, &run) == GN_STATUS_OK);
    assert(run.reason == GN_RUN_STOPPED);
    uint16_t saveram_round_trip = 0u;
    assert(gn_test_mvs_read_work_ram(vectors, UINT32_C(0x100000),
                                     &saveram_round_trip) == GN_STATUS_OK);
    assert(saveram_round_trip == UINT16_C(0x1234));
    uint16_t saved_after_reset = 0u;
    assert(gn_test_mvs_read_bus(vectors, UINT32_C(0xd00020),
                                &saved_after_reset) == GN_STATUS_OK);
    assert(saved_after_reset == UINT16_C(0x1234));
    assert(gn_reset(vectors) == GN_STATUS_OK);
    assert(gn_test_mvs_read_bus(vectors, UINT32_C(0xd00020),
                                &saved_after_reset) == GN_STATUS_OK);
    assert(saved_after_reset == UINT16_C(0x1234));
    assert(gn_observe_mvs_bus_fault(vectors, &observation, sizeof(observation)) == GN_STATUS_OK);
    assert(observation.mvs_save_ram_unlocked == 0u);

    const uint8_t select_palette_bank[] = {
        0x13u, 0xfcu, 0x00u, 0xffu, 0x00u, 0x3au, 0x00u, 0x1fu};
    memcpy(vector_bios + 0x100u, select_palette_bank, sizeof(select_palette_bank));
    assert(gn_load_mvs(vectors, &vector_manifest) == GN_STATUS_OK);
    assert(gn_run_mvs(vectors, 1u, &run) == GN_STATUS_OK);
    assert(gn_run_mvs(vectors, 20u, &run) == GN_STATUS_OK);
    assert(gn_observe_mvs_bus_fault(vectors, &observation, sizeof(observation)) == GN_STATUS_OK);
    assert(observation.valid == 0u && observation.mvs_palette_bank_selected == 1u);

    const uint8_t wrong_palette_latch_output[] = {
        0x13u, 0xfcu, 0x00u, 0xffu, 0x00u, 0x3au, 0x00u, 0x07u};
    memcpy(vector_bios + 0x100u, wrong_palette_latch_output,
           sizeof(wrong_palette_latch_output));
    assert(gn_load_mvs(vectors, &vector_manifest) == GN_STATUS_OK);
    assert(gn_run_mvs(vectors, 1u, &run) == GN_STATUS_OK);
    assert(gn_run_mvs(vectors, 20u, &run) == GN_STATUS_CPU_FAILURE);
    assert(gn_observe_mvs_bus_fault(vectors, &observation, sizeof(observation)) == GN_STATUS_OK);
    assert(observation.mvs_palette_bank_selected == 0u);

    const uint8_t palette_banks_guest_round_trip[] = {
        0x13u, 0xfcu, 0x00u, 0xffu, 0x00u, 0x3au, 0x00u, 0x1fu,
        0x33u, 0xfcu, 0x12u, 0x34u, 0x00u, 0x40u, 0x00u, 0x00u,
        0x13u, 0xfcu, 0x00u, 0xffu, 0x00u, 0x3au, 0x00u, 0x0fu,
        0x33u, 0xfcu, 0x56u, 0x78u, 0x00u, 0x40u, 0x00u, 0x00u,
        0x13u, 0xfcu, 0x00u, 0xffu, 0x00u, 0x3au, 0x00u, 0x1fu,
        0x32u, 0x39u, 0x00u, 0x40u, 0x00u, 0x00u,
        0x33u, 0xc1u, 0x00u, 0x10u, 0x00u, 0x00u,
        0x13u, 0xfcu, 0x00u, 0xffu, 0x00u, 0x3au, 0x00u, 0x0fu,
        0x32u, 0x39u, 0x00u, 0x40u, 0x00u, 0x00u,
        0x33u, 0xc1u, 0x00u, 0x10u, 0x00u, 0x02u,
        0x4eu, 0x72u, 0x27u, 0x00u};
    memcpy(vector_bios + 0x100u, palette_banks_guest_round_trip,
           sizeof(palette_banks_guest_round_trip));
    assert(gn_load_mvs(vectors, &vector_manifest) == GN_STATUS_OK);
    assert(gn_run_mvs(vectors, 1u, &run) == GN_STATUS_OK);
    assert(gn_run_mvs(vectors, 240u, &run) == GN_STATUS_OK);
    assert(run.reason == GN_RUN_STOPPED);
    uint16_t palette_bank_1 = 0u;
    uint16_t palette_bank_0 = 0u;
    assert(gn_test_mvs_read_work_ram(vectors, UINT32_C(0x100000),
                                     &palette_bank_1) == GN_STATUS_OK);
    assert(gn_test_mvs_read_work_ram(vectors, UINT32_C(0x100002),
                                     &palette_bank_0) == GN_STATUS_OK);
    assert(palette_bank_1 == UINT16_C(0x1234));
    assert(palette_bank_0 == UINT16_C(0x5678));

    const uint8_t wrong_cart_audio_output[] = {
        0x13u, 0xfcu, 0x00u, 0xffu, 0x00u, 0x3au, 0x00u, 0x19u};
    memcpy(vector_bios + 0x100u, wrong_cart_audio_output,
           sizeof(wrong_cart_audio_output));
    assert(gn_load_mvs(vectors, &vector_manifest) == GN_STATUS_OK);
    assert(gn_run_mvs(vectors, 1u, &run) == GN_STATUS_OK);
    assert(gn_run_mvs(vectors, 20u, &run) == GN_STATUS_CPU_FAILURE);
    gn_destroy(vectors);

    gn_mvs_manifest watchdog_manifest = bundle_manifest(bundle, size, NULL);
    uint8_t *watchdog_bios = (uint8_t *)watchdog_manifest.regions[0].source;
    const uint8_t pet_program[] = {
        0x70u, 0x5au, 0x13u, 0xc0u, 0x00u, 0x30u, 0x00u, 0x01u,
        0x4eu, 0x72u, 0x27u, 0x00u};
    memcpy(watchdog_bios + 0x100u, pet_program, sizeof(pet_program));
    gn_instance *watchdog = NULL;
    assert(gn_create(&watchdog) == GN_STATUS_OK);
    assert(gn_load_mvs(watchdog, &watchdog_manifest) == GN_STATUS_OK);
    assert(gn_run_mvs(watchdog, 1u, &run) == GN_STATUS_OK && run.elapsed_cycles == 64u);
    assert(gn_run_mvs(watchdog, 20u, &run) == GN_STATUS_OK);
    assert(run.reason == GN_RUN_STOPPED && run.elapsed_cycles == 20u);
    assert(gn_observe_mvs_bus_fault(watchdog, &observation, sizeof(observation)) == GN_STATUS_OK);
    assert(observation.mame_watchdog_pet_count == 1u);
    assert(observation.mame_watchdog_reset_count == 0u);
    run_mvs_in_bounded_chunks(watchdog, MAME_MVS_WATCHDOG_CPU_CYCLES - 5u, &run);
    assert(gn_observe_mvs_bus_fault(watchdog, &observation, sizeof(observation)) == GN_STATUS_OK);
    assert(observation.mame_watchdog_reset_count == 0u);
    assert(gn_run_mvs(watchdog, 1u, &run) == GN_STATUS_OK);
    assert(gn_observe_mvs_bus_fault(watchdog, &observation, sizeof(observation)) == GN_STATUS_OK);
    assert(observation.mame_watchdog_reset_count == 1u);
    assert(gn_run_mvs(watchdog, 1u, &run) == GN_STATUS_OK);
    assert(run.elapsed_cycles == 64u && run.boundary_pc == UINT32_C(0x00c00100));
    gn_destroy(watchdog);

    const uint8_t video_offset_program[] = {
        0x33u, 0xfcu, 0x92u, 0x34u, 0x00u, 0x3cu, 0x00u, 0x00u};
    memcpy(watchdog_bios + 0x100u, video_offset_program,
           sizeof(video_offset_program));
    assert(gn_create(&watchdog) == GN_STATUS_OK);
    assert(gn_load_mvs(watchdog, &watchdog_manifest) == GN_STATUS_OK);
    assert(gn_run_mvs(watchdog, 1u, &run) == GN_STATUS_OK && run.elapsed_cycles == 64u);
    assert(gn_run_mvs(watchdog, 20u, &run) == GN_STATUS_OK);
    assert(run.reason == GN_RUN_BUDGET && run.elapsed_cycles == 20u);
    assert(gn_observe_mvs_bus_fault(watchdog, &observation, sizeof(observation)) == GN_STATUS_OK);
    assert(observation.valid == 0u && observation.video_ram_offset == UINT16_C(0x8234));
    gn_destroy(watchdog);

    const uint8_t video_modulo_program[] = {
        0x33u, 0xfcu, 0x00u, 0x04u, 0x00u, 0x3cu, 0x00u, 0x04u};
    memcpy(watchdog_bios + 0x100u, video_modulo_program,
           sizeof(video_modulo_program));
    assert(gn_create(&watchdog) == GN_STATUS_OK);
    assert(gn_load_mvs(watchdog, &watchdog_manifest) == GN_STATUS_OK);
    assert(gn_run_mvs(watchdog, 1u, &run) == GN_STATUS_OK && run.elapsed_cycles == 64u);
    assert(gn_run_mvs(watchdog, 20u, &run) == GN_STATUS_OK);
    assert(run.reason == GN_RUN_BUDGET && run.elapsed_cycles == 20u);
    uint16_t video_modulo = 0u;
    assert(gn_test_mvs_read_bus(watchdog, UINT32_C(0x3c0004), &video_modulo) ==
           GN_STATUS_OK);
    assert(video_modulo == UINT16_C(0x0004));
    assert(gn_observe_mvs_bus_fault(watchdog, &observation, sizeof(observation)) == GN_STATUS_OK);
    assert(observation.valid == 0u &&
           observation.video_ram_modulo == UINT16_C(0x0004));
    gn_destroy(watchdog);

    const uint8_t video_ram_data_program[] = {
        0x33u, 0xfcu, 0x00u, 0x01u, 0x00u, 0x3cu, 0x00u, 0x04u,
        0x33u, 0xfcu, 0x00u, 0x20u, 0x00u, 0x3cu, 0x00u, 0x00u,
        0x33u, 0xfcu, 0x12u, 0x34u, 0x00u, 0x3cu, 0x00u, 0x02u,
        0x33u, 0xfcu, 0x00u, 0x20u, 0x00u, 0x3cu, 0x00u, 0x00u};
    memcpy(watchdog_bios + 0x100u, video_ram_data_program,
           sizeof(video_ram_data_program));
    assert(gn_create(&watchdog) == GN_STATUS_OK);
    assert(gn_load_mvs(watchdog, &watchdog_manifest) == GN_STATUS_OK);
    assert(gn_run_mvs(watchdog, 1u, &run) == GN_STATUS_OK && run.elapsed_cycles == 64u);
    assert(gn_run_mvs(watchdog, 60u, &run) == GN_STATUS_OK);
    assert(run.reason == GN_RUN_BUDGET && run.elapsed_cycles == 60u);
    assert(gn_observe_mvs_bus_fault(watchdog, &observation, sizeof(observation)) ==
           GN_STATUS_OK);
    assert(observation.valid == 0u);
    assert(observation.video_ram_offset == UINT16_C(0x0021));
    uint16_t video_ram_data = 0u;
    assert(gn_test_mvs_read_bus(watchdog, UINT32_C(0x3c0002), &video_ram_data) ==
           GN_STATUS_OK);
    assert(video_ram_data == 0u);
    assert(gn_run_mvs(watchdog, 20u, &run) == GN_STATUS_OK);
    assert(run.reason == GN_RUN_BUDGET && run.elapsed_cycles == 20u);
    assert(gn_test_mvs_read_bus(watchdog, UINT32_C(0x3c0002), &video_ram_data) ==
           GN_STATUS_OK);
    assert(video_ram_data == UINT16_C(0x1234));
    assert(gn_observe_mvs_bus_fault(watchdog, &observation, sizeof(observation)) ==
           GN_STATUS_OK);
    assert(observation.valid == 0u);
    assert(observation.video_ram_offset == UINT16_C(0x0020));
    assert(observation.video_ram_modulo == UINT16_C(0x0001));
    assert(gn_reset(watchdog) == GN_STATUS_OK);
    assert(gn_observe_mvs_bus_fault(watchdog, &observation, sizeof(observation)) ==
           GN_STATUS_OK);
    assert(observation.video_ram_offset == UINT16_C(0x0020));
    assert(observation.video_ram_modulo == UINT16_C(0x0001));
    assert(gn_test_mvs_read_bus(watchdog, UINT32_C(0x3c0002), &video_ram_data) ==
           GN_STATUS_OK);
    assert(video_ram_data == UINT16_C(0x1234));
    gn_destroy(watchdog);

    const uint8_t video_ram_upper_boundary_program[] = {
        0x33u, 0xfcu, 0x78u, 0x00u, 0x00u, 0x3cu, 0x00u, 0x04u,
        0x33u, 0xfcu, 0x87u, 0xffu, 0x00u, 0x3cu, 0x00u, 0x00u,
        0x33u, 0xfcu, 0xbeu, 0xefu, 0x00u, 0x3cu, 0x00u, 0x02u,
        0x33u, 0xfcu, 0x87u, 0xffu, 0x00u, 0x3cu, 0x00u, 0x00u};
    memcpy(watchdog_bios + 0x100u, video_ram_upper_boundary_program,
           sizeof(video_ram_upper_boundary_program));
    assert(gn_create(&watchdog) == GN_STATUS_OK);
    assert(gn_load_mvs(watchdog, &watchdog_manifest) == GN_STATUS_OK);
    assert(gn_run_mvs(watchdog, 1u, &run) == GN_STATUS_OK && run.elapsed_cycles == 64u);
    assert(gn_run_mvs(watchdog, 80u, &run) == GN_STATUS_OK);
    assert(run.reason == GN_RUN_BUDGET && run.elapsed_cycles == 80u);
    assert(gn_test_mvs_read_bus(watchdog, UINT32_C(0x3c0002), &video_ram_data) ==
           GN_STATUS_OK);
    assert(video_ram_data == UINT16_C(0xbeef));
    assert(gn_observe_mvs_bus_fault(watchdog, &observation, sizeof(observation)) ==
           GN_STATUS_OK);
    assert(observation.valid == 0u);
    assert(observation.video_ram_offset == UINT16_C(0x87ff));
    assert(observation.video_ram_modulo == UINT16_C(0x7800));
    gn_destroy(watchdog);

    const uint8_t video_control_program[] = {
        0x33u, 0xfcu, 0xa0u, 0xb8u, 0x00u, 0x3cu, 0x00u, 0x06u};
    memcpy(watchdog_bios + 0x100u, video_control_program,
           sizeof(video_control_program));
    assert(gn_create(&watchdog) == GN_STATUS_OK);
    assert(gn_load_mvs(watchdog, &watchdog_manifest) == GN_STATUS_OK);
    assert(gn_run_mvs(watchdog, 1u, &run) == GN_STATUS_OK && run.elapsed_cycles == 64u);
    assert(gn_run_mvs(watchdog, 20u, &run) == GN_STATUS_OK);
    assert(run.reason == GN_RUN_BUDGET && run.elapsed_cycles == 20u);
    assert(gn_observe_mvs_bus_fault(watchdog, &observation, sizeof(observation)) == GN_STATUS_OK);
    assert(observation.valid == 0u);
    assert(observation.video_auto_animation_speed == UINT8_C(0xa0));
    assert(observation.video_auto_animation_disabled == 1u);
    assert(observation.display_position_interrupt_control == UINT8_C(0xb0));
    gn_destroy(watchdog);

    const uint8_t interrupt_ack_program[] = {
        0x33u, 0xfcu, 0x00u, 0x07u, 0x00u, 0x3cu, 0x00u, 0x0cu};
    memcpy(watchdog_bios + 0x100u, interrupt_ack_program,
           sizeof(interrupt_ack_program));
    assert(gn_create(&watchdog) == GN_STATUS_OK);
    assert(gn_load_mvs(watchdog, &watchdog_manifest) == GN_STATUS_OK);
    assert(gn_run_mvs(watchdog, 1u, &run) == GN_STATUS_OK && run.elapsed_cycles == 64u);
    assert(gn_run_mvs(watchdog, 20u, &run) == GN_STATUS_OK);
    assert(run.reason == GN_RUN_BUDGET && run.elapsed_cycles == 20u);
    assert(gn_observe_mvs_bus_fault(watchdog, &observation, sizeof(observation)) == GN_STATUS_OK);
    assert(observation.valid == 0u);
    gn_destroy(watchdog);

    const uint8_t wrong_video_index[] = {
        0x33u, 0xfcu, 0x12u, 0x34u, 0x00u, 0x3cu, 0x00u, 0x08u};
    memcpy(watchdog_bios + 0x100u, wrong_video_index,
           sizeof(wrong_video_index));
    assert(gn_create(&watchdog) == GN_STATUS_OK);
    assert(gn_load_mvs(watchdog, &watchdog_manifest) == GN_STATUS_OK);
    assert(gn_run_mvs(watchdog, 1u, &run) == GN_STATUS_OK && run.elapsed_cycles == 64u);
    assert(gn_run_mvs(watchdog, 20u, &run) == GN_STATUS_CPU_FAILURE);
    assert(gn_observe_mvs_bus_fault(watchdog, &observation, sizeof(observation)) == GN_STATUS_OK);
    assert(observation.valid == 1u && observation.access == GN_MVS_BUS_ACCESS_WRITE &&
           observation.width == 2u && observation.address == UINT32_C(0x3c0008));
    gn_destroy(watchdog);

    const uint8_t mvs_output_strobe_program[] = {
        0x13u, 0xfcu, 0x00u, 0x5au, 0x00u, 0x38u, 0x00u, 0x41u,
        0x13u, 0xfcu, 0x00u, 0xa5u, 0x00u, 0x38u, 0x00u, 0x31u};
    memcpy(watchdog_bios + 0x100u, mvs_output_strobe_program,
           sizeof(mvs_output_strobe_program));
    assert(gn_create(&watchdog) == GN_STATUS_OK);
    assert(gn_load_mvs(watchdog, &watchdog_manifest) == GN_STATUS_OK);
    assert(gn_run_mvs(watchdog, 1u, &run) == GN_STATUS_OK && run.elapsed_cycles == 64u);
    assert(gn_run_mvs(watchdog, 40u, &run) == GN_STATUS_OK);
    assert(run.reason == GN_RUN_BUDGET && run.elapsed_cycles == 40u);
    assert(gn_observe_mvs_bus_fault(watchdog, &observation, sizeof(observation)) == GN_STATUS_OK);
    assert(observation.valid == 0u && observation.mvs_output_data == UINT8_C(0x5a) &&
           observation.mvs_output_latch == UINT8_C(0xa5));
    gn_destroy(watchdog);

    /* Wrong-behavior control: neighboring unmapped I/O register still faults. */
    const uint8_t unsupported_io_control[] = {
        0x13u, 0xfcu, 0x00u, 0x5au, 0x00u, 0x38u, 0x00u, 0x71u};
    memcpy(watchdog_bios + 0x100u, unsupported_io_control,
           sizeof(unsupported_io_control));
    assert(gn_create(&watchdog) == GN_STATUS_OK);
    assert(gn_load_mvs(watchdog, &watchdog_manifest) == GN_STATUS_OK);
    assert(gn_run_mvs(watchdog, 1u, &run) == GN_STATUS_OK && run.elapsed_cycles == 64u);
    assert(gn_run_mvs(watchdog, 20u, &run) == GN_STATUS_CPU_FAILURE);
    assert(gn_observe_mvs_bus_fault(watchdog, &observation, sizeof(observation)) == GN_STATUS_OK);
    assert(observation.valid == 1u && observation.access == GN_MVS_BUS_ACCESS_WRITE &&
           observation.width == 1u);
    gn_destroy(watchdog);

    /* The video-control read includes live raster state, which this profile
     * does not model; do not fall through to the overlapping cart ROM range. */
    assert(gn_create(&watchdog) == GN_STATUS_OK);
    assert(gn_load_mvs(watchdog, &watchdog_manifest) == GN_STATUS_OK);
    uint16_t cart_read_control = 0u;
    assert(gn_test_mvs_read_bus(watchdog, UINT32_C(0x3c000c),
                                &cart_read_control) == GN_STATUS_INVALID_MEDIA);
    assert(gn_observe_mvs_bus_fault(watchdog, &observation, sizeof(observation)) == GN_STATUS_OK);
    assert(observation.valid == 1u && observation.access == GN_MVS_BUS_ACCESS_READ &&
           observation.width == 2u);
    gn_destroy(watchdog);

    const uint8_t no_pet_then_stop[] = {
        0x70u, 0x5au, 0x13u, 0xc0u, 0x00u, 0x10u, 0x00u, 0x01u,
        0x4eu, 0x72u, 0x27u, 0x00u};
    memcpy(watchdog_bios + 0x100u, no_pet_then_stop, sizeof(no_pet_then_stop));
    assert(gn_create(&watchdog) == GN_STATUS_OK);
    assert(gn_load_mvs(watchdog, &watchdog_manifest) == GN_STATUS_OK);
    assert(gn_run_mvs(watchdog, 1u, &run) == GN_STATUS_OK && run.elapsed_cycles == 64u);
    assert(gn_run_mvs(watchdog, 20u, &run) == GN_STATUS_OK);
    assert(run.reason == GN_RUN_STOPPED && run.elapsed_cycles == 20u);
    run_mvs_in_bounded_chunks(watchdog, MAME_MVS_WATCHDOG_CPU_CYCLES - 60u, &run);
    assert(gn_observe_mvs_bus_fault(watchdog, &observation, sizeof(observation)) == GN_STATUS_OK);
    assert(observation.mame_watchdog_reset_count == 1u);
    assert(gn_test_mvs_read_bus(watchdog, UINT32_C(0x100000), &written_word) ==
           GN_STATUS_OK && written_word == UINT16_C(0x005a));
    gn_destroy(watchdog);
}

static void check_high_bios_mirror(const uint8_t *bundle, size_t size) {
    gn_mvs_manifest manifest = bundle_manifest(bundle, size, NULL);
    uint8_t *bios = (uint8_t *)manifest.regions[0].source;
    bios[0x402u] = 0x12u;
    bios[0x403u] = 0x34u;
    bios[0x1fffeu] = 0x56u;
    bios[0x1ffffu] = 0x78u;
    gn_instance *instance = NULL;
    assert(gn_create(&instance) == GN_STATUS_OK);
    assert(gn_load_mvs(instance, &manifest) == GN_STATUS_OK);
    uint16_t value = 0u;
    assert(gn_test_mvs_read_bus(instance, UINT32_C(0xc00402), &value) ==
           GN_STATUS_OK);
    assert(value == UINT16_C(0x1234));
    assert(gn_test_mvs_read_bus(instance, UINT32_C(0xc20402), &value) ==
           GN_STATUS_OK && value == UINT16_C(0x1234));
    uint16_t low_vector = 0u;
    assert(gn_test_mvs_read_bus(instance, 0u, &low_vector) == GN_STATUS_OK);
    assert(gn_test_mvs_read_bus(instance, UINT32_C(0xc00000), &value) ==
           GN_STATUS_OK && value == low_vector);
    assert(gn_test_mvs_read_bus(instance, UINT32_C(0x000080), &value) ==
           GN_STATUS_INVALID_MEDIA);
    assert(gn_test_mvs_read_bus(instance, UINT32_C(0x00007e), &value) ==
           GN_STATUS_OK);
    assert(gn_test_mvs_read_bus(instance, UINT32_C(0x000100), &value) ==
           GN_STATUS_INVALID_MEDIA);
    const uint32_t mirror_ends[] = {
        UINT32_C(0xc1fffe), UINT32_C(0xc3fffe), UINT32_C(0xc5fffe),
        UINT32_C(0xc7fffe), UINT32_C(0xc9fffe), UINT32_C(0xcbfffe),
        UINT32_C(0xcdfffe), UINT32_C(0xcffffe)};
    for (size_t i = 0u; i < sizeof(mirror_ends) / sizeof(mirror_ends[0]); ++i) {
        assert(gn_test_mvs_read_bus(instance, mirror_ends[i], &value) == GN_STATUS_OK);
        assert(value == UINT16_C(0x5678));
    }
    /* MAME maps save RAM here; the unpersisted per-instance buffer starts zero. */
    assert(gn_test_mvs_read_bus(instance, UINT32_C(0xd00000), &value) ==
           GN_STATUS_OK);
    assert(value == 0u);
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
        check_mvs_bus_fault_observation(bundle, bundle_size);
        check_media_contract(bundle, bundle_size);
    } else if (strcmp(argv[1], "--media-contract") == 0) {
        check_media_contract(bundle, bundle_size);
    } else if (strcmp(argv[1], "--boot-checkpoint") == 0) {
        check_boot_checkpoint(bundle, bundle_size);
        check_mvs_bus_fault_observation(bundle, bundle_size);
    } else if (strcmp(argv[1], "--callback-contract") == 0) {
        check_callbacks(bundle, bundle_size);
    } else if (strcmp(argv[1], "--bus-fault-observation") == 0) {
        check_mvs_bus_fault_observation(bundle, bundle_size);
    } else if (strcmp(argv[1], "--high-bios-mirror") == 0) {
        check_high_bios_mirror(bundle, bundle_size);
    }
    assert(argc == 1 || argc == 2);
    assert(argc == 1 || strcmp(argv[1], "--media-contract") == 0 ||
           strcmp(argv[1], "--boot-checkpoint") == 0 ||
           strcmp(argv[1], "--callback-contract") == 0 ||
           strcmp(argv[1], "--bus-fault-observation") == 0 ||
           strcmp(argv[1], "--high-bios-mirror") == 0);
    free(bundle);
    puts("MVS selected contract passed");
    return 0;
}
