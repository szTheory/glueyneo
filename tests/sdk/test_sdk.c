/* SPDX-License-Identifier: MIT */
#include "glueyneo/glueyneo.h"
#include "chips/ym2610_candidate.h"
#include "guest_fixture.h"
#include "sdk_private.h"
#include "test_support.h"

#if !defined(_WIN32)
#include <stdatomic.h>
#endif
#include <stdlib.h>
#include <stdio.h>
#include <string.h>

#ifndef GLUEYNEO_SOURCE_REVISION
#define GLUEYNEO_SOURCE_REVISION "unknown"
#endif
#ifndef GLUEYNEO_CONFIGURATION
#define GLUEYNEO_CONFIGURATION "unspecified"
#endif
#ifndef GLUEYNEO_COMPILER_ID
#define GLUEYNEO_COMPILER_ID "unknown"
#endif
#ifndef GLUEYNEO_COMPILER_VERSION
#define GLUEYNEO_COMPILER_VERSION "unknown"
#endif

static gn_instance *instance;
static gn_instance *state_peer;
static gn_instance *state_witness;
static const char *selected_suite;
static uint64_t sdk_failpoint_positions;
static uint64_t sdk_failpoint_failures;
static uint64_t sdk_failpoint_success_boundaries;
static char sdk_sound_fixture_path[4096];

enum {
    SDK_SOUND_HEADER_BYTES = 16u,
    SDK_SOUND_REGION_COUNT = 8u,
    SDK_SOUND_DESCRIPTOR_BYTES = 12u,
    SDK_SOUND_WIDTH = 320u,
    SDK_SOUND_HEIGHT = 224u,
    SDK_SOUND_FRAMES = 6u
};

typedef struct {
    uint8_t *bytes;
    size_t size;
    size_t offsets[SDK_SOUND_REGION_COUNT];
    size_t lengths[SDK_SOUND_REGION_COUNT];
} sdk_sound_bundle;

static uint32_t sdk_sound_read_u32_be(const uint8_t *bytes) {
    return ((uint32_t)bytes[0] << 24) | ((uint32_t)bytes[1] << 16) |
           ((uint32_t)bytes[2] << 8) | (uint32_t)bytes[3];
}

static void sdk_sound_set_fixture_path(const char *executable) {
    const char *slash = strrchr(executable, '/');
    size_t directory_bytes = slash == NULL ? 0u : (size_t)(slash - executable);
    const char *suffix = "public-sound-mvs.bin";
    if (directory_bytes + (directory_bytes != 0u ? 1u : 0u) +
            strlen(suffix) + 1u > sizeof(sdk_sound_fixture_path)) return;
    if (directory_bytes != 0u) {
        memcpy(sdk_sound_fixture_path, executable, directory_bytes);
        sdk_sound_fixture_path[directory_bytes++] = '/';
    }
    memcpy(sdk_sound_fixture_path + directory_bytes, suffix, strlen(suffix) + 1u);
}

static int sdk_sound_bundle_read(sdk_sound_bundle *bundle) {
    memset(bundle, 0, sizeof(*bundle));
    if (sdk_sound_fixture_path[0] == '\0') return 0;
    FILE *file = fopen(sdk_sound_fixture_path, "rb");
    if (file == NULL) return 0;
    if (fseek(file, 0L, SEEK_END) != 0) {
        (void)fclose(file);
        return 0;
    }
    const long measured = ftell(file);
    if (measured < (long)(SDK_SOUND_HEADER_BYTES +
                          SDK_SOUND_REGION_COUNT * SDK_SOUND_DESCRIPTOR_BYTES) ||
        (uint64_t)measured > GN_MVS_MAX_MEDIA_BYTES +
            SDK_SOUND_HEADER_BYTES +
            SDK_SOUND_REGION_COUNT * SDK_SOUND_DESCRIPTOR_BYTES ||
        fseek(file, 0L, SEEK_SET) != 0) {
        (void)fclose(file);
        return 0;
    }
    bundle->size = (size_t)measured;
    bundle->bytes = (uint8_t *)malloc(bundle->size);
    if (bundle->bytes == NULL) {
        (void)fclose(file);
        return 0;
    }
    const size_t count = fread(bundle->bytes, 1u, bundle->size, file);
    const int extra = fgetc(file);
    const int close_status = fclose(file);
    if (count != bundle->size || extra != EOF || close_status != 0 ||
        memcmp(bundle->bytes, "GNMV", 4u) != 0 ||
        sdk_sound_read_u32_be(bundle->bytes + 4u) !=
            GN_MVS_MANIFEST_VERSION_ZOOM ||
        sdk_sound_read_u32_be(bundle->bytes + 8u) != GN_MVS_PROFILE_MSX ||
        sdk_sound_read_u32_be(bundle->bytes + 12u) != SDK_SOUND_REGION_COUNT) {
        free(bundle->bytes);
        memset(bundle, 0, sizeof(*bundle));
        return 0;
    }
    size_t cursor = SDK_SOUND_HEADER_BYTES;
    for (size_t index = 0u; index < SDK_SOUND_REGION_COUNT; ++index) {
        if (cursor > bundle->size ||
            bundle->size - cursor < SDK_SOUND_DESCRIPTOR_BYTES) goto invalid;
        const uint32_t role = sdk_sound_read_u32_be(bundle->bytes + cursor);
        const uint32_t high = sdk_sound_read_u32_be(bundle->bytes + cursor + 4u);
        const uint32_t low = sdk_sound_read_u32_be(bundle->bytes + cursor + 8u);
        cursor += SDK_SOUND_DESCRIPTOR_BYTES;
        if (role != index + 1u || high != 0u || low == 0u ||
            (size_t)low > bundle->size - cursor) goto invalid;
        bundle->offsets[index] = cursor;
        bundle->lengths[index] = (size_t)low;
        cursor += (size_t)low;
    }
    if (cursor != bundle->size) goto invalid;
    return 1;
invalid:
    free(bundle->bytes);
    memset(bundle, 0, sizeof(*bundle));
    return 0;
}

static int sdk_sound_patch_sequence(uint8_t *region, size_t size,
                                    const uint8_t *from, size_t from_size,
                                    const uint8_t *to, size_t to_size,
                                    size_t *out_changes) {
    if (from_size != to_size || from_size == 0u) return 0;
    size_t changes = 0u;
    for (size_t index = 0u; index + from_size <= size; ++index) {
        if (memcmp(region + index, from, from_size) == 0) {
            memcpy(region + index, to, to_size);
            ++changes;
            index += from_size - 1u;
        }
    }
    if (out_changes != NULL) *out_changes = changes;
    return 1;
}

static int sdk_sound_make_variant(sdk_sound_bundle *bundle) {
    uint8_t *const bios = bundle->bytes + bundle->offsets[0];
    uint8_t *const audio_bios = bundle->bytes + bundle->offsets[6];
    uint8_t *const samples = bundle->bytes + bundle->offsets[4];
    static const uint8_t music_set[] = {
        0x13u, 0xfcu, 0x00u, 0x3cu, 0x00u, 0x32u, 0x00u, 0x00u
    };
    static const uint8_t music_set_variant[] = {
        0x13u, 0xfcu, 0x00u, 0x3du, 0x00u, 0x32u, 0x00u, 0x00u
    };
    static const uint8_t music_compare[] = {0x0cu, 0x00u, 0x00u, 0x3cu};
    static const uint8_t music_compare_variant[] = {0x0cu, 0x00u, 0x00u, 0x3du};
    static const uint8_t audio_compare[] = {0xfeu, 0x3cu};
    static const uint8_t audio_compare_variant[] = {0xfeu, 0x3du};
    static const uint8_t ssg_pitch[] = {
        0x3eu, 0x00u, 0xd3u, 0x04u, 0x3eu, 0x7du, 0xd3u, 0x05u
    };
    static const uint8_t ssg_pitch_variant[] = {
        0x3eu, 0x00u, 0xd3u, 0x04u, 0x3eu, 0x61u, 0xd3u, 0x05u
    };
    static const uint8_t adpcm_pan[] = {
        0x3eu, 0x11u, 0xd3u, 0x04u, 0x3eu, 0xc0u, 0xd3u, 0x05u
    };
    static const uint8_t adpcm_pan_variant[] = {
        0x3eu, 0x11u, 0xd3u, 0x04u, 0x3eu, 0x80u, 0xd3u, 0x05u
    };
    size_t set_changes = 0u, compare_changes = 0u, audio_changes = 0u;
    size_t pitch_changes = 0u, pan_changes = 0u;
    if (!sdk_sound_patch_sequence(bios, bundle->lengths[0], music_set,
            sizeof(music_set), music_set_variant, sizeof(music_set_variant),
            &set_changes) ||
        !sdk_sound_patch_sequence(bios, bundle->lengths[0], music_compare,
            sizeof(music_compare), music_compare_variant,
            sizeof(music_compare_variant), &compare_changes) ||
        !sdk_sound_patch_sequence(audio_bios, bundle->lengths[6], audio_compare,
            sizeof(audio_compare), audio_compare_variant,
            sizeof(audio_compare_variant), &audio_changes) ||
        !sdk_sound_patch_sequence(audio_bios, bundle->lengths[6], ssg_pitch,
            sizeof(ssg_pitch), ssg_pitch_variant, sizeof(ssg_pitch_variant),
            &pitch_changes) ||
        !sdk_sound_patch_sequence(audio_bios, bundle->lengths[6], adpcm_pan,
            sizeof(adpcm_pan), adpcm_pan_variant, sizeof(adpcm_pan_variant),
            &pan_changes)) return 0;
    if (set_changes != 2u || compare_changes != 2u || audio_changes != 1u ||
        pitch_changes != 2u || pan_changes != 1u || bundle->lengths[4] < 256u) {
        (void)fprintf(stderr, "SDK_MVS_ISOLATION variant matches %zu/%zu/%zu/%zu/%zu\n",
                      set_changes, compare_changes, audio_changes, pitch_changes,
                      pan_changes);
        return 0;
    }
    for (size_t index = 0u; index < 256u; ++index)
        samples[index] = (uint8_t)((samples[index] << 4) | (samples[index] >> 4));
    return 1;
}

static void make_manifest(gn_manifest *manifest, guest_fixture_image *fixture,
                          unsigned scenario) {
    guest_fixture_build(fixture, (guest_fixture_scenario)scenario);
    memset(manifest, 0, sizeof(*manifest));
    manifest->version = GN_MANIFEST_VERSION;
    manifest->profile = GN_PROFILE_DIAGNOSTIC;
    manifest->region_count = GN_MAX_REGIONS;
    manifest->regions[0] = (gn_region){0u, GUEST_FIXTURE_ROM_SIZE, fixture->rom,
                                      GUEST_FIXTURE_ROM_SIZE, GN_REGION_ROM};
    manifest->regions[1] = (gn_region){0x1000u, 4096u, fixture->ram_seed,
                                      GUEST_FIXTURE_RAM_INIT_SIZE, GN_REGION_RAM};
}

static int suite_is_control(void) {
    return selected_suite != NULL && strncmp(selected_suite, "control-", 8u) == 0;
}

static gn_test_mutation mutation_for_suite(void) {
    if (strcmp(selected_suite, "control-bss") == 0) {
        return GN_TEST_MUTATION_BSS_READ;
    }
    if (strcmp(selected_suite, "control-run-elapsed") == 0) {
        return GN_TEST_MUTATION_RUN_ELAPSED;
    }
    if (strcmp(selected_suite, "control-run-instructions") == 0) {
        return GN_TEST_MUTATION_RUN_INSTRUCTIONS;
    }
    if (strcmp(selected_suite, "control-run-stop") == 0) {
        return GN_TEST_MUTATION_RUN_STOP_REASON;
    }
    if (strcmp(selected_suite, "control-byte-order") == 0) {
        return GN_TEST_MUTATION_OBSERVATION_BYTE_ORDER;
    }
    if (strcmp(selected_suite, "control-access-order") == 0) {
        return GN_TEST_MUTATION_TRACE_ORDER;
    }
    return GN_TEST_MUTATION_NONE;
}

static gn_status load_scenario(gn_instance *target, unsigned scenario) {
    guest_fixture_image *fixture =
        (guest_fixture_image *)malloc(sizeof(*fixture));
    if (fixture == NULL) return GN_STATUS_OUT_OF_MEMORY;
    gn_manifest manifest;
    make_manifest(&manifest, fixture, scenario);
    if (strcmp(selected_suite, "control-arithmetic") == 0) {
        fixture->rom[0x101u] = UINT8_C(8);
    } else if (strcmp(selected_suite, "control-initialized") == 0) {
        fixture->ram_seed[8u] = UINT8_C(0x12);
        fixture->ram_seed[9u] = UINT8_C(0x35);
    }
    const gn_status status = gn_load(target, &manifest);
    memset(fixture, 0xa5, sizeof(*fixture));
    free(fixture);
    return status;
}

void setUp(void) {
    instance = NULL;
    if (strcmp(selected_suite, "cold") == 0 ||
        strcmp(selected_suite, "isolation") == 0 ||
        strcmp(selected_suite, "state-machine") == 0) {
        return;
    }
    SDK_CHECK_STATUS("sdk.instance.create", GN_STATUS_OK, gn_create(&instance));
    if (instance != NULL && (strcmp(selected_suite, "diagnostic") == 0 ||
                             strcmp(selected_suite, "state-tracer") == 0 ||
                             strcmp(selected_suite, "state-identity") == 0 ||
                             strcmp(selected_suite, "run") == 0 ||
                             strcmp(selected_suite, "controls") == 0 ||
                             suite_is_control())) {
        SDK_CHECK_STATUS("sdk.media.load.original-a", GN_STATUS_OK,
                         load_scenario(instance, 0u));
        if (suite_is_control() && mutation_for_suite() != GN_TEST_MUTATION_NONE) {
            SDK_CHECK_STATUS("sdk.control.install-test-adapter-mutation",
                             GN_STATUS_OK,
                             gn_test_set_mutation(instance, mutation_for_suite()));
        }
    }
}

void tearDown(void) {
    gn_destroy(instance);
    instance = NULL;
    gn_destroy(state_peer);
    state_peer = NULL;
    gn_destroy(state_witness);
    state_witness = NULL;
}

static void original_guest_computes_named_results(void) {
    SDK_CASE("sdk.diagnostic.original-a");
    gn_run_result run;
    memset(&run, 0xa5, sizeof(run));
    SDK_CHECK_STATUS("sdk.run.status", GN_STATUS_OK, gn_run(instance, 172u, &run));
    SDK_CHECK_U64("sdk.run.requested-cycles", 172u, run.requested_cycles);
    SDK_CHECK_U64("sdk.run.elapsed-cycles", 172u, run.elapsed_cycles);
    SDK_CHECK_U64("sdk.run.overshoot-cycles", 0u, run.overshoot_cycles);
    SDK_CHECK_U64("sdk.run.instructions", 12u, run.instructions);
    SDK_CHECK_STATUS("sdk.run.reason-stopped", GN_RUN_STOPPED, run.reason);
    SDK_CHECK_U64("sdk.run.boundary-pc", 0x12eu, run.boundary_pc);

    gn_observations observations;
    memset(&observations, 0xa5, sizeof(observations));
    SDK_CHECK_STATUS("sdk.observe.status", GN_STATUS_OK,
                     gn_observe(instance, &observations));
    SDK_CHECK_U64("sdk.observe.arithmetic", 10u, observations.arithmetic_result);
    SDK_CHECK_U64("sdk.observe.initialized", 0x1237u, observations.initialized_result);
    SDK_CHECK_U64("sdk.observe.bss", 1u, observations.bss_result);
    SDK_CHECK_U64("sdk.observe.ready", 1u, observations.ready);
}

static void failed_replacement_and_reset_preserve_owned_media(void) {
    SDK_CASE("sdk.media.failed-replacement-preserves-live");
    gn_manifest invalid;
    memset(&invalid, 0, sizeof(invalid));
    invalid.version = GN_MANIFEST_VERSION;
    invalid.profile = GN_PROFILE_DIAGNOSTIC;
    SDK_CHECK_STATUS("sdk.media.reject-empty-manifest", GN_STATUS_INVALID_MEDIA,
                     gn_load(instance, &invalid));
    SDK_CHECK_STATUS("sdk.reset.owned-seed", GN_STATUS_OK, gn_reset(instance));

    gn_observations before_run;
    memset(&before_run, 0xa5, sizeof(before_run));
    SDK_CHECK_STATUS("sdk.observe.reset", GN_STATUS_OK,
                     gn_observe(instance, &before_run));
    SDK_CHECK_U64("sdk.reset.arithmetic-zero", 0u, before_run.arithmetic_result);
    SDK_CHECK_U64("sdk.reset.initialized-zero", 0u, before_run.initialized_result);
    SDK_CHECK_U64("sdk.reset.bss-zero", 0u, before_run.bss_result);

    gn_run_result run;
    SDK_CHECK_STATUS("sdk.run.after-reset", GN_STATUS_OK, gn_run(instance, 172u, &run));
    gn_observations after_run;
    SDK_CHECK_STATUS("sdk.observe.after-reset-run", GN_STATUS_OK,
                     gn_observe(instance, &after_run));
    SDK_CHECK_U64("sdk.reset.restored-arithmetic", 10u, after_run.arithmetic_result);
    SDK_CHECK_U64("sdk.reset.restored-initialized", 0x1237u,
                  after_run.initialized_result);
    SDK_CHECK_U64("sdk.reset.restored-bss", 1u, after_run.bss_result);
    SDK_CHECK_U64("sdk.reset.restored-stop", GN_RUN_STOPPED, run.reason);
}

static void scenario_b_has_distinguishable_named_results(void) {
    SDK_CASE("sdk.diagnostic.original-b");
    SDK_CHECK_STATUS("sdk.media.load.original-b", GN_STATUS_OK,
                     load_scenario(instance, GUEST_FIXTURE_SCENARIO_B));
    gn_run_result run;
    SDK_CHECK_STATUS("sdk.run.scenario-b", GN_STATUS_OK, gn_run(instance, 172u, &run));
    gn_observations observations;
    SDK_CHECK_STATUS("sdk.observe.scenario-b", GN_STATUS_OK,
                     gn_observe(instance, &observations));
    SDK_CHECK_U64("sdk.scenario-b.arithmetic", 16u,
                  observations.arithmetic_result);
    SDK_CHECK_U64("sdk.scenario-b.initialized", 0x2348u,
                  observations.initialized_result);
    SDK_CHECK_U64("sdk.scenario-b.bss", 1u, observations.bss_result);
    SDK_CHECK_U64("sdk.scenario-b.cycles", 172u, run.elapsed_cycles);
    SDK_CHECK_U64("sdk.scenario-b.instructions", 12u, run.instructions);
    SDK_CHECK_STATUS("sdk.scenario-b.stopped", GN_RUN_STOPPED, run.reason);
}

static void original_instruction_boundaries_match_manual_recipe(void) {
    static const uint64_t requests[] = {
        40u, 4u, 8u, 20u, 4u, 16u, 8u, 20u, 4u, 16u, 8u, 20u, 4u
    };
    static const uint64_t cumulative_cycles[] = {
        40u, 44u, 52u, 72u, 76u, 92u, 100u, 120u, 124u, 140u, 148u, 168u, 172u
    };
    static const uint32_t boundary_pcs[] = {
        0x100u, 0x102u, 0x104u, 0x10au, 0x10cu, 0x112u, 0x114u,
        0x11au, 0x11cu, 0x122u, 0x124u, 0x12au, 0x12eu
    };
    SDK_CASE("sdk.diagnostic.original-a-instruction-boundaries");
    uint64_t total_elapsed = 0u;
    uint64_t total_instructions = 0u;
    for (size_t index = 0u; index < sizeof(requests) / sizeof(requests[0]); ++index) {
        gn_run_result run;
        memset(&run, 0, sizeof(run));
        SDK_CHECK_STATUS("sdk.boundary.run", GN_STATUS_OK,
                         gn_run(instance, requests[index], &run));
        total_elapsed += run.elapsed_cycles;
        total_instructions += run.instructions;
        SDK_CHECK_U64("sdk.boundary.elapsed-this-call", requests[index],
                      run.elapsed_cycles);
        SDK_CHECK_U64("sdk.boundary.elapsed-total", cumulative_cycles[index],
                      total_elapsed);
        SDK_CHECK_U64("sdk.boundary.instructions-total", (uint64_t)index,
                      total_instructions);
        SDK_CHECK_U64("sdk.boundary.pc", boundary_pcs[index], run.boundary_pc);
        const gn_run_reason expected_reason =
            index + 1u == sizeof(requests) / sizeof(requests[0])
                ? GN_RUN_STOPPED
                : GN_RUN_BUDGET;
        SDK_CHECK_STATUS("sdk.boundary.reason", expected_reason, run.reason);
    }
}

#if defined(GN_STATE_FORMAT_V1_VERSION)
static int sdk_state_future_equal(gn_instance *left, gn_instance *right,
                                  uint64_t budget) {
    gn_run_result left_run;
    gn_run_result right_run;
    gn_observations left_observations;
    gn_observations right_observations;
    if (gn_run(left, budget, &left_run) != GN_STATUS_OK ||
        gn_run(right, budget, &right_run) != GN_STATUS_OK ||
        left_run.requested_cycles != right_run.requested_cycles ||
        left_run.elapsed_cycles != right_run.elapsed_cycles ||
        left_run.overshoot_cycles != right_run.overshoot_cycles ||
        left_run.instructions != right_run.instructions ||
        left_run.boundary_pc != right_run.boundary_pc ||
        left_run.reason != right_run.reason ||
        gn_observe(left, &left_observations) != GN_STATUS_OK ||
        gn_observe(right, &right_observations) != GN_STATUS_OK) return 0;
    return left_observations.arithmetic_result ==
               right_observations.arithmetic_result &&
           left_observations.initialized_result ==
               right_observations.initialized_result &&
           left_observations.bss_result == right_observations.bss_result &&
           left_observations.ready == right_observations.ready;
}
#endif

static void check_diagnostic_restore_resources(gn_instance *subject,
                                              int complete) {
    gn_test_state_resources r;
    SDK_CHECK_STATUS("sdk.state-tracer.resources.read", GN_STATUS_OK,
                     gn_test_state_resources_read(subject, &r));
    SDK_CHECK_U64("sdk.state-tracer.resources.no-heap-staging", 0u,
                  r.heap_staging_bytes);
    SDK_CHECK_TRUE("sdk.state-tracer.resources.includes-ram-and-cpu-copies",
                   r.stack_staging_bytes > 4096u);
    SDK_CHECK_TRUE("sdk.state-tracer.resources.bounded-work",
        r.byte_work <= r.byte_work_limit && r.phases <= r.phase_limit &&
        r.repeated_phase == 0u);
    if (complete) {
        SDK_CHECK_U64("sdk.state-tracer.resources.full-byte-charge",
                      r.byte_work_limit, r.byte_work);
        SDK_CHECK_U64("sdk.state-tracer.resources.full-fixed-phases", 4u,
                      r.phases);
        (void)printf("SDK_STATE_DIAGNOSTIC_BOUND input_bytes=%zu "
            "stack_staging_bytes=%zu byte_work_limit=%zu fixed_phases=%zu\n",
            r.input_bytes, r.stack_staging_bytes, r.byte_work_limit, r.phases);
    }
}

static void diagnostic_native_state_tracer_round_trips_real_continuation(void) {
    SDK_CASE("sdk.state-tracer.diagnostic-continuation");
#if !defined(GN_STATE_FORMAT_V1_VERSION)
    SDK_CHECK_TRUE("sdk.state-tracer.public-api-available", 0);
#else
    size_t capacity = 0u;
    SDK_CHECK_STATUS("sdk.state-tracer.capacity", GN_STATUS_OK,
                     gn_state_capacity_v1(instance, &capacity));
    SDK_CHECK_TRUE("sdk.state-tracer.capacity-nonzero", capacity > 1u);
    SDK_CHECK_STATUS("sdk.state-tracer.create-peer", GN_STATUS_OK,
                     gn_create(&state_peer));
    SDK_CHECK_STATUS("sdk.state-tracer.load-peer", GN_STATUS_OK,
                     load_scenario(state_peer, 0u));

    uint8_t *exact = (uint8_t *)malloc(capacity);
    uint8_t *repeat = (uint8_t *)malloc(capacity);
    uint8_t *larger = (uint8_t *)malloc(capacity + 1u);
    SDK_CHECK_TRUE("sdk.state-tracer.allocate-capture-buffers",
                   exact != NULL && repeat != NULL && larger != NULL);
    memset(exact, 0xa5, capacity);
    memset(repeat, 0x3c, capacity);
    memset(larger, 0x5a, capacity + 1u);

    gn_observations before_capture;
    gn_observations after_capture;
    SDK_CHECK_STATUS("sdk.state-tracer.observe-before-capture", GN_STATUS_OK,
                     gn_observe(instance, &before_capture));
    size_t exact_written = SIZE_MAX;
    size_t repeat_written = SIZE_MAX;
    size_t larger_written = SIZE_MAX;
    gn_state_detail_v1 detail;
    memset(&detail, 0, sizeof(detail));
    detail.size = (uint32_t)sizeof(detail);
    SDK_CHECK_STATUS("sdk.state-tracer.capture-loaded", GN_STATUS_OK,
                     gn_state_capture_v1(instance, exact, capacity,
                                         &exact_written, &detail,
                                         sizeof(detail)));
    SDK_CHECK_STATUS("sdk.state-tracer.capture-repeat", GN_STATUS_OK,
                     gn_state_capture_v1(instance, repeat, capacity,
                                         &repeat_written, &detail,
                                         sizeof(detail)));
    SDK_CHECK_STATUS("sdk.state-tracer.capture-larger-buffer", GN_STATUS_OK,
                     gn_state_capture_v1(instance, larger, capacity + 1u,
                                         &larger_written, &detail,
                                         sizeof(detail)));
    SDK_CHECK_U64("sdk.state-tracer.capture-length-exact", exact_written,
                  repeat_written);
    SDK_CHECK_U64("sdk.state-tracer.capture-length-larger", exact_written,
                  larger_written);
    SDK_CHECK_TRUE("sdk.state-tracer.capture-bytes-deterministic",
                   exact_written <= capacity &&
                       memcmp(exact, repeat, exact_written) == 0 &&
                       memcmp(exact, larger, exact_written) == 0);
    SDK_CHECK_U64("sdk.state-tracer.larger-buffer-tail-untouched", 0x5au,
                  larger[capacity]);
    SDK_CHECK_STATUS("sdk.state-tracer.observe-after-capture", GN_STATUS_OK,
                     gn_observe(instance, &after_capture));
    SDK_CHECK_U64("sdk.state-tracer.capture-no-execution-arithmetic",
                  before_capture.arithmetic_result,
                  after_capture.arithmetic_result);
    SDK_CHECK_U64("sdk.state-tracer.capture-no-execution-initialized",
                  before_capture.initialized_result,
                  after_capture.initialized_result);
    SDK_CHECK_U64("sdk.state-tracer.capture-no-execution-bss",
                  before_capture.bss_result, after_capture.bss_result);

    uint8_t *small = (uint8_t *)malloc(capacity);
    SDK_CHECK_TRUE("sdk.state-tracer.allocate-small-buffer", small != NULL);
    memset(small, 0xa5, capacity);
    size_t failed_written = SIZE_MAX;
    SDK_CHECK_STATUS("sdk.state-tracer.reject-capacity-minus-one",
                     GN_STATUS_INVALID_ARGUMENT,
                     gn_state_capture_v1(instance, small, capacity - 1u,
                                         &failed_written, &detail,
                                         sizeof(detail)));
    SDK_CHECK_U64("sdk.state-tracer.failed-capture-count-zero", 0u,
                  failed_written);
    SDK_CHECK_U64("sdk.state-tracer.capacity-error-reason",
                  GN_STATE_REASON_INSUFFICIENT_CAPACITY, detail.reason);
    int untouched = 1;
    for (size_t index = 0u; index < capacity; ++index) {
        if (small[index] != UINT8_C(0xa5)) untouched = 0;
    }
    SDK_CHECK_TRUE("sdk.state-tracer.capacity-reject-no-write", untouched);

    uint8_t *transfer = (uint8_t *)malloc(exact_written);
    SDK_CHECK_TRUE("sdk.state-tracer.allocate-transfer", transfer != NULL);
    memcpy(transfer, exact, exact_written);
    SDK_CHECK_STATUS("sdk.state-tracer.restore-fresh-peer", GN_STATUS_OK,
                     gn_state_restore_v1(state_peer, transfer, exact_written,
                                         &detail, sizeof(detail)));
    check_diagnostic_restore_resources(state_peer, 1);
    memset(transfer, 0x96, exact_written);
    free(transfer);
    transfer = NULL;
    gn_run_result source_run;
    gn_run_result peer_run;
    SDK_CHECK_STATUS("sdk.state-tracer.run-source-after-load-capture",
                     GN_STATUS_OK, gn_run(instance, 172u, &source_run));
    SDK_CHECK_STATUS("sdk.state-tracer.run-peer-after-buffer-destroy",
                     GN_STATUS_OK, gn_run(state_peer, 172u, &peer_run));
    SDK_CHECK_U64("sdk.state-tracer.future-cycles-match",
                  source_run.elapsed_cycles, peer_run.elapsed_cycles);
    SDK_CHECK_U64("sdk.state-tracer.future-instructions-match",
                  source_run.instructions, peer_run.instructions);
    SDK_CHECK_U64("sdk.state-tracer.future-stop-match", source_run.reason,
                  peer_run.reason);
    SDK_CHECK_TRUE("sdk.state-tracer.future-observations-match",
                   sdk_state_future_equal(instance, state_peer, 8u));

    SDK_CHECK_STATUS("sdk.state-tracer.reset-capture-source", GN_STATUS_OK,
                     gn_reset(instance));
    size_t reset_written = 0u;
    SDK_CHECK_STATUS("sdk.state-tracer.capture-after-reset", GN_STATUS_OK,
                     gn_state_capture_v1(instance, exact, capacity,
                                         &reset_written, &detail,
                                         sizeof(detail)));
    SDK_CHECK_STATUS("sdk.state-tracer.raw-budget", GN_STATUS_OK,
                     gn_run(instance, 40u, &source_run));
    SDK_CHECK_U64("sdk.state-tracer.raw-budget-reason", GN_RUN_BUDGET,
                  source_run.reason);
    size_t raw_written = 0u;
    SDK_CHECK_STATUS("sdk.state-tracer.capture-after-raw-budget", GN_STATUS_OK,
                     gn_state_capture_v1(instance, exact, capacity,
                                         &raw_written, &detail,
                                         sizeof(detail)));
    SDK_CHECK_STATUS("sdk.state-tracer.restore-raw-budget", GN_STATUS_OK,
                     gn_state_restore_v1(state_peer, exact, raw_written,
                                         &detail, sizeof(detail)));
    SDK_CHECK_TRUE("sdk.state-tracer.raw-budget-continuation-matches",
                   sdk_state_future_equal(instance, state_peer, 132u));
    size_t stop_written = 0u;
    SDK_CHECK_STATUS("sdk.state-tracer.capture-after-normal-stop", GN_STATUS_OK,
                     gn_state_capture_v1(instance, exact, capacity,
                                         &stop_written, &detail,
                                         sizeof(detail)));
    SDK_CHECK_STATUS("sdk.state-tracer.restore-stop-state", GN_STATUS_OK,
                     gn_state_restore_v1(state_peer, exact, stop_written,
                                         &detail, sizeof(detail)));
    SDK_CHECK_TRUE("sdk.state-tracer.stop-continuation-matches",
                   sdk_state_future_equal(instance, state_peer, 16u));

    SDK_CHECK_STATUS("sdk.state-tracer.create-independent-witness",
                     GN_STATUS_OK, gn_create(&state_witness));
    SDK_CHECK_STATUS("sdk.state-tracer.load-independent-witness", GN_STATUS_OK,
                     load_scenario(state_witness, 0u));
    SDK_CHECK_STATUS("sdk.state-tracer.seed-peer-for-rejection", GN_STATUS_OK,
                     gn_state_restore_v1(state_peer, exact, stop_written,
                                         &detail, sizeof(detail)));
    SDK_CHECK_STATUS("sdk.state-tracer.seed-witness-for-rejection", GN_STATUS_OK,
                     gn_state_restore_v1(state_witness, exact, stop_written,
                                         &detail, sizeof(detail)));

    SDK_CHECK_STATUS("sdk.state-tracer.reject-truncated-state",
                     GN_STATUS_INVALID_ARGUMENT,
                     gn_state_restore_v1(state_peer, exact, stop_written - 1u,
                                         &detail, sizeof(detail)));
    check_diagnostic_restore_resources(state_peer, 0);
    SDK_CHECK_U64("sdk.state-tracer.truncated-reason", GN_STATE_REASON_TRUNCATED,
                  detail.reason);
    SDK_CHECK_TRUE("sdk.state-tracer.truncated-rejection-preserves-machine",
                   sdk_state_future_equal(state_peer, state_witness, 8u));

    uint8_t *extended = (uint8_t *)malloc(stop_written + 1u);
    SDK_CHECK_TRUE("sdk.state-tracer.allocate-extended", extended != NULL);
    memcpy(extended, exact, stop_written);
    extended[stop_written] = UINT8_C(0x7e);
    SDK_CHECK_STATUS("sdk.state-tracer.seed-peer-before-trailing-reject",
                     GN_STATUS_OK,
                     gn_state_restore_v1(state_peer, exact, stop_written,
                                         &detail, sizeof(detail)));
    SDK_CHECK_STATUS("sdk.state-tracer.seed-witness-before-trailing-reject",
                     GN_STATUS_OK,
                     gn_state_restore_v1(state_witness, exact, stop_written,
                                         &detail, sizeof(detail)));
    SDK_CHECK_STATUS("sdk.state-tracer.reject-trailing-data",
                     GN_STATUS_INVALID_ARGUMENT,
                     gn_state_restore_v1(state_peer, extended,
                                         stop_written + 1u, &detail,
                                         sizeof(detail)));
    SDK_CHECK_U64("sdk.state-tracer.trailing-reason",
                  GN_STATE_REASON_TRAILING_DATA, detail.reason);
    SDK_CHECK_TRUE("sdk.state-tracer.trailing-rejection-preserves-machine",
                   sdk_state_future_equal(state_peer, state_witness, 8u));
    free(extended);

    uint8_t *wrong_format = (uint8_t *)malloc(stop_written);
    SDK_CHECK_TRUE("sdk.state-tracer.allocate-wrong-format",
                   wrong_format != NULL);
    memcpy(wrong_format, exact, stop_written);
    wrong_format[16u] ^= UINT8_C(0x80);
    SDK_CHECK_STATUS("sdk.state-tracer.seed-peer-before-format-reject",
                     GN_STATUS_OK,
                     gn_state_restore_v1(state_peer, exact, stop_written,
                                         &detail, sizeof(detail)));
    SDK_CHECK_STATUS("sdk.state-tracer.seed-witness-before-format-reject",
                     GN_STATUS_OK,
                     gn_state_restore_v1(state_witness, exact, stop_written,
                                         &detail, sizeof(detail)));
    SDK_CHECK_STATUS("sdk.state-tracer.reject-format-mismatch",
                     GN_STATUS_INVALID_ARGUMENT,
                     gn_state_restore_v1(state_peer, wrong_format,
                                         stop_written, &detail,
                                         sizeof(detail)));
    check_diagnostic_restore_resources(state_peer, 0);
    SDK_CHECK_U64("sdk.state-tracer.format-mismatch-reason",
                  GN_STATE_REASON_UNSUPPORTED_FORMAT, detail.reason);
    SDK_CHECK_TRUE("sdk.state-tracer.format-rejection-preserves-machine",
                   sdk_state_future_equal(state_peer, state_witness, 8u));
    free(wrong_format);

    guest_fixture_image fault_fixture;
    gn_manifest fault_manifest;
    make_manifest(&fault_manifest, &fault_fixture,
                  GUEST_FIXTURE_SCENARIO_A);
    fault_fixture.rom[0x100u] = UINT8_C(0x4a);
    fault_fixture.rom[0x101u] = UINT8_C(0xfc);
    SDK_CHECK_STATUS("sdk.state-tracer.load-guest-fault", GN_STATUS_OK,
                     gn_load(instance, &fault_manifest));
    SDK_CHECK_STATUS("sdk.state-tracer.run-guest-fault", GN_STATUS_OK,
                     gn_run(instance, 172u, &source_run));
    SDK_CHECK_STATUS("sdk.state-tracer.guest-fault-reason", GN_RUN_FAULT,
                     source_run.reason);
    failed_written = SIZE_MAX;
    SDK_CHECK_STATUS("sdk.state-tracer.reject-latched-guest-fault",
                     GN_STATUS_INVALID_STATE,
                     gn_state_capture_v1(instance, exact, capacity,
                                         &failed_written, &detail,
                                         sizeof(detail)));
    SDK_CHECK_U64("sdk.state-tracer.guest-fault-count-zero", 0u,
                  failed_written);
    SDK_CHECK_U64("sdk.state-tracer.guest-fault-capture-reason",
                  GN_STATE_REASON_GUEST_FAULT, detail.reason);
    SDK_CHECK_STATUS("sdk.state-tracer.reset-clears-guest-fault",
                     GN_STATUS_OK, gn_reset(instance));
    SDK_CHECK_STATUS("sdk.state-tracer.capture-after-fault-reset",
                     GN_STATUS_OK,
                     gn_state_capture_v1(instance, exact, capacity,
                                         &reset_written, &detail,
                                         sizeof(detail)));
    free(small);
    free(larger);
    free(repeat);
    free(exact);
#endif
}

