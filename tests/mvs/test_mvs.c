/* SPDX-License-Identifier: MIT */
#include "glueyneo/glueyneo.h"
#include "libretro.h"
#include "sdk_private.h"
#include "chips/z80_candidate.h"
#include "chips/ym2610_candidate.h"

#include <assert.h>
#include <stdarg.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <zlib.h>

int mvs_import_memory(const uint8_t *zip, size_t zip_size,
                      uint8_t **out_bundle, size_t *out_size);
int gn_test_mvs_pcm_convert(const int32_t *triplets, size_t source_frames,
                            const size_t *partitions, size_t partition_count,
                            int16_t *stereo_output,
                            size_t output_capacity_frames,
                            size_t *out_output_frames);

void public_guest_build(uint8_t out[602]);
enum { REGION_COUNT = 7 };
static bool av_update_allowed = true;
static bool av_test_active;
static bool av_test_in_run;
static unsigned av_update_calls;
static double av_updated_fps;
#define MAME_MVS_WATCHDOG_CPU_CYCLES UINT64_C(1622015)
static unsigned pixel_requests;
static uint8_t io_status_byte(const gn_instance *instance, uint32_t address);
/* Fake frontend log interface: captures every formatted line. */
#define LOG_LINES_MAX 8u
static bool log_interface_offered;
static char log_lines[LOG_LINES_MAX][512];
static size_t log_line_count;
static char audio_delivery_line[512];
static size_t audio_delivery_line_count;
static size_t audio_frame_line_count;
static unsigned long long audio_frame_sample_total;
static unsigned long long audio_frame_last_mask;
#define OBSERVATION_RECORDS_MAX 256u
static char observation_lines[OBSERVATION_RECORDS_MAX][128];
static size_t observation_line_count;
static size_t observation_video_callbacks;
static size_t observation_callback_at_log[OBSERVATION_RECORDS_MAX];
#define ADAPTER_INPUT_DESCRIPTORS_MAX 16u
static struct retro_input_descriptor
    adapter_input_descriptors[ADAPTER_INPUT_DESCRIPTORS_MAX];
static size_t adapter_input_descriptor_count;

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
static void RETRO_CALLCONV capture_log(enum retro_log_level level, const char *fmt, ...) {
    (void)level;
    va_list arguments;
    va_start(arguments, fmt);
    char formatted[512];
    const int written = vsnprintf(formatted, sizeof(formatted), fmt, arguments);
    assert(written >= 0 && (size_t)written < sizeof(formatted));
    const size_t length = strlen(formatted);
    if (length != 0u && formatted[length - 1u] == '\n') formatted[length - 1u] = '\0';
    if (strncmp(formatted, "glueyneo: mvs ", 13u) == 0) {
        assert(observation_line_count < OBSERVATION_RECORDS_MAX);
        observation_callback_at_log[observation_line_count] = observation_video_callbacks;
        strcpy(observation_lines[observation_line_count++], formatted);
    } else if (strncmp(formatted, "glueyneo: MVS audio frame:",
                       sizeof("glueyneo: MVS audio frame:") - 1u) == 0) {
        const char *cursor = formatted + sizeof("glueyneo: MVS audio frame:") - 1u;
        unsigned long long values[18];
        for (size_t index = 0u; index < 18u; ++index) {
            int used = 0;
            assert(sscanf(cursor, " %llu%n", &values[index], &used) == 1 && used > 0);
            cursor += used;
        }
        assert(*cursor == '\0');
        if (values[0] == 1u) {
            audio_frame_line_count = 0u;
            audio_frame_sample_total = 0u;
        }
        assert(values[0] == audio_frame_line_count + 1u);
        assert(values[1] <= 0x3ffu && values[2] > 0u &&
               values[3] > 0u && values[3] <= GN_MVS_AUDIO_CAPACITY_FRAMES_V1 && values[4] <= 1u);
        ++audio_frame_line_count;
        audio_frame_sample_total += values[3];
        audio_frame_last_mask = values[1];
    } else if (strncmp(formatted, "glueyneo: MVS audio final delivery:",
                       sizeof("glueyneo: MVS audio final delivery:") - 1u) == 0) {
        strcpy(audio_delivery_line, formatted);
        ++audio_delivery_line_count;
    } else {
        if (log_line_count < LOG_LINES_MAX)
            strcpy(log_lines[log_line_count], formatted);
        ++log_line_count;
    }
    va_end(arguments);
}
static bool environment(unsigned command, void *data) {
    if (command == RETRO_ENVIRONMENT_SET_SYSTEM_AV_INFO && data != NULL) {
        if (av_test_active) assert(av_test_in_run);
        ++av_update_calls;
        av_updated_fps = ((struct retro_system_av_info *)data)->timing.fps;
        return av_update_allowed;
    }
    if (command == RETRO_ENVIRONMENT_GET_LOG_INTERFACE && data != NULL &&
        log_interface_offered) {
        ((struct retro_log_callback *)data)->log = capture_log;
        return true;
    }
    if (command == RETRO_ENVIRONMENT_SET_PIXEL_FORMAT && data != NULL &&
        *(enum retro_pixel_format *)data == RETRO_PIXEL_FORMAT_XRGB8888) {
        ++pixel_requests;
        return true;
    }
    if (command == RETRO_ENVIRONMENT_SET_INPUT_DESCRIPTORS && data != NULL) {
        const struct retro_input_descriptor *descriptors =
            (const struct retro_input_descriptor *)data;
        adapter_input_descriptor_count = 0u;
        while (adapter_input_descriptor_count <
               ADAPTER_INPUT_DESCRIPTORS_MAX) {
            adapter_input_descriptors[adapter_input_descriptor_count] =
                descriptors[adapter_input_descriptor_count];
            if (descriptors[adapter_input_descriptor_count].description == NULL)
                return true;
            ++adapter_input_descriptor_count;
        }
        return false;
    }
    return false;
}

static void build_zip(uint8_t *zip, size_t capacity, size_t *out_size,
                      uint8_t *regions[REGION_COUNT],
                      size_t lengths[REGION_COUNT]) {
    static const char *const names[REGION_COUNT] = {
        "bios.bin", "program.bin", "fixed.bin", "audio.bin",
        "samples.bin", "sprites.bin", "audio-bios.bin"};
    static const size_t expected[REGION_COUNT] = {
        GN_MVS_BIOS_BYTES, GN_MVS_PROGRAM_BYTES, GN_MVS_FIXED_BYTES,
        GN_MVS_AUDIO_PROGRAM_BYTES, GN_MVS_SAMPLES_BYTES,
        GN_MVS_SPRITES_BYTES, GN_MVS_AUDIO_BIOS_BYTES};
    for (size_t i = 0u; i < REGION_COUNT; ++i) {
        lengths[i] = expected[i];
        regions[i] = (uint8_t *)calloc(lengths[i], 1u);
        assert(regions[i] != NULL);
    }
    regions[1][0] = 0x12u;
    regions[1][1] = 0x34u;
    /* The default P2 bank zero starts at program offset 1 MiB (S16d). */
    regions[1][UINT32_C(0x100000)] = 0x12u;
    regions[1][UINT32_C(0x100001)] = 0x34u;
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
    assert(get32be(bundle + 4u) == GN_MVS_MANIFEST_VERSION);
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

static gn_mvs_manifest_v3 bundle_manifest_v3(const uint8_t *bundle, size_t size,
                                             uint8_t *zoom,
                                             int include_audio_bios) {
    const gn_mvs_manifest legacy = bundle_manifest(bundle, size, NULL);
    gn_mvs_manifest_v3 manifest;
    memset(&manifest, 0, sizeof(manifest));
    manifest.version = GN_MVS_MANIFEST_VERSION_ZOOM;
    manifest.profile = GN_MVS_PROFILE_MSX;
    for (size_t index = 0u; index < legacy.region_count; ++index) {
        if (include_audio_bios == 0 &&
            legacy.regions[index].role == GN_MVS_REGION_AUDIO_BIOS) continue;
        manifest.regions[manifest.region_count++] = legacy.regions[index];
    }
    manifest.regions[manifest.region_count++] = (gn_mvs_region){
        GN_MVS_REGION_Y_ZOOM, zoom, GN_MVS_Y_ZOOM_BYTES,
        GN_MVS_Y_ZOOM_BYTES, GN_MVS_LAYOUT_LINEAR};
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
    uint8_t *original_bios = (uint8_t *)manifest.regions[0].source;
    memset(original_bios, 0, manifest.regions[0].source_size);
    assert(gn_test_mvs_read_bus(instance, UINT32_C(0x200000), &program_word) ==
           GN_STATUS_OK && program_word == UINT16_C(0x1234));
    memcpy(original_bios, recovery_regions[0], manifest.regions[0].source_size);
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

static void check_zoom_manifest_contract(const uint8_t *bundle, size_t size) {
    uint8_t *zoom = (uint8_t *)malloc(GN_MVS_Y_ZOOM_BYTES);
    assert(zoom != NULL);
    for (size_t index = 0u; index < GN_MVS_Y_ZOOM_BYTES; ++index)
        zoom[index] = (uint8_t)index;
    gn_mvs_manifest_v3 with_audio = bundle_manifest_v3(bundle, size, zoom, 1);
    gn_mvs_manifest_v3 without_audio = bundle_manifest_v3(bundle, size, zoom, 0);
    assert(with_audio.region_count == GN_MVS_V3_MAX_REGIONS);
    assert(without_audio.region_count == GN_MVS_V3_MAX_REGIONS - 1u);

    gn_instance *first = NULL;
    gn_instance *second = NULL;
    assert(gn_create(&first) == GN_STATUS_OK);
    assert(gn_create(&second) == GN_STATUS_OK);
    assert(gn_load_mvs_v3(first, &with_audio) == GN_STATUS_OK);
    assert(gn_load_mvs_v3(second, &without_audio) == GN_STATUS_OK);
    memset(zoom, 0, GN_MVS_Y_ZOOM_BYTES);
    assert(gn_reset(first) == GN_STATUS_OK);
    assert(gn_reset(second) == GN_STATUS_OK);
    gn_run_result run;
    assert(gn_run_mvs(first, 1000u, &run) == GN_STATUS_OK);
    assert(run.reason == GN_RUN_STOPPED);

    gn_mvs_manifest_v3 invalid = with_audio;
    invalid.region_count = GN_MVS_MAX_REGIONS;
    assert(gn_load_mvs_v3(first, &invalid) == GN_STATUS_INVALID_MEDIA);
    invalid = with_audio;
    invalid.regions[invalid.region_count - 1u].role = GN_MVS_REGION_SPRITES;
    assert(gn_load_mvs_v3(first, &invalid) == GN_STATUS_INVALID_MEDIA);
    invalid = with_audio;
    invalid.regions[invalid.region_count - 1u].source_size--;
    assert(gn_load_mvs_v3(first, &invalid) == GN_STATUS_INVALID_MEDIA);
    invalid = with_audio;
    invalid.version = GN_MVS_MANIFEST_VERSION;
    assert(gn_load_mvs_v3(first, &invalid) == GN_STATUS_UNSUPPORTED_PROFILE);
    gn_mvs_manifest legacy = {0};
    legacy.version = GN_MVS_MANIFEST_VERSION_ZOOM;
    legacy.profile = GN_MVS_PROFILE_MSX;
    legacy.region_count = GN_MVS_V3_MAX_REGIONS;
    assert(gn_load_mvs(first, &legacy) == GN_STATUS_UNSUPPORTED_PROFILE);

    gn_destroy(first);
    gn_destroy(second);
    free(zoom);
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

/* Cartridge P1 fixed window (plan 05-07, D-07). Reads at 0x000080-0x0fffff
 * return the program-region bytes at the same offset while 0x000000-0x00007f
 * keeps the vector-latch selection. Sources S6 and S7 in docs/mvs-media.md. */
static void check_cartridge_p1_window(const uint8_t *bundle, size_t size) {
    uint8_t *copy = (uint8_t *)malloc(size);
    assert(copy != NULL);
    memcpy(copy, bundle, size);
    gn_mvs_manifest manifest = bundle_manifest(copy, size, NULL);
    uint8_t *bios = NULL;
    uint8_t *program = NULL;
    for (size_t index = 0u; index < manifest.region_count; ++index) {
        if (manifest.regions[index].role == GN_MVS_REGION_BIOS)
            bios = (uint8_t *)manifest.regions[index].source;
        if (manifest.regions[index].role == GN_MVS_REGION_PROGRAM)
            program = (uint8_t *)manifest.regions[index].source;
    }
    assert(bios != NULL && program != NULL);
    assert(manifest.regions[1].source_size >= UINT32_C(0x100000));
    bios[0x7eu] = 0x9au; bios[0x7fu] = 0xbcu;
    program[0x7eu] = 0xdeu; program[0x7fu] = 0xf0u;
    program[0x80u] = 0x11u; program[0x81u] = 0x22u;
    program[0x100u] = 0xabu; program[0x101u] = 0xcdu;
    program[0x122u] = 0x4eu; program[0x123u] = 0xf9u;
    program[0xffffeu] = 0x5au; program[0xfffffu] = 0xa5u;
    /* MOVEQ #$5a,D0; MOVE.B D0,$000100.L; STOP: a write into the window. */
    const uint8_t write_into_window[] = {
        0x70u, 0x5au, 0x13u, 0xc0u, 0x00u, 0x00u, 0x01u, 0x00u,
        0x4eu, 0x72u, 0x27u, 0x00u};
    memcpy(bios + 0x100u, write_into_window, sizeof(write_into_window));
    gn_instance *instance = NULL;
    assert(gn_create(&instance) == GN_STATUS_OK);
    assert(gn_load_mvs(instance, &manifest) == GN_STATUS_OK);
    uint16_t word = 0u;
    assert(gn_test_mvs_read_bus(instance, UINT32_C(0x000080), &word) == GN_STATUS_OK);
    assert(word == UINT16_C(0x1122));
    assert(gn_test_mvs_read_bus(instance, UINT32_C(0x000100), &word) == GN_STATUS_OK);
    assert(word == UINT16_C(0xabcd));
    assert(gn_test_mvs_read_bus(instance, UINT32_C(0x000122), &word) == GN_STATUS_OK);
    assert(word == UINT16_C(0x4ef9));
    assert(gn_test_mvs_read_bus(instance, UINT32_C(0x0ffffe), &word) == GN_STATUS_OK);
    assert(word == UINT16_C(0x5aa5));
    /* The vector window still follows the latch: BIOS vectors after reset. */
    assert(gn_test_mvs_read_bus(instance, UINT32_C(0x00007e), &word) == GN_STATUS_OK);
    assert(word == UINT16_C(0x9abc));
    /* The window ends at 0x0fffff; 0x100000 is work RAM, not program bytes. */
    assert(gn_test_mvs_read_bus(instance, UINT32_C(0x100000), &word) == GN_STATUS_OK);
    assert(word == 0u);
    gn_run_result run;
    assert(gn_run_mvs(instance, 1u, &run) == GN_STATUS_OK);
    assert(gn_run_mvs(instance, 40u, &run) == GN_STATUS_OK);
    gn_mvs_bus_fault_observation observation;
    assert(gn_observe_mvs_bus_fault(instance, &observation, sizeof(observation)) ==
           GN_STATUS_OK);
    assert(observation.mame_unmapped_write_count == 1u);
    assert(gn_test_mvs_read_bus(instance, UINT32_C(0x000100), &word) == GN_STATUS_OK);
    assert(word == UINT16_C(0xabcd));
    gn_destroy(instance);
    free(copy);
}

/* Attract/start predicate controls (plan 05-08, D-07). The guests below are
 * rights-clear synthetic code: BIOS-region instructions at 0xc00100 and
 * cartridge-window instructions at the documented USER entry 0x000122 (docs/
 * mvs-media.md "Attract/start predicate"). They use only opcodes in the owned
 * CPU inventory. The predicate sees addresses and values, never program bytes. */
typedef struct {
    uint8_t *copy;
    gn_mvs_manifest manifest;
    uint8_t *bios;
    uint8_t *program;
    uint8_t *audio;
    uint8_t *audio_bios;
    uint8_t *fixed;
    uint8_t *sprites;
    uint8_t *zoom;
} guest_media;

static void open_guest_media(const uint8_t *bundle, size_t size, guest_media *media) {
    media->copy = (uint8_t *)malloc(size);
    assert(media->copy != NULL);
    memcpy(media->copy, bundle, size);
    media->manifest = bundle_manifest(media->copy, size, NULL);
    media->bios = NULL;
    media->program = NULL;
    media->audio = NULL;
    media->audio_bios = NULL;
    media->fixed = NULL;
    media->sprites = NULL;
    media->zoom = NULL;
    for (size_t index = 0u; index < media->manifest.region_count; ++index) {
        if (media->manifest.regions[index].role == GN_MVS_REGION_BIOS)
            media->bios = (uint8_t *)media->manifest.regions[index].source;
        if (media->manifest.regions[index].role == GN_MVS_REGION_PROGRAM)
            media->program = (uint8_t *)media->manifest.regions[index].source;
        if (media->manifest.regions[index].role == GN_MVS_REGION_AUDIO_PROGRAM)
            media->audio = (uint8_t *)media->manifest.regions[index].source;
        if (media->manifest.regions[index].role == GN_MVS_REGION_AUDIO_BIOS)
            media->audio_bios = (uint8_t *)media->manifest.regions[index].source;
        if (media->manifest.regions[index].role == GN_MVS_REGION_FIXED)
            media->fixed = (uint8_t *)media->manifest.regions[index].source;
        if (media->manifest.regions[index].role == GN_MVS_REGION_SPRITES)
            media->sprites = (uint8_t *)media->manifest.regions[index].source;
    }
    assert(media->bios != NULL && media->program != NULL && media->audio != NULL &&
           media->fixed != NULL && media->sprites != NULL);
    assert(media->audio_bios != NULL);
    memset(media->bios, 0, 0x400u);
    memset(media->program, 0, 0x400u);
    /* Reset vectors: SSP 0x0010fffe, PC 0x00c00100 (BIOS region). */
    const uint8_t vectors[] = {0x00u, 0x10u, 0xffu, 0xfeu, 0x00u, 0xc0u, 0x01u, 0x00u};
    memcpy(media->bios, vectors, sizeof(vectors));
}

static uint8_t *emit16(uint8_t *at, uint16_t value) {
    at[0] = (uint8_t)(value >> 8); at[1] = (uint8_t)value;
    return at + 2;
}
static uint8_t *emit32(uint8_t *at, uint32_t value) {
    return emit16(emit16(at, (uint16_t)(value >> 16)), (uint16_t)value);
}
static uint8_t *emit_move_b_imm(uint8_t *at, uint8_t value, uint32_t address) {
    return emit32(emit16(emit16(at, 0x13fcu), value), address);
}
static uint8_t *emit_move_w_imm(uint8_t *at, uint16_t value, uint32_t address) {
    return emit32(emit16(emit16(at, 0x33fcu), value), address);
}
static uint8_t *emit_jsr(uint8_t *at, uint32_t address) {
    return emit32(emit16(at, 0x4eb9u), address);
}
static uint8_t *emit_rts(uint8_t *at) { return emit16(at, 0x4e75u); }
static uint8_t *emit_stop(uint8_t *at) { return emit16(emit16(at, 0x4e72u), 0x2700u); }

/* Run the synthetic guest to its STOP and return the verdict plus the trace. */
static gn_mvs_attract_verdict run_guest(guest_media *media,
                                        gn_mvs_protocol_event *events,
                                        size_t *event_count, uint32_t *dropped) {
    gn_instance *instance = NULL;
    assert(gn_create(&instance) == GN_STATUS_OK);
    assert(gn_load_mvs(instance, &media->manifest) == GN_STATUS_OK);
    gn_run_result run;
    assert(gn_run_mvs(instance, 100000u, &run) == GN_STATUS_OK);
    assert(run.reason == GN_RUN_STOPPED);
    gn_mvs_attract_verdict verdict;
    assert(gn_private_mvs_attract_verdict(instance, &verdict) == GN_STATUS_OK);
    assert(gn_private_mvs_protocol_trace(instance, events,
                                         GN_MVS_PROTOCOL_TRACE_CAPACITY,
                                         event_count, dropped) == GN_STATUS_OK);
    gn_destroy(instance);
    return verdict;
}

static void check_attract_predicate(const uint8_t *bundle, size_t size) {
    gn_mvs_protocol_event events[GN_MVS_PROTOCOL_TRACE_CAPACITY];
    size_t count = 0u;
    uint32_t dropped = 0u;
    guest_media media;
    uint8_t *code;

    /* Positive: a BIOS-region request write of Demo, then the USER entry, then a
     * cartridge-region BIOS_USER_MODE write corroborating the handoff. */
    open_guest_media(bundle, size, &media);
    code = emit_move_b_imm(media.bios + 0x100u, 2u, GN_MVS_BIOS_USER_REQUEST);
    code = emit_jsr(code, GN_MVS_USER_ENTRY);
    emit_stop(code);
    code = emit_move_b_imm(media.program + 0x122u, 1u, GN_MVS_BIOS_USER_MODE);
    emit_rts(code);
    gn_mvs_attract_verdict verdict = run_guest(&media, events, &count, &dropped);
    assert(verdict.accepted == 1u && verdict.rejection == GN_MVS_ATTRACT_NONE);
    assert(verdict.user_request == GN_MVS_REQUEST_DEMO);
    assert(verdict.user_mode_corroborated == 1u);
    assert(verdict.request_sequence < verdict.entry_sequence);
    assert(dropped == 0u && count == 2u);
    assert(events[0].kind == GN_MVS_PROTOCOL_BIOS_VAR_WRITE);
    assert(events[0].address == GN_MVS_BIOS_USER_REQUEST && events[0].value == 2u);
    assert(events[0].writer_pc_region == GN_MVS_PC_BIOS);
    assert(events[1].kind == GN_MVS_PROTOCOL_USER_ENTRY_FETCH);
    assert(events[1].address == GN_MVS_USER_ENTRY);
    assert(events[1].total_cycles > events[0].total_cycles);
    free(media.copy);

    /* Positive, word write: the high byte of a word store at the request address
     * is the request (Title) and the low byte is BIOS_USER_MODE; no corroboration. */
    open_guest_media(bundle, size, &media);
    code = emit_move_w_imm(media.bios + 0x100u, 0x0300u, GN_MVS_BIOS_USER_REQUEST);
    code = emit_jsr(code, GN_MVS_USER_ENTRY);
    emit_stop(code);
    emit_rts(media.program + 0x122u);
    verdict = run_guest(&media, events, &count, &dropped);
    assert(verdict.accepted == 1u && verdict.user_request == GN_MVS_REQUEST_TITLE);
    assert(verdict.user_mode_corroborated == 0u);
    assert(count == 3u && events[1].address == GN_MVS_BIOS_USER_MODE);
    free(media.copy);

    /* WRONG_VALUE: the request holds a non-Demo/Title value at the entry. */
    open_guest_media(bundle, size, &media);
    code = emit_move_b_imm(media.bios + 0x100u, 1u, GN_MVS_BIOS_USER_REQUEST);
    code = emit_jsr(code, GN_MVS_USER_ENTRY);
    emit_stop(code);
    emit_rts(media.program + 0x122u);
    verdict = run_guest(&media, events, &count, &dropped);
    assert(verdict.accepted == 0u && verdict.rejection == GN_MVS_ATTRACT_WRONG_VALUE);
    free(media.copy);

    /* WRONG_SOURCE: cartridge code (not the BIOS) wrote a valid request value. */
    open_guest_media(bundle, size, &media);
    code = emit_jsr(media.bios + 0x100u, UINT32_C(0x000200));
    code = emit_jsr(code, GN_MVS_USER_ENTRY);
    emit_stop(code);
    emit_rts(emit_move_b_imm(media.program + 0x200u, 2u, GN_MVS_BIOS_USER_REQUEST));
    emit_rts(media.program + 0x122u);
    verdict = run_guest(&media, events, &count, &dropped);
    assert(verdict.accepted == 0u && verdict.rejection == GN_MVS_ATTRACT_WRONG_SOURCE);
    assert(events[0].writer_pc_region == GN_MVS_PC_CART_FIXED);
    free(media.copy);

    /* WRONG_ORDER: the entry runs before the request is written. */
    open_guest_media(bundle, size, &media);
    code = emit_jsr(media.bios + 0x100u, GN_MVS_USER_ENTRY);
    code = emit_move_b_imm(code, 2u, GN_MVS_BIOS_USER_REQUEST);
    emit_stop(code);
    emit_rts(media.program + 0x122u);
    verdict = run_guest(&media, events, &count, &dropped);
    assert(verdict.accepted == 0u && verdict.rejection == GN_MVS_ATTRACT_WRONG_ORDER);
    free(media.copy);

    /* NO_REQUEST: the entry runs and no request was ever written. */
    open_guest_media(bundle, size, &media);
    code = emit_jsr(media.bios + 0x100u, GN_MVS_USER_ENTRY);
    emit_stop(code);
    emit_rts(media.program + 0x122u);
    verdict = run_guest(&media, events, &count, &dropped);
    assert(verdict.accepted == 0u && verdict.rejection == GN_MVS_ATTRACT_NO_REQUEST);
    free(media.copy);

    /* TRACE_OVERFLOW: 80 distinct alternating protocol writes precede an
     * otherwise valid Demo request and entry, exceeding the 64-event ring. */
    open_guest_media(bundle, size, &media);
    code = emit16(media.bios + 0x100u, 0x7427u);               /* MOVEQ #39,D2 */
    uint8_t *loop = code;
    code = emit_move_b_imm(code, 0u, GN_MVS_BIOS_USER_REQUEST);
    code = emit_move_b_imm(code, 1u, GN_MVS_BIOS_USER_REQUEST);
    code = emit16(emit16(code, 0x51cau), (uint16_t)(0u - (uint16_t)(code + 2 - loop)));
    code = emit_move_b_imm(code, 2u, GN_MVS_BIOS_USER_REQUEST);
    code = emit_jsr(code, GN_MVS_USER_ENTRY);
    emit_stop(code);
    emit_rts(media.program + 0x122u);
    verdict = run_guest(&media, events, &count, &dropped);
    assert(dropped > 0u && count == GN_MVS_PROTOCOL_TRACE_CAPACITY);
    assert(verdict.accepted == 0u && verdict.rejection == GN_MVS_ATTRACT_TRACE_OVERFLOW);
    free(media.copy);

    /* Host-side hooks never record, and reset clears a decided trace. */
    open_guest_media(bundle, size, &media);
    code = emit_move_b_imm(media.bios + 0x100u, 3u, GN_MVS_BIOS_USER_REQUEST);
    code = emit_jsr(code, GN_MVS_USER_ENTRY);
    emit_stop(code);
    emit_rts(media.program + 0x122u);
    gn_instance *instance = NULL;
    assert(gn_create(&instance) == GN_STATUS_OK);
    assert(gn_load_mvs(instance, &media.manifest) == GN_STATUS_OK);
    uint16_t word = 0u;
    assert(gn_test_mvs_read_bus(instance, GN_MVS_USER_ENTRY & ~UINT32_C(1), &word) ==
           GN_STATUS_OK);
    assert(gn_private_mvs_protocol_trace(instance, events, GN_MVS_PROTOCOL_TRACE_CAPACITY,
                                         &count, &dropped) == GN_STATUS_OK);
    assert(count == 0u && dropped == 0u);
    gn_run_result run;
    assert(gn_run_mvs(instance, 100000u, &run) == GN_STATUS_OK);
    assert(gn_private_mvs_attract_verdict(instance, &verdict) == GN_STATUS_OK);
    assert(verdict.accepted == 1u && verdict.user_request == GN_MVS_REQUEST_TITLE);
    assert(gn_reset(instance) == GN_STATUS_OK);
    assert(gn_private_mvs_attract_verdict(instance, &verdict) == GN_STATUS_OK);
    assert(verdict.accepted == 0u && verdict.rejection == GN_MVS_ATTRACT_NO_REQUEST);
    assert(gn_private_mvs_protocol_trace(instance, events, GN_MVS_PROTOCOL_TRACE_CAPACITY,
                                         &count, &dropped) == GN_STATUS_OK);
    assert(count == 0u);
    gn_destroy(instance);
    free(media.copy);
}

static uint8_t *emit_move_b_from(uint8_t *at, uint32_t address) {
    return emit32(emit16(at, 0x1039u), address); /* MOVE.B (xxx).L,D0 */
}

static uint8_t *emit_btst_imm0_d0(uint8_t *at) {
    return emit16(emit16(at, 0x0800u), 0u); /* BTST #0,D0 */
}

static uint8_t *emit_bne_s_to(uint8_t *at, const uint8_t *target) {
    const intptr_t displacement = target - (at + 2u);
    assert(displacement >= -128 && displacement <= 127);
    return emit16(at, (uint16_t)(0x6600u | (uint8_t)displacement));
}

static uint8_t *emit_status_wait(uint8_t *at, uint32_t address) {
    uint8_t *loop = at;
    at = emit_move_b_from(at, address);
    at = emit_btst_imm0_d0(at);
    return emit_bne_s_to(at, loop);
}

static void prepare_input_guest(guest_media *media, const uint8_t *bundle,
                                size_t size, int early_player_start) {
    open_guest_media(bundle, size, media);
    uint8_t *code = media->bios + 0x100u;
    code = emit_move_b_imm(code, GN_MVS_REQUEST_DEMO, GN_MVS_BIOS_USER_REQUEST);
    code = emit_jsr(code, GN_MVS_USER_ENTRY);
    if (early_player_start != 0) {
        code = emit_jsr(code, UINT32_C(0x000128));
        emit_stop(code);
    } else {
        code = emit_status_wait(code, UINT32_C(0x00320001));
        code = emit_status_wait(code, UINT32_C(0x00380000));
        code = emit_move_b_imm(code, 1u, GN_MVS_BIOS_START_FLAG);
        code = emit_jsr(code, UINT32_C(0x000128));
        emit_stop(code);
    }
    emit_rts(media->program + GN_MVS_USER_ENTRY);
    emit_rts(media->program + UINT32_C(0x000128));
}

static void observe_input_progress(const gn_instance *instance,
                                   gn_mvs_progress_observation *observation) {
    memset(observation, 0, sizeof(*observation));
    assert(gn_observe_mvs_progress(instance, observation, sizeof(*observation)) ==
           GN_STATUS_OK);
    assert(observation->version == GN_MVS_PROGRESS_OBSERVATION_VERSION);
    assert(observation->size == sizeof(*observation));
}

static void run_input_guest(gn_instance *instance, uint64_t cycles) {
    gn_run_result run;
    assert(gn_run_mvs(instance, cycles, &run) == GN_STATUS_OK);
    assert(run.reason == GN_RUN_BUDGET || run.reason == GN_RUN_STOPPED);
}

static void check_start_flag_controls(const uint8_t *bundle, size_t size) {
    /* Independent neighbors of the source-semantic oracle: P1 vs P2,
     * byte/word lanes, stale indication, clear and cartridge authorship. */
    for (unsigned variant = 0u; variant < 7u; ++variant) {
        guest_media media;
        open_guest_media(bundle, size, &media);
        uint8_t *code = emit_move_b_imm(media.bios + 0x100u,
            GN_MVS_REQUEST_DEMO, GN_MVS_BIOS_USER_REQUEST);
        code = emit_jsr(code, GN_MVS_USER_ENTRY);
        if (variant == 3u)
            code = emit_move_b_imm(code, 1u, GN_MVS_BIOS_START_FLAG);
        code = emit_status_wait(code, UINT32_C(0x320001));
        code = emit_status_wait(code, UINT32_C(0x380000));
        if (variant == 0u)
            code = emit_move_b_imm(code, 2u, GN_MVS_BIOS_START_FLAG);
        if (variant == 1u || variant == 2u)
            code = emit_move_w_imm(code, variant == 1u ? 0x0100u : 0x0001u,
                                   GN_MVS_BIOS_START_FLAG);
        if (variant >= 4u) {
            code = emit_move_b_imm(code, 1u, GN_MVS_BIOS_START_FLAG);
            if (variant == 4u)
                code = emit_move_b_imm(code, 0u, GN_MVS_BIOS_START_FLAG);
            if (variant == 5u) {
                code = emit_jsr(code, UINT32_C(0x200));
                uint8_t *cart = emit_move_b_imm(media.program + 0x200u,
                                               1u, GN_MVS_BIOS_START_FLAG);
                emit_rts(cart);
            }
        }
        code = emit_jsr(code, GN_MVS_PLAYER_START_ENTRY);
        emit_stop(code);
        emit_rts(media.program + GN_MVS_USER_ENTRY);
        emit_rts(media.program + GN_MVS_PLAYER_START_ENTRY);
        gn_instance *instance = NULL;
        assert(gn_create(&instance) == GN_STATUS_OK);
        assert(gn_load_mvs(instance, &media.manifest) == GN_STATUS_OK);
        run_input_guest(instance, 12000u);
        assert(gn_set_mvs_inputs(instance, GN_MVS_INPUT_COIN1) == GN_STATUS_OK);
        run_input_guest(instance, 12000u);
        assert(gn_set_mvs_inputs(instance,
            GN_MVS_INPUT_COIN1 | GN_MVS_INPUT_P1_START) == GN_STATUS_OK);
        run_input_guest(instance, 12000u);
        gn_mvs_progress_observation progress;
        observe_input_progress(instance, &progress);
        assert(progress.player_start_entered == 1u);
        assert(progress.player_start_with_p1_indication ==
               (uint8_t)(variant == 1u || variant == 6u));
        gn_destroy(instance);
        free(media.copy);
    }
    /* A fresh Start edge invalidates an indication from an earlier epoch,
     * even if the flag was never cleared in memory. */
    gn_mvs_protocol protocol;
    gn_mvs_protocol_reset(&protocol);
    protocol.guest_active = 1u;
    protocol.attract_start_reached = 1u;
    gn_mvs_protocol_note_input_change(&protocol, 0u, GN_MVS_INPUT_COIN1);
    gn_mvs_protocol_note_input_change(&protocol, GN_MVS_INPUT_COIN1,
        GN_MVS_INPUT_COIN1 | GN_MVS_INPUT_P1_START);
    gn_mvs_protocol_note_write(&protocol, GN_MVS_BIOS_START_FLAG, 1u, 1u,
                               GN_MVS_PC_BIOS);
    gn_mvs_protocol_note_input_change(&protocol,
        GN_MVS_INPUT_COIN1 | GN_MVS_INPUT_P1_START, GN_MVS_INPUT_COIN1);
    gn_mvs_protocol_note_input_change(&protocol, GN_MVS_INPUT_COIN1,
        GN_MVS_INPUT_COIN1 | GN_MVS_INPUT_P1_START);
    gn_mvs_protocol_note_player_start(&protocol);
    assert(protocol.player_start_with_p1_indication == 0u);
    gn_mvs_protocol_note_write(&protocol, GN_MVS_BIOS_START_FLAG, 1u, 1u,
                               GN_MVS_PC_BIOS);
    gn_mvs_protocol_note_player_start(&protocol);
    assert(protocol.player_start_with_p1_indication == 1u);
}

static void check_start_input(const uint8_t *bundle, size_t size) {
    /* Timer-only negative control: read both inputs but never branch on them.
     * DBRA, rather than input values, determines entry into PLAYER_START. */
    guest_media timeout;
    open_guest_media(bundle, size, &timeout);
    uint8_t *timer = emit_move_b_imm(timeout.bios + 0x100u,
        GN_MVS_REQUEST_DEMO, GN_MVS_BIOS_USER_REQUEST);
    timer = emit_jsr(timer, GN_MVS_USER_ENTRY);
    timer = emit16(timer, 0x747fu); /* MOVEQ #127,D2 */
    uint8_t *poll = timer;
    timer = emit_move_b_from(timer, UINT32_C(0x320001));
    timer = emit_move_b_from(timer, UINT32_C(0x380000));
    timer = emit16(emit16(timer, 0x51cau),
        (uint16_t)(poll - (timer + 2u))); /* DBRA D2,poll */
    timer = emit_jsr(timer, GN_MVS_PLAYER_START_ENTRY);
    emit_stop(timer);
    emit_rts(timeout.program + GN_MVS_USER_ENTRY);
    emit_rts(timeout.program + GN_MVS_PLAYER_START_ENTRY);
    gn_instance *timer_instance = NULL;
    assert(gn_create(&timer_instance) == GN_STATUS_OK);
    assert(gn_load_mvs(timer_instance, &timeout.manifest) == GN_STATUS_OK);
    run_input_guest(timer_instance, 1000u);
    assert(gn_set_mvs_inputs(timer_instance, GN_MVS_INPUT_COIN1) == GN_STATUS_OK);
    run_input_guest(timer_instance, 1000u);
    assert(gn_set_mvs_inputs(timer_instance,
        GN_MVS_INPUT_COIN1 | GN_MVS_INPUT_P1_START) == GN_STATUS_OK);
    /* A host test write cannot impersonate a BIOS protocol indication. */
    assert(gn_test_mvs_write_bus8(timer_instance, GN_MVS_BIOS_START_FLAG, 1u) ==
           GN_STATUS_OK);
    run_input_guest(timer_instance, 12000u);
    gn_mvs_progress_observation timer_progress;
    observe_input_progress(timer_instance, &timer_progress);
    assert(timer_progress.attract_start_reached == 1u);
    assert(timer_progress.player_start_entered == 1u);
    assert(timer_progress.player_start_with_p1_indication == 0u);
    gn_destroy(timer_instance);
    free(timeout.copy);
    check_start_flag_controls(bundle, size);

    guest_media media;
    prepare_input_guest(&media, bundle, size, 0);
    gn_instance *instance = NULL;
    gn_instance *isolated = NULL;
    assert(gn_create(&instance) == GN_STATUS_OK);
    assert(gn_create(&isolated) == GN_STATUS_OK);
    assert(gn_load_mvs(instance, &media.manifest) == GN_STATUS_OK);
    assert(gn_load_mvs(isolated, &media.manifest) == GN_STATUS_OK);

    gn_mvs_progress_observation progress;
    observe_input_progress(instance, &progress);
    assert(progress.attract_start_reached == 0u &&
           progress.player_start_entered == 0u &&
           progress.player_start_with_p1_indication == 0u);
    assert(gn_set_mvs_inputs(instance, 0u) == GN_STATUS_OK);
    assert(gn_set_mvs_inputs(isolated, 0u) == GN_STATUS_OK);
    run_input_guest(instance, 12000u);
    run_input_guest(isolated, 12000u);
    observe_input_progress(instance, &progress);
    assert(progress.attract_start_reached == 1u &&
           progress.user_request == GN_MVS_REQUEST_DEMO &&
           progress.player_start_entered == 0u);
    assert(io_status_byte(instance, UINT32_C(0x320001)) == UINT8_C(0x1f));
    assert(io_status_byte(instance, UINT32_C(0x380000)) == UINT8_C(0xff));

    /* Coin is visible on the active-low AUDIO_COIN bit and remains local to
     * the instance. The other guest is left polling its released input. */
    assert(gn_set_mvs_inputs(instance, GN_MVS_INPUT_COIN1) == GN_STATUS_OK);
    assert(io_status_byte(instance, UINT32_C(0x320001)) == UINT8_C(0x1e));
    assert(io_status_byte(isolated, UINT32_C(0x320001)) == UINT8_C(0x1f));
    run_input_guest(instance, 12000u);
    run_input_guest(isolated, 12000u);
    assert(gn_set_mvs_inputs(instance,
        GN_MVS_INPUT_COIN1 | GN_MVS_INPUT_P1_START) == GN_STATUS_OK);
    assert(io_status_byte(instance, UINT32_C(0x380000)) == UINT8_C(0xfe));
    assert(io_status_byte(isolated, UINT32_C(0x380000)) == UINT8_C(0xff));
    run_input_guest(instance, 12000u);
    run_input_guest(isolated, 12000u);
    observe_input_progress(instance, &progress);
    assert(progress.attract_start_reached == 1u &&
           progress.player_start_entered == 1u &&
           progress.player_start_with_p1_indication == 1u);
    gn_mvs_protocol_event events[GN_MVS_PROTOCOL_TRACE_CAPACITY];
    size_t event_count = 0u;
    uint32_t dropped = 0u;
    assert(gn_private_mvs_protocol_trace(instance, events,
        GN_MVS_PROTOCOL_TRACE_CAPACITY, &event_count, &dropped) == GN_STATUS_OK);
    assert(dropped == 0u && event_count >= 3u);
    assert(events[event_count - 1u].kind == GN_MVS_PROTOCOL_PLAYER_START_FETCH);
    assert(events[event_count - 1u].input_sequence == 2u);
    observe_input_progress(isolated, &progress);
    assert(progress.attract_start_reached == 1u &&
           progress.player_start_entered == 0u &&
           progress.player_start_with_p1_indication == 0u);

    /* An unsupported mask leaves the last valid coin state in place. */
    assert(gn_set_mvs_inputs(instance, GN_MVS_INPUT_COIN1) == GN_STATUS_OK);
    assert(gn_set_mvs_inputs(instance, UINT32_C(0x80000000)) ==
           GN_STATUS_INVALID_ARGUMENT);
    assert(io_status_byte(instance, UINT32_C(0x320001)) == UINT8_C(0x1e));
    assert(gn_reset(instance) == GN_STATUS_OK);
    assert(io_status_byte(instance, UINT32_C(0x320001)) == UINT8_C(0x1f));
    observe_input_progress(instance, &progress);
    assert(progress.attract_start_reached == 0u &&
           progress.player_start_entered == 0u &&
           progress.player_start_with_p1_indication == 0u);
    gn_destroy(instance);
    gn_destroy(isolated);
    free(media.copy);

    /* No input, and start without coin, both remain in the BIOS poll loops. */
    prepare_input_guest(&media, bundle, size, 0);
    assert(gn_create(&instance) == GN_STATUS_OK);
    assert(gn_load_mvs(instance, &media.manifest) == GN_STATUS_OK);
    run_input_guest(instance, 12000u);
    observe_input_progress(instance, &progress);
    assert(progress.attract_start_reached == 1u &&
           progress.player_start_entered == 0u);
    assert(gn_set_mvs_inputs(instance, GN_MVS_INPUT_P1_START) == GN_STATUS_OK);
    run_input_guest(instance, 12000u);
    observe_input_progress(instance, &progress);
    assert(progress.player_start_entered == 0u &&
           progress.player_start_with_p1_indication == 0u);
    gn_destroy(instance);
    free(media.copy);

    /* A guest can reach the documented cartridge entry before host input, but
     * that transfer alone is not attributed to a user input response. */
    prepare_input_guest(&media, bundle, size, 1);
    assert(gn_create(&instance) == GN_STATUS_OK);
    assert(gn_load_mvs(instance, &media.manifest) == GN_STATUS_OK);
    run_input_guest(instance, 12000u);
    observe_input_progress(instance, &progress);
    assert(progress.attract_start_reached == 1u &&
           progress.player_start_entered == 1u &&
           progress.player_start_with_p1_indication == 0u);
    gn_destroy(instance);
    free(media.copy);

    /* A loaded diagnostic image is not an MVS input target. */
    uint8_t fixture_rom[512] = {0};
    uint8_t fixture_ram[10] = {0};
    fixture_rom[0] = 0x00u; fixture_rom[1] = 0x00u;
    fixture_rom[2] = 0x20u; fixture_rom[3] = 0x00u;
    fixture_rom[7] = 0x08u;
    fixture_rom[8] = 0x4eu; fixture_rom[9] = 0x72u;
    fixture_rom[10] = 0x27u; fixture_rom[11] = 0x00u;
    const gn_manifest fixture = {
        GN_MANIFEST_VERSION, GN_PROFILE_DIAGNOSTIC, 2u,
        {{0u, 512u, fixture_rom, sizeof(fixture_rom), GN_REGION_ROM},
         {0x1000u, 0x1000u, fixture_ram, sizeof(fixture_ram), GN_REGION_RAM}}
    };
    assert(gn_create(&instance) == GN_STATUS_OK);
    assert(gn_load(instance, &fixture) == GN_STATUS_OK);
    assert(gn_set_mvs_inputs(instance, GN_MVS_INPUT_COIN1) ==
           GN_STATUS_UNSUPPORTED_PROFILE);
    assert(gn_set_mvs_inputs(instance, GN_MVS_INPUT_P1_A) ==
           GN_STATUS_UNSUPPORTED_PROFILE);
    gn_destroy(instance);
}

/* Stall diagnosis (plan 05-08, D-07, docs/mvs-media.md "Stall diagnosis"):
 * observation only. Each guest below is rights-clear synthetic code; the report
 * carries counts and public register addresses, never PCs or program bytes. */
static uint8_t *emit_move_w_from(uint8_t *at, uint32_t address) {
    return emit32(emit16(at, 0x3039u), address);          /* MOVE.W (xxx).L,D0 */
}
static uint8_t *emit_jmp(uint8_t *at, uint32_t address) {
    return emit32(emit16(at, 0x4ef9u), address);
}
static uint8_t *emit_move_to_sr(uint8_t *at, uint16_t value) {
    return emit16(emit16(at, 0x46fcu), value);
}

static uint64_t histogram_sum(const uint64_t *values, size_t count) {
    uint64_t total = 0u;
    for (size_t index = 0u; index < count; ++index) total += values[index];
    return total;
}

static gn_status run_for_diagnosis(guest_media *media, uint64_t cycles,
                                   gn_run_result *run, gn_mvs_stall_diagnosis *diagnosis) {
    gn_instance *instance = NULL;
    assert(gn_create(&instance) == GN_STATUS_OK);
    assert(gn_load_mvs(instance, &media->manifest) == GN_STATUS_OK);
    const gn_status status = gn_run_mvs(instance, cycles, run);
    assert(gn_private_mvs_stall_diagnosis(instance, diagnosis) == GN_STATUS_OK);
    gn_destroy(instance);
    return status;
}

static void check_stall_diagnosis(const uint8_t *bundle, size_t size) {
    guest_media media;
    gn_run_result run;
    gn_mvs_stall_diagnosis diagnosis;
    uint8_t *code;
    uint8_t *loop;

    /* A guest spinning on one I/O read with interrupts masked (reset SR 0x2700). */
    open_guest_media(bundle, size, &media);
    loop = media.bios + 0x100u;
    code = emit_move_w_from(loop, UINT32_C(0x3c0000));
    emit_jmp(code, UINT32_C(0xc00100));
    assert(run_for_diagnosis(&media, 5000u, &run, &diagnosis) == GN_STATUS_OK);
    assert(run.instructions > 20u);
    assert(diagnosis.polled_count == 1u);
    assert(diagnosis.polled[0].address == UINT32_C(0x3c0000));
    assert(diagnosis.polled[0].reads >= 10u);
    assert(diagnosis.interrupts_taken == 0u && diagnosis.irq_ack_writes == 0u);
    assert(diagnosis.sr_mask_histogram[7] == run.instructions);
    assert(histogram_sum(diagnosis.sr_mask_histogram, GN_MVS_SR_MASK_BUCKETS) ==
           run.instructions);
    assert(diagnosis.pc_region_histogram[GN_MVS_PC_BIOS] == run.instructions);
    assert(histogram_sum(diagnosis.pc_region_histogram, GN_MVS_PC_REGION_BUCKETS) ==
           run.instructions);
    assert(diagnosis.low_program_window_reads == 0u);
    assert(diagnosis.unmapped_read_count == 0u);
    free(media.copy);

    /* Lowering the mask moves later instructions to bucket 0; the MOVE to SR
     * itself still executes at mask 7. */
    open_guest_media(bundle, size, &media);
    code = emit_move_to_sr(media.bios + 0x100u, 0x2000u);
    loop = code;
    code = emit_move_w_from(code, UINT32_C(0x3c0002));
    emit_jmp(code, UINT32_C(0xc00100) + (uint32_t)(loop - (media.bios + 0x100u)));
    assert(run_for_diagnosis(&media, 5000u, &run, &diagnosis) == GN_STATUS_OK);
    assert(diagnosis.sr_mask_histogram[7] == 1u);
    assert(diagnosis.sr_mask_histogram[0] == run.instructions - 1u);
    free(media.copy);

    /* A read from the cartridge window below the work RAM increments the
     * program-window counter; BIOS fetches and vector reads do not. */
    open_guest_media(bundle, size, &media);
    code = emit_move_w_from(media.bios + 0x100u, UINT32_C(0x000100));
    emit_stop(code);
    assert(run_for_diagnosis(&media, 5000u, &run, &diagnosis) == GN_STATUS_OK);
    assert(diagnosis.low_program_window_reads == 1u);
    assert(diagnosis.polled_count == 0u);
    free(media.copy);

    /* Execution inside the cartridge fixed window lands in its PC bucket. */
    open_guest_media(bundle, size, &media);
    emit_jmp(media.bios + 0x100u, UINT32_C(0x000200));
    code = emit_move_w_from(media.program + 0x200u, UINT32_C(0x3c0004));
    emit_jmp(code, UINT32_C(0x000200));
    assert(run_for_diagnosis(&media, 5000u, &run, &diagnosis) == GN_STATUS_OK);
    assert(diagnosis.pc_region_histogram[GN_MVS_PC_BIOS] == 1u);
    assert(diagnosis.pc_region_histogram[GN_MVS_PC_CART_FIXED] == run.instructions - 1u);
    free(media.copy);

    /* Low-byte-only access to the video-control register remains unmapped.
     * The read map is word-wide, and the MAME callback leaves this lane open. */
    open_guest_media(bundle, size, &media);
    code = emit_move_b_from(media.bios + 0x100u, UINT32_C(0x3c0007));
    emit_stop(code);
    assert(run_for_diagnosis(&media, 5000u, &run, &diagnosis) != GN_STATUS_OK);
    assert(diagnosis.unmapped_read_count == 1u);
    assert(diagnosis.polled_count == 1u);
    assert(diagnosis.polled[0].address == UINT32_C(0x3c0007));
    assert(diagnosis.polled[0].reads == 1u);
    free(media.copy);

    /* A write of the interrupt acknowledge register ($3C000C) is counted, and
     * the last BIOS variable values and the pending rejection are reported. */
    open_guest_media(bundle, size, &media);
    code = emit_move_w_imm(media.bios + 0x100u, 7u, UINT32_C(0x3c000c));
    code = emit_move_b_imm(code, 2u, GN_MVS_BIOS_USER_REQUEST);
    emit_stop(code);
    assert(run_for_diagnosis(&media, 5000u, &run, &diagnosis) == GN_STATUS_OK);
    assert(diagnosis.irq_ack_writes == 1u);
    assert(diagnosis.bios_user_request == 2u && diagnosis.bios_system_mode == 0u &&
           diagnosis.bios_user_mode == 0u);
    assert(diagnosis.attract_rejection == GN_MVS_ATTRACT_NONE);
    free(media.copy);

    /* The polled table is bounded: at most 8 rows, only public windows, ranked
     * by read count, with reads that do not fit counted as untracked. */
    gn_mvs_protocol protocol;
    gn_mvs_protocol_reset(&protocol);
    protocol.guest_active = 1u;
    for (unsigned repeat = 0u; repeat < 100u; ++repeat)
        gn_mvs_protocol_note_read(&protocol, UINT32_C(0x380000));
    const uint32_t outside[] = {GN_MVS_BIOS_USER_REQUEST, UINT32_C(0x2fffde),
                                UINT32_C(0x400000), UINT32_C(0x000100),
                                UINT32_C(0xc00000)};
    for (size_t index = 0u; index < sizeof(outside) / sizeof(outside[0]); ++index)
        gn_mvs_protocol_note_read(&protocol, outside[index]);
    gn_mvs_protocol_note_read(&protocol, UINT32_C(0x2fffe0));
    gn_mvs_protocol_note_read(&protocol, UINT32_C(0x3fffff));
    gn_mvs_protocol_diagnose(&protocol, &diagnosis);
    assert(diagnosis.polled_count == 3u);
    assert(diagnosis.polled[0].address == UINT32_C(0x380000) &&
           diagnosis.polled[0].reads == 100u);
    assert(diagnosis.polled[1].address == UINT32_C(0x2fffe0) &&
           diagnosis.polled[2].address == UINT32_C(0x3fffff));
    assert(diagnosis.low_program_window_reads == 1u);
    gn_mvs_protocol_reset(&protocol);
    protocol.guest_active = 1u;
    for (unsigned repeat = 0u; repeat < 100u; ++repeat)
        gn_mvs_protocol_note_read(&protocol, UINT32_C(0x380000));
    for (uint32_t index = 0u; index < 40u; ++index)
        gn_mvs_protocol_note_read(&protocol, UINT32_C(0x300000) + 2u * index);
    gn_mvs_protocol_diagnose(&protocol, &diagnosis);
    assert(diagnosis.polled_count == GN_MVS_POLLED_REPORT_ROWS);
    assert(diagnosis.polled[0].address == UINT32_C(0x380000));
    for (size_t index = 0u; index < diagnosis.polled_count; ++index) {
        const uint32_t address = diagnosis.polled[index].address;
        assert((address >= UINT32_C(0x300000) && address <= UINT32_C(0x3fffff)) ||
               (address >= UINT32_C(0x2fffe0) && address <= UINT32_C(0x2fffff)));
        if (index > 0u) assert(diagnosis.polled[index - 1u].reads >= diagnosis.polled[index].reads);
    }
    /* 1 hot row + 31 single-read rows fill the 32-row table; 9 reads are lost. */
    assert(diagnosis.polled_untracked_reads == 9u);
}

static void check_mvs_bus_fault_observation(uint8_t *bundle, size_t size) {
    /* The guest runner maps a bounded owned-CPU fault to GN_RUN_FAULT while
     * retaining GN_STATUS_OK. The structured first-failure observer must still
     * identify that event and the completed instruction boundary before it. */
    guest_media unsupported;
    open_guest_media(bundle, size, &unsupported);
    const uint8_t unsupported_program[] = {
        0x4eu, 0x71u, /* NOP */
        0xffu, 0xffu  /* Unsupported instruction in this owned subset */
    };
    memcpy(unsupported.bios + 0x100u, unsupported_program,
           sizeof(unsupported_program));
    gn_instance *faulted = NULL;
    assert(gn_create(&faulted) == GN_STATUS_OK);
    assert(gn_load_mvs(faulted, &unsupported.manifest) == GN_STATUS_OK);
    gn_run_result fault_run;
    assert(gn_run_mvs(faulted, 1000u, &fault_run) == GN_STATUS_OK);
    assert(fault_run.reason == GN_RUN_FAULT && fault_run.instructions == 1u);
    gn_mvs_failure failure;
    assert(gn_private_mvs_failure(faulted, &failure) == GN_STATUS_OK);
    assert(failure.valid == 1u &&
           failure.component == GN_MVS_FAILURE_COMPONENT_MAIN_CPU &&
           failure.stage == GN_MVS_FAILURE_STAGE_EXECUTE &&
           failure.reason == GN_MVS_FAILURE_REASON_INTERNAL_FAILURE &&
           failure.site == GN_MVS_FAILURE_SITE_MAIN_EXECUTION &&
           failure.site_valid == 1u &&
           failure.device_cause == GN_MVS_FAILURE_CAUSE_OWNED_CPU &&
           failure.device_cause_valid == 1u);
    assert(failure.underlying_status ==
               GN_MVS_FAILURE_STATUS_OWNED_CPU_UNSUPPORTED_OPCODE &&
           failure.underlying_status_valid == 1u);
    assert(failure.completed_main_instructions == 1u &&
           failure.instruction_boundary_valid == 1u &&
           failure.guest_executed == 1u);
    assert(failure.pc_valid == 1u && failure.pc == UINT32_C(0xc00102) &&
           failure.opcode_valid == 1u && failure.opcode == UINT16_C(0xffff));
    assert(failure.bus_access_valid == 0u);
    gn_destroy(faulted);
    free(unsupported.copy);

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
    assert(run.reason == GN_RUN_BUDGET && run.elapsed_cycles == 40u);
    /* MOVEQ 4(1/0) + MOVE.B D0,(xxx).L 16(3/1): MC68000 UM Rev. 9.1 Tables 8-5
     * (p. 8-5) and 8-2 (p. 8-2) give 20 clocks (plan 05-19 correction). */
    const gn_status mapped_status = gn_run_mvs(mapped, 20u, &run);
    if (mapped_status != GN_STATUS_OK) fprintf(stderr, "mapped synthetic status=%u reason=%u\n", (unsigned)mapped_status, (unsigned)run.reason);
    assert(mapped_status == GN_STATUS_OK);
    assert(run.reason == GN_RUN_BUDGET && run.elapsed_cycles == 20u);
    uint16_t written_word = 0u;
    assert(gn_test_mvs_read_bus(mapped, UINT32_C(0x100000), &written_word) ==
           GN_STATUS_OK && written_word == UINT16_C(0x005a));
    const uint8_t unmapped_low_byte_writes[] = {
        0x72u, 0x5au, 0x13u, 0xc0u, 0x00u, 0x00u, 0x00u, 0x20u,
        0x13u, 0xc0u, 0x00u, 0x00u, 0x01u, 0x00u};
    memcpy(bios + 0x100u, unmapped_low_byte_writes, sizeof(unmapped_low_byte_writes));
    assert(gn_load_mvs(mapped, &manifest) == GN_STATUS_OK);
    assert(gn_run_mvs(mapped, 1u, &run) == GN_STATUS_OK);
    assert(run.reason == GN_RUN_BUDGET && run.elapsed_cycles == 40u);
    /* MOVEQ 4 + two MOVE.B D0,(xxx).L at 16 each = 36 (Tables 8-5, 8-2). */
    assert(gn_run_mvs(mapped, 36u, &run) == GN_STATUS_OK);
    assert(run.reason == GN_RUN_BUDGET && run.elapsed_cycles == 36u);
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
    assert(run.reason == GN_RUN_BUDGET && run.elapsed_cycles == 40u);
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
    vector_program[0x80u] = 0x77u;
    vector_program[0x81u] = 0x88u;
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
    /* The P1 window is independent of the vector-latch selection. */
    assert(gn_test_mvs_read_bus(vectors, UINT32_C(0x80), &vector_word) == GN_STATUS_OK);
    assert(vector_word == UINT16_C(0x7788));
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
        0x13u, 0xfcu, 0x00u, 0xffu, 0x00u, 0x3au, 0x00u, 0x09u};
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

    const uint8_t coin_counter_output[] = {
        0x13u, 0xfcu, 0x00u, 0xffu, 0x00u, 0x38u, 0x00u, 0xe1u};
    memcpy(vector_bios + 0x100u, coin_counter_output,
           sizeof(coin_counter_output));
    emit_stop(vector_bios + 0x108u);
    assert(gn_load_mvs(vectors, &vector_manifest) == GN_STATUS_OK);
    assert(gn_run_mvs(vectors, 1u, &run) == GN_STATUS_OK);
    assert(gn_run_mvs(vectors, 100u, &run) == GN_STATUS_OK);
    assert(run.reason == GN_RUN_STOPPED);
    assert(gn_observe_mvs_bus_fault(vectors, &observation, sizeof(observation)) == GN_STATUS_OK);
    assert(observation.valid == 0u && observation.mvs_coin_lockout_mask == 0u);

    const uint8_t unlock_saveram[] = {
        0x13u, 0xfcu, 0x00u, 0xffu, 0x00u, 0x3au, 0x00u, 0x1du};
    memcpy(vector_bios + 0x100u, unlock_saveram, sizeof(unlock_saveram));
    assert(gn_load_mvs(vectors, &vector_manifest) == GN_STATUS_OK);
    assert(gn_run_mvs(vectors, 1u, &run) == GN_STATUS_OK);
    assert(gn_run_mvs(vectors, 20u, &run) == GN_STATUS_OK);
    assert(gn_observe_mvs_bus_fault(vectors, &observation, sizeof(observation)) == GN_STATUS_OK);
    assert(observation.valid == 0u && observation.mvs_save_ram_unlocked == 1u);

    const uint8_t unsupported_output4_saveram_control[] = {
        0x13u, 0xfcu, 0x00u, 0xffu, 0x00u, 0x3au, 0x00u, 0x09u};
    memcpy(vector_bios + 0x100u, unsupported_output4_saveram_control,
           sizeof(unsupported_output4_saveram_control));
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
        0x13u, 0xfcu, 0x00u, 0xffu, 0x00u, 0x3au, 0x00u, 0x09u};
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
    assert(gn_run_mvs(watchdog, 1u, &run) == GN_STATUS_OK && run.elapsed_cycles == 40u);
    /* MOVEQ 4 + MOVE.B D0,(xxx).L 16 + STOP 4 = 24 (Tables 8-5, 8-2, 8-12). */
    assert(gn_run_mvs(watchdog, 24u, &run) == GN_STATUS_OK);
    assert(run.reason == GN_RUN_STOPPED && run.elapsed_cycles == 24u);
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
    assert(run.elapsed_cycles == 40u && run.boundary_pc == UINT32_C(0x00c00100));
    gn_destroy(watchdog);

    const uint8_t video_offset_program[] = {
        0x33u, 0xfcu, 0x92u, 0x34u, 0x00u, 0x3cu, 0x00u, 0x00u};
    memcpy(watchdog_bios + 0x100u, video_offset_program,
           sizeof(video_offset_program));
    assert(gn_create(&watchdog) == GN_STATUS_OK);
    assert(gn_load_mvs(watchdog, &watchdog_manifest) == GN_STATUS_OK);
    assert(gn_run_mvs(watchdog, 1u, &run) == GN_STATUS_OK && run.elapsed_cycles == 40u);
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
    assert(gn_run_mvs(watchdog, 1u, &run) == GN_STATUS_OK && run.elapsed_cycles == 40u);
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
    assert(gn_run_mvs(watchdog, 1u, &run) == GN_STATUS_OK && run.elapsed_cycles == 40u);
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
    assert(gn_run_mvs(watchdog, 1u, &run) == GN_STATUS_OK && run.elapsed_cycles == 40u);
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
    assert(gn_run_mvs(watchdog, 1u, &run) == GN_STATUS_OK && run.elapsed_cycles == 40u);
    assert(gn_run_mvs(watchdog, 20u, &run) == GN_STATUS_OK);
    assert(run.reason == GN_RUN_BUDGET && run.elapsed_cycles == 20u);
    assert(gn_observe_mvs_bus_fault(watchdog, &observation, sizeof(observation)) == GN_STATUS_OK);
    assert(observation.valid == 0u);
    assert(observation.video_auto_animation_speed == UINT8_C(0xa0));
    assert(observation.video_auto_animation_disabled == 1u);
    assert(observation.display_position_interrupt_control == UINT8_C(0xb0));
    gn_destroy(watchdog);

    /* The read-side video register map mirrors across 0x20000 bytes and the
     * video-control word exposes the live raster line plus animation counter.
     * STOP keeps the main CPU idle while the per-instance raster advances. */
    const uint8_t video_control_read_stop[] = {0x4eu, 0x72u, 0x27u, 0x00u};
    memcpy(watchdog_bios + 0x100u, video_control_read_stop,
           sizeof(video_control_read_stop));
    assert(gn_create(&watchdog) == GN_STATUS_OK);
    assert(gn_load_mvs(watchdog, &watchdog_manifest) == GN_STATUS_OK);
    assert(gn_run_mvs(watchdog, 1u, &run) == GN_STATUS_OK &&
           run.elapsed_cycles == 40u);
    assert(gn_run_mvs(watchdog, 4u, &run) == GN_STATUS_OK &&
           run.reason == GN_RUN_STOPPED && run.elapsed_cycles == 4u);
    uint16_t video_control = 0u;
    assert(gn_test_mvs_read_bus(watchdog, UINT32_C(0x3c0006),
                                &video_control) == GN_STATUS_OK);
    assert(video_control == UINT16_C(0x8000));
    assert(gn_test_mvs_read_bus(watchdog, UINT32_C(0x3c000e),
                                &video_control) == GN_STATUS_OK);
    assert(video_control == UINT16_C(0x8000));
    assert(gn_test_mvs_read_bus(watchdog, UINT32_C(0x3dfffe),
                                &video_control) == GN_STATUS_OK);
    assert(video_control == UINT16_C(0x8000));
    uint8_t video_control_high = 0u;
    assert(gn_test_mvs_read_bus8(watchdog, UINT32_C(0x3c0006),
                                 &video_control_high) == GN_STATUS_OK);
    assert(video_control_high == UINT8_C(0x80));
    assert(gn_test_mvs_read_bus(watchdog, UINT32_C(0x3c000c),
                                &video_control) == GN_STATUS_OK);
    assert(video_control == UINT16_C(0x0000));
    assert(gn_run_mvs(watchdog, UINT64_C(255) * UINT64_C(768) - 44u,
                      &run) == GN_STATUS_OK);
    assert(run.elapsed_cycles == UINT64_C(255) * UINT64_C(768) - 44u);
    assert(gn_test_mvs_read_bus(watchdog, UINT32_C(0x3c0006),
                                &video_control) == GN_STATUS_OK);
    assert(video_control == UINT16_C(0xff80));
    assert(gn_run_mvs(watchdog, UINT64_C(768), &run) == GN_STATUS_OK);
    assert(gn_test_mvs_read_bus(watchdog, UINT32_C(0x3c0006),
                                &video_control) == GN_STATUS_OK);
    assert(video_control == UINT16_C(0x7c01));
    assert(gn_observe_mvs_bus_fault(watchdog, &observation, sizeof(observation)) ==
           GN_STATUS_OK);
    assert(observation.valid == 0u);
    gn_destroy(watchdog);

    /* The mapped video read mirror ends at $3dffff; the following I/O window
     * is an explicit unsupported read rather than another alias. */
    assert(gn_create(&watchdog) == GN_STATUS_OK);
    assert(gn_load_mvs(watchdog, &watchdog_manifest) == GN_STATUS_OK);
    assert(gn_test_mvs_read_bus(watchdog, UINT32_C(0x3e0000),
                                &video_control) == GN_STATUS_INVALID_MEDIA);
    assert(gn_observe_mvs_bus_fault(watchdog, &observation, sizeof(observation)) ==
           GN_STATUS_OK);
    assert(observation.valid == 1u &&
           observation.access == GN_MVS_BUS_ACCESS_READ &&
           observation.width == 2u &&
           observation.address == UINT32_C(0x3e0000));
    gn_destroy(watchdog);

    /* Speed one advances the three-bit counter on alternate scanline-0x100
     * callbacks, with each callback occurring from emulated raster time. */
    const uint8_t video_animation_speed_one[] = {
        0x33u, 0xfcu, 0x01u, 0x00u, 0x00u, 0x3cu, 0x00u, 0x06u,
        0x4eu, 0x72u, 0x27u, 0x00u};
    memcpy(watchdog_bios + 0x100u, video_animation_speed_one,
           sizeof(video_animation_speed_one));
    assert(gn_create(&watchdog) == GN_STATUS_OK);
    assert(gn_load_mvs(watchdog, &watchdog_manifest) == GN_STATUS_OK);
    assert(gn_run_mvs(watchdog, 1u, &run) == GN_STATUS_OK &&
           run.elapsed_cycles == 40u);
    assert(gn_run_mvs(watchdog, 24u, &run) == GN_STATUS_OK &&
           run.reason == GN_RUN_STOPPED && run.elapsed_cycles == 24u);
    assert(gn_run_mvs(watchdog, UINT64_C(256) * UINT64_C(768) - 64u,
                      &run) == GN_STATUS_OK);
    assert(gn_test_mvs_read_bus(watchdog, UINT32_C(0x3c0006),
                                &video_control) == GN_STATUS_OK);
    assert((video_control & UINT16_C(7)) == UINT16_C(1));
    assert(gn_run_mvs(watchdog, UINT64_C(264) * UINT64_C(768),
                      &run) == GN_STATUS_OK);
    assert(gn_test_mvs_read_bus(watchdog, UINT32_C(0x3c0006),
                                &video_control) == GN_STATUS_OK);
    assert((video_control & UINT16_C(7)) == UINT16_C(1));
    assert(gn_run_mvs(watchdog, UINT64_C(264) * UINT64_C(768),
                      &run) == GN_STATUS_OK);
    assert(gn_test_mvs_read_bus(watchdog, UINT32_C(0x3c0006),
                                &video_control) == GN_STATUS_OK);
    assert((video_control & UINT16_C(7)) == UINT16_C(2));
    gn_destroy(watchdog);

    /* MAME maps the high byte of the control word but leaves the low-byte-only
     * lane unmapped; retain that distinction in the owned bus contract. */
    assert(gn_create(&watchdog) == GN_STATUS_OK);
    assert(gn_load_mvs(watchdog, &watchdog_manifest) == GN_STATUS_OK);
    uint8_t video_control_low = 0u;
    assert(gn_test_mvs_read_bus8(watchdog, UINT32_C(0x3c0007),
                                 &video_control_low) == GN_STATUS_INVALID_MEDIA);
    assert(gn_observe_mvs_bus_fault(watchdog, &observation, sizeof(observation)) ==
           GN_STATUS_OK);
    assert(observation.valid == 1u && observation.access == GN_MVS_BUS_ACCESS_READ &&
           observation.width == 1u);
    gn_destroy(watchdog);

    /* MAME's even/high-byte path duplicates the byte into both lanes before
     * calling video_register_w. Keep the callback data effects, including the
     * low-byte control bits, visible through the guest bus. */
    const uint8_t video_control_high_byte_write[] = {
        0x13u, 0xfcu, 0x00u, 0xa8u, 0x00u, 0x3cu, 0x00u, 0x06u};
    memcpy(watchdog_bios + 0x100u, video_control_high_byte_write,
           sizeof(video_control_high_byte_write));
    assert(gn_create(&watchdog) == GN_STATUS_OK);
    assert(gn_load_mvs(watchdog, &watchdog_manifest) == GN_STATUS_OK);
    assert(gn_run_mvs(watchdog, 1u, &run) == GN_STATUS_OK &&
           run.elapsed_cycles == 40u);
    assert(gn_run_mvs(watchdog, 20u, &run) == GN_STATUS_OK &&
           run.reason == GN_RUN_BUDGET && run.elapsed_cycles == 20u);
    assert(gn_observe_mvs_bus_fault(watchdog, &observation, sizeof(observation)) ==
           GN_STATUS_OK);
    assert(observation.valid == 0u);
    assert(observation.video_auto_animation_speed == UINT8_C(0xa8));
    assert(observation.video_auto_animation_disabled == 1u);
    assert(observation.display_position_interrupt_control == UINT8_C(0xa0));
    gn_destroy(watchdog);

    /* The odd/low-byte lane remains unmapped for video-register writes. */
    const uint8_t video_control_low_byte_write[] = {
        0x13u, 0xfcu, 0x00u, 0xa8u, 0x00u, 0x3cu, 0x00u, 0x07u};
    memcpy(watchdog_bios + 0x100u, video_control_low_byte_write,
           sizeof(video_control_low_byte_write));
    assert(gn_create(&watchdog) == GN_STATUS_OK);
    assert(gn_load_mvs(watchdog, &watchdog_manifest) == GN_STATUS_OK);
    assert(gn_run_mvs(watchdog, 1u, &run) == GN_STATUS_OK &&
           run.elapsed_cycles == 40u);
    assert(gn_run_mvs(watchdog, 20u, &run) == GN_STATUS_CPU_FAILURE);
    assert(gn_observe_mvs_bus_fault(watchdog, &observation, sizeof(observation)) ==
           GN_STATUS_OK);
    assert(observation.valid == 1u &&
           observation.access == GN_MVS_BUS_ACCESS_WRITE &&
           observation.width == 1u &&
           observation.address == UINT32_C(0x3c0007));
    gn_destroy(watchdog);

    const uint8_t interrupt_ack_program[] = {
        0x33u, 0xfcu, 0x00u, 0x07u, 0x00u, 0x3cu, 0x00u, 0x0cu};
    memcpy(watchdog_bios + 0x100u, interrupt_ack_program,
           sizeof(interrupt_ack_program));
    assert(gn_create(&watchdog) == GN_STATUS_OK);
    assert(gn_load_mvs(watchdog, &watchdog_manifest) == GN_STATUS_OK);
    assert(gn_run_mvs(watchdog, 1u, &run) == GN_STATUS_OK && run.elapsed_cycles == 40u);
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
    assert(gn_run_mvs(watchdog, 1u, &run) == GN_STATUS_OK && run.elapsed_cycles == 40u);
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
    assert(gn_run_mvs(watchdog, 1u, &run) == GN_STATUS_OK && run.elapsed_cycles == 40u);
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
    assert(gn_run_mvs(watchdog, 1u, &run) == GN_STATUS_OK && run.elapsed_cycles == 40u);
    assert(gn_run_mvs(watchdog, 20u, &run) == GN_STATUS_CPU_FAILURE);
    assert(gn_observe_mvs_bus_fault(watchdog, &observation, sizeof(observation)) == GN_STATUS_OK);
    assert(observation.valid == 1u && observation.access == GN_MVS_BUS_ACCESS_WRITE &&
           observation.width == 1u);
    gn_destroy(watchdog);

    /* The read-side modulo register wins over the overlapping cart ROM range;
     * this address is an index-2 read mirror while its write decode is IRQ ack. */
    assert(gn_create(&watchdog) == GN_STATUS_OK);
    assert(gn_load_mvs(watchdog, &watchdog_manifest) == GN_STATUS_OK);
    uint16_t cart_read_control = 0u;
    assert(gn_test_mvs_read_bus(watchdog, UINT32_C(0x3c000c),
                                &cart_read_control) == GN_STATUS_OK);
    assert(cart_read_control == UINT16_C(0x0000));
    assert(gn_observe_mvs_bus_fault(watchdog, &observation, sizeof(observation)) == GN_STATUS_OK);
    assert(observation.valid == 0u);
    gn_destroy(watchdog);

    const uint8_t no_pet_then_stop[] = {
        0x70u, 0x5au, 0x13u, 0xc0u, 0x00u, 0x10u, 0x00u, 0x01u,
        0x4eu, 0x72u, 0x27u, 0x00u};
    memcpy(watchdog_bios + 0x100u, no_pet_then_stop, sizeof(no_pet_then_stop));
    assert(gn_create(&watchdog) == GN_STATUS_OK);
    assert(gn_load_mvs(watchdog, &watchdog_manifest) == GN_STATUS_OK);
    assert(gn_run_mvs(watchdog, 1u, &run) == GN_STATUS_OK && run.elapsed_cycles == 40u);
    /* MOVEQ 4 + MOVE.B D0,(xxx).L 16 + STOP 4 = 24 (Tables 8-5, 8-2, 8-12). */
    assert(gn_run_mvs(watchdog, 24u, &run) == GN_STATUS_OK);
    assert(run.reason == GN_RUN_STOPPED && run.elapsed_cycles == 24u);
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
    /* 0x000080-0x0fffff now returns cartridge P1 bytes (plan 05-07). */
    const uint8_t *p1 = (const uint8_t *)manifest.regions[1].source;
    assert(gn_test_mvs_read_bus(instance, UINT32_C(0x000080), &value) ==
           GN_STATUS_OK && value == (uint16_t)((p1[0x80u] << 8) | p1[0x81u]));
    assert(gn_test_mvs_read_bus(instance, UINT32_C(0x00007e), &value) ==
           GN_STATUS_OK);
    assert(gn_test_mvs_read_bus(instance, UINT32_C(0x000100), &value) ==
           GN_STATUS_OK && value == (uint16_t)((p1[0x100u] << 8) | p1[0x101u]));
    assert(gn_test_mvs_read_bus(instance, UINT32_C(0x0ffffe), &value) ==
           GN_STATUS_OK && value == (uint16_t)((p1[0xffffeu] << 8) | p1[0xfffffu]));
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

/* Asserts exactly one captured log line and clears the capture. */
static void expect_one_log_line(const char *expected) {
    assert(log_line_count == 1u);
    assert(strcmp(log_lines[0], expected) == 0);
    log_line_count = 0u;
}

static uint16_t adapter_joypad_state;
static uint16_t adapter_p1_joypad_state;
static size_t adapter_l3_queries;
static size_t adapter_input_polls;
static size_t adapter_video_calls;
static const void *adapter_video_data[4];
static uint32_t adapter_video_pixels[4][320u * 224u];
static unsigned adapter_video_width[4];
static unsigned adapter_video_height[4];
static size_t adapter_video_pitch[4];

static void RETRO_CALLCONV adapter_input_poll(void) {
    ++adapter_input_polls;
}

static int16_t RETRO_CALLCONV adapter_input_state(unsigned port,
                                                  unsigned device,
                                                  unsigned index,
                                                  unsigned id) {
    (void)index;
    if (port != 0u || device != RETRO_DEVICE_JOYPAD) return 0;
    if (id == RETRO_DEVICE_ID_JOYPAD_SELECT)
        return (adapter_joypad_state & UINT16_C(0x0001)) != 0u;
    if (id == RETRO_DEVICE_ID_JOYPAD_START)
        return (adapter_joypad_state & UINT16_C(0x0002)) != 0u;
    return 0;
}

static int16_t RETRO_CALLCONV adapter_p1_input_state(unsigned port,
                                                     unsigned device,
                                                     unsigned index,
                                                     unsigned id) {
    (void)index;
    if (port != 0u || device != RETRO_DEVICE_JOYPAD || id >= 16u) return 0;
    if (id == RETRO_DEVICE_ID_JOYPAD_L3) ++adapter_l3_queries;
    return (adapter_p1_joypad_state & (uint16_t)(UINT16_C(1) << id)) != 0u;
}

static void RETRO_CALLCONV adapter_video_refresh(const void *data,
                                                 unsigned width,
                                                 unsigned height,
                                                 size_t pitch) {
    if (adapter_video_calls < sizeof(adapter_video_data) /
                              sizeof(adapter_video_data[0])) {
        adapter_video_data[adapter_video_calls] = data;
        adapter_video_width[adapter_video_calls] = width;
        adapter_video_height[adapter_video_calls] = height;
        adapter_video_pitch[adapter_video_calls] = pitch;
        if (data != NULL && width == 320u && height == 224u &&
            pitch >= (size_t)width * sizeof(uint32_t)) {
            uint8_t *destination = (uint8_t *)adapter_video_pixels[
                adapter_video_calls];
            const uint8_t *source = (const uint8_t *)data;
            for (size_t y = 0u; y < (size_t)height; ++y)
                memcpy(destination + y * (size_t)width * sizeof(uint32_t),
                       source + y * pitch,
                       (size_t)width * sizeof(uint32_t));
        }
    }
    ++adapter_video_calls;
    ++observation_video_callbacks;
}

static uint8_t *emit_video_ram_word(uint8_t *code, uint16_t offset,
                                    uint16_t value);
static uint32_t sprite_frame_pixel(const uint8_t *pixels, size_t pitch,
                                   size_t x, size_t y);

static uint8_t *make_adapter_input_bundle(const uint8_t *bundle, size_t size,
                                         int timeout_only, int draw_video) {
    uint8_t *copy = (uint8_t *)malloc(size);
    assert(copy != NULL);
    memcpy(copy, bundle, size);
    const gn_mvs_manifest manifest = bundle_manifest(copy, size, NULL);
    uint8_t *bios = (uint8_t *)manifest.regions[0].source;
    uint8_t *program = (uint8_t *)manifest.regions[1].source;
    uint8_t *fixed = NULL;
    uint8_t *sprites = NULL;
    for (size_t index = 0u; index < manifest.region_count; ++index) {
        if (manifest.regions[index].role == GN_MVS_REGION_FIXED)
            fixed = (uint8_t *)manifest.regions[index].source;
        if (manifest.regions[index].role == GN_MVS_REGION_SPRITES)
            sprites = (uint8_t *)manifest.regions[index].source;
    }
    assert(fixed != NULL && (draw_video != 4 || sprites != NULL));
    memset(fixed, 0, (size_t)0x20000u);
    fixed[0x20u + 0x10u] = UINT8_C(0x20);
    fixed[0x20u + 0x18u] = UINT8_C(0x03);
    fixed[0x20u + 0x00u] = UINT8_C(0x05);
    fixed[0x20u + 0x08u] = UINT8_C(0x07);
    uint8_t *code = bios + 0x100u;
    code = emit_move_b_imm(code, GN_MVS_REQUEST_DEMO,
                           GN_MVS_BIOS_USER_REQUEST);
    code = emit_jsr(code, GN_MVS_USER_ENTRY);
    if (timeout_only != 0) {
        code = emit16(emit16(code, 0x343cu), 0x7fffu); /* MOVE.W #32767,D2 */
        uint8_t *poll = code;
        code = emit_move_b_from(code, UINT32_C(0x320001));
        code = emit_move_b_from(code, UINT32_C(0x380000));
        code = emit16(emit16(code, 0x51cau), (uint16_t)(poll - (code + 2u)));
    } else {
        code = emit_status_wait(code, UINT32_C(0x00320001));
        code = emit_status_wait(code, UINT32_C(0x00380000));
        code = emit_move_b_imm(code, 1u, GN_MVS_BIOS_START_FLAG);
    }
    code = emit_jsr(code, GN_MVS_PLAYER_START_ENTRY);
    if (draw_video == 4 || draw_video == 5) emit_jmp(code, UINT32_C(0xc00100));
    else emit_stop(code);
    emit_rts(program + GN_MVS_USER_ENTRY);
    uint8_t *player = program + GN_MVS_PLAYER_START_ENTRY;
    if (draw_video == 1) {
        player = emit_video_ram_word(player, UINT16_C(0x7002),
                                     UINT16_C(0x1001));
        for (uint16_t pen = 1u; pen <= 8u; ++pen) {
            const uint32_t address = UINT32_C(0x400000) +
                (uint32_t)(UINT16_C(0x10) + pen) * UINT32_C(2);
            player = emit_move_w_imm(player, UINT16_C(0x7fff), address);
        }
    } else if (draw_video == 2) {
        player = emit_video_ram_word(player, UINT16_C(0x8000),
                                     UINT16_C(0x00fe));
        player = emit_video_ram_word(player, UINT16_C(0x8200),
                                     UINT16_C(0xf801));
        player = emit_video_ram_word(player, UINT16_C(0x8400),
                                     UINT16_C(0x0400));
    } else if (draw_video == 3) {
        /* P1 RIGHT is active-low bit 3 in the P1 control byte. A neutral
         * guest sees 0xff and leaves the tilemap and palette untouched. */
        player = emit_move_b_from(player, UINT32_C(0x00300000));
        player = emit16(emit16(player, UINT16_C(0x0c00)), UINT16_C(0x00f7));
        uint8_t *skip_video = player;
        player = emit16(player, UINT16_C(0x6600)); /* BNE.s, patched below. */
        player = emit_video_ram_word(player, UINT16_C(0x7002),
                                     UINT16_C(0x1001));
        for (uint16_t pen = 1u; pen <= 8u; ++pen) {
            const uint32_t address = UINT32_C(0x400000) +
                (uint32_t)(UINT16_C(0x10) + pen) * UINT32_C(2);
            player = emit_move_w_imm(player, UINT16_C(0x7fff), address);
        }
        const ptrdiff_t displacement = player - (skip_video + 2u);
        assert(displacement >= -128 && displacement <= 127);
        skip_video[1] = (uint8_t)displacement;
    } else if (draw_video == 5) {
        /* Original guest polls the complete active-low P1 byte and writes an
         * independently specified palette for each exact held control. */
        player = emit_video_ram_word(player, UINT16_C(0x7002), UINT16_C(0x1001));
        static const uint16_t values[] = {0xffu, 0xf7u, 0xfbu, 0xefu, 0xe7u};
        static const uint16_t colors[] = {0x100fu, 0x7fffu, 0x4f00u, 0x20f0u, 0x6ff0u};
        for (size_t index = 0u; index < 5u; ++index) {
            player = emit_move_b_from(player, UINT32_C(0x00300000));
            player = emit16(emit16(player, UINT16_C(0x0c00)), values[index]);
            uint8_t *skip = player;
            player = emit16(player, UINT16_C(0x6600));
            for (uint16_t pen = 1u; pen <= 8u; ++pen)
                player = emit_move_w_imm(player, colors[index],
                    UINT32_C(0x400020) + (uint32_t)pen * 2u);
            const ptrdiff_t displacement = player - (skip + 2u);
            assert(displacement > 0 && displacement <= 127);
            skip[1] = (uint8_t)displacement;
        }
    } else if (draw_video == 4) {
        /* Guest-selected scenery positions scroll beneath stationary player
         * and projectile strips; transparent pens expose lower-priority
         * scenery and FIX stays in front. Layout ancestry: SNK Hardware
         * pp.4,15-21 and pinned MAME S32-S38b in docs/mvs-media.md. */
        memset(sprites, 0, (size_t)0x180u);
        fixed[0x38u] = 0u;
        fixed[0x20u] = 0u;
        fixed[0x28u] = 0u;
        sprites[0x40u] = UINT8_C(0x81);
        sprites[0x00u] = UINT8_C(0xf1);
        sprites[0x42u] = UINT8_C(0x02);
        sprites[0x41u] = UINT8_C(0x04);
        sprites[0x43u] = UINT8_C(0x08);
        sprites[0xc0u] = UINT8_C(0x01); /* tile 1: player pen at x=0 */
        sprites[0x140u] = UINT8_C(0x02); /* tile 2: projectile at x=1 */
        player = emit_video_ram_word(player, UINT16_C(0x7022),
                                     UINT16_C(0x2001));
        player = emit_video_ram_word(player, UINT16_C(0x8000),
                                     UINT16_C(0xffff));
        player = emit_video_ram_word(player, UINT16_C(0x8200),
                                     UINT16_C(0xf801));
        player = emit_video_ram_word(player, UINT16_C(0x0000), 0u);
        player = emit_video_ram_word(player, UINT16_C(0x0001),
                                     UINT16_C(0x0100));
        for (uint16_t pen = 1u; pen <= 8u; ++pen) {
            const uint32_t sprite_palette = UINT32_C(0x400000) +
                (uint32_t)(UINT16_C(0x10) + pen) * UINT32_C(2);
            const uint32_t fixed_palette = UINT32_C(0x400000) +
                (uint32_t)(UINT16_C(0x20) + pen) * UINT32_C(2);
            player = emit_move_w_imm(player, UINT16_C(0x20f0), sprite_palette);
            player = emit_move_w_imm(player, UINT16_C(0x4f00), fixed_palette);
        }
        /* Later sprite strips overlay scenery; each uses a distinct palette. */
        for (uint16_t strip = 1u; strip <= 2u; ++strip) {
            player = emit_video_ram_word(player, (uint16_t)(0x8000u + strip), 0xffffu);
            player = emit_video_ram_word(player, (uint16_t)(0x8200u + strip), 0xf801u);
            player = emit_video_ram_word(player, (uint16_t)(0x8400u + strip),
                                         strip == 1u ? 0x0400u : 0x0c00u);
            player = emit_video_ram_word(player, (uint16_t)(strip * 0x40u), strip);
            player = emit_video_ram_word(player, (uint16_t)(strip * 0x40u + 1u),
                                         strip == 1u ? 0x0300u : 0x0400u);
        }
        player = emit_move_w_imm(player, 0x7fffu, UINT32_C(0x400062));
        player = emit_move_w_imm(player, 0x6ff0u, UINT32_C(0x400082));
        player = emit_move_w_imm(player, UINT16_C(0x100f),
                                 UINT32_C(0x401ffe));
        player = emit_move_b_from(player, UINT32_C(0x00300000));
        player = emit16(emit16(player, UINT16_C(0x0c00)), UINT16_C(0x00f7));
        uint8_t *right_branch = player;
        player = emit16(player, UINT16_C(0x6700)); /* BEQ.s, patched below. */
        player = emit_video_ram_word(player, UINT16_C(0x8400),
                                     UINT16_C(0x0400));
        uint8_t *skip_right = player;
        player = emit16(player, UINT16_C(0x6000)); /* BRA.s, patched below. */
        uint8_t *right_position = player;
        player = emit_video_ram_word(player, UINT16_C(0x8400),
                                     UINT16_C(0x0c00));
        ptrdiff_t displacement = right_position - (right_branch + 2u);
        assert(displacement >= -128 && displacement <= 127);
        right_branch[1] = (uint8_t)displacement;
        displacement = player - (skip_right + 2u);
        assert(displacement >= -128 && displacement <= 127);
        skip_right[1] = (uint8_t)displacement;
    }
    emit_rts(player);
    return copy;
}

static uint8_t *make_adapter_zoom_bundle(const uint8_t *bundle, size_t size,
                                         size_t *out_size) {
    assert(size >= 16u && get32be(bundle + 4u) == GN_MVS_MANIFEST_VERSION &&
           get32be(bundle + 12u) == GN_MVS_MAX_REGIONS);
    const size_t zoom_size = GN_MVS_Y_ZOOM_BYTES;
    assert(size <= SIZE_MAX - 12u - zoom_size);
    *out_size = size + 12u + zoom_size;
    uint8_t *copy = (uint8_t *)calloc(*out_size, 1u);
    assert(copy != NULL);
    memcpy(copy, bundle, size);
    /* The core test uses a synthetic table solely to exercise native loading. */
    copy[7] = (uint8_t)GN_MVS_MANIFEST_VERSION_ZOOM;
    copy[15] = (uint8_t)GN_MVS_V3_MAX_REGIONS;
    uint8_t *descriptor = copy + size;
    descriptor[3] = (uint8_t)GN_MVS_REGION_Y_ZOOM;
    descriptor[8] = (uint8_t)(zoom_size >> 24);
    descriptor[9] = (uint8_t)(zoom_size >> 16);
    descriptor[10] = (uint8_t)(zoom_size >> 8);
    descriptor[11] = (uint8_t)zoom_size;
    return copy;
}

static void check_mvs_adapter_start_response(const uint8_t *bundle,
                                             size_t bundle_size) {
    uint8_t *adapter_bundle = make_adapter_input_bundle(bundle, bundle_size,
                                                        0, 1);
    struct retro_game_info game = {
        NULL, adapter_bundle, bundle_size, NULL};
    const gn_mvs_manifest manifest = bundle_manifest(adapter_bundle,
                                                       bundle_size, NULL);
    gn_instance *native = NULL;
    assert(gn_create(&native) == GN_STATUS_OK);
    assert(gn_load_mvs(native, &manifest) == GN_STATUS_OK);
    const size_t frame_bytes = (size_t)320u * (size_t)224u * sizeof(uint32_t);
    uint8_t *native_pixels = (uint8_t *)malloc(frame_bytes);
    assert(native_pixels != NULL);
    size_t native_produced = 0u;
    memset(adapter_video_data, 0, sizeof(adapter_video_data));
    memset(adapter_video_width, 0, sizeof(adapter_video_width));
    memset(adapter_video_height, 0, sizeof(adapter_video_height));
    memset(adapter_video_pitch, 0, sizeof(adapter_video_pitch));
    adapter_video_calls = 0u;
    adapter_input_polls = 0u;
    adapter_joypad_state = 0u;
    retro_set_input_poll(adapter_input_poll);
    retro_set_input_state(adapter_input_state);
    retro_set_video_refresh(adapter_video_refresh);
    assert(retro_load_game(&game));
    expect_one_log_line("glueyneo: MVS bundle loaded");

    /* The no-input frame and coin-only frame do not claim a start response. */
    retro_run();
    assert(log_line_count == 0u);
    adapter_joypad_state = UINT16_C(0x0001);
    retro_run();
    assert(log_line_count == 0u);
    adapter_joypad_state = UINT16_C(0x0003);
    retro_run();
    expect_one_log_line("glueyneo: MVS P1 start indication observed");
    retro_run();
    assert(log_line_count == 0u);

    assert(adapter_video_calls == 4u && adapter_input_polls == 4u);
    const uint32_t frame_inputs[] = {
        0u, GN_MVS_INPUT_COIN1,
        GN_MVS_INPUT_COIN1 | GN_MVS_INPUT_P1_START,
        GN_MVS_INPUT_COIN1 | GN_MVS_INPUT_P1_START};
    for (size_t frame = 0u; frame < adapter_video_calls; ++frame) {
        assert(adapter_video_data[frame] != NULL);
        assert(adapter_video_width[frame] == 320u);
        assert(adapter_video_height[frame] == 224u);
        assert(adapter_video_pitch[frame] == 320u * sizeof(uint32_t));
        assert(gn_set_mvs_inputs(native, frame_inputs[frame]) == GN_STATUS_OK);
        gn_run_result native_run;
        assert(gn_mvs_run_frame_budget(native, &native_run) ==
               GN_STATUS_OK);
        assert(native_run.reason != GN_RUN_ERROR &&
               native_run.reason != GN_RUN_FAULT);
        assert(gn_private_mvs_render_frame(native, 320u, 224u,
                   320u * sizeof(uint32_t), native_pixels, frame_bytes,
                   &native_produced) == GN_STATUS_OK);
        assert(native_produced == (size_t)320u * (size_t)224u);
        const uint32_t *pixels = adapter_video_pixels[frame];
        if (frame < 2u) {
            for (size_t pixel = 0u; pixel < 320u * 224u; ++pixel)
                assert(pixels[pixel] == 0u);
        } else {
            const uint32_t expected[] = {
                UINT32_C(0), UINT32_C(0x00ffffff), UINT32_C(0x00ffffff),
                UINT32_C(0), UINT32_C(0x00ffffff), UINT32_C(0),
                UINT32_C(0x00ffffff), UINT32_C(0)};
            for (size_t pixel = 0u; pixel < sizeof(expected) / sizeof(expected[0]);
                 ++pixel) {
                assert(((const uint32_t *)native_pixels)[pixel] ==
                       expected[pixel]);
                assert(pixels[pixel] == expected[pixel]);
            }
            assert(pixels[8u] == 0u);
        }
        assert(memcmp(pixels, native_pixels, frame_bytes) == 0);
    }
    /* A log checkpoint counts submitted frames, never a host-time delay.
     * Exercise the neighbor boundaries and one-shot behavior. */
    for (unsigned frame = 4u; frame < 719u; ++frame) retro_run();
    assert(log_line_count == 5u);
    for (size_t line = 0u; line < log_line_count; ++line) {
        char expected[128];
        (void)snprintf(expected, sizeof(expected),
            "glueyneo: MVS video checkpoint: %u frames",
            (unsigned)(line + 1u) * 120u);
        assert(strcmp(log_lines[line], expected) == 0);
    }
    log_line_count = 0u;
    retro_run();
    expect_one_log_line("glueyneo: MVS video checkpoint: 720 frames");
    retro_run();
    assert(log_line_count == 0u);
    retro_reset();
    for (unsigned frame = 0u; frame < 719u; ++frame) retro_run();
    /* Reset may produce another guest start indication, independently. */
    log_line_count = 0u;
    retro_run();
    expect_one_log_line("glueyneo: MVS video checkpoint: 720 frames");
    retro_unload_game();
    gn_destroy(native);
    free(native_pixels);

    /* Unload and a rejected load submit no frame. A new valid instance follows. */
    memset(adapter_video_data, 0, sizeof(adapter_video_data));
    memset(adapter_video_pixels, 0xa5, sizeof(adapter_video_pixels));
    adapter_video_calls = 0u;
    retro_run();
    assert(adapter_video_calls == 0u);
    struct retro_game_info rejected = game;
    rejected.size = bundle_size - 100u;
    assert(!retro_load_game(&rejected));
    expect_one_log_line("glueyneo: MVS bundle rejected: malformed");
    retro_run();
    assert(adapter_video_calls == 0u);
    free(adapter_bundle);

    adapter_bundle = make_adapter_input_bundle(bundle, bundle_size, 0, 2);
    game.data = adapter_bundle;
    game.size = bundle_size;
    assert(retro_load_game(&game));
    expect_one_log_line("glueyneo: MVS bundle loaded");
    adapter_joypad_state = 0u;
    retro_run();
    adapter_joypad_state = UINT16_C(0x0001);
    retro_run();
    adapter_joypad_state = UINT16_C(0x0003);
    retro_run();
    expect_one_log_line("glueyneo: MVS video rendering failed");
    assert(adapter_video_calls == 3u);
    for (size_t frame = 0u; frame < 3u; ++frame) {
        assert(adapter_video_data[frame] != NULL);
        assert(adapter_video_width[frame] == 320u);
        assert(adapter_video_height[frame] == 224u);
        const uint32_t *pixels = adapter_video_pixels[frame];
        for (size_t pixel = 0u; pixel < 320u * 224u; ++pixel)
            assert(pixels[pixel] == 0u);
    }
    retro_unload_game();
    free(adapter_bundle);

    adapter_bundle = make_adapter_input_bundle(bundle, bundle_size, 1, 0);
    game.data = adapter_bundle;
    adapter_video_calls = 0u;
    memset(adapter_video_data, 0, sizeof(adapter_video_data));
    memset(adapter_video_pixels, 0xa5, sizeof(adapter_video_pixels));
    adapter_joypad_state = 0u;
    assert(retro_load_game(&game));
    expect_one_log_line("glueyneo: MVS bundle loaded");
    for (unsigned frame = 0u; frame < 9u; ++frame) {
        adapter_joypad_state = frame == 1u ? UINT16_C(1) :
                              frame == 2u ? UINT16_C(2) : UINT16_C(0);
        retro_run();
        assert(log_line_count == 0u);
    }
    assert(adapter_video_calls == 9u);
    for (size_t frame = 0u; frame < 4u; ++frame) {
        assert(adapter_video_data[frame] != NULL);
        for (size_t pixel = 0u; pixel < 320u * 224u; ++pixel)
            assert(adapter_video_pixels[frame][pixel] == 0u);
    }
    retro_unload_game();
    free(adapter_bundle);
}

static void check_mvs_adapter_right_guest_pixels(const uint8_t *bundle,
                                                  size_t bundle_size) {
    uint8_t *adapter_bundle = make_adapter_input_bundle(
        bundle, bundle_size, 0, 3);
    struct retro_game_info game = {NULL, adapter_bundle, bundle_size, NULL};
    const size_t frame_bytes = (size_t)320u * 224u * sizeof(uint32_t);
    uint8_t *native_pixels = (uint8_t *)malloc(frame_bytes);
    uint8_t *neutral_pixels = (uint8_t *)malloc(frame_bytes);
    assert(native_pixels != NULL && neutral_pixels != NULL);
    memset(adapter_video_data, 0, sizeof(adapter_video_data));
    memset(adapter_video_pixels, 0xa5, sizeof(adapter_video_pixels));
    adapter_video_calls = 0u;
    adapter_input_polls = 0u;
    adapter_input_descriptor_count = 0u;
    adapter_p1_joypad_state =
        (uint16_t)((UINT16_C(1) << RETRO_DEVICE_ID_JOYPAD_SELECT) |
                   (UINT16_C(1) << RETRO_DEVICE_ID_JOYPAD_START) |
                   (UINT16_C(1) << RETRO_DEVICE_ID_JOYPAD_RIGHT));
    retro_set_environment(environment);
    retro_set_input_poll(adapter_input_poll);
    retro_set_input_state(adapter_p1_input_state);
    retro_set_video_refresh(adapter_video_refresh);
    assert(retro_load_game(&game));
    expect_one_log_line("glueyneo: MVS bundle loaded");
    retro_run();
    assert(adapter_input_polls == 1u && adapter_video_calls == 1u);
    assert(adapter_video_data[0] != NULL && adapter_video_width[0] == 320u &&
           adapter_video_height[0] == 224u &&
           adapter_video_pitch[0] == 320u * sizeof(uint32_t));

    /* The original guest branches on the exact control byte before writing
     * its fixed tile and palette. RIGHT must reach the callback's guest run. */
    const uint32_t expected[] = {
        UINT32_C(0), UINT32_C(0x00ffffff), UINT32_C(0x00ffffff),
        UINT32_C(0), UINT32_C(0x00ffffff), UINT32_C(0),
        UINT32_C(0x00ffffff), UINT32_C(0)};
    const uint32_t *callback_pixels = adapter_video_pixels[0];
    for (size_t x = 0u; x < sizeof(expected) / sizeof(expected[0]); ++x)
        assert(callback_pixels[x] == expected[x]);
    for (size_t x = 8u; x < 320u; ++x) assert(callback_pixels[x] == 0u);

    const gn_mvs_manifest manifest = bundle_manifest(adapter_bundle,
                                                       bundle_size, NULL);
    gn_instance *native = NULL;
    gn_instance *neutral = NULL;
    assert(gn_create(&native) == GN_STATUS_OK);
    assert(gn_load_mvs(native, &manifest) == GN_STATUS_OK);
    assert(gn_set_mvs_inputs(native, GN_MVS_INPUT_COIN1 |
        GN_MVS_INPUT_P1_START | UINT32_C(0x00000020)) == GN_STATUS_OK);
    gn_run_result run;
    assert(gn_mvs_run_frame_budget(native, &run) == GN_STATUS_OK);
    assert(run.reason != GN_RUN_ERROR && run.reason != GN_RUN_FAULT);
    size_t produced = 0u;
    assert(gn_private_mvs_render_frame(native, 320u, 224u, 320u * 4u,
        native_pixels, frame_bytes, &produced) == GN_STATUS_OK);
    assert(produced == (size_t)320u * 224u);
    assert(memcmp(callback_pixels, native_pixels, frame_bytes) == 0);

    assert(gn_create(&neutral) == GN_STATUS_OK);
    assert(gn_load_mvs(neutral, &manifest) == GN_STATUS_OK);
    assert(gn_set_mvs_inputs(neutral, GN_MVS_INPUT_COIN1 |
        GN_MVS_INPUT_P1_START) == GN_STATUS_OK);
    assert(gn_mvs_run_frame_budget(neutral, &run) == GN_STATUS_OK);
    assert(run.reason != GN_RUN_ERROR && run.reason != GN_RUN_FAULT);
    assert(gn_private_mvs_render_frame(neutral, 320u, 224u, 320u * 4u,
        neutral_pixels, frame_bytes, &produced) == GN_STATUS_OK);
    assert(produced == (size_t)320u * 224u);
    for (size_t pixel = 0u; pixel < (size_t)320u * 224u; ++pixel)
        assert(((const uint32_t *)neutral_pixels)[pixel] == 0u);

    /* Input descriptors are static for the loaded game's lifetime and name
     * the physical Neo Geo line rather than a guessed game action. */
    assert(adapter_input_descriptor_count == 10u);
    assert(strcmp(adapter_input_descriptors[0].description, "P1 Up") == 0);
    assert(strcmp(adapter_input_descriptors[3].description, "P1 Right") == 0);
    assert(strcmp(adapter_input_descriptors[4].description, "P1 Button A") == 0);
    assert(strcmp(adapter_input_descriptors[9].description, "P1 Start") == 0);

    gn_destroy(native);
    gn_destroy(neutral);
    retro_unload_game();
    free(native_pixels);
    free(neutral_pixels);
    free(adapter_bundle);
}

#ifdef GLUEYNEO_MVS_INPUT_OBSERVATIONS
typedef struct {
    char kind;
    unsigned long long sample, mask, video, cycles;
} input_observation;

static input_observation read_input_observation(size_t index) {
    assert(index < observation_line_count);
    input_observation record;
    int consumed = 0;
    assert(sscanf(observation_lines[index], "glueyneo: mvs %c %llu %llu %llu %llu%n",
        &record.kind, &record.sample, &record.mask, &record.video,
        &record.cycles, &consumed) == 5);
    assert(observation_lines[index][consumed] == '\0');
    return record;
}

static size_t count_observation_kind(char kind) {
    size_t count = 0u;
    for (size_t index = 0u; index < observation_line_count; ++index)
        if (read_input_observation(index).kind == kind) ++count;
    return count;
}
#endif

static void check_mvs_input_observations(const uint8_t *bundle, size_t size) {
    audio_delivery_line_count = 0u;
    log_interface_offered = true;
    log_line_count = 0u;
    observation_line_count = 0u;
    observation_video_callbacks = 0u;
    adapter_l3_queries = 0u;
    retro_set_environment(environment);
    retro_init();
    retro_set_input_poll(adapter_input_poll);
    retro_set_input_state(adapter_p1_input_state);
    retro_set_video_refresh(adapter_video_refresh);
    uint8_t *copy = make_adapter_input_bundle(bundle, size, 0, 5);
    struct retro_game_info game = {NULL, copy, size, NULL};
    assert(retro_load_game(&game));
    expect_one_log_line("glueyneo: MVS bundle loaded");
    const unsigned masks[] = {RETRO_DEVICE_ID_JOYPAD_RIGHT,
        RETRO_DEVICE_ID_JOYPAD_RIGHT, 16u, RETRO_DEVICE_ID_JOYPAD_LEFT,
        RETRO_DEVICE_ID_JOYPAD_RIGHT, RETRO_DEVICE_ID_JOYPAD_B, 16u};
    const uint32_t expected[] = {0xffffffu, 0xffffffu, 0xffu,
        0xff0000u, 0xffff00u, 0xff00u, 0xffu};
    for (size_t frame = 0u; frame < 7u; ++frame) {
        adapter_video_calls = 0u;
        adapter_p1_joypad_state = (uint16_t)(
            (UINT16_C(1) << RETRO_DEVICE_ID_JOYPAD_SELECT) |
            (UINT16_C(1) << RETRO_DEVICE_ID_JOYPAD_START) |
            (masks[frame] == 16u ? 0u : (UINT16_C(1) << masks[frame])) |
            (frame == 4u ? (UINT16_C(1) << RETRO_DEVICE_ID_JOYPAD_B) : 0u));
        retro_run();
        assert(adapter_video_calls == 1u);
        assert(adapter_video_pixels[0][1] == expected[frame]);
    }
#ifdef GLUEYNEO_MVS_INPUT_OBSERVATIONS
    assert(observation_line_count > 0u);
    assert(audio_frame_line_count == 7u && audio_frame_sample_total > 0u);
    assert(audio_frame_last_mask == 3u);
    assert(strcmp(observation_lines[0], "glueyneo: mvs B 0 0 0 0") == 0);
    const unsigned long long samples[] = {1u, 3u, 4u, 5u, 6u, 7u};
    const unsigned long long complete_masks[] = {35u, 3u, 19u, 99u, 67u, 3u};
    size_t transitions = 0u;
    size_t successful = 0u;
    unsigned long long last_sample = 0u, last_video = 0u, last_cycles = 0u;
    input_observation last_success = {0};
    for (size_t index = 0u; index < observation_line_count; ++index) {
        const input_observation record = read_input_observation(index);
        assert(record.sample >= last_sample && record.video >= last_video &&
               record.cycles >= last_cycles);
        last_sample = record.sample;
        last_video = record.video;
        last_cycles = record.cycles;
        if (record.kind == 'S') {
            assert(transitions < 6u);
            assert(record.sample == samples[transitions]);
            assert(record.mask == complete_masks[transitions]);
            assert(record.video == record.sample - 1u);
            assert((record.sample == 1u) == (record.cycles == 0u));
            assert(observation_callback_at_log[index] == record.video);
            ++transitions;
        } else if (record.kind == 'V') {
            assert(successful < 6u);
            assert(record.sample == samples[successful]);
            assert(record.mask == complete_masks[successful]);
            assert(record.video == record.sample && record.cycles > 0u);
            assert(observation_callback_at_log[index] == record.video);
            ++successful;
            last_success = record;
        } else if (record.kind == 'R' || record.kind == 'P') {
            assert(last_success.kind == 'V' && record.sample == last_success.sample &&
                   record.video == last_success.video && record.cycles == last_success.cycles);
        }
        /* An executable public original-guest trace for the host parser. */
        puts(observation_lines[index]);
    }
    assert(transitions == 6u && successful == 6u);
    assert(count_observation_kind('B') == 1u);
    /* This palette guest does not draw the P1 indication. Protocol entry
     * alone must not invent that visible readiness claim. */
    assert(count_observation_kind('P') == 0u);
    assert(count_observation_kind('R') == 1u);

    /* Hold creates bounded frame checkpoints, with no invented new sample
     * transition. Callback sequence, rather than host time, advances them. */
    const size_t previous_lines = observation_line_count;
    for (unsigned frame = 0u; frame < 64u; ++frame) retro_run();
    assert(count_observation_kind('S') == 6u);
    bool found32 = false, found64 = false, found10 = false, found14 = false;
    for (size_t index = previous_lines; index < observation_line_count; ++index) {
        const input_observation record = read_input_observation(index);
        if (record.kind != 'V') continue;
        assert(record.sample == record.video && record.cycles > 0u);
        assert(observation_callback_at_log[index] == record.video);
        found32 |= record.video == 32u;
        found64 |= record.video == 64u;
        found10 |= record.video == 10u; /* fourth frame after sample seven */
        found14 |= record.video == 14u; /* eighth frame in transition burst */
        assert(record.video <= 14u || record.video % 32u == 0u);
    }
    assert(found32 && found64 && found10 && found14);

    /* L3 is an opt-in host observation request, never an emulated Neo Geo
     * input. It adds two-frame successful-video checkpoints while held. */
    const size_t before_request = observation_line_count;
    adapter_p1_joypad_state |= (uint16_t)(UINT16_C(1) << RETRO_DEVICE_ID_JOYPAD_L3);
    for (unsigned frame = 0u; frame < 9u; ++frame) {
        adapter_video_calls = 0u;
        retro_run();
        assert(adapter_video_calls == 1u && adapter_video_pixels[0][1] == 0xffu);
    }
    assert(observation_line_count == before_request + 5u);
    for (size_t index = 0u; index < 5u; ++index) {
        const input_observation record = read_input_observation(before_request + index);
        assert(record.kind == 'V' && record.video == 72u + index * 2u);
        assert(record.sample == record.video && record.mask == 3u);
        const unsigned long long horizon = record.video * 202752u;
        assert(record.cycles >= horizon && record.cycles < horizon + 64u);
        assert(observation_callback_at_log[before_request + index] == record.video);
    }
    const size_t after_request = observation_line_count;
    adapter_p1_joypad_state &= (uint16_t)~(UINT16_C(1) << RETRO_DEVICE_ID_JOYPAD_L3);
    for (unsigned frame = 0u; frame < 17u; ++frame) retro_run();
    assert(observation_line_count == after_request + 1u);
    const input_observation released_request = read_input_observation(after_request);
    assert(released_request.kind == 'V' && released_request.video == 96u &&
           released_request.mask == 3u);
    assert(count_observation_kind('S') == 6u);
    assert(adapter_l3_queries == 97u);

    /* More than enough changes exhaust exactly 256 total records, with one
     * explicit terminal marker. A held request cannot bypass that cap, and
     * guest video still runs after diagnostics stop. */
    adapter_p1_joypad_state |= (uint16_t)(UINT16_C(1) << RETRO_DEVICE_ID_JOYPAD_L3);
    for (unsigned frame = 0u; frame < 150u; ++frame) {
        adapter_p1_joypad_state ^= (uint16_t)(UINT16_C(1) << RETRO_DEVICE_ID_JOYPAD_RIGHT);
        retro_run();
    }
    assert(observation_line_count == OBSERVATION_RECORDS_MAX);
    assert(count_observation_kind('X') == 1u);
    assert(read_input_observation(255u).kind == 'X');
    size_t bytes = 0u;
    for (size_t index = 0u; index < observation_line_count; ++index)
        bytes += strlen(observation_lines[index]) + 1u;
    assert(bytes < 12u * 1024u);
    const size_t callbacks_before = observation_video_callbacks;
    for (unsigned frame = 0u; frame < 4u; ++frame) retro_run();
    assert(observation_line_count == 256u &&
           observation_video_callbacks == callbacks_before + 4u);

    /* Successful reset and a fresh load both restart counters and allowance. */
    retro_reset();
    observation_line_count = 0u;
    observation_video_callbacks = 0u;
    retro_run();
    assert(strcmp(observation_lines[0], "glueyneo: mvs B 0 0 0 0") == 0);
    assert(read_input_observation(1u).sample == 1u);
    assert(read_input_observation(2u).video == 1u);
#else
    adapter_p1_joypad_state |= (uint16_t)(UINT16_C(1) << RETRO_DEVICE_ID_JOYPAD_L3);
    adapter_video_calls = 0u;
    retro_run();
    assert(adapter_video_calls == 1u && adapter_video_pixels[0][1] == 0xffu);
    assert(observation_line_count == 0u);
    assert(adapter_l3_queries == 0u);
#endif
    retro_unload_game();
#ifdef GLUEYNEO_MVS_INPUT_OBSERVATIONS
    assert(audio_delivery_line_count == 1u);
    unsigned long long generated, submitted, processed, discarded, overreports;
    assert(sscanf(audio_delivery_line,
        "glueyneo: MVS audio final delivery: generated=%llu submitted=%llu "
        "processed=%llu discarded=%llu overreports=%llu",
        &generated, &submitted, &processed, &discarded, &overreports) == 5);
    /* This original observer guest has no audio callback: every generated
     * frame is deliberately discarded, rather than submitted or queued. */
    assert(generated > 0u && submitted == 0u && processed == 0u &&
           discarded == generated && overreports == 0u);
    assert(audio_frame_line_count == 1u && audio_frame_sample_total == generated);
#endif
    const size_t unloaded_lines = observation_line_count;
    retro_run();
    assert(observation_line_count == unloaded_lines);
    free(copy);
#ifdef GLUEYNEO_MVS_INPUT_OBSERVATIONS
    observation_line_count = 0u;
    observation_video_callbacks = 0u;
    copy = make_adapter_input_bundle(bundle, size, 0, 1);
    game.data = copy;
    log_line_count = 0u;
    assert(retro_load_game(&game));
    expect_one_log_line("glueyneo: MVS bundle loaded");
    adapter_p1_joypad_state = 0u;
    retro_run();
    adapter_p1_joypad_state = (uint16_t)(UINT16_C(1) << RETRO_DEVICE_ID_JOYPAD_SELECT);
    retro_run();
    adapter_p1_joypad_state |= (uint16_t)(UINT16_C(1) << RETRO_DEVICE_ID_JOYPAD_START);
    retro_run();
    expect_one_log_line("glueyneo: MVS P1 start indication observed");
    for (unsigned frame = 0u; frame < 4u; ++frame) retro_run();
    assert(count_observation_kind('P') == 1u && count_observation_kind('R') == 1u);
    retro_unload_game();
    free(copy);

    observation_line_count = 0u;
    observation_video_callbacks = 0u;
    copy = make_adapter_input_bundle(bundle, size, 0, 2);
    game.data = copy;
    log_line_count = 0u;
    assert(retro_load_game(&game));
    expect_one_log_line("glueyneo: MVS bundle loaded");
    adapter_p1_joypad_state = (uint16_t)(
        (UINT16_C(1) << RETRO_DEVICE_ID_JOYPAD_SELECT) |
        (UINT16_C(1) << RETRO_DEVICE_ID_JOYPAD_START));
    retro_run();
    expect_one_log_line("glueyneo: MVS video rendering failed");
    assert(count_observation_kind('B') == 1u && count_observation_kind('S') == 1u);
    assert(count_observation_kind('V') == 0u && count_observation_kind('P') == 0u &&
           count_observation_kind('R') == 0u);
    retro_unload_game();
    free(copy);

    observation_line_count = 0u;
    observation_video_callbacks = 0u;
    copy = make_adapter_input_bundle(bundle, size, 0, 1);
    const gn_mvs_manifest fault_manifest = bundle_manifest(copy, size, NULL);
    uint8_t *fault_code = (uint8_t *)fault_manifest.regions[0].source + 0x100u;
    fault_code[0] = 0x4eu; fault_code[1] = 0x71u; /* NOP */
    fault_code[2] = 0xffu; fault_code[3] = 0xffu; /* unsupported */
    game.data = copy;
    assert(retro_load_game(&game));
    expect_one_log_line("glueyneo: MVS bundle loaded");
    retro_run();
    expect_one_log_line("glueyneo: MVS guest run fault");
    assert(count_observation_kind('B') == 1u && count_observation_kind('S') == 1u);
    assert(count_observation_kind('V') == 0u && count_observation_kind('P') == 0u &&
           count_observation_kind('R') == 0u);
    retro_unload_game();
    free(copy);
#endif
    retro_deinit();
    log_line_count = 0u;
    log_interface_offered = false;
}

static void check_mvs_adapter_composition(const uint8_t *bundle,
                                          size_t bundle_size) {
    uint8_t *adapter_bundle = make_adapter_input_bundle(
        bundle, bundle_size, 0, 4);
    struct retro_game_info game = {NULL, adapter_bundle, bundle_size, NULL};
    const gn_mvs_manifest manifest = bundle_manifest(adapter_bundle,
                                                       bundle_size, NULL);
    const size_t frame_bytes = (size_t)320u * 224u * sizeof(uint32_t);
    uint8_t *native_pixels = (uint8_t *)malloc(frame_bytes);
    assert(native_pixels != NULL);
    memset(adapter_video_data, 0, sizeof(adapter_video_data));
    memset(adapter_video_pixels, 0xa5, sizeof(adapter_video_pixels));
    adapter_video_calls = 0u;
    adapter_input_polls = 0u;
    adapter_p1_joypad_state = 0u;
    retro_set_environment(environment);
    retro_set_input_poll(adapter_input_poll);
    retro_set_input_state(adapter_p1_input_state);
    retro_set_video_refresh(adapter_video_refresh);
    assert(retro_load_game(&game));
    expect_one_log_line("glueyneo: MVS bundle loaded");

    gn_instance *native = NULL;
    assert(gn_create(&native) == GN_STATUS_OK);
    assert(gn_load_mvs(native, &manifest) == GN_STATUS_OK);
    for (unsigned frame = 0u; frame < 3u; ++frame) {
        const int moved = frame == 1u;
        adapter_p1_joypad_state = (uint16_t)(
            (UINT16_C(1) << RETRO_DEVICE_ID_JOYPAD_SELECT) |
            (UINT16_C(1) << RETRO_DEVICE_ID_JOYPAD_START) |
            (moved ? (UINT16_C(1) << RETRO_DEVICE_ID_JOYPAD_RIGHT) : 0u));
        retro_run();
        assert(adapter_video_calls == (size_t)frame + 1u);
        assert(adapter_video_data[frame] != NULL &&
               adapter_video_width[frame] == 320u &&
               adapter_video_height[frame] == 224u &&
               adapter_video_pitch[frame] == 320u * sizeof(uint32_t));

        const uint32_t inputs = GN_MVS_INPUT_COIN1 | GN_MVS_INPUT_P1_START |
            (moved ? GN_MVS_INPUT_P1_RIGHT : 0u);
        assert(gn_set_mvs_inputs(native, inputs) == GN_STATUS_OK);
        gn_run_result run;
        assert(gn_mvs_run_frame_budget(native, &run) == GN_STATUS_OK);
        assert(run.reason == GN_RUN_BUDGET);
        size_t produced = 0u;
        assert(gn_private_mvs_render_frame(native, 320u, 224u, 320u * 4u,
            native_pixels, frame_bytes, &produced) == GN_STATUS_OK);
        assert(produced == (size_t)320u * 224u);
        assert(memcmp(adapter_video_pixels[frame], native_pixels,
                      frame_bytes) == 0);

        /* Player/projectile remain fixed as the scenery moves under them.
         * FIX red at x=9 covers scenery; its hole at x=8 reveals the player. */
        assert(sprite_frame_pixel((const uint8_t *)adapter_video_pixels[frame], 320u * 4u,
                                  9u, 0u) == UINT32_C(0x00ff0000));
        assert(sprite_frame_pixel((const uint8_t *)adapter_video_pixels[frame], 320u * 4u,
                                  8u, 0u) == UINT32_C(0x00ffffff));
        assert(sprite_frame_pixel((const uint8_t *)adapter_video_pixels[frame], 320u * 4u,
                                  25u, 0u) == UINT32_C(0x00ffff00));
        assert(sprite_frame_pixel((const uint8_t *)adapter_video_pixels[frame], 320u * 4u,
                                  moved ? 26u : 10u, 0u) == UINT32_C(0x0000ff00));
        assert(sprite_frame_pixel((const uint8_t *)adapter_video_pixels[frame], 320u * 4u,
                                  moved ? 10u : 26u, 0u) == UINT32_C(0x000000ff));
        assert(sprite_frame_pixel((const uint8_t *)adapter_video_pixels[frame], 320u * 4u,
                                  300u, 0u) == UINT32_C(0x000000ff));
    }
    assert(adapter_input_polls == 3u);
    gn_destroy(native);
    retro_unload_game();
    free(native_pixels);
    free(adapter_bundle);
}

static void check_content_cadence(const uint8_t *bundle, size_t size) {
    struct retro_system_av_info av;
    av_test_active = true;
    av_update_calls = 0u;
    retro_get_system_av_info(&av);
    assert(av.timing.fps == 60.0);
    struct retro_game_info mvs = {NULL, bundle, size, NULL};
    assert(retro_load_game(&mvs));
    expect_one_log_line("glueyneo: MVS bundle loaded");
    retro_get_system_av_info(&av);
    assert(av.timing.fps == 12000000.0 / 202752.0);
    assert(av_update_calls == 0u); /* API permits updates only in retro_run. */
    av_test_in_run = true;
    retro_run();
    av_test_in_run = false;
    assert(av_update_calls == 1u && av_updated_fps == av.timing.fps);
    av_test_in_run = true;
    retro_run();
    av_test_in_run = false;
    assert(av_update_calls == 1u);
    retro_unload_game();
    retro_get_system_av_info(&av);
    assert(av.timing.fps == 60.0);
    uint8_t fixture[602];
    public_guest_build(fixture);
    struct retro_game_info gnfx = {NULL, fixture, sizeof(fixture), NULL};
    assert(retro_load_game(&gnfx));
    retro_get_system_av_info(&av);
    assert(av.timing.fps == 60.0);
    av_test_in_run = true;
    retro_run();
    av_test_in_run = false;
    assert(av_update_calls == 2u && av_updated_fps == 60.0);
    retro_unload_game();
    av_update_allowed = false;
    assert(retro_load_game(&mvs));
    expect_one_log_line("glueyneo: MVS bundle loaded");
    av_test_in_run = true;
    retro_run();
    retro_run();
    av_test_in_run = false;
    assert(av_update_calls == 3u);
    expect_one_log_line("glueyneo: AV timing update unsupported");
    retro_get_system_av_info(&av);
    assert(av.timing.fps == 12000000.0 / 202752.0);
    retro_unload_game();
    av_update_allowed = true;
    av_test_active = false;
}

static void check_callbacks(const uint8_t *bundle, size_t bundle_size) {
    retro_set_environment(environment);
    retro_init();
    struct retro_game_info game = {NULL, bundle, bundle_size, NULL};
    assert(retro_load_game(&game));
    retro_unload_game();
    assert(retro_load_game(&game));
    retro_unload_game();
    assert(pixel_requests == 2u);
    /* Without a frontend log interface the adapter still loads and rejects. */
    assert(log_line_count == 0u);
    retro_deinit();

    /* Rejected loads emit one bounded generic line, keep no instance, and the
     * next valid load succeeds (D-05, MEDIA-04). */
    log_interface_offered = true;
    retro_set_environment(environment);
    retro_init();
    uint8_t *mutated = (uint8_t *)malloc(bundle_size);
    assert(mutated != NULL);

    struct retro_game_info truncated = {NULL, bundle, bundle_size - 100u, NULL};
    assert(!retro_load_game(&truncated));
    expect_one_log_line("glueyneo: MVS bundle rejected: malformed");
    assert(retro_load_game(&game));
    expect_one_log_line("glueyneo: MVS bundle loaded");
    /* RetroArch probes metadata on the already-loaded core, then restores
     * its real environment callback while environment requests are ignored.
     * Neither setter call may discard the initialized runtime logger. */
    log_interface_offered = false;
    retro_set_environment(environment);
    retro_set_environment(environment);
    log_interface_offered = true;
    retro_unload_game();
    assert(log_line_count == 0u);

    memcpy(mutated, bundle, bundle_size);
    mutated[7] = (uint8_t)(GN_MVS_MANIFEST_VERSION_ZOOM + 1u);
    struct retro_game_info wrong_version = {NULL, mutated, bundle_size, NULL};
    assert(!retro_load_game(&wrong_version));
    expect_one_log_line("glueyneo: MVS bundle rejected: unsupported profile");
    assert(retro_load_game(&game));
    expect_one_log_line("glueyneo: MVS bundle loaded");
    retro_unload_game();

    memcpy(mutated, bundle, bundle_size);
    mutated[7] = (uint8_t)GN_MVS_MANIFEST_VERSION_LEGACY;
    mutated[15] = (uint8_t)GN_MVS_LEGACY_REGIONS;
    struct retro_game_info missing_audio_bios = {
        NULL, mutated, bundle_size - 12u - GN_MVS_AUDIO_BIOS_BYTES, NULL};
    assert(!retro_load_game(&missing_audio_bios));
    expect_one_log_line("glueyneo: MVS bundle rejected: missing audio BIOS");
    assert(retro_load_game(&game));
    expect_one_log_line("glueyneo: MVS bundle loaded");
    retro_unload_game();

    memcpy(mutated, bundle, bundle_size);
    mutated[19u] = 99u; /* first region role is not a known MVS role */
    struct retro_game_info wrong_role = {NULL, mutated, bundle_size, NULL};
    assert(!retro_load_game(&wrong_role));
    expect_one_log_line("glueyneo: MVS bundle rejected: native load rejected");
    assert(retro_load_game(&game));
    expect_one_log_line("glueyneo: MVS bundle loaded");

    /* A second load while an instance is held is refused silently and does
     * not disturb the loaded instance. */
    assert(!retro_load_game(&truncated));
    assert(log_line_count == 0u);
    retro_unload_game();

    size_t zoom_bundle_size = 0u;
    uint8_t *zoom_bundle = make_adapter_zoom_bundle(bundle, bundle_size,
                                                     &zoom_bundle_size);
    struct retro_game_info zoom_game = {
        NULL, zoom_bundle, zoom_bundle_size, NULL};
    assert(retro_load_game(&zoom_game));
    expect_one_log_line("glueyneo: MVS bundle loaded");
    retro_unload_game();

    uint8_t *malformed_zoom = (uint8_t *)malloc(zoom_bundle_size);
    assert(malformed_zoom != NULL);
    memcpy(malformed_zoom, zoom_bundle, zoom_bundle_size);
    malformed_zoom[15] = (uint8_t)(GN_MVS_V3_MAX_REGIONS + 1u);
    struct retro_game_info malformed_zoom_game = {
        NULL, malformed_zoom, zoom_bundle_size, NULL};
    assert(!retro_load_game(&malformed_zoom_game));
    expect_one_log_line("glueyneo: MVS bundle rejected: unsupported profile");
    assert(retro_load_game(&zoom_game));
    expect_one_log_line("glueyneo: MVS bundle loaded");
    retro_unload_game();

    memcpy(malformed_zoom, zoom_bundle, zoom_bundle_size);
    malformed_zoom[15] = (uint8_t)(GN_MVS_V3_MAX_REGIONS - 1u);
    assert(!retro_load_game(&malformed_zoom_game));
    expect_one_log_line("glueyneo: MVS bundle rejected: malformed");
    assert(retro_load_game(&zoom_game));
    expect_one_log_line("glueyneo: MVS bundle loaded");
    retro_unload_game();

    free(malformed_zoom);
    free(zoom_bundle);
    check_mvs_adapter_start_response(bundle, bundle_size);
    check_mvs_adapter_right_guest_pixels(bundle, bundle_size);
    check_mvs_adapter_composition(bundle, bundle_size);
    check_content_cadence(bundle, bundle_size);
    retro_deinit();
    free(mutated);
    log_interface_offered = false;
    log_line_count = 0u;
}

/* Board behavior (plan 05-10, D-07). Each case group is a synthetic, rights-clear
 * guest that exercises one demanded board behavior from emulated time, with a
 * wrong-behavior control. Constants below are recomputed here from the cited
 * pinned MAME values (docs/mvs-media.md "Interrupts and timing"), not read back
 * from the implementation: 384x264 pixels at a 6 MHz pixel clock is 768 68000
 * clocks per line and 202,752 per frame; VBlank sets 240 lines plus 58 master
 * clocks (29 CPU clocks) into the frame. */
#define BB_LINE_CYCLES UINT64_C(768)
#define BB_FRAME_CYCLES (UINT64_C(264) * BB_LINE_CYCLES)
#define BB_FIRST_VBLANK (UINT64_C(240) * BB_LINE_CYCLES + UINT64_C(29))
#define BB_COUNTER UINT32_C(0x00100100)
#define BB_REG_IRQACK UINT32_C(0x003c000c)

static uint8_t *emit_stop_sr(uint8_t *at, uint16_t sr) {
    return emit16(emit16(at, 0x4e72u), sr);
}

/* Level-1 VBlank handler counting entries in D3 and a work-RAM long. The
 * acknowledge value is a parameter so controls can omit or misdirect it. A
 * negative value means no acknowledge write at all. */
static void build_irq_guest(guest_media *media, uint16_t main_sr, int ack_value) {
    const uint8_t vector[] = {0x00u, 0xc0u, 0x02u, 0x00u};   /* handler 0xc00200 */
    memcpy(media->bios + 0x64u, vector, sizeof(vector));      /* vector 25 = level 1 */
    uint8_t *code = emit_move_to_sr(media->bios + 0x100u, main_sr);
    uint8_t *stop_at = code;
    code = emit_stop_sr(code, main_sr);
    emit_jmp(code, UINT32_C(0xc00000) + (uint32_t)(stop_at - media->bios));
    code = emit16(media->bios + 0x200u, 0x5283u);              /* ADDQ.L #1,D3 */
    code = emit16(code, 0x23c3u);                              /* MOVE.L D3,(abs).L */
    code = emit32(code, BB_COUNTER);
    if (ack_value >= 0) code = emit_move_w_imm(code, (uint16_t)ack_value, BB_REG_IRQACK);
    emit16(code, 0x4e73u);                                     /* RTE */
}

static uint32_t bb_counter(const gn_instance *instance) {
    uint16_t low = 0u;
    assert(gn_test_mvs_read_work_ram(instance, BB_COUNTER + 2u, &low) == GN_STATUS_OK);
    return low;
}

static gn_instance *bb_start(guest_media *media) {
    gn_instance *instance = NULL;
    assert(gn_create(&instance) == GN_STATUS_OK);
    assert(gn_load_mvs(instance, &media->manifest) == GN_STATUS_OK);
    return instance;
}

static void bb_run(gn_instance *instance, uint64_t cycles) {
    gn_run_result run;
    run_mvs_in_bounded_chunks(instance, cycles, &run);
    assert(run.reason != GN_RUN_FAULT && run.reason != GN_RUN_ERROR);
}

static uint64_t bb_interrupts_taken(const gn_instance *instance) {
    gn_mvs_stall_diagnosis diagnosis;
    assert(gn_private_mvs_stall_diagnosis(instance, &diagnosis) == GN_STATUS_OK);
    return diagnosis.interrupts_taken;
}

static void check_irq_timing(const uint8_t *bundle, size_t size) {
    guest_media media;
    gn_instance *instance;

    /* Positive: four acknowledged VBlank entries inside four full frames of
     * emulated time, none before the documented boundary, and the guest-taken
     * entries are visible in the diagnosis. */
    open_guest_media(bundle, size, &media);
    build_irq_guest(&media, 0x2000u, 4);
    instance = bb_start(&media);
    bb_run(instance, BB_FIRST_VBLANK - UINT64_C(1));
    assert(bb_counter(instance) == 0u && bb_interrupts_taken(instance) == 0u);
    /* The source sets exactly at the boundary clock; the 68000 enters the
     * handler at the following instruction boundary, one clock later here. */
    bb_run(instance, UINT64_C(1));
    assert(bb_interrupts_taken(instance) == 0u);
    bb_run(instance, UINT64_C(1));
    assert(bb_interrupts_taken(instance) == 1u);
    bb_run(instance, UINT64_C(2000));
    assert(bb_counter(instance) == 1u && bb_interrupts_taken(instance) == 1u);
    bb_run(instance, BB_FRAME_CYCLES * 3u);
    assert(bb_counter(instance) == 4u && bb_interrupts_taken(instance) == 4u);
    gn_destroy(instance);

    /* Control: mask 7 never enters the handler, however many frames pass. */
    open_guest_media(bundle, size, &media);
    build_irq_guest(&media, 0x2700u, 4);
    instance = bb_start(&media);
    bb_run(instance, BB_FIRST_VBLANK + BB_FRAME_CYCLES * 3u);
    assert(bb_counter(instance) == 0u && bb_interrupts_taken(instance) == 0u);
    gn_destroy(instance);
    free(media.copy);

    /* Control: a handler that never acknowledges is re-entered while the
     * level-sensitive source stays pending (an interrupt storm bounded by the
     * cycle budget); the acknowledging handler enters exactly once in the same
     * window. A misdirected acknowledge (IRQ3 and raster bits only) behaves the
     * same as none. */
    const int ack_values[] = {-1, 3};
    for (size_t index = 0u; index < sizeof(ack_values) / sizeof(ack_values[0]); ++index) {
        open_guest_media(bundle, size, &media);
        build_irq_guest(&media, 0x2000u, ack_values[index]);
        instance = bb_start(&media);
        bb_run(instance, BB_FIRST_VBLANK + UINT64_C(3000));
        assert(bb_counter(instance) >= 10u);
        /* The run may end between an entry and its first handler instruction. */
        assert(bb_interrupts_taken(instance) - bb_counter(instance) <= 1u);
        gn_destroy(instance);
        free(media.copy);
    }
    open_guest_media(bundle, size, &media);
    build_irq_guest(&media, 0x2000u, 4);
    instance = bb_start(&media);
    bb_run(instance, BB_FIRST_VBLANK + UINT64_C(3000));
    assert(bb_counter(instance) == 1u);
    gn_destroy(instance);

    /* Reset restarts the frame phase: after running into the second frame, a
     * reset followed by less than one first-VBlank distance raises nothing. */
    instance = bb_start(&media);
    bb_run(instance, BB_FIRST_VBLANK + UINT64_C(100000));
    assert(bb_counter(instance) == 1u);
    assert(gn_reset(instance) == GN_STATUS_OK);
    bb_run(instance, UINT64_C(150000));
    assert(bb_counter(instance) == 0u && bb_interrupts_taken(instance) == 0u);
    bb_run(instance, BB_FIRST_VBLANK - UINT64_C(150000) + UINT64_C(2000));
    assert(bb_counter(instance) == 1u);
    gn_destroy(instance);

    /* Two instances stepped in different slice sizes keep identical, independent
     * counts, and a third masked instance in the middle never leaks into them. */
    guest_media masked;
    open_guest_media(bundle, size, &masked);
    build_irq_guest(&masked, 0x2700u, 4);
    gn_instance *a = bb_start(&media);
    gn_instance *b = bb_start(&media);
    gn_instance *c = bb_start(&masked);
    const uint64_t total = BB_FIRST_VBLANK + BB_FRAME_CYCLES * 2u + UINT64_C(2000);
    uint64_t done_a = 0u, done_b = 0u, done_c = 0u;
    while (done_a < total || done_b < total || done_c < total) {
        uint64_t slice = total - done_a < UINT64_C(5000) ? total - done_a : UINT64_C(5000);
        if (slice != 0u) { bb_run(a, slice); done_a += slice; }
        slice = total - done_b < UINT64_C(12347) ? total - done_b : UINT64_C(12347);
        if (slice != 0u) { bb_run(b, slice); done_b += slice; }
        slice = total - done_c < UINT64_C(1999) ? total - done_c : UINT64_C(1999);
        if (slice != 0u) { bb_run(c, slice); done_c += slice; }
    }
    assert(bb_counter(a) == 3u && bb_counter(b) == 3u && bb_counter(c) == 0u);
    assert(bb_interrupts_taken(a) == 3u && bb_interrupts_taken(b) == 3u &&
           bb_interrupts_taken(c) == 0u);
    gn_destroy(a);
    gn_destroy(b);
    gn_destroy(c);
    free(masked.copy);
    free(media.copy);
}

/* Input and status registers (plan 05-12, D-07). The selected boot polls the
 * REG_DIPSW byte at $300001. Pinned MAME 31e52312 neogeo.cpp lines 1814-1836
 * (DSW port: every switch default is its Off/Normal position, 0xff) with
 * ngarcade_base_state::in0_edge_r lines 899-902 (the low byte of the word read
 * at $300000 is m_dsw->read()) and the 0x01ff7e mirror at machine_start line
 * 1581-1583; the NeoGeo Development Wiki "Memory mapped registers" oldid 9288
 * gives REG_DIPSW at $300001, decode mask $FE0081, active low. The test program
 * bytes at the cartridge-window offsets of these addresses are nonzero and
 * different from 0xff, so a read still served from program bytes fails. */
static uint8_t io_status_byte(const gn_instance *instance, uint32_t address) {
    uint8_t value = 0u;
    assert(gn_test_mvs_read_bus8(instance, address, &value) == GN_STATUS_OK);
    return value;
}

static void assert_p1_control_bus(const gn_instance *instance,
                                  uint8_t expected_control) {
    const uint16_t expected_word = (uint16_t)(
        ((uint16_t)expected_control << 8) | UINT16_C(0x00ff));
    const uint32_t byte_addresses[] = {
        UINT32_C(0x00300000), UINT32_C(0x0031ff7e),
        UINT32_C(0x00300001), UINT32_C(0x0031ff7f)};
    const uint8_t expected_bytes[] = {
        expected_control, expected_control, UINT8_C(0xff), UINT8_C(0xff)};
    for (size_t index = 0u; index < sizeof(byte_addresses) / sizeof(byte_addresses[0]);
         ++index) {
        assert(io_status_byte(instance, byte_addresses[index]) ==
               expected_bytes[index]);
    }
    uint16_t value = 0u;
    assert(gn_test_mvs_read_bus(instance, UINT32_C(0x00300000), &value) ==
           GN_STATUS_OK);
    assert(value == expected_word);
    assert(gn_test_mvs_read_bus(instance, UINT32_C(0x0031ff7e), &value) ==
           GN_STATUS_OK);
    assert(value == expected_word);
}

static void check_mvs_p1_guest_held_case(const uint8_t *bundle, size_t size,
                                         uint32_t input_mask,
                                         uint8_t expected_control) {
    static const uint32_t byte_addresses[] = {
        UINT32_C(0x00300000), UINT32_C(0x0031ff7e)};
    static const uint32_t word_addresses[] = {
        UINT32_C(0x00300000), UINT32_C(0x0031ff7e)};
    guest_media media;
    open_guest_media(bundle, size, &media);
    const uint16_t expected_word = (uint16_t)(
        ((uint16_t)expected_control << 8) | UINT16_C(0x00ff));
    uint8_t *code = emit_move_b_imm(media.bios + 0x100u, UINT8_C(0x5a),
                                    UINT32_C(0x00100000));
    code = emit16(emit16(code, UINT16_C(0x46fc)), UINT16_C(0x2700));
    uint8_t *loop = code;
    uint8_t *failure_branches[4];
    size_t branch_index = 0u;
    for (size_t index = 0u;
         index < sizeof(byte_addresses) / sizeof(byte_addresses[0]); ++index) {
        code = emit_move_b_from(code, byte_addresses[index]);
        code = emit16(emit16(code, UINT16_C(0x0c00)), expected_control);
        failure_branches[branch_index++] = code;
        code = emit16(code, UINT16_C(0x6600));
    }
    for (size_t index = 0u;
         index < sizeof(word_addresses) / sizeof(word_addresses[0]); ++index) {
        code = emit_move_w_from(code, word_addresses[index]);
        code = emit16(emit16(code, UINT16_C(0x0c40)), expected_word);
        failure_branches[branch_index++] = code;
        code = emit16(code, UINT16_C(0x6600));
    }
    uint8_t *loop_branch = code;
    code = emit16(code, UINT16_C(0x6000));
    uint8_t *failure = code;
    code = emit_move_b_imm(code, 0u, UINT32_C(0x00100000));
    emit_stop(code);
    for (size_t index = 0u; index < branch_index; ++index) {
        const ptrdiff_t displacement = failure - (failure_branches[index] + 2u);
        assert(displacement >= -128 && displacement <= 127);
        failure_branches[index][1] = (uint8_t)displacement;
    }
    const ptrdiff_t loop_displacement = loop - (loop_branch + 2u);
    assert(loop_displacement >= -128 && loop_displacement <= 127);
    loop_branch[1] = (uint8_t)loop_displacement;

    gn_instance *instance = bb_start(&media);
    assert(gn_set_mvs_inputs(instance, input_mask) == GN_STATUS_OK);
    for (unsigned frame = 0u; frame < 3u; ++frame) {
        gn_run_result run;
        assert(gn_run_mvs(instance, UINT64_C(202752), &run) == GN_STATUS_OK);
        assert(run.reason == GN_RUN_BUDGET);
    }
    uint8_t marker = 0u;
    assert(gn_test_mvs_read_bus8(instance, UINT32_C(0x00100000), &marker) ==
           GN_STATUS_OK);
    assert(marker == UINT8_C(0x5a));
    assert_p1_control_bus(instance, expected_control);
    assert(io_status_byte(instance, UINT32_C(0x00320001)) == UINT8_C(0x1f));
    assert(io_status_byte(instance, UINT32_C(0x00380000)) == UINT8_C(0xff));
    gn_destroy(instance);
    free(media.copy);
}

static void check_mvs_p1_control_boundaries(const uint8_t *bundle, size_t size) {
    static const struct {
        uint32_t mask;
        uint8_t control;
    } cases[] = {
        {GN_MVS_INPUT_P1_UP, UINT8_C(0xfe)},
        {GN_MVS_INPUT_P1_DOWN, UINT8_C(0xfd)},
        {GN_MVS_INPUT_P1_LEFT, UINT8_C(0xfb)},
        {GN_MVS_INPUT_P1_RIGHT, UINT8_C(0xf7)},
        {GN_MVS_INPUT_P1_A, UINT8_C(0xef)},
        {GN_MVS_INPUT_P1_B, UINT8_C(0xdf)},
        {GN_MVS_INPUT_P1_C, UINT8_C(0xbf)},
        {GN_MVS_INPUT_P1_D, UINT8_C(0x7f)},
        {GN_MVS_INPUT_P1_UP | GN_MVS_INPUT_P1_A | GN_MVS_INPUT_P1_D,
         UINT8_C(0x6e)},
        {GN_MVS_INPUT_P1_LEFT | GN_MVS_INPUT_P1_RIGHT, UINT8_C(0xf3)},
        {GN_MVS_INPUT_P1_UP | GN_MVS_INPUT_P1_DOWN |
             GN_MVS_INPUT_P1_LEFT | GN_MVS_INPUT_P1_RIGHT,
         UINT8_C(0xf0)},
        {GN_MVS_INPUT_P1_UP | GN_MVS_INPUT_P1_DOWN |
             GN_MVS_INPUT_P1_LEFT | GN_MVS_INPUT_P1_RIGHT |
             GN_MVS_INPUT_P1_A | GN_MVS_INPUT_P1_B |
             GN_MVS_INPUT_P1_C | GN_MVS_INPUT_P1_D,
         UINT8_C(0x00)}
    };
    assert(GN_MVS_INPUT_COIN1 == UINT32_C(0x00000001));
    assert(GN_MVS_INPUT_P1_START == UINT32_C(0x00000002));
    assert(GN_MVS_INPUT_SUPPORTED_MASK == UINT32_C(0x000003ff));
    for (size_t index = 0u; index < sizeof(cases) / sizeof(cases[0]); ++index)
        check_mvs_p1_guest_held_case(bundle, size, cases[index].mask,
                                     cases[index].control);

    guest_media media;
    open_guest_media(bundle, size, &media);
    gn_instance *first = bb_start(&media);
    gn_instance *second = bb_start(&media);
    assert(gn_set_mvs_inputs(first,
        GN_MVS_INPUT_P1_UP | GN_MVS_INPUT_P1_B) == GN_STATUS_OK);
    assert(gn_set_mvs_inputs(second,
        GN_MVS_INPUT_P1_RIGHT | GN_MVS_INPUT_P1_A) == GN_STATUS_OK);
    assert_p1_control_bus(first, UINT8_C(0xde));
    assert_p1_control_bus(second, UINT8_C(0xe7));
    assert(gn_set_mvs_inputs(first, UINT32_C(0x80000000)) ==
           GN_STATUS_INVALID_ARGUMENT);
    assert_p1_control_bus(first, UINT8_C(0xde));
    assert(gn_set_mvs_inputs(first, 0u) == GN_STATUS_OK);
    assert_p1_control_bus(first, UINT8_C(0xff));

    /* A successful reset, load and unload/reload each begin with released P1.
     * An invalid candidate load leaves the live instance and its held state. */
    assert(gn_reset(first) == GN_STATUS_OK);
    assert_p1_control_bus(first, UINT8_C(0xff));
    assert(gn_set_mvs_inputs(first, GN_MVS_INPUT_P1_LEFT) == GN_STATUS_OK);
    gn_mvs_manifest invalid_manifest = media.manifest;
    invalid_manifest.region_count = 0u;
    assert(gn_load_mvs(first, &invalid_manifest) == GN_STATUS_INVALID_MEDIA);
    assert_p1_control_bus(first, UINT8_C(0xfb));
    assert(gn_load_mvs(first, &media.manifest) == GN_STATUS_OK);
    assert_p1_control_bus(first, UINT8_C(0xff));
    assert_p1_control_bus(second, UINT8_C(0xe7));
    assert(gn_set_mvs_inputs(first, GN_MVS_INPUT_P1_C) == GN_STATUS_OK);
    assert(gn_unload(first) == GN_STATUS_OK);
    assert(gn_set_mvs_inputs(first, 0u) == GN_STATUS_INVALID_STATE);
    assert(gn_load_mvs(first, &media.manifest) == GN_STATUS_OK);
    assert_p1_control_bus(first, UINT8_C(0xff));
    assert_p1_control_bus(second, UINT8_C(0xe7));
    gn_destroy(first);
    gn_destroy(second);
    free(media.copy);
}

static void check_io_status(const uint8_t *bundle, size_t size) {
    guest_media media;
    open_guest_media(bundle, size, &media);
    media.program[UINT32_C(0x100001)] = 0x5au;
    media.program[UINT32_C(0x100003)] = 0x5au;
    media.program[UINT32_C(0x11ff7f)] = 0x5au;
    media.program[UINT32_C(0x100081)] = 0x77u;
    media.program[UINT32_C(0x100000)] = 0x33u;
    media.program[UINT32_C(0x140001)] = 0x44u;
    gn_instance *a = bb_start(&media);
    gn_instance *b = bb_start(&media);

    /* REG_DIPSW: the cited default configuration (all switches off, active low
     * so 0xff) at $300001 and at every mirror the 0x01ff7e mask names. */
    assert(io_status_byte(a, UINT32_C(0x300001)) == 0xffu);
    assert(io_status_byte(a, UINT32_C(0x300003)) == 0xffu);
    assert(io_status_byte(a, UINT32_C(0x310001)) == 0xffu);
    assert(io_status_byte(a, UINT32_C(0x31ff7f)) == 0xffu);
    /* Deterministic and per instance: repeated reads, a second instance and a
     * reset return the same value, and no read mutates observable state. */
    assert(io_status_byte(a, UINT32_C(0x300001)) == 0xffu);
    assert(io_status_byte(b, UINT32_C(0x300001)) == 0xffu);
    assert(gn_reset(a) == GN_STATUS_OK);
    assert(io_status_byte(a, UINT32_C(0x300001)) == 0xffu);

    /* The TEST port is a separate MAME decode (S20c). S20d declares active-
     * high unused bits 0-5, a custom JAMMA sense bit with no callback, and an
     * active-low service input; for released inputs the low byte is 0x80.
     * This is reference-emulator default behavior, not a physical-board claim. */
    assert(io_status_byte(a, UINT32_C(0x300081)) == 0x80u);
    assert(io_status_byte(a, UINT32_C(0x300083)) == 0x80u);
    assert(io_status_byte(a, UINT32_C(0x310081)) == 0x80u);
    assert(io_status_byte(a, UINT32_C(0x31ffff)) == 0x80u);
    assert(io_status_byte(a, UINT32_C(0x300081)) == 0x80u);
    assert(io_status_byte(b, UINT32_C(0x300081)) == 0x80u);
    assert(gn_reset(a) == GN_STATUS_OK);
    assert(io_status_byte(a, UINT32_C(0x300081)) == 0x80u);

    /* No blanket default: reads of other I/O addresses still fault and are
     * recorded, even where cartridge program bytes exist at the old window
     * offsets. $300080 is the unobserved high-byte lane of TEST and $380001
     * is not implemented here. */
    const uint32_t not_implemented[] = {
        UINT32_C(0x300080), UINT32_C(0x380001)};
    for (size_t index = 0u; index < sizeof(not_implemented) / sizeof(not_implemented[0]);
         ++index) {
        gn_instance *fresh = bb_start(&media);
        uint8_t value = 0xa5u;
        assert(gn_test_mvs_read_bus8(fresh, not_implemented[index], &value) ==
               GN_STATUS_INVALID_MEDIA);
        gn_mvs_bus_fault_observation observation;
        assert(gn_observe_mvs_bus_fault(fresh, &observation, sizeof(observation)) ==
               GN_STATUS_OK);
        assert(observation.valid == 1u && observation.address == not_implemented[index] &&
               observation.access == GN_MVS_BUS_ACCESS_READ && observation.width == 1u);
        gn_destroy(fresh);
    }
    /* The P2 default is bank zero, whose cartridge base is the second
     * megabyte (MAME differential source S16d). */
    media.program[UINT32_C(0x1fffff)] = 0x6bu;
    gn_instance *window = bb_start(&media);
    assert(io_status_byte(window, UINT32_C(0x2fffff)) == 0x6bu);
    gn_destroy(window);
    gn_destroy(a);
    gn_destroy(b);
    free(media.copy);
}

/* MVS edge-connector controls (MAME neogeo.cpp machine_start,
 * in0_edge_joy_r/in1_edge_joy_r, pinned 31e52312). With no guest input
 * asserted, P1's control byte and DSW byte are both $ff; the empty P2 input is
 * likewise $ff on both byte lanes. This guest verifies the value it consumed
 * before recording a marker; host-side bus probes alone would not establish
 * instruction-to-board integration. */
static void check_mvs_controls_guest(const uint8_t *bundle, size_t size) {
    guest_media media;
    open_guest_media(bundle, size, &media);
    uint8_t *code = media.bios + 0x100u;
    uint8_t *branches[9];
    const uint32_t byte_addresses[] = {
        UINT32_C(0x00300000), UINT32_C(0x0031ff7e),
        UINT32_C(0x00340000), UINT32_C(0x00340001),
        UINT32_C(0x0035fffe), UINT32_C(0x0035ffff)};
    for (size_t index = 0u;
         index < sizeof(byte_addresses) / sizeof(byte_addresses[0]); ++index) {
        code = emit_move_b_from(code, byte_addresses[index]);
        code = emit16(emit16(code, UINT16_C(0x0c00)), UINT16_C(0x00ff));
        branches[index] = code;
        code = emit16(code, UINT16_C(0x6600)); /* BNE.s failure path, patched below. */
    }
    const uint32_t word_addresses[] = {
        UINT32_C(0x00300000), UINT32_C(0x0031ff7e), UINT32_C(0x00340000)};
    for (size_t index = 0u;
         index < sizeof(word_addresses) / sizeof(word_addresses[0]); ++index) {
        code = emit32(emit16(code, UINT16_C(0x3039)), word_addresses[index]);
        code = emit16(emit16(code, UINT16_C(0x0c40)), UINT16_C(0xffff));
        branches[6u + index] = code;
        code = emit16(code, UINT16_C(0x6600));
    }
    code = emit_move_b_imm(code, UINT8_C(0xa5), UINT32_C(0x00100000));
    code = emit_stop(code);
    uint8_t *failure = code;
    code = emit_move_b_imm(code, 0u, UINT32_C(0x00100000));
    emit_stop(code);
    for (size_t index = 0u; index < sizeof(branches) / sizeof(branches[0]);
         ++index) {
        const ptrdiff_t displacement = failure - (branches[index] + 2u);
        assert(displacement >= -128 && displacement <= 127);
        branches[index][1] = (uint8_t)displacement;
    }

    gn_instance *instance = bb_start(&media);
    gn_run_result run;
    assert(gn_run_mvs(instance, 1000u, &run) == GN_STATUS_OK);
    assert(run.reason == GN_RUN_STOPPED && run.instructions >= 29u);
    uint8_t marker = 0u;
    assert(gn_test_mvs_read_bus8(instance, UINT32_C(0x00100000), &marker) ==
           GN_STATUS_OK);
    assert(marker == UINT8_C(0xa5));
    gn_destroy(instance);
    free(media.copy);

    /* MAME maps this next block explicitly to unmapped_r; the owned core keeps
     * its fail-closed policy instead of treating unknown reads as port data. */
    guest_media unmapped;
    open_guest_media(bundle, size, &unmapped);
    (void)emit_move_b_from(unmapped.bios + 0x100u, UINT32_C(0x00360000));
    gn_instance *rejected = bb_start(&unmapped);
    assert(gn_run_mvs(rejected, 1000u, &run) == GN_STATUS_CPU_FAILURE);
    assert(run.reason == GN_RUN_ERROR);
    gn_mvs_bus_fault_observation fault;
    assert(gn_observe_mvs_bus_fault(rejected, &fault, sizeof(fault)) == GN_STATUS_OK);
    assert(fault.valid == 1u && fault.address == UINT32_C(0x00360000) &&
           fault.access == GN_MVS_BUS_ACCESS_READ && fault.width == 1u);
    gn_destroy(rejected);
    free(unmapped.copy);

    check_mvs_p1_control_boundaries(bundle, size);
}

/* uPD4990A calendar (plan 05-21 rerun 8, D-07). The selected boot writes the
 * calendar control byte at $380051 (the first fault after the owned encodings).
 * Pinned MAME 31e52312: neogeo.cpp ngarcade_base_state::io_control_w offset
 * 0x28 drives data_in (bit 0), clk (bit 1) and stb (bit 2) of the uPD4990A,
 * and machine_start holds cs, oe and c0-c2 high (serial mode); upd1990a.cpp
 * stb_w and clk_w define the command register, shift register and timers, with
 * a 32,768 Hz chip clock that is 366.2109375 CPU clocks per tick at 12 MHz.
 * The seed 2000-01-01 00:00:00 is the documented emulator choice, not
 * hardware and not host time. All constants below are recomputed here from the
 * cited values, not read back from the implementation. */
#define CAL_REG UINT32_C(0x00380051)
#define CAL_SECOND_CYCLES UINT64_C(12000000)
#define CAL_COUNTER UINT32_C(0x00100100)
enum { CAL_REG_HOLD = 0, CAL_SHIFT = 1, CAL_TIME_SET = 2, CAL_TIME_READ = 3,
       CAL_TP_64HZ = 4, CAL_TEST = 15 };
static const uint8_t cal_epoch[6] = {0x00u, 0x00u, 0x00u, 0x01u, 0x10u, 0x00u};

static gn_status cal_put(gn_instance *instance, unsigned data, unsigned clk,
                         unsigned stb) {
    return gn_test_mvs_write_bus8(instance, CAL_REG,
                                  (uint8_t)(data | (clk << 1) | (stb << 2)));
}

static void cal_clock_bit(gn_instance *instance, unsigned bit) {
    assert(cal_put(instance, bit, 0u, 0u) == GN_STATUS_OK);
    assert(cal_put(instance, bit, 1u, 0u) == GN_STATUS_OK);
    assert(cal_put(instance, bit, 0u, 0u) == GN_STATUS_OK);
}

/* Four command bits, least significant first, then the strobe pulse. Returns
 * the status of the strobe-rising write, which carries the command. */
static gn_status cal_command(gn_instance *instance, unsigned command) {
    for (unsigned bit = 0u; bit < 4u; ++bit) cal_clock_bit(instance, (command >> bit) & 1u);
    const gn_status strobe = cal_put(instance, 0u, 0u, 1u);
    assert(cal_put(instance, 0u, 0u, 0u) == GN_STATUS_OK);
    return strobe;
}

static gn_mvs_calendar cal_state(const gn_instance *instance) {
    gn_mvs_calendar state;
    assert(gn_test_mvs_calendar(instance, &state) == GN_STATUS_OK);
    return state;
}

/* Compare every defined field: structure assignment may leave padding bytes
 * unspecified, so object-representation equality is not a state invariant. */
static void assert_calendar_equal(const gn_mvs_calendar *before,
                                  const gn_mvs_calendar *after) {
    assert(memcmp(before->time_counter, after->time_counter,
                  sizeof(before->time_counter)) == 0);
    assert(memcmp(before->shift_reg, after->shift_reg,
                  sizeof(before->shift_reg)) == 0);
    assert(before->data_in == after->data_in);
    assert(before->clk == after->clk);
    assert(before->stb == after->stb);
    assert(before->command == after->command);
    assert(before->data_out == after->data_out);
    assert(before->tp == after->tp);
    assert(before->clock_running == after->clock_running);
    assert(before->data_out_running == after->data_out_running);
    assert(before->tp_running == after->tp_running);
    assert(before->tick_remainder == after->tick_remainder);
    assert(before->clock_remaining == after->clock_remaining);
    assert(before->data_out_remaining == after->data_out_remaining);
    assert(before->data_out_period == after->data_out_period);
    assert(before->tp_remaining == after->tp_remaining);
    assert(before->tp_period == after->tp_period);
}

/* Idle guest: SR 0x2700, STOP. Runs reach the STOP within a few clocks. */
static gn_instance *cal_start_idle(guest_media *media, const uint8_t *bundle,
                                   size_t size) {
    open_guest_media(bundle, size, media);
    uint8_t *code = emit_move_to_sr(media->bios + 0x100u, 0x2700u);
    emit_stop_sr(code, 0x2700u);
    return bb_start(media);
}

static uint64_t cal_run(gn_instance *instance, uint64_t cycles) {
    gn_run_result run;
    uint64_t elapsed = 0u;
    while (cycles != 0u) {
        const uint64_t chunk = cycles > GN_MAX_CYCLE_BUDGET ? GN_MAX_CYCLE_BUDGET : cycles;
        assert(gn_run_mvs(instance, chunk, &run) == GN_STATUS_OK);
        assert(run.reason != GN_RUN_FAULT && run.reason != GN_RUN_ERROR);
        elapsed += run.elapsed_cycles;
        cycles -= chunk;
    }
    return elapsed;
}

static void check_calendar(const uint8_t *bundle, size_t size) {
    guest_media media;

    /* The guest-visible demand: a 68000 program writes the control byte three
     * times (data high, clock rising, clock falling) and keeps running. The
     * write is no longer a bus fault, and one clock edge moved the data bit
     * into the serial command register (bit 3 of the 4-bit register). */
    open_guest_media(bundle, size, &media);
    uint8_t *code = emit_move_to_sr(media.bios + 0x100u, 0x2700u);
    code = emit_move_b_imm(code, 0x01u, CAL_REG);
    code = emit_move_b_imm(code, 0x03u, CAL_REG);
    code = emit_move_b_imm(code, 0x01u, CAL_REG);
    code = emit_move_w_imm(code, 0x1234u, CAL_COUNTER);
    emit_stop_sr(code, 0x2700u);
    gn_instance *instance = bb_start(&media);
    bb_run(instance, UINT64_C(400));
    gn_mvs_bus_fault_observation fault;
    assert(gn_observe_mvs_bus_fault(instance, &fault, sizeof(fault)) == GN_STATUS_OK);
    assert(fault.valid == 0u);
    uint16_t counter = 0u;
    assert(gn_test_mvs_read_work_ram(instance, CAL_COUNTER, &counter) == GN_STATUS_OK);
    assert(counter == 0x1234u);
    assert(cal_state(instance).shift_reg[6] == 0x08u);
    gn_destroy(instance);
    free(media.copy);

    /* Power-on seed, two identical instances, and a strobe-less command that
     * leaves the latched command untouched (wrong-behavior control). */
    instance = cal_start_idle(&media, bundle, size);
    gn_instance *other = bb_start(&media);
    gn_mvs_calendar state = cal_state(instance);
    assert(memcmp(state.time_counter, cal_epoch, sizeof(cal_epoch)) == 0);
    assert(state.command == 0u && state.stb == 0u && state.clk == 0u);
    assert(memcmp(cal_state(other).time_counter, cal_epoch, sizeof(cal_epoch)) == 0);
    for (unsigned bit = 0u; bit < 4u; ++bit) cal_clock_bit(instance, (CAL_TIME_READ >> bit) & 1u);
    state = cal_state(instance);
    assert(state.shift_reg[6] == CAL_TIME_READ && state.command == 0u);
    assert(cal_state(other).shift_reg[6] == 0u);

    /* TIME READ then SHIFT presents the 48 time bits, least significant
     * first, on data out; the seed is read back. */
    assert(cal_put(instance, 0u, 0u, 1u) == GN_STATUS_OK);
    assert(cal_put(instance, 0u, 0u, 0u) == GN_STATUS_OK);
    assert(cal_state(instance).command == CAL_TIME_READ);
    assert(cal_command(instance, CAL_SHIFT) == GN_STATUS_OK);
    uint8_t bytes[6] = {0};
    for (unsigned bit = 0u; bit < 48u; ++bit) {
        bytes[bit / 8u] |= (uint8_t)(cal_state(instance).data_out << (bit % 8u));
        assert(cal_put(instance, 0u, 1u, 0u) == GN_STATUS_OK);
        assert(cal_put(instance, 0u, 0u, 0u) == GN_STATUS_OK);
    }
    assert(memcmp(bytes, cal_epoch, sizeof(cal_epoch)) == 0);
    gn_destroy(other);

    /* The mirror of the control byte is the same register; the even byte, the
     * read direction and the 16-bit window are still faults (no blanket
     * default). */
    assert(gn_test_mvs_write_bus8(instance, UINT32_C(0x39ff51), 0x01u) == GN_STATUS_OK);
    assert(cal_state(instance).data_in == 1u);
    assert(gn_test_mvs_write_bus8(instance, CAL_REG, 0x00u) == GN_STATUS_OK);
    gn_instance *fresh = cal_start_idle(&media, bundle, size);
    const gn_mvs_calendar before = cal_state(fresh);
    assert(gn_test_mvs_write_bus8(fresh, UINT32_C(0x380050), 0x07u) == GN_STATUS_INVALID_MEDIA);
    gn_mvs_bus_fault_observation even_fault;
    assert(gn_observe_mvs_bus_fault(fresh, &even_fault, sizeof(even_fault)) == GN_STATUS_OK);
    assert(even_fault.valid == 1u && even_fault.address == UINT32_C(0x380050) &&
           even_fault.access == GN_MVS_BUS_ACCESS_WRITE && even_fault.width == 1u);
    const gn_mvs_calendar after = cal_state(fresh);
    assert_calendar_equal(&before, &after);
    gn_destroy(fresh);
    uint8_t byte = 0u;
    assert(gn_test_mvs_read_bus8(instance, CAL_REG, &byte) == GN_STATUS_INVALID_MEDIA);
    gn_destroy(instance);

    /* TIME SET loads the 48 shifted bits (the serial protocol feeds the main
     * register through the 4-bit command register, so 52 clocks) and stops the
     * counter; the loaded value reads back through TIME READ and SHIFT. */
    instance = cal_start_idle(&media, bundle, size);
    static const uint8_t set_time[6] = {0x56u, 0x34u, 0x12u, 0x28u, 0x72u, 0x24u};
    assert(cal_command(instance, CAL_SHIFT) == GN_STATUS_OK);
    for (unsigned bit = 0u; bit < 48u; ++bit)
        cal_clock_bit(instance, (set_time[bit / 8u] >> (bit % 8u)) & 1u);
    for (unsigned bit = 0u; bit < 4u; ++bit)
        cal_clock_bit(instance, (CAL_TIME_SET >> bit) & 1u);
    assert(cal_put(instance, 0u, 0u, 1u) == GN_STATUS_OK);
    assert(cal_put(instance, 0u, 0u, 0u) == GN_STATUS_OK);
    state = cal_state(instance);
    assert(state.command == CAL_TIME_SET && state.clock_running == 0u);
    assert(memcmp(state.time_counter, set_time, sizeof(set_time)) == 0);
    cal_run(instance, UINT64_C(3) * CAL_SECOND_CYCLES);
    assert(memcmp(cal_state(instance).time_counter, set_time, sizeof(set_time)) == 0);
    assert(cal_command(instance, CAL_TIME_READ) == GN_STATUS_OK);
    assert(cal_state(instance).clock_running == 1u);
    gn_destroy(instance);

    /* TEST mode is not modeled: the strobe that selects it is a recorded
     * fault, not a silent sink. */
    instance = cal_start_idle(&media, bundle, size);
    assert(cal_command(instance, CAL_TEST) == GN_STATUS_INVALID_MEDIA);
    gn_mvs_bus_fault_observation test_fault;
    assert(gn_observe_mvs_bus_fault(instance, &test_fault, sizeof(test_fault)) ==
           GN_STATUS_OK);
    assert(test_fault.valid == 1u && test_fault.address == CAL_REG &&
           test_fault.access == GN_MVS_BUS_ACCESS_WRITE && test_fault.width == 1u);
    gn_destroy(instance);
    free(media.copy);
}

static void check_calendar_timing(const uint8_t *bundle, size_t size) {
    guest_media media;
    gn_instance *instance = cal_start_idle(&media, bundle, size);
    gn_instance *untouched = bb_start(&media);

    /* The counter runs from power-on: one second is 12,000,000 emulated
     * clocks (32,768 chip ticks at 12 MHz), not one clock earlier. */
    uint64_t total = cal_run(instance, UINT64_C(1000));
    total += cal_run(instance, CAL_SECOND_CYCLES - UINT64_C(1) - total);
    assert(total == CAL_SECOND_CYCLES - UINT64_C(1));
    assert(cal_state(instance).time_counter[0] == 0x00u);
    total += cal_run(instance, UINT64_C(1));
    assert(cal_state(instance).time_counter[0] == 0x01u);
    /* Carry into minutes after 60 seconds. */
    total += cal_run(instance, UINT64_C(59) * CAL_SECOND_CYCLES);
    gn_mvs_calendar state = cal_state(instance);
    assert(total == UINT64_C(60) * CAL_SECOND_CYCLES);
    assert(state.time_counter[0] == 0x00u && state.time_counter[1] == 0x01u);
    /* An instance that never ran keeps the seed. */
    assert(memcmp(cal_state(untouched).time_counter, cal_epoch, sizeof(cal_epoch)) == 0);
    gn_destroy(untouched);

    /* REGISTER HOLD starts the 64 Hz time pulse and the 1 Hz data-out pulse;
     * each output toggles once at the command, then after every half period of
     * 256 and 16,384 chip ticks. The chip ticks free-run at 32,768 Hz against
     * the 12 MHz clock, so the first expiry after the command is the smallest
     * clock count whose tick total is the command's tick total plus the half
     * period; recomputed here with integer arithmetic, not read back. */
    assert(gn_reset(instance) == GN_STATUS_OK);
    total = cal_run(instance, UINT64_C(1000));
    const uint64_t ticks_at_command = total * UINT64_C(128) / UINT64_C(46875);
    assert(cal_command(instance, CAL_REG_HOLD) == GN_STATUS_OK);
    state = cal_state(instance);
    assert(state.tp == 1u && state.data_out == 1u);
    const uint64_t tp_delta =
        ((ticks_at_command + UINT64_C(256)) * UINT64_C(46875) + UINT64_C(127)) /
            UINT64_C(128) - total;
    const uint64_t data_delta =
        ((ticks_at_command + UINT64_C(16384)) * UINT64_C(46875) + UINT64_C(127)) /
            UINT64_C(128) - total;
    assert(tp_delta >= UINT64_C(93000) && tp_delta <= UINT64_C(93750));
    cal_run(instance, tp_delta - UINT64_C(1));
    assert(cal_state(instance).tp == 1u);
    cal_run(instance, UINT64_C(1));
    assert(cal_state(instance).tp == 0u && cal_state(instance).data_out == 1u);
    cal_run(instance, data_delta - tp_delta - UINT64_C(1));
    assert(cal_state(instance).data_out == 1u);
    cal_run(instance, UINT64_C(1));
    assert(cal_state(instance).data_out == 0u);
    gn_destroy(instance);
    free(media.copy);
}

static void check_calendar_interrupt_noops(const uint8_t *bundle, size_t size) {
    static const unsigned commands[] = {12u, 13u, 14u};
    static const uint8_t set_time[6] = {
        0x56u, 0x34u, 0x12u, 0x28u, 0x72u, 0x24u};
    uint8_t stopped_time[sizeof(set_time)];
    gn_mvs_calendar after_command[sizeof(commands) / sizeof(commands[0])];
    gn_mvs_calendar after_advance[sizeof(commands) / sizeof(commands[0])];

    /* Commands 12-14 are documented no-ops in the retained source. Exercise
     * each from the same stopped TIME SET state, then keep only the defined
     * stopped-clock invariants separate from protocol/timer fields. */
    for (size_t index = 0u; index < sizeof(commands) / sizeof(commands[0]); ++index) {
        guest_media media;
        gn_instance *instance = cal_start_idle(&media, bundle, size);
        assert(cal_command(instance, CAL_SHIFT) == GN_STATUS_OK);
        for (unsigned bit = 0u; bit < 48u; ++bit)
            cal_clock_bit(instance, (set_time[bit / 8u] >> (bit % 8u)) & 1u);
        for (unsigned bit = 0u; bit < 4u; ++bit)
            cal_clock_bit(instance, (CAL_TIME_SET >> bit) & 1u);
        assert(cal_put(instance, 0u, 0u, 1u) == GN_STATUS_OK);
        assert(cal_put(instance, 0u, 0u, 0u) == GN_STATUS_OK);
        const gn_mvs_calendar stopped = cal_state(instance);
        assert(stopped.command == CAL_TIME_SET && stopped.clock_running == 0u);
        memcpy(stopped_time, stopped.time_counter, sizeof(stopped_time));

        assert(cal_command(instance, commands[index]) == GN_STATUS_OK);
        after_command[index] = cal_state(instance);
        cal_run(instance, UINT64_C(3) * CAL_SECOND_CYCLES);
        after_advance[index] = cal_state(instance);
        gn_destroy(instance);
        free(media.copy);
    }

    for (size_t index = 0u; index < sizeof(commands) / sizeof(commands[0]); ++index) {
        assert(after_command[index].command == commands[index]);
        assert(after_command[index].shift_reg[6] == commands[index]);
        assert(after_command[index].data_in == 0u && after_command[index].clk == 0u &&
               after_command[index].stb == 0u);
        assert(after_command[index].clock_running == 0u);
        assert(after_advance[index].clock_running == 0u);
        for (size_t field = 0u; field < sizeof(stopped_time); ++field) {
            assert(after_command[index].time_counter[field] == stopped_time[field]);
            assert(after_advance[index].time_counter[field] == stopped_time[field]);
        }
    }
}

static void check_calendar_resume_commands(const uint8_t *bundle, size_t size) {
    static const unsigned commands[] = {4u, 5u, 6u, 7u, 8u, 9u, 10u, 11u};
    static const uint8_t set_time[6] = {
        0x56u, 0x34u, 0x12u, 0x28u, 0x72u, 0x24u};

    /* TIME SET stops the counter. Every documented pulse command 4-11 then
     * resumes it, toggles its time-pulse output at command time, and advances
     * the counter by one emulated second. */
    for (size_t index = 0u; index < sizeof(commands) / sizeof(commands[0]); ++index) {
        guest_media media;
        gn_instance *instance = cal_start_idle(&media, bundle, size);
        assert(cal_command(instance, CAL_SHIFT) == GN_STATUS_OK);
        for (unsigned bit = 0u; bit < 48u; ++bit)
            cal_clock_bit(instance, (set_time[bit / 8u] >> (bit % 8u)) & 1u);
        for (unsigned bit = 0u; bit < 4u; ++bit)
            cal_clock_bit(instance, (CAL_TIME_SET >> bit) & 1u);
        assert(cal_put(instance, 0u, 0u, 1u) == GN_STATUS_OK);
        assert(cal_put(instance, 0u, 0u, 0u) == GN_STATUS_OK);
        const gn_mvs_calendar stopped = cal_state(instance);
        assert(stopped.clock_running == 0u);

        assert(cal_command(instance, commands[index]) == GN_STATUS_OK);
        const gn_mvs_calendar resumed = cal_state(instance);
        assert(resumed.command == commands[index]);
        assert(resumed.clock_running == 1u);
        assert(resumed.tp == 1u);

        cal_run(instance, CAL_SECOND_CYCLES);
        const gn_mvs_calendar advanced = cal_state(instance);
        assert(advanced.clock_running == 1u);
        assert(memcmp(advanced.time_counter, stopped.time_counter,
                      sizeof(stopped.time_counter)) != 0);
        gn_destroy(instance);
        free(media.copy);
    }
}

/* REG_STATUS_A (plan 05-22 rerun 13, D-07, kind io, citation S22 and its continuation rows). The
 * selected boot reads the byte at $320001. Pinned MAME 31e52312 neogeo.cpp
 * maps $320000-$320001 (mirror 0x01fffe) to the AUDIO_COIN port: with nothing
 * pressed, coin 1, coin 2, service and the two unused low bits (3 and 4) read
 * 1, the 4-slot sense bit 5 has no handler and reads 0, bit 6 is the uPD4990A
 * time pulse and bit 7 its data out. The high byte (sound reply) is not read
 * here and stays a recorded fault. Expected bytes are recomputed from the
 * cited bit layout, not read back from the implementation. */
#define STATUS_A UINT32_C(0x00320001)
#define STATUS_A_IDLE UINT8_C(0x1f)
#define STATUS_A_TP UINT8_C(0x40)
#define STATUS_A_DATA_OUT UINT8_C(0x80)

static void check_status_a(const uint8_t *bundle, size_t size) {
    guest_media media;
    gn_instance *instance = cal_start_idle(&media, bundle, size);
    gn_instance *other = bb_start(&media);

    /* No input pressed and both calendar pins low at power-on. */
    assert(io_status_byte(instance, STATUS_A) == STATUS_A_IDLE);
    /* Every address the 0x01fffe mirror names reads the same register. */
    assert(io_status_byte(instance, UINT32_C(0x320003)) == STATUS_A_IDLE);
    assert(io_status_byte(instance, UINT32_C(0x330001)) == STATUS_A_IDLE);
    assert(io_status_byte(instance, UINT32_C(0x33ffff)) == STATUS_A_IDLE);
    /* A read is deterministic and mutates no calendar state. */
    const gn_mvs_calendar before = cal_state(instance);
    assert(io_status_byte(instance, STATUS_A) == STATUS_A_IDLE);
    const gn_mvs_calendar after = cal_state(instance);
    assert_calendar_equal(&before, &after);

    /* TIME READ then SHIFT presents the 48 time bits, least significant
     * first, on data out (bit 7): the seed is read back through the bus. */
    for (unsigned bit = 0u; bit < 4u; ++bit) cal_clock_bit(instance, (CAL_TIME_READ >> bit) & 1u);
    assert(cal_put(instance, 0u, 0u, 1u) == GN_STATUS_OK);
    assert(cal_put(instance, 0u, 0u, 0u) == GN_STATUS_OK);
    assert(cal_command(instance, CAL_SHIFT) == GN_STATUS_OK);
    uint8_t bytes[6] = {0};
    for (unsigned bit = 0u; bit < 48u; ++bit) {
        const uint8_t status = io_status_byte(instance, STATUS_A);
        assert((status & STATUS_A_IDLE) == STATUS_A_IDLE && (status & STATUS_A_TP) == 0u);
        bytes[bit / 8u] |= (uint8_t)(((status & STATUS_A_DATA_OUT) != 0u ? 1u : 0u) << (bit % 8u));
        assert(cal_put(instance, 0u, 1u, 0u) == GN_STATUS_OK);
        assert(cal_put(instance, 0u, 0u, 0u) == GN_STATUS_OK);
    }
    assert(memcmp(bytes, cal_epoch, sizeof(cal_epoch)) == 0);
    /* A second instance that never saw the commands is unaffected. */
    assert(io_status_byte(other, STATUS_A) == STATUS_A_IDLE);

    /* REGISTER HOLD raises both pins at the command; the 64 Hz time pulse
     * falls after 256 chip ticks (under 93,750 clocks) while the 1 Hz data
     * out stays high for 16,384 chip ticks. */
    assert(gn_reset(instance) == GN_STATUS_OK);
    assert(io_status_byte(instance, STATUS_A) == STATUS_A_IDLE);
    assert(cal_command(instance, CAL_REG_HOLD) == GN_STATUS_OK);
    assert(io_status_byte(instance, STATUS_A) ==
           (uint8_t)(STATUS_A_IDLE | STATUS_A_TP | STATUS_A_DATA_OUT));
    cal_run(instance, UINT64_C(100000));
    assert(io_status_byte(instance, STATUS_A) == (uint8_t)(STATUS_A_IDLE | STATUS_A_DATA_OUT));
    assert(io_status_byte(other, STATUS_A) == STATUS_A_IDLE);
    /* Reset returns both pins low. */
    assert(gn_reset(instance) == GN_STATUS_OK);
    assert(io_status_byte(instance, STATUS_A) == STATUS_A_IDLE);

    /* No blanket default: the reply byte at $320000, its word read and the
     * neighboring status windows still fault and are recorded. */
    const uint32_t still_faulting[] = {UINT32_C(0x360000), UINT32_C(0x360001)};
    for (size_t index = 0u; index < sizeof(still_faulting) / sizeof(still_faulting[0]);
         ++index) {
        gn_instance *fresh = bb_start(&media);
        uint8_t value = 0xa5u;
        assert(gn_test_mvs_read_bus8(fresh, still_faulting[index], &value) ==
               GN_STATUS_INVALID_MEDIA);
        gn_mvs_bus_fault_observation observation;
        assert(gn_observe_mvs_bus_fault(fresh, &observation, sizeof(observation)) ==
               GN_STATUS_OK);
        assert(observation.valid == 1u && observation.address == still_faulting[index] &&
               observation.access == GN_MVS_BUS_ACCESS_READ && observation.width == 1u);
        gn_destroy(fresh);
    }
    gn_instance *word = bb_start(&media);
    uint16_t word_value = 0xa5a5u;
    assert(gn_test_mvs_read_bus(word, UINT32_C(0x360000), &word_value) ==
           GN_STATUS_INVALID_MEDIA);
    gn_destroy(word);
    gn_destroy(other);
    gn_destroy(instance);
    free(media.copy);
}

/* Synthetic source-qualified audio program: enable NMI, read and clear the
 * command latch from port $00, complement the command, and write the result to
 * the reply latch at port $0c. The main guest issues the first command through
 * its ordinary MVS byte-write path. */
static void install_sound_reply_fixture(guest_media *media, uint8_t command) {
    static const uint8_t z80_boot[] = {
        0x31u, 0xffu, 0xffu,       /* LD SP,$ffff */
        0x3eu, 0x01u,               /* LD A,1 */
        0xd3u, 0x08u,               /* OUT ($08),A: enable command NMI */
        0x76u,                       /* HALT */
        0x18u, 0xfdu                /* JR back to HALT */
    };
    static const uint8_t z80_nmi[] = {
        0xdbu, 0x00u,               /* IN A,($00): read and clear command */
        0x2fu,                       /* CPL */
        0xd3u, 0x0cu,               /* OUT ($0c),A: write reply */
        0xedu, 0x45u                /* RETN */
    };
    assert(media != NULL && media->bios != NULL && media->audio != NULL);
    memcpy(media->audio, z80_boot, sizeof(z80_boot));
    memcpy(media->audio + 0x66u, z80_nmi, sizeof(z80_nmi));
    memcpy(media->audio_bios, z80_boot, sizeof(z80_boot));
    memcpy(media->audio_bios + 0x66u, z80_nmi, sizeof(z80_nmi));
    uint8_t *code = emit_move_b_imm(media->bios + 0x100u, command,
                                    UINT32_C(0x320000));
    *code++ = 0x60u;                /* BRA.s -2: keep the main CPU running */
    *code = 0xfeu;
}

static void check_sound_command_reply(const uint8_t *bundle, size_t size) {
    guest_media media;
    open_guest_media(bundle, size, &media);
    install_sound_reply_fixture(&media, 0x3cu);
    gn_instance *instance = bb_start(&media);
    gn_instance *other = bb_start(&media);
    gn_run_result run;
    uint8_t reply = 0u;

    assert(gn_run_mvs(instance, UINT64_C(5000), &run) == GN_STATUS_OK);
    assert(run.reason == GN_RUN_BUDGET);
    gn_mvs_bus_fault_observation fault;
    assert(gn_observe_mvs_bus_fault(instance, &fault, sizeof(fault)) == GN_STATUS_OK);
    assert(fault.valid == 0u);
    assert(gn_test_mvs_read_bus8(instance, UINT32_C(0x320000), &reply) == GN_STATUS_OK);
    assert(reply == 0xc3u);
    uint16_t audio_port = 0u;
    assert(gn_test_mvs_read_bus(instance, UINT32_C(0x320000), &audio_port) ==
           GN_STATUS_OK);
    assert(audio_port == UINT16_C(0xc31f));

    /* The command and reply state belong to one instance. */
    assert(gn_test_mvs_read_bus8(other, UINT32_C(0x320000), &reply) == GN_STATUS_OK);
    assert(reply == 0u);
    assert(gn_test_mvs_write_bus8(instance, UINT32_C(0x320000), 0x96u) ==
           GN_STATUS_OK);
    bb_run(instance, UINT64_C(3000));
    assert(gn_test_mvs_read_bus8(instance, UINT32_C(0x320000), &reply) == GN_STATUS_OK);
    assert(reply == 0x69u);
    assert(gn_test_mvs_read_bus(instance, UINT32_C(0x320000), &audio_port) ==
           GN_STATUS_OK);
    assert(audio_port == UINT16_C(0x691f));

    assert(gn_reset(instance) == GN_STATUS_OK);
    assert(gn_test_mvs_read_bus8(instance, UINT32_C(0x320000), &reply) == GN_STATUS_OK);
    assert(reply == 0u);
    assert(gn_test_mvs_read_bus8(other, UINT32_C(0x320000), &reply) == GN_STATUS_OK);
    assert(reply == 0u);
    assert(gn_run_mvs(other, UINT64_C(5000), &run) == GN_STATUS_OK);
    assert(run.reason == GN_RUN_BUDGET);
    assert(gn_test_mvs_read_bus8(other, UINT32_C(0x320000), &reply) == GN_STATUS_OK);
    assert(reply == 0xc3u);

    gn_destroy(other);
    gn_destroy(instance);
    free(media.copy);
}

/* Source-qualified pending command control (S25b-S25e). The audio BIOS keeps
 * NMI disabled through a deterministic guest loop, then enables it without a
 * second command. The handler's RAM write and reply expose guest execution. */
static void check_disabled_nmi_pending_then_enable(void) {
    uint8_t cart[0x20000u] = {0};
    uint8_t bios[0x20000u] = {0};
    static const uint8_t boot[] = {
        0x31u, 0xffu, 0xffu,       /* LD SP,$ffff */
        0x3eu, 0xa5u,               /* LD A,$a5: boot RAM sentinel */
        0x32u, 0x00u, 0xf8u,        /* LD ($f800),A */
        0x01u, 0x00u, 0x40u,        /* LD BC,$4000 */
        0x0bu,                       /* wait: DEC BC */
        0x78u, 0xb1u,               /* LD A,B / OR C */
        0x20u, 0xfbu,               /* JR NZ,wait */
        0x3eu, 0x01u,
        0xd3u, 0x08u,               /* OUT ($08),A: enable NMI */
        0x76u, 0x18u, 0xfdu         /* HALT / JR back to HALT */
    };
    static const uint8_t handler[] = {
        0xdbu, 0x00u,               /* IN A,($00): consume pending command */
        0x2fu,                       /* CPL */
        0x32u, 0x01u, 0xf8u,        /* LD ($f801),A: handler side effect */
        0xd3u, 0x0cu,               /* OUT ($0c),A: command-derived reply */
        0xedu, 0x45u                /* RETN */
    };
    memcpy(bios, boot, sizeof(boot));
    memcpy(bios + 0x66u, handler, sizeof(handler));

    gn_mvs_sound sound;
    assert(gn_mvs_sound_create(&sound, cart, sizeof(cart)) == GN_STATUS_OK);
    sound.bios_program = bios;
    sound.bios_program_size = sizeof(bios);
    assert(gn_mvs_sound_reset(&sound) == GN_STATUS_OK);
    assert(gn_mvs_sound_write_command(&sound, UINT32_C(0x320000), 0x3cu) == 1);

    /* 500,000 main clocks advance the BIOS but stay inside its 0x4000-step
     * wait. The pending command must not be consumed and no handler output or
     * handler RAM side effect may appear while NMI remains disabled. */
    assert(gn_mvs_sound_advance(&sound, UINT64_C(500000)) == GN_STATUS_OK);
    assert(sound.nmi_enabled == 0u);
    assert(sound.command_pending == 1u);
    assert(sound.reply == 0u);
    assert(sound.ram[0] == 0xa5u);
    assert(sound.ram[1] == 0u);

    /* Guest I/O alone enables NMI. The retained command reaches the handler,
     * which consumes it, records its guest-only RAM side effect and replies. */
    assert(gn_mvs_sound_advance(&sound, UINT64_C(1000000)) == GN_STATUS_OK);
    assert(sound.nmi_enabled == 1u);
    assert(sound.command_pending == 0u);
    assert(sound.reply == 0xc3u);
    assert(sound.ram[0] == 0xa5u);
    assert(sound.ram[1] == 0xc3u);

    assert(gn_mvs_sound_reset(&sound) == GN_STATUS_OK);
    assert(sound.nmi_enabled == 0u && sound.command_pending == 0u &&
           sound.reply == 0u && sound.ram[0] == 0u && sound.ram[1] == 0u);
    gn_mvs_sound_destroy(&sound);
}

/* Specified oracle: sequential no-wait MOVE transfers cost four clocks each.
 * Z80 LD A,n / OUT (n),A publishes the reply during the absolute-long read's
 * 16 clocks, after the main CPU's 40-clock reset event. */
static void check_sound_bus_boundary(const uint8_t *bundle, size_t size) {
    guest_media media;
    open_guest_media(bundle, size, &media);
    const uint8_t audio[] = {0x3eu, 0x5au, 0xd3u, 0x0cu, 0x76u};
    memcpy(media.audio, audio, sizeof(audio));
    memcpy(media.audio_bios, audio, sizeof(audio));
    uint8_t *code = emit32(emit16(media.bios + 0x100u, 0x1239u),
                            UINT32_C(0x320000));
    code = emit32(emit16(code, 0x33c1u), UINT32_C(0x100000));
    (void)emit_stop(code);
    gn_instance *instance = bb_start(&media);
    gn_run_result run;
    assert(gn_run_mvs(instance, 40u, &run) == GN_STATUS_OK);
    uint8_t reply = 0xffu;
    assert(gn_test_mvs_read_bus8(instance, UINT32_C(0x320000), &reply) == GN_STATUS_OK);
    assert(reply == 0u);
    assert(gn_run_mvs(instance, 16u, &run) == GN_STATUS_OK);
    assert(run.elapsed_cycles == 16u);
    bb_run(instance, 20u);
    uint16_t sampled = 0u;
    assert(gn_test_mvs_read_work_ram(instance, UINT32_C(0x100000), &sampled) == GN_STATUS_OK);
    assert(sampled == 0x5au);
    gn_destroy(instance);
    free(media.copy);

    open_guest_media(bundle, size, &media);
    /* NOP then IN samples old command during the main CPU's immediate
     * absolute-long write (five transfers, 20 clocks). OUT publishes later. */
    const uint8_t poll[] = {0x00u, 0xdbu, 0x00u, 0xd3u, 0x0cu, 0x76u};
    memcpy(media.audio, poll, sizeof(poll));
    memcpy(media.audio_bios, poll, sizeof(poll));
    code = emit_move_b_imm(media.bios + 0x100u, 0x6du, UINT32_C(0x320000));
    (void)emit_stop(code);
    instance = bb_start(&media);
    assert(gn_run_mvs(instance, 40u, &run) == GN_STATUS_OK);
    assert(gn_run_mvs(instance, 20u, &run) == GN_STATUS_OK);
    assert(run.elapsed_cycles == 20u);
    bb_run(instance, 80u);
    assert(gn_test_mvs_read_bus8(instance, UINT32_C(0x320000), &reply) == GN_STATUS_OK);
    assert(reply == 0u);
    gn_destroy(instance);
    instance = bb_start(&media);
    /* A legacy manifest carries only its six original region entries. The
     * runtime must never read a seventh entry or substitute cartridge bytes. */
    const size_t legacy_bytes = offsetof(gn_mvs_manifest, regions) +
        GN_MVS_LEGACY_REGIONS * sizeof(gn_mvs_region);
    gn_mvs_manifest *legacy = (gn_mvs_manifest *)malloc(legacy_bytes);
    assert(legacy != NULL);
    memcpy(legacy, &media.manifest, legacy_bytes);
    legacy->version = GN_MVS_MANIFEST_VERSION_LEGACY;
    legacy->region_count = GN_MVS_LEGACY_REGIONS;
    assert(gn_load_mvs(instance, legacy) == GN_STATUS_OK);
    legacy->version = GN_MVS_MANIFEST_VERSION;
    assert(gn_load_mvs(instance, legacy) == GN_STATUS_INVALID_MEDIA);
    legacy->version = UINT32_C(3);
    assert(gn_load_mvs(instance, legacy) == GN_STATUS_UNSUPPORTED_PROFILE);
    free(legacy);
    assert(gn_test_mvs_write_bus8(instance, UINT32_C(0x3a000b), 0u) == GN_STATUS_OK);
    assert(gn_run_mvs(instance, 40u, &run) == GN_STATUS_CPU_FAILURE);
    gn_destroy(instance);
    free(media.copy);
}

/* Derived oracle: pinned YM2610 read_data returns the programmed SSG register;
 * a constant status stub cannot satisfy this guest-driven round trip. */
static void check_sound_ym_registers(void) {
    uint8_t cart[0x20000u] = {0};
    uint8_t bios[0x8000u] = {0};
    const uint8_t code[] = {
        0x3e, 0x08, 0xd3, 0x04, /* select SSG volume */
        0x3e, 0x0b, 0xd3, 0x05, /* program a nonzero value */
        0xdb, 0x05, 0x32, 0x00, 0xf8, /* read data to sound RAM */
        0x76
    };
    memcpy(bios, code, sizeof(code));
    gn_mvs_sound sound;
    assert(gn_mvs_sound_create(&sound, cart, sizeof(cart)) == GN_STATUS_OK);
    sound.bios_program = bios;
    sound.bios_program_size = sizeof(bios);
    assert(gn_mvs_sound_advance(&sound, 600u) == GN_STATUS_OK);
    assert(sound.ram[0] == 0x0bu);
    gn_mvs_sound_destroy(&sound);
}

/* The selected importer stores the compact 128 KiB audio program. MAME's
 * pinned NEO_BIOS_AUDIO_128K loader reloads that source at 0x10000 before its
 * bank formula is applied, so the compact consumer must translate a mapped
 * address back by that reload base rather than treating the expanded offset
 * as an index into the compact bytes. */
static void check_sound_compact_audio_bank_windows(void) {
    uint8_t cart[0x20000u];
    for (size_t index = 0u; index < sizeof(cart); ++index) {
        cart[index] = (uint8_t)(index ^ (index >> 12u) ^
                                ((index >> 16u) * 0x53u));
    }
    static const struct {
        uint8_t region;
        uint8_t bank;
        uint8_t shift;
        uint16_t window;
        uint16_t first;
        uint16_t last;
    } cases[] = {
        {0u, 0x1eu, 11u, 0xf000u, 0xf000u, 0xf7ffu},
        {1u, 0x0eu, 12u, 0xe000u, 0xe000u, 0xefffu},
        {2u, 0x06u, 13u, 0xc000u, 0xc000u, 0xdfffu},
        {3u, 0x02u, 14u, 0x8000u, 0x8000u, 0xbfffu},
    };
    for (size_t case_index = 0u;
         case_index < sizeof(cases) / sizeof(cases[0]); ++case_index) {
        const uint16_t addresses[] = {cases[case_index].first,
                                      cases[case_index].last};
        for (size_t address_index = 0u;
             address_index < sizeof(addresses) / sizeof(addresses[0]);
             ++address_index) {
            const uint16_t address = addresses[address_index];
            const size_t bank_base =
                ((size_t)cases[case_index].bank << cases[case_index].shift) &
                (sizeof(cart) - 1u);
            const size_t relative = (size_t)address - cases[case_index].window;
            const size_t compact_offset = bank_base + relative;
            const size_t expanded_offset = 0x10000u +
                (((size_t)cases[case_index].bank << cases[case_index].shift) &
                 0xffffu) + relative;
            assert(compact_offset < sizeof(cart));
            assert(expanded_offset < sizeof(cart));
            assert(cart[compact_offset] != cart[expanded_offset]);

            const uint8_t read_program[] = {
                0x3au, (uint8_t)address, (uint8_t)(address >> 8u),
                0x32u, 0x00u, 0xf8u, 0x76u,
            };
            uint8_t bios[0x8000u] = {0};
            memcpy(bios, read_program, sizeof(read_program));
            gn_mvs_sound sound;
            assert(gn_mvs_sound_create(&sound, cart, sizeof(cart)) == GN_STATUS_OK);
            sound.bios_program = bios;
            sound.bios_program_size = sizeof(bios);
            sound.banks[cases[case_index].region] = cases[case_index].bank;
            assert(gn_mvs_sound_advance(&sound, 600u) == GN_STATUS_OK);
            assert(sound.ram[0] == cart[compact_offset]);
            assert(sound.ram[0] != cart[expanded_offset]);
            assert(sound.failure_reason == GN_MVS_FAILURE_REASON_NONE);
            gn_mvs_sound_destroy(&sound);
        }
    }
}

/* Derived oracle: the pinned audio_io_map plus MAME's default unmapped-write
 * handler (S31-S31c) discards writes outside its explicit handlers. Enumerate
 * the map complement rather than deriving any program from private media. */
static void check_sound_unmapped_io_writes(void) {
    uint8_t cart[0x20000u] = {0};
    const uint8_t high_bytes[] = {0u, 0x7fu, 0xffu};
    for (unsigned port = 0u; port <= 0xffu; ++port) {
        const int mapped_write = port == 0u || (port >= 4u && port <= 7u) ||
            port == 8u || port == 0x18u || port == 0x0cu;
        if (mapped_write) continue;
        for (size_t high = 0u; high < sizeof(high_bytes); ++high) {
            uint8_t bios[0x8000u] = {0};
            const uint8_t code[] = {
                0x01u, (uint8_t)port, high_bytes[high], /* LD BC,port */
                0x3eu, 0xa5u, 0xedu, 0x79u, /* LD A,$a5 / OUT (C),A */
                0x3eu, 0x5au, 0x32u, 0x00u, 0xf8u, /* guest continuation */
                0xd3u, 0x0cu, 0x76u /* reply / HALT */
            };
            memcpy(bios, code, sizeof(code));
            gn_mvs_sound sound;
            assert(gn_mvs_sound_create(&sound, cart, sizeof(cart)) == GN_STATUS_OK);
            sound.bios_program = bios;
            sound.bios_program_size = sizeof(bios);
            sound.command = 0x3cu;
            sound.command_pending = 1u;
            assert(ym2610_candidate_write(sound.ym, 0u, 8u) == YM2610_CANDIDATE_OK);
            assert(ym2610_candidate_write(sound.ym, 1u, 0x0bu) == YM2610_CANDIDATE_OK);
            assert(gn_mvs_sound_advance(&sound, 600u) == GN_STATUS_OK);
            assert(sound.ram[0] == 0x5au && sound.reply == 0x5au);
            assert(sound.command == 0x3cu && sound.command_pending == 1u);
            assert(sound.nmi_enabled == 0u && sound.failed == 0u);
            assert(sound.failure_reason == GN_MVS_FAILURE_REASON_NONE);
            assert(sound.banks[0] == 0x1eu && sound.banks[1] == 0x0eu &&
                   sound.banks[2] == 0x06u && sound.banks[3] == 0x02u);
            uint8_t volume = 0u;
            assert(ym2610_candidate_write(sound.ym, 0u, 8u) == YM2610_CANDIDATE_OK);
            assert(ym2610_candidate_read(sound.ym, 1u, &volume) == YM2610_CANDIDATE_OK);
            assert(volume == 0x0bu);
            gn_mvs_sound_destroy(&sound);

            /* The write-only repair must not invent open-bus read values.
             * Test every unsupported read neighbor in the same port set. */
            const unsigned low = port & 0x0fu;
            if (low >= 8u && low <= 11u) continue;
            bios[5] = 0xedu;
            bios[6] = 0x78u; /* IN A,(C), same original synthetic address */
            assert(gn_mvs_sound_create(&sound, cart, sizeof(cart)) == GN_STATUS_OK);
            sound.bios_program = bios;
            sound.bios_program_size = sizeof(bios);
            assert(gn_mvs_sound_advance(&sound, 600u) == GN_STATUS_CPU_FAILURE);
            assert(sound.failure_stage == GN_MVS_FAILURE_STAGE_BUS_ACCESS);
            assert(sound.failure_reason == GN_MVS_FAILURE_REASON_BUS_FAILURE);
            assert(sound.ram[0] == 0u && sound.reply == 0u);
            gn_mvs_sound_destroy(&sound);
        }
    }
}

static void sound_ym_write(gn_mvs_sound *sound, uint8_t reg, uint8_t value) {
    assert(ym2610_candidate_write(sound->ym, 0u, reg) == YM2610_CANDIDATE_OK);
    assert(ym2610_candidate_write(sound->ym, 1u, value) == YM2610_CANDIDATE_OK);
}

static void sound_timer_a(gn_mvs_sound *sound) {
    sound_ym_write(sound, 0x24u, 0xffu);
    sound_ym_write(sound, 0x25u, 3u);
    sound_ym_write(sound, 0x27u, 5u);
}

static void check_sound_ym_sample_bounds(void) {
    uint8_t cart[0x20000u] = {0};
    uint8_t bios[0x8000u] = {0x76u};
    uint8_t samples[256u] = {0};
    gn_mvs_sound sound;
    assert(gn_mvs_sound_create(&sound, cart, sizeof(cart)) == GN_STATUS_OK);
    sound.bios_program = bios;
    sound.bios_program_size = sizeof(bios);
    for (unsigned engine = 0; engine < 2u; ++engine) {
        for (unsigned valid = 0; valid < 2u; ++valid) {
            assert(gn_mvs_sound_reset(&sound) == GN_STATUS_OK);
            sound.samples = samples;
            sound.samples_size = valid ? sizeof(samples) : 1u;
            if (engine == 0u) {
                /* ADPCM-A channel zero, start/end block zero. */
                assert(ym2610_candidate_write(sound.ym, 2u, 0u) == YM2610_CANDIDATE_OK);
                assert(ym2610_candidate_write(sound.ym, 3u, 1u) == YM2610_CANDIDATE_OK);
            } else {
                /* ADPCM-B start/end block zero, maximum delta. */
                sound_ym_write(&sound, 0x19u, 0xffu);
                sound_ym_write(&sound, 0x1au, 0xffu);
                sound_ym_write(&sound, 0x10u, 0x80u);
            }
            const gn_status status = gn_mvs_sound_advance(&sound, 20000u);
            assert(status == (valid ? GN_STATUS_OK : GN_STATUS_CPU_FAILURE));
            if (!valid) {
                assert(sound.failure_stage == GN_MVS_FAILURE_STAGE_SOUND_CATCHUP);
                assert(sound.failure_reason == GN_MVS_FAILURE_REASON_INTERNAL_FAILURE);
                assert(gn_mvs_sound_advance(&sound, 3u) == GN_STATUS_CPU_FAILURE);
            }
        }
    }
    gn_mvs_sound_destroy(&sound);
}

static void check_sound_ym_board(const uint8_t *bundle, size_t size) {
    check_sound_unmapped_io_writes();
    guest_media media;
    open_guest_media(bundle, size, &media);
    const uint8_t code[] = {
        0x01, 0x04, 0x7f, 0x3e, 0x08, 0xed, 0x79, /* mirrored SSG select */
        0x0c, 0x3e, 0x0b, 0xed, 0x79, /* mirrored data write */
        0xed, 0x78, 0xd3, 0x0c, 0x76 /* read register, publish real reply */
    };
    memcpy(media.audio_bios, code, sizeof(code));
    media.bios[0x100u] = 0x60u;
    media.bios[0x101u] = 0xfeu;
    gn_instance *a = bb_start(&media), *b = bb_start(&media);
    uint8_t reply = 0u;
    bb_run(a, 3000u);
    assert(gn_test_mvs_read_bus8(a, UINT32_C(0x320000), &reply) == GN_STATUS_OK);
    assert(reply == 0x0bu);
    assert(gn_test_mvs_read_bus8(b, UINT32_C(0x320000), &reply) == GN_STATUS_OK);
    assert(reply == 0u);
    assert(gn_reset(a) == GN_STATUS_OK);
    assert(gn_test_mvs_read_bus8(a, UINT32_C(0x320000), &reply) == GN_STATUS_OK);
    assert(reply == 0u);
    bb_run(b, 3000u);
    bb_run(a, 3000u);
    assert(gn_test_mvs_read_bus8(a, UINT32_C(0x320000), &reply) == GN_STATUS_OK);
    assert(reply == 0x0bu);
    assert(gn_test_mvs_read_bus8(b, UINT32_C(0x320000), &reply) == GN_STATUS_OK);
    assert(reply == 0x0bu);
    gn_destroy(b);
    gn_destroy(a);
    free(media.copy);
}

/* Derived oracle: pinned ymfm update_timer is (1024-A)*24*6 input
 * clocks; MAME master/3 YM vs master/6 Z80 means 216 main clocks here.
 * Boundary neighbors expose ratio, expiry, IRQ-clear and partition errors. */
static void check_sound_ym_timers(void) {
    uint8_t cart[0x20000u] = {0};
    uint8_t bios[0x8000u] = {0x76u}; /* HALT with IRQ masked */
    gn_mvs_sound a, b;
    assert(gn_mvs_sound_create(&a, cart, sizeof(cart)) == GN_STATUS_OK);
    assert(gn_mvs_sound_create(&b, cart, sizeof(cart)) == GN_STATUS_OK);
    a.bios_program = b.bios_program = bios;
    a.bios_program_size = b.bios_program_size = sizeof(bios);
    for (unsigned split = 0u; split <= 219u; ++split) {
        uint8_t status = 0u, other = 0u;
        assert(gn_mvs_sound_reset(&a) == GN_STATUS_OK);
        assert(gn_mvs_sound_reset(&b) == GN_STATUS_OK);
        sound_timer_a(&a);
        sound_timer_a(&b);
        assert(gn_mvs_sound_advance(&a, 213u) == GN_STATUS_OK);
        assert(a.ym_irq == 0u);
        assert(ym2610_candidate_read(a.ym, 0u, &status) == YM2610_CANDIDATE_OK);
        assert((status & 1u) == 0u);
        assert(gn_mvs_sound_advance(&a, 3u) == GN_STATUS_OK);
        assert(a.ym_irq == 1u);
        assert(gn_mvs_sound_advance(&a, 3u) == GN_STATUS_OK);
        assert(gn_mvs_sound_advance(&b, split) == GN_STATUS_OK);
        assert(gn_mvs_sound_advance(&b, 219u - split) == GN_STATUS_OK);
        assert(b.ym_irq == 1u);
        assert(ym2610_candidate_read(a.ym, 0u, &status) == YM2610_CANDIDATE_OK);
        assert(ym2610_candidate_read(b.ym, 0u, &other) == YM2610_CANDIDATE_OK);
        assert(status == other && (status & 1u) != 0u);
        sound_ym_write(&a, 0x27u, 0x10u);
        assert(a.ym_irq == 0u && b.ym_irq == 1u);
        assert(gn_mvs_sound_reset(&b) == GN_STATUS_OK);
        assert(b.ym_irq == 0u);
    }
    /* IM1/EI/HALT must actually vector the Z80 and execute an ISR.
     * The handler clears timer A, leaves a marker, and returns. */
    const uint8_t boot[] = {0x31, 0xff, 0xff, 0xed, 0x56, 0xfb, 0x76, 0x18, 0xfd};
    const uint8_t handler[] = {
        0x3e, 0x27, 0xd3, 0x04, 0x3e, 0x10, 0xd3, 0x05,
        0x3e, 0xa6, 0x32, 0x00, 0xf8, 0xed, 0x4d
    };
    memset(bios, 0, sizeof(bios));
    memcpy(bios, boot, sizeof(boot));
    memcpy(bios + 0x38u, handler, sizeof(handler));
    assert(gn_mvs_sound_reset(&a) == GN_STATUS_OK);
    assert(gn_mvs_sound_reset(&b) == GN_STATUS_OK);
    sound_timer_a(&a);
    assert(gn_mvs_sound_advance(&a, 3000u) == GN_STATUS_OK);
    assert(a.ram[0] == 0xa6u && a.ym_irq == 0u);
    assert(gn_mvs_sound_advance(&b, 3000u) == GN_STATUS_OK);
    assert(b.ram[0] == 0u && b.ym_irq == 0u);
    gn_mvs_sound_destroy(&b);
    gn_mvs_sound_destroy(&a);
}

static void check_sound_clock_and_sources(void) {
    check_sound_ym_registers();
    check_sound_compact_audio_bank_windows();
    check_sound_ym_timers();
    check_sound_ym_sample_bounds();
    uint8_t *cart = (uint8_t *)calloc(0x20000u, 1u);
    uint8_t bios[0x8000u] = {0u};
    assert(cart != NULL);
    /* Original distinguishable programs; no commercial source bytes. */
    const uint8_t cart_code[] = {0x3eu, 0x35u, 0xd3u, 0x0cu, 0x76u};
    const uint8_t bios_code[] = {0x3eu, 0xcau, 0xd3u, 0x0cu, 0x76u};
    memcpy(cart, cart_code, sizeof(cart_code));
    memcpy(bios, bios_code, sizeof(bios_code));
    gn_mvs_sound a, b;
    assert(gn_mvs_sound_create(&a, cart, 0x20000u) == GN_STATUS_OK);
    assert(gn_mvs_sound_create(&b, cart, 0x20000u) == GN_STATUS_OK);
    a.bios_program = bios;
    a.bios_program_size = sizeof(bios);
    a.cart_selected = 0u;
    b.cart_selected = 1u;
    assert(gn_mvs_sound_advance(&a, 90u) == GN_STATUS_OK);
    assert(gn_mvs_sound_advance(&b, 90u) == GN_STATUS_OK);
    assert(a.reply == 0xcau && b.reply == 0x35u);
    assert(gn_mvs_sound_reset(&a) == GN_STATUS_OK);
    assert(a.cart_selected == 0u);
    assert(gn_mvs_sound_advance(&a, 90u) == GN_STATUS_OK);
    assert(a.reply == 0xcau);
    assert(gn_mvs_sound_reset(&a) == GN_STATUS_OK);
    a.bios_program = NULL;
    a.bios_program_size = 0u;
    a.cart_selected = 0u;
    assert(gn_mvs_sound_advance(&a, 30u) == GN_STATUS_CPU_FAILURE);
    /* Boundary neighbors 0/1/2/3/4 and every remainder: partitioning cannot
     * create or lose a tick, nor alter candidate continuation state. */
    for (uint64_t total = 0u; total <= 100u; ++total) {
        for (uint64_t split = 0u; split <= total; ++split) {
            assert(gn_mvs_sound_reset(&a) == GN_STATUS_OK);
            assert(gn_mvs_sound_reset(&b) == GN_STATUS_OK);
            a.cart_selected = 1u;
            b.cart_selected = 1u;
            assert(gn_mvs_sound_advance(&a, total) == GN_STATUS_OK);
            assert(gn_mvs_sound_advance(&b, split) == GN_STATUS_OK);
            assert(gn_mvs_sound_advance(&b, total - split) == GN_STATUS_OK);
            z80_candidate_snapshot sa, sb;
            assert(z80_candidate_capture(a.cpu, &sa) == Z80_CANDIDATE_OK);
            assert(z80_candidate_capture(b.cpu, &sb) == Z80_CANDIDATE_OK);
            assert(sa.cycles == total / 3u && sb.cycles == sa.cycles);
            assert(sa.pins == sb.pins);
            assert(memcmp(&sa.cpu, &sb.cpu, sizeof(sa.cpu)) == 0);
            assert(a.main_clock_remainder == total % 3u);
            assert(a.main_clock_remainder == b.main_clock_remainder);
        }
    }
    gn_mvs_sound_destroy(&b);
    gn_mvs_sound_destroy(&a);
    free(cart);
}

static void check_sound_selector_reset(const uint8_t *bundle, size_t size) {
    guest_media media;
    open_guest_media(bundle, size, &media);
    const uint8_t bios[] = {0x3eu, 0xcau, 0xd3u, 0x0cu, 0x18u, 0xfau};
    const uint8_t cart[] = {0x3eu, 0x35u, 0xd3u, 0x0cu, 0x18u, 0xfau};
    memcpy(media.audio_bios, bios, sizeof(bios));
    memcpy(media.audio, cart, sizeof(cart));
    (void)emit_stop(media.bios + 0x100u);
    gn_instance *instance = bb_start(&media);
    gn_instance *other = bb_start(&media);
    bb_run(instance, 300u);
    bb_run(other, 300u);
    uint8_t reply = 0u;
    assert(gn_test_mvs_read_bus8(instance, UINT32_C(0x320000), &reply) == GN_STATUS_OK);
    assert(reply == 0xcau);
    assert(gn_test_mvs_write_bus8(instance, UINT32_C(0x3a001b), 0u) == GN_STATUS_OK);
    bb_run(instance, 300u);
    assert(gn_test_mvs_read_bus8(instance, UINT32_C(0x320000), &reply) == GN_STATUS_OK);
    assert(reply == 0x35u);
    assert(gn_test_mvs_read_bus8(other, UINT32_C(0x320000), &reply) == GN_STATUS_OK);
    assert(reply == 0xcau);
    gn_run_result run;
    run_mvs_in_bounded_chunks(instance, MAME_MVS_WATCHDOG_CPU_CYCLES + 300u, &run);
    gn_mvs_bus_fault_observation observation;
    assert(gn_observe_mvs_bus_fault(instance, &observation, sizeof(observation)) == GN_STATUS_OK);
    assert(observation.mame_watchdog_reset_count == 1u);
    assert(observation.mvs_cart_audio_selected == 0u);
    assert(gn_test_mvs_read_bus8(instance, UINT32_C(0x320000), &reply) == GN_STATUS_OK);
    assert(reply == 0xcau);
    assert(gn_test_mvs_write_bus8(instance, UINT32_C(0x3a001b), 0u) == GN_STATUS_OK);
    assert(gn_reset(instance) == GN_STATUS_OK);
    bb_run(instance, 300u);
    assert(gn_test_mvs_read_bus8(instance, UINT32_C(0x320000), &reply) == GN_STATUS_OK);
    assert(reply == 0xcau);
    gn_destroy(other);
    gn_destroy(instance);
    free(media.copy);
}

/* REG_STATUS_B high byte (05-25 rerun 25), pinned MAME 31e52312,
 * neogeo.cpp lines 1732, 919-925, 1063-1067, 1841-1843 and joystick.cpp
 * START port: released start/select lines, absent card (7), MVS type (1).
 * docs/mvs-media.md S23-S23i. Only the demanded even-byte lane is admitted. */
static void check_status_b(const uint8_t *bundle, size_t size) {
    guest_media media;
    open_guest_media(bundle, size, &media);
    gn_instance *a = bb_start(&media);
    gn_instance *b = bb_start(&media);
    const uint32_t addresses[] = {
        UINT32_C(0x380000), UINT32_C(0x380002),
        UINT32_C(0x390000), UINT32_C(0x39fffe)};
    for (size_t i = 0u; i < sizeof(addresses) / sizeof(addresses[0]); ++i) {
        uint8_t value = 0u;
        assert(gn_test_mvs_read_bus8(a, addresses[i], &value) == GN_STATUS_OK);
        assert(value == 0xffu);
        assert(io_status_byte(b, addresses[i]) == 0xffu);
    }
    assert(gn_reset(a) == GN_STATUS_OK);
    assert(io_status_byte(a, UINT32_C(0x380000)) == 0xffu);
    assert(io_status_byte(b, UINT32_C(0x380000)) == 0xffu);
    gn_mvs_bus_fault_observation observation;
    assert(gn_observe_mvs_bus_fault(a, &observation, sizeof(observation)) == GN_STATUS_OK);
    assert(observation.valid == 0u);
    /* Low-byte lane and word reads stay outside the observed subset; the next
     * I/O region is not part of the mirror. No existing fault control moves. */
    uint8_t byte_value = 0xa5u;
    assert(gn_test_mvs_read_bus8(a, UINT32_C(0x380001), &byte_value) == GN_STATUS_INVALID_MEDIA);
    assert(byte_value == 0xa5u);
    assert(gn_observe_mvs_bus_fault(a, &observation, sizeof(observation)) == GN_STATUS_OK);
    assert(observation.valid == 1u && observation.address == UINT32_C(0x380001) &&
           observation.access == GN_MVS_BUS_ACCESS_READ && observation.width == 1u);
    uint16_t word_value = 0xa5a5u;
    assert(gn_test_mvs_read_bus(a, UINT32_C(0x380000), &word_value) == GN_STATUS_INVALID_MEDIA);
    assert(word_value == 0xa5a5u);
    assert(gn_test_mvs_read_bus8(b, UINT32_C(0x3a0000), &byte_value) == GN_STATUS_INVALID_MEDIA);
    gn_destroy(a); gn_destroy(b); free(media.copy);
}

static uint8_t system_latch_output3(const gn_instance *instance) {
    uint8_t value = 0xffu;
    assert(gn_test_mvs_system_latch_output3(instance, &value) == GN_STATUS_OK);
    return value;
}

static uint8_t system_latch_output2(const gn_instance *instance) {
    uint8_t value = 0xffu;
    assert(gn_test_mvs_system_latch_output2(instance, &value) == GN_STATUS_OK);
    return value;
}

static void check_output3_latch(const uint8_t *bundle, size_t size) {
    guest_media media;
    open_guest_media(bundle, size, &media);
    gn_instance *instance = bb_start(&media);
    gn_instance *other = bb_start(&media);
    assert(system_latch_output3(instance) == 0u);
    assert(system_latch_output3(other) == 0u);

    /* Output 3 is an address-selected HC259 latch: the odd lane at output 3,
     * including its mirror, selects unlock2 regardless of the written byte. */
    assert(gn_test_mvs_write_bus8(instance, UINT32_C(0x3a0017), 0x00u) ==
           GN_STATUS_OK);
    assert(system_latch_output3(instance) == 1u);
    assert(system_latch_output3(other) == 0u);
    assert(gn_test_mvs_write_bus8(instance, UINT32_C(0x3a0017), 0xffu) ==
           GN_STATUS_OK);
    assert(system_latch_output3(instance) == 1u);
    assert(gn_test_mvs_write_bus8(instance, UINT32_C(0x3bffe7), 0x00u) ==
           GN_STATUS_OK);
    assert(system_latch_output3(instance) == 0u);
    assert(gn_test_mvs_write_bus8(instance, UINT32_C(0x3a0007), 0xffu) ==
           GN_STATUS_OK);
    assert(system_latch_output3(instance) == 0u);

    /* Neighboring output 4 and the even byte lane stay unsupported. */
    assert(gn_test_mvs_write_bus8(instance, UINT32_C(0x3a0016), 0x01u) ==
           GN_STATUS_INVALID_MEDIA);
    gn_mvs_bus_fault_observation observation;
    assert(gn_observe_mvs_bus_fault(instance, &observation, sizeof(observation)) ==
           GN_STATUS_OK);
    assert(observation.valid == 1u && observation.address == UINT32_C(0x3a0016) &&
           observation.access == GN_MVS_BUS_ACCESS_WRITE && observation.width == 1u);
    assert(observation.mvs_save_ram_unlocked == 0u);
    assert(gn_reset(instance) == GN_STATUS_OK);
    assert(system_latch_output3(instance) == 0u);
    assert(gn_test_mvs_write_bus8(instance, UINT32_C(0x3a0009), 0x01u) ==
           GN_STATUS_INVALID_MEDIA);
    assert(gn_observe_mvs_bus_fault(instance, &observation, sizeof(observation)) ==
           GN_STATUS_OK);
    assert(observation.valid == 1u && observation.address == UINT32_C(0x3a0009) &&
           observation.access == GN_MVS_BUS_ACCESS_WRITE && observation.width == 1u);
    assert(observation.mvs_save_ram_unlocked == 0u);
    assert(system_latch_output3(instance) == 0u);

    /* Latch state is per image and cleared by reset and successful reload. */
    assert(gn_test_mvs_write_bus8(other, UINT32_C(0x3a0017), 0x00u) ==
           GN_STATUS_OK);
    assert(system_latch_output3(other) == 1u);
    assert(system_latch_output3(instance) == 0u);
    assert(gn_reset(other) == GN_STATUS_OK);
    assert(system_latch_output3(other) == 0u);
    assert(gn_test_mvs_write_bus8(other, UINT32_C(0x3a0017), 0xffu) ==
           GN_STATUS_OK);
    assert(system_latch_output3(other) == 1u);
    assert(gn_load_mvs(other, &media.manifest) == GN_STATUS_OK);
    assert(system_latch_output3(other) == 0u);
    gn_destroy(other);
    gn_destroy(instance);
    free(media.copy);

    /* A guest byte write follows the same latch path and continues normally. */
    guest_media guest;
    open_guest_media(bundle, size, &guest);
    uint8_t *code = guest.bios + 0x100u;
    code = emit_move_b_imm(code, 0x00u, UINT32_C(0x3a0017));
    code = emit_move_w_imm(code, UINT16_C(0x1234), UINT32_C(0x100100));
    emit_stop(code);
    instance = bb_start(&guest);
    gn_run_result run;
    assert(gn_run_mvs(instance, 100000u, &run) == GN_STATUS_OK);
    assert(run.reason == GN_RUN_STOPPED);
    uint16_t guest_marker = 0u;
    assert(gn_test_mvs_read_work_ram(instance, UINT32_C(0x100100), &guest_marker) ==
           GN_STATUS_OK);
    assert(guest_marker == UINT16_C(0x1234));
    assert(system_latch_output3(instance) == 1u);
    gn_destroy(instance);
    free(guest.copy);
}

static void check_output2_latch(const uint8_t *bundle, size_t size) {
    guest_media media;
    open_guest_media(bundle, size, &media);
    gn_instance *instance = bb_start(&media);
    gn_instance *other = bb_start(&media);

    assert(system_latch_output2(instance) == 0u);
    assert(system_latch_output2(other) == 0u);
    assert(system_latch_output3(instance) == 0u);

    /* S24f maps system-latch output 2 to memory-card lock 1. S24c makes the
     * address select the output and its state; the written data is ignored. */
    assert(gn_test_mvs_write_bus8(instance, UINT32_C(0x3a0015), 0x00u) ==
           GN_STATUS_OK);
    assert(system_latch_output2(instance) == 1u);
    assert(system_latch_output2(other) == 0u);
    assert(system_latch_output3(instance) == 0u);
    assert(gn_test_mvs_write_bus8(instance, UINT32_C(0x3a0015), 0xffu) ==
           GN_STATUS_OK);
    assert(system_latch_output2(instance) == 1u);
    assert(gn_test_mvs_write_bus8(instance, UINT32_C(0x3bffe5), 0xffu) ==
           GN_STATUS_OK);
    assert(system_latch_output2(instance) == 0u);
    assert(gn_test_mvs_write_bus8(instance, UINT32_C(0x3a0005), 0x01u) ==
           GN_STATUS_OK);
    assert(system_latch_output2(instance) == 0u);

    /* Output 1 remains independent; the even byte lane remains unsupported. */
    assert(gn_test_mvs_write_bus8(instance, UINT32_C(0x3a0013), 0x01u) ==
           GN_STATUS_OK);
    assert(system_latch_output2(instance) == 0u);
    gn_mvs_bus_fault_observation observation;
    assert(gn_test_mvs_write_bus8(instance, UINT32_C(0x3a0014), 0x01u) ==
           GN_STATUS_INVALID_MEDIA);
    assert(gn_observe_mvs_bus_fault(instance, &observation, sizeof(observation)) ==
           GN_STATUS_OK);
    assert(observation.valid == 1u && observation.address == UINT32_C(0x3a0014) &&
           observation.access == GN_MVS_BUS_ACCESS_WRITE && observation.width == 1u);
    assert(system_latch_output2(instance) == 0u);

    assert(gn_reset(instance) == GN_STATUS_OK);
    assert(system_latch_output2(instance) == 0u);
    assert(gn_test_mvs_write_bus8(other, UINT32_C(0x3a0015), 0x00u) ==
           GN_STATUS_OK);
    assert(system_latch_output2(other) == 1u);
    assert(system_latch_output2(instance) == 0u);
    assert(gn_load_mvs(other, &media.manifest) == GN_STATUS_OK);
    assert(system_latch_output2(other) == 0u);
    gn_destroy(other);
    gn_destroy(instance);
    free(media.copy);

    /* A guest write to output 2 continues into the following instruction. */
    guest_media guest;
    open_guest_media(bundle, size, &guest);
    uint8_t *code = guest.bios + 0x100u;
    code = emit_move_b_imm(code, 0x00u, UINT32_C(0x3a0015));
    code = emit_move_w_imm(code, UINT16_C(0x1234), UINT32_C(0x100100));
    emit_stop(code);
    instance = bb_start(&guest);
    gn_run_result run;
    assert(gn_run_mvs(instance, 100000u, &run) == GN_STATUS_OK);
    assert(run.reason == GN_RUN_STOPPED);
    uint16_t guest_marker = 0u;
    assert(gn_test_mvs_read_work_ram(instance, UINT32_C(0x100100), &guest_marker) ==
           GN_STATUS_OK);
    assert(guest_marker == UINT16_C(0x1234));
    assert(system_latch_output2(instance) == 1u);

    gn_destroy(instance);
    free(guest.copy);
}

/* MAME 31e52312: mvs_state::io_control_w selects a cartridge slot at I/O
 * control offset 0x10. This native profile has one loaded cartridge in slot
 * zero; selecting an empty slot leaves the current mapping intact. */
static void check_single_cartridge_slot_selection(const uint8_t *bundle,
                                                  size_t size) {
    const uint32_t slot_select_address = UINT32_C(0x00380021);
    guest_media guest;
    open_guest_media(bundle, size, &guest);
    uint8_t *code = guest.bios + 0x100u;
    code = emit_move_b_imm(code, 5u, slot_select_address);
    code = emit_move_b_imm(code, 0u, slot_select_address);
    emit_stop(code);

    gn_instance *instance = NULL;
    assert(gn_create(&instance) == GN_STATUS_OK);
    assert(gn_load_mvs(instance, &guest.manifest) == GN_STATUS_OK);
    uint16_t before = 0u;
    uint16_t after = 0u;
    assert(gn_test_mvs_read_bus(instance, UINT32_C(0x200000), &before) ==
           GN_STATUS_OK);
    gn_run_result run;
    assert(gn_run_mvs(instance, 100000u, &run) == GN_STATUS_OK);
    assert(run.reason == GN_RUN_STOPPED);
    assert(gn_test_mvs_read_bus(instance, UINT32_C(0x200000), &after) ==
           GN_STATUS_OK);
    assert(after == before);
    gn_mvs_bus_fault_observation observation;
    assert(gn_observe_mvs_bus_fault(instance, &observation, sizeof(observation)) ==
           GN_STATUS_OK);
    assert(observation.valid == 0u);
    gn_destroy(instance);
    free(guest.copy);

    /* Keep selector values outside MAME's six-entry slot array fail-closed. */
    open_guest_media(bundle, size, &guest);
    code = emit_move_b_imm(guest.bios + 0x100u, 6u, slot_select_address);
    emit_stop(code);
    assert(gn_create(&instance) == GN_STATUS_OK);
    assert(gn_load_mvs(instance, &guest.manifest) == GN_STATUS_OK);
    assert(gn_run_mvs(instance, 100000u, &run) == GN_STATUS_CPU_FAILURE);
    assert(gn_observe_mvs_bus_fault(instance, &observation, sizeof(observation)) ==
           GN_STATUS_OK);
    assert(observation.valid == 1u &&
           observation.access == GN_MVS_BUS_ACCESS_WRITE &&
           observation.width == 1u &&
           observation.address == slot_select_address);
    gn_destroy(instance);
    free(guest.copy);
}

/* The pinned MAME P2 bank write path is exercised by original synthetic guest
 * instructions. Distinct pages make a wrong-bank mapping visible without
 * relying on private media bytes or an emulator-generated expected trace. */
static void check_p2_banking_guest_write_and_instance_reset(const uint8_t *bundle,
                                                            size_t size) {
    guest_media guest;
    open_guest_media(bundle, size, &guest);
    guest.program[0u] = 0x12u;
    guest.program[1u] = 0x34u; /* wrong linear mapping control */
    guest.program[0x100000u] = 0x11u;
    guest.program[0x100001u] = 0x22u; /* reset bank zero */
    guest.program[0x1ffffeu] = 0xabu;
    guest.program[0x1fffffu] = 0xcdu;
    guest.program[0x200000u] = 0x33u;
    guest.program[0x200001u] = 0x44u; /* bank one */
    guest.program[0x2ffffeu] = 0xcau;
    guest.program[0x2fffffu] = 0xfeu;
    guest.program[0x400000u] = 0x55u;
    guest.program[0x400001u] = 0x66u; /* bank three, bounds control */

    uint8_t *code = emit_move_w_imm(guest.bios + 0x100u, 0x0009u,
                                    UINT32_C(0x002ffff8));
    emit_stop(code);
    gn_instance *selected = NULL;
    assert(gn_create(&selected) == GN_STATUS_OK);
    assert(gn_load_mvs(selected, &guest.manifest) == GN_STATUS_OK);

    /* gn_load_mvs owns its inputs: rewrite the source guest after loading the
     * first instance to give an isolated instance a valid-then-invalid bank
     * sequence. MAME masks the select to three bits, then falls back to bank
     * zero when the selected page exceeds the loaded program region. */
    memset(guest.bios + 0x100u, 0, 32u);
    code = emit_move_w_imm(guest.bios + 0x100u, 1u, UINT32_C(0x002ffff0));
    code = emit_move_w_imm(code, 0x000fu, UINT32_C(0x002ffff0));
    emit_stop(code);
    gn_instance *invalid_select = NULL;
    assert(gn_create(&invalid_select) == GN_STATUS_OK);
    assert(gn_load_mvs(invalid_select, &guest.manifest) == GN_STATUS_OK);

    gn_run_result run;
    const gn_status selected_status = gn_run_mvs(selected, 100000u, &run);
    if (selected_status != GN_STATUS_OK) {
        gn_mvs_bus_fault_observation failed_write;
        assert(selected_status == GN_STATUS_CPU_FAILURE);
        assert(gn_observe_mvs_bus_fault(selected, &failed_write,
                                        sizeof(failed_write)) == GN_STATUS_OK);
        assert(failed_write.valid == 1u &&
               failed_write.access == GN_MVS_BUS_ACCESS_WRITE &&
               failed_write.width == 2u &&
               failed_write.address == UINT32_C(0x002ffff8));
    }
    assert(selected_status == GN_STATUS_OK);
    assert(run.reason == GN_RUN_STOPPED);
    uint16_t word = 0u;
    assert(gn_test_mvs_read_bus(selected, UINT32_C(0x00200000), &word) ==
           GN_STATUS_OK);
    assert(word == UINT16_C(0x3344));
    assert(gn_test_mvs_read_bus(selected, UINT32_C(0x002ffffe), &word) ==
           GN_STATUS_OK);
    assert(word == UINT16_C(0xcafe));

    /* The second image remains on its default bank while the first is on 1. */
    assert(gn_test_mvs_read_bus(invalid_select, UINT32_C(0x00200000), &word) ==
           GN_STATUS_OK);
    assert(word == UINT16_C(0x1122));

    assert(gn_run_mvs(invalid_select, 100000u, &run) == GN_STATUS_OK);
    assert(run.reason == GN_RUN_STOPPED);
    assert(gn_test_mvs_read_bus(invalid_select, UINT32_C(0x00200000), &word) ==
           GN_STATUS_OK);
    assert(word == UINT16_C(0x1122));
    gn_mvs_bus_fault_observation observation;
    assert(gn_observe_mvs_bus_fault(invalid_select, &observation,
                                    sizeof(observation)) == GN_STATUS_OK);
    assert(observation.valid == 0u);

    assert(gn_reset(selected) == GN_STATUS_OK);
    assert(gn_test_mvs_read_bus(selected, UINT32_C(0x00200000), &word) ==
           GN_STATUS_OK);
    assert(word == UINT16_C(0x1122));
    assert(gn_test_mvs_read_bus(selected, UINT32_C(0x002ffffe), &word) ==
           GN_STATUS_OK);
    assert(word == UINT16_C(0xabcd));
    assert(gn_observe_mvs_bus_fault(selected, &observation, sizeof(observation)) ==
           GN_STATUS_OK);
    assert(observation.valid == 0u);
    gn_destroy(invalid_select);
    gn_destroy(selected);
    free(guest.copy);
}

static void check_p2_banking_guest_byte_lanes(const uint8_t *bundle, size_t size) {
    const uint32_t select_addresses[] = {
        UINT32_C(0x002ffffe), UINT32_C(0x002fffff)
    };
    const uint16_t expected_words[] = {UINT16_C(0x1122), UINT16_C(0x3344)};

    for (size_t index = 0u; index < sizeof(select_addresses) / sizeof(select_addresses[0]);
         ++index) {
        guest_media guest;
        open_guest_media(bundle, size, &guest);
        guest.program[UINT32_C(0x100000)] = 0x11u;
        guest.program[UINT32_C(0x100001)] = 0x22u;
        guest.program[UINT32_C(0x200000)] = 0x33u;
        guest.program[UINT32_C(0x200001)] = 0x44u;
        uint8_t *code = emit_move_b_imm(guest.bios + 0x100u, 1u,
                                        select_addresses[index]);
        emit_stop(code);

        gn_instance *instance = NULL;
        assert(gn_create(&instance) == GN_STATUS_OK);
        assert(gn_load_mvs(instance, &guest.manifest) == GN_STATUS_OK);
        gn_run_result run;
        assert(gn_run_mvs(instance, 100000u, &run) == GN_STATUS_OK);
        assert(run.reason == GN_RUN_STOPPED);
        uint16_t word = 0u;
        assert(gn_test_mvs_read_bus(instance, UINT32_C(0x00200000), &word) ==
               GN_STATUS_OK);
        assert(word == expected_words[index]);
        gn_mvs_bus_fault_observation observation;
        assert(gn_observe_mvs_bus_fault(instance, &observation,
                                        sizeof(observation)) == GN_STATUS_OK);
        assert(observation.valid == 0u);
        gn_destroy(instance);
        free(guest.copy);
    }
}

/* Pinned MAME 31e52312 neogeo_base_state::io_control_w offset 0 selects the
 * controller protocol on optional input devices. This native profile has no
 * host input device, so the guest write is accepted without a device effect. */
static void check_controller_select_without_host_input(const uint8_t *bundle,
                                                       size_t size) {
    guest_media guest;
    open_guest_media(bundle, size, &guest);
    uint8_t *code = emit_move_b_imm(guest.bios + 0x100u, 0x1fu,
                                    UINT32_C(0x00380001));
    code = emit_move_w_imm(code, UINT16_C(0x5aa5), UINT32_C(0x00100100));
    emit_stop(code);

    gn_instance *instance = NULL;
    assert(gn_create(&instance) == GN_STATUS_OK);
    assert(gn_load_mvs(instance, &guest.manifest) == GN_STATUS_OK);
    gn_run_result run;
    assert(gn_run_mvs(instance, 100000u, &run) == GN_STATUS_OK);
    assert(run.reason == GN_RUN_STOPPED);
    uint16_t marker = 0u;
    assert(gn_test_mvs_read_work_ram(instance, UINT32_C(0x00100100), &marker) ==
           GN_STATUS_OK);
    assert(marker == UINT16_C(0x5aa5));
    gn_mvs_bus_fault_observation observation;
    assert(gn_observe_mvs_bus_fault(instance, &observation, sizeof(observation)) ==
           GN_STATUS_OK);
    assert(observation.valid == 0u);
    gn_destroy(instance);
    free(guest.copy);
}

static void render_fixed_guest(const uint8_t *bundle, size_t bundle_size,
                               uint16_t vram_offset, uint16_t tile_and_palette,
                               int swap_pixel_nibbles, uint8_t *pixels,
                               size_t pixel_capacity) {
    const uint32_t width = UINT32_C(320);
    const uint32_t height = UINT32_C(224);
    const size_t pitch = (size_t)width * sizeof(uint32_t);
    guest_media media;
    open_guest_media(bundle, bundle_size, &media);
    memset(media.fixed, 0, (size_t)0x20000u);
    media.fixed[0x20u + 0x10u] = UINT8_C(0x20);
    media.fixed[0x20u + 0x18u] = UINT8_C(0x03);
    media.fixed[0x20u + 0x00u] = UINT8_C(0x05);
    media.fixed[0x20u + 0x08u] = UINT8_C(0x07);
    if (swap_pixel_nibbles != 0) {
        const size_t groups[] = {0x20u + 0x10u, 0x20u + 0x18u,
                                 0x20u + 0x00u, 0x20u + 0x08u};
        for (size_t index = 0u; index < sizeof(groups) / sizeof(groups[0]);
             ++index) {
            const uint8_t value = media.fixed[groups[index]];
            media.fixed[groups[index]] =
                (uint8_t)((uint8_t)(value << 4) | (value >> 4));
        }
    }

    uint8_t *code = emit_move_w_imm(media.bios + 0x100u, vram_offset,
                                    UINT32_C(0x3c0000));
    code = emit_move_w_imm(code, tile_and_palette, UINT32_C(0x3c0002));
    if (((tile_and_palette >> 12) & 0x0fu) == 1u) {
        for (uint16_t pen = 1u; pen <= 8u; ++pen) {
            const uint32_t palette_address = UINT32_C(0x400000) +
                (uint32_t)(UINT16_C(0x10) + pen) * UINT32_C(2);
            code = emit_move_w_imm(code, UINT16_C(0x7fff), palette_address);
        }
    }
    emit_stop(code);

    gn_instance *instance = NULL;
    assert(gn_create(&instance) == GN_STATUS_OK);
    assert(gn_load_mvs(instance, &media.manifest) == GN_STATUS_OK);
    gn_run_result run;
    assert(gn_run_mvs(instance, UINT64_C(100000), &run) == GN_STATUS_OK);
    assert(run.reason == GN_RUN_STOPPED);
    gn_mvs_private_video_activity activity;
    assert(gn_private_mvs_video_activity(instance, &activity) == GN_STATUS_OK);
    assert(activity.nonzero_vram_words == 1u);
    assert(activity.nonzero_fixed_tilemap_words == 1u);
    assert(activity.nonzero_sprite_words == 0u);
    assert(activity.nonzero_palette_entries ==
           (((tile_and_palette >> 12) & 0x0fu) == 1u ? 8u : 0u));
    assert(activity.visible_sprites == 0u);
    assert(activity.visible_nonfull_y_zoom_samples == 0u);
    assert(activity.backdrop_palette_nonzero == 0u);
    gn_mvs_private_video_activity activity_again;
    assert(gn_private_mvs_video_activity(instance, &activity_again) == GN_STATUS_OK);
    assert(memcmp(&activity, &activity_again, sizeof(activity)) == 0);

    uint16_t raster_before = 0u;
    assert(gn_test_mvs_read_bus(instance, UINT32_C(0x3c0006), &raster_before) ==
           GN_STATUS_OK);
    size_t produced = 0u;
    assert(gn_private_mvs_render_frame(instance, width, height, pitch, pixels,
                                       pixel_capacity, &produced) == GN_STATUS_OK);
    assert(produced == (size_t)width * (size_t)height);
    uint16_t raster_after = 0u;
    assert(gn_test_mvs_read_bus(instance, UINT32_C(0x3c0006), &raster_after) ==
           GN_STATUS_OK);
    assert(raster_after == raster_before);

    if (vram_offset == UINT16_C(0x7002) &&
        (tile_and_palette & UINT16_C(0xf000)) == UINT16_C(0x1000) &&
        swap_pixel_nibbles == 0) {
        const uint32_t expected[] = {
            UINT32_C(0x00000000), UINT32_C(0x00ffffff),
            UINT32_C(0x00ffffff), UINT32_C(0x00000000),
            UINT32_C(0x00ffffff), UINT32_C(0x00000000),
            UINT32_C(0x00ffffff), UINT32_C(0x00000000)};
        const uint32_t *frame = (const uint32_t *)pixels;
        for (size_t x = 0u; x < sizeof(expected) / sizeof(expected[0]); ++x)
            assert(frame[x] == expected[x]);
        for (size_t x = 8u; x < width; ++x) assert(frame[x] == 0u);
    }

    gn_destroy(instance);
    free(media.copy);
}

static void check_mvs_fixed_renderer(const uint8_t *bundle, size_t size) {
    const size_t frame_bytes = (size_t)320u * 224u * sizeof(uint32_t);
    uint8_t *pixels = (uint8_t *)malloc(frame_bytes);
    assert(pixels != NULL);
    memset(pixels, 0xa5, frame_bytes);

    /* The output seam rejects bad geometry and capacity before writing and
     * clears its produced count for every failure. */
    guest_media media;
    open_guest_media(bundle, size, &media);
    memset(media.fixed, 0, (size_t)0x20000u);
    media.fixed[0x20u + 0x10u] = UINT8_C(0x20);
    media.fixed[0x20u + 0x18u] = UINT8_C(0x03);
    media.fixed[0x20u + 0x00u] = UINT8_C(0x05);
    media.fixed[0x20u + 0x08u] = UINT8_C(0x07);
    uint8_t *code = emit_move_w_imm(media.bios + 0x100u, UINT16_C(0x7002),
                                    UINT32_C(0x3c0000));
    code = emit_move_w_imm(code, UINT16_C(0x1001), UINT32_C(0x3c0002));
    for (uint16_t pen = 1u; pen <= 8u; ++pen) {
        const uint32_t address = UINT32_C(0x400000) +
            (uint32_t)(UINT16_C(0x10) + pen) * UINT32_C(2);
        code = emit_move_w_imm(code, UINT16_C(0x7fff), address);
    }
    emit_stop(code);
    gn_instance *instance = NULL;
    assert(gn_create(&instance) == GN_STATUS_OK);
    assert(gn_load_mvs(instance, &media.manifest) == GN_STATUS_OK);
    gn_run_result run;
    assert(gn_run_mvs(instance, UINT64_C(100000), &run) == GN_STATUS_OK);
    assert(run.reason == GN_RUN_STOPPED);

    size_t produced = 77u;
    assert(gn_private_mvs_render_frame(instance, 320u, 224u, 320u * 4u,
                                       NULL, frame_bytes, &produced) ==
           GN_STATUS_INVALID_ARGUMENT);
    assert(produced == 0u);
    produced = 77u;
    assert(gn_private_mvs_render_frame(instance, 319u, 224u, 320u * 4u,
                                       pixels, frame_bytes, &produced) ==
           GN_STATUS_INVALID_ARGUMENT);
    assert(produced == 0u);
    produced = 77u;
    assert(gn_private_mvs_render_frame(instance, 320u, 224u, 320u * 4u,
                                       pixels, frame_bytes - 1u, &produced) ==
           GN_STATUS_INVALID_ARGUMENT);
    assert(produced == 0u && pixels[0] == 0xa5u &&
           pixels[frame_bytes - 1u] == 0xa5u);
    produced = 77u;
    assert(gn_private_mvs_render_frame(instance, 320u, 224u, SIZE_MAX,
                                       pixels, SIZE_MAX, &produced) ==
           GN_STATUS_INVALID_ARGUMENT);
    assert(produced == 0u && pixels[0] == 0xa5u);
    produced = 77u;
    assert(gn_private_mvs_render_frame(instance, 0u, 224u, 0u,
                                       pixels, 0u, &produced) ==
           GN_STATUS_INVALID_ARGUMENT);
    assert(produced == 0u && pixels[0] == 0xa5u);
    produced = 77u;
    assert(gn_private_mvs_render_frame(instance, 320u, 0u, 320u * 4u,
                                       pixels, 0u, &produced) ==
           GN_STATUS_INVALID_ARGUMENT);
    assert(produced == 0u && pixels[0] == 0xa5u);
    assert(gn_private_mvs_render_frame(instance, 320u, 224u, 320u * 4u,
                                       pixels, frame_bytes, NULL) ==
           GN_STATUS_INVALID_ARGUMENT);

    render_fixed_guest(bundle, size, UINT16_C(0x7002), UINT16_C(0x1001), 0,
                       pixels, frame_bytes);
    assert(gn_private_mvs_render_frame(instance, 320u, 224u, 320u * 4u,
                                       pixels, frame_bytes, &produced) ==
           GN_STATUS_OK);
    assert(produced == (size_t)320u * 224u);
    assert(((const uint32_t *)pixels)[1] == UINT32_C(0x00ffffff));

    /* Controls: wrong map address, palette selection, and low/high nibble
     * ordering each change the independently specified expected pixels. */
    render_fixed_guest(bundle, size, UINT16_C(0x7003), UINT16_C(0x1001), 0,
                       pixels, frame_bytes);
    assert(((const uint32_t *)pixels)[1] == 0u);
    render_fixed_guest(bundle, size, UINT16_C(0x7002), UINT16_C(0x2001), 0,
                       pixels, frame_bytes);
    assert(((const uint32_t *)pixels)[1] == 0u);
    render_fixed_guest(bundle, size, UINT16_C(0x7002), UINT16_C(0x1001), 1,
                       pixels, frame_bytes);
    assert(((const uint32_t *)pixels)[1] == 0u);

    gn_destroy(instance);
    free(media.copy);
    free(pixels);
}

static uint8_t *emit_video_ram_word(uint8_t *code, uint16_t offset,
                                    uint16_t value) {
    code = emit_move_w_imm(code, offset, UINT32_C(0x3c0000));
    return emit_move_w_imm(code, value, UINT32_C(0x3c0002));
}

static gn_status render_sprite_guest_format(const uint8_t *bundle, size_t size,
                                     uint16_t zoom_control,
                                     uint16_t y_control,
                                     uint16_t x_position,
                                     uint16_t sprite_code,
                                     uint16_t sprite_attr,
                                     int chained, int effects, int with_zoom_table,
                                     size_t zoom_override_index,
                                     uint8_t zoom_override_value,
                                     uint8_t *pixels, size_t capacity,
                                     size_t pitch, size_t *produced) {
    guest_media media;
    open_guest_media(bundle, size, &media);
    memset(media.fixed, 0, (size_t)0x20000u);
    memset(media.sprites, 0, (size_t)0x100u);
    /* Four bitplanes select pens 1, 2, 4 and 8 at x=0..3; x=7 also
     * selects pen 1 so the horizontal zoom table's one-pixel mode is tested. */
    media.sprites[0x40u] = UINT8_C(0x81);
    media.sprites[0x00u] = UINT8_C(0xf1);
    media.sprites[0x42u] = UINT8_C(0x02);
    media.sprites[0x41u] = UINT8_C(0x04);
    media.sprites[0x43u] = UINT8_C(0x08);
    gn_mvs_manifest_v3 manifest_v3;
    memset(&manifest_v3, 0, sizeof(manifest_v3));
    if (with_zoom_table != 0) {
        media.zoom = (uint8_t *)calloc(GN_MVS_Y_ZOOM_BYTES, 1u);
        assert(media.zoom != NULL);
        for (size_t index = 0u; index < GN_MVS_Y_ZOOM_BYTES; ++index)
            media.zoom[index] = (uint8_t)index;
        if (zoom_override_index < GN_MVS_Y_ZOOM_BYTES) {
            memset(media.zoom, 0, GN_MVS_Y_ZOOM_BYTES);
            media.zoom[zoom_override_index] = zoom_override_value;
            memset(media.sprites, 0, (size_t)0x100u);
            media.sprites[0x44u] = UINT8_C(0x01);
        }
        manifest_v3.version = GN_MVS_MANIFEST_VERSION_ZOOM;
        manifest_v3.profile = GN_MVS_PROFILE_MSX;
        manifest_v3.region_count = media.manifest.region_count + 1u;
        for (size_t index = 0u; index < media.manifest.region_count; ++index)
            manifest_v3.regions[index] = media.manifest.regions[index];
        manifest_v3.regions[media.manifest.region_count] = (gn_mvs_region){
            GN_MVS_REGION_Y_ZOOM, media.zoom, GN_MVS_Y_ZOOM_BYTES,
            GN_MVS_Y_ZOOM_BYTES, GN_MVS_LAYOUT_LINEAR};
    }
    if ((effects & 1) != 0) media.fixed[0x20u + 0x10u] = UINT8_C(0x20);

    uint8_t *code = media.bios + 0x100u;
    code = emit_video_ram_word(code, UINT16_C(0x8000), zoom_control);
    code = emit_video_ram_word(code, UINT16_C(0x8200), y_control);
    code = emit_video_ram_word(code, UINT16_C(0x8400), x_position);
    code = emit_video_ram_word(code, UINT16_C(0x0000), sprite_code);
    code = emit_video_ram_word(code, UINT16_C(0x0001), sprite_attr);
    if (chained != 0) {
        code = emit_video_ram_word(code, UINT16_C(0x8001), zoom_control);
        code = emit_video_ram_word(code, UINT16_C(0x8201),
                                   (uint16_t)(y_control | UINT16_C(0x0040)));
        code = emit_video_ram_word(code, UINT16_C(0x8401), UINT16_C(0));
        code = emit_video_ram_word(code, UINT16_C(0x0040), UINT16_C(0));
        code = emit_video_ram_word(code, UINT16_C(0x0041), UINT16_C(0x0100));
    }
    if ((effects & 1) != 0) {
        code = emit_video_ram_word(code, UINT16_C(0x7022), UINT16_C(0x2001));
    }
    for (uint16_t pen = 1u; pen <= 8u; ++pen) {
        const uint32_t address = UINT32_C(0x400000) +
            (uint32_t)(UINT16_C(0x10) + pen) * UINT32_C(2);
        const uint16_t color = pen == 8u ? UINT16_C(0xffff)
                                         : UINT16_C(0x7fff);
        code = emit_move_w_imm(code, color, address);
    }
    if ((effects & 1) != 0) {
        code = emit_move_w_imm(code, UINT16_C(0x000f),
                               UINT32_C(0x400000) + UINT32_C(0x44));
    }
    if ((effects & 2) != 0)
        code = emit_move_b_imm(code, 0u, UINT32_C(0x3a0011));
    emit_stop(code);

    gn_instance *instance = NULL;
    assert(gn_create(&instance) == GN_STATUS_OK);
    assert((with_zoom_table != 0
        ? gn_load_mvs_v3(instance, &manifest_v3)
        : gn_load_mvs(instance, &media.manifest)) == GN_STATUS_OK);
    if (with_zoom_table != 0) memset(media.zoom, 0, GN_MVS_Y_ZOOM_BYTES);
    gn_run_result run;
    assert(gn_run_mvs(instance, UINT64_C(100000), &run) == GN_STATUS_OK);
    assert(run.reason == GN_RUN_STOPPED);
    uint16_t raster_before = 0u;
    assert(gn_test_mvs_read_bus(instance, UINT32_C(0x3c0006), &raster_before) ==
           GN_STATUS_OK);
    const gn_status status = gn_private_mvs_render_frame(
        instance, 320u, 224u, pitch, pixels, capacity, produced);
    uint16_t raster_after = 0u;
    assert(gn_test_mvs_read_bus(instance, UINT32_C(0x3c0006), &raster_after) ==
           GN_STATUS_OK);
    assert(raster_after == raster_before);
    gn_destroy(instance);
    free(media.zoom);
    free(media.copy);
    return status;
}

static gn_status render_sprite_guest(const uint8_t *bundle, size_t size,
                                     uint16_t zoom_control,
                                     uint16_t y_control,
                                     uint16_t x_position,
                                     uint16_t sprite_code,
                                     uint16_t sprite_attr,
                                     int chained, int effects,
                                     uint8_t *pixels, size_t capacity,
                                     size_t pitch, size_t *produced) {
    return render_sprite_guest_format(bundle, size, zoom_control, y_control,
        x_position, sprite_code, sprite_attr, chained, effects, 0,
        GN_MVS_Y_ZOOM_BYTES, 0u, pixels, capacity, pitch, produced);
}

static gn_status render_sprite_guest_zoom(const uint8_t *bundle, size_t size,
                                          uint16_t zoom_control,
                                          uint16_t y_control,
                                          uint16_t x_position,
                                          uint16_t sprite_code,
                                          uint16_t sprite_attr,
                                          size_t zoom_override_index,
                                          uint8_t zoom_override_value,
                                          uint8_t *pixels, size_t capacity,
                                          size_t pitch, size_t *produced) {
    return render_sprite_guest_format(bundle, size, zoom_control, y_control,
        x_position, sprite_code, sprite_attr, 0, 0, 1,
        zoom_override_index, zoom_override_value, pixels, capacity, pitch,
        produced);
}

static uint32_t sprite_frame_pixel(const uint8_t *pixels, size_t pitch,
                                   size_t x, size_t y) {
    uint32_t value = 0u;
    memcpy(&value, pixels + y * pitch + x * sizeof(value), sizeof(value));
    return value;
}

static void build_sprite_instance_guest(guest_media *media,
                                        uint16_t x_position) {
    memset(media->fixed, 0, (size_t)0x20000u);
    memset(media->sprites, 0, (size_t)0x100u);
    media->sprites[0x40u] = UINT8_C(0x81);
    media->sprites[0x00u] = UINT8_C(0xf1);
    media->sprites[0x42u] = UINT8_C(0x02);
    media->sprites[0x41u] = UINT8_C(0x04);
    media->sprites[0x43u] = UINT8_C(0x08);
    uint8_t *code = media->bios + 0x100u;
    code = emit_video_ram_word(code, UINT16_C(0x8000), UINT16_C(0xffff));
    code = emit_video_ram_word(code, UINT16_C(0x8200), UINT16_C(0xf801));
    code = emit_video_ram_word(code, UINT16_C(0x8400), x_position);
    code = emit_video_ram_word(code, UINT16_C(0x0000), UINT16_C(0));
    code = emit_video_ram_word(code, UINT16_C(0x0001), UINT16_C(0x0100));
    for (uint16_t pen = 1u; pen <= 8u; ++pen) {
        const uint32_t address = UINT32_C(0x400000) +
            (uint32_t)(UINT16_C(0x10) + pen) * UINT32_C(2);
        code = emit_move_w_imm(code,
                               pen == 8u ? UINT16_C(0xffff) : UINT16_C(0x7fff),
                               address);
    }
    emit_stop(code);
}

static void run_sprite_instance(gn_instance *instance) {
    gn_run_result run;
    assert(gn_run_mvs(instance, UINT64_C(100000), &run) == GN_STATUS_OK);
    assert(run.reason == GN_RUN_STOPPED);
}

static void render_sprite_instance(gn_instance *instance, uint8_t *pixels,
                                   size_t capacity, size_t *produced) {
    assert(gn_private_mvs_render_frame(instance, 320u, 224u, 320u * 4u,
                                       pixels, capacity, produced) ==
           GN_STATUS_OK);
    assert(*produced == (size_t)320u * (size_t)224u);
}

static void check_sprite_output_guards(const uint8_t *storage, size_t pitch,
                                       size_t row_bytes, size_t height,
                                       size_t output_allocation,
                                       size_t guard) {
    for (size_t y = 0u; y < height; ++y)
        for (size_t pad = row_bytes; pad < pitch; ++pad)
            assert(storage[guard + y * pitch + pad] == 0xa5u);
    for (size_t index = 0u; index < guard; ++index) {
        assert(storage[index] == 0xa5u);
        assert(storage[guard + output_allocation + index] == 0xa5u);
    }
}

static void check_mvs_sprite_renderer(const uint8_t *bundle, size_t size) {
    const size_t width = (size_t)320u;
    const size_t height = (size_t)224u;
    const size_t row_bytes = width * sizeof(uint32_t);
    const size_t pitch = row_bytes + (size_t)12u;
    const size_t required = pitch * (height - 1u) + row_bytes;
    const size_t output_allocation = required + (pitch - row_bytes);
    const size_t guard = (size_t)8u;
    uint8_t *storage = (uint8_t *)malloc(output_allocation + guard * 2u);
    assert(storage != NULL);
    size_t produced = 0u;
    memset(storage, 0xa5, output_allocation + guard * 2u);
    assert(render_sprite_guest(bundle, size, UINT16_C(0xffff),
                               UINT16_C(0xf801), UINT16_C(0x0400), 0u,
                               UINT16_C(0x0100), 0, 0, storage + guard,
                               required, pitch, &produced) == GN_STATUS_OK);
    assert(produced == width * height);
    assert(sprite_frame_pixel(storage + guard, pitch, 7u, 0u) == 0u);
    for (size_t x = 8u; x <= 11u; ++x)
        assert(sprite_frame_pixel(storage + guard, pitch, x, 0u) ==
               (x == 11u ? UINT32_C(0x00fbfbfb) : UINT32_C(0x00ffffff)));
    assert(sprite_frame_pixel(storage + guard, pitch, 12u, 0u) == 0u);
    assert(sprite_frame_pixel(storage + guard, pitch, 15u, 0u) ==
           UINT32_C(0x00ffffff));
    for (size_t x = 20u; x <= 23u; ++x)
        assert(sprite_frame_pixel(storage + guard, pitch, x, 0u) ==
               UINT32_C(0x00ffffff));
    assert(sprite_frame_pixel(storage + guard, pitch, 8u, 1u) == 0u);
    check_sprite_output_guards(storage, pitch, row_bytes, height,
                               output_allocation, guard);

    /* Flip, horizontal zoom, clipping, wrap, palette/code selection and a
     * chained block each produce independently predicted public pixels. */
    memset(storage, 0xa5, output_allocation + guard * 2u);
    produced = 0u;
    assert(render_sprite_guest(bundle, size, UINT16_C(0xffff),
                               UINT16_C(0xf801), UINT16_C(0x0400), 0u,
                               UINT16_C(0x0101), 0, 0, storage + guard,
                               required, pitch, &produced) == GN_STATUS_OK);
    for (size_t x = 8u; x <= 11u; ++x)
        assert(sprite_frame_pixel(storage + guard, pitch, x, 0u) ==
               UINT32_C(0x00ffffff));
    assert(sprite_frame_pixel(storage + guard, pitch, 12u, 0u) == 0u);
    assert(sprite_frame_pixel(storage + guard, pitch, 15u, 0u) ==
           UINT32_C(0x00ffffff));
    assert(sprite_frame_pixel(storage + guard, pitch, 16u, 0u) ==
           UINT32_C(0x00ffffff));
    for (size_t x = 20u; x <= 23u; ++x)
        assert(sprite_frame_pixel(storage + guard, pitch, x, 0u) ==
               (x == 20u ? UINT32_C(0x00fbfbfb) : UINT32_C(0x00ffffff)));

    memset(storage, 0xa5, output_allocation + guard * 2u);
    produced = 0u;
    assert(render_sprite_guest(bundle, size, UINT16_C(0x00ff),
                               UINT16_C(0xf801), UINT16_C(0x0400), 0u,
                               UINT16_C(0x0100), 0, 0, storage + guard,
                               required, pitch, &produced) == GN_STATUS_OK);
    assert(sprite_frame_pixel(storage + guard, pitch, 8u, 0u) ==
           UINT32_C(0x00ffffff));
    assert(sprite_frame_pixel(storage + guard, pitch, 9u, 0u) == 0u);

    memset(storage, 0xa5, output_allocation + guard * 2u);
    produced = 0u;
    assert(render_sprite_guest(bundle, size, UINT16_C(0xffff),
                               UINT16_C(0xf801), UINT16_C(0x9f80), 0u,
                               UINT16_C(0x0100), 0, 0, storage + guard,
                               required, pitch, &produced) == GN_STATUS_OK);
    assert(sprite_frame_pixel(storage + guard, pitch, 319u, 0u) ==
           UINT32_C(0x00ffffff));
    check_sprite_output_guards(storage, pitch, row_bytes, height,
                               output_allocation, guard);

    memset(storage, 0xa5, output_allocation + guard * 2u);
    produced = 0u;
    assert(render_sprite_guest(bundle, size, UINT16_C(0xffff),
                               UINT16_C(0xf801), UINT16_C(0xfe00), 0u,
                               UINT16_C(0x0100), 0, 0, storage + guard,
                               required, pitch, &produced) == GN_STATUS_OK);
    assert(sprite_frame_pixel(storage + guard, pitch, 3u, 0u) ==
           UINT32_C(0x00ffffff));
    assert(sprite_frame_pixel(storage + guard, pitch, 4u, 0u) ==
           UINT32_C(0x00ffffff));
    assert(sprite_frame_pixel(storage + guard, pitch, 8u, 0u) ==
           UINT32_C(0x00ffffff));
    assert(sprite_frame_pixel(storage + guard, pitch, 11u, 0u) ==
           UINT32_C(0x00ffffff));
    check_sprite_output_guards(storage, pitch, row_bytes, height,
                               output_allocation, guard);

    memset(storage, 0xa5, output_allocation + guard * 2u);
    produced = 0u;
    assert(render_sprite_guest(bundle, size, UINT16_C(0xffff),
                               UINT16_C(0xf801), UINT16_C(0x0400), 0u,
                               UINT16_C(0x0100), 1, 0, storage + guard,
                               required, pitch, &produced) == GN_STATUS_OK);
    assert(sprite_frame_pixel(storage + guard, pitch, 8u, 0u) ==
           UINT32_C(0x00ffffff));
    assert(sprite_frame_pixel(storage + guard, pitch, 24u, 0u) ==
           UINT32_C(0x00ffffff));

    memset(storage, 0xa5, output_allocation + guard * 2u);
    produced = 0u;
    assert(render_sprite_guest(bundle, size, UINT16_C(0xffff),
                               UINT16_C(0xf801), UINT16_C(0x0400), 0u,
                               UINT16_C(0x0200), 0, 0, storage + guard,
                               required, pitch, &produced) == GN_STATUS_OK);
    assert(sprite_frame_pixel(storage + guard, pitch, 8u, 0u) == 0u);

    memset(storage, 0xa5, output_allocation + guard * 2u);
    produced = 0u;
    assert(render_sprite_guest(bundle, size, UINT16_C(0xffff),
                               UINT16_C(0xf801), UINT16_C(0x0400), 1u,
                               UINT16_C(0x0100), 0, 0, storage + guard,
                               required, pitch, &produced) == GN_STATUS_OK);
    assert(sprite_frame_pixel(storage + guard, pitch, 8u, 0u) == 0u);

    memset(storage, 0xa5, output_allocation + guard * 2u);
    produced = 0u;
    assert(render_sprite_guest(bundle, size, UINT16_C(0xffff),
                               UINT16_C(0xf801), UINT16_C(0x0400),
                               UINT16_C(0x0fff), UINT16_C(0x00f0), 0, 0,
                               storage + guard, required, pitch, &produced) ==
           GN_STATUS_OK);
    assert(sprite_frame_pixel(storage + guard, pitch, 8u, 0u) == 0u);

    memset(storage, 0xa5, output_allocation + guard * 2u);
    produced = 0u;
    assert(render_sprite_guest(bundle, size, UINT16_C(0xffff),
                               UINT16_C(0xf801), UINT16_C(0xc800), 0u,
                               UINT16_C(0x0100), 0, 0, storage + guard,
                               required, pitch, &produced) == GN_STATUS_OK);
    assert(sprite_frame_pixel(storage + guard, pitch, 8u, 0u) == 0u);

    memset(storage, 0xa5, output_allocation + guard * 2u);
    produced = 0u;
    assert(render_sprite_guest(bundle, size, UINT16_C(0xffff),
                               UINT16_C(0xf801), UINT16_C(0x0400), 0u,
                               UINT16_C(0x0100), 0, 1, storage + guard,
                               required, pitch, &produced) == GN_STATUS_OK);
    assert(sprite_frame_pixel(storage + guard, pitch, 8u, 0u) ==
           UINT32_C(0x00ffffff));
    assert(sprite_frame_pixel(storage + guard, pitch, 9u, 0u) ==
           UINT32_C(0x000000f7));

    memset(storage, 0xa5, output_allocation + guard * 2u);
    produced = 0u;
    assert(render_sprite_guest(bundle, size, UINT16_C(0xffff),
                               UINT16_C(0xf801), UINT16_C(0x0400), 0u,
                               UINT16_C(0x0100), 0, 2, storage + guard,
                               required, pitch, &produced) == GN_STATUS_OK);
    assert(sprite_frame_pixel(storage + guard, pitch, 8u, 0u) ==
           UINT32_C(0x008e8e8e));
    assert(sprite_frame_pixel(storage + guard, pitch, 11u, 0u) ==
           UINT32_C(0x008d8d8d));
    check_sprite_output_guards(storage, pitch, row_bytes, height,
                               output_allocation, guard);

    memset(storage, 0xa5, output_allocation + guard * 2u);
    produced = 99u;
    assert(render_sprite_guest(bundle, size, UINT16_C(0x007f),
                               UINT16_C(0xf801), UINT16_C(0x0400), 0u,
                               UINT16_C(0x0100), 0, 0, storage + guard,
                               required, pitch, &produced) ==
           GN_STATUS_UNSUPPORTED_PROFILE);
    assert(produced == 0u);
    for (size_t index = 0u; index < output_allocation + guard * 2u; ++index)
        assert(storage[index] == 0xa5u);

    memset(storage, 0xa5, output_allocation + guard * 2u);
    produced = 0u;
    assert(render_sprite_guest_zoom(bundle, size, UINT16_C(0xffff),
        UINT16_C(0x77a0), UINT16_C(0x0400), 0u, UINT16_C(0x0100),
        (size_t)0x0ffffu, UINT8_C(0x01), storage + guard, required, pitch,
        &produced) == GN_STATUS_OK);
    assert(produced == (size_t)320u * (size_t)224u);
    assert(sprite_frame_pixel(storage + guard, pitch, 8u, 0u) != 0u);
    assert(sprite_frame_pixel(storage + guard, pitch, 8u, 1u) == 0u);

    memset(storage, 0xa5, output_allocation + guard * 2u);
    produced = 0u;
    assert(render_sprite_guest_zoom(bundle, size, UINT16_C(0xffff),
        UINT16_C(0x77a0), UINT16_C(0x0400), 0u, UINT16_C(0x0100),
        (size_t)0x0fffeu, UINT8_C(0x01), storage + guard, required, pitch,
        &produced) == GN_STATUS_OK);
    assert(sprite_frame_pixel(storage + guard, pitch, 8u, 0u) == 0u);
    free(storage);
}

static void check_mvs_sprite_instance_isolation(const uint8_t *bundle,
                                                size_t size) {
    const size_t frame_bytes = (size_t)320u * (size_t)224u * sizeof(uint32_t);
    uint8_t *first_pixels = (uint8_t *)malloc(frame_bytes);
    uint8_t *second_pixels = (uint8_t *)malloc(frame_bytes);
    uint8_t *saved_first = (uint8_t *)malloc(frame_bytes);
    uint8_t *saved_second = (uint8_t *)malloc(frame_bytes);
    assert(first_pixels != NULL && second_pixels != NULL &&
           saved_first != NULL && saved_second != NULL);

    guest_media first_media;
    guest_media second_media;
    open_guest_media(bundle, size, &first_media);
    open_guest_media(bundle, size, &second_media);
    build_sprite_instance_guest(&first_media, UINT16_C(0x0400));
    build_sprite_instance_guest(&second_media, UINT16_C(0x0c00));
    gn_instance *first = bb_start(&first_media);
    gn_instance *second = bb_start(&second_media);

    run_sprite_instance(first);
    run_sprite_instance(second);
    size_t first_produced = 0u;
    size_t second_produced = 0u;
    render_sprite_instance(second, second_pixels, frame_bytes, &second_produced);
    render_sprite_instance(first, first_pixels, frame_bytes, &first_produced);
    assert(sprite_frame_pixel(first_pixels, (size_t)320u * 4u, 8u, 0u) ==
           UINT32_C(0x00ffffff));
    assert(sprite_frame_pixel(first_pixels, (size_t)320u * 4u, 24u, 0u) == 0u);
    assert(sprite_frame_pixel(second_pixels, (size_t)320u * 4u, 8u, 0u) == 0u);
    assert(sprite_frame_pixel(second_pixels, (size_t)320u * 4u, 24u, 0u) ==
           UINT32_C(0x00ffffff));
    memcpy(saved_first, first_pixels, frame_bytes);
    memcpy(saved_second, second_pixels, frame_bytes);

    assert(gn_reset(second) == GN_STATUS_OK);
    run_sprite_instance(second);
    render_sprite_instance(second, second_pixels, frame_bytes, &second_produced);
    assert(memcmp(second_pixels, saved_second, frame_bytes) == 0);
    render_sprite_instance(first, first_pixels, frame_bytes, &first_produced);
    assert(memcmp(first_pixels, saved_first, frame_bytes) == 0);
    assert(gn_reset(first) == GN_STATUS_OK);
    run_sprite_instance(first);
    render_sprite_instance(first, first_pixels, frame_bytes, &first_produced);
    assert(memcmp(first_pixels, saved_first, frame_bytes) == 0);

    gn_destroy(first);
    gn_destroy(second);
    free(first_media.copy);
    free(second_media.copy);
    free(first_pixels);
    free(second_pixels);
    free(saved_first);
    free(saved_second);
}

/* Synthetic guest coverage for the selected MSLUGX protection aperture. The
 * command-1 serial bit path and command-0x0fff work-RAM-selected bit path
 * follow the pinned MAME device; this is differential evidence, not a physical
 * board oracle. The public ROM table bytes are deliberately synthetic. */
static void check_mslugx_protection_guest(const uint8_t *bundle, size_t size) {
    guest_media guest;
    open_guest_media(bundle, size, &guest);
    guest.program[UINT32_C(0x0dedd2)] = 0x80u;
    guest.program[UINT32_C(0x0dedd3)] = 0x00u;

    uint8_t *code = guest.bios + 0x100u;
    code = emit_move_w_imm(code, UINT16_C(1), UINT32_C(0x002fffe2));
    code = emit16(code, UINT16_C(0x3039)); /* MOVE.W (xxx).L,D0 */
    code = emit32(code, UINT32_C(0x002fffe0));
    code = emit16(code, UINT16_C(0x33c0)); /* MOVE.W D0,(xxx).L */
    code = emit32(code, UINT32_C(0x00100100));
    code = emit16(code, UINT16_C(0x3039));
    code = emit32(code, UINT32_C(0x002fffe0));
    code = emit16(code, UINT16_C(0x33c0));
    code = emit32(code, UINT32_C(0x00100102));

    code = emit_move_w_imm(code, 0u, UINT32_C(0x002fffe0));
    code = emit_move_w_imm(code, UINT16_C(0x0fff), UINT32_C(0x002fffe2));
    code = emit_move_w_imm(code, UINT16_C(1), UINT32_C(0x0010f00a));
    code = emit16(code, UINT16_C(0x3039));
    code = emit32(code, UINT32_C(0x002fffe0));
    code = emit16(code, UINT16_C(0x33c0));
    code = emit32(code, UINT32_C(0x00100104));
    code = emit_move_w_imm(code, 0u, UINT32_C(0x002fffea));
    code = emit_move_w_imm(code, UINT16_C(1), UINT32_C(0x002fffe2));
    code = emit16(code, UINT16_C(0x3039));
    code = emit32(code, UINT32_C(0x002fffe0));
    code = emit16(code, UINT16_C(0x33c0));
    code = emit32(code, UINT32_C(0x00100106));
    emit_stop(code);

    gn_instance *instance = NULL;
    assert(gn_create(&instance) == GN_STATUS_OK);
    assert(gn_load_mvs(instance, &guest.manifest) == GN_STATUS_OK);
    gn_run_result run;
    assert(gn_run_mvs(instance, UINT64_C(100000), &run) == GN_STATUS_OK);
    assert(run.reason == GN_RUN_STOPPED);

    uint16_t value = 0u;
    assert(gn_test_mvs_read_work_ram(instance, UINT32_C(0x00100100), &value) ==
           GN_STATUS_OK && value == UINT16_C(1));
    assert(gn_test_mvs_read_work_ram(instance, UINT32_C(0x00100102), &value) ==
           GN_STATUS_OK && value == 0u);
    assert(gn_test_mvs_read_work_ram(instance, UINT32_C(0x00100104), &value) ==
           GN_STATUS_OK && value == UINT16_C(1));
    assert(gn_test_mvs_read_work_ram(instance, UINT32_C(0x00100106), &value) ==
           GN_STATUS_OK && value == UINT16_C(1));
    gn_mvs_bus_fault_observation observation;
    assert(gn_observe_mvs_bus_fault(instance, &observation, sizeof(observation)) ==
           GN_STATUS_OK && observation.valid == 0u);
    assert(gn_reset(instance) == GN_STATUS_OK);
    assert(gn_run_mvs(instance, UINT64_C(100000), &run) == GN_STATUS_OK);
    assert(run.reason == GN_RUN_STOPPED);
    assert(gn_test_mvs_read_work_ram(instance, UINT32_C(0x00100100), &value) ==
           GN_STATUS_OK && value == 0u);
    assert(gn_test_mvs_read_work_ram(instance, UINT32_C(0x00100106), &value) ==
           GN_STATUS_OK && value == UINT16_C(1));
    gn_destroy(instance);
    free(guest.copy);
}

static void check_mslugx_protection_instance_isolation(const uint8_t *bundle,
                                                       size_t size) {
    guest_media guest;
    open_guest_media(bundle, size, &guest);
    guest.program[UINT32_C(0x0dedd2)] = 0x80u;
    uint8_t *code = guest.bios + 0x100u;
    code = emit_move_w_imm(code, 0u, UINT32_C(0x002fffe0));
    code = emit_move_w_imm(code, UINT16_C(1), UINT32_C(0x002fffe2));
    code = emit16(code, UINT16_C(0x3039)); /* MOVE.W (xxx).L,D0 */
    code = emit32(code, UINT32_C(0x002fffe0));
    code = emit16(code, UINT16_C(0x33c0)); /* MOVE.W D0,(xxx).L */
    code = emit32(code, UINT32_C(0x00100100));
    emit_stop(code);

    gn_instance *first = NULL;
    gn_instance *second = NULL;
    assert(gn_create(&first) == GN_STATUS_OK);
    assert(gn_create(&second) == GN_STATUS_OK);
    assert(gn_load_mvs(first, &guest.manifest) == GN_STATUS_OK);
    assert(gn_load_mvs(second, &guest.manifest) == GN_STATUS_OK);
    gn_run_result run;
    assert(gn_run_mvs(first, UINT64_C(100000), &run) == GN_STATUS_OK);
    assert(run.reason == GN_RUN_STOPPED);
    assert(gn_run_mvs(second, UINT64_C(100000), &run) == GN_STATUS_OK);
    assert(run.reason == GN_RUN_STOPPED);

    uint16_t value = 0u;
    assert(gn_test_mvs_read_work_ram(first, UINT32_C(0x00100100), &value) ==
           GN_STATUS_OK && value == UINT16_C(1));
    assert(gn_test_mvs_read_work_ram(second, UINT32_C(0x00100100), &value) ==
           GN_STATUS_OK && value == UINT16_C(1));
    gn_destroy(first);
    gn_destroy(second);
    free(guest.copy);
}

/* A failure after VBlank must report the prefix that already advanced
 * CPU/raster time. Exercise both the raw API and its logical-frame consumer. */
static void check_failed_frame_prefix(const uint8_t *bundle, size_t size) {
    guest_media media;
    open_guest_media(bundle, size, &media);
    emit16(emit16(media.bios + 0x100u, 0x4e71u), 0x60fcu);
    for (unsigned logical = 0u; logical < 2u; ++logical) {
        gn_instance *instance = bb_start(&media);
        assert(gn_test_mvs_set_failure(instance,
            GN_TEST_MVS_FAILURE_MAIN_IRQ_UPDATE) == GN_STATUS_OK);
        gn_run_result run;
        const gn_status status = logical != 0u
            ? gn_mvs_run_frame_budget(instance, &run)
            : gn_run_mvs(instance, BB_FRAME_CYCLES, &run);
        assert(status == GN_STATUS_CPU_FAILURE && run.reason == GN_RUN_ERROR);
        gn_mvs_private_video_activity activity;
        assert(gn_private_mvs_video_activity(instance, &activity) == GN_STATUS_OK);
        assert(activity.frame_cycle >= BB_FIRST_VBLANK &&
               activity.frame_cycle < BB_FRAME_CYCLES);
        assert(run.elapsed_cycles == activity.frame_cycle && run.instructions > 0u);
        assert(run.overshoot_cycles == 0u);
        const uint64_t prefix = run.elapsed_cycles;
        assert(activity.frame_cycle_carry == (logical != 0u ? prefix : 0u));
        gn_mvs_failure failure;
        assert(gn_private_mvs_failure(instance, &failure) == GN_STATUS_OK);
        assert(failure.stage == GN_MVS_FAILURE_STAGE_IRQ_UPDATE);
        if (logical != 0u) {
            assert(gn_mvs_run_frame_budget(instance, &run) == GN_STATUS_OK);
            assert(run.requested_cycles == BB_FRAME_CYCLES - prefix);
            assert(prefix + run.elapsed_cycles >= BB_FRAME_CYCLES &&
                   prefix + run.elapsed_cycles < BB_FRAME_CYCLES + 64u);
            assert(gn_private_mvs_failure(instance, &failure) == GN_STATUS_OK);
            assert(failure.stage == GN_MVS_FAILURE_STAGE_IRQ_UPDATE);
        }
        gn_destroy(instance);
    }
    free(media.copy);
}

/* Source-derived clocks/events use the independent BB constants above. A
 * 14-clock NOP/BRA loop does not divide a frame, so raw per-frame budgets
 * accumulate instruction excess instead of preserving the logical horizon. */
static void check_logical_frame_budget(const uint8_t *bundle, size_t size) {
    guest_media media;
    open_guest_media(bundle, size, &media);
    uint8_t *code = emit16(media.bios + 0x100u, 0x4e71u); /* NOP */
    emit16(code, 0x60fcu); /* BRA.s back to NOP */
    gn_instance *a = bb_start(&media);
    gn_instance *b = bb_start(&media);
    uint64_t total = 0u;
    uint64_t first_elapsed = 0u;
    for (uint64_t frame = 1u; frame <= 64u; ++frame) {
        gn_run_result run;
        assert(gn_mvs_run_frame_budget(a, &run) == GN_STATUS_OK);
        assert(run.reason == GN_RUN_BUDGET);
        assert(run.elapsed_cycles >= run.requested_cycles);
        assert(run.overshoot_cycles == run.elapsed_cycles - run.requested_cycles);
        total += run.elapsed_cycles;
        if (frame == 1u) first_elapsed = run.elapsed_cycles;
        const uint64_t target = frame * BB_FRAME_CYCLES;
        assert(total >= target && total < target + UINT64_C(64));
        gn_mvs_private_video_activity activity;
        assert(gn_private_mvs_video_activity(a, &activity) == GN_STATUS_OK);
        assert(activity.frame_cycle == total % BB_FRAME_CYCLES);
        assert(activity.frame_cycle_carry == total - target);
        const uint64_t events = (total + BB_FRAME_CYCLES - BB_FIRST_VBLANK) /
                                BB_FRAME_CYCLES;
        assert(activity.frame_count == events);
        assert(activity.auto_animation_counter ==
               (uint8_t)((total + BB_FRAME_CYCLES - UINT64_C(256) * BB_LINE_CYCLES) /
                         BB_FRAME_CYCLES));
        if (frame == 16u) {
            gn_run_result other;
            assert(gn_mvs_run_frame_budget(b, &other) == GN_STATUS_OK);
            assert(other.elapsed_cycles == first_elapsed);
        }
    }
    gn_run_result run;
    assert(gn_run_mvs(a, UINT64_C(999999), &run) == GN_STATUS_OK);
    total += run.elapsed_cycles;
    gn_mvs_private_video_activity activity;
    assert(gn_private_mvs_video_activity(a, &activity) == GN_STATUS_OK);
    assert(activity.frame_cycle == total % BB_FRAME_CYCLES);
    assert(activity.frame_count ==
           (total + BB_FRAME_CYCLES - BB_FIRST_VBLANK) / BB_FRAME_CYCLES);
    assert(gn_reset(a) == GN_STATUS_OK);
    assert(gn_private_mvs_video_activity(a, &activity) == GN_STATUS_OK);
    assert(activity.frame_cycle == 0u && activity.frame_cycle_carry == 0u &&
           activity.frame_count == 0u && activity.auto_animation_counter == 0u);
    assert(gn_mvs_run_frame_budget(a, &run) == GN_STATUS_OK);
    assert(run.elapsed_cycles == first_elapsed);
    assert(gn_unload(a) == GN_STATUS_OK);
    assert(gn_mvs_run_frame_budget(a, &run) == GN_STATUS_INVALID_STATE);
    assert(run.elapsed_cycles == 0u);
    gn_destroy(b);
    gn_destroy(a);
    free(media.copy);
}

/* Frozen independent MVS PCM contract, established before any runtime PCM is
 * accepted (D7-04). The pinned ymfm candidate's 8 MHz YM clock at MAX fidelity
 * emits one triplet per 16 clocks (500 kHz); the consumer contract is 48 kHz,
 * so the rational output count is floor((12*N + phase)/125), with phase in
 * [0,124]. The guest tone uses SSG channel A, period 125, mixer 0x3e and
 * amplitude 0x0f. ym2610::update_prescale configures MAX SSG at 2:1, and the
 * pinned resample_n_1 implementation clocks the SSG once per two 500 kHz chip
 * samples: 250 kHz. ssg_engine::clock toggles after each tone period, giving
 * 250 kHz/(2*125)=1 kHz for a complete tone cycle.
 * These are source-derived emulator expectations, not silicon or game evidence.
 *
 * The independent converter oracle is a causal 12-phase, 80-tap Kaiser-windowed
 * sinc, cutoff 20 kHz, beta 5.0. For tap k and phase p, the unnormalized
 * coefficient is 0.08*sinc(0.08*(k-39.5+0.5-p/12))*Kaiser(k); each phase is
 * divided by its floating coefficient sum, then coefficients are rounded
 * ties-away-from-zero to signed Q1.30. History begins at zero and is never
 * flushed at frame end. For each phase, the design response is checked every
 * 50 Hz from DC through 12 kHz against the mean phase magnitude at 1 kHz; the
 * worst deviation is 0.248329 dB. At 30 kHz, worst-phase rejection relative to
 * that reference is 51.349654 dB. The same calculation gives respectively
 * 48 taps: 1.387119 dB / 21.058337 dB, 64: 0.638353 / 31.068987,
 * 72: 0.410923 / 37.994974, 80: 0.248329 / 51.349654,
 * 96: 0.056964 / 54.555501, and 224: 0.007969 / 64.175647. Therefore 80 is
 * the shortest passing member of this evaluated set under <=1 dB passband and
 * >=40 dB rejection criteria; it is not a claim about every possible length.
 * The coefficients are original Glueyneo work; no third-party code or media
 * is embedded by this design.
 *
 * Preserve FM left/right separately and mix the mono SSG lane into each side:
 * ties-away round((2*FM + SSG)/4), then 80-tap Q1.30 convolution with signed
 * int64 accumulation, ties-away rounding to S16, and final S16 saturation.
 * ymfm bounds FM at 32768 per side and each SSG channel at 16382, so the
 * conservative prefilter numerator is <= 2*32768 + 3*16382 = 114682 and the
 * mixed sample magnitude <= 28671. Each Q1.30 phase has coefficient L1 norm
 * <2, bounding the accumulator below 28671*2*2^30 < 6.2e13 (well within
 * INT64_MAX). The symmetric 80-tap midpoint delay is 39.5 native samples,
 * 79 us or 3.792 output frames; this delay is retained and never end-flushed.
 *
 * The public per-frame capacity is separately derived from B=202752 main
 * clocks and maximum single-event excess O=159. Current owned DIVS.W
 * immediate costs at most160 clocks:156 signed-divide clocks plus4 EA.
 * SUBSET.md records other current maxima: MOVEM/DIVU148, long shifts134,
 * RESET132, address error50, IRQ44, instruction exception34 (divide-by-zero
 * plus admitted EA at most50), reset recovery40; idle is exact/capped.
 * The worst-case DIVS regression proves160 elapsed from a one-clock request.
 * Thus M=B+O=202911 even when carry reduces the next request. With main/Z80
 * remainder r3<=2, floor((M+r3)/3)=67637 Z80 ticks and135274 YM clocks occur.
 * With native remainder r16<=15, floor((135274+r16)/16)=8455 chip samples occur.
 * With converter phase r125<=124, output is at most
 * floor((12*8455+r125)/125)=812 frames. The causal filter emits online and
 * retains no pending output (P=0); its group delay is history, not capacity.
 * The implementation checks this maximum at runtime. The selected 80-tap
 * filter costs 160 MACs per output frame (7.68 million MAC/s); 224 taps cost
 * 448 MACs per frame.
 *
 * Sources: ymfm revision 81aec25ccbb98f4873a255f7551ac4dadac59b4a,
 * src/ymfm_opn.cpp ym2610::update_prescale/generate,
 * ssg_resampler::resample_n_1 and src/ymfm_ssg.cpp ssg_engine::clock/amplitude
 * table; `src/chips/ym2610_candidate.cpp`'s 16-clock sample divider,
 * `src/mvs/mvs_bus.c`'s 3:1 main/Z80 ratio, `src/instance.c`'s frame carry,
 * `src/sdk_private.h`'s B=202752 budget, and owned Neo Geo master/3 YM clock
 * evidence in the Phase 07
 * research. These references describe emulation-source ancestry, not hardware
 * truth. Quantizing any coefficient contributes at most half a Q1.30 unit;
 * with 80 taps and the frozen input bound, worst output quantization error is
 * below 0.002 S16 units. The runtime tone window excludes its first 32 frames,
 * then measures 768 frames (16 whole 1 kHz periods) with maximum phase of a
 * 48-sample square-wave correlation; its score must be >=256 S16 counts, and
 * left/right must match. Wrong command PCM must remain exactly zero; key-off PCM
 * must become exactly zero after the causal history drains. Frozen response
 * limits and routing must not be relaxed after PCM runs.
 */
static void pcm_test_emit_ym_write(uint8_t *bios, size_t *cursor,
                                   uint8_t reg, uint8_t value) {
    bios[(*cursor)++] = 0x3eu; bios[(*cursor)++] = reg;
    bios[(*cursor)++] = 0xd3u; bios[(*cursor)++] = 0x04u;
    bios[(*cursor)++] = 0x3eu; bios[(*cursor)++] = value;
    bios[(*cursor)++] = 0xd3u; bios[(*cursor)++] = 0x05u;
}

static void pcm_test_build_audio_bios(uint8_t *bios) {
    memset(bios, 0, GN_MVS_AUDIO_BIOS_BYTES);
    const uint8_t boot[] = {
        0x31u, 0xffu, 0xffu, /* LD SP,$ffff */
        0x3eu, 0x00u, 0xd3u, 0x08u, /* enable command NMI */
        0xfbu, 0x76u, 0x18u, 0xfdu /* EI; HALT; JR HALT */
    };
    memcpy(bios, boot, sizeof(boot));

    size_t cursor = 0x66u; /* synthetic Z80 NMI handler */
    bios[cursor++] = 0xdbu; bios[cursor++] = 0x00u; /* IN A,($00), consume */
    bios[cursor++] = 0xd3u; bios[cursor++] = 0x0cu; /* publish handled command */
    bios[cursor++] = 0xfeu; bios[cursor++] = 0x3cu; /* CP $3c: tone on */
    bios[cursor++] = 0x28u;
    const size_t on_displacement = cursor++;
    bios[cursor++] = 0xfeu; bios[cursor++] = 0x00u; /* CP $00: key off */
    bios[cursor++] = 0x28u;
    const size_t off_displacement = cursor++;
    bios[cursor++] = 0xedu; bios[cursor++] = 0x45u; /* RETN: wrong command */

    const size_t on_handler = cursor;
    pcm_test_emit_ym_write(bios, &cursor, 0u, 0x7du); /* tone A period 125 */
    pcm_test_emit_ym_write(bios, &cursor, 1u, 0x00u);
    pcm_test_emit_ym_write(bios, &cursor, 7u, 0x3eu); /* tone A only */
    pcm_test_emit_ym_write(bios, &cursor, 8u, 0x0fu); /* max fixed volume */
    bios[cursor++] = 0xedu; bios[cursor++] = 0x45u;

    const size_t off_handler = cursor;
    pcm_test_emit_ym_write(bios, &cursor, 8u, 0x00u);
    bios[cursor++] = 0xedu; bios[cursor++] = 0x45u;
    bios[on_displacement] = (uint8_t)(on_handler - (on_displacement + 1u));
    bios[off_displacement] = (uint8_t)(off_handler - (off_displacement + 1u));
}

static gn_mvs_frame_request_v1 pcm_test_request(uint32_t input_mask,
                                                uint32_t *pixels,
                                                size_t pixel_bytes,
                                                int16_t *audio,
                                                size_t audio_frames) {
    return (gn_mvs_frame_request_v1){
        GN_MVS_FRAME_REQUEST_V1_VERSION, input_mask, GN_PIXEL_XRGB8888,
        320u, 224u, (size_t)320u * sizeof(uint32_t), (uint8_t *)pixels,
        pixel_bytes, audio, audio_frames
    };
}

static void pcm_test_check_tone(const int16_t *pcm, size_t frames) {
    assert(frames >= 800u && frames <= GN_MVS_AUDIO_CAPACITY_FRAMES_V1);
    int64_t best = 0;
    for (size_t offset = 0u; offset < 48u; ++offset) {
        int64_t correlation = 0;
        for (size_t frame = 32u; frame < 800u; ++frame) {
            const int sign = ((frame + offset) % 48u) < 24u ? 1 : -1;
            const int16_t left = pcm[frame * 2u];
            const int16_t right = pcm[frame * 2u + 1u];
            assert(left == right);
            correlation += (int64_t)left * sign;
        }
        const int64_t magnitude = correlation < 0 ? -correlation : correlation;
        if (magnitude > best) best = magnitude;
    }
    assert(best / INT64_C(768) >= INT64_C(256));
}

static void pcm_test_check_silence(const int16_t *pcm, size_t frames) {
    for (size_t frame = 0u; frame < frames; ++frame)
        assert(pcm[frame * 2u] == 0 && pcm[frame * 2u + 1u] == 0);
}

static void check_mvs_pcm_streaming_converter(void) {
    const size_t source_frames = 500000u;
    const size_t max_partition = 8454u;
    const size_t partition_count =
        (source_frames + max_partition - 1u) / max_partition;
    int32_t *triplets = (int32_t *)malloc(source_frames * 3u * sizeof(int32_t));
    size_t *partitions = (size_t *)malloc(partition_count * sizeof(size_t));
    const size_t output_capacity = 48000u;
    int16_t *output = (int16_t *)malloc(output_capacity * 2u * sizeof(int16_t));
    assert(triplets != NULL && partitions != NULL && output != NULL);
    for (size_t sample = 0u; sample < source_frames; ++sample) {
        triplets[sample * 3u] = 10000;
        triplets[sample * 3u + 1u] = -10000;
        triplets[sample * 3u + 2u] = 4000;
    }
    size_t partitioned = 0u;
    for (size_t index = 0u; index < partition_count; ++index) {
        const size_t remaining = source_frames - partitioned;
        partitions[index] = remaining < max_partition ? remaining : max_partition;
        partitioned += partitions[index];
    }
    assert(partitioned == source_frames);
    size_t output_frames = 0u;
    assert(gn_test_mvs_pcm_convert(triplets, source_frames, partitions,
                                   partition_count, output, output_capacity,
                                   &output_frames));
    assert(output_frames == 48000u);
    for (size_t frame = 32u; frame < output_frames; ++frame) {
        assert(output[frame * 2u] == 6000);
        assert(output[frame * 2u + 1u] == -4000);
        assert(output[frame * 2u] > INT16_MIN &&
               output[frame * 2u] < INT16_MAX);
        assert(output[frame * 2u + 1u] > INT16_MIN &&
               output[frame * 2u + 1u] < INT16_MAX);
    }
    free(output);
    free(partitions);
    free(triplets);

    enum { SHORT_FRAMES = 4000u, IMPULSE_FRAMES = 512u };
    const size_t short_frames = SHORT_FRAMES;
    const size_t partition_sizes[] = {13u, 125u, 126u, 2047u, 1689u};
    int32_t short_triplets[SHORT_FRAMES * 3u];
    for (size_t sample = 0u; sample < short_frames; ++sample) {
        short_triplets[sample * 3u] = (int32_t)((sample * 73u) % 40001u) - 20000;
        short_triplets[sample * 3u + 1u] = (int32_t)((sample * 97u) % 30001u) - 15000;
        short_triplets[sample * 3u + 2u] = (int32_t)((sample * 29u) % 12001u);
    }
    int16_t one_chunk[400u * 2u];
    int16_t split_chunks[400u * 2u];
    size_t one_count = 0u, split_count = 0u;
    const size_t one_partition[] = {short_frames};
    assert(gn_test_mvs_pcm_convert(short_triplets, short_frames, one_partition,
                                   1u, one_chunk, 400u, &one_count));
    assert(gn_test_mvs_pcm_convert(short_triplets, short_frames, partition_sizes,
                                   sizeof(partition_sizes) / sizeof(partition_sizes[0]),
                                   split_chunks, 400u, &split_count));
    assert(one_count == split_count);
    assert(memcmp(one_chunk, split_chunks,
                  one_count * 2u * sizeof(int16_t)) == 0);

    const size_t impulse_frames = IMPULSE_FRAMES;
    int32_t impulse[IMPULSE_FRAMES * 3u] = {0};
    impulse[0] = 30000;
    int16_t impulse_output[64u * 2u];
    size_t impulse_count = 0u;
    const size_t impulse_partition[] = {impulse_frames};
    assert(gn_test_mvs_pcm_convert(impulse, impulse_frames, impulse_partition,
                                   1u, impulse_output, 64u, &impulse_count));
    int64_t peak = 0;
    size_t peak_frame = 0u;
    for (size_t frame = 0u; frame < impulse_count; ++frame) {
        assert(impulse_output[frame * 2u + 1u] == 0);
        const int64_t sample = impulse_output[frame * 2u];
        const int64_t magnitude = sample < 0 ? -sample : sample;
        if (magnitude > peak) {
            peak = magnitude;
            peak_frame = frame;
        }
    }
    assert(peak > 1000 && peak_frame >= 3u && peak_frame <= 5u);

    /* The inputs here intentionally exceed YMFM's signed-16 FM range. This
     * isolates the converter's specified final S16 clamp from chip headroom. */
    enum { OVER_RANGE_FRAMES = 600 };
    int32_t over_range[OVER_RANGE_FRAMES * 3u];
    for (size_t sample = 0u; sample < OVER_RANGE_FRAMES; ++sample) {
        over_range[sample * 3u] = 100000;
        over_range[sample * 3u + 1u] = -100000;
        over_range[sample * 3u + 2u] = 0;
    }
    const size_t over_range_partition[] = {OVER_RANGE_FRAMES};
    int16_t clipped_output[64u * 2u];
    size_t clipped_count = 0u;
    assert(gn_test_mvs_pcm_convert(
        over_range, OVER_RANGE_FRAMES, over_range_partition, 1u,
        clipped_output, 64u, &clipped_count));
    assert(clipped_count == 57u);
    for (size_t frame = 20u; frame < clipped_count; ++frame) {
        assert(clipped_output[frame * 2u] == INT16_MAX);
        assert(clipped_output[frame * 2u + 1u] == INT16_MIN);
    }
}

static void check_mvs_pcm_rejects_misaligned_audio(const uint8_t *bundle,
                                                  size_t bundle_size) {
    guest_media media;
    open_guest_media(bundle, bundle_size, &media);
    pcm_test_build_audio_bios(media.audio_bios);
    uint8_t *main_code = emit_move_b_imm(media.bios + 0x100u,
                                        0x3cu, UINT32_C(0x320000));
    emit_stop(main_code);
    gn_instance *instance = bb_start(&media);
    const size_t pixel_bytes = (size_t)320u * (size_t)224u * sizeof(uint32_t);
    uint32_t *pixels = (uint32_t *)malloc(pixel_bytes);
    assert(pixels != NULL);
    union {
        uint64_t alignment;
        uint8_t bytes[1u + GN_MVS_AUDIO_CAPACITY_FRAMES_V1 * 2u * sizeof(int16_t)];
    } audio_storage;
    memset(pixels, 0xa5, pixel_bytes);
    memset(audio_storage.bytes, 0x5a, sizeof(audio_storage.bytes));
    gn_mvs_frame_request_v1 request = pcm_test_request(
        0u, pixels, pixel_bytes,
        (int16_t *)(void *)(audio_storage.bytes + 1u),
        GN_MVS_AUDIO_CAPACITY_FRAMES_V1);
    gn_mvs_frame_result_v1 result;
    memset(&result, 0xa5, sizeof(result));
    assert(gn_mvs_advance_frame_v1(instance, &request, sizeof(request), &result,
                                   sizeof(result)) == GN_STATUS_INVALID_ARGUMENT);
    const uint8_t *result_bytes = (const uint8_t *)&result;
    for (size_t index = 0u; index < sizeof(result); ++index)
        assert(result_bytes[index] == 0xa5u);
    const uint8_t *pixel_bytes_view = (const uint8_t *)pixels;
    for (size_t index = 0u; index < pixel_bytes; ++index)
        assert(pixel_bytes_view[index] == 0xa5u);
    for (size_t index = 0u; index < sizeof(audio_storage.bytes); ++index)
        assert(audio_storage.bytes[index] == 0x5au);
    gn_destroy(instance);
    free(media.copy);
    free(pixels);
}

static void pcm_test_prepare_guest(const uint8_t *bundle, size_t bundle_size,
                                   guest_media *media) {
    open_guest_media(bundle, bundle_size, media);
    pcm_test_build_audio_bios(media->audio_bios);
    uint8_t *code = emit_move_b_imm(media->bios + 0x100u,
                                    0x3cu, UINT32_C(0x320000));
    code = emit16(code, 0x4e71u); /* NOP */
    emit16(code, 0x60fcu);        /* BRA.S back to NOP */
}

/* A reference trace of actual execution chooses the single-call target. This
 * rejects equal requested budgets as a clock oracle and compares only exact
 * reachable instruction/event boundaries. */
static void check_mvs_pcm_actual_boundary_partition(const uint8_t *bundle,
                                                     size_t bundle_size) {
    guest_media media;
    open_guest_media(bundle, bundle_size, &media);
    pcm_test_build_audio_bios(media.audio_bios);
    uint8_t *main_code = emit_move_b_imm(media.bios + 0x100u,
                                        0x3cu, UINT32_C(0x320000));
    emit_stop(main_code);
    gn_instance *partitioned = bb_start(&media);
    gn_instance *single = bb_start(&media);
    static const uint64_t requests[] = {10001u, 10003u, 10007u};
    const size_t capacity = GN_MVS_AUDIO_CAPACITY_FRAMES_V1;
    int16_t *piece = (int16_t *)malloc((capacity + 1u) * 2u * sizeof(int16_t));
    int16_t *joined = (int16_t *)malloc(capacity * 2u * sizeof(int16_t));
    int16_t *whole = (int16_t *)malloc(capacity * 2u * sizeof(int16_t));
    const size_t pixel_bytes = (size_t)320u * 224u * sizeof(uint32_t);
    uint32_t *pixels_partitioned = (uint32_t *)malloc(pixel_bytes);
    uint32_t *pixels_single = (uint32_t *)malloc(pixel_bytes);
    assert(piece != NULL && joined != NULL && whole != NULL &&
           pixels_partitioned != NULL && pixels_single != NULL);
    size_t joined_frames = 0u;
    uint64_t actual_total = 0u;
    int phase125_nonzero = 0;
    int phase3_nonzero = 0;
    int phase16_nonzero = 0;
    for (size_t index = 0u; index < sizeof(requests) / sizeof(requests[0]);
         ++index) {
        memset(piece, 0x5a, (capacity + 1u) * 2u * sizeof(int16_t));
        gn_run_result run;
        size_t frames = 0u;
        assert(gn_test_mvs_run_with_pcm_capture(
                   partitioned, requests[index], piece, capacity, &run,
                   &frames) == GN_STATUS_OK);
        assert(run.elapsed_cycles >= requests[index] &&
               run.elapsed_cycles - requests[index] <= UINT64_C(131));
        assert(frames <= capacity && frames <= capacity - joined_frames);
        const uint8_t *piece_bytes = (const uint8_t *)piece;
        for (size_t sample = frames * 2u; sample < (capacity + 1u) * 2u;
             ++sample) {
            assert(piece_bytes[sample * sizeof(int16_t)] == 0x5au &&
                   piece_bytes[sample * sizeof(int16_t) + 1u] == 0x5au);
        }
        memcpy(joined + joined_frames * 2u, piece,
               frames * 2u * sizeof(int16_t));
        joined_frames += frames;
        actual_total += run.elapsed_cycles;
        gn_test_mvs_sound_state checkpoint;
        assert(gn_test_mvs_sound_state_read(partitioned, &checkpoint) ==
               GN_STATUS_OK);
        if (checkpoint.pcm_output_phase != 0u) phase125_nonzero = 1;
        if (checkpoint.main_clock_remainder != 0u) phase3_nonzero = 1;
        if (checkpoint.ym_clock_remainder != 0u) phase16_nonzero = 1;
    }
    memset(whole, 0x5a, capacity * 2u * sizeof(int16_t));
    gn_run_result whole_run;
    size_t whole_frames = 0u;
    assert(gn_test_mvs_run_with_pcm_capture(
               single, actual_total, whole, capacity, &whole_run,
               &whole_frames) == GN_STATUS_OK);
    if (whole_run.elapsed_cycles != actual_total) {
        (void)printf("MVS_PCM_PARTITION unsupported requested=%llu actual=%llu; "
                     "reference boundary was not reached exactly\n",
                     (unsigned long long)actual_total,
                     (unsigned long long)whole_run.elapsed_cycles);
        goto cleanup;
    }
    assert(whole_frames == joined_frames);
    assert(memcmp(whole, joined, joined_frames * 2u * sizeof(int16_t)) == 0);
    gn_mvs_private_video_activity video_partitioned, video_single;
    assert(gn_private_mvs_video_activity(partitioned, &video_partitioned) ==
           GN_STATUS_OK);
    assert(gn_private_mvs_video_activity(single, &video_single) == GN_STATUS_OK);
    assert(memcmp(&video_partitioned, &video_single,
                  sizeof(video_partitioned)) == 0);
    size_t produced_partitioned = 0u, produced_single = 0u;
    assert(gn_private_mvs_render_frame(partitioned, 320u, 224u,
               (size_t)320u * sizeof(uint32_t), (uint8_t *)pixels_partitioned,
               pixel_bytes, &produced_partitioned) == GN_STATUS_OK);
    assert(gn_private_mvs_render_frame(single, 320u, 224u,
               (size_t)320u * sizeof(uint32_t), (uint8_t *)pixels_single,
               pixel_bytes, &produced_single) == GN_STATUS_OK);
    assert(produced_partitioned == (size_t)320u * 224u &&
           produced_single == produced_partitioned);
    assert(memcmp(pixels_partitioned, pixels_single, pixel_bytes) == 0);
    gn_mvs_bus_fault_observation bus_partitioned, bus_single;
    memset(&bus_partitioned, 0, sizeof(bus_partitioned));
    memset(&bus_single, 0, sizeof(bus_single));
    assert(gn_observe_mvs_bus_fault(partitioned, &bus_partitioned,
               sizeof(bus_partitioned)) == GN_STATUS_OK);
    assert(gn_observe_mvs_bus_fault(single, &bus_single,
               sizeof(bus_single)) == GN_STATUS_OK);
    assert(memcmp(&bus_partitioned, &bus_single, sizeof(bus_partitioned)) == 0);
    gn_test_mvs_sound_state sound_partitioned, sound_single;
    assert(gn_test_mvs_sound_state_read(partitioned, &sound_partitioned) ==
           GN_STATUS_OK);
    assert(gn_test_mvs_sound_state_read(single, &sound_single) == GN_STATUS_OK);
    assert(memcmp(&sound_partitioned, &sound_single,
                  sizeof(sound_partitioned)) == 0);
    assert(sound_partitioned.main_cycles_advanced == actual_total &&
           sound_partitioned.native_samples != 0u &&
           phase125_nonzero != 0 && phase3_nonzero != 0 &&
           phase16_nonzero != 0);
    (void)printf("MVS_PCM_PARTITION supported requests=3 actual_clocks=%llu "
                 "pcm_frames=%zu native_samples=%llu\n",
                 (unsigned long long)actual_total, joined_frames,
                 (unsigned long long)sound_partitioned.native_samples);
cleanup:
    gn_destroy(single);
    gn_destroy(partitioned);
    free(pixels_single);
    free(pixels_partitioned);
    free(whole);
    free(joined);
    free(piece);
    free(media.copy);
}

static void pcm_test_expect_preflight_rejection(
    gn_instance *instance, const gn_mvs_frame_request_v1 *request,
    size_t request_size, size_t result_size, uint32_t *pixels,
    size_t pixel_bytes, int16_t *audio, size_t audio_frames) {
    gn_mvs_frame_result_v1 result;
    memset(&result, 0xc3, sizeof(result));
    memset(pixels, 0xa5, pixel_bytes);
    memset(audio, 0x5a, audio_frames * (size_t)2u * sizeof(int16_t));
    assert(gn_mvs_advance_frame_v1(instance, request, request_size, &result,
                                   result_size) == GN_STATUS_INVALID_ARGUMENT);
    const uint8_t *result_bytes = (const uint8_t *)&result;
    for (size_t index = 0u; index < sizeof(result); ++index)
        assert(result_bytes[index] == 0xc3u);
    const uint8_t *pixel_bytes_view = (const uint8_t *)pixels;
    for (size_t index = 0u; index < pixel_bytes; ++index)
        assert(pixel_bytes_view[index] == 0xa5u);
    const uint8_t *audio_bytes_view = (const uint8_t *)audio;
    for (size_t index = 0u;
         index < audio_frames * (size_t)2u * sizeof(int16_t); ++index)
        assert(audio_bytes_view[index] == 0x5au);
}

static void pcm_test_same_execution(const gn_mvs_frame_result_v1 *first,
                                    const gn_mvs_frame_result_v1 *second) {
    assert(first->version == second->version);
    assert(first->requested_cycles == second->requested_cycles);
    assert(first->elapsed_cycles == second->elapsed_cycles);
    assert(first->instructions == second->instructions);
    assert(first->frame_time_numerator == second->frame_time_numerator);
    assert(first->frame_time_denominator == second->frame_time_denominator);
    assert(first->machine_clock_hz_numerator ==
           second->machine_clock_hz_numerator);
    assert(first->machine_clock_hz_denominator ==
           second->machine_clock_hz_denominator);
    assert(first->reason == second->reason);
    assert(first->audio_format == second->audio_format);
    assert(first->audio_sample_rate == second->audio_sample_rate);
    assert(first->audio_channels == second->audio_channels);
    assert(first->video_pixels_produced == second->video_pixels_produced);
}

static void check_mvs_pcm_preflight_and_discard(const uint8_t *bundle,
                                               size_t bundle_size) {
    guest_media media;
    pcm_test_prepare_guest(bundle, bundle_size, &media);
    const size_t pixel_bytes = (size_t)320u * (size_t)224u * sizeof(uint32_t);
    const size_t capacity = GN_MVS_AUDIO_CAPACITY_FRAMES_V1;
    const size_t storage_frames = capacity + 1u;
    uint32_t *pixels_a = (uint32_t *)malloc(pixel_bytes);
    uint32_t *pixels_b = (uint32_t *)malloc(pixel_bytes);
    int16_t *audio_a = (int16_t *)malloc(storage_frames * 2u * sizeof(int16_t));
    int16_t *audio_b = (int16_t *)malloc(storage_frames * 2u * sizeof(int16_t));
    assert(pixels_a != NULL && pixels_b != NULL && audio_a != NULL &&
           audio_b != NULL);

    gn_instance *preflight = bb_start(&media);
    gn_instance *control = bb_start(&media);
    size_t queried = 0u;
    assert(gn_mvs_audio_capacity_v1(preflight, &queried) == GN_STATUS_OK &&
           queried == capacity);
    gn_mvs_frame_request_v1 request = pcm_test_request(
        0u, pixels_a, pixel_bytes, audio_a, capacity);
    pcm_test_expect_preflight_rejection(
        preflight, &request, sizeof(request) - 1u, sizeof(gn_mvs_frame_result_v1),
        pixels_a, pixel_bytes, audio_a, storage_frames);
    pcm_test_expect_preflight_rejection(
        preflight, &request, sizeof(request), sizeof(gn_mvs_frame_result_v1) - 1u,
        pixels_a, pixel_bytes, audio_a, storage_frames);
    gn_mvs_frame_request_v1 invalid = request;
    invalid.version++;
    pcm_test_expect_preflight_rejection(
        preflight, &invalid, sizeof(invalid), sizeof(gn_mvs_frame_result_v1),
        pixels_a, pixel_bytes, audio_a, storage_frames);
    invalid = request;
    invalid.input_mask = UINT32_MAX;
    pcm_test_expect_preflight_rejection(
        preflight, &invalid, sizeof(invalid), sizeof(gn_mvs_frame_result_v1),
        pixels_a, pixel_bytes, audio_a, storage_frames);
    invalid = request;
    invalid.audio = NULL;
    invalid.audio_capacity_frames = 1u;
    pcm_test_expect_preflight_rejection(
        preflight, &invalid, sizeof(invalid), sizeof(gn_mvs_frame_result_v1),
        pixels_a, pixel_bytes, audio_a, storage_frames);
    invalid = request;
    invalid.audio_capacity_frames = 0u;
    pcm_test_expect_preflight_rejection(
        preflight, &invalid, sizeof(invalid), sizeof(gn_mvs_frame_result_v1),
        pixels_a, pixel_bytes, audio_a, storage_frames);
    invalid = request;
    invalid.audio_capacity_frames = capacity - 1u;
    pcm_test_expect_preflight_rejection(
        preflight, &invalid, sizeof(invalid), sizeof(gn_mvs_frame_result_v1),
        pixels_a, pixel_bytes, audio_a, storage_frames);
    invalid = request;
    invalid.pitch_bytes = SIZE_MAX;
    pcm_test_expect_preflight_rejection(
        preflight, &invalid, sizeof(invalid), sizeof(gn_mvs_frame_result_v1),
        pixels_a, pixel_bytes, audio_a, storage_frames);
    invalid = request;
    invalid.pixel_capacity_bytes = SIZE_MAX;
    pcm_test_expect_preflight_rejection(
        preflight, &invalid, sizeof(invalid), sizeof(gn_mvs_frame_result_v1),
        pixels_a, pixel_bytes, audio_a, storage_frames);
    invalid = request;
    invalid.audio_capacity_frames = SIZE_MAX;
    pcm_test_expect_preflight_rejection(
        preflight, &invalid, sizeof(invalid), sizeof(gn_mvs_frame_result_v1),
        pixels_a, pixel_bytes, audio_a, storage_frames);

    gn_mvs_frame_result_v1 alias_result;
    memset(&alias_result, 0xc3, sizeof(alias_result));
    memset(pixels_a, 0xa5, pixel_bytes);
    invalid = request;
    invalid.audio = (int16_t *)(void *)pixels_a;
    assert(gn_mvs_advance_frame_v1(preflight, &invalid, sizeof(invalid),
                                   &alias_result, sizeof(alias_result)) ==
           GN_STATUS_INVALID_ARGUMENT);
    for (size_t index = 0u; index < sizeof(alias_result); ++index)
        assert(((const uint8_t *)&alias_result)[index] == 0xc3u);
    for (size_t index = 0u; index < pixel_bytes; ++index)
        assert(((const uint8_t *)pixels_a)[index] == 0xa5u);

    memset(&alias_result, 0xc3, sizeof(alias_result));
    invalid = request;
    invalid.pixels = (uint8_t *)&alias_result;
    assert(gn_mvs_advance_frame_v1(preflight, &invalid, sizeof(invalid),
                                   &alias_result, sizeof(alias_result)) ==
           GN_STATUS_INVALID_ARGUMENT);
    for (size_t index = 0u; index < sizeof(alias_result); ++index)
        assert(((const uint8_t *)&alias_result)[index] == 0xc3u);

    size_t capacity_after_rejections = 0u;
    assert(gn_mvs_audio_capacity_v1(preflight, &capacity_after_rejections) ==
           GN_STATUS_OK && capacity_after_rejections == capacity);
    memset(pixels_a, 0, pixel_bytes);
    memset(pixels_b, 0, pixel_bytes);
    memset(audio_a, 0x5a, storage_frames * 2u * sizeof(int16_t));
    memset(audio_b, 0x5a, storage_frames * 2u * sizeof(int16_t));
    request = pcm_test_request(0u, pixels_a, pixel_bytes, audio_a, capacity);
    gn_mvs_frame_result_v1 first_result, second_result;
    assert(gn_mvs_advance_frame_v1(preflight, &request, sizeof(request),
                                   &first_result, sizeof(first_result)) == GN_STATUS_OK);
    request = pcm_test_request(0u, pixels_b, pixel_bytes, audio_b, capacity);
    assert(gn_mvs_advance_frame_v1(control, &request, sizeof(request),
                                   &second_result, sizeof(second_result)) == GN_STATUS_OK);
    pcm_test_same_execution(&first_result, &second_result);
    assert(first_result.audio_frames_generated ==
           first_result.audio_frames_delivered);
    assert(first_result.audio_frames_discarded == 0u);
    assert(memcmp(pixels_a, pixels_b, pixel_bytes) == 0);
    assert(memcmp(audio_a, audio_b,
                  storage_frames * 2u * sizeof(int16_t)) == 0);
    for (size_t index = first_result.audio_frames_delivered * 2u * sizeof(int16_t);
         index < storage_frames * 2u * sizeof(int16_t); ++index)
        assert(((const uint8_t *)audio_a)[index] == 0x5au);

    /* Oversized caller capacity is accepted, with the bounded frame prefix
     * written and every byte after it retained as a canary. */
    memset(pixels_b, 0, pixel_bytes);
    memset(audio_b, 0x5a, storage_frames * 2u * sizeof(int16_t));
    request = pcm_test_request(0u, pixels_b, pixel_bytes, audio_b, capacity + 1u);
    assert(gn_mvs_advance_frame_v1(control, &request, sizeof(request),
                                   &second_result, sizeof(second_result)) == GN_STATUS_OK);
    assert(second_result.audio_frames_delivered <= capacity);
    for (size_t index = second_result.audio_frames_delivered * 2u * sizeof(int16_t);
         index < storage_frames * 2u * sizeof(int16_t); ++index)
        assert(((const uint8_t *)audio_b)[index] == 0x5au);

    gn_instance *discard = bb_start(&media);
    gn_instance *capture = bb_start(&media);
    gn_instance *plain_run = bb_start(&media);
    memset(pixels_a, 0, pixel_bytes);
    memset(pixels_b, 0, pixel_bytes);
    request = pcm_test_request(0u, pixels_a, pixel_bytes, NULL, 0u);
    assert(gn_mvs_advance_frame_v1(discard, &request, sizeof(request),
                                   &first_result, sizeof(first_result)) == GN_STATUS_OK);
    request = pcm_test_request(0u, pixels_b, pixel_bytes, audio_b, capacity);
    memset(audio_b, 0x5a, storage_frames * 2u * sizeof(int16_t));
    assert(gn_mvs_advance_frame_v1(capture, &request, sizeof(request),
                                   &second_result, sizeof(second_result)) == GN_STATUS_OK);
    pcm_test_same_execution(&first_result, &second_result);
    assert(first_result.audio_frames_generated ==
           second_result.audio_frames_generated);
    assert(first_result.audio_frames_delivered == 0u &&
           first_result.audio_frames_discarded ==
               first_result.audio_frames_generated);
    assert(second_result.audio_frames_delivered ==
           second_result.audio_frames_generated &&
           second_result.audio_frames_discarded == 0u);
    assert(memcmp(pixels_a, pixels_b, pixel_bytes) == 0);

    gn_run_result raw_run;
    assert(gn_run_mvs(plain_run, GN_MVS_FRAME_BUDGET_CYCLES, &raw_run) ==
           GN_STATUS_OK);
    assert(raw_run.requested_cycles == first_result.requested_cycles &&
           raw_run.elapsed_cycles == first_result.elapsed_cycles &&
           raw_run.instructions == first_result.instructions);
    memset(audio_a, 0x5a, storage_frames * 2u * sizeof(int16_t));
    memset(audio_b, 0x5a, storage_frames * 2u * sizeof(int16_t));
    memset(pixels_a, 0, pixel_bytes);
    memset(pixels_b, 0, pixel_bytes);
    request = pcm_test_request(0u, pixels_a, pixel_bytes, audio_a, capacity);
    assert(gn_mvs_advance_frame_v1(discard, &request, sizeof(request),
                                   &first_result, sizeof(first_result)) == GN_STATUS_OK);
    request = pcm_test_request(0u, pixels_b, pixel_bytes, audio_b, capacity);
    assert(gn_mvs_advance_frame_v1(capture, &request, sizeof(request),
                                   &second_result, sizeof(second_result)) == GN_STATUS_OK);
    pcm_test_same_execution(&first_result, &second_result);
    assert(first_result.audio_frames_delivered ==
           second_result.audio_frames_delivered);
    assert(memcmp(audio_a, audio_b,
                  storage_frames * 2u * sizeof(int16_t)) == 0);
    memset(audio_b, 0x5a, storage_frames * 2u * sizeof(int16_t));
    request = pcm_test_request(0u, pixels_b, pixel_bytes, audio_b, capacity);
    assert(gn_mvs_advance_frame_v1(plain_run, &request, sizeof(request),
                                   &second_result, sizeof(second_result)) == GN_STATUS_OK);
    assert(second_result.audio_frames_delivered == first_result.audio_frames_delivered);
    assert(memcmp(audio_a, audio_b,
                  storage_frames * 2u * sizeof(int16_t)) == 0);

    gn_destroy(plain_run);
    gn_destroy(capture);
    gn_destroy(discard);
    gn_destroy(control);
    gn_destroy(preflight);
    free(audio_b);
    free(audio_a);
    free(pixels_b);
    free(pixels_a);
    free(media.copy);
}

static void check_mvs_pcm_lifecycle_and_failure(const uint8_t *bundle,
                                               size_t bundle_size) {
    guest_media media;
    pcm_test_prepare_guest(bundle, bundle_size, &media);
    const size_t pixel_bytes = (size_t)320u * (size_t)224u * sizeof(uint32_t);
    const size_t capacity = GN_MVS_AUDIO_CAPACITY_FRAMES_V1;
    const size_t storage_frames = capacity + 1u;
    uint32_t *pixels_a = (uint32_t *)malloc(pixel_bytes);
    uint32_t *pixels_b = (uint32_t *)malloc(pixel_bytes);
    int16_t *audio_a = (int16_t *)malloc(storage_frames * 2u * sizeof(int16_t));
    int16_t *audio_b = (int16_t *)malloc(storage_frames * 2u * sizeof(int16_t));
    assert(pixels_a != NULL && pixels_b != NULL && audio_a != NULL &&
           audio_b != NULL);

    gn_instance *subject = bb_start(&media);
    gn_instance *peer = bb_start(&media);
    gn_instance *peer_reference = bb_start(&media);
    gn_mvs_frame_result_v1 first, second;
    gn_mvs_frame_request_v1 request = pcm_test_request(
        0u, pixels_a, pixel_bytes, audio_a, capacity);
    assert(gn_mvs_advance_frame_v1(subject, &request, sizeof(request), &first,
                                   sizeof(first)) == GN_STATUS_OK);
    request = pcm_test_request(0u, pixels_b, pixel_bytes, audio_b, capacity);
    assert(gn_mvs_advance_frame_v1(peer, &request, sizeof(request), &second,
                                   sizeof(second)) == GN_STATUS_OK);
    request = pcm_test_request(0u, pixels_b, pixel_bytes, audio_b, capacity);
    assert(gn_mvs_advance_frame_v1(peer_reference, &request, sizeof(request),
                                   &second, sizeof(second)) == GN_STATUS_OK);

    assert(gn_reset(subject) == GN_STATUS_OK);
    gn_instance *fresh = bb_start(&media);
    memset(audio_a, 0x5a, storage_frames * 2u * sizeof(int16_t));
    memset(audio_b, 0x5a, storage_frames * 2u * sizeof(int16_t));
    request = pcm_test_request(0u, pixels_a, pixel_bytes, audio_a, capacity);
    assert(gn_mvs_advance_frame_v1(subject, &request, sizeof(request), &first,
                                   sizeof(first)) == GN_STATUS_OK);
    request = pcm_test_request(0u, pixels_b, pixel_bytes, audio_b, capacity);
    assert(gn_mvs_advance_frame_v1(fresh, &request, sizeof(request), &second,
                                   sizeof(second)) == GN_STATUS_OK);
    pcm_test_same_execution(&first, &second);
    assert(memcmp(audio_a, audio_b,
                  storage_frames * 2u * sizeof(int16_t)) == 0);
    assert(memcmp(pixels_a, pixels_b, pixel_bytes) == 0);

    /* A rejected replacement load leaves the live machine and its history
     * unchanged. */
    gn_mvs_manifest invalid_manifest = media.manifest;
    invalid_manifest.region_count--;
    assert(gn_load_mvs(subject, &invalid_manifest) == GN_STATUS_INVALID_MEDIA);
    memset(audio_a, 0x5a, storage_frames * 2u * sizeof(int16_t));
    memset(audio_b, 0x5a, storage_frames * 2u * sizeof(int16_t));
    request = pcm_test_request(0u, pixels_a, pixel_bytes, audio_a, capacity);
    assert(gn_mvs_advance_frame_v1(subject, &request, sizeof(request), &first,
                                   sizeof(first)) == GN_STATUS_OK);
    request = pcm_test_request(0u, pixels_b, pixel_bytes, audio_b, capacity);
    assert(gn_mvs_advance_frame_v1(fresh, &request, sizeof(request), &second,
                                   sizeof(second)) == GN_STATUS_OK);
    pcm_test_same_execution(&first, &second);
    assert(memcmp(audio_a, audio_b,
                  storage_frames * 2u * sizeof(int16_t)) == 0);

    assert(gn_unload(subject) == GN_STATUS_OK);
    size_t capacity_after_unload = 77u;
    assert(gn_mvs_audio_capacity_v1(subject, &capacity_after_unload) ==
           GN_STATUS_INVALID_STATE);
    assert(capacity_after_unload == 77u);
    assert(gn_load_mvs(subject, &invalid_manifest) == GN_STATUS_INVALID_MEDIA);
    assert(gn_load_mvs(subject, &media.manifest) == GN_STATUS_OK);
    gn_instance *reload_reference = bb_start(&media);
    memset(audio_a, 0x5a, storage_frames * 2u * sizeof(int16_t));
    memset(audio_b, 0x5a, storage_frames * 2u * sizeof(int16_t));
    request = pcm_test_request(0u, pixels_a, pixel_bytes, audio_a, capacity);
    assert(gn_mvs_advance_frame_v1(subject, &request, sizeof(request), &first,
                                   sizeof(first)) == GN_STATUS_OK);
    request = pcm_test_request(0u, pixels_b, pixel_bytes, audio_b, capacity);
    assert(gn_mvs_advance_frame_v1(reload_reference, &request, sizeof(request),
                                   &second, sizeof(second)) == GN_STATUS_OK);
    pcm_test_same_execution(&first, &second);
    assert(memcmp(audio_a, audio_b,
                  storage_frames * 2u * sizeof(int16_t)) == 0);

    /* Reset and unload of the subject have not disturbed the peer's stream. */
    memset(audio_a, 0x5a, storage_frames * 2u * sizeof(int16_t));
    memset(audio_b, 0x5a, storage_frames * 2u * sizeof(int16_t));
    request = pcm_test_request(0u, pixels_a, pixel_bytes, audio_a, capacity);
    assert(gn_mvs_advance_frame_v1(peer, &request, sizeof(request), &first,
                                   sizeof(first)) == GN_STATUS_OK);
    request = pcm_test_request(0u, pixels_b, pixel_bytes, audio_b, capacity);
    assert(gn_mvs_advance_frame_v1(peer_reference, &request, sizeof(request),
                                   &second, sizeof(second)) == GN_STATUS_OK);
    pcm_test_same_execution(&first, &second);
    assert(memcmp(audio_a, audio_b,
                  storage_frames * 2u * sizeof(int16_t)) == 0);

    /* A fault after VBlank reports the real clock prefix and the audio prefix
     * already written. Rendering does not begin after the failed run. */
    gn_instance *fault = bb_start(&media);
    assert(gn_test_mvs_set_failure(fault,
        GN_TEST_MVS_FAILURE_MAIN_IRQ_UPDATE) == GN_STATUS_OK);
    memset(pixels_a, 0xa5, pixel_bytes);
    memset(audio_a, 0x5a, storage_frames * 2u * sizeof(int16_t));
    request = pcm_test_request(0u, pixels_a, pixel_bytes, audio_a, capacity);
    const gn_status fault_status = gn_mvs_advance_frame_v1(
        fault, &request, sizeof(request), &first, sizeof(first));
    assert(fault_status == GN_STATUS_CPU_FAILURE && first.reason == GN_RUN_ERROR);
    assert(first.elapsed_cycles > 0u && first.elapsed_cycles < first.requested_cycles);
    assert(first.audio_frames_generated > 0u &&
           first.audio_frames_delivered == first.audio_frames_generated &&
           first.audio_frames_discarded == 0u);
    assert(first.audio_frames_delivered <= capacity &&
           first.video_pixels_produced == 0u);
    for (size_t index = 0u; index < pixel_bytes; ++index)
        assert(((const uint8_t *)pixels_a)[index] == 0xa5u);
    for (size_t index = first.audio_frames_delivered * 2u * sizeof(int16_t);
         index < storage_frames * 2u * sizeof(int16_t); ++index)
        assert(((const uint8_t *)audio_a)[index] == 0x5au);

    assert(gn_reset(fault) == GN_STATUS_OK);
    gn_instance *fault_reference = bb_start(&media);
    memset(audio_a, 0x5a, storage_frames * 2u * sizeof(int16_t));
    memset(audio_b, 0x5a, storage_frames * 2u * sizeof(int16_t));
    request = pcm_test_request(0u, pixels_a, pixel_bytes, audio_a, capacity);
    assert(gn_mvs_advance_frame_v1(fault, &request, sizeof(request), &first,
                                   sizeof(first)) == GN_STATUS_OK);
    request = pcm_test_request(0u, pixels_b, pixel_bytes, audio_b, capacity);
    assert(gn_mvs_advance_frame_v1(fault_reference, &request, sizeof(request),
                                   &second, sizeof(second)) == GN_STATUS_OK);
    pcm_test_same_execution(&first, &second);
    assert(memcmp(audio_a, audio_b,
                  storage_frames * 2u * sizeof(int16_t)) == 0);

    gn_destroy(fault_reference);
    gn_destroy(fault);
    gn_destroy(reload_reference);
    gn_destroy(fresh);
    gn_destroy(peer_reference);
    gn_destroy(peer);
    gn_destroy(subject);
    free(media.copy);
    free(audio_b);
    free(audio_a);
    free(pixels_b);
    free(pixels_a);
}

/* A watchdog reset is an emulated event inside a synchronous caller-owned
 * output call; it must reset sound state without detaching that call's sink. */
static void check_mvs_pcm_watchdog_delivery(const uint8_t *bundle, size_t size) {
    guest_media media;
    open_guest_media(bundle, size, &media);
    pcm_test_build_audio_bios(media.audio_bios);
    uint8_t *main_code = emit_move_b_imm(media.bios + 0x100u,
                                        0x3cu, UINT32_C(0x320000));
    emit_stop(main_code);
    gn_instance *instance = bb_start(&media);
    /* Place watchdog expiry inside the next output block, rather than at its
     * edge where no later sample may need the sink in that call. */
    gn_run_result prefix;
    run_mvs_in_bounded_chunks(instance, MAME_MVS_WATCHDOG_CPU_CYCLES -
                              GN_MVS_FRAME_BUDGET_CYCLES / 2u, &prefix);
    const size_t pixel_bytes = (size_t)320u * 224u * sizeof(uint32_t);
    uint32_t *pixels = (uint32_t *)malloc(pixel_bytes);
    const size_t capacity = GN_MVS_AUDIO_CAPACITY_FRAMES_V1;
    int16_t *audio = (int16_t *)malloc((capacity + 1u) * 2u * sizeof(int16_t));
    assert(pixels != NULL && audio != NULL);
    gn_mvs_frame_request_v1 request = pcm_test_request(
        0u, pixels, pixel_bytes, audio, capacity);
    uint64_t total_cycles = 0u;
    for (unsigned frame = 0u; frame < 18u; ++frame) {
        memset(audio, 0x5a, (capacity + 1u) * 2u * sizeof(int16_t));
        gn_mvs_frame_result_v1 result;
        assert(gn_mvs_advance_frame_v1(instance, &request, sizeof(request),
                                      &result, sizeof(result)) == GN_STATUS_OK);
        assert(result.audio_frames_generated > 0u &&
               result.audio_frames_generated == result.audio_frames_delivered &&
               result.audio_frames_discarded == 0u);
        assert(result.audio_frames_delivered <= capacity);
        total_cycles += result.elapsed_cycles;
        for (size_t byte = result.audio_frames_delivered * 2u * sizeof(int16_t);
             byte < (capacity + 1u) * 2u * sizeof(int16_t); ++byte)
            assert(((const uint8_t *)audio)[byte] == 0x5au);
    }
    gn_mvs_bus_fault_observation observation;
    assert(gn_observe_mvs_bus_fault(instance, &observation, sizeof(observation)) ==
           GN_STATUS_OK);
    assert(total_cycles > 2u * MAME_MVS_WATCHDOG_CPU_CYCLES &&
           observation.mame_watchdog_reset_count >= 2u);
    gn_destroy(instance);
    free(audio);
    free(pixels);
    free(media.copy);
}

static void check_mvs_pcm_public_api(const uint8_t *bundle, size_t size) {
    check_mvs_pcm_actual_boundary_partition(bundle, size);
    check_mvs_pcm_watchdog_delivery(bundle, size);
    check_mvs_pcm_rejects_misaligned_audio(bundle, size);
    check_mvs_pcm_preflight_and_discard(bundle, size);
    check_mvs_pcm_lifecycle_and_failure(bundle, size);
    check_mvs_pcm_streaming_converter();
    assert(GN_MVS_FRAME_REQUEST_V1_VERSION == 1u);
    const size_t pixel_bytes = (size_t)320u * (size_t)224u * sizeof(uint32_t);
    uint32_t *pixels = (uint32_t *)malloc(pixel_bytes);
    int16_t *pcm = (int16_t *)malloc(
        GN_MVS_AUDIO_CAPACITY_FRAMES_V1 * (size_t)2u * sizeof(int16_t));
    assert(pixels != NULL && pcm != NULL);

    guest_media tone_media;
    open_guest_media(bundle, size, &tone_media);
    pcm_test_build_audio_bios(tone_media.audio_bios);
    uint8_t *main_code = emit_move_b_imm(tone_media.bios + 0x100u,
                                        0x3cu, UINT32_C(0x320000));
    emit_stop(main_code);
    gn_instance *tone = bb_start(&tone_media);
    size_t capacity = 0u;
    assert(gn_mvs_audio_capacity_v1(tone, &capacity) == GN_STATUS_OK);
    assert(capacity == GN_MVS_AUDIO_CAPACITY_FRAMES_V1);

    gn_mvs_frame_request_v1 request = pcm_test_request(
        0u, pixels, pixel_bytes, pcm, capacity);
    gn_mvs_frame_result_v1 result;
    memset(&result, 0, sizeof(result));
    assert(gn_mvs_advance_frame_v1(tone, &request, sizeof(request), &result,
                                   sizeof(result)) == GN_STATUS_OK);
    assert(result.version == GN_MVS_FRAME_RESULT_V1_VERSION);
    assert(result.audio_format == GN_AUDIO_S16_INTERLEAVED_STEREO &&
           result.audio_sample_rate == 48000u && result.audio_channels == 2u);
    assert(result.audio_frames_generated >= 800u &&
           result.audio_frames_generated <= capacity &&
           result.audio_frames_delivered == result.audio_frames_generated &&
           result.audio_frames_discarded == 0u);
    assert(result.video_pixels_produced == (size_t)320u * (size_t)224u);
    assert(result.elapsed_cycles >= result.requested_cycles &&
           result.elapsed_cycles - result.requested_cycles <= UINT64_C(131));
    assert(result.frame_time_numerator == result.elapsed_cycles &&
           result.frame_time_denominator == UINT64_C(12000000));
    uint8_t reply = 0u;
    assert(gn_test_mvs_read_bus8(tone, UINT32_C(0x320000), &reply) ==
           GN_STATUS_OK);
    assert(reply == 0x3cu);
    pcm_test_check_tone(pcm, result.audio_frames_delivered);
    gn_destroy(tone);
    free(tone_media.copy);

    guest_media wrong_media;
    open_guest_media(bundle, size, &wrong_media);
    pcm_test_build_audio_bios(wrong_media.audio_bios);
    main_code = emit_move_b_imm(wrong_media.bios + 0x100u,
                                0x55u, UINT32_C(0x320000));
    emit_stop(main_code);
    gn_instance *wrong = bb_start(&wrong_media);
    request = pcm_test_request(0u, pixels, pixel_bytes, pcm, capacity);
    assert(gn_mvs_advance_frame_v1(wrong, &request, sizeof(request), &result,
                                   sizeof(result)) == GN_STATUS_OK);
    assert(gn_test_mvs_read_bus8(wrong, UINT32_C(0x320000), &reply) ==
           GN_STATUS_OK);
    assert(reply == 0x55u);
    pcm_test_check_silence(pcm, result.audio_frames_delivered);
    gn_destroy(wrong);
    free(wrong_media.copy);

    guest_media keyoff_media;
    open_guest_media(bundle, size, &keyoff_media);
    pcm_test_build_audio_bios(keyoff_media.audio_bios);
    main_code = emit_move_b_imm(keyoff_media.bios + 0x100u,
                                0x3cu, UINT32_C(0x320000));
    main_code = emit16(main_code, 0x303cu); /* MOVE.W #$ffff,D0 */
    main_code = emit16(main_code, UINT16_C(0xffff));
    main_code = emit16(main_code, 0x5340u); /* SUBQ.W #1,D0 */
    main_code = emit16(main_code, 0x66fcu); /* BNE.S back to SUBQ */
    main_code = emit_move_b_imm(main_code, 0x00u, UINT32_C(0x320000));
    emit_stop(main_code);
    gn_instance *keyoff = bb_start(&keyoff_media);
    request = pcm_test_request(0u, pixels, pixel_bytes, pcm, capacity);
    assert(gn_mvs_advance_frame_v1(keyoff, &request, sizeof(request), &result,
                                   sizeof(result)) == GN_STATUS_OK);
    pcm_test_check_tone(pcm, result.audio_frames_delivered);
    request = pcm_test_request(0u, pixels, pixel_bytes, NULL, 0u);
    for (size_t frame = 0u; frame < 6u; ++frame)
        assert(gn_mvs_advance_frame_v1(keyoff, &request, sizeof(request),
                                       &result, sizeof(result)) == GN_STATUS_OK);
    request = pcm_test_request(0u, pixels, pixel_bytes, pcm, capacity);
    assert(gn_mvs_advance_frame_v1(keyoff, &request, sizeof(request), &result,
                                   sizeof(result)) == GN_STATUS_OK);
    pcm_test_check_silence(pcm, result.audio_frames_delivered);
    gn_destroy(keyoff);
    free(keyoff_media.copy);
    free(pcm);
    free(pixels);
}

/* Each CTest partition retains the 180-second child bound. Repeated full-media
 * identity hashing dominates sampled Debug load cost. Release process resources
 * between groups while retaining every subcheck and the comprehensive CLI. */
static void check_board_core(const uint8_t *bundle, size_t size) {
    check_mvs_pcm_public_api(bundle, size);
    check_start_input(bundle, size);
    check_irq_timing(bundle, size);
    check_logical_frame_budget(bundle, size);
    check_failed_frame_prefix(bundle, size);
}

static void check_board_io(const uint8_t *bundle, size_t size) {
    check_io_status(bundle, size);
    check_mvs_controls_guest(bundle, size);
    check_status_a(bundle, size);
    check_controller_select_without_host_input(bundle, size);
    check_status_b(bundle, size);
    check_output3_latch(bundle, size);
    check_output2_latch(bundle, size);
    check_single_cartridge_slot_selection(bundle, size);
}

static void check_board_calendar(const uint8_t *bundle, size_t size) {
    check_calendar(bundle, size);
    check_calendar_timing(bundle, size);
    check_calendar_interrupt_noops(bundle, size);
    check_calendar_resume_commands(bundle, size);
}

static void check_board_sound(const uint8_t *bundle, size_t size) {
    check_sound_command_reply(bundle, size);
    check_disabled_nmi_pending_then_enable();
    check_sound_bus_boundary(bundle, size);
    check_sound_clock_and_sources();
    check_sound_ym_board(bundle, size);
    check_sound_selector_reset(bundle, size);
}

static void check_board_cartridge(const uint8_t *bundle, size_t size) {
    check_p2_banking_guest_write_and_instance_reset(bundle, size);
    check_p2_banking_guest_byte_lanes(bundle, size);
    check_mslugx_protection_guest(bundle, size);
    check_mslugx_protection_instance_isolation(bundle, size);
}

static void check_board_video(const uint8_t *bundle, size_t size) {
    check_mvs_fixed_renderer(bundle, size);
    check_mvs_sprite_renderer(bundle, size);
    check_mvs_sprite_instance_isolation(bundle, size);
}

static void check_board_behavior(const uint8_t *bundle, size_t size) {
    check_board_core(bundle, size);
    check_board_io(bundle, size);
    check_board_calendar(bundle, size);
    check_board_sound(bundle, size);
    check_board_cartridge(bundle, size);
    check_board_video(bundle, size);
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
        /* Import and execute one original synthetic guest here. The full
         * callback, P1/bus-fault, attract/stall and media assertions run in
         * mvs_callback_contract, mvs_boot_checkpoint, mvs_attract_predicate
         * and mvs_media_contract respectively. Repeating their many content
         * loads here multiplies immutable-media hashing and exceeds this
         * smoke test's unchanged 60-second bound. Keep the dedicated cases
         * registered; no behavioral assertion is removed from the SDK suite. */
        check_boot_checkpoint(bundle, bundle_size);
    } else if (strcmp(argv[1], "--sound-boundary") == 0) {
        check_sound_bus_boundary(bundle, bundle_size);
    } else if (strcmp(argv[1], "--sound-sources") == 0) {
        check_sound_clock_and_sources();
        check_sound_ym_board(bundle, bundle_size);
        check_sound_selector_reset(bundle, bundle_size);
    } else if (strcmp(argv[1], "--media-contract") == 0) {
        check_media_contract(bundle, bundle_size);
        check_zoom_manifest_contract(bundle, bundle_size);
    } else if (strcmp(argv[1], "--boot-checkpoint") == 0) {
        check_boot_checkpoint(bundle, bundle_size);
        check_cartridge_p1_window(bundle, bundle_size);
        check_mvs_bus_fault_observation(bundle, bundle_size);
    } else if (strcmp(argv[1], "--attract-predicate") == 0) {
        check_attract_predicate(bundle, bundle_size);
        check_stall_diagnosis(bundle, bundle_size);
    } else if (strcmp(argv[1], "--frame-prefix") == 0) {
        check_failed_frame_prefix(bundle, bundle_size);
    } else if (strcmp(argv[1], "--frame-budget") == 0) {
        check_logical_frame_budget(bundle, bundle_size);
    } else if (strcmp(argv[1], "--board-core") == 0) {
        check_board_core(bundle, bundle_size);
    } else if (strcmp(argv[1], "--board-io") == 0) {
        check_board_io(bundle, bundle_size);
    } else if (strcmp(argv[1], "--board-calendar") == 0) {
        check_board_calendar(bundle, bundle_size);
    } else if (strcmp(argv[1], "--board-sound") == 0) {
        check_board_sound(bundle, bundle_size);
    } else if (strcmp(argv[1], "--board-cartridge") == 0) {
        check_board_cartridge(bundle, bundle_size);
    } else if (strcmp(argv[1], "--board-video") == 0) {
        check_board_video(bundle, bundle_size);
    } else if (strcmp(argv[1], "--board-behavior") == 0) {
        check_board_behavior(bundle, bundle_size);
    } else if (strcmp(argv[1], "--callback-contract") == 0) {
        check_callbacks(bundle, bundle_size);
        check_mvs_input_observations(bundle, bundle_size);
    } else if (strcmp(argv[1], "--input-observations") == 0) {
        check_mvs_input_observations(bundle, bundle_size);
    } else if (strcmp(argv[1], "--bus-fault-observation") == 0) {
        check_mvs_bus_fault_observation(bundle, bundle_size);
    } else if (strcmp(argv[1], "--high-bios-mirror") == 0) {
        check_high_bios_mirror(bundle, bundle_size);
    }
    assert(argc == 1 || argc == 2);
    assert(argc == 1 || strcmp(argv[1], "--sound-boundary") == 0 ||
           strcmp(argv[1], "--sound-sources") == 0 ||
           strcmp(argv[1], "--media-contract") == 0 ||
           strcmp(argv[1], "--boot-checkpoint") == 0 ||
           strcmp(argv[1], "--attract-predicate") == 0 ||
           strcmp(argv[1], "--board-core") == 0 ||
           strcmp(argv[1], "--board-io") == 0 ||
           strcmp(argv[1], "--board-calendar") == 0 ||
           strcmp(argv[1], "--board-sound") == 0 ||
           strcmp(argv[1], "--board-cartridge") == 0 ||
           strcmp(argv[1], "--board-video") == 0 ||
           strcmp(argv[1], "--board-behavior") == 0 ||
           strcmp(argv[1], "--frame-budget") == 0 ||
           strcmp(argv[1], "--frame-prefix") == 0 ||
           strcmp(argv[1], "--input-observations") == 0 ||
           strcmp(argv[1], "--callback-contract") == 0 ||
           strcmp(argv[1], "--bus-fault-observation") == 0 ||
           strcmp(argv[1], "--high-bios-mirror") == 0);
    free(bundle);
    puts("MVS selected contract passed");
    return 0;
}