static void sdk_state_write_u32(uint8_t *bytes, uint32_t value) {
    bytes[0] = (uint8_t)(value >> 24);
    bytes[1] = (uint8_t)(value >> 16);
    bytes[2] = (uint8_t)(value >> 8);
    bytes[3] = (uint8_t)value;
}

#if defined(GN_TEST_NATIVE_SHA256_HOOK)
static int sdk_hex_nibble(char value) {
    if (value >= '0' && value <= '9') return value - '0';
    if (value >= 'a' && value <= 'f') return value - 'a' + 10;
    if (value >= 'A' && value <= 'F') return value - 'A' + 10;
    return -1;
}

static int sdk_sha256_matches_hex(const uint8_t digest[32], const char *hex) {
    for (size_t index = 0u; index < 32u; ++index) {
        const int high = sdk_hex_nibble(hex[index * 2u]);
        const int low = sdk_hex_nibble(hex[index * 2u + 1u]);
        if (high < 0 || low < 0 ||
            digest[index] != (uint8_t)((high << 4) | low)) return 0;
    }
    return hex[64] == '\0';
}

static void diagnostic_sha256_known_answer_vectors(void) {
    uint8_t digest[32];
    static const uint8_t abc[] = "abc";
    static const uint8_t padding_edge[] =
        "abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq";
    static const char block_pattern[] =
        "0123456701234567012345670123456701234567012345670123456701234567";
    uint8_t exact_blocks[640];
    SDK_CHECK_U64("sdk.state-identity.sha256-pattern-size", 64u,
                  sizeof(block_pattern) - 1u);
    for (size_t block = 0u; block < 10u; ++block)
        memcpy(exact_blocks + block * 64u, block_pattern, 64u);
    SDK_CHECK_STATUS("sdk.state-identity.sha256-empty-status", GN_STATUS_OK,
                     gn_test_sha256(NULL, 0u, digest));
    SDK_CHECK_TRUE("sdk.state-identity.sha256-empty-kat",
                   sdk_sha256_matches_hex(digest,
                       "e3b0c44298fc1c149afbf4c8996fb924"
                       "27ae41e4649b934ca495991b7852b855"));
    SDK_CHECK_STATUS("sdk.state-identity.sha256-abc-status", GN_STATUS_OK,
                     gn_test_sha256(abc, sizeof(abc) - 1u, digest));
    SDK_CHECK_TRUE("sdk.state-identity.sha256-abc-kat",
                   sdk_sha256_matches_hex(digest,
                       "ba7816bf8f01cfea414140de5dae2223"
                       "b00361a396177a9cb410ff61f20015ad"));
    SDK_CHECK_STATUS("sdk.state-identity.sha256-padding-edge-status",
                     GN_STATUS_OK,
                     gn_test_sha256(padding_edge,
                                    sizeof(padding_edge) - 1u, digest));
    SDK_CHECK_TRUE("sdk.state-identity.sha256-padding-edge-kat",
                   sdk_sha256_matches_hex(digest,
                       "248d6a61d20638b8e5c026930c3e6039"
                       "a33ce45964ff2167f6ecedd419db06c1"));
    SDK_CHECK_STATUS("sdk.state-identity.sha256-exact-blocks-status",
                     GN_STATUS_OK,
                     gn_test_sha256(exact_blocks, sizeof(exact_blocks), digest));
    SDK_CHECK_TRUE("sdk.state-identity.sha256-exact-blocks-kat",
                   sdk_sha256_matches_hex(digest,
                       "594847328451bdfa85056225462cc1d8"
                       "67d877fb388df0ce35f25ab5562bfbb5"));
    SDK_CHECK_STATUS("sdk.state-identity.sha256-reject-null-input",
                     GN_STATUS_INVALID_ARGUMENT,
                     gn_test_sha256(NULL, 1u, digest));
    SDK_CHECK_STATUS("sdk.state-identity.sha256-reject-null-output",
                     GN_STATUS_INVALID_ARGUMENT,
                     gn_test_sha256(abc, sizeof(abc) - 1u, NULL));
}
#endif

static void diagnostic_identity_exposes_ids_and_rejects_mismatch(void) {
    SDK_CASE("sdk.state-identity.native-identities");
    gn_state_compatibility_info_v1 source_info;
    memset(&source_info, 0xa5, sizeof(source_info));
    SDK_CHECK_STATUS("sdk.state-identity.compatibility", GN_STATUS_OK,
                     gn_state_compatibility_v1(instance, &source_info,
                                               sizeof(source_info)));
    SDK_CHECK_U64("sdk.state-identity.compatibility-size",
                  sizeof(source_info), source_info.size);
    SDK_CHECK_U64("sdk.state-identity.format-id", GN_STATE_FORMAT_V1_ID,
                  source_info.format_id);
    SDK_CHECK_U64("sdk.state-identity.replay-id", GN_STATE_REPLAY_V1_ID,
                  source_info.replay_id);
    SDK_CHECK_U64("sdk.state-identity.durable-save-unsupported", 0u,
                  source_info.durable_save_id);
    SDK_CHECK_U64("sdk.state-identity.public-abi-id", GN_STATE_PUBLIC_ABI_V1_ID,
                  source_info.public_abi_id);
    SDK_CHECK_U64("sdk.state-identity.profile-id", GN_PROFILE_DIAGNOSTIC,
                  source_info.profile_id);
    SDK_CHECK_U64("sdk.state-identity.configuration-id",
                  GN_STATE_CONFIGURATION_DIAGNOSTIC_V1,
                  source_info.configuration_id);

    gn_state_compatibility_info_v1 untouched_info;
    memset(&untouched_info, 0xa5, sizeof(untouched_info));
    SDK_CHECK_STATUS("sdk.state-identity.reject-short-compatibility",
                     GN_STATUS_INVALID_ARGUMENT,
                     gn_state_compatibility_v1(instance, &untouched_info,
                                               sizeof(untouched_info) - 1u));
    SDK_CHECK_U64("sdk.state-identity.short-output-untouched",
                  UINT32_C(0xa5a5a5a5), untouched_info.size);

    size_t capacity = 0u;
    SDK_CHECK_STATUS("sdk.state-identity.capacity", GN_STATUS_OK,
                     gn_state_capacity_v1(instance, &capacity));
    uint8_t *state = (uint8_t *)malloc(capacity);
    uint8_t *mutated = (uint8_t *)malloc(capacity);
    SDK_CHECK_TRUE("sdk.state-identity.allocate-state",
                   state != NULL && mutated != NULL);
    size_t written = 0u;
    gn_state_detail_v1 detail;
    SDK_CHECK_STATUS("sdk.state-identity.capture-source", GN_STATUS_OK,
                     gn_state_capture_v1(instance, state, capacity, &written,
                                         &detail, sizeof(detail)));

    gn_instance *role_order_peer = NULL;
    SDK_CHECK_STATUS("sdk.state-identity.create-role-order-peer", GN_STATUS_OK,
                     gn_create(&role_order_peer));
    guest_fixture_image role_order_fixture;
    gn_manifest role_order_manifest;
    make_manifest(&role_order_manifest, &role_order_fixture,
                  GUEST_FIXTURE_SCENARIO_A);
    const gn_region first_region = role_order_manifest.regions[0];
    role_order_manifest.regions[0] = role_order_manifest.regions[1];
    role_order_manifest.regions[1] = first_region;
    SDK_CHECK_STATUS("sdk.state-identity.load-role-order-peer", GN_STATUS_OK,
                     gn_load(role_order_peer, &role_order_manifest));
    gn_state_compatibility_info_v1 role_order_info;
    SDK_CHECK_STATUS("sdk.state-identity.role-order-compatibility", GN_STATUS_OK,
                     gn_state_compatibility_v1(role_order_peer, &role_order_info,
                                               sizeof(role_order_info)));
    SDK_CHECK_TRUE("sdk.state-identity.role-order-normalized",
                   memcmp(source_info.media_identity_sha256,
                          role_order_info.media_identity_sha256, 32u) == 0);

    SDK_CHECK_STATUS("sdk.state-identity.create-media-mismatch-peer",
                     GN_STATUS_OK, gn_create(&state_peer));
    SDK_CHECK_STATUS("sdk.state-identity.create-media-witness",
                     GN_STATUS_OK, gn_create(&state_witness));
    guest_fixture_image changed_fixture;
    gn_manifest changed_manifest;
    make_manifest(&changed_manifest, &changed_fixture,
                  GUEST_FIXTURE_SCENARIO_A);
    changed_fixture.ram_seed[8u] ^= UINT8_C(0x01);
    SDK_CHECK_STATUS("sdk.state-identity.load-changed-media-peer",
                     GN_STATUS_OK, gn_load(state_peer, &changed_manifest));
    SDK_CHECK_STATUS("sdk.state-identity.load-changed-media-witness",
                     GN_STATUS_OK, load_scenario(state_witness,
                                                 GUEST_FIXTURE_SCENARIO_A));
    gn_state_compatibility_info_v1 changed_info;
    SDK_CHECK_STATUS("sdk.state-identity.changed-media-compatibility",
                     GN_STATUS_OK,
                     gn_state_compatibility_v1(state_peer, &changed_info,
                                               sizeof(changed_info)));
    SDK_CHECK_TRUE("sdk.state-identity.effective-ram-changes-identity",
                   memcmp(source_info.media_identity_sha256,
                          changed_info.media_identity_sha256, 32u) != 0);
    SDK_CHECK_STATUS("sdk.state-identity.reject-media-mismatch",
                     GN_STATUS_INVALID_MEDIA,
                     gn_state_restore_v1(state_peer, state, written, &detail,
                                         sizeof(detail)));
    SDK_CHECK_U64("sdk.state-identity.media-mismatch-reason",
                  GN_STATE_REASON_MEDIA_IDENTITY, detail.reason);
    SDK_CHECK_TRUE("sdk.state-identity.media-reject-no-mutation",
                   sdk_state_future_equal(state_peer, state_witness, 8u));

    memcpy(mutated, state, written);
    sdk_state_write_u32(mutated + 20u, GN_STATE_REPLAY_V1_ID + 1u);
    SDK_CHECK_STATUS("sdk.state-identity.reject-replay-id",
                     GN_STATUS_UNSUPPORTED_PROFILE,
                     gn_state_restore_v1(role_order_peer, mutated, written,
                                         &detail, sizeof(detail)));
    SDK_CHECK_U64("sdk.state-identity.replay-id-reason",
                  GN_STATE_REASON_REPLAY_IDENTITY, detail.reason);
    memcpy(mutated, state, written);
    sdk_state_write_u32(mutated + 24u, GN_PROFILE_DIAGNOSTIC + 1u);
    SDK_CHECK_STATUS("sdk.state-identity.reject-profile-id",
                     GN_STATUS_UNSUPPORTED_PROFILE,
                     gn_state_restore_v1(role_order_peer, mutated, written,
                                         &detail, sizeof(detail)));
    SDK_CHECK_U64("sdk.state-identity.profile-id-reason",
                  GN_STATE_REASON_PROFILE_IDENTITY, detail.reason);
    memcpy(mutated, state, written);
    sdk_state_write_u32(mutated + 28u,
                        GN_STATE_CONFIGURATION_DIAGNOSTIC_V1 + 1u);
    SDK_CHECK_STATUS("sdk.state-identity.reject-configuration-id",
                     GN_STATUS_UNSUPPORTED_PROFILE,
                     gn_state_restore_v1(role_order_peer, mutated, written,
                                         &detail, sizeof(detail)));
    SDK_CHECK_U64("sdk.state-identity.configuration-id-reason",
                  GN_STATE_REASON_CONFIGURATION_IDENTITY, detail.reason);
    memcpy(mutated, state, written);
    mutated[68u] = UINT8_C(1);
    SDK_CHECK_STATUS("sdk.state-identity.reject-reserved-corruption",
                     GN_STATUS_INVALID_MEDIA,
                     gn_state_restore_v1(role_order_peer, mutated, written,
                                         &detail, sizeof(detail)));
    SDK_CHECK_U64("sdk.state-identity.reserved-corruption-reason",
                  GN_STATE_REASON_RESERVED, detail.reason);

    gn_state_compatibility_info_v1 after_reset_info;
    SDK_CHECK_STATUS("sdk.state-identity.reset-preserves-media-identity",
                     GN_STATUS_OK, gn_reset(instance));
    SDK_CHECK_STATUS("sdk.state-identity.compatibility-after-reset",
                     GN_STATUS_OK,
                     gn_state_compatibility_v1(instance, &after_reset_info,
                                               sizeof(after_reset_info)));
    SDK_CHECK_TRUE("sdk.state-identity.reset-keeps-cached-identity",
                   memcmp(source_info.media_identity_sha256,
                          after_reset_info.media_identity_sha256, 32u) == 0);
#if defined(GN_TEST_NATIVE_SHA256_HOOK)
    diagnostic_sha256_known_answer_vectors();
#else
    SDK_CHECK_TRUE("sdk.state-identity.sha256-test-hook-available", 0);
#endif
    free(mutated);
    free(state);
    gn_destroy(role_order_peer);
}

enum { SDK_YM_SAMPLE_BYTES = 4096u, SDK_YM_FUTURE_CLOCKS = 512u };

typedef struct sdk_ym_owner {
    uint8_t *samples;
    size_t sample_bytes;
    uint64_t clock_position;
    uint64_t irq_clocks[16];
    int irq_levels[16];
    size_t irq_count;
    size_t sample_reads;
} sdk_ym_owner;

static int sdk_ym_owner_init(sdk_ym_owner *owner) {
    memset(owner, 0, sizeof(*owner));
    owner->samples = (uint8_t *)malloc(SDK_YM_SAMPLE_BYTES);
    if (owner->samples == NULL) return 0;
    owner->sample_bytes = SDK_YM_SAMPLE_BYTES;
    for (size_t index = 0u; index < owner->sample_bytes; ++index)
        owner->samples[index] = (uint8_t)((index * 37u + 0x6du) & 0xffu);
    return 1;
}

static void sdk_ym_owner_destroy(sdk_ym_owner *owner) {
    free(owner->samples);
    memset(owner, 0, sizeof(*owner));
}

static int sdk_ym_read(void *userdata, uint32_t access, uint32_t address,
                       uint8_t *value) {
    sdk_ym_owner *owner = (sdk_ym_owner *)userdata;
    if (owner == NULL || value == NULL || owner->samples == NULL ||
        (access != YM2610_CANDIDATE_ACCESS_ADPCM_A &&
         access != YM2610_CANDIDATE_ACCESS_ADPCM_B) ||
        address >= owner->sample_bytes) return -1;
    *value = owner->samples[address];
    ++owner->sample_reads;
    return 0;
}

static int sdk_ym_write(void *userdata, uint32_t access, uint32_t address,
                        uint8_t value) {
    (void)userdata;
    (void)access;
    (void)address;
    (void)value;
    return 0;
}

static void sdk_ym_irq(void *userdata, int asserted) {
    sdk_ym_owner *owner = (sdk_ym_owner *)userdata;
    if (owner == NULL || owner->irq_count >= 16u) return;
    owner->irq_clocks[owner->irq_count] = owner->clock_position;
    owner->irq_levels[owner->irq_count] = asserted;
    ++owner->irq_count;
}

static const ym2610_candidate_callbacks SDK_YM_CALLBACKS = {
    sdk_ym_read, sdk_ym_write, sdk_ym_irq,
    SDK_YM_SAMPLE_BYTES, SDK_YM_SAMPLE_BYTES, 2u
};

static ym2610_candidate_status sdk_ym_write_register(
    ym2610_candidate *candidate, uint8_t reg, uint8_t value) {
    ym2610_candidate_status status = ym2610_candidate_write(candidate, 0u, reg);
    if (status != YM2610_CANDIDATE_OK) return status;
    return ym2610_candidate_write(candidate, 1u, value);
}

static ym2610_candidate_status sdk_ym_program_tone(
    ym2610_candidate *candidate) {
    ym2610_candidate_status status;
    for (uint8_t offset = 0u; offset < 16u; offset += 4u) {
        status = sdk_ym_write_register(candidate, (uint8_t)(0x30u + offset + 1u), 1u);
        if (status != YM2610_CANDIDATE_OK) return status;
        status = sdk_ym_write_register(candidate, (uint8_t)(0x40u + offset + 1u), 0u);
        if (status != YM2610_CANDIDATE_OK) return status;
        status = sdk_ym_write_register(candidate, (uint8_t)(0x50u + offset + 1u), 0x1fu);
        if (status != YM2610_CANDIDATE_OK) return status;
        status = sdk_ym_write_register(candidate, (uint8_t)(0x60u + offset + 1u), 0u);
        if (status != YM2610_CANDIDATE_OK) return status;
        status = sdk_ym_write_register(candidate, (uint8_t)(0x70u + offset + 1u), 0u);
        if (status != YM2610_CANDIDATE_OK) return status;
        status = sdk_ym_write_register(candidate, (uint8_t)(0x80u + offset + 1u), 0x0fu);
        if (status != YM2610_CANDIDATE_OK) return status;
    }
    status = sdk_ym_write_register(candidate, 0xa1u, 0x80u);
    if (status != YM2610_CANDIDATE_OK) return status;
    status = sdk_ym_write_register(candidate, 0xa5u, 0x22u);
    if (status != YM2610_CANDIDATE_OK) return status;
    status = sdk_ym_write_register(candidate, 0xb1u, 0x07u);
    if (status != YM2610_CANDIDATE_OK) return status;
    status = sdk_ym_write_register(candidate, 0xb5u, 0xc0u);
    if (status != YM2610_CANDIDATE_OK) return status;
    status = sdk_ym_write_register(candidate, 0x28u, 0xf1u);
    if (status != YM2610_CANDIDATE_OK) return status;
    status = sdk_ym_write_register(candidate, 0u, 1u);
    if (status != YM2610_CANDIDATE_OK) return status;
    status = sdk_ym_write_register(candidate, 1u, 0u);
    if (status != YM2610_CANDIDATE_OK) return status;
    status = sdk_ym_write_register(candidate, 7u, 0x3eu);
    if (status != YM2610_CANDIDATE_OK) return status;
    return sdk_ym_write_register(candidate, 8u, 0x0fu);
}

static ym2610_candidate_status sdk_ym_program_timer_a(
    ym2610_candidate *candidate) {
    ym2610_candidate_status status = sdk_ym_write_register(candidate, 0x24u, 0xffu);
    if (status != YM2610_CANDIDATE_OK) return status;
    status = sdk_ym_write_register(candidate, 0x25u, 0x03u);
    if (status != YM2610_CANDIDATE_OK) return status;
    return sdk_ym_write_register(candidate, 0x27u, 0x05u);
}

static int sdk_ym_clock(ym2610_candidate *candidate, sdk_ym_owner *owner,
                        uint32_t clocks, int32_t *samples,
                        size_t sample_capacity, size_t *frames) {
    *frames = 0u;
    for (uint32_t clock = 0u; clock < clocks; ++clock) {
        int32_t frame[3] = {0, 0, 0};
        size_t produced = 0u;
        ++owner->clock_position;
        if (ym2610_candidate_clock(candidate, 1u, frame, 1u, &produced) !=
            YM2610_CANDIDATE_OK) return 0;
        if (produced != 0u) {
            if (samples == NULL || *frames >= sample_capacity) return 0;
            memcpy(samples + (*frames * 3u), frame, sizeof(frame));
            ++*frames;
        }
    }
    return 1;
}

static size_t sdk_ym_nonzero_values(const int32_t *samples, size_t count) {
    size_t nonzero = 0u;
    for (size_t index = 0u; index < count; ++index)
        if (samples[index] != 0) ++nonzero;
    return nonzero;
}

static void ym2610_state_round_trip_continues_pcm_and_timer_after_source_destruction(void) {
    SDK_CASE("sdk.state-ym.nonzero-continuation-and-owner-rebind");
    sdk_ym_owner source_owner, reference_owner, destination_owner;
    memset(&source_owner, 0, sizeof(source_owner));
    memset(&reference_owner, 0, sizeof(reference_owner));
    memset(&destination_owner, 0, sizeof(destination_owner));
    ym2610_candidate *source = NULL, *reference = NULL, *staged = NULL;
    uint8_t *bytes = NULL;
    int32_t source_warm[256u * 3u] = {0};
    int32_t reference_warm[256u * 3u] = {0};
    int32_t source_future[64u * 3u] = {0};
    int32_t reference_future[64u * 3u] = {0};
    size_t source_warm_frames = 0u, reference_warm_frames = 0u;
    size_t source_pre_frames = 0u, reference_pre_frames = 0u;
    size_t source_future_frames = 0u, reference_future_frames = 0u;
    size_t written = 0u, state_bytes = 0u;
    size_t rebind_allocation_points = 0u;
    int64_t rebind_lifetime_balance = -1;
    ym2610_candidate_state_detail detail = {0};
    ym2610_candidate_observation reference_before = {0}, reference_after = {0};
    ym2610_candidate_observation staged_before = {0}, staged_after = {0};
    int setup_ok = sdk_ym_owner_init(&source_owner) &&
                   sdk_ym_owner_init(&reference_owner) &&
                   sdk_ym_owner_init(&destination_owner);
    int continued = 0, owners_rebound = 0, timer_observed = 0;

    if (setup_ok &&
        ym2610_candidate_create(&SDK_YM_CALLBACKS, &source_owner, &source) == YM2610_CANDIDATE_OK &&
        ym2610_candidate_create(&SDK_YM_CALLBACKS, &reference_owner, &reference) == YM2610_CANDIDATE_OK &&
        sdk_ym_program_tone(source) == YM2610_CANDIDATE_OK &&
        sdk_ym_program_tone(reference) == YM2610_CANDIDATE_OK &&
        sdk_ym_clock(source, &source_owner, 4096u, source_warm, 256u,
                     &source_warm_frames) &&
        sdk_ym_clock(reference, &reference_owner, 4096u, reference_warm, 256u,
                     &reference_warm_frames) &&
        sdk_ym_program_timer_a(source) == YM2610_CANDIDATE_OK &&
        sdk_ym_program_timer_a(reference) == YM2610_CANDIDATE_OK &&
        sdk_ym_clock(source, &source_owner, 48u, source_future, 64u,
                     &source_pre_frames) &&
        sdk_ym_clock(reference, &reference_owner, 48u, reference_future, 64u,
                     &reference_pre_frames) &&
        ym2610_candidate_state_size(source, &state_bytes) == YM2610_CANDIDATE_OK &&
        state_bytes != 0u) {
        bytes = (uint8_t *)malloc(state_bytes);
        if (bytes != NULL &&
            ym2610_candidate_state_capture(source, bytes, state_bytes,
                                           &written) == YM2610_CANDIDATE_OK &&
            written == state_bytes) {
            ym2610_candidate_destroy(source);
            source = NULL;
            sdk_ym_owner_destroy(&source_owner);
            if (ym2610_candidate_state_stage(bytes, written, &staged, &detail) ==
                    YM2610_CANDIDATE_OK &&
                ym2610_candidate_test_state_rebind_failpoint(
                    staged, &SDK_YM_CALLBACKS, &destination_owner, 0u,
                    &rebind_allocation_points, &rebind_lifetime_balance) ==
                    YM2610_CANDIDATE_OK &&
                ym2610_candidate_state_rebind(staged, &SDK_YM_CALLBACKS,
                                              &destination_owner) ==
                    YM2610_CANDIDATE_OK &&
                ym2610_candidate_observe(reference, &reference_before) ==
                    YM2610_CANDIDATE_OK &&
                ym2610_candidate_observe(staged, &staged_before) ==
                    YM2610_CANDIDATE_OK) {
                owners_rebound = destination_owner.irq_count == 0u &&
                    destination_owner.sample_reads == 0u;
                destination_owner.clock_position =
                    reference_owner.clock_position;
                reference_owner.irq_count = 0u;
                destination_owner.irq_count = 0u;
                if (sdk_ym_clock(reference, &reference_owner,
                                 SDK_YM_FUTURE_CLOCKS, reference_future,
                                 64u, &reference_future_frames) &&
                    sdk_ym_clock(staged, &destination_owner,
                                 SDK_YM_FUTURE_CLOCKS, source_future,
                                 64u, &source_future_frames) &&
                    ym2610_candidate_observe(reference, &reference_after) ==
                        YM2610_CANDIDATE_OK &&
                    ym2610_candidate_observe(staged, &staged_after) ==
                        YM2610_CANDIDATE_OK) {
                    continued = reference_future_frames == source_future_frames &&
                        memcmp(reference_future, source_future,
                               reference_future_frames * 3u * sizeof(int32_t)) == 0;
                    timer_observed = reference_owner.irq_count != 0u &&
                        reference_owner.irq_count == destination_owner.irq_count &&
                        memcmp(reference_owner.irq_clocks,
                               destination_owner.irq_clocks,
                               reference_owner.irq_count * sizeof(uint64_t)) == 0 &&
                        memcmp(reference_owner.irq_levels,
                               destination_owner.irq_levels,
                               reference_owner.irq_count * sizeof(int)) == 0 &&
                        reference_after.timer_expirations >
                            reference_before.timer_expirations &&
                        staged_after.timer_expirations >
                            staged_before.timer_expirations;
                }
            }
        }
    }

    ym2610_candidate_destroy(source);
    ym2610_candidate_destroy(reference);
    ym2610_candidate_destroy(staged);
    free(bytes);
    sdk_ym_owner_destroy(&source_owner);
    sdk_ym_owner_destroy(&reference_owner);
    sdk_ym_owner_destroy(&destination_owner);

    SDK_CHECK_TRUE("sdk.state-ym.valid-independent-setup", setup_ok);
    SDK_CHECK_U64("sdk.state-ym.warm-nonzero-fm", 1u,
                  sdk_ym_nonzero_values(reference_warm,
                                        reference_warm_frames * 3u) != 0u);
    SDK_CHECK_U64("sdk.state-ym.warm-frame-count", 256u, reference_warm_frames);
    SDK_CHECK_TRUE("sdk.state-ym.stage-rebound-without-callbacks", owners_rebound);
    SDK_CHECK_TRUE("sdk.state-ym.rebind-is-no-throw-no-allocation",
                   rebind_allocation_points == 0u &&
                       rebind_lifetime_balance == 0);
    SDK_CHECK_TRUE("sdk.state-ym.future-pcm-equal", continued);
    SDK_CHECK_TRUE("sdk.state-ym.future-timer-and-irq-equal", timer_observed);
    SDK_CHECK_TRUE("sdk.state-ym.future-nonzero-waveform",
                   sdk_ym_nonzero_values(reference_future,
                                         reference_future_frames * 3u) != 0u);
}

static void ym2610_state_uses_canonical_scalars_and_rejects_invalid_nested_input(void) {
    SDK_CASE("sdk.state-ym.canonical-scalar-and-hostile-input");
    sdk_ym_owner owner;
    memset(&owner, 0, sizeof(owner));
    ym2610_candidate *candidate = NULL, *staged = NULL;
    uint8_t *valid = NULL, *mutated = NULL;
    size_t state_bytes = 0u, written = 0u, second_written = 0u;
    ym2610_candidate_state_detail detail = {0};
    int boolean_found = 0, enum_found = 0, nested_range_found = 0;
    int live_unchanged = 0;
    int32_t scalar_samples[18u * 3u] = {0};
    int setup_ok = sdk_ym_owner_init(&owner) &&
        ym2610_candidate_create(&SDK_YM_CALLBACKS, &owner, &candidate) ==
            YM2610_CANDIDATE_OK;
    int deterministic = 0, scalar_vector = 0, boundary_rejection = 0;
    int all_truncations_rejected = 1, all_extensions_rejected = 1;
    int legal_eos_status_accepted = 0;
    if (setup_ok && ym2610_candidate_reset(candidate) == YM2610_CANDIDATE_OK &&
        ym2610_candidate_state_size(candidate, &state_bytes) == YM2610_CANDIDATE_OK) {
        valid = (uint8_t *)malloc((state_bytes * 2u) + 1u);
        mutated = (uint8_t *)malloc(state_bytes);
        if (valid != NULL && mutated != NULL &&
            ym2610_candidate_state_capture(candidate, valid, state_bytes,
                                           &written) == YM2610_CANDIDATE_OK &&
            written == state_bytes) {
            uint8_t *second = (uint8_t *)malloc(state_bytes);
            if (second != NULL &&
                ym2610_candidate_state_capture(candidate, second, state_bytes,
                                               &second_written) ==
                    YM2610_CANDIDATE_OK) {
                deterministic = second_written == written &&
                    memcmp(valid, second, written) == 0;
            }
            free(second);

            if (sdk_ym_clock(candidate, &owner, 0x123u, scalar_samples, 18u,
                             &second_written) &&
                ym2610_candidate_state_capture(candidate, valid, state_bytes,
                                               &written) == YM2610_CANDIDATE_OK) {
                scalar_vector = written == state_bytes &&
                    valid[0] == 'G' && valid[1] == 'Y' &&
                    valid[2] == 'M' && valid[3] == '1' &&
                    valid[4] == 0u && valid[5] == 0u &&
                    valid[6] == 0u && valid[7] == 1u &&
                    valid[8] == 0u && valid[9] == 0u &&
                    valid[10] == 0u && valid[11] == 0u &&
                    valid[12] == 0u && valid[13] == 0u &&
                    valid[14] == 1u && valid[15] == 0x23u &&
                    valid[42] == 3u && valid[43] == 0u &&
                    valid[49] == 1u && valid[50] == 0x23u;
            }

            const ym2610_candidate_status truncated_status =
                ym2610_candidate_state_validate(valid, written - 1u, &detail);
            const ym2610_candidate_state_reason truncated_reason = detail.reason;
            const size_t truncated_offset = detail.offset;
            const size_t truncated_consumed = detail.consumed;
            valid[written] = 0xa5u;
            const ym2610_candidate_status extended_status =
                ym2610_candidate_state_validate(valid, written + 1u, &detail);
            boundary_rejection = truncated_status != YM2610_CANDIDATE_OK &&
                truncated_reason == YM2610_CANDIDATE_STATE_REASON_TRUNCATED &&
                truncated_offset == written - 1u &&
                truncated_consumed == written - 1u &&
                extended_status != YM2610_CANDIDATE_OK &&
                detail.reason == YM2610_CANDIDATE_STATE_REASON_TRAILING &&
                detail.offset == written && detail.consumed == written;

            for (size_t prefix = 0u; prefix < written; ++prefix) {
                const ym2610_candidate_status status =
                    ym2610_candidate_state_validate(valid, prefix, &detail);
                all_truncations_rejected &=
                    status == YM2610_CANDIDATE_INVALID_ARGUMENT &&
                    detail.reason == YM2610_CANDIDATE_STATE_REASON_TRUNCATED &&
                    detail.offset == prefix && detail.consumed == prefix;
            }
            for (size_t extra = 1u; extra <= written; ++extra) {
                memset(valid + written, 0xa5, extra);
                const ym2610_candidate_status status =
                    ym2610_candidate_state_validate(valid, written + extra,
                                                    &detail);
                all_extensions_rejected &=
                    status == YM2610_CANDIDATE_INVALID_ARGUMENT &&
                    detail.reason == YM2610_CANDIDATE_STATE_REASON_TRAILING &&
                    detail.offset == written && detail.consumed == written;
            }

            memcpy(mutated, valid, written);
            mutated[53u] = 0xffu;
            const ym2610_candidate_status address_status =
                ym2610_candidate_state_stage(mutated, written, &staged, &detail);
            boundary_rejection = boundary_rejection &&
                address_status == YM2610_CANDIDATE_INVALID_ARGUMENT &&
                staged == NULL &&
                detail.reason == YM2610_CANDIDATE_STATE_REASON_RANGE;

            memcpy(mutated, valid, written);
            mutated[40u] = 2u;
            boolean_found =
                ym2610_candidate_state_validate(mutated, written, &detail) ==
                    YM2610_CANDIDATE_INVALID_ARGUMENT &&
                detail.reason == YM2610_CANDIDATE_STATE_REASON_BOOLEAN;

            memcpy(mutated, valid, written);
            mutated[55u] = 0xffu;
            legal_eos_status_accepted =
                ym2610_candidate_state_validate(mutated, written, &detail) ==
                    YM2610_CANDIDATE_OK &&
                detail.reason == YM2610_CANDIDATE_STATE_REASON_NONE;

            for (size_t offset = 57u; offset < written; ++offset) {
                memcpy(mutated, valid, written);
                mutated[offset] = 0xffu;
                const ym2610_candidate_status status =
                    ym2610_candidate_state_validate(mutated, written, &detail);
                if (status == YM2610_CANDIDATE_INVALID_ARGUMENT &&
                    detail.reason == YM2610_CANDIDATE_STATE_REASON_ENUM)
                    enum_found = 1;
                if (status == YM2610_CANDIDATE_INVALID_ARGUMENT &&
                    detail.reason == YM2610_CANDIDATE_STATE_REASON_RANGE &&
                    detail.offset > 1000u)
                    nested_range_found = 1;
                if (boolean_found && enum_found && nested_range_found) break;
            }

            if (ym2610_candidate_state_capture(candidate, mutated, state_bytes,
                                               &second_written) ==
                    YM2610_CANDIDATE_OK && second_written == written) {
                live_unchanged = memcmp(valid, mutated, written) == 0 &&
                    owner.irq_count == 0u && owner.sample_reads == 0u;
            }
        }
    }
    ym2610_candidate_destroy(staged);
    ym2610_candidate_destroy(candidate);
    free(valid);
    free(mutated);
    sdk_ym_owner_destroy(&owner);

    SDK_CHECK_TRUE("sdk.state-ym.setup", setup_ok);
    SDK_CHECK_TRUE("sdk.state-ym.canonical-bytes-repeat", deterministic);
    SDK_CHECK_TRUE("sdk.state-ym.big-endian-scalar-vector", scalar_vector);
    SDK_CHECK_TRUE("sdk.state-ym.exact-nested-boundaries", boundary_rejection);
    SDK_CHECK_TRUE("sdk.state-ym.every-truncated-prefix-rejected",
                   all_truncations_rejected);
    SDK_CHECK_TRUE("sdk.state-ym.every-extension-length-rejected",
                   all_extensions_rejected);
    SDK_CHECK_TRUE("sdk.state-ym.accepts-full-eos-status-bits",
                   legal_eos_status_accepted);
    SDK_CHECK_TRUE("sdk.state-ym.rejects-raw-boolean", boolean_found);
    SDK_CHECK_TRUE("sdk.state-ym.rejects-invalid-enum", enum_found);
    SDK_CHECK_TRUE("sdk.state-ym.rejects-nested-index-range", nested_range_found);
    SDK_CHECK_TRUE("sdk.state-ym.hostile-input-preserves-live-target",
                   live_unchanged);
}

static void ym2610_state_allocation_failures_are_swept_and_atomic(void) {
    SDK_CASE("sdk.state-ym.allocation-failure-sweeps");
    enum { SDK_YM_CONSTRUCTOR_ALLOCATION_POINTS = 1 + 6 + 24 + 6 + 1 };
    sdk_ym_owner owner;
    memset(&owner, 0, sizeof(owner));
    ym2610_candidate *candidate = NULL;
    uint8_t *bytes = NULL, *destination = NULL, *after = NULL;
    size_t state_bytes = 0u, written = 0u, attempts = 0u;
    int64_t lifetime_balance = -1;
    ym2610_candidate_observation observation_before = {0}, observation_after = {0};
    int setup_ok = sdk_ym_owner_init(&owner) &&
        ym2610_candidate_create(&SDK_YM_CALLBACKS, &owner, &candidate) ==
            YM2610_CANDIDATE_OK &&
        ym2610_candidate_reset(candidate) == YM2610_CANDIDATE_OK &&
        ym2610_candidate_state_size(candidate, &state_bytes) == YM2610_CANDIDATE_OK;
    int create_sweep_ok = 1, stage_sweep_ok = 1, capture_sweep_ok = 1;
    int construction_balanced = 1, target_untouched = 1;
    size_t create_failures = 0u, stage_failures = 0u, capture_failures = 0u;
    size_t capture_success_points = 0u;

    if (setup_ok) {
        bytes = (uint8_t *)malloc(state_bytes);
        destination = (uint8_t *)malloc(state_bytes);
        after = (uint8_t *)malloc(state_bytes);
        setup_ok = bytes != NULL && destination != NULL && after != NULL &&
            ym2610_candidate_state_capture(candidate, bytes, state_bytes,
                                           &written) == YM2610_CANDIDATE_OK &&
            written == state_bytes &&
            ym2610_candidate_observe(candidate, &observation_before) ==
                YM2610_CANDIDATE_OK;
    }

    for (size_t fail_at = 0u;
         setup_ok && fail_at <= SDK_YM_CONSTRUCTOR_ALLOCATION_POINTS;
         ++fail_at) {
        const ym2610_candidate_status status =
            ym2610_candidate_test_state_create_failpoint(
                fail_at, &attempts, &lifetime_balance);
        construction_balanced &= lifetime_balance == 0;
        if (fail_at < SDK_YM_CONSTRUCTOR_ALLOCATION_POINTS) {
            create_failures += status == YM2610_CANDIDATE_NO_MEMORY;
            create_sweep_ok &= status == YM2610_CANDIDATE_NO_MEMORY &&
                attempts == fail_at + 1u;
        } else {
            create_sweep_ok &= status == YM2610_CANDIDATE_OK &&
                attempts == SDK_YM_CONSTRUCTOR_ALLOCATION_POINTS;
        }

        const ym2610_candidate_status stage_status =
            ym2610_candidate_test_state_stage_failpoint(
                bytes, state_bytes, fail_at, &attempts, &lifetime_balance);
        construction_balanced &= lifetime_balance == 0;
        if (fail_at < SDK_YM_CONSTRUCTOR_ALLOCATION_POINTS) {
            stage_failures += stage_status == YM2610_CANDIDATE_NO_MEMORY;
            stage_sweep_ok &= stage_status == YM2610_CANDIDATE_NO_MEMORY &&
                attempts == fail_at + 1u;
        } else {
            stage_sweep_ok &= stage_status == YM2610_CANDIDATE_OK &&
                attempts == SDK_YM_CONSTRUCTOR_ALLOCATION_POINTS;
        }
    }

    for (size_t fail_at = 0u; setup_ok && fail_at < 64u; ++fail_at) {
        memset(destination, 0xa5, state_bytes);
        written = SIZE_MAX;
        const ym2610_candidate_status status =
            ym2610_candidate_test_state_capture_failpoint(
                candidate, destination, state_bytes, &written, fail_at,
                &attempts, &lifetime_balance);
        construction_balanced &= lifetime_balance == 0;
        if (status == YM2610_CANDIDATE_NO_MEMORY) {
            ++capture_failures;
            capture_sweep_ok &= attempts == fail_at + 1u && written == 0u;
            for (size_t index = 0u; index < state_bytes; ++index)
                target_untouched &= destination[index] == 0xa5u;
            continue;
        }
        capture_success_points = attempts;
        capture_sweep_ok &= status == YM2610_CANDIDATE_OK &&
            written == state_bytes && capture_failures != 0u;
        if (status == YM2610_CANDIDATE_OK)
            target_untouched &= memcmp(destination, bytes, state_bytes) == 0;
        break;
    }

    if (setup_ok) {
        target_untouched &= ym2610_candidate_observe(candidate, &observation_after) ==
                YM2610_CANDIDATE_OK &&
            observation_before.clocks == observation_after.clocks &&
            observation_before.register_writes == observation_after.register_writes &&
            observation_before.timer_expirations == observation_after.timer_expirations &&
            observation_before.irq_assertions == observation_after.irq_assertions &&
            observation_before.irq_deassertions == observation_after.irq_deassertions &&
            owner.irq_count == 0u && owner.sample_reads == 0u;
        written = 0u;
        target_untouched &= ym2610_candidate_state_capture(
                candidate, after, state_bytes, &written) == YM2610_CANDIDATE_OK &&
            written == state_bytes && memcmp(bytes, after, state_bytes) == 0;
    }

    ym2610_candidate_destroy(candidate);
    free(bytes);
    free(destination);
    free(after);
    sdk_ym_owner_destroy(&owner);

    SDK_CHECK_TRUE("sdk.state-ym.allocation-fixture-ready", setup_ok);
    SDK_CHECK_U64("sdk.state-ym.candidate-construction-failpoint-sweep",
                  SDK_YM_CONSTRUCTOR_ALLOCATION_POINTS, create_failures);
    SDK_CHECK_TRUE("sdk.state-ym.candidate-construction-failpoints-cover-all-sites",
                   create_sweep_ok);
    SDK_CHECK_U64("sdk.state-ym.staged-construction-failpoint-sweep",
                  SDK_YM_CONSTRUCTOR_ALLOCATION_POINTS, stage_failures);
    SDK_CHECK_TRUE("sdk.state-ym.staged-construction-failpoints-cover-all-sites",
                   stage_sweep_ok);
    SDK_CHECK_TRUE("sdk.state-ym.capture-vector-growth-failpoint-sweep",
                   capture_sweep_ok && capture_success_points != 0u);
    SDK_CHECK_U64("sdk.state-ym.capture-vector-growth-allocation-count",
                  capture_success_points, capture_failures);
    SDK_CHECK_TRUE("sdk.state-ym.partial-construction-lifetimes-balanced",
                   construction_balanced);
    SDK_CHECK_TRUE("sdk.state-ym.failure-preserves-target-bytes-and-observations",
                   target_untouched);
}

static void assert_run_result(const char *label, uint64_t request,
                              uint64_t elapsed, uint64_t overshoot,
                              uint64_t instructions, uint32_t pc,
                              gn_run_reason reason) {
    gn_run_result run;
    memset(&run, 0xa5, sizeof(run));
    SDK_CHECK_STATUS(label, GN_STATUS_OK, gn_run(instance, request, &run));
    SDK_CHECK_U64("sdk.run.requested", request, run.requested_cycles);
    SDK_CHECK_U64("sdk.run.elapsed", elapsed, run.elapsed_cycles);
    SDK_CHECK_U64("sdk.run.overshoot", overshoot, run.overshoot_cycles);
    SDK_CHECK_U64("sdk.run.instructions", instructions, run.instructions);
    SDK_CHECK_U64("sdk.run.pc", pc, run.boundary_pc);
    SDK_CHECK_STATUS("sdk.run.reason", reason, run.reason);
}

static void bounded_run_reports_actual_progress_and_preserves_invalid_requests(void) {
    SDK_CASE("sdk.run.budget-boundaries");
    uint64_t before = 0u;
    uint64_t after = 0u;
    SDK_CHECK_STATUS("sdk.run.digest-before-zero", GN_STATUS_OK,
                     gn_test_image_digest(instance, &before));

    assert_run_result("sdk.run.zero-status", 0u, 0u, 0u, 0u, 0x100u,
                      GN_RUN_BUDGET);
    SDK_CHECK_STATUS("sdk.run.digest-after-zero", GN_STATUS_OK,
                     gn_test_image_digest(instance, &after));
    SDK_CHECK_U64("sdk.run.zero-does-not-change-state", before, after);

    assert_run_result("sdk.run.one-status", 1u, 40u, 39u, 0u, 0x100u,
                      GN_RUN_BUDGET);
    SDK_CHECK_STATUS("sdk.run.reset-before-39", GN_STATUS_OK, gn_reset(instance));
    assert_run_result("sdk.run.39-status", 39u, 40u, 1u, 0u, 0x100u,
                      GN_RUN_BUDGET);
    SDK_CHECK_STATUS("sdk.run.reset-before-40", GN_STATUS_OK, gn_reset(instance));
    assert_run_result("sdk.run.40-status", 40u, 40u, 0u, 0u, 0x100u,
                      GN_RUN_BUDGET);
    SDK_CHECK_STATUS("sdk.run.reset-before-41", GN_STATUS_OK, gn_reset(instance));
    assert_run_result("sdk.run.41-status", 41u, 44u, 3u, 1u, 0x102u,
                      GN_RUN_BUDGET);

    SDK_CHECK_STATUS("sdk.run.reset-before-172", GN_STATUS_OK, gn_reset(instance));
    assert_run_result("sdk.run.172-status", 172u, 172u, 0u, 12u, 0x12eu,
                      GN_RUN_STOPPED);
    assert_run_result("sdk.run.173-status", 173u, 173u, 0u, 0u, 0x12eu,
                      GN_RUN_STOPPED);
    SDK_CHECK_STATUS("sdk.run.reset-before-maximum", GN_STATUS_OK,
                     gn_reset(instance));
    assert_run_result("sdk.run.maximum-status", GN_MAX_CYCLE_BUDGET,
                      GN_MAX_CYCLE_BUDGET, 0u, 12u, 0x12eu, GN_RUN_STOPPED);

    SDK_CHECK_STATUS("sdk.run.reset-before-invalid", GN_STATUS_OK,
                     gn_reset(instance));
    SDK_CHECK_STATUS("sdk.run.digest-before-invalid", GN_STATUS_OK,
                     gn_test_image_digest(instance, &before));
    gn_run_result invalid;
    memset(&invalid, 0xa5, sizeof(invalid));
    SDK_CHECK_STATUS("sdk.run.reject-over-maximum", GN_STATUS_INVALID_ARGUMENT,
                     gn_run(instance, GN_MAX_CYCLE_BUDGET + 1u, &invalid));
    SDK_CHECK_U64("sdk.run.invalid-clears-request", 0u,
                  invalid.requested_cycles);
    SDK_CHECK_U64("sdk.run.invalid-clears-elapsed", 0u, invalid.elapsed_cycles);
    SDK_CHECK_STATUS("sdk.run.digest-after-invalid", GN_STATUS_OK,
                     gn_test_image_digest(instance, &after));
    SDK_CHECK_U64("sdk.run.invalid-does-not-change-state", before, after);
}

static void stopped_guest_consumes_idle_budget_without_dispatches(void) {
    SDK_CASE("sdk.run.stop-idle-progress");
    assert_run_result("sdk.run.stop-before-idle", 172u, 172u, 0u, 12u,
                      0x12eu, GN_RUN_STOPPED);
    assert_run_result("sdk.run.stop-idle", 21u, 21u, 0u, 0u, 0x12eu,
                      GN_RUN_STOPPED);
}

static void reset_debt_overflow_is_rejected_before_any_event_mutation(void) {
    SDK_CASE("sdk.run.counter-overflow-atomic");
    uint64_t before = 0u;
    uint64_t after = 0u;
    gn_run_result completed;
    SDK_CHECK_STATUS("sdk.run.overflow-establish-stop", GN_STATUS_OK,
                     gn_run(instance, 172u, &completed));
    SDK_CHECK_STATUS("sdk.run.overflow-establish-stop-reason", GN_RUN_STOPPED,
                     completed.reason);
    SDK_CHECK_STATUS("sdk.run.overflow-seed-counters", GN_STATUS_OK,
                     gn_test_seed_counters(instance, 12u, 132u, 0u,
                                           UINT64_MAX - UINT64_C(172),
                                           UINT64_MAX));
    SDK_CHECK_STATUS("sdk.run.overflow-digest-before", GN_STATUS_OK,
                     gn_test_image_digest(instance, &before));
    gn_run_result result;
    memset(&result, 0xa5, sizeof(result));
    SDK_CHECK_STATUS("sdk.run.overflow-status", GN_STATUS_CPU_FAILURE,
                     gn_run(instance, 1u, &result));
    SDK_CHECK_STATUS("sdk.run.overflow-reason", GN_RUN_ERROR, result.reason);
    SDK_CHECK_U64("sdk.run.overflow-no-partial-elapsed", 0u,
                  result.elapsed_cycles);
    SDK_CHECK_U64("sdk.run.overflow-no-dispatch", 0u, result.instructions);
    SDK_CHECK_STATUS("sdk.run.overflow-digest-after", GN_STATUS_OK,
                     gn_test_image_digest(instance, &after));
    SDK_CHECK_U64("sdk.run.overflow-no-partial-mutation", before, after);
}

static void unsupported_instruction_exposes_only_bounded_fault_details(void) {
    SDK_CASE("sdk.run.unsupported-fault-details");
    guest_fixture_image fixture;
    gn_manifest manifest;
    make_manifest(&manifest, &fixture, GUEST_FIXTURE_SCENARIO_A);
    fixture.rom[0x100u] = UINT8_C(0x4a);
    fixture.rom[0x101u] = UINT8_C(0xfc);
    SDK_CHECK_STATUS("sdk.run.load-unsupported", GN_STATUS_OK,
                     gn_load(instance, &manifest));
    gn_run_result result;
    SDK_CHECK_STATUS("sdk.run.unsupported-status", GN_STATUS_OK,
                     gn_run(instance, 172u, &result));
    SDK_CHECK_STATUS("sdk.run.unsupported-reason", GN_RUN_FAULT, result.reason);
    SDK_CHECK_U64("sdk.run.unsupported-fault-pc", 0x100u, result.fault_pc);
    SDK_CHECK_U64("sdk.run.unsupported-opcode", 0x4afcu,
                  result.instruction_register);
    SDK_CHECK_U64("sdk.run.unsupported-elapsed-reset-only", 40u,
                  result.elapsed_cycles);
    SDK_CHECK_U64("sdk.run.unsupported-no-dispatch", 0u, result.instructions);
}

static void host_fault_is_sticky_until_reset_and_can_recover(void) {
    SDK_CASE("sdk.run.host-fault-reset-recovery");
    assert_run_result("sdk.run.host-fault-reset-debt", 40u, 40u, 0u, 0u,
                      0x100u, GN_RUN_BUDGET);
    SDK_CHECK_STATUS("sdk.run.arm-host-fault", GN_STATUS_OK,
                     gn_test_fail_next_bus_callback(instance));
    gn_run_result result;
    SDK_CHECK_STATUS("sdk.run.host-fault-status", GN_STATUS_CPU_FAILURE,
                     gn_run(instance, 4u, &result));
    SDK_CHECK_STATUS("sdk.run.host-fault-reason", GN_RUN_ERROR, result.reason);
    SDK_CHECK_STATUS("sdk.run.sticky-host-fault-status", GN_STATUS_CPU_FAILURE,
                     gn_run(instance, 4u, &result));
    SDK_CHECK_STATUS("sdk.run.sticky-host-fault-reason", GN_RUN_ERROR,
                     result.reason);
    SDK_CHECK_STATUS("sdk.run.reset-clears-host-fault", GN_STATUS_OK,
                     gn_reset(instance));
    SDK_CHECK_STATUS("sdk.run.host-fault-recovery", GN_STATUS_OK,
                     gn_run(instance, 172u, &result));
    SDK_CHECK_STATUS("sdk.run.host-fault-recovery-stopped", GN_RUN_STOPPED,
                     result.reason);
}

static void expected_result_integer_boundaries_match_original_encodings(void) {
    static const struct {
        uint8_t moveq;
        uint32_t expected;
        const char *name;
    } moveq_vectors[] = {
        {UINT8_C(0x7f), UINT32_C(0x00000082), "moveq-7f"},
        {UINT8_C(0x80), UINT32_C(0xffffff83), "moveq-80"},
        {UINT8_C(0xff), UINT32_C(0x00000002), "moveq-ff"}
    };
    SDK_CASE("sdk.run.integer-boundaries");
    for (size_t index = 0u;
         index < sizeof(moveq_vectors) / sizeof(moveq_vectors[0]); ++index) {
        guest_fixture_image fixture;
        gn_manifest manifest;
        make_manifest(&manifest, &fixture, GUEST_FIXTURE_SCENARIO_A);
        fixture.rom[0x101u] = moveq_vectors[index].moveq;
        SDK_CHECK_STATUS("sdk.run.integer-load-moveq", GN_STATUS_OK,
                         gn_load(instance, &manifest));
        gn_run_result run;
        SDK_CHECK_STATUS("sdk.run.integer-run-moveq", GN_STATUS_OK,
                         gn_run(instance, 172u, &run));
        gn_observations observations;
        SDK_CHECK_STATUS("sdk.run.integer-observe-moveq", GN_STATUS_OK,
                         gn_observe(instance, &observations));
        (void)printf("# VECTOR %s expected=%" PRIu32 " observed=%" PRIu32 "\n",
                     moveq_vectors[index].name,
                     moveq_vectors[index].expected,
                     observations.arithmetic_result);
        SDK_CHECK_U64("sdk.run.integer-moveq-result",
                      moveq_vectors[index].expected,
                      observations.arithmetic_result);
        SDK_CHECK_STATUS("sdk.run.integer-moveq-stop", GN_RUN_STOPPED,
                         run.reason);
    }

    guest_fixture_image fixture;
    gn_manifest manifest;
    make_manifest(&manifest, &fixture, GUEST_FIXTURE_SCENARIO_A);
    fixture.rom[0x100u] = UINT8_C(0x70);
    fixture.rom[0x101u] = UINT8_C(0xff);
    fixture.rom[0x102u] = UINT8_C(0x52);
    fixture.rom[0x103u] = UINT8_C(0x80);
    SDK_CHECK_STATUS("sdk.run.integer-load-addq-wrap", GN_STATUS_OK,
                     gn_load(instance, &manifest));
    gn_run_result wrap_run;
    SDK_CHECK_STATUS("sdk.run.integer-run-addq-wrap", GN_STATUS_OK,
                     gn_run(instance, 172u, &wrap_run));
    gn_observations wrap_observations;
    SDK_CHECK_STATUS("sdk.run.integer-observe-addq-wrap", GN_STATUS_OK,
                     gn_observe(instance, &wrap_observations));
    SDK_CHECK_U64("sdk.run.integer-addq-unsigned-wrap", 0u,
                  wrap_observations.arithmetic_result);
    SDK_CHECK_STATUS("sdk.run.integer-addq-wrap-stop", GN_RUN_STOPPED,
                     wrap_run.reason);
}

typedef struct {
    uint32_t address;
    uint16_t value;
    uint8_t direction;
} expected_bus_event;

static void assert_original_functional_bus_trace(gn_instance *target) {
    static const expected_bus_event expected[] = {
        {0x0000u, 0x0000u, GN_TEST_BUS_READ},
        {0x0002u, 0x2000u, GN_TEST_BUS_READ},
        {0x0004u, 0x0000u, GN_TEST_BUS_READ},
        {0x0006u, 0x0100u, GN_TEST_BUS_READ},
        {0x0100u, 0x7007u, GN_TEST_BUS_READ},
        {0x0102u, 0x5680u, GN_TEST_BUS_READ},
        {0x0104u, 0x23c0u, GN_TEST_BUS_READ},
        {0x0106u, 0x0000u, GN_TEST_BUS_READ},
        {0x0108u, 0x1000u, GN_TEST_BUS_READ},
        {0x1000u, 0x0000u, GN_TEST_BUS_WRITE},
        {0x1002u, 0x000au, GN_TEST_BUS_WRITE},
        {0x010au, 0x7200u, GN_TEST_BUS_READ},
        {0x010cu, 0x3239u, GN_TEST_BUS_READ},
        {0x010eu, 0x0000u, GN_TEST_BUS_READ},
        {0x0110u, 0x1008u, GN_TEST_BUS_READ},
        {0x1008u, 0x1234u, GN_TEST_BUS_READ},
        {0x0112u, 0x5681u, GN_TEST_BUS_READ},
        {0x0114u, 0x23c1u, GN_TEST_BUS_READ},
        {0x0116u, 0x0000u, GN_TEST_BUS_READ},
        {0x0118u, 0x1004u, GN_TEST_BUS_READ},
        {0x1004u, 0x0000u, GN_TEST_BUS_WRITE},
        {0x1006u, 0x1237u, GN_TEST_BUS_WRITE},
        {0x011au, 0x7400u, GN_TEST_BUS_READ},
        {0x011cu, 0x3439u, GN_TEST_BUS_READ},
        {0x011eu, 0x0000u, GN_TEST_BUS_READ},
        {0x0120u, 0x100au, GN_TEST_BUS_READ},
        {0x100au, 0x0000u, GN_TEST_BUS_READ},
        {0x0122u, 0x5282u, GN_TEST_BUS_READ},
        {0x0124u, 0x23c2u, GN_TEST_BUS_READ},
        {0x0126u, 0x0000u, GN_TEST_BUS_READ},
        {0x0128u, 0x1010u, GN_TEST_BUS_READ},
        {0x1010u, 0x0000u, GN_TEST_BUS_WRITE},
        {0x1012u, 0x0001u, GN_TEST_BUS_WRITE},
        {0x012au, 0x4e72u, GN_TEST_BUS_READ},
        {0x012cu, 0x2700u, GN_TEST_BUS_READ}
    };
    gn_test_bus_event events[GN_TEST_TRACE_CAPACITY];
    size_t count = 0u;
    size_t dropped = 0u;
    SDK_CHECK_STATUS("sdk.bus.trace-read", GN_STATUS_OK,
                     gn_test_trace_read(target, events,
                                       GN_TEST_TRACE_CAPACITY, &count, &dropped));
    SDK_CHECK_U64("sdk.bus.trace-count",
                  sizeof(expected) / sizeof(expected[0]), count);
    SDK_CHECK_U64("sdk.bus.trace-dropped", 0u, dropped);
    for (size_t index = 0u; index < sizeof(expected) / sizeof(expected[0]); ++index) {
        char assertion[64];
        (void)snprintf(assertion, sizeof(assertion),
                       "sdk.bus.event.%02zu.address", index);
        SDK_CHECK_U64(assertion, expected[index].address, events[index].address);
        (void)snprintf(assertion, sizeof(assertion),
                       "sdk.bus.event.%02zu.direction", index);
        SDK_CHECK_U64(assertion, expected[index].direction, events[index].direction);
        (void)snprintf(assertion, sizeof(assertion),
                       "sdk.bus.event.%02zu.width", index);
        SDK_CHECK_U64(assertion, 16u, events[index].width_bits);
        (void)snprintf(assertion, sizeof(assertion),
                       "sdk.bus.event.%02zu.value", index);
        SDK_CHECK_U64(assertion, expected[index].value, events[index].value);
    }
}

static void named_observations_and_bounded_functional_trace_match_fixture(void) {
    SDK_CASE("sdk.controls.original-functional-trace");
    gn_run_result run;
    SDK_CHECK_STATUS("sdk.controls.run", GN_STATUS_OK,
                     gn_run(instance, 172u, &run));
    SDK_CHECK_U64("sdk.run.elapsed-cycles", 172u, run.elapsed_cycles);
    SDK_CHECK_U64("sdk.run.instructions", 12u, run.instructions);
    SDK_CHECK_STATUS("sdk.run.reason-stopped", GN_RUN_STOPPED, run.reason);
    gn_observations observations;
    SDK_CHECK_STATUS("sdk.controls.observe", GN_STATUS_OK,
                     gn_observe(instance, &observations));
    SDK_CHECK_U64("sdk.observe.arithmetic", 10u,
                  observations.arithmetic_result);
    SDK_CHECK_U64("sdk.observe.initialized", 0x1237u,
                  observations.initialized_result);
    SDK_CHECK_U64("sdk.observe.bss", 1u, observations.bss_result);
    SDK_CHECK_U64("sdk.observe.arithmetic-byte-order", 10u,
                  observations.arithmetic_result);
    assert_original_functional_bus_trace(instance);
}

static void controlled_wrong_behavior_fails_its_exact_assertion(void) {
    SDK_CASE("sdk.controls.exact-negative-control");
    gn_run_result run;
    SDK_CHECK_STATUS("sdk.control.run-status", GN_STATUS_OK,
                     gn_run(instance, 172u, &run));
    gn_observations observations;
    SDK_CHECK_STATUS("sdk.control.observe-status", GN_STATUS_OK,
                     gn_observe(instance, &observations));

    if (strcmp(selected_suite, "control-arithmetic") == 0) {
        SDK_CHECK_U64("sdk.observe.arithmetic", 10u,
                      observations.arithmetic_result);
    } else if (strcmp(selected_suite, "control-initialized") == 0) {
        SDK_CHECK_U64("sdk.observe.initialized", 0x1237u,
                      observations.initialized_result);
    } else if (strcmp(selected_suite, "control-bss") == 0) {
        SDK_CHECK_U64("sdk.observe.bss", 1u, observations.bss_result);
    } else if (strcmp(selected_suite, "control-run-instructions") == 0) {
        SDK_CHECK_U64("sdk.run.instructions", 12u, run.instructions);
    } else if (strcmp(selected_suite, "control-run-elapsed") == 0) {
        SDK_CHECK_U64("sdk.run.elapsed-cycles", 172u, run.elapsed_cycles);
    } else if (strcmp(selected_suite, "control-run-stop") == 0) {
        SDK_CHECK_STATUS("sdk.run.reason-stopped", GN_RUN_STOPPED, run.reason);
    } else if (strcmp(selected_suite, "control-byte-order") == 0) {
        SDK_CHECK_U64("sdk.observe.arithmetic-byte-order", 10u,
                      observations.arithmetic_result);
    } else if (strcmp(selected_suite, "control-access-order") == 0) {
        gn_test_bus_event events[GN_TEST_TRACE_CAPACITY];
        size_t count = 0u;
        size_t dropped = 0u;
        SDK_CHECK_STATUS("sdk.control.trace-status", GN_STATUS_OK,
                         gn_test_trace_read(instance, events,
                                           GN_TEST_TRACE_CAPACITY,
                                           &count, &dropped));
        SDK_CHECK_U64("sdk.control.trace-count", 35u, count);
        SDK_CHECK_U64("sdk.control.trace-dropped", 0u, dropped);
        SDK_CHECK_U64("sdk.bus.event.00.address", 0u, events[0].address);
    } else {
        SDK_CHECK_TRUE("sdk.control.known-mutation", 0);
    }
}

enum { SDK_BOUNDARY_COUNT = 13, SDK_ISOLATION_PAIRS = 16 };

static const uint64_t sdk_boundary_requests[SDK_BOUNDARY_COUNT] = {
    40u, 4u, 8u, 20u, 4u, 16u, 8u, 20u, 4u, 16u, 8u, 20u, 4u
};

static const uint64_t sdk_boundary_cycles[SDK_BOUNDARY_COUNT] = {
    40u, 44u, 52u, 72u, 76u, 92u, 100u, 120u, 124u, 140u, 148u, 168u, 172u
};

static const uint32_t sdk_boundary_pcs[SDK_BOUNDARY_COUNT] = {
    0x100u, 0x102u, 0x104u, 0x10au, 0x10cu, 0x112u, 0x114u,
    0x11au, 0x11cu, 0x122u, 0x124u, 0x12au, 0x12eu
};

typedef struct {
    uint32_t arithmetic;
    uint32_t initialized;
    uint32_t bss;
    uint8_t ready;
    uint32_t boundary_pc;
    gn_run_reason reason;
    uint64_t elapsed_total;
    uint64_t instructions_total;
    uint64_t overshoot_total;
    uint64_t image_digest;
    uint64_t trace_digest;
    size_t trace_count;
    size_t trace_dropped;
    uint64_t call_requested;
    uint64_t call_elapsed;
    uint64_t call_overshoot;
    uint64_t call_instructions;
} sdk_boundary_snapshot;

typedef struct {
    sdk_boundary_snapshot owners[2][SDK_BOUNDARY_COUNT];
} sdk_isolation_baselines;

typedef struct {
#if defined(_WIN32)
    volatile LONG ready;
    volatile LONG release;
#else
    atomic_uint ready;
    atomic_int release;
#endif
} sdk_start_gate;

static void sdk_start_gate_init(sdk_start_gate *gate) {
#if defined(_WIN32)
    gate->ready = 0;
    gate->release = 0;
#else
    atomic_init(&gate->ready, 0u);
    atomic_init(&gate->release, 0);
#endif
}

static void sdk_start_gate_arrive(sdk_start_gate *gate) {
#if defined(_WIN32)
    /* Interlocked operations provide a full fence for the shared start gate. */
    (void)InterlockedIncrement(&gate->ready);
#else
    atomic_fetch_add_explicit(&gate->ready, 1u, memory_order_release);
#endif
}

static int sdk_start_gate_ready(sdk_start_gate *gate) {
#if defined(_WIN32)
    return InterlockedCompareExchange(&gate->ready, 0, 0) == 2;
#else
    return atomic_load_explicit(&gate->ready, memory_order_acquire) == 2u;
#endif
}

static int sdk_start_gate_released(sdk_start_gate *gate) {
#if defined(_WIN32)
    return InterlockedCompareExchange(&gate->release, 0, 0) != 0;
#else
    return atomic_load_explicit(&gate->release, memory_order_acquire) != 0;
#endif
}

static void sdk_start_gate_release(sdk_start_gate *gate) {
#if defined(_WIN32)
    (void)InterlockedExchange(&gate->release, 1);
#else
    atomic_store_explicit(&gate->release, 1, memory_order_release);
#endif
}

typedef struct {
    sdk_boundary_snapshot snapshots[SDK_BOUNDARY_COUNT];
    int sequence_ok;
    int candidate_failure_ok;
    int recovery_ok;
    int cleanup_ok;
} sdk_thread_result;

typedef struct {
    sdk_start_gate *gate;
    unsigned owner;
    sdk_thread_result *result;
} sdk_thread_argument;

static uint64_t sdk_trace_hash_byte(uint64_t digest, uint8_t byte) {
    return (digest ^ byte) * UINT64_C(1099511628211);
}

static uint64_t sdk_trace_hash_u16(uint64_t digest, uint16_t value) {
    digest = sdk_trace_hash_byte(digest, (uint8_t)(value >> 8));
    return sdk_trace_hash_byte(digest, (uint8_t)value);
}

static uint64_t sdk_trace_hash_u32(uint64_t digest, uint32_t value) {
    digest = sdk_trace_hash_byte(digest, (uint8_t)(value >> 24));
    digest = sdk_trace_hash_byte(digest, (uint8_t)(value >> 16));
    digest = sdk_trace_hash_byte(digest, (uint8_t)(value >> 8));
    return sdk_trace_hash_byte(digest, (uint8_t)value);
}

static uint64_t sdk_trace_digest(const gn_test_bus_event *events, size_t count) {
    uint64_t digest = UINT64_C(14695981039346656037);
    for (size_t index = 0u; index < count; ++index) {
        digest = sdk_trace_hash_u32(digest, events[index].address);
        digest = sdk_trace_hash_u16(digest, events[index].value);
        digest = sdk_trace_hash_byte(digest, events[index].width_bits);
        digest = sdk_trace_hash_byte(digest, events[index].direction);
    }
    return digest;
}

static int sdk_capture_boundary(const gn_instance *target,
                                const gn_run_result *run,
                                uint64_t elapsed_total,
                                uint64_t instructions_total,
                                uint64_t overshoot_total,
                                sdk_boundary_snapshot *snapshot) {
    gn_observations observations;
    gn_test_bus_event events[GN_TEST_TRACE_CAPACITY];
    size_t count = 0u;
    size_t dropped = 0u;
    memset(snapshot, 0, sizeof(*snapshot));
    if (gn_observe(target, &observations) != GN_STATUS_OK ||
        gn_test_image_digest(target, &snapshot->image_digest) != GN_STATUS_OK ||
        gn_test_trace_read(target, events, GN_TEST_TRACE_CAPACITY,
                           &count, &dropped) != GN_STATUS_OK) {
        return 0;
    }
    snapshot->arithmetic = observations.arithmetic_result;
    snapshot->initialized = observations.initialized_result;
    snapshot->bss = observations.bss_result;
    snapshot->ready = observations.ready;
    snapshot->boundary_pc = run->boundary_pc;
    snapshot->reason = run->reason;
    snapshot->elapsed_total = elapsed_total;
    snapshot->instructions_total = instructions_total;
    snapshot->overshoot_total = overshoot_total;
    snapshot->trace_count = count;
    snapshot->trace_dropped = dropped;
    snapshot->trace_digest = sdk_trace_digest(events, count);
    snapshot->call_requested = run->requested_cycles;
    snapshot->call_elapsed = run->elapsed_cycles;
    snapshot->call_overshoot = run->overshoot_cycles;
    snapshot->call_instructions = run->instructions;
    return 1;
}

static int sdk_boundary_equal(const sdk_boundary_snapshot *expected,
                              const sdk_boundary_snapshot *actual,
                              int compare_call) {
    if (expected->arithmetic != actual->arithmetic ||
        expected->initialized != actual->initialized ||
        expected->bss != actual->bss || expected->ready != actual->ready ||
        expected->boundary_pc != actual->boundary_pc ||
        expected->reason != actual->reason ||
        expected->elapsed_total != actual->elapsed_total ||
        expected->instructions_total != actual->instructions_total ||
        expected->overshoot_total != actual->overshoot_total ||
        expected->image_digest != actual->image_digest ||
        expected->trace_digest != actual->trace_digest ||
        expected->trace_count != actual->trace_count ||
        expected->trace_dropped != actual->trace_dropped) {
        return 0;
    }
    if (compare_call != 0 &&
        (expected->call_requested != actual->call_requested ||
         expected->call_elapsed != actual->call_elapsed ||
         expected->call_overshoot != actual->call_overshoot ||
         expected->call_instructions != actual->call_instructions)) {
        return 0;
    }
    return 1;
}

static int sdk_run_boundary(gn_instance *target, size_t boundary,
                            uint64_t *elapsed_total,
                            uint64_t *instructions_total,
                            uint64_t *overshoot_total,
                            sdk_boundary_snapshot *snapshot) {
    gn_run_result run;
    if (gn_run(target, sdk_boundary_requests[boundary], &run) != GN_STATUS_OK ||
        run.requested_cycles != sdk_boundary_requests[boundary] ||
        run.overshoot_cycles != 0u) {
        return 0;
    }
    *elapsed_total += run.elapsed_cycles;
    *instructions_total += run.instructions;
    *overshoot_total += run.overshoot_cycles;
    if (*elapsed_total != sdk_boundary_cycles[boundary] ||
        *instructions_total != (uint64_t)boundary ||
        run.boundary_pc != sdk_boundary_pcs[boundary] ||
        run.reason != (boundary + 1u == SDK_BOUNDARY_COUNT
                           ? GN_RUN_STOPPED : GN_RUN_BUDGET)) {
        return 0;
    }
    return sdk_capture_boundary(target, &run, *elapsed_total,
                                *instructions_total, *overshoot_total,
                                snapshot);
}

static int sdk_run_split_sequence(gn_instance *target,
                                  sdk_boundary_snapshot snapshots[SDK_BOUNDARY_COUNT]) {
    uint64_t elapsed_total = 0u;
    uint64_t instructions_total = 0u;
    uint64_t overshoot_total = 0u;
    for (size_t boundary = 0u; boundary < SDK_BOUNDARY_COUNT; ++boundary) {
        if (!sdk_run_boundary(target, boundary, &elapsed_total,
                              &instructions_total, &overshoot_total,
                              &snapshots[boundary])) {
            return 0;
        }
    }
    return 1;
}

static int sdk_load_owner(unsigned owner, gn_instance **out_instance) {
    *out_instance = NULL;
    if (gn_create(out_instance) != GN_STATUS_OK || *out_instance == NULL) {
        gn_destroy(*out_instance);
        *out_instance = NULL;
        return 0;
    }
    if (load_scenario(*out_instance, owner) != GN_STATUS_OK) {
        gn_destroy(*out_instance);
        *out_instance = NULL;
        return 0;
    }
    return 1;
}

static int sdk_build_isolated_baselines(sdk_isolation_baselines *baselines) {
    for (unsigned owner = 0u; owner < 2u; ++owner) {
        gn_instance *isolated = NULL;
        if (!sdk_load_owner(owner, &isolated)) return 0;
        const int passed = sdk_run_split_sequence(isolated,
                                                   baselines->owners[owner]);
        gn_destroy(isolated);
        if (passed == 0) return 0;
    }
    return 1;
}

static int sdk_repeated_and_single_calls_match(
    const sdk_isolation_baselines *baselines) {
    for (unsigned owner = 0u; owner < 2u; ++owner) {
        gn_instance *repeated = NULL;
        if (!sdk_load_owner(owner, &repeated)) return 0;
        sdk_boundary_snapshot actual[SDK_BOUNDARY_COUNT];
        if (!sdk_run_split_sequence(repeated, actual)) {
            gn_destroy(repeated);
            return 0;
        }
        for (size_t boundary = 0u; boundary < SDK_BOUNDARY_COUNT; ++boundary) {
            if (!sdk_boundary_equal(&baselines->owners[owner][boundary],
                                    &actual[boundary], 1)) {
                gn_destroy(repeated);
                return 0;
            }
        }
        if (gn_test_trace_clear(repeated) != GN_STATUS_OK ||
            gn_reset(repeated) != GN_STATUS_OK ||
            !sdk_run_split_sequence(repeated, actual)) {
            gn_destroy(repeated);
            return 0;
        }
        for (size_t boundary = 0u; boundary < SDK_BOUNDARY_COUNT; ++boundary) {
            if (!sdk_boundary_equal(&baselines->owners[owner][boundary],
                                    &actual[boundary], 1)) {
                gn_destroy(repeated);
                return 0;
            }
        }
        gn_destroy(repeated);

        gn_instance *single = NULL;
        if (!sdk_load_owner(owner, &single)) return 0;
        gn_run_result run;
        if (gn_run(single, 172u, &run) != GN_STATUS_OK ||
            run.requested_cycles != 172u || run.elapsed_cycles != 172u ||
            run.overshoot_cycles != 0u || run.instructions != 12u ||
            run.reason != GN_RUN_STOPPED || run.boundary_pc != 0x12eu) {
            gn_destroy(single);
            return 0;
        }
        sdk_boundary_snapshot final;
        const int captured = sdk_capture_boundary(single, &run, run.elapsed_cycles,
                                                   run.instructions,
                                                   run.overshoot_cycles, &final);
        const int matches = captured != 0 && sdk_boundary_equal(
            &baselines->owners[owner][SDK_BOUNDARY_COUNT - 1u], &final, 0);
        gn_destroy(single);
        if (matches == 0) return 0;
    }
    return 1;
}

static int sdk_interleaved_pairs_match(
    const sdk_isolation_baselines *baselines) {
    for (unsigned pair = 0u; pair < SDK_ISOLATION_PAIRS; ++pair) {
        gn_instance *owners[2] = {NULL, NULL};
        if (!sdk_load_owner(0u, &owners[0]) ||
            !sdk_load_owner(1u, &owners[1])) {
            gn_destroy(owners[0]);
            gn_destroy(owners[1]);
            return 0;
        }
        uint64_t elapsed[2] = {0u, 0u};
        uint64_t instructions[2] = {0u, 0u};
        uint64_t overshoot[2] = {0u, 0u};
        for (size_t boundary = 0u; boundary < SDK_BOUNDARY_COUNT; ++boundary) {
            for (unsigned turn = 0u; turn < 2u; ++turn) {
                const unsigned owner = (pair + (unsigned)boundary + turn) & 1u;
                sdk_boundary_snapshot actual;
                if (!sdk_run_boundary(owners[owner], boundary,
                                      &elapsed[owner], &instructions[owner],
                                      &overshoot[owner], &actual) ||
                    !sdk_boundary_equal(&baselines->owners[owner][boundary],
                                        &actual, 1)) {
                    gn_destroy(owners[0]);
                    gn_destroy(owners[1]);
                    return 0;
                }
            }
        }
        gn_destroy(owners[0]);
        gn_destroy(owners[1]);
    }
    return 1;
}

static SDK_TEST_THREAD_RESULT SDK_TEST_THREAD_CALL
sdk_concurrent_owner_thread(void *userdata) {
    sdk_thread_argument *argument = (sdk_thread_argument *)userdata;
    sdk_thread_result *result = argument->result;
    sdk_start_gate_arrive(argument->gate);
    while (!sdk_start_gate_released(argument->gate)) {
        sdk_test_thread_yield();
    }

    gn_test_allocator allocator;
    gn_test_allocator_init(&allocator);
    gn_instance *target = NULL;
    if (gn_test_create(&allocator, &target) != GN_STATUS_OK || target == NULL) {
        gn_destroy(target);
        result->sequence_ok = 0;
        result->cleanup_ok = allocator.live_allocations == 0u &&
                             allocator.live_bytes == 0u;
        return SDK_TEST_THREAD_DONE;
    }
    if (load_scenario(target, argument->owner) != GN_STATUS_OK) {
        gn_destroy(target);
        result->sequence_ok = 0;
        result->cleanup_ok = allocator.live_allocations == 0u &&
                             allocator.live_bytes == 0u;
        return SDK_TEST_THREAD_DONE;
    }

    uint64_t digest_before = 0u;
    uint64_t digest_after = 0u;
    const size_t allocations_before = allocator.live_allocations;
    const size_t bytes_before = allocator.live_bytes;
    const gn_status before_status =
        gn_test_image_digest(target, &digest_before);
    guest_fixture_image replacement_fixture;
    gn_manifest replacement_manifest;
    make_manifest(&replacement_manifest, &replacement_fixture,
                  argument->owner == 0u ? GUEST_FIXTURE_SCENARIO_B
                                        : GUEST_FIXTURE_SCENARIO_A);
    gn_test_allocator_arm(&allocator, 1u);
    const gn_status failed_replacement = gn_load(target, &replacement_manifest);
    gn_test_allocator_disarm(&allocator);
    result->candidate_failure_ok =
        failed_replacement == GN_STATUS_OUT_OF_MEMORY &&
        before_status == GN_STATUS_OK &&
        gn_test_image_digest(target, &digest_after) == GN_STATUS_OK &&
        digest_before == digest_after &&
        allocator.live_allocations == allocations_before &&
        allocator.live_bytes == bytes_before;

    result->sequence_ok =
        sdk_run_split_sequence(target, result->snapshots);
    if (gn_test_trace_clear(target) != GN_STATUS_OK ||
        gn_reset(target) != GN_STATUS_OK) {
        result->recovery_ok = 0;
    } else {
        gn_run_result reset_run;
        gn_run_result first_instruction;
        result->recovery_ok =
            gn_run(target, 40u, &reset_run) == GN_STATUS_OK &&
            reset_run.reason == GN_RUN_BUDGET &&
            reset_run.boundary_pc == 0x100u &&
            gn_run(target, 4u, &first_instruction) == GN_STATUS_OK &&
            first_instruction.reason == GN_RUN_BUDGET &&
            first_instruction.instructions == 1u &&
            first_instruction.boundary_pc == 0x102u;
    }
    result->cleanup_ok = gn_unload(target) == GN_STATUS_OK;
    gn_destroy(target);
    result->cleanup_ok = result->cleanup_ok != 0 &&
                         allocator.live_allocations == 0u &&
                         allocator.live_bytes == 0u;
    return SDK_TEST_THREAD_DONE;
}

static int sdk_run_barrier_concurrent_pair(sdk_thread_result results[2]) {
    sdk_start_gate gate;
    sdk_start_gate_init(&gate);
    sdk_thread_argument arguments[2];
    sdk_test_thread threads[2];
    unsigned started = 0u;
    memset(results, 0, 2u * sizeof(results[0]));
    for (unsigned owner = 0u; owner < 2u; ++owner) {
        arguments[owner] = (sdk_thread_argument){&gate, owner, &results[owner]};
        if (!sdk_test_thread_start(&threads[owner], sdk_concurrent_owner_thread,
                                    &arguments[owner])) {
            sdk_start_gate_release(&gate);
            for (unsigned index = 0u; index < started; ++index) {
                (void)sdk_test_thread_join(threads[index]);
            }
            return 0;
        }
        ++started;
    }
    while (!sdk_start_gate_ready(&gate)) {
        sdk_test_thread_yield();
    }
    sdk_start_gate_release(&gate);
    int joined = 1;
    for (unsigned owner = 0u; owner < 2u; ++owner) {
        if (!sdk_test_thread_join(threads[owner])) joined = 0;
    }
    return joined;
}

static int sdk_concurrent_pairs_match(
    const sdk_isolation_baselines *baselines) {
    for (unsigned pair = 0u; pair < SDK_ISOLATION_PAIRS; ++pair) {
        sdk_thread_result results[2];
        if (!sdk_run_barrier_concurrent_pair(results)) return 0;
        for (unsigned owner = 0u; owner < 2u; ++owner) {
            if (results[owner].sequence_ok == 0 ||
                results[owner].candidate_failure_ok == 0 ||
                results[owner].recovery_ok == 0 ||
                results[owner].cleanup_ok == 0) {
                return 0;
            }
            for (size_t boundary = 0u; boundary < SDK_BOUNDARY_COUNT; ++boundary) {
                if (!sdk_boundary_equal(&baselines->owners[owner][boundary],
                                        &results[owner].snapshots[boundary], 1)) {
                    return 0;
                }
            }
        }
    }
    return 1;
}

typedef struct {
    gn_mvs_frame_result_v1 result;
    gn_mvs_private_video_activity video;
    gn_mvs_bus_fault_observation bus;
    gn_test_mvs_sound_state sound;
    uint8_t guest_reply;
    uint64_t elapsed_total;
    uint64_t pixel_digest;
    size_t audio_frames;
    int16_t audio[GN_MVS_AUDIO_CAPACITY_FRAMES_V1 * 2u];
} sdk_mvs_snapshot;

typedef struct {
    sdk_sound_bundle owners[2];
    sdk_mvs_snapshot baselines[2][SDK_SOUND_FRAMES];
    uint64_t elapsed[2][SDK_SOUND_FRAMES];
} sdk_mvs_isolation_fixture;

static const uint32_t sdk_mvs_inputs[2][SDK_SOUND_FRAMES] = {
    {0u, GN_MVS_INPUT_P1_A, 0u, 0u, GN_MVS_INPUT_P1_A, 0u},
    {0u, 0u, GN_MVS_INPUT_P1_A, 0u, 0u, GN_MVS_INPUT_P1_A}
};

static uint64_t sdk_mvs_pixel_digest(const uint8_t *pixels, size_t bytes) {
    uint64_t digest = UINT64_C(14695981039346656037);
    for (size_t index = 0u; index < bytes; ++index)
        digest = (digest ^ pixels[index]) * UINT64_C(1099511628211);
    return digest;
}

static void sdk_mvs_fixture_destroy(sdk_mvs_isolation_fixture *fixture) {
    for (unsigned owner = 0u; owner < 2u; ++owner) {
        free(fixture->owners[owner].bytes);
        memset(&fixture->owners[owner], 0, sizeof(fixture->owners[owner]));
    }
}

static int sdk_mvs_fixture_prepare(sdk_mvs_isolation_fixture *fixture) {
    memset(fixture, 0, sizeof(*fixture));
    if (!sdk_sound_bundle_read(&fixture->owners[0])) {
        (void)fprintf(stderr, "SDK_MVS_ISOLATION source fixture read failed\n");
        return 0;
    }
    uint8_t *audio_bios = fixture->owners[0].bytes +
        fixture->owners[0].offsets[6];
    static const uint8_t startup[] = {
        0x31u, 0xffu, 0xffu, /* LD SP,$ffff */
        0x01u, 0x08u, 0x0au, /* LD BC,$0a08: select sound ROM bank 0. */
        0xedu, 0x78u         /* IN A,(C): bank transition on the sound bus. */
    };
    size_t cursor = sizeof(startup);
    memcpy(audio_bios, startup, sizeof(startup));
    static const uint8_t timer_setup[][8] = {
        {0x3eu, 0x24u, 0xd3u, 0x04u, 0x3eu, 0xffu, 0xd3u, 0x05u},
        {0x3eu, 0x25u, 0xd3u, 0x04u, 0x3eu, 0x03u, 0xd3u, 0x05u},
        {0x3eu, 0x27u, 0xd3u, 0x04u, 0x3eu, 0x05u, 0xd3u, 0x05u}
    };
    for (size_t index = 0u; index < sizeof(timer_setup) / sizeof(timer_setup[0]);
         ++index) {
        memcpy(audio_bios + cursor, timer_setup[index], sizeof(timer_setup[index]));
        cursor += sizeof(timer_setup[index]);
    }
    static const uint8_t finish[] = {
        0x3eu, 0x00u, 0xd3u, 0x08u, /* Enable command NMI. */
        0xedu, 0x56u,               /* IM 1 for YM timer IRQ. */
        0xfbu, 0x76u, 0x18u, 0xfdu /* EI; HALT; JR HALT. */
    };
    memcpy(audio_bios + cursor, finish, sizeof(finish));
    cursor += sizeof(finish);
    if (cursor >= 0x38u) goto fail;
    audio_bios[0x38u] = 0xc3u; audio_bios[0x39u] = 0x00u;
    audio_bios[0x3au] = 0x01u; /* Timer interrupt vector -> $0100. */
    static const uint8_t timer_isr[] = {
        0xf5u,                         /* PUSH AF */
        0x3eu, 0x27u, 0xd3u, 0x04u,   /* Select YM timer control. */
        0x3eu, 0x10u, 0xd3u, 0x05u,   /* Clear timer A's IRQ latch. */
        0xf1u, 0xfbu, 0xedu, 0x4du    /* POP AF; EI; RETI. */
    };
    memcpy(audio_bios + 0x100u, timer_isr, sizeof(timer_isr));
    fixture->owners[1].size = fixture->owners[0].size;
    fixture->owners[1].bytes = (uint8_t *)malloc(fixture->owners[1].size);
    if (fixture->owners[1].bytes == NULL) goto fail;
    memcpy(fixture->owners[1].bytes, fixture->owners[0].bytes,
           fixture->owners[1].size);
    memcpy(fixture->owners[1].offsets, fixture->owners[0].offsets,
           sizeof(fixture->owners[1].offsets));
    memcpy(fixture->owners[1].lengths, fixture->owners[0].lengths,
           sizeof(fixture->owners[1].lengths));
    if (!sdk_sound_make_variant(&fixture->owners[1])) {
        (void)fprintf(stderr, "SDK_MVS_ISOLATION fixture variant rejected\n");
        goto fail;
    }
    return 1;
fail:
    sdk_mvs_fixture_destroy(fixture);
    return 0;
}

static int sdk_mvs_instance_load(const sdk_sound_bundle *bundle,
                                 gn_instance **out_instance) {
    *out_instance = NULL;
    if (bundle == NULL || bundle->bytes == NULL ||
        gn_create(out_instance) != GN_STATUS_OK || *out_instance == NULL) {
        gn_destroy(*out_instance);
        *out_instance = NULL;
        return 0;
    }
    gn_mvs_manifest_v3 manifest;
    memset(&manifest, 0, sizeof(manifest));
    manifest.version = GN_MVS_MANIFEST_VERSION_ZOOM;
    manifest.profile = GN_MVS_PROFILE_MSX;
    manifest.region_count = SDK_SOUND_REGION_COUNT;
    for (size_t index = 0u; index < SDK_SOUND_REGION_COUNT; ++index) {
        manifest.regions[index] = (gn_mvs_region){
            (gn_mvs_region_role)(index + 1u),
            bundle->bytes + bundle->offsets[index], bundle->lengths[index],
            bundle->lengths[index], GN_MVS_LAYOUT_LINEAR};
    }
    if (gn_load_mvs_v3(*out_instance, &manifest) != GN_STATUS_OK) {
        gn_destroy(*out_instance);
        *out_instance = NULL;
        return 0;
    }
    return 1;
}

static int sdk_mvs_capture_frame(gn_instance *instance, unsigned owner,
                                 size_t boundary, uint64_t prior_elapsed,
                                 sdk_mvs_snapshot *snapshot) {
    const size_t pixel_bytes = (size_t)SDK_SOUND_WIDTH * SDK_SOUND_HEIGHT *
                               sizeof(uint32_t);
    const size_t audio_storage_frames = GN_MVS_AUDIO_CAPACITY_FRAMES_V1 + 1u;
    uint8_t *pixels = (uint8_t *)malloc(pixel_bytes);
    int16_t *audio = (int16_t *)malloc(audio_storage_frames * 2u * sizeof(int16_t));
    if (pixels == NULL || audio == NULL) {
        free(audio);
        free(pixels);
        return 0;
    }
    memset(audio, 0x5a, audio_storage_frames * 2u * sizeof(int16_t));
    const gn_mvs_frame_request_v1 request = {
        GN_MVS_FRAME_REQUEST_V1_VERSION, sdk_mvs_inputs[owner][boundary],
        GN_PIXEL_XRGB8888, SDK_SOUND_WIDTH, SDK_SOUND_HEIGHT,
        (size_t)SDK_SOUND_WIDTH * sizeof(uint32_t), pixels, pixel_bytes,
        audio, GN_MVS_AUDIO_CAPACITY_FRAMES_V1
    };
    memset(snapshot, 0, sizeof(*snapshot));
    const gn_status status = gn_mvs_advance_frame_v1(
        instance, &request, sizeof(request), &snapshot->result,
        sizeof(snapshot->result));
    int passed = status == GN_STATUS_OK &&
        snapshot->result.audio_frames_generated ==
            snapshot->result.audio_frames_delivered &&
        snapshot->result.audio_frames_delivered <=
            GN_MVS_AUDIO_CAPACITY_FRAMES_V1 &&
        snapshot->result.audio_frames_discarded == 0u &&
        snapshot->result.video_pixels_produced ==
            (size_t)SDK_SOUND_WIDTH * SDK_SOUND_HEIGHT;
    for (size_t index = snapshot->result.audio_frames_delivered * 2u;
         passed != 0 && index < audio_storage_frames * 2u; ++index) {
        const uint8_t byte = ((const uint8_t *)audio)[index * sizeof(int16_t)];
        const uint8_t byte2 = ((const uint8_t *)audio)[index * sizeof(int16_t) + 1u];
        if (byte != 0x5au || byte2 != 0x5au) passed = 0;
    }
    if (passed != 0 &&
        (gn_private_mvs_video_activity(instance, &snapshot->video) !=
             GN_STATUS_OK ||
         gn_observe_mvs_bus_fault(instance, &snapshot->bus,
                                   sizeof(snapshot->bus)) != GN_STATUS_OK ||
         gn_test_mvs_sound_state_read(instance, &snapshot->sound) !=
             GN_STATUS_OK ||
         gn_test_mvs_read_bus8(instance, UINT32_C(0x320000),
                               &snapshot->guest_reply) != GN_STATUS_OK))
        passed = 0;
    if (passed != 0) {
        snapshot->audio_frames = snapshot->result.audio_frames_delivered;
        memcpy(snapshot->audio, audio,
               snapshot->audio_frames * 2u * sizeof(int16_t));
        snapshot->elapsed_total = prior_elapsed + snapshot->result.elapsed_cycles;
        snapshot->pixel_digest = sdk_mvs_pixel_digest(pixels, pixel_bytes);
    }
    free(audio);
    free(pixels);
    return passed;
}

static int sdk_mvs_snapshot_equal(const sdk_mvs_snapshot *expected,
                                 const sdk_mvs_snapshot *actual) {
    return memcmp(&expected->result, &actual->result,
                  sizeof(expected->result)) == 0 &&
        memcmp(&expected->video, &actual->video, sizeof(expected->video)) == 0 &&
        memcmp(&expected->bus, &actual->bus, sizeof(expected->bus)) == 0 &&
        memcmp(&expected->sound, &actual->sound, sizeof(expected->sound)) == 0 &&
        expected->guest_reply == actual->guest_reply &&
        expected->elapsed_total == actual->elapsed_total &&
        expected->pixel_digest == actual->pixel_digest &&
        expected->audio_frames == actual->audio_frames &&
        memcmp(expected->audio, actual->audio,
               expected->audio_frames * 2u * sizeof(int16_t)) == 0;
}

static int sdk_mvs_capture_discard_matches(
    gn_instance *instance, unsigned owner, size_t boundary,
    uint64_t prior_elapsed, const sdk_mvs_snapshot *expected) {
    const size_t pixel_bytes = (size_t)SDK_SOUND_WIDTH * SDK_SOUND_HEIGHT *
                               sizeof(uint32_t);
    uint8_t *pixels = (uint8_t *)malloc(pixel_bytes);
    if (pixels == NULL) return 0;
    memset(pixels, 0xa5, pixel_bytes);
    const gn_mvs_frame_request_v1 request = {
        GN_MVS_FRAME_REQUEST_V1_VERSION, sdk_mvs_inputs[owner][boundary],
        GN_PIXEL_XRGB8888, SDK_SOUND_WIDTH, SDK_SOUND_HEIGHT,
        (size_t)SDK_SOUND_WIDTH * sizeof(uint32_t), pixels, pixel_bytes,
        NULL, 0u
    };
    sdk_mvs_snapshot actual;
    memset(&actual, 0, sizeof(actual));
    const gn_status status = gn_mvs_advance_frame_v1(
        instance, &request, sizeof(request), &actual.result,
        sizeof(actual.result));
    int passed = status == GN_STATUS_OK &&
        actual.result.audio_frames_generated != 0u &&
        actual.result.audio_frames_delivered == 0u &&
        actual.result.audio_frames_discarded ==
            actual.result.audio_frames_generated &&
        actual.result.video_pixels_produced ==
            (size_t)SDK_SOUND_WIDTH * SDK_SOUND_HEIGHT &&
        gn_private_mvs_video_activity(instance, &actual.video) == GN_STATUS_OK &&
        gn_observe_mvs_bus_fault(instance, &actual.bus, sizeof(actual.bus)) ==
            GN_STATUS_OK &&
        gn_test_mvs_sound_state_read(instance, &actual.sound) == GN_STATUS_OK &&
        gn_test_mvs_read_bus8(instance, UINT32_C(0x320000),
                              &actual.guest_reply) == GN_STATUS_OK;
    if (passed != 0) {
        actual.elapsed_total = prior_elapsed + actual.result.elapsed_cycles;
        actual.pixel_digest = sdk_mvs_pixel_digest(pixels, pixel_bytes);
        gn_mvs_frame_result_v1 normalized = actual.result;
        normalized.audio_frames_delivered =
            expected->result.audio_frames_delivered;
        normalized.audio_frames_discarded =
            expected->result.audio_frames_discarded;
        passed = memcmp(&normalized, &expected->result,
                        sizeof(normalized)) == 0 &&
            memcmp(&actual.video, &expected->video, sizeof(actual.video)) == 0 &&
            memcmp(&actual.bus, &expected->bus, sizeof(actual.bus)) == 0 &&
            memcmp(&actual.sound, &expected->sound, sizeof(actual.sound)) == 0 &&
            actual.guest_reply == expected->guest_reply &&
            actual.elapsed_total == expected->elapsed_total &&
            actual.pixel_digest == expected->pixel_digest;
    }
    free(pixels);
    return passed;
}

static int sdk_mvs_injected_sound_failure_is_bounded(gn_instance *instance,
                                                     unsigned owner,
                                                     size_t boundary) {
    const size_t pixel_bytes = (size_t)SDK_SOUND_WIDTH * SDK_SOUND_HEIGHT *
                               sizeof(uint32_t);
    const size_t storage_frames = GN_MVS_AUDIO_CAPACITY_FRAMES_V1 + 1u;
    uint8_t *pixels = (uint8_t *)malloc(pixel_bytes);
    int16_t *audio = (int16_t *)malloc(storage_frames * 2u * sizeof(int16_t));
    if (pixels == NULL || audio == NULL) {
        free(audio);
        free(pixels);
        return 0;
    }
    memset(pixels, 0xa5, pixel_bytes);
    memset(audio, 0x5a, storage_frames * 2u * sizeof(int16_t));
    int passed = gn_test_mvs_set_failure(
        instance, GN_TEST_MVS_FAILURE_SOUND_TICK_LIMIT) == GN_STATUS_OK;
    gn_mvs_frame_result_v1 result;
    memset(&result, 0, sizeof(result));
    const gn_mvs_frame_request_v1 request = {
        GN_MVS_FRAME_REQUEST_V1_VERSION, sdk_mvs_inputs[owner][boundary],
        GN_PIXEL_XRGB8888, SDK_SOUND_WIDTH, SDK_SOUND_HEIGHT,
        (size_t)SDK_SOUND_WIDTH * sizeof(uint32_t), pixels, pixel_bytes,
        audio, GN_MVS_AUDIO_CAPACITY_FRAMES_V1
    };
    if (passed != 0) {
        const gn_status status = gn_mvs_advance_frame_v1(
            instance, &request, sizeof(request), &result, sizeof(result));
        passed = status == GN_STATUS_CPU_FAILURE &&
            result.reason == GN_RUN_ERROR && result.elapsed_cycles != 0u &&
            result.elapsed_cycles < result.requested_cycles &&
            result.audio_frames_generated == result.audio_frames_delivered +
                result.audio_frames_discarded &&
            result.audio_frames_delivered <= GN_MVS_AUDIO_CAPACITY_FRAMES_V1 &&
            result.video_pixels_produced == 0u;
    }
    for (size_t index = 0u; passed != 0 && index < pixel_bytes; ++index)
        if (pixels[index] != 0xa5u) passed = 0;
    for (size_t index = result.audio_frames_delivered * 2u * sizeof(int16_t);
         passed != 0 && index < storage_frames * 2u * sizeof(int16_t); ++index)
        if (((const uint8_t *)audio)[index] != 0x5au) passed = 0;
    gn_test_mvs_sound_state failed_state;
    if (passed != 0 &&
        (gn_test_mvs_sound_state_read(instance, &failed_state) != GN_STATUS_OK ||
         failed_state.failed == 0u)) passed = 0;
    free(audio);
    free(pixels);
    return passed;
}

static int sdk_mvs_short_preflight_preserves_boundary(
    gn_instance *instance, unsigned owner, size_t boundary,
    const sdk_mvs_snapshot *expected) {
    const size_t pixel_bytes = (size_t)SDK_SOUND_WIDTH * SDK_SOUND_HEIGHT *
                               sizeof(uint32_t);
    const size_t storage_frames = GN_MVS_AUDIO_CAPACITY_FRAMES_V1 + 1u;
    uint8_t *pixels = (uint8_t *)malloc(pixel_bytes);
    int16_t *audio = (int16_t *)malloc(storage_frames * 2u * sizeof(int16_t));
    if (pixels == NULL || audio == NULL) {
        free(audio);
        free(pixels);
        return 0;
    }
    memset(pixels, 0xa5, pixel_bytes);
    memset(audio, 0x5a, storage_frames * 2u * sizeof(int16_t));
    gn_mvs_frame_result_v1 result;
    memset(&result, 0xc3, sizeof(result));
    const gn_mvs_frame_request_v1 request = {
        GN_MVS_FRAME_REQUEST_V1_VERSION, sdk_mvs_inputs[owner][boundary],
        GN_PIXEL_XRGB8888, SDK_SOUND_WIDTH, SDK_SOUND_HEIGHT,
        (size_t)SDK_SOUND_WIDTH * sizeof(uint32_t), pixels, pixel_bytes,
        audio, GN_MVS_AUDIO_CAPACITY_FRAMES_V1 - 1u
    };
    int passed = gn_mvs_advance_frame_v1(
        instance, &request, sizeof(request), &result, sizeof(result)) ==
            GN_STATUS_INVALID_ARGUMENT;
    const uint8_t *result_bytes = (const uint8_t *)&result;
    for (size_t index = 0u; passed != 0 && index < sizeof(result); ++index)
        if (result_bytes[index] != 0xc3u) passed = 0;
    for (size_t index = 0u; passed != 0 && index < pixel_bytes; ++index)
        if (pixels[index] != 0xa5u) passed = 0;
    for (size_t index = 0u; passed != 0 &&
         index < storage_frames * 2u * sizeof(int16_t); ++index)
        if (((const uint8_t *)audio)[index] != 0x5au) passed = 0;
    gn_test_mvs_sound_state state;
    if (passed != 0 &&
        (gn_test_mvs_sound_state_read(instance, &state) != GN_STATUS_OK ||
         memcmp(&state, &expected->sound, sizeof(state)) != 0)) passed = 0;
    free(audio);
    free(pixels);
    return passed;
}

static int sdk_mvs_manifest_make(const sdk_sound_bundle *bundle,
                                 gn_mvs_manifest_v3 *manifest) {
    if (bundle == NULL || bundle->bytes == NULL || manifest == NULL) return 0;
    memset(manifest, 0, sizeof(*manifest));
    manifest->version = GN_MVS_MANIFEST_VERSION_ZOOM;
    manifest->profile = GN_MVS_PROFILE_MSX;
    manifest->region_count = SDK_SOUND_REGION_COUNT;
    for (size_t index = 0u; index < SDK_SOUND_REGION_COUNT; ++index) {
        manifest->regions[index] = (gn_mvs_region){
            (gn_mvs_region_role)(index + 1u),
            bundle->bytes + bundle->offsets[index], bundle->lengths[index],
            bundle->lengths[index], GN_MVS_LAYOUT_LINEAR};
    }
    return 1;
}

static int sdk_mvs_lifecycle_peer_isolation(
    sdk_mvs_isolation_fixture *fixture) {
    gn_instance *subject = NULL;
    gn_instance *peer = NULL;
    if (!sdk_mvs_instance_load(&fixture->owners[0], &subject) ||
        !sdk_mvs_instance_load(&fixture->owners[1], &peer)) {
        gn_destroy(peer);
        gn_destroy(subject);
        return 0;
    }
    int passed = 1;
    sdk_mvs_snapshot actual;
    uint64_t subject_elapsed = 0u;
    if (!sdk_mvs_capture_frame(subject, 0u, 0u, subject_elapsed, &actual) ||
        !sdk_mvs_snapshot_equal(&fixture->baselines[0][0], &actual))
        passed = 0;
    else subject_elapsed = actual.elapsed_total;

    for (size_t boundary = 0u; boundary < SDK_SOUND_FRAMES && passed != 0;
         ++boundary) {
        if (boundary == 1u) {
            if (!sdk_mvs_short_preflight_preserves_boundary(subject, 0u, 1u,
                    &fixture->baselines[0][0]) ||
                !sdk_mvs_capture_frame(subject, 0u, 1u, subject_elapsed,
                                       &actual) ||
                !sdk_mvs_snapshot_equal(&fixture->baselines[0][1], &actual) ||
                !sdk_mvs_injected_sound_failure_is_bounded(subject, 0u, 2u) ||
                gn_reset(subject) != GN_STATUS_OK ||
                !sdk_mvs_capture_frame(subject, 0u, 0u, 0u, &actual) ||
                !sdk_mvs_snapshot_equal(&fixture->baselines[0][0], &actual)) {
                passed = 0;
            } else {
                subject_elapsed = actual.elapsed_total;
            }
        } else if (boundary == 2u) {
            if (!sdk_mvs_capture_discard_matches(subject, 0u, 1u,
                    subject_elapsed, &fixture->baselines[0][1])) {
                passed = 0;
            } else {
                subject_elapsed = fixture->baselines[0][1].elapsed_total;
            }
        } else if (boundary == 3u) {
            gn_mvs_manifest_v3 rejected;
            if (!sdk_mvs_manifest_make(&fixture->owners[0], &rejected)) {
                passed = 0;
            } else {
                rejected.region_count--;
                if (gn_load_mvs_v3(subject, &rejected) != GN_STATUS_INVALID_MEDIA ||
                    !sdk_mvs_capture_frame(subject, 0u, 2u, subject_elapsed,
                                           &actual) ||
                    !sdk_mvs_snapshot_equal(&fixture->baselines[0][2], &actual)) {
                    passed = 0;
                } else {
                    subject_elapsed = actual.elapsed_total;
                }
            }
        } else if (boundary == 4u) {
            gn_mvs_manifest_v3 reload;
            if (gn_unload(subject) != GN_STATUS_OK ||
                !sdk_mvs_manifest_make(&fixture->owners[0], &reload) ||
                gn_load_mvs_v3(subject, &reload) != GN_STATUS_OK ||
                !sdk_mvs_capture_frame(subject, 0u, 0u, 0u, &actual) ||
                !sdk_mvs_snapshot_equal(&fixture->baselines[0][0], &actual)) {
                passed = 0;
            } else {
                subject_elapsed = actual.elapsed_total;
            }
        } else if (boundary == 5u) {
            gn_destroy(subject);
            subject = NULL;
        }
        sdk_mvs_snapshot peer_actual;
        uint64_t peer_elapsed = boundary == 0u ? 0u :
            fixture->baselines[1][boundary - 1u].elapsed_total;
        if (passed != 0 &&
            (!sdk_mvs_capture_frame(peer, 1u, boundary, peer_elapsed,
                                    &peer_actual) ||
             !sdk_mvs_snapshot_equal(&fixture->baselines[1][boundary],
                                     &peer_actual)))
            passed = 0;
    }
    gn_destroy(peer);
    gn_destroy(subject);
    if (passed == 0)
        (void)fprintf(stderr,
            "SDK_MVS_LIFECYCLE peer continuation or owner recovery mismatch\n");
    else
        (void)printf("SDK_MVS_LIFECYCLE peer_frames=%u reset=1 discard=1 "
                     "failure=1 rejected_load=1 reload=1 destroy=1 status=pass\n",
                     SDK_SOUND_FRAMES);
    return passed;
}

static int sdk_mvs_run_sequence(const sdk_sound_bundle *bundle, unsigned owner,
                                sdk_mvs_snapshot *snapshots,
                                uint64_t *elapsed_out) {
    gn_instance *target = NULL;
    if (!sdk_mvs_instance_load(bundle, &target)) return 0;
    uint64_t elapsed = 0u;
    int passed = 1;
    for (size_t boundary = 0u; boundary < SDK_SOUND_FRAMES; ++boundary) {
        if (!sdk_mvs_capture_frame(target, owner, boundary, elapsed,
                                   &snapshots[boundary])) {
            passed = 0;
            break;
        }
        elapsed = snapshots[boundary].elapsed_total;
    }
    gn_destroy(target);
    if (passed != 0) *elapsed_out = elapsed;
    return passed;
}

static int sdk_mvs_repeated_and_interleaved(sdk_mvs_isolation_fixture *fixture) {
    for (unsigned owner = 0u; owner < 2u; ++owner) {
        sdk_mvs_snapshot repeated[SDK_SOUND_FRAMES];
        uint64_t elapsed = 0u;
        if (!sdk_mvs_run_sequence(&fixture->owners[owner], owner,
                                  repeated, &elapsed)) return 0;
        for (size_t boundary = 0u; boundary < SDK_SOUND_FRAMES; ++boundary) {
            if (!sdk_mvs_snapshot_equal(&fixture->baselines[owner][boundary],
                                        &repeated[boundary])) return 0;
        }
    }
    gn_instance *instances[2] = {NULL, NULL};
    for (unsigned owner = 0u; owner < 2u; ++owner) {
        if (!sdk_mvs_instance_load(&fixture->owners[owner], &instances[owner])) {
            gn_destroy(instances[0]);
            gn_destroy(instances[1]);
            return 0;
        }
    }
    uint64_t elapsed[2] = {0u, 0u};
    int passed = 1;
    for (size_t boundary = 0u; boundary < SDK_SOUND_FRAMES && passed != 0;
         ++boundary) {
        for (unsigned turn = 0u; turn < 2u; ++turn) {
            const unsigned owner = (unsigned)((boundary + turn) & 1u);
            sdk_mvs_snapshot actual;
            if (!sdk_mvs_capture_frame(instances[owner], owner, boundary,
                                       elapsed[owner], &actual) ||
                !sdk_mvs_snapshot_equal(&fixture->baselines[owner][boundary],
                                        &actual)) {
                passed = 0;
                break;
            }
            elapsed[owner] = actual.elapsed_total;
        }
    }
    gn_destroy(instances[1]);
    gn_destroy(instances[0]);
    return passed;
}

#if defined(_WIN32)
typedef struct { volatile LONG active, overlap, progress; } sdk_mvs_markers;
static LONG sdk_mvs_marker_read(volatile LONG *value) {
    return InterlockedCompareExchange(value, 0, 0);
}
static void sdk_mvs_marker_or(volatile LONG *value, LONG bits) {
    (void)InterlockedOr(value, bits);
}
static void sdk_mvs_marker_and(volatile LONG *value, LONG bits) {
    (void)InterlockedAnd(value, bits);
}
#else
typedef struct { atomic_uint active, overlap, progress; } sdk_mvs_markers;
static unsigned sdk_mvs_marker_read(atomic_uint *value) {
    return atomic_load_explicit(value, memory_order_acquire);
}
static void sdk_mvs_marker_or(atomic_uint *value, unsigned bits) {
    atomic_fetch_or_explicit(value, bits, memory_order_acq_rel);
}
static void sdk_mvs_marker_and(atomic_uint *value, unsigned bits) {
    atomic_fetch_and_explicit(value, bits, memory_order_acq_rel);
}
#endif

typedef struct {
    sdk_start_gate *gate;
    sdk_mvs_markers *markers;
    sdk_mvs_isolation_fixture *fixture;
    unsigned owner;
    int sequence_ok;
    sdk_mvs_snapshot snapshots[SDK_SOUND_FRAMES];
} sdk_mvs_thread_argument;

static SDK_TEST_THREAD_RESULT SDK_TEST_THREAD_CALL
sdk_mvs_owner_thread(void *userdata) {
    sdk_mvs_thread_argument *argument = (sdk_mvs_thread_argument *)userdata;
    const unsigned owner = argument->owner;
    gn_instance *target = NULL;
    const size_t pixel_bytes = (size_t)SDK_SOUND_WIDTH * SDK_SOUND_HEIGHT *
                               sizeof(uint32_t);
    const size_t audio_storage_frames = GN_MVS_AUDIO_CAPACITY_FRAMES_V1 + 1u;
    uint8_t *pixels = (uint8_t *)malloc(pixel_bytes);
    int16_t *audio = (int16_t *)malloc(audio_storage_frames * 2u * sizeof(int16_t));
    if (pixels == NULL || audio == NULL ||
        !sdk_mvs_instance_load(&argument->fixture->owners[owner], &target)) {
        free(audio);
        free(pixels);
        gn_destroy(target);
        argument->sequence_ok = 0;
        return SDK_TEST_THREAD_DONE;
    }
    sdk_start_gate_arrive(argument->gate);
    while (!sdk_start_gate_released(argument->gate)) sdk_test_thread_yield();

    uint64_t elapsed = 0u;
    argument->sequence_ok = 1;
    for (size_t boundary = 0u; boundary < SDK_SOUND_FRAMES; ++boundary) {
        memset(audio, 0x5a, audio_storage_frames * 2u * sizeof(int16_t));
        const gn_mvs_frame_request_v1 request = {
            GN_MVS_FRAME_REQUEST_V1_VERSION, sdk_mvs_inputs[owner][boundary],
            GN_PIXEL_XRGB8888, SDK_SOUND_WIDTH, SDK_SOUND_HEIGHT,
            (size_t)SDK_SOUND_WIDTH * sizeof(uint32_t), pixels, pixel_bytes,
            audio, GN_MVS_AUDIO_CAPACITY_FRAMES_V1
        };
        const unsigned bit = 1u << owner;
        const unsigned other = 1u << (owner ^ 1u);
        sdk_mvs_marker_or(&argument->markers->active, bit);
        if ((sdk_mvs_marker_read(&argument->markers->active) & other) != 0u)
            sdk_mvs_marker_or(&argument->markers->overlap, bit);
        sdk_mvs_snapshot *snapshot = &argument->snapshots[boundary];
        memset(snapshot, 0, sizeof(*snapshot));
        const gn_status status = gn_mvs_advance_frame_v1(
            target, &request, sizeof(request), &snapshot->result,
            sizeof(snapshot->result));
        if (status != GN_STATUS_OK ||
            snapshot->result.audio_frames_delivered !=
                snapshot->result.audio_frames_generated ||
            snapshot->result.audio_frames_delivered >
                GN_MVS_AUDIO_CAPACITY_FRAMES_V1 ||
            snapshot->result.video_pixels_produced !=
                (size_t)SDK_SOUND_WIDTH * SDK_SOUND_HEIGHT ||
            gn_private_mvs_video_activity(target, &snapshot->video) !=
                GN_STATUS_OK ||
            gn_observe_mvs_bus_fault(target, &snapshot->bus,
                                      sizeof(snapshot->bus)) != GN_STATUS_OK ||
            gn_test_mvs_sound_state_read(target, &snapshot->sound) !=
                GN_STATUS_OK ||
            gn_test_mvs_read_bus8(target, UINT32_C(0x320000),
                                  &snapshot->guest_reply) != GN_STATUS_OK) {
            argument->sequence_ok = 0;
#if defined(_WIN32)
            sdk_mvs_marker_and(&argument->markers->active, ~(LONG)bit);
#else
            sdk_mvs_marker_and(&argument->markers->active, ~bit);
#endif
            break;
        }
        snapshot->audio_frames = snapshot->result.audio_frames_delivered;
        memcpy(snapshot->audio, audio,
               snapshot->audio_frames * 2u * sizeof(int16_t));
        snapshot->elapsed_total = elapsed + snapshot->result.elapsed_cycles;
        snapshot->pixel_digest = sdk_mvs_pixel_digest(pixels, pixel_bytes);
        elapsed = snapshot->elapsed_total;
        if ((sdk_mvs_marker_read(&argument->markers->active) & other) != 0u) {
            sdk_mvs_marker_or(&argument->markers->overlap, bit);
            sdk_mvs_marker_or(&argument->markers->progress, bit);
        }
#if defined(_WIN32)
        sdk_mvs_marker_and(&argument->markers->active, ~(LONG)bit);
#else
        sdk_mvs_marker_and(&argument->markers->active, ~bit);
#endif
        sdk_test_thread_yield();
    }
    gn_destroy(target);
    free(audio);
    free(pixels);
    return SDK_TEST_THREAD_DONE;
}

static int sdk_mvs_concurrent(sdk_mvs_isolation_fixture *fixture,
                              unsigned *out_overlap, unsigned *out_progress) {
    sdk_start_gate gate;
    sdk_start_gate_init(&gate);
    sdk_mvs_markers markers;
#if defined(_WIN32)
    markers.active = 0; markers.overlap = 0; markers.progress = 0;
#else
    atomic_init(&markers.active, 0u);
    atomic_init(&markers.overlap, 0u);
    atomic_init(&markers.progress, 0u);
#endif
    sdk_mvs_thread_argument arguments[2];
    sdk_test_thread threads[2];
    unsigned started = 0u;
    memset(arguments, 0, sizeof(arguments));
    for (unsigned owner = 0u; owner < 2u; ++owner) {
        arguments[owner].gate = &gate;
        arguments[owner].markers = &markers;
        arguments[owner].fixture = fixture;
        arguments[owner].owner = owner;
        if (!sdk_test_thread_start(&threads[owner], sdk_mvs_owner_thread,
                                   &arguments[owner])) {
            sdk_start_gate_release(&gate);
            for (unsigned index = 0u; index < started; ++index)
                (void)sdk_test_thread_join(threads[index]);
            return 0;
        }
        ++started;
    }
    while (!sdk_start_gate_ready(&gate)) sdk_test_thread_yield();
    sdk_start_gate_release(&gate);
    int joined = 1;
    for (unsigned owner = 0u; owner < 2u; ++owner)
        if (!sdk_test_thread_join(threads[owner])) joined = 0;
    *out_overlap = (unsigned)sdk_mvs_marker_read(&markers.overlap);
    *out_progress = (unsigned)sdk_mvs_marker_read(&markers.progress);
    if (joined == 0 || *out_overlap != 3u || *out_progress != 3u) return 0;
    for (unsigned owner = 0u; owner < 2u; ++owner) {
        if (arguments[owner].sequence_ok == 0) return 0;
        for (size_t boundary = 0u; boundary < SDK_SOUND_FRAMES; ++boundary) {
            if (!sdk_mvs_snapshot_equal(
                    &fixture->baselines[owner][boundary],
                    &arguments[owner].snapshots[boundary])) return 0;
        }
    }
    return 1;
}

static int sdk_mvs_full_machine_isolation(void) {
    sdk_mvs_isolation_fixture fixture;
    if (!sdk_mvs_fixture_prepare(&fixture)) {
        (void)fprintf(stderr, "SDK_MVS_ISOLATION fixture preparation failed\n");
        return 0;
    }
    int passed = 1;
    unsigned main_remainder_mask = 0u;
    unsigned ym_remainder_mask = 0u;
    unsigned pcm_phase_mask = 0u;
    for (unsigned owner = 0u; owner < 2u && passed != 0; ++owner) {
        uint64_t elapsed = 0u;
        passed = sdk_mvs_run_sequence(&fixture.owners[owner], owner,
            fixture.baselines[owner], &elapsed);
        fixture.elapsed[owner][SDK_SOUND_FRAMES - 1u] = elapsed;
        if (passed != 0) {
            for (size_t boundary = 0u; boundary < SDK_SOUND_FRAMES; ++boundary) {
                const gn_test_mvs_sound_state *state =
                    &fixture.baselines[owner][boundary].sound;
                main_remainder_mask |= 1u << state->main_clock_remainder;
                ym_remainder_mask |= 1u << state->ym_clock_remainder;
                pcm_phase_mask |= 1u << (state->pcm_output_phase != 0u);
            }
            const gn_test_mvs_sound_state *final =
                &fixture.baselines[owner][SDK_SOUND_FRAMES - 1u].sound;
            if (final->main_cycles_advanced == 0u || final->native_samples == 0u ||
                final->bank_changes == 0u ||
                final->timer_register_writes[0] == 0u ||
                final->timer_register_writes[1] == 0u ||
                final->timer_register_writes[2] == 0u ||
                final->irq_assertions == 0u || final->irq_deassertions == 0u ||
                final->failed != 0u) {
                (void)fprintf(stderr,
                    "SDK_MVS_ISOLATION sound events owner=%u bank=%llu timer=%llu/%llu/%llu irq=%llu/%llu samples=%llu failed=%u\n",
                    owner, (unsigned long long)final->bank_changes,
                    (unsigned long long)final->timer_register_writes[0],
                    (unsigned long long)final->timer_register_writes[1],
                    (unsigned long long)final->timer_register_writes[2],
                    (unsigned long long)final->irq_assertions,
                    (unsigned long long)final->irq_deassertions,
                    (unsigned long long)final->native_samples, final->failed);
                passed = 0;
            }
        }
        if (passed != 0) {
            (void)printf("SDK_MVS_COMMAND owner=%u replies=%02x,%02x,%02x,%02x,%02x,%02x\n",
                owner,
                fixture.baselines[owner][0].guest_reply,
                fixture.baselines[owner][1].guest_reply,
                fixture.baselines[owner][2].guest_reply,
                fixture.baselines[owner][3].guest_reply,
                fixture.baselines[owner][4].guest_reply,
                fixture.baselines[owner][5].guest_reply);
        }
    }
    if (passed != 0 && ((main_remainder_mask & ~1u) == 0u ||
                        (ym_remainder_mask & ~1u) == 0u ||
                        (pcm_phase_mask & 2u) == 0u)) {
        (void)fprintf(stderr,
            "SDK_MVS_ISOLATION remainder coverage main=%x ym=%x pcm=%x\n",
            main_remainder_mask, ym_remainder_mask, pcm_phase_mask);
        passed = 0;
    }
    if (passed != 0) {
        int distinct = 0;
        int swapped_sequence_equal = 1;
        for (size_t boundary = 0u; boundary < SDK_SOUND_FRAMES; ++boundary) {
            if (!sdk_mvs_snapshot_equal(&fixture.baselines[0][boundary],
                                        &fixture.baselines[1][boundary]))
                distinct = 1;
            if (!sdk_mvs_snapshot_equal(&fixture.baselines[0][boundary],
                                        &fixture.baselines[1][boundary]))
                swapped_sequence_equal = 0;
        }
        const int guest_input_landmarks =
            fixture.baselines[0][0].guest_reply == 0x3cu &&
            fixture.baselines[0][1].guest_reply == 0xa5u &&
            fixture.baselines[1][0].guest_reply == 0x3du &&
            fixture.baselines[1][1].guest_reply == 0x3du &&
            fixture.baselines[1][2].guest_reply == 0xa5u;
        const int swapped_control_rejected = swapped_sequence_equal == 0;
        passed = distinct && swapped_control_rejected && guest_input_landmarks &&
                 sdk_mvs_repeated_and_interleaved(&fixture);
        if (!distinct)
            (void)fprintf(stderr, "SDK_MVS_ISOLATION owner streams were identical\n");
        if (!swapped_control_rejected)
            (void)fprintf(stderr, "SDK_MVS_ISOLATION swapped baseline control matched\n");
        if (!guest_input_landmarks)
            (void)fprintf(stderr, "SDK_MVS_ISOLATION guest input landmarks mismatched\n");
    }
    unsigned overlap = 0u, progress = 0u;
    if (passed != 0) passed = sdk_mvs_concurrent(&fixture, &overlap, &progress);
    if (passed != 0) passed = sdk_mvs_lifecycle_peer_isolation(&fixture);
    (void)printf("SDK_MVS_ISOLATION frames=%u owners=2 overlap_mask=%u "
                 "progress_mask=%u status=%s\n", SDK_SOUND_FRAMES, overlap,
                 progress, passed != 0 ? "pass" : "fail");
    sdk_mvs_fixture_destroy(&fixture);
    return passed;
}

static void mvs_native_state_api_accepts_the_public_machine_profile(void) {
    SDK_CASE("sdk.state-machine.mvs-public-profile");
    sdk_mvs_isolation_fixture fixture;
    memset(&fixture, 0, sizeof(fixture));
    SDK_CHECK_TRUE("sdk.state-machine.public-fixture-prepared",
                   sdk_mvs_fixture_prepare(&fixture));
    gn_instance *subject = NULL;
    SDK_CHECK_TRUE("sdk.state-machine.public-fixture-loaded",
                   sdk_mvs_instance_load(&fixture.owners[0], &subject));

    size_t capacity = 0u;
    SDK_CHECK_STATUS("sdk.state-machine.mvs-capacity", GN_STATUS_OK,
                     gn_state_capacity_v1(subject, &capacity));
    SDK_CHECK_TRUE("sdk.state-machine.mvs-capacity-includes-device-state",
                   capacity > GN_STATE_MAX_SIZE_V1);
    gn_destroy(subject);
    sdk_mvs_fixture_destroy(&fixture);
}

static int sdk_mvs_state_snapshot_equal(const sdk_mvs_snapshot *expected,
                                        const sdk_mvs_snapshot *actual) {
    sdk_mvs_snapshot expected_copy = *expected;
    sdk_mvs_snapshot actual_copy = *actual;
    gn_test_mvs_sound_state *left = &expected_copy.sound;
    gn_test_mvs_sound_state *right = &actual_copy.sound;
    left->main_cycles_advanced = right->main_cycles_advanced = 0u;
    left->ym_input_clocks = right->ym_input_clocks = 0u;
    left->native_samples = right->native_samples = 0u;
    left->irq_assertions = right->irq_assertions = 0u;
    left->irq_deassertions = right->irq_deassertions = 0u;
    left->bank_changes = right->bank_changes = 0u;
    memset(left->timer_register_writes, 0, sizeof(left->timer_register_writes));
    memset(right->timer_register_writes, 0, sizeof(right->timer_register_writes));
    left->ym_clock_remainder = right->ym_clock_remainder = 0u;
    return sdk_mvs_snapshot_equal(&expected_copy, &actual_copy);
}

static int sdk_mvs_state_section_payload_offset(const uint8_t *state,
                                                 size_t capacity,
                                                 uint32_t section_id,
                                                 size_t *out_offset);

static void mvs_native_state_restores_full_continuation_atomically(void) {
    SDK_CASE("sdk.state-machine.mvs-continuation");
    sdk_mvs_isolation_fixture fixture;
    memset(&fixture, 0, sizeof(fixture));
    SDK_CHECK_TRUE("sdk.state-machine.fixture-prepared",
                   sdk_mvs_fixture_prepare(&fixture));
    if (fixture.owners[0].bytes == NULL) return;
    uint8_t *main_bios = fixture.owners[0].bytes +
        fixture.owners[0].offsets[GN_MVS_REGION_BIOS - 1u];
    static const uint8_t input_poll[] = {
        0x10u, 0x39u, 0x00u, 0x30u, 0x00u, 0x00u,
        0x0cu, 0x00u, 0x00u, 0xefu
    };
    static const uint8_t stop_after_sound[] = {
        0x4eu, 0x72u, 0x27u, 0x00u, 0x4eu, 0x71u,
        0x4eu, 0x71u, 0x4eu, 0x71u
    };
    size_t stop_patches = 0u;
    SDK_CHECK_TRUE("sdk.state-machine.stopped-guest-fixture",
        sdk_sound_patch_sequence(main_bios,
            fixture.owners[0].lengths[GN_MVS_REGION_BIOS - 1u], input_poll,
            sizeof(input_poll), stop_after_sound, sizeof(stop_after_sound),
            &stop_patches));
    SDK_CHECK_U64("sdk.state-machine.single-stop-patch", 1u, stop_patches);
    gn_instance *subject = NULL;
    gn_test_allocator allocator;
    gn_test_allocator_init(&allocator);
    gn_mvs_manifest_v3 manifest;
    const int manifest_ready = sdk_mvs_manifest_make(&fixture.owners[0],
                                                      &manifest);
    SDK_CHECK_TRUE("sdk.state-machine.fixture-manifest", manifest_ready);
    if (manifest_ready == 0) {
        sdk_mvs_fixture_destroy(&fixture);
        return;
    }
    const gn_status owner_status = gn_test_create(&allocator, &subject);
    SDK_CHECK_STATUS("sdk.state-machine.fixture-owner-created", GN_STATUS_OK,
                     owner_status);
    if (subject == NULL) {
        sdk_mvs_fixture_destroy(&fixture);
        return;
    }
    const gn_status load_status = gn_load_mvs_v3(subject, &manifest);
    SDK_CHECK_STATUS("sdk.state-machine.fixture-loaded", GN_STATUS_OK,
                     load_status);
    if (load_status != GN_STATUS_OK) {
        gn_destroy(subject);
        sdk_mvs_fixture_destroy(&fixture);
        return;
    }
    if (subject == NULL) {
        sdk_mvs_fixture_destroy(&fixture);
        return;
    }
    size_t capacity = 0u;
    gn_state_detail_v1 detail;
    size_t written = 0u;
    SDK_CHECK_STATUS("sdk.state-machine.capacity", GN_STATUS_OK,
                     gn_state_capacity_v1(subject, &capacity));
    uint8_t *baseline = (uint8_t *)malloc(capacity);
    uint8_t *current = (uint8_t *)malloc(capacity);
    uint8_t *rejected = (uint8_t *)malloc(capacity);
    const size_t surface_bytes = (size_t)SDK_SOUND_WIDTH * SDK_SOUND_HEIGHT *
                                 sizeof(uint32_t);
    uint8_t *expected_surface = (uint8_t *)malloc(surface_bytes);
    uint8_t *replayed_surface = (uint8_t *)malloc(surface_bytes);
    SDK_CHECK_TRUE("sdk.state-machine.transfer-buffers-allocated",
                   baseline != NULL && current != NULL && rejected != NULL &&
                   expected_surface != NULL && replayed_surface != NULL);
    if (baseline == NULL || current == NULL || rejected == NULL ||
        expected_surface == NULL || replayed_surface == NULL) goto cleanup;

    gn_run_result raw;
    SDK_CHECK_STATUS("sdk.state-machine.raw-run-status", GN_STATUS_OK,
                     gn_run(subject, 20000u, &raw));
    SDK_CHECK_STATUS("sdk.state-machine.raw-run-stopped", GN_RUN_STOPPED,
                     raw.reason);

    sdk_mvs_snapshot prefix;
    sdk_mvs_snapshot expected;
    sdk_mvs_snapshot replayed;
    uint64_t prior_elapsed = 0u;
    SDK_CHECK_TRUE("sdk.state-machine.first-frame",
                   sdk_mvs_capture_frame(subject, 0u, 0u, prior_elapsed,
                                         &prefix));
    prior_elapsed = prefix.elapsed_total;
    SDK_CHECK_STATUS("sdk.state-machine.capture-frame-boundary", GN_STATUS_OK,
        gn_state_capture_v1(subject, baseline, capacity, &written,
                            &detail, sizeof(detail)));
    SDK_CHECK_U64("sdk.state-machine.full-mvs-state-written", capacity, written);
    size_t board_payload_offset = 0u;
    SDK_CHECK_TRUE("sdk.state-machine.board-section-located",
        sdk_mvs_state_section_payload_offset(baseline, capacity, 3u,
                                              &board_payload_offset));
    memcpy(rejected, baseline, capacity);
    rejected[board_payload_offset + 51u] = UINT8_C(0xa5);
    rejected[board_payload_offset + 52u] = UINT8_C(0x5a);
    SDK_CHECK_STATUS("sdk.state-machine.arbitrary-output-registers-restore",
                     GN_STATUS_OK,
        gn_state_restore_v1(subject, rejected, capacity, &detail,
                            sizeof(detail)));
    size_t output_register_state_size = 0u;
    SDK_CHECK_STATUS("sdk.state-machine.arbitrary-output-registers-recapture",
                     GN_STATUS_OK,
        gn_state_capture_v1(subject, current, capacity,
                            &output_register_state_size, &detail,
                            sizeof(detail)));
    SDK_CHECK_TRUE("sdk.state-machine.arbitrary-output-registers-preserved",
        output_register_state_size == capacity &&
        memcmp(current, rejected, capacity) == 0);
    SDK_CHECK_STATUS("sdk.state-machine.restore-baseline-after-register-check",
                     GN_STATUS_OK,
        gn_state_restore_v1(subject, baseline, capacity, &detail,
                            sizeof(detail)));
    const uintptr_t save_ram_before = gn_test_mvs_save_ram_address(subject);
    SDK_CHECK_TRUE("sdk.state-machine.save-ram-owned-address",
                   save_ram_before != (uintptr_t)0);

    SDK_CHECK_TRUE("sdk.state-machine.expected-continuation",
                   sdk_mvs_capture_frame(subject, 0u, 1u, prior_elapsed,
                                         &expected));
    size_t pixels_produced = 0u;
    SDK_CHECK_STATUS("sdk.state-machine.raw-video-observation", GN_STATUS_OK,
        gn_private_mvs_render_frame(subject, SDK_SOUND_WIDTH, SDK_SOUND_HEIGHT,
            (size_t)SDK_SOUND_WIDTH * sizeof(uint32_t), expected_surface,
            surface_bytes, &pixels_produced));
    SDK_CHECK_U64("sdk.state-machine.raw-video-byte-count",
                   (uint64_t)SDK_SOUND_WIDTH * SDK_SOUND_HEIGHT,
                   pixels_produced);
    SDK_CHECK_TRUE("sdk.state-machine.chip-and-filter-state-advanced",
                   expected.sound.native_samples > prefix.sound.native_samples &&
                   expected.sound.filter_history_digest !=
                       prefix.sound.filter_history_digest);
    SDK_CHECK_STATUS("sdk.state-machine.inject-sound-fault", GN_STATUS_OK,
        gn_test_mvs_set_failure(subject, GN_TEST_MVS_FAILURE_SOUND_TICK_LIMIT));
    SDK_CHECK_STATUS("sdk.state-machine.sound-fault-status",
                     GN_STATUS_CPU_FAILURE, gn_run(subject, 64u, &raw));
    SDK_CHECK_STATUS("sdk.state-machine.faulted-capture-rejected",
                     GN_STATUS_INVALID_STATE,
        gn_state_capture_v1(subject, current, capacity, &written,
                            &detail, sizeof(detail)));
    SDK_CHECK_U64("sdk.state-machine.fault-latch-reason",
                   GN_STATE_REASON_GUEST_FAULT, detail.reason);
    gn_test_allocator_arm(&allocator, 1u);
    SDK_CHECK_STATUS("sdk.state-machine.restore-full-machine", GN_STATUS_OK,
        gn_state_restore_v1(subject, baseline, capacity, &detail, sizeof(detail)));
    SDK_CHECK_U64("sdk.state-machine.no-fallible-image-allocation-at-commit",
                   0u, allocator.attempts);
    gn_test_allocator_disarm(&allocator);
    SDK_CHECK_U64("sdk.state-machine.save-ram-address-retained",
                   save_ram_before, gn_test_mvs_save_ram_address(subject));
    memset(baseline, 0xddu, capacity);
    free(baseline);
    baseline = NULL;
    SDK_CHECK_TRUE("sdk.state-machine.transfer-buffer-independent",
                   sdk_mvs_capture_frame(subject, 0u, 1u, prior_elapsed,
                                         &replayed));
    SDK_CHECK_TRUE("sdk.state-machine.guest-video-pcm-time-match",
                   sdk_mvs_state_snapshot_equal(&expected, &replayed));
    pixels_produced = 0u;
    SDK_CHECK_STATUS("sdk.state-machine.raw-video-replay", GN_STATUS_OK,
        gn_private_mvs_render_frame(subject, SDK_SOUND_WIDTH, SDK_SOUND_HEIGHT,
            (size_t)SDK_SOUND_WIDTH * sizeof(uint32_t), replayed_surface,
            surface_bytes, &pixels_produced));
    SDK_CHECK_TRUE("sdk.state-machine.full-raw-video-match",
                   pixels_produced == (size_t)SDK_SOUND_WIDTH * SDK_SOUND_HEIGHT &&
                   memcmp(expected_surface, replayed_surface, surface_bytes) == 0);

    SDK_CHECK_STATUS("sdk.state-machine.capture-pre-rejection", GN_STATUS_OK,
        gn_state_capture_v1(subject, current, capacity, &written,
                            &detail, sizeof(detail)));
    memcpy(rejected, current, capacity);
    rejected[68] = 1u; /* Reserved header word must reject before any apply. */
    SDK_CHECK_STATUS("sdk.state-machine.reject-malformed-state",
                     GN_STATUS_INVALID_MEDIA,
                     gn_state_restore_v1(subject, rejected, capacity,
                                         &detail, sizeof(detail)));
    SDK_CHECK_U64("sdk.state-machine.rejection-reason",
                   GN_STATE_REASON_RESERVED, detail.reason);
    SDK_CHECK_STATUS("sdk.state-machine.capture-after-rejection", GN_STATUS_OK,
        gn_state_capture_v1(subject, baseline = (uint8_t *)malloc(capacity),
                            capacity, &written, &detail, sizeof(detail)));
    SDK_CHECK_TRUE("sdk.state-machine.rejected-load-is-atomic",
                   baseline != NULL && memcmp(current, baseline, capacity) == 0);
    SDK_CHECK_U64("sdk.state-machine.save-ram-address-after-rejection",
                   save_ram_before, gn_test_mvs_save_ram_address(subject));
cleanup:
    free(replayed_surface);
    free(expected_surface);
    free(rejected);
    free(current);
    free(baseline);
    gn_destroy(subject);
    SDK_CHECK_U64("sdk.state-machine.owner-allocation-balance", 0u,
                   allocator.live_allocations);
    sdk_mvs_fixture_destroy(&fixture);
}

static int sdk_mvs_restore_rejects_atomically(
    gn_instance *instance, const uint8_t *rejected_state, size_t rejected_length,
    size_t capacity,
    gn_status expected_status, gn_state_reason expected_reason) {
    uint8_t *before = (uint8_t *)malloc(capacity);
    uint8_t *after = (uint8_t *)malloc(capacity);
    if (before == NULL || after == NULL) {
        free(after);
        free(before);
        return 0;
    }
    gn_state_detail_v1 detail;
    size_t before_written = 0u, after_written = 0u;
    int passed = gn_state_capture_v1(instance, before, capacity,
        &before_written, &detail, sizeof(detail)) == GN_STATUS_OK &&
        before_written == capacity &&
        gn_state_restore_v1(instance, rejected_state, rejected_length,
            &detail, sizeof(detail)) == expected_status &&
        detail.reason == expected_reason &&
        gn_state_capture_v1(instance, after, capacity,
            &after_written, &detail, sizeof(detail)) == GN_STATUS_OK &&
        after_written == capacity && memcmp(before, after, capacity) == 0;
    free(after);
    free(before);
    return passed;
}

static int sdk_mvs_state_section_payload_offset(const uint8_t *state,
                                                 size_t capacity,
                                                 uint32_t section_id,
                                                 size_t *out_offset) {
    if (state == NULL || out_offset == NULL || capacity < 72u) return 0;
    size_t offset = 72u;
    for (size_t index = 0u; index < 5u; ++index) {
        if (offset > capacity || capacity - offset < 8u) return 0;
        const uint32_t id = sdk_sound_read_u32_be(state + offset);
        const uint32_t size = sdk_sound_read_u32_be(state + offset + 4u);
        offset += 8u;
        if ((size_t)size > capacity - offset) return 0;
        if (id == section_id) {
            *out_offset = offset;
            return 1;
        }
        offset += size;
    }
    return 0;
}

static void mvs_native_state_identity_is_normalized_and_fail_closed(void) {
    SDK_CASE("sdk.state-identity.mvs-normalized-media");
    sdk_mvs_isolation_fixture fixture;
    memset(&fixture, 0, sizeof(fixture));
    SDK_CHECK_TRUE("sdk.state-identity.fixture-prepared",
                   sdk_mvs_fixture_prepare(&fixture));
    if (fixture.owners[0].bytes == NULL) return;

    gn_mvs_manifest_v3 ordered;
    SDK_CHECK_TRUE("sdk.state-identity.ordered-manifest",
                   sdk_mvs_manifest_make(&fixture.owners[0], &ordered));
    gn_mvs_manifest_v3 reordered = ordered;
    for (size_t index = 0u; index < SDK_SOUND_REGION_COUNT; ++index)
        reordered.regions[index] = ordered.regions[SDK_SOUND_REGION_COUNT - 1u - index];

    sdk_sound_bundle swapped_bundle;
    memset(&swapped_bundle, 0, sizeof(swapped_bundle));
    swapped_bundle.size = fixture.owners[0].size;
    swapped_bundle.bytes = (uint8_t *)malloc(swapped_bundle.size);
    SDK_CHECK_TRUE("sdk.state-identity.word-swap-buffer",
                   swapped_bundle.bytes != NULL);
    if (swapped_bundle.bytes == NULL) goto cleanup;
    memcpy(swapped_bundle.bytes, fixture.owners[0].bytes, swapped_bundle.size);
    memcpy(swapped_bundle.offsets, fixture.owners[0].offsets,
           sizeof(swapped_bundle.offsets));
    memcpy(swapped_bundle.lengths, fixture.owners[0].lengths,
           sizeof(swapped_bundle.lengths));
    for (size_t role = 0u; role < SDK_SOUND_REGION_COUNT; ++role) {
        uint8_t *region = swapped_bundle.bytes + swapped_bundle.offsets[role];
        for (size_t byte = 0u; byte < swapped_bundle.lengths[role]; byte += 2u) {
            const uint8_t first = region[byte];
            region[byte] = region[byte + 1u];
            region[byte + 1u] = first;
        }
    }
    gn_mvs_manifest_v3 word_swapped;
    SDK_CHECK_TRUE("sdk.state-identity.swapped-manifest",
                   sdk_mvs_manifest_make(&swapped_bundle, &word_swapped));
    for (size_t index = 0u; index < SDK_SOUND_REGION_COUNT / 2u; ++index) {
        const size_t opposite = SDK_SOUND_REGION_COUNT - 1u - index;
        const gn_mvs_region temporary = word_swapped.regions[index];
        word_swapped.regions[index] = word_swapped.regions[opposite];
        word_swapped.regions[opposite] = temporary;
    }
    for (size_t index = 0u; index < SDK_SOUND_REGION_COUNT; ++index)
        word_swapped.regions[index].layout = GN_MVS_LAYOUT_WORD_SWAP;

    gn_mvs_manifest_v3 swapped_roles = ordered;
    const size_t fixed_index = (size_t)GN_MVS_REGION_FIXED - 1u;
    const size_t audio_bios_index =
        (size_t)GN_MVS_REGION_AUDIO_BIOS - 1u;
    SDK_CHECK_TRUE("sdk.state-identity.swapped-role-fixture-distinct",
        memcmp(ordered.regions[fixed_index].source,
               ordered.regions[audio_bios_index].source,
               ordered.regions[fixed_index].source_size) != 0);
    const uint8_t *role_bytes = swapped_roles.regions[fixed_index].source;
    swapped_roles.regions[fixed_index].source =
        swapped_roles.regions[audio_bios_index].source;
    swapped_roles.regions[audio_bios_index].source = role_bytes;

    gn_instance *source = NULL, *role_peer = NULL, *layout_peer = NULL;
    gn_instance *swapped_role_peer = NULL, *foreign = NULL, *optional_peer = NULL;
    SDK_CHECK_STATUS("sdk.state-identity.source-create", GN_STATUS_OK,
                     gn_create(&source));
    SDK_CHECK_STATUS("sdk.state-identity.role-peer-create", GN_STATUS_OK,
                     gn_create(&role_peer));
    SDK_CHECK_STATUS("sdk.state-identity.layout-peer-create", GN_STATUS_OK,
                     gn_create(&layout_peer));
    SDK_CHECK_STATUS("sdk.state-identity.swapped-role-peer-create", GN_STATUS_OK,
                     gn_create(&swapped_role_peer));
    if (source == NULL || role_peer == NULL || layout_peer == NULL ||
        swapped_role_peer == NULL) goto cleanup_instances;
    SDK_CHECK_STATUS("sdk.state-identity.source-load", GN_STATUS_OK,
                     gn_load_mvs_v3(source, &ordered));
    SDK_CHECK_STATUS("sdk.state-identity.role-order-load", GN_STATUS_OK,
                     gn_load_mvs_v3(role_peer, &reordered));
    SDK_CHECK_STATUS("sdk.state-identity.layout-load", GN_STATUS_OK,
                     gn_load_mvs_v3(layout_peer, &word_swapped));
    SDK_CHECK_STATUS("sdk.state-identity.swapped-role-load", GN_STATUS_OK,
                     gn_load_mvs_v3(swapped_role_peer, &swapped_roles));

    gn_state_compatibility_info_v1 source_info, role_info, layout_info;
    gn_state_compatibility_info_v1 swapped_role_info;
    memset(&source_info, 0, sizeof(source_info));
    memset(&role_info, 0, sizeof(role_info));
    memset(&layout_info, 0, sizeof(layout_info));
    memset(&swapped_role_info, 0, sizeof(swapped_role_info));
    SDK_CHECK_STATUS("sdk.state-identity.source-compatibility", GN_STATUS_OK,
        gn_state_compatibility_v1(source, &source_info, sizeof(source_info)));
    SDK_CHECK_STATUS("sdk.state-identity.role-compatibility", GN_STATUS_OK,
        gn_state_compatibility_v1(role_peer, &role_info, sizeof(role_info)));
    SDK_CHECK_STATUS("sdk.state-identity.layout-compatibility", GN_STATUS_OK,
        gn_state_compatibility_v1(layout_peer, &layout_info, sizeof(layout_info)));
    SDK_CHECK_STATUS("sdk.state-identity.swapped-role-compatibility", GN_STATUS_OK,
        gn_state_compatibility_v1(swapped_role_peer, &swapped_role_info,
                                  sizeof(swapped_role_info)));
    SDK_CHECK_U64("sdk.state-identity.profile-id", GN_MVS_PROFILE_MSX,
                   source_info.profile_id);
    SDK_CHECK_U64("sdk.state-identity.configuration-id", 2u,
                   source_info.configuration_id);
    SDK_CHECK_U64("sdk.state-identity.durable-id-enabled", 1u,
                   source_info.durable_save_id);
    SDK_CHECK_TRUE("sdk.state-identity.role-order-equivalent",
        memcmp(source_info.media_identity_sha256,
               role_info.media_identity_sha256, 32u) == 0);
    SDK_CHECK_TRUE("sdk.state-identity.layout-equivalent",
        memcmp(source_info.media_identity_sha256,
               layout_info.media_identity_sha256, 32u) == 0);
    SDK_CHECK_TRUE("sdk.state-identity.swapped-role-differs",
        memcmp(source_info.media_identity_sha256,
               swapped_role_info.media_identity_sha256, 32u) != 0);

    size_t capacity = 0u, role_capacity = 0u, layout_capacity = 0u;
    size_t swapped_role_capacity = 0u;
    SDK_CHECK_STATUS("sdk.state-identity.source-capacity", GN_STATUS_OK,
                     gn_state_capacity_v1(source, &capacity));
    SDK_CHECK_STATUS("sdk.state-identity.role-capacity", GN_STATUS_OK,
                     gn_state_capacity_v1(role_peer, &role_capacity));
    SDK_CHECK_STATUS("sdk.state-identity.layout-capacity", GN_STATUS_OK,
                     gn_state_capacity_v1(layout_peer, &layout_capacity));
    SDK_CHECK_STATUS("sdk.state-identity.swapped-role-capacity", GN_STATUS_OK,
                     gn_state_capacity_v1(swapped_role_peer,
                                          &swapped_role_capacity));
    SDK_CHECK_U64("sdk.state-identity.role-capacity-stable", capacity,
                   role_capacity);
    SDK_CHECK_U64("sdk.state-identity.layout-capacity-stable", capacity,
                   layout_capacity);
    SDK_CHECK_U64("sdk.state-identity.swapped-role-capacity-stable", capacity,
                   swapped_role_capacity);

    sdk_mvs_snapshot boundary;
    SDK_CHECK_TRUE("sdk.state-identity.source-frame",
                   sdk_mvs_capture_frame(source, 0u, 0u, 0u, &boundary));
    uint8_t *state = (uint8_t *)malloc(capacity);
    uint8_t *verify = (uint8_t *)malloc(capacity + 1u);
    uint8_t *mutated = (uint8_t *)malloc(capacity);
    SDK_CHECK_TRUE("sdk.state-identity.state-buffers",
                   state != NULL && verify != NULL && mutated != NULL);
    if (state == NULL || verify == NULL || mutated == NULL) {
        free(mutated); free(verify); free(state);
        goto cleanup_instances;
    }
    gn_state_detail_v1 detail;
    size_t written = 0u;
    SDK_CHECK_STATUS("sdk.state-identity.capture", GN_STATUS_OK,
        gn_state_capture_v1(source, state, capacity, &written,
                            &detail, sizeof(detail)));
    SDK_CHECK_U64("sdk.state-identity.capture-exact", capacity, written);
    SDK_CHECK_TRUE("sdk.state-identity.swapped-role-reject-atomic",
        sdk_mvs_restore_rejects_atomically(swapped_role_peer, state, capacity,
            capacity, GN_STATUS_INVALID_MEDIA,
            GN_STATE_REASON_MEDIA_IDENTITY));
    SDK_CHECK_STATUS("sdk.state-identity.restore-reordered", GN_STATUS_OK,
        gn_state_restore_v1(role_peer, state, capacity, &detail, sizeof(detail)));
    SDK_CHECK_STATUS("sdk.state-identity.restore-word-swapped", GN_STATUS_OK,
        gn_state_restore_v1(layout_peer, state, capacity, &detail, sizeof(detail)));
    size_t verify_written = 0u;
    SDK_CHECK_STATUS("sdk.state-identity.recapture-reordered", GN_STATUS_OK,
        gn_state_capture_v1(role_peer, verify, capacity, &verify_written,
                            &detail, sizeof(detail)));
    SDK_CHECK_TRUE("sdk.state-identity.reordered-full-state-equal",
                   verify_written == capacity && memcmp(state, verify, capacity) == 0);
    SDK_CHECK_STATUS("sdk.state-identity.recapture-word-swapped", GN_STATUS_OK,
        gn_state_capture_v1(layout_peer, verify, capacity, &verify_written,
                            &detail, sizeof(detail)));
    SDK_CHECK_TRUE("sdk.state-identity.word-swapped-full-state-equal",
                   verify_written == capacity && memcmp(state, verify, capacity) == 0);

    size_t z80_payload_offset = 0u, ym_payload_offset = 0u;
    SDK_CHECK_TRUE("sdk.state-identity.z80-section-located",
        sdk_mvs_state_section_payload_offset(state, capacity, 4u,
                                             &z80_payload_offset));
    SDK_CHECK_TRUE("sdk.state-identity.ym-section-located",
        sdk_mvs_state_section_payload_offset(state, capacity, 5u,
                                             &ym_payload_offset));
    memcpy(mutated, state, capacity);
    mutated[z80_payload_offset + 4u] = 2u;
    SDK_CHECK_TRUE("sdk.state-identity.z80-schema-reject-atomic",
        sdk_mvs_restore_rejects_atomically(role_peer, mutated, capacity,
            capacity, GN_STATUS_INVALID_MEDIA, GN_STATE_REASON_CPU_STATE));
    memcpy(mutated, state, capacity);
    sdk_state_write_u32(mutated + ym_payload_offset + 4u, 2u);
    SDK_CHECK_TRUE("sdk.state-identity.ym-schema-reject-atomic",
        sdk_mvs_restore_rejects_atomically(role_peer, mutated, capacity,
            capacity, GN_STATUS_INVALID_MEDIA, GN_STATE_REASON_CPU_STATE));

    static const struct {
        size_t offset;
        uint32_t value;
        gn_status status;
        gn_state_reason reason;
        const char *label;
    } header_mismatches[] = {
        {16u, 2u, GN_STATUS_INVALID_ARGUMENT, GN_STATE_REASON_FORMAT,
         "format"},
        {20u, 2u, GN_STATUS_UNSUPPORTED_PROFILE, GN_STATE_REASON_REPLAY_IDENTITY,
         "replay"},
        {24u, GN_PROFILE_DIAGNOSTIC, GN_STATUS_UNSUPPORTED_PROFILE,
         GN_STATE_REASON_PROFILE_IDENTITY, "profile"},
        {28u, 3u, GN_STATUS_UNSUPPORTED_PROFILE,
         GN_STATE_REASON_CONFIGURATION_IDENTITY, "configuration"},
        {64u, 4u, GN_STATUS_INVALID_MEDIA, GN_STATE_REASON_SECTION, "section"},
        {68u, 1u, GN_STATUS_INVALID_MEDIA, GN_STATE_REASON_RESERVED, "reserved"}
    };
    for (size_t index = 0u;
         index < sizeof(header_mismatches) / sizeof(header_mismatches[0]);
         ++index) {
        memcpy(mutated, state, capacity);
        sdk_state_write_u32(mutated + header_mismatches[index].offset,
                            header_mismatches[index].value);
        SDK_CHECK_TRUE(header_mismatches[index].label,
            sdk_mvs_restore_rejects_atomically(role_peer, mutated, capacity,
                capacity,
                header_mismatches[index].status,
                header_mismatches[index].reason));
    }

    uint8_t *trailing_state = (uint8_t *)malloc(capacity + 1u);
    SDK_CHECK_TRUE("sdk.state-identity.trailing-state-buffer",
                   trailing_state != NULL);
    if (trailing_state != NULL) {
        memcpy(trailing_state, state, capacity);
        trailing_state[capacity] = 0x91u;
        SDK_CHECK_TRUE("sdk.state-identity.trailing-restore-atomic",
            sdk_mvs_restore_rejects_atomically(role_peer, trailing_state,
                capacity + 1u, capacity, GN_STATUS_INVALID_ARGUMENT,
                GN_STATE_REASON_TRAILING_BYTES));
        free(trailing_state);
    }

    memset(verify, 0x6du, capacity);
    written = 123u;
    SDK_CHECK_STATUS("sdk.state-identity.short-capture-rejected",
                     GN_STATUS_INVALID_ARGUMENT,
        gn_state_capture_v1(source, verify, capacity - 1u, &written,
                            &detail, sizeof(detail)));
    SDK_CHECK_U64("sdk.state-identity.short-capture-zero-count", 0u, written);
    SDK_CHECK_U64("sdk.state-identity.short-capture-reason",
                   GN_STATE_REASON_CAPACITY, detail.reason);
    SDK_CHECK_U64("sdk.state-identity.short-capture-buffer-untouched",
                   0x6du, verify[0]);
    SDK_CHECK_STATUS("sdk.state-identity.null-zero-capture-rejected",
                     GN_STATUS_INVALID_ARGUMENT,
        gn_state_capture_v1(source, NULL, 0u, &written,
                            &detail, sizeof(detail)));
    SDK_CHECK_U64("sdk.state-identity.null-zero-capture-invalid-argument",
                   GN_STATE_REASON_INVALID_ARGUMENT, detail.reason);
    SDK_CHECK_U64("sdk.state-identity.null-zero-capture-zero-count", 0u,
                   written);
    memset(verify, 0x6du, capacity);
    gn_state_detail_v1 alias_detail;
    memset(&alias_detail, 0xa5, sizeof(alias_detail));
    SDK_CHECK_STATUS("sdk.state-identity.count-payload-alias-rejected",
                     GN_STATUS_INVALID_ARGUMENT,
        gn_state_capture_v1(source, verify, capacity,
                            (size_t *)verify, &alias_detail,
                            sizeof(alias_detail)));
    SDK_CHECK_U64("sdk.state-identity.count-payload-alias-untouched",
                   0x6du, verify[0]);
    SDK_CHECK_U64("sdk.state-identity.alias-detail-untouched",
                   UINT32_C(0xa5a5a5a5), alias_detail.reason);
    memcpy(verify, state, capacity);
    SDK_CHECK_STATUS("sdk.state-identity.restore-input-detail-alias-rejected",
                     GN_STATUS_INVALID_ARGUMENT,
        gn_state_restore_v1(role_peer, verify, capacity,
                            (gn_state_detail_v1 *)(void *)verify,
                            sizeof(gn_state_detail_v1)));
    SDK_CHECK_TRUE("sdk.state-identity.restore-input-detail-alias-untouched",
                   memcmp(verify, state, capacity) == 0);
    memset(verify, 0x6du, capacity + 1u);
    written = 0u;
    SDK_CHECK_STATUS("sdk.state-identity.oversized-capture", GN_STATUS_OK,
        gn_state_capture_v1(source, verify, capacity + 1u, &written,
                            &detail, sizeof(detail)));
    SDK_CHECK_U64("sdk.state-identity.oversized-capture-exact-count", capacity,
                   written);
    SDK_CHECK_TRUE("sdk.state-identity.oversized-capture-extra-untouched",
                   verify[capacity] == 0x6du);
    SDK_CHECK_TRUE("sdk.state-identity.capture-stable-after-rejected-calls",
        gn_state_capture_v1(source, mutated, capacity, &verify_written,
                            &detail, sizeof(detail)) == GN_STATUS_OK &&
        verify_written == capacity && memcmp(state, mutated, capacity) == 0);

    SDK_CHECK_STATUS("sdk.state-identity.reset-peer", GN_STATUS_OK,
                     gn_reset(layout_peer));
    size_t post_reset_capacity = 0u;
    gn_state_compatibility_info_v1 post_reset_info;
    SDK_CHECK_STATUS("sdk.state-identity.post-reset-capacity", GN_STATUS_OK,
        gn_state_capacity_v1(layout_peer, &post_reset_capacity));
    SDK_CHECK_U64("sdk.state-identity.capacity-survives-reset", capacity,
                   post_reset_capacity);
    SDK_CHECK_STATUS("sdk.state-identity.post-reset-compatibility", GN_STATUS_OK,
        gn_state_compatibility_v1(layout_peer, &post_reset_info,
                                  sizeof(post_reset_info)));
    SDK_CHECK_TRUE("sdk.state-identity.digest-survives-reset",
        memcmp(layout_info.media_identity_sha256,
               post_reset_info.media_identity_sha256, 32u) == 0);

    gn_mvs_manifest_v3 rejected_replacement = ordered;
    rejected_replacement.region_count--;
    SDK_CHECK_STATUS("sdk.state-identity.failed-replacement", GN_STATUS_INVALID_MEDIA,
        gn_load_mvs_v3(source, &rejected_replacement));
    gn_state_compatibility_info_v1 after_replacement;
    size_t after_replacement_capacity = 0u;
    SDK_CHECK_STATUS("sdk.state-identity.replacement-identity", GN_STATUS_OK,
        gn_state_compatibility_v1(source, &after_replacement,
                                  sizeof(after_replacement)));
    SDK_CHECK_TRUE("sdk.state-identity.failed-load-keeps-digest",
        memcmp(source_info.media_identity_sha256,
               after_replacement.media_identity_sha256, 32u) == 0);
    SDK_CHECK_STATUS("sdk.state-identity.replacement-capacity", GN_STATUS_OK,
        gn_state_capacity_v1(source, &after_replacement_capacity));
    SDK_CHECK_U64("sdk.state-identity.failed-load-keeps-capacity", capacity,
                   after_replacement_capacity);

    SDK_CHECK_TRUE("sdk.state-identity.foreign-instance-load",
                   sdk_mvs_instance_load(&fixture.owners[1], &foreign));
    if (foreign != NULL) {
        gn_state_compatibility_info_v1 foreign_info;
        size_t foreign_capacity = 0u;
        SDK_CHECK_STATUS("sdk.state-identity.foreign-info", GN_STATUS_OK,
            gn_state_compatibility_v1(foreign, &foreign_info,
                                      sizeof(foreign_info)));
        SDK_CHECK_TRUE("sdk.state-identity.foreign-digest-differs",
            memcmp(source_info.media_identity_sha256,
                   foreign_info.media_identity_sha256, 32u) != 0);
        SDK_CHECK_STATUS("sdk.state-identity.foreign-capacity", GN_STATUS_OK,
            gn_state_capacity_v1(foreign, &foreign_capacity));
        SDK_CHECK_U64("sdk.state-identity.foreign-capacity-compatible",
                       capacity, foreign_capacity);
        SDK_CHECK_TRUE("sdk.state-identity.foreign-restore-atomic",
            sdk_mvs_restore_rejects_atomically(foreign, state, capacity,
                capacity,
                GN_STATUS_INVALID_MEDIA, GN_STATE_REASON_MEDIA_IDENTITY));
    }

    gn_mvs_manifest_v3 without_audio_bios = ordered;
    without_audio_bios.region_count = 0u;
    for (size_t index = 0u; index < SDK_SOUND_REGION_COUNT; ++index) {
        if (ordered.regions[index].role == GN_MVS_REGION_AUDIO_BIOS) continue;
        without_audio_bios.regions[without_audio_bios.region_count++] =
            ordered.regions[index];
    }
    SDK_CHECK_STATUS("sdk.state-identity.optional-role-instance", GN_STATUS_OK,
                     gn_create(&optional_peer));
    if (optional_peer != NULL) {
        SDK_CHECK_STATUS("sdk.state-identity.optional-role-load", GN_STATUS_OK,
            gn_load_mvs_v3(optional_peer, &without_audio_bios));
        gn_state_compatibility_info_v1 optional_info;
        SDK_CHECK_STATUS("sdk.state-identity.optional-role-info", GN_STATUS_OK,
            gn_state_compatibility_v1(optional_peer, &optional_info,
                                      sizeof(optional_info)));
        SDK_CHECK_TRUE("sdk.state-identity.optional-presence-changes-digest",
            memcmp(source_info.media_identity_sha256,
                   optional_info.media_identity_sha256, 32u) != 0);
    }
    free(mutated); free(verify); free(state);
cleanup_instances:
    gn_destroy(optional_peer);
    gn_destroy(foreign);
    gn_destroy(layout_peer);
    gn_destroy(role_peer);
    gn_destroy(source);
cleanup:
    free(swapped_bundle.bytes);
    sdk_mvs_fixture_destroy(&fixture);
}

static void mvs_status_ok_raw_guest_fault_rejects_capture_and_recovers(void) {
    SDK_CASE("sdk.state-identity.mvs-raw-fault-recovery");
    sdk_mvs_isolation_fixture fixture;
    memset(&fixture, 0, sizeof(fixture));
    SDK_CHECK_TRUE("sdk.state-identity.fault-fixture-ready",
                   sdk_mvs_fixture_prepare(&fixture));
    if (fixture.owners[0].bytes == NULL) return;

    uint8_t *main_bios = fixture.owners[0].bytes +
        fixture.owners[0].offsets[GN_MVS_REGION_BIOS - 1u];
    static const uint8_t input_poll[] = {
        0x10u, 0x39u, 0x00u, 0x30u, 0x00u, 0x00u,
        0x0cu, 0x00u, 0x00u, 0xefu
    };
    static const uint8_t guest_fault[] = {
        0x4au, 0xfcu, 0x00u, 0x00u, 0x00u,
        0x00u, 0x00u, 0x00u, 0x00u, 0x00u
    };
    size_t patches = 0u;
    SDK_CHECK_TRUE("sdk.state-identity.fault-fixture-patch",
        sdk_sound_patch_sequence(main_bios,
            fixture.owners[0].lengths[GN_MVS_REGION_BIOS - 1u],
            input_poll, sizeof(input_poll), guest_fault, sizeof(guest_fault),
            &patches));
    SDK_CHECK_U64("sdk.state-identity.fault-fixture-single-patch", 1u,
                   patches);

    gn_mvs_manifest_v3 manifest;
    SDK_CHECK_TRUE("sdk.state-identity.fault-manifest",
                   sdk_mvs_manifest_make(&fixture.owners[0], &manifest));
    gn_instance *target = NULL;
    SDK_CHECK_STATUS("sdk.state-identity.fault-instance-create", GN_STATUS_OK,
                     gn_create(&target));
    if (target == NULL) {
        sdk_mvs_fixture_destroy(&fixture);
        return;
    }
    SDK_CHECK_STATUS("sdk.state-identity.fault-instance-load", GN_STATUS_OK,
                     gn_load_mvs_v3(target, &manifest));

    size_t capacity = 0u, written = 0u;
    gn_state_detail_v1 detail;
    SDK_CHECK_STATUS("sdk.state-identity.fault-capacity", GN_STATUS_OK,
                     gn_state_capacity_v1(target, &capacity));
    uint8_t *baseline = (uint8_t *)malloc(capacity);
    uint8_t *after = (uint8_t *)malloc(capacity);
    uint8_t *rejected = (uint8_t *)malloc(capacity);
    SDK_CHECK_TRUE("sdk.state-identity.fault-state-buffers",
                   baseline != NULL && after != NULL && rejected != NULL);
    if (baseline == NULL || after == NULL || rejected == NULL) goto cleanup;
    SDK_CHECK_STATUS("sdk.state-identity.fault-baseline-capture", GN_STATUS_OK,
        gn_state_capture_v1(target, baseline, capacity, &written,
                            &detail, sizeof(detail)));
    SDK_CHECK_U64("sdk.state-identity.fault-baseline-exact", capacity, written);

    gn_run_result run;
    SDK_CHECK_STATUS("sdk.state-identity.raw-fault-status-ok", GN_STATUS_OK,
                     gn_run(target, 20000u, &run));
    SDK_CHECK_STATUS("sdk.state-identity.raw-fault-reason", GN_RUN_FAULT,
                     run.reason);
    memset(rejected, 0x6du, capacity);
    written = 77u;
    SDK_CHECK_STATUS("sdk.state-identity.raw-fault-capture-rejected",
                     GN_STATUS_INVALID_STATE,
        gn_state_capture_v1(target, rejected, capacity, &written,
                            &detail, sizeof(detail)));
    SDK_CHECK_U64("sdk.state-identity.raw-fault-reason-detail",
                   GN_STATE_REASON_GUEST_FAULT, detail.reason);
    SDK_CHECK_U64("sdk.state-identity.raw-fault-count-zero", 0u, written);
    SDK_CHECK_U64("sdk.state-identity.raw-fault-payload-untouched",
                   0x6du, rejected[0]);

    SDK_CHECK_STATUS("sdk.state-identity.raw-fault-state-restore", GN_STATUS_OK,
        gn_state_restore_v1(target, baseline, capacity, &detail, sizeof(detail)));
    SDK_CHECK_STATUS("sdk.state-identity.raw-fault-recovered-capture", GN_STATUS_OK,
        gn_state_capture_v1(target, after, capacity, &written,
                            &detail, sizeof(detail)));
    SDK_CHECK_TRUE("sdk.state-identity.raw-fault-recovery-restores-bytes",
                   written == capacity && memcmp(baseline, after, capacity) == 0);
    SDK_CHECK_STATUS("sdk.state-identity.raw-fault-repeat-status-ok", GN_STATUS_OK,
                     gn_run(target, 20000u, &run));
    SDK_CHECK_STATUS("sdk.state-identity.raw-fault-repeat-reason", GN_RUN_FAULT,
                     run.reason);
    SDK_CHECK_STATUS("sdk.state-identity.raw-fault-repeat-capture-rejected",
                     GN_STATUS_INVALID_STATE,
        gn_state_capture_v1(target, rejected, capacity, &written,
                            &detail, sizeof(detail)));
    SDK_CHECK_U64("sdk.state-identity.raw-fault-repeat-latch",
                   GN_STATE_REASON_GUEST_FAULT, detail.reason);
cleanup:
    free(rejected);
    free(after);
    free(baseline);
    gn_destroy(target);
    sdk_mvs_fixture_destroy(&fixture);
}

static void repeat_split_and_interleaved_instances_match_isolated_boundaries(void) {
    SDK_CASE("sdk.isolation.equal-boundary-determinism");
    sdk_isolation_baselines baselines;
    memset(&baselines, 0, sizeof(baselines));
    SDK_CHECK_TRUE("sdk.isolation.isolated-baselines",
                   sdk_build_isolated_baselines(&baselines));
    SDK_CHECK_U64("sdk.isolation.a-arithmetic", 10u,
                  baselines.owners[0][SDK_BOUNDARY_COUNT - 1u].arithmetic);
    SDK_CHECK_U64("sdk.isolation.a-initialized", 0x1237u,
                  baselines.owners[0][SDK_BOUNDARY_COUNT - 1u].initialized);
    SDK_CHECK_U64("sdk.isolation.a-bss", 1u,
                  baselines.owners[0][SDK_BOUNDARY_COUNT - 1u].bss);
    SDK_CHECK_U64("sdk.isolation.b-arithmetic", 16u,
                  baselines.owners[1][SDK_BOUNDARY_COUNT - 1u].arithmetic);
    SDK_CHECK_U64("sdk.isolation.b-initialized", 0x2348u,
                  baselines.owners[1][SDK_BOUNDARY_COUNT - 1u].initialized);
    SDK_CHECK_U64("sdk.isolation.b-bss", 1u,
                  baselines.owners[1][SDK_BOUNDARY_COUNT - 1u].bss);
    SDK_CHECK_TRUE("sdk.isolation.owner-baselines-distinguishable",
                   baselines.owners[0][SDK_BOUNDARY_COUNT - 1u].image_digest !=
                       baselines.owners[1][SDK_BOUNDARY_COUNT - 1u].image_digest);
    SDK_CHECK_TRUE("sdk.isolation.repeat-and-single-call",
                   sdk_repeated_and_single_calls_match(&baselines));
    SDK_CHECK_TRUE("sdk.isolation.interleaved-16-pairs",
                   sdk_interleaved_pairs_match(&baselines));
    SDK_CHECK_TRUE("sdk.isolation.barrier-concurrent-16-pairs",
                   sdk_concurrent_pairs_match(&baselines) &&
                       sdk_mvs_full_machine_isolation());
    (void)printf("SDK_ISOLATION boundaries=%u interleaved_pairs=%u "
                 "barrier_concurrent_pairs=%u "
                 "concurrent_candidate_failure_paths=%u\n",
                 SDK_BOUNDARY_COUNT, SDK_ISOLATION_PAIRS, SDK_ISOLATION_PAIRS,
                 2u * SDK_ISOLATION_PAIRS);
}

static void cold_concurrent_instances_create_fail_recover_and_teardown(void) {
    SDK_CASE("sdk.isolation.cold-concurrent-lifecycle");
    sdk_thread_result results[2];
    SDK_CHECK_TRUE("sdk.cold.barrier-concurrent-pair",
                   sdk_run_barrier_concurrent_pair(results));
    for (unsigned owner = 0u; owner < 2u; ++owner) {
        const sdk_boundary_snapshot *final =
            &results[owner].snapshots[SDK_BOUNDARY_COUNT - 1u];
        SDK_CHECK_TRUE("sdk.cold.candidate-failure-preserved",
                       results[owner].candidate_failure_ok != 0);
        SDK_CHECK_TRUE("sdk.cold.reset-recovery",
                       results[owner].recovery_ok != 0);
        SDK_CHECK_TRUE("sdk.cold.teardown-no-leaks",
                       results[owner].cleanup_ok != 0);
        SDK_CHECK_U64("sdk.cold.final-cycles", 172u, final->elapsed_total);
        SDK_CHECK_U64("sdk.cold.final-instructions", 12u,
                      final->instructions_total);
        SDK_CHECK_U64("sdk.cold.final-pc", 0x12eu, final->boundary_pc);
        SDK_CHECK_U64("sdk.cold.final-trace-events", 35u, final->trace_count);
        SDK_CHECK_U64("sdk.cold.no-trace-drops", 0u, final->trace_dropped);
        SDK_CHECK_U64("sdk.cold.owner-result", owner == 0u ? 10u : 16u,
                      final->arithmetic);
    }
    (void)printf("SDK_COLD process_pairs=1 owners=2 candidate_failure_paths=2 "
                 "reset_recoveries=2 teardown_leaks=0\n");
}

static void swapped_owner_control_fails_exact_owner_assertion(void) {
    SDK_CASE("sdk.isolation.control-swapped-owner");
    gn_instance *wrong_owner = NULL;
    if (!sdk_load_owner(1u, &wrong_owner)) {
        SDK_CHECK_TRUE("sdk.isolation.owner.arithmetic", 0);
        return;
    }
    gn_run_result run;
    (void)gn_run(wrong_owner, 172u, &run);
    gn_observations observations;
    (void)gn_observe(wrong_owner, &observations);
    SDK_CHECK_U64("sdk.isolation.owner.arithmetic", 10u,
                  observations.arithmetic_result);
    gn_destroy(wrong_owner);
}

static void altered_split_progress_control_fails_equal_boundary_assertion(void) {
    SDK_CASE("sdk.isolation.control-altered-split-progress");
    SDK_CHECK_STATUS("sdk.isolation.control-set-progress-mutation", GN_STATUS_OK,
                     gn_test_set_mutation(instance,
                                          GN_TEST_MUTATION_RUN_ELAPSED));
    gn_run_result run;
    SDK_CHECK_STATUS("sdk.isolation.control-run-status", GN_STATUS_OK,
                     gn_run(instance, 40u, &run));
    SDK_CHECK_U64("sdk.isolation.split-progress", 40u, run.elapsed_cycles);
}

static void unloaded_lifecycle_and_null_arguments_are_reported(void) {
    SDK_CASE("sdk.lifecycle.unloaded-and-null-arguments");
    gn_run_result run;
    gn_observations observations;
    memset(&run, 0xa5, sizeof(run));
    memset(&observations, 0xa5, sizeof(observations));

    SDK_CHECK_STATUS("sdk.lifecycle.create-null-output", GN_STATUS_INVALID_ARGUMENT,
                     gn_create(NULL));
    gn_instance *created = (gn_instance *)(uintptr_t)1u;
    SDK_CHECK_STATUS("sdk.lifecycle.create-clears-output", GN_STATUS_OK,
                     gn_create(&created));
    SDK_CHECK_TRUE("sdk.lifecycle.created-handle", created != NULL);
    SDK_CHECK_STATUS("sdk.lifecycle.reset-before-load", GN_STATUS_INVALID_STATE,
                     gn_reset(created));
    SDK_CHECK_STATUS("sdk.lifecycle.run-before-load", GN_STATUS_INVALID_STATE,
                     gn_run(created, 1u, &run));
    SDK_CHECK_U64("sdk.lifecycle.run-output-zero-request", 0u, run.requested_cycles);
    SDK_CHECK_U64("sdk.lifecycle.run-output-zero-reason", GN_RUN_BUDGET, run.reason);
    SDK_CHECK_STATUS("sdk.lifecycle.observe-before-load", GN_STATUS_INVALID_STATE,
                     gn_observe(created, &observations));
    SDK_CHECK_U64("sdk.lifecycle.observe-output-zero", 0u,
                  observations.initialized_result);
    SDK_CHECK_STATUS("sdk.lifecycle.null-run-handle", GN_STATUS_INVALID_ARGUMENT,
                     gn_run(NULL, 1u, &run));
    SDK_CHECK_U64("sdk.lifecycle.null-run-zero-output", 0u, run.elapsed_cycles);
    SDK_CHECK_STATUS("sdk.lifecycle.null-observe-handle", GN_STATUS_INVALID_ARGUMENT,
                     gn_observe(NULL, &observations));
    SDK_CHECK_U64("sdk.lifecycle.null-observe-zero-output", 0u,
                  observations.arithmetic_result);
    SDK_CHECK_STATUS("sdk.lifecycle.null-reset-handle", GN_STATUS_INVALID_ARGUMENT,
                     gn_reset(NULL));
    SDK_CHECK_STATUS("sdk.lifecycle.null-unload-handle", GN_STATUS_INVALID_ARGUMENT,
                     gn_unload(NULL));
    SDK_CHECK_STATUS("sdk.lifecycle.unload-already-unloaded", GN_STATUS_OK,
                     gn_unload(created));
    SDK_CHECK_STATUS("sdk.lifecycle.unload-repeat", GN_STATUS_OK,
                     gn_unload(created));
    SDK_CHECK_STATUS("sdk.lifecycle.run-null-output", GN_STATUS_INVALID_ARGUMENT,
                     gn_run(created, 1u, NULL));
    SDK_CHECK_STATUS("sdk.lifecycle.load-null-manifest", GN_STATUS_INVALID_ARGUMENT,
                     gn_load(created, NULL));
    gn_destroy(NULL);
    gn_destroy(created);
}

static void unload_reload_and_repeated_reset_reproduce_results(void) {
    SDK_CASE("sdk.lifecycle.unload-reload-repeat-reset");
    gn_instance *created = NULL;
    SDK_CHECK_STATUS("sdk.lifecycle.create", GN_STATUS_OK, gn_create(&created));
    SDK_CHECK_STATUS("sdk.lifecycle.load", GN_STATUS_OK, load_scenario(created, 0u));

    for (unsigned reset = 0u; reset < 2u; ++reset) {
        gn_run_result run;
        gn_observations observations;
        SDK_CHECK_STATUS("sdk.lifecycle.reset-loaded", GN_STATUS_OK,
                         gn_reset(created));
        SDK_CHECK_STATUS("sdk.lifecycle.run-after-reset", GN_STATUS_OK,
                         gn_run(created, 172u, &run));
        SDK_CHECK_STATUS("sdk.lifecycle.observe-after-run", GN_STATUS_OK,
                         gn_observe(created, &observations));
        SDK_CHECK_STATUS("sdk.lifecycle.repeat-stop", GN_RUN_STOPPED, run.reason);
        SDK_CHECK_U64("sdk.lifecycle.repeat-result", 10u,
                      observations.arithmetic_result);
        SDK_CHECK_U64("sdk.lifecycle.repeat-initialized", 0x1237u,
                      observations.initialized_result);
    }

    SDK_CHECK_STATUS("sdk.lifecycle.unload", GN_STATUS_OK, gn_unload(created));
    SDK_CHECK_STATUS("sdk.lifecycle.reset-after-unload", GN_STATUS_INVALID_STATE,
                     gn_reset(created));
    SDK_CHECK_STATUS("sdk.lifecycle.reload", GN_STATUS_OK, load_scenario(created, 1u));
    gn_run_result run;
    gn_observations observations;
    SDK_CHECK_STATUS("sdk.lifecycle.run-after-reload", GN_STATUS_OK,
                     gn_run(created, 172u, &run));
    SDK_CHECK_STATUS("sdk.lifecycle.observe-after-reload", GN_STATUS_OK,
                     gn_observe(created, &observations));
    SDK_CHECK_U64("sdk.lifecycle.reloaded-scenario", 16u,
                  observations.arithmetic_result);
    SDK_CHECK_STATUS("sdk.lifecycle.destroy-after-use", GN_STATUS_OK,
                     gn_unload(created));
    gn_destroy(created);
}

static uint64_t test_image_digest(const char *id, const gn_instance *target) {
    uint64_t digest = 0u;
    SDK_CHECK_STATUS(id, GN_STATUS_OK,
                     gn_test_image_digest(target, &digest));
    return digest;
}

static void rejected_manifest_preserves_digest(const char *id,
                                               gn_instance *target,
                                               const gn_manifest *candidate,
                                               gn_status expected) {
    const uint64_t before = test_image_digest("sdk.media.digest-before-reject",
                                              target);
    SDK_CHECK_STATUS(id, expected, gn_load(target, candidate));
    const uint64_t after = test_image_digest("sdk.media.digest-after-reject",
                                             target);
    SDK_CHECK_U64("sdk.media.rejected-load-keeps-full-image", before, after);
}

static void malformed_manifests_are_rejected_before_touching_live_media(void) {
    SDK_CASE("sdk.media.validation-preserves-live-image");
    guest_fixture_image *fixture =
        (guest_fixture_image *)malloc(sizeof(*fixture));
    TEST_ASSERT_NOT_NULL(fixture);
    gn_manifest valid;
    make_manifest(&valid, fixture, GUEST_FIXTURE_SCENARIO_A);
    SDK_CHECK_STATUS("sdk.media.exact-supported-manifest", GN_STATUS_OK,
                     gn_load(instance, &valid));

    gn_instance *baseline = NULL;
    SDK_CHECK_STATUS("sdk.media.baseline-create", GN_STATUS_OK,
                     gn_create(&baseline));
    SDK_CHECK_STATUS("sdk.media.baseline-load", GN_STATUS_OK,
                     load_scenario(baseline, GUEST_FIXTURE_SCENARIO_A));
    gn_run_result initial_run;
    gn_run_result baseline_run;
    SDK_CHECK_STATUS("sdk.media.initial-progress", GN_STATUS_OK,
                     gn_run(instance, 120u, &initial_run));
    SDK_CHECK_STATUS("sdk.media.baseline-progress", GN_STATUS_OK,
                     gn_run(baseline, 120u, &baseline_run));
    SDK_CHECK_STATUS("sdk.media.initial-budget-result", GN_RUN_BUDGET,
                     initial_run.reason);
    const uint64_t loaded_digest = test_image_digest("sdk.media.initial-digest",
                                                     instance);
    SDK_CHECK_U64("sdk.media.baseline-digest-matches",
                  test_image_digest("sdk.media.baseline-digest", baseline),
                  loaded_digest);

    gn_manifest candidate = valid;
    candidate.version += 1u;
    rejected_manifest_preserves_digest("sdk.media.reject-version",
                                       instance, &candidate,
                                       GN_STATUS_INVALID_MEDIA);
    candidate = valid;
    candidate.region_count = 1u;
    rejected_manifest_preserves_digest("sdk.media.reject-short-count",
                                       instance, &candidate,
                                       GN_STATUS_INVALID_MEDIA);
    candidate = valid;
    candidate.region_count = GN_MAX_REGIONS + 1u;
    rejected_manifest_preserves_digest("sdk.media.reject-long-count",
                                       instance, &candidate,
                                       GN_STATUS_INVALID_MEDIA);
    candidate = valid;
    candidate.profile += 1u;
    rejected_manifest_preserves_digest("sdk.media.reject-unsupported-profile",
                                       instance, &candidate,
                                       GN_STATUS_UNSUPPORTED_PROFILE);
    candidate = valid;
    candidate.regions[1].kind = GN_REGION_ROM;
    rejected_manifest_preserves_digest("sdk.media.reject-duplicate-role",
                                       instance, &candidate,
                                       GN_STATUS_INVALID_MEDIA);
    candidate = valid;
    candidate.regions[1].kind = (gn_region_kind)0;
    rejected_manifest_preserves_digest("sdk.media.reject-unknown-role",
                                       instance, &candidate,
                                       GN_STATUS_INVALID_MEDIA);
    candidate = valid;
    candidate.regions[0].source = NULL;
    rejected_manifest_preserves_digest("sdk.media.reject-null-source",
                                       instance, &candidate,
                                       GN_STATUS_INVALID_MEDIA);
    candidate = valid;
    candidate.regions[0].source = NULL;
    candidate.regions[0].source_size = 0u;
    rejected_manifest_preserves_digest("sdk.media.reject-empty-rom",
                                       instance, &candidate,
                                       GN_STATUS_INVALID_MEDIA);
    candidate = valid;
    candidate.regions[1].source_size = 0u;
    rejected_manifest_preserves_digest("sdk.media.reject-empty-ram-seed",
                                       instance, &candidate,
                                       GN_STATUS_INVALID_MEDIA);
    candidate = valid;
    candidate.regions[0].source_size -= 1u;
    rejected_manifest_preserves_digest("sdk.media.reject-short-rom",
                                       instance, &candidate,
                                       GN_STATUS_INVALID_MEDIA);
    candidate = valid;
    candidate.regions[0].source_size += 1u;
    rejected_manifest_preserves_digest("sdk.media.reject-long-rom",
                                       instance, &candidate,
                                       GN_STATUS_INVALID_MEDIA);
    candidate = valid;
    candidate.regions[1].source_size -= 1u;
    rejected_manifest_preserves_digest("sdk.media.reject-short-ram-seed",
                                       instance, &candidate,
                                       GN_STATUS_INVALID_MEDIA);
    candidate = valid;
    candidate.regions[1].source_size += 1u;
    rejected_manifest_preserves_digest("sdk.media.reject-long-ram-seed",
                                       instance, &candidate,
                                       GN_STATUS_INVALID_MEDIA);
    candidate = valid;
    candidate.regions[0].guest_base = 2u;
    rejected_manifest_preserves_digest("sdk.media.reject-rom-base",
                                       instance, &candidate,
                                       GN_STATUS_INVALID_MEDIA);
    candidate = valid;
    candidate.regions[1].mapped_size -= 2u;
    rejected_manifest_preserves_digest("sdk.media.reject-ram-map-size",
                                       instance, &candidate,
                                       GN_STATUS_INVALID_MEDIA);

    guest_fixture_image invalid_vectors = *fixture;
    invalid_vectors.rom[7] = 1u;
    candidate = valid;
    candidate.regions[0].source = invalid_vectors.rom;
    rejected_manifest_preserves_digest("sdk.media.reject-odd-reset-pc",
                                       instance, &candidate,
                                       GN_STATUS_INVALID_MEDIA);
    invalid_vectors = *fixture;
    invalid_vectors.rom[4] = 0u;
    invalid_vectors.rom[5] = 0u;
    invalid_vectors.rom[6] = 2u;
    invalid_vectors.rom[7] = 0u;
    candidate = valid;
    candidate.regions[0].source = invalid_vectors.rom;
    rejected_manifest_preserves_digest("sdk.media.reject-pc-at-map-end",
                                       instance, &candidate,
                                       GN_STATUS_INVALID_MEDIA);
    invalid_vectors = *fixture;
    invalid_vectors.rom[3] = 1u;
    candidate = valid;
    candidate.regions[0].source = invalid_vectors.rom;
    rejected_manifest_preserves_digest("sdk.media.reject-initial-ssp",
                                       instance, &candidate,
                                       GN_STATUS_INVALID_MEDIA);

    uint64_t after_digest = test_image_digest("sdk.media.final-digest", instance);
    SDK_CHECK_U64("sdk.media.all-rejections-kept-current-state", loaded_digest,
                  after_digest);
    gn_run_result final_run;
    gn_run_result baseline_final_run;
    SDK_CHECK_STATUS("sdk.media.continued-run", GN_STATUS_OK,
                     gn_run(instance, 76u, &final_run));
    SDK_CHECK_STATUS("sdk.media.baseline-continued-run", GN_STATUS_OK,
                     gn_run(baseline, 76u, &baseline_final_run));
    SDK_CHECK_STATUS("sdk.media.continued-stop", GN_RUN_STOPPED,
                     final_run.reason);
    SDK_CHECK_U64("sdk.media.continued-cycles-match",
                  baseline_final_run.elapsed_cycles, final_run.elapsed_cycles);
    SDK_CHECK_U64("sdk.media.continued-instructions-match",
                  baseline_final_run.instructions, final_run.instructions);
    SDK_CHECK_U64("sdk.media.continued-pc-match",
                  baseline_final_run.boundary_pc, final_run.boundary_pc);
    gn_observations after;
    gn_observations baseline_after;
    SDK_CHECK_STATUS("sdk.media.continued-observe", GN_STATUS_OK,
                     gn_observe(instance, &after));
    SDK_CHECK_STATUS("sdk.media.baseline-observe", GN_STATUS_OK,
                     gn_observe(baseline, &baseline_after));
    SDK_CHECK_U64("sdk.media.continued-result-match",
                  baseline_after.arithmetic_result, after.arithmetic_result);
    SDK_CHECK_U64("sdk.media.continued-initialized-match",
                  baseline_after.initialized_result, after.initialized_result);
    gn_destroy(baseline);
    free(fixture);
}

static void region_range_arithmetic_and_cap_are_checked_without_dereference(void) {
    SDK_CASE("sdk.media.range-overlap-endpoint-and-cap");
    guest_fixture_image fixture;
    gn_manifest manifest;
    make_manifest(&manifest, &fixture, GUEST_FIXTURE_SCENARIO_A);

    manifest.regions[1].guest_base = GUEST_FIXTURE_ROM_SIZE;
    SDK_CHECK_STATUS("sdk.media.adjacent-spans-layout-valid", GN_STATUS_OK,
                     gn_test_validate_region_layout(&manifest));
    SDK_CHECK_STATUS("sdk.media.adjacent-span-profile-rejected",
                     GN_STATUS_INVALID_MEDIA, gn_load(instance, &manifest));
    manifest.regions[1].guest_base = GUEST_FIXTURE_ROM_SIZE - 1u;
    SDK_CHECK_STATUS("sdk.media.one-byte-overlap-rejected",
                     GN_STATUS_INVALID_MEDIA,
                     gn_test_validate_region_layout(&manifest));
    SDK_CHECK_STATUS("sdk.media.one-byte-overlap-load-rejected",
                     GN_STATUS_INVALID_MEDIA, gn_load(instance, &manifest));

    make_manifest(&manifest, &fixture, GUEST_FIXTURE_SCENARIO_A);
    manifest.regions[0].mapped_size = UINT32_C(800000);
    manifest.regions[1].guest_base = UINT32_C(0x00100000);
    manifest.regions[1].mapped_size =
        (uint32_t)(GN_MAX_MEDIA_BYTES - 522u - 800000u);
    SDK_CHECK_STATUS("sdk.media-exact-one-mib-accounting",
                     GN_STATUS_OK,
                     gn_test_validate_region_layout(&manifest));
    SDK_CHECK_STATUS("sdk.media-exact-one-mib-profile-rejected",
                     GN_STATUS_INVALID_MEDIA, gn_load(instance, &manifest));
    manifest.regions[1].mapped_size += 1u;
    SDK_CHECK_STATUS("sdk.media-over-one-mib-accounting",
                     GN_STATUS_INVALID_MEDIA,
                     gn_test_validate_region_layout(&manifest));
    SDK_CHECK_STATUS("sdk.media-over-one-mib-load-rejected",
                     GN_STATUS_INVALID_MEDIA, gn_load(instance, &manifest));

    make_manifest(&manifest, &fixture, GUEST_FIXTURE_SCENARIO_A);
    manifest.regions[1].source = (const uint8_t *)(uintptr_t)1u;
    manifest.regions[1].source_size = SIZE_MAX;
    manifest.regions[1].mapped_size = UINT32_MAX;
    SDK_CHECK_STATUS("sdk.media-size-max-rejected-before-read",
                     GN_STATUS_INVALID_MEDIA,
                     gn_test_validate_region_layout(&manifest));
    SDK_CHECK_STATUS("sdk.media-size-max-load-rejected-before-read",
                     GN_STATUS_INVALID_MEDIA, gn_load(instance, &manifest));
    manifest.regions[1].source_size = 8u;
    manifest.regions[1].mapped_size = 8u;
    manifest.regions[1].guest_base = UINT32_MAX - 3u;
    SDK_CHECK_STATUS("sdk.media-u32-endpoint-overflow-rejected",
                     GN_STATUS_INVALID_MEDIA,
                     gn_test_validate_region_layout(&manifest));
    SDK_CHECK_STATUS("sdk.media-u32-endpoint-load-rejected",
                     GN_STATUS_INVALID_MEDIA, gn_load(instance, &manifest));
    manifest.regions[1].guest_base = UINT32_C(0x00100000);
    manifest.regions[1].source_size = 1u;
    manifest.regions[1].mapped_size = UINT32_MAX;
    SDK_CHECK_STATUS("sdk.media-u32-map-size-over-cap-rejected",
                     GN_STATUS_INVALID_MEDIA,
                     gn_test_validate_region_layout(&manifest));
    SDK_CHECK_STATUS("sdk.media-u32-map-size-load-rejected",
                     GN_STATUS_INVALID_MEDIA, gn_load(instance, &manifest));
}

static void successful_replacement_owns_source_and_reset_seed(void) {
    SDK_CASE("sdk.media.replacement-copies-and-resets-seed");
    guest_fixture_image *source =
        (guest_fixture_image *)malloc(sizeof(*source));
    TEST_ASSERT_NOT_NULL(source);
    gn_manifest manifest;
    make_manifest(&manifest, source, GUEST_FIXTURE_SCENARIO_B);
    SDK_CHECK_STATUS("sdk.media.load-distinguishable-replacement", GN_STATUS_OK,
                     gn_load(instance, &manifest));
    memset(source, 0xa5, sizeof(*source));
    free(source);

    gn_run_result run;
    gn_observations observations;
    SDK_CHECK_STATUS("sdk.media.reset-after-source-release", GN_STATUS_OK,
                     gn_reset(instance));
    SDK_CHECK_STATUS("sdk.media.run-after-source-release", GN_STATUS_OK,
                     gn_run(instance, 172u, &run));
    SDK_CHECK_STATUS("sdk.media.observe-after-source-release", GN_STATUS_OK,
                     gn_observe(instance, &observations));
    SDK_CHECK_STATUS("sdk.media.replacement-stopped", GN_RUN_STOPPED, run.reason);
    SDK_CHECK_U64("sdk.media.replacement-arithmetic", 16u,
                  observations.arithmetic_result);
    SDK_CHECK_U64("sdk.media.replacement-initialized-seed", 0x2348u,
                  observations.initialized_result);
    SDK_CHECK_U64("sdk.media.replacement-bss-zero-fill", 1u,
                  observations.bss_result);
}

static void peer_start_at_first_instruction(gn_instance *peer,
                                            const char *label) {
    gn_run_result run;
    SDK_CHECK_STATUS(label, GN_STATUS_OK, gn_reset(peer));
    SDK_CHECK_STATUS("sdk.faults.peer-reset-budget", GN_STATUS_OK,
                     gn_run(peer, 40u, &run));
    SDK_CHECK_STATUS("sdk.faults.peer-reset-boundary", GN_RUN_BUDGET,
                     run.reason);
    SDK_CHECK_U64("sdk.faults.peer-reset-pc", 0x100u, run.boundary_pc);
}

static void peer_progress_after_failure(gn_instance *peer,
                                        const char *label) {
    gn_run_result run;
    SDK_CHECK_STATUS(label, GN_STATUS_OK, gn_run(peer, 4u, &run));
    SDK_CHECK_STATUS("sdk.faults.peer-progress-budget", GN_RUN_BUDGET,
                     run.reason);
    SDK_CHECK_U64("sdk.faults.peer-progress-pc", 0x102u, run.boundary_pc);
}

static void assert_test_allocator_counts(const char *label,
                                         const gn_test_allocator *allocator,
                                         size_t attempts,
                                         size_t total_attempts,
                                         size_t live_allocations,
                                         size_t live_bytes) {
    char field[96];
    (void)snprintf(field, sizeof(field), "%s.attempts", label);
    SDK_CHECK_U64(field, attempts, allocator->attempts);
    (void)snprintf(field, sizeof(field), "%s.total-attempts", label);
    SDK_CHECK_U64(field, total_attempts, allocator->total_attempts);
    (void)snprintf(field, sizeof(field), "%s.live-allocations", label);
    SDK_CHECK_U64(field, live_allocations, allocator->live_allocations);
    (void)snprintf(field, sizeof(field), "%s.live-bytes", label);
    SDK_CHECK_U64(field, live_bytes, allocator->live_bytes);
    (void)printf("# ALLOCATION %s attempts=%zu total_attempts=%zu "
                 "live_allocations=%zu live_bytes=%zu\n",
                 label, allocator->attempts, allocator->total_attempts,
                 allocator->live_allocations, allocator->live_bytes);
}

static void assert_named_result(gn_instance *target, uint32_t arithmetic,
                                const char *label) {
    gn_run_result run;
    gn_observations observations;
    SDK_CHECK_STATUS("sdk.faults.recovery-run", GN_STATUS_OK,
                     gn_run(target, 172u, &run));
    SDK_CHECK_STATUS("sdk.faults.recovery-observe", GN_STATUS_OK,
                     gn_observe(target, &observations));
    SDK_CHECK_STATUS(label, GN_RUN_STOPPED, run.reason);
    SDK_CHECK_U64("sdk.faults.recovery-result", arithmetic,
                  observations.arithmetic_result);
}

static void allocation_failures_in_create_and_first_load_are_contained(void) {
    SDK_CASE("sdk.faults.create-and-first-load-allocation-sweep");
    gn_instance *peer = NULL;
    SDK_CHECK_STATUS("sdk.faults.peer-create", GN_STATUS_OK, gn_create(&peer));
    SDK_CHECK_STATUS("sdk.faults.peer-load-b", GN_STATUS_OK,
                     load_scenario(peer, GUEST_FIXTURE_SCENARIO_B));
    peer_start_at_first_instruction(peer, "sdk.faults.peer-before-create-failure");

    gn_test_allocator create_failure;
    gn_test_allocator_init(&create_failure);
    gn_test_allocator_arm(&create_failure, 1u);
    gn_instance *created = (gn_instance *)(uintptr_t)1u;
    ++sdk_failpoint_positions;
    ++sdk_failpoint_failures;
    SDK_CHECK_STATUS("sdk.faults.create-allocation-fails", GN_STATUS_OUT_OF_MEMORY,
                     gn_test_create(&create_failure, &created));
    SDK_CHECK_TRUE("sdk.faults.create-output-cleared", created == NULL);
    assert_test_allocator_counts("create-fail-1", &create_failure, 1u, 1u,
                                 0u, 0u);
    peer_progress_after_failure(peer, "sdk.faults.peer-after-create-failure");

    gn_test_allocator create_success;
    gn_test_allocator_init(&create_success);
    gn_test_allocator_arm(&create_success, 2u);
    ++sdk_failpoint_positions;
    ++sdk_failpoint_success_boundaries;
    SDK_CHECK_STATUS("sdk.faults.create-first-success", GN_STATUS_OK,
                     gn_test_create(&create_success, &created));
    assert_test_allocator_counts("create-success-after-1", &create_success,
                                 1u, 1u, 1u, create_success.live_bytes);
    peer_start_at_first_instruction(peer, "sdk.faults.peer-before-create-success");
    peer_progress_after_failure(peer, "sdk.faults.peer-after-create-success");
    gn_destroy(created);
    assert_test_allocator_counts("create-destroy", &create_success, 1u, 1u,
                                 0u, 0u);

    for (size_t fail_at = 1u; fail_at <= 6u; ++fail_at) {
        gn_test_allocator allocator;
        gn_test_allocator_init(&allocator);
        gn_instance *target = NULL;
        SDK_CHECK_STATUS("sdk.faults.first-load-create", GN_STATUS_OK,
                         gn_test_create(&allocator, &target));
        const size_t baseline_allocations = allocator.live_allocations;
        const size_t baseline_bytes = allocator.live_bytes;
        gn_test_allocator_arm(&allocator, fail_at);
        peer_start_at_first_instruction(peer, "sdk.faults.peer-before-first-load-failure");

        gn_manifest invalid;
        memset(&invalid, 0, sizeof(invalid));
        invalid.version = GN_MANIFEST_VERSION;
        invalid.profile = GN_PROFILE_DIAGNOSTIC;
        SDK_CHECK_STATUS("sdk.faults.invalid-request-before-first-load",
                         GN_STATUS_INVALID_MEDIA, gn_load(target, &invalid));
        SDK_CHECK_U64("sdk.faults.invalid-request-allocation-free", 0u,
                      allocator.attempts);

        const gn_status expected = fail_at <= 5u ? GN_STATUS_OUT_OF_MEMORY
                                                 : GN_STATUS_OK;
        ++sdk_failpoint_positions;
        if (fail_at <= 5u) {
            ++sdk_failpoint_failures;
        } else {
            ++sdk_failpoint_success_boundaries;
        }
        const gn_status actual = load_scenario(target,
                                               GUEST_FIXTURE_SCENARIO_A);
        char label[64];
        (void)snprintf(label, sizeof(label), "first-load-position-%zu", fail_at);
        SDK_CHECK_STATUS(label, expected, actual);
        const size_t expected_attempts = fail_at <= 5u ? fail_at : 5u;
        const size_t expected_total_attempts = 1u + expected_attempts;
        const size_t expected_allocations =
            baseline_allocations + (fail_at <= 5u ? 0u : 5u);
        const size_t expected_bytes = fail_at <= 5u ? baseline_bytes
                                                     : allocator.live_bytes;
        assert_test_allocator_counts(label, &allocator, expected_attempts,
                                     expected_total_attempts,
                                     expected_allocations, expected_bytes);
        peer_progress_after_failure(peer, "sdk.faults.peer-after-first-load-failure");
        gn_test_allocator_disarm(&allocator);

        if (fail_at <= 5u) {
            gn_run_result run;
            gn_observations observations;
            SDK_CHECK_STATUS("sdk.faults.first-load-unloaded-reset",
                             GN_STATUS_INVALID_STATE, gn_reset(target));
            SDK_CHECK_STATUS("sdk.faults.first-load-unloaded-run",
                             GN_STATUS_INVALID_STATE, gn_run(target, 1u, &run));
            SDK_CHECK_U64("sdk.faults.first-load-error-output-cleared", 0u,
                          run.requested_cycles);
            SDK_CHECK_STATUS("sdk.faults.first-load-unloaded-observe",
                             GN_STATUS_INVALID_STATE,
                             gn_observe(target, &observations));
            SDK_CHECK_U64("sdk.faults.first-load-observation-cleared", 0u,
                          observations.arithmetic_result);
            SDK_CHECK_STATUS("sdk.faults.first-load-unload-after-error",
                             GN_STATUS_OK, gn_unload(target));
            SDK_CHECK_STATUS("sdk.faults.first-load-reload", GN_STATUS_OK,
                             load_scenario(target, GUEST_FIXTURE_SCENARIO_B));
        } else {
            SDK_CHECK_STATUS("sdk.faults.first-load-reset", GN_STATUS_OK,
                             gn_reset(target));
            assert_named_result(target, 10u, "sdk.faults.first-load-success-stopped");
            SDK_CHECK_STATUS("sdk.faults.first-load-unload", GN_STATUS_OK,
                             gn_unload(target));
            SDK_CHECK_STATUS("sdk.faults.first-load-reload", GN_STATUS_OK,
                             load_scenario(target, GUEST_FIXTURE_SCENARIO_B));
        }
        SDK_CHECK_STATUS("sdk.faults.first-load-invalid-budget-recovery",
                         GN_STATUS_OK, gn_reset(target));
        assert_named_result(target, 16u, "sdk.faults.first-load-reloaded-b-stopped");
        SDK_CHECK_STATUS("sdk.faults.first-load-final-unload", GN_STATUS_OK,
                         gn_unload(target));
        gn_destroy(target);
        assert_test_allocator_counts("first-load-final-destroy", &allocator,
                                     expected_attempts + 5u,
                                     expected_total_attempts + 5u, 0u, 0u);
    }

    gn_reset(peer);
    assert_named_result(peer, 16u, "sdk.faults.peer-remains-distinct-b");
    gn_destroy(peer);
}

static void allocation_failures_in_replacement_preserve_old_image_and_peer(void) {
    SDK_CASE("sdk.faults.replacement-allocation-sweep");
    gn_instance *peer = NULL;
    SDK_CHECK_STATUS("sdk.faults.replacement-peer-create", GN_STATUS_OK,
                     gn_create(&peer));
    SDK_CHECK_STATUS("sdk.faults.replacement-peer-load-b", GN_STATUS_OK,
                     load_scenario(peer, GUEST_FIXTURE_SCENARIO_B));

    for (size_t fail_at = 1u; fail_at <= 6u; ++fail_at) {
        gn_test_allocator allocator;
        gn_test_allocator_init(&allocator);
        gn_instance *target = NULL;
        SDK_CHECK_STATUS("sdk.faults.replacement-create", GN_STATUS_OK,
                         gn_test_create(&allocator, &target));
        SDK_CHECK_STATUS("sdk.faults.replacement-load-original-a", GN_STATUS_OK,
                         load_scenario(target, GUEST_FIXTURE_SCENARIO_A));
        gn_run_result partial;
        SDK_CHECK_STATUS("sdk.faults.replacement-partial-run", GN_STATUS_OK,
                         gn_run(target, 120u, &partial));
        const uint64_t before = test_image_digest("sdk.faults.replacement-before",
                                                  target);
        const size_t baseline_allocations = allocator.live_allocations;
        const size_t baseline_bytes = allocator.live_bytes;
        gn_test_allocator_arm(&allocator, fail_at);
        peer_start_at_first_instruction(peer,
                                        "sdk.faults.peer-before-replacement-failure");

        gn_manifest invalid;
        memset(&invalid, 0, sizeof(invalid));
        invalid.version = GN_MANIFEST_VERSION;
        invalid.profile = GN_PROFILE_DIAGNOSTIC;
        SDK_CHECK_STATUS("sdk.faults.invalid-request-before-replacement",
                         GN_STATUS_INVALID_MEDIA, gn_load(target, &invalid));
        SDK_CHECK_U64("sdk.faults.replacement-invalid-is-allocation-free", 0u,
                      allocator.attempts);

        const gn_status expected = fail_at <= 5u ? GN_STATUS_OUT_OF_MEMORY
                                                 : GN_STATUS_OK;
        ++sdk_failpoint_positions;
        if (fail_at <= 5u) {
            ++sdk_failpoint_failures;
        } else {
            ++sdk_failpoint_success_boundaries;
        }
        const gn_status actual = load_scenario(target,
                                               GUEST_FIXTURE_SCENARIO_B);
        char label[64];
        (void)snprintf(label, sizeof(label), "replacement-position-%zu", fail_at);
        SDK_CHECK_STATUS(label, expected, actual);
        const size_t expected_attempts = fail_at <= 5u ? fail_at : 5u;
        const size_t expected_total_attempts = 6u + expected_attempts;
        assert_test_allocator_counts(label, &allocator, expected_attempts,
                                     expected_total_attempts,
                                     baseline_allocations, baseline_bytes);
        peer_progress_after_failure(peer,
                                    "sdk.faults.peer-after-replacement-failure");
        gn_test_allocator_disarm(&allocator);

        if (fail_at <= 5u) {
            SDK_CHECK_U64("sdk.faults.failed-replacement-keeps-complete-image",
                          before,
                          test_image_digest("sdk.faults.replacement-after",
                                            target));
            gn_run_result invalid_budget;
            memset(&invalid_budget, 0xa5, sizeof(invalid_budget));
            SDK_CHECK_STATUS("sdk.faults.replacement-invalid-budget",
                             GN_STATUS_INVALID_ARGUMENT,
                             gn_run(target, GN_MAX_CYCLE_BUDGET + 1u,
                                    &invalid_budget));
            SDK_CHECK_U64("sdk.faults.replacement-invalid-budget-zeroed", 0u,
                          invalid_budget.requested_cycles);
            SDK_CHECK_STATUS("sdk.faults.replacement-reset-after-error",
                             GN_STATUS_OK, gn_reset(target));
            assert_named_result(target, 10u,
                                "sdk.faults.replacement-old-a-recovers");
            SDK_CHECK_STATUS("sdk.faults.replacement-unload-after-error",
                             GN_STATUS_OK, gn_unload(target));
            SDK_CHECK_STATUS("sdk.faults.replacement-reload-after-error",
                             GN_STATUS_OK,
                             load_scenario(target, GUEST_FIXTURE_SCENARIO_B));
        } else {
            SDK_CHECK_TRUE("sdk.faults.successful-replacement-changes-image",
                           before != test_image_digest(
                                        "sdk.faults.replacement-success-digest",
                                        target));
            assert_named_result(target, 16u,
                                "sdk.faults.successful-replacement-b");
            SDK_CHECK_STATUS("sdk.faults.successful-replacement-reset",
                             GN_STATUS_OK, gn_reset(target));
        }
        assert_named_result(target, 16u, "sdk.faults.replacement-b-recovery");
        SDK_CHECK_STATUS("sdk.faults.replacement-final-unload", GN_STATUS_OK,
                         gn_unload(target));
        gn_destroy(target);
        assert_test_allocator_counts("replacement-final-destroy", &allocator,
                                     expected_attempts + (fail_at <= 5u ? 5u : 0u),
                                     expected_total_attempts +
                                         (fail_at <= 5u ? 5u : 0u),
                                     0u, 0u);
    }

    gn_reset(peer);
    assert_named_result(peer, 16u, "sdk.faults.replacement-peer-b");
    gn_destroy(peer);
}

static void guest_fault_reset_and_invalid_requests_allow_recovery(void) {
    SDK_CASE("sdk.faults.guest-fault-and-invalid-request-recovery");
    guest_fixture_image fixture;
    gn_manifest manifest;
    make_manifest(&manifest, &fixture, GUEST_FIXTURE_SCENARIO_A);
    fixture.rom[0x100u] = UINT8_C(0x4a);
    fixture.rom[0x101u] = UINT8_C(0xfc);
    SDK_CHECK_STATUS("sdk.faults.load-guest-fault", GN_STATUS_OK,
                     gn_load(instance, &manifest));
    gn_run_result result;
    SDK_CHECK_STATUS("sdk.faults.guest-fault-run-status", GN_STATUS_OK,
                     gn_run(instance, 172u, &result));
    SDK_CHECK_STATUS("sdk.faults.guest-fault-reason", GN_RUN_FAULT,
                     result.reason);
    SDK_CHECK_U64("sdk.faults.guest-fault-pc", 0x100u, result.fault_pc);
    SDK_CHECK_STATUS("sdk.faults.reset-after-guest-fault", GN_STATUS_OK,
                     gn_reset(instance));
    SDK_CHECK_STATUS("sdk.faults.repeat-guest-fault-status", GN_STATUS_OK,
                     gn_run(instance, 172u, &result));
    SDK_CHECK_STATUS("sdk.faults.repeat-guest-fault-reason", GN_RUN_FAULT,
                     result.reason);
    SDK_CHECK_STATUS("sdk.faults.unload-after-guest-fault", GN_STATUS_OK,
                     gn_unload(instance));
    SDK_CHECK_STATUS("sdk.faults.reload-after-guest-fault", GN_STATUS_OK,
                     load_scenario(instance, GUEST_FIXTURE_SCENARIO_B));
    assert_named_result(instance, 16u, "sdk.faults.valid-run-after-fault");
}

static void sdk_lifecycle_suite(void) {
    RUN_TEST(unloaded_lifecycle_and_null_arguments_are_reported);
    RUN_TEST(unload_reload_and_repeated_reset_reproduce_results);
}

static void sdk_media_suite(void) {
    RUN_TEST(malformed_manifests_are_rejected_before_touching_live_media);
    RUN_TEST(region_range_arithmetic_and_cap_are_checked_without_dereference);
    RUN_TEST(successful_replacement_owns_source_and_reset_seed);
}

static void sdk_faults_suite(void) {
    RUN_TEST(allocation_failures_in_create_and_first_load_are_contained);
    RUN_TEST(allocation_failures_in_replacement_preserve_old_image_and_peer);
    RUN_TEST(guest_fault_reset_and_invalid_requests_allow_recovery);
    (void)printf("# FAILPOINT_SWEEP positions=%" PRIu64
                 " injected_failures=%" PRIu64
                 " successful_boundaries=%" PRIu64 "\n",
                 sdk_failpoint_positions, sdk_failpoint_failures,
                 sdk_failpoint_success_boundaries);
    SDK_CHECK_U64("sdk.faults.failpoint-positions", 14u,
                  sdk_failpoint_positions);
    SDK_CHECK_U64("sdk.faults.injected-failure-count", 11u,
                  sdk_failpoint_failures);
    SDK_CHECK_U64("sdk.faults.first-success-boundaries", 3u,
                  sdk_failpoint_success_boundaries);
}

static void sdk_diagnostic_suite(void) {
    RUN_TEST(original_guest_computes_named_results);
    RUN_TEST(failed_replacement_and_reset_preserve_owned_media);
    RUN_TEST(scenario_b_has_distinguishable_named_results);
    RUN_TEST(original_instruction_boundaries_match_manual_recipe);
}

static void sdk_state_tracer_suite(void) {
    RUN_TEST(diagnostic_native_state_tracer_round_trips_real_continuation);
}

static void sdk_state_identity_suite(void) {
    RUN_TEST(diagnostic_identity_exposes_ids_and_rejects_mismatch);
    RUN_TEST(mvs_native_state_identity_is_normalized_and_fail_closed);
    RUN_TEST(mvs_status_ok_raw_guest_fault_rejects_capture_and_recovers);
}

static void sdk_state_ym_suite(void) {
    RUN_TEST(ym2610_state_round_trip_continues_pcm_and_timer_after_source_destruction);
    RUN_TEST(ym2610_state_uses_canonical_scalars_and_rejects_invalid_nested_input);
    RUN_TEST(ym2610_state_allocation_failures_are_swept_and_atomic);
}

static void sdk_state_machine_suite(void) {
    RUN_TEST(mvs_native_state_api_accepts_the_public_machine_profile);
    RUN_TEST(mvs_native_state_restores_full_continuation_atomically);
}

static void sdk_run_suite(void) {
    RUN_TEST(bounded_run_reports_actual_progress_and_preserves_invalid_requests);
    RUN_TEST(stopped_guest_consumes_idle_budget_without_dispatches);
    RUN_TEST(reset_debt_overflow_is_rejected_before_any_event_mutation);
    RUN_TEST(unsupported_instruction_exposes_only_bounded_fault_details);
    RUN_TEST(host_fault_is_sticky_until_reset_and_can_recover);
    RUN_TEST(expected_result_integer_boundaries_match_original_encodings);
}

static void sdk_controls_suite(void) {
    RUN_TEST(named_observations_and_bounded_functional_trace_match_fixture);
}

static void sdk_isolation_suite(void) {
    RUN_TEST(repeat_split_and_interleaved_instances_match_isolated_boundaries);
}

static void sdk_cold_suite(void) {
    RUN_TEST(cold_concurrent_instances_create_fail_recover_and_teardown);
}

static void sdk_control_suite(void) {
    if (strcmp(selected_suite, "control-swapped-owner") == 0) {
        RUN_TEST(swapped_owner_control_fails_exact_owner_assertion);
    } else if (strcmp(selected_suite, "control-altered-split-progress") == 0) {
        RUN_TEST(altered_split_progress_control_fails_equal_boundary_assertion);
    } else {
        RUN_TEST(controlled_wrong_behavior_fails_its_exact_assertion);
    }
}

int main(int argc, char **argv) {
    if (argc != 2) {
        (void)fprintf(stderr,
                      "usage: %s <diagnostic|lifecycle|media|faults|run|controls|"
                      "isolation|cold|state-tracer|state-identity|state-ym|"
                      "state-machine|control-...>\n",
                      argv[0]);
        return 2;
    }
    sdk_sound_set_fixture_path(argv[0]);
    selected_suite = argv[1];
    UNITY_BEGIN();
    if (strcmp(selected_suite, "diagnostic") == 0) {
        sdk_diagnostic_suite();
    } else if (strcmp(selected_suite, "lifecycle") == 0) {
        sdk_lifecycle_suite();
    } else if (strcmp(selected_suite, "media") == 0) {
        sdk_media_suite();
    } else if (strcmp(selected_suite, "faults") == 0) {
        sdk_faults_suite();
    } else if (strcmp(selected_suite, "run") == 0) {
        sdk_run_suite();
    } else if (strcmp(selected_suite, "controls") == 0) {
        sdk_controls_suite();
    } else if (strcmp(selected_suite, "isolation") == 0) {
        sdk_isolation_suite();
    } else if (strcmp(selected_suite, "cold") == 0) {
        sdk_cold_suite();
    } else if (strcmp(selected_suite, "state-tracer") == 0) {
        sdk_state_tracer_suite();
    } else if (strcmp(selected_suite, "state-identity") == 0) {
        sdk_state_identity_suite();
    } else if (strcmp(selected_suite, "state-ym") == 0) {
        sdk_state_ym_suite();
    } else if (strcmp(selected_suite, "state-machine") == 0) {
        sdk_state_machine_suite();
    } else if (suite_is_control()) {
        sdk_control_suite();
    } else {
        (void)fprintf(stderr, "unknown suite: %s\n", selected_suite);
        return 2;
    }
    const int failures = UNITY_END();
    if (sdk_cases == 0u) {
        (void)fprintf(stderr, "suite executed zero named cases: %s\n",
                       selected_suite);
        return 2;
    }
    sdk_test_result(selected_suite, failures, GLUEYNEO_SOURCE_REVISION,
                    GLUEYNEO_CONFIGURATION, GLUEYNEO_COMPILER_ID,
                    GLUEYNEO_COMPILER_VERSION);
    return failures;
}
