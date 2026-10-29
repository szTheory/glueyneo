/* SPDX-License-Identifier: MIT */
#include "../support/portable_stdio.h"

#include "guest_fixture.h"
#include "state_fixture.h"

#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#if defined(_WIN32)
#include <process.h>
#define STATE_PROCESS_ID() ((long long)_getpid())
#else
#include <unistd.h>
#define STATE_PROCESS_ID() ((long long)getpid())
#endif

#ifndef GLUEYNEO_SOURCE_REVISION
#define GLUEYNEO_SOURCE_REVISION "unknown"
#endif
#ifndef GLUEYNEO_SOURCE_CONTENT_ID
#define GLUEYNEO_SOURCE_CONTENT_ID "unknown"
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
#ifndef GLUEYNEO_SANITIZER
#define GLUEYNEO_SANITIZER "NONE"
#endif

#define STATE_PROCESS_MAX_PAYLOAD ((size_t)1024u * 1024u)
#define STATE_LOCAL_MAX_BUNDLE_BYTES ((size_t)64u * 1024u * 1024u + 512u)
#define STATE_LOCAL_MAX_ACTIVE_FRAMES 3600u
#define STATE_LOCAL_MAX_FUTURE_FRAMES 8u
#define STATE_LOCAL_MAX_BOOT_FRAMES 1200u
#define STATE_LOCAL_MAX_ATTRACT_CHUNKS 256u
#define STATE_LOCAL_SAVE_RAM_BYTES ((size_t)0x10000u)
#define DIAGNOSTIC_WARMUP_CYCLES UINT64_C(40)
#define STATE_FRONTEND_WINDOW_FRAMES 4u
#define STATE_FRONTEND_MAX_TRACE_BYTES ((size_t)8u * 1024u * 1024u)

static uint64_t process_assertions;
static uint64_t process_failures;

void setUp(void) {}
void tearDown(void) {}

static const uint64_t diagnostic_future_budgets[] = {
    UINT64_C(4), UINT64_C(8), UINT64_C(20), UINT64_C(4),
    UINT64_C(16), UINT64_C(8), UINT64_C(20), UINT64_C(4),
    UINT64_C(16), UINT64_C(8), UINT64_C(20), UINT64_C(4)
};

static const uint32_t mvs_future_inputs[] = {
    0u, GN_MVS_INPUT_P1_A, GN_MVS_INPUT_P1_B, 0u
};

typedef struct {
    uint64_t observations;
    uint64_t elapsed_cycles;
    uint64_t nonzero_guest_values;
    uint64_t video_frames;
    uint64_t video_bytes;
    uint64_t nonzero_video_bytes;
    uint64_t audio_frames;
    uint64_t audio_samples;
    uint64_t nonzero_audio_samples;
    uint64_t payload_bytes;
    uint8_t media_identity[32];
    uint32_t profile_id;
    uint32_t configuration_id;
} process_metrics;

static int process_check(const char *name, int condition) {
    ++process_assertions;
    if (!condition) {
        ++process_failures;
        (void)fprintf(stderr,
                       "STATE_ASSERT %s expected=1 observed=0\n", name);
        return 0;
    }
    return 1;
}

static int write_bytes(FILE *file, const void *bytes, size_t length) {
    return file != NULL && (length == 0u ||
        fwrite(bytes, 1u, length, file) == length);
}

static int write_u8(FILE *file, uint8_t value) {
    return write_bytes(file, &value, sizeof(value));
}

static int write_u16be(FILE *file, uint16_t value) {
    const uint8_t bytes[2] = {
        (uint8_t)(value >> 8), (uint8_t)value
    };
    return write_bytes(file, bytes, sizeof(bytes));
}

static int write_u32be(FILE *file, uint32_t value) {
    uint8_t bytes[4];
    state_fixture_write_u32be(bytes, value);
    return write_bytes(file, bytes, sizeof(bytes));
}

static int write_u64be(FILE *file, uint64_t value) {
    return write_u32be(file, (uint32_t)(value >> 32)) &&
           write_u32be(file, (uint32_t)value);
}

static int write_trace_header(FILE *file, const char magic[4],
                              uint32_t count) {
    return write_bytes(file, magic, 4u) && write_u32be(file, 1u) &&
           write_u32be(file, count);
}

static int write_state_file(const char *path, const uint8_t *state,
                            size_t state_size) {
    FILE *file = gn_portable_fopen(path, "wb");
    if (file == NULL) return 0;
    int ok = write_bytes(file, state, state_size);
    if (fclose(file) != 0) ok = 0;
    return ok;
}

static int read_state_file(const char *path, uint8_t **out_state,
                           size_t *out_size) {
    if (out_state == NULL || out_size == NULL) return 0;
    *out_state = NULL;
    *out_size = 0u;
    FILE *file = gn_portable_fopen(path, "rb");
    if (file == NULL) return 0;
    int ok = fseek(file, 0L, SEEK_END) == 0;
    const long end = ok ? ftell(file) : -1L;
    if (end <= 0L || (uintmax_t)end > (uintmax_t)STATE_PROCESS_MAX_PAYLOAD)
        ok = 0;
    if (ok && fseek(file, 0L, SEEK_SET) != 0) ok = 0;
    uint8_t *state = ok ? (uint8_t *)malloc((size_t)end) : NULL;
    if (state == NULL) ok = 0;
    if (ok && fread(state, 1u, (size_t)end, file) != (size_t)end) ok = 0;
    if (fclose(file) != 0) ok = 0;
    if (!ok) {
        free(state);
        return 0;
    }
    *out_state = state;
    *out_size = (size_t)end;
    return 1;
}

static int file_contents_equal(const char *left_path,
                               const char *right_path) {
    FILE *left = gn_portable_fopen(left_path, "rb");
    FILE *right = gn_portable_fopen(right_path, "rb");
    int equal = left != NULL && right != NULL;
    uint8_t left_bytes[8192];
    uint8_t right_bytes[8192];
    while (equal) {
        const size_t left_count = fread(left_bytes, 1u, sizeof(left_bytes), left);
        const size_t right_count = fread(right_bytes, 1u, sizeof(right_bytes), right);
        if (left_count != right_count ||
            memcmp(left_bytes, right_bytes, left_count) != 0) {
            equal = 0;
            break;
        }
        if (left_count == 0u) break;
    }
    if (left != NULL && fclose(left) != 0) equal = 0;
    if (right != NULL && fclose(right) != 0) equal = 0;
    return equal;
}

static int append_suffix(const char *path, const char *suffix,
                         char *out_path, size_t capacity) {
    const size_t path_length = strlen(path);
    const size_t suffix_length = strlen(suffix);
    if (path_length > capacity || suffix_length >= capacity - path_length)
        return 0;
    memcpy(out_path, path, path_length);
    memcpy(out_path + path_length, suffix, suffix_length + 1u);
    return 1;
}

static int write_capture(const char *path, gn_instance *instance,
                         size_t *out_size) {
    uint8_t *state = NULL;
    size_t written = 0u;
    if (!state_fixture_capture(instance, &state, &written)) return 0;
    if (written > STATE_PROCESS_MAX_PAYLOAD ||
        !state_fixture_guard_valid(state, written)) {
        memset(state, 0xa5, written);
        free(state);
        return 0;
    }
    const int ok = write_state_file(path, state, written);
    memset(state, 0xa5, written);
    free(state);
    if (ok) *out_size = written;
    return ok;
}

static int read_compatibility(gn_instance *instance,
                              process_metrics *metrics) {
    gn_state_compatibility_info_v1 info;
    memset(&info, 0, sizeof(info));
    info.size = (uint32_t)sizeof(info);
    if (gn_state_compatibility_v1(instance, &info, sizeof(info)) !=
        GN_STATUS_OK)
        return 0;
    memcpy(metrics->media_identity, info.media_identity_sha256,
           sizeof(metrics->media_identity));
    metrics->profile_id = info.profile_id;
    metrics->configuration_id = info.configuration_id;
    return 1;
}

static int load_diagnostic(gn_instance **out_instance, unsigned scenario) {
    *out_instance = NULL;
    if (gn_create(out_instance) != GN_STATUS_OK || *out_instance == NULL)
        return 0;
    guest_fixture_image fixture;
    guest_fixture_build(&fixture, (guest_fixture_scenario)scenario);
    gn_manifest manifest;
    memset(&manifest, 0, sizeof(manifest));
    manifest.version = GN_MANIFEST_VERSION;
    manifest.profile = GN_PROFILE_DIAGNOSTIC;
    manifest.region_count = 2u;
    manifest.regions[0] = (gn_region){
        0u, GUEST_FIXTURE_ROM_SIZE, fixture.rom,
        sizeof(fixture.rom), GN_REGION_ROM
    };
    manifest.regions[1] = (gn_region){
        UINT32_C(0x1000), UINT32_C(4096), fixture.ram_seed,
        sizeof(fixture.ram_seed), GN_REGION_RAM
    };
    const gn_status status = gn_load(*out_instance, &manifest);
    memset(&fixture, 0xa5, sizeof(fixture));
    if (status != GN_STATUS_OK) {
        gn_destroy(*out_instance);
        *out_instance = NULL;
        return 0;
    }
    return 1;
}

static int run_diagnostic(gn_instance *instance, const char *trace_path,
                          process_metrics *metrics) {
    FILE *trace = gn_portable_fopen(trace_path, "wb");
    if (trace == NULL) return 0;
    int ok = write_trace_header(trace, "GNSD",
        (uint32_t)(sizeof(diagnostic_future_budgets) /
                   sizeof(diagnostic_future_budgets[0])));
    uint64_t total_cycles = 0u;
    for (size_t index = 0u; ok && index <
         sizeof(diagnostic_future_budgets) /
         sizeof(diagnostic_future_budgets[0]); ++index) {
        const uint64_t budget = diagnostic_future_budgets[index];
        gn_run_result result;
        gn_observations observations;
        memset(&result, 0, sizeof(result));
        memset(&observations, 0, sizeof(observations));
        ok = gn_run(instance, budget, &result) == GN_STATUS_OK &&
             gn_observe(instance, &observations) == GN_STATUS_OK &&
             UINT64_MAX - total_cycles >= result.elapsed_cycles;
        if (!ok) break;
        total_cycles += result.elapsed_cycles;
        ok = write_u64be(trace, budget) &&
             write_u64be(trace, result.requested_cycles) &&
             write_u64be(trace, result.elapsed_cycles) &&
             write_u64be(trace, result.overshoot_cycles) &&
             write_u64be(trace, result.instructions) &&
             write_u32be(trace, (uint32_t)result.reason) &&
             write_u32be(trace, result.boundary_pc) &&
             write_u32be(trace, result.fault_pc) &&
             write_u32be(trace, result.instruction_register) &&
             write_u32be(trace, observations.arithmetic_result) &&
             write_u32be(trace, observations.initialized_result) &&
             write_u32be(trace, observations.bss_result) &&
             write_u8(trace, observations.ready) &&
             write_u64be(trace, total_cycles);
        if (!ok) break;
        ++metrics->observations;
        metrics->elapsed_cycles += result.elapsed_cycles;
        metrics->nonzero_guest_values +=
            (observations.arithmetic_result != 0u) +
            (observations.initialized_result != 0u) +
            (observations.bss_result != 0u) + (observations.ready != 0u);
    }
    if (fclose(trace) != 0) ok = 0;
    return ok;
}

static int run_mvs(gn_instance *instance, const char *trace_path,
                   process_metrics *metrics) {
    FILE *trace = gn_portable_fopen(trace_path, "wb");
    if (trace == NULL) return 0;
    const uint32_t count = (uint32_t)(sizeof(mvs_future_inputs) /
                                      sizeof(mvs_future_inputs[0]));
    int ok = write_trace_header(trace, "GNSM", count);
    uint64_t total_cycles = 0u;
    for (size_t index = 0u; ok && index < count; ++index) {
        state_fixture_observation observation;
        memset(&observation, 0, sizeof(observation));
        if (!state_fixture_advance(instance, mvs_future_inputs[index],
                                   &observation) ||
            UINT64_MAX - total_cycles < observation.result.elapsed_cycles) {
            ok = 0;
            break;
        }
        total_cycles += observation.result.elapsed_cycles;
        const gn_mvs_frame_result_v1 *result = &observation.result;
        ok = write_u32be(trace, mvs_future_inputs[index]) &&
             write_u32be(trace, result->version) &&
             write_u64be(trace, result->requested_cycles) &&
             write_u64be(trace, result->elapsed_cycles) &&
             write_u64be(trace, result->instructions) &&
             write_u64be(trace, result->frame_time_numerator) &&
             write_u64be(trace, result->frame_time_denominator) &&
             write_u32be(trace, result->machine_clock_hz_numerator) &&
             write_u32be(trace, result->machine_clock_hz_denominator) &&
             write_u32be(trace, (uint32_t)result->reason) &&
             write_u32be(trace, (uint32_t)result->audio_format) &&
             write_u32be(trace, result->audio_sample_rate) &&
             write_u32be(trace, result->audio_channels) &&
             write_u64be(trace, (uint64_t)result->audio_frames_generated) &&
             write_u64be(trace, (uint64_t)result->audio_frames_discarded) &&
             write_u64be(trace, (uint64_t)result->audio_frames_delivered) &&
             write_u64be(trace, (uint64_t)result->video_pixels_produced) &&
             write_u8(trace, observation.guest_reply) &&
             write_u64be(trace, total_cycles) &&
             write_u64be(trace, observation.audio_frames) &&
             write_bytes(trace, observation.pixels,
                         sizeof(observation.pixels));
        for (size_t sample = 0u; ok && sample <
             observation.audio_frames * 2u; ++sample) {
            ok = write_u16be(trace, (uint16_t)observation.audio[sample]);
            if (observation.audio[sample] != 0)
                ++metrics->nonzero_audio_samples;
        }
        if (!ok) break;
        ++metrics->observations;
        ++metrics->video_frames;
        metrics->video_bytes += sizeof(observation.pixels);
        metrics->audio_frames += observation.audio_frames;
        metrics->audio_samples += observation.audio_frames * 2u;
        metrics->elapsed_cycles += observation.result.elapsed_cycles;
        for (size_t pixel = 0u; pixel < sizeof(observation.pixels); ++pixel) {
            if (observation.pixels[pixel] != 0u)
                ++metrics->nonzero_video_bytes;
        }
    }
    if (fclose(trace) != 0) ok = 0;
    return ok;
}

static int load_profile(const char *profile, gn_instance **out_instance,
                        unsigned variant) {
    if (strcmp(profile, "diagnostic") == 0)
        return load_diagnostic(out_instance, variant);
    if (strcmp(profile, "mvs") == 0)
        return state_fixture_load(out_instance, variant);
    return 0;
}

static int same_process_restore_control(const char *profile,
                                        const char *payload_path) {
    gn_instance *control = NULL;
    uint8_t *state = NULL;
    size_t state_size = 0u;
    const int ok = load_profile(profile, &control, 0u) &&
                   read_state_file(payload_path, &state, &state_size) &&
                   state_fixture_restore(control, state, state_size);
    if (state != NULL) {
        memset(state, 0xa5, state_size);
        free(state);
    }
    gn_destroy(control);
    return ok;
}

static int warm_profile(const char *profile, gn_instance *instance) {
    if (strcmp(profile, "diagnostic") == 0) {
        gn_run_result result;
        memset(&result, 0, sizeof(result));
        return gn_run(instance, DIAGNOSTIC_WARMUP_CYCLES, &result) ==
                   GN_STATUS_OK &&
               result.requested_cycles == DIAGNOSTIC_WARMUP_CYCLES;
    }
    state_fixture_observation observation;
    return state_fixture_advance(instance, 0u, &observation) &&
           state_fixture_advance(instance, GN_MVS_INPUT_P1_A, &observation);
}

static int export_process(const char *profile, const char *payload_path,
                          const char *trace_path, process_metrics *metrics) {
    gn_instance *instance = NULL;
    int ok = load_profile(profile, &instance, 0u) &&
             process_check("sdk.state.process.exporter-loads-independent-media",
                           instance != NULL) &&
             warm_profile(profile, instance) &&
             process_check("sdk.state.process.exporter-captures-after-warmup",
                           instance != NULL) &&
             read_compatibility(instance, metrics);
    size_t payload_size = 0u;
    if (ok) ok = write_capture(payload_path, instance, &payload_size);
    if (ok) {
        metrics->payload_bytes = (uint64_t)payload_size;
        ok = process_check("sdk.state.process.same-build-control-restores",
                           same_process_restore_control(profile, payload_path));
    }
    if (ok) {
        ok = strcmp(profile, "diagnostic") == 0
                 ? run_diagnostic(instance, trace_path, metrics)
                 : run_mvs(instance, trace_path, metrics);
    }
    gn_destroy(instance);
    return ok;
}

static int stale_identity_control(const char *profile, const uint8_t *state,
                                  size_t state_size, const char *trace_path) {
    gn_instance *stale_target = NULL;
    gn_instance *reference = NULL;
    char stale_trace[4096] = {0};
    char reference_trace[4096] = {0};
    int ok = load_profile(profile, &stale_target, 1u) &&
             load_profile(profile, &reference, 1u) &&
             append_suffix(trace_path, ".stale", stale_trace,
                           sizeof(stale_trace)) &&
             append_suffix(trace_path, ".stale-reference", reference_trace,
                           sizeof(reference_trace));
    if (ok) {
        gn_state_compatibility_info_v1 wrong_info;
        memset(&wrong_info, 0, sizeof(wrong_info));
        wrong_info.size = (uint32_t)sizeof(wrong_info);
        gn_state_detail_v1 detail;
        memset(&detail, 0, sizeof(detail));
        detail.size = (uint32_t)sizeof(detail);
        const gn_status query_status = gn_state_compatibility_v1(
            stale_target, &wrong_info, sizeof(wrong_info));
        const gn_status restore_status = gn_state_restore_v1(
            stale_target, state, state_size, &detail, sizeof(detail));
        ok = process_check("sdk.state.process.stale-media-identity-differs",
                           query_status == GN_STATUS_OK &&
                           memcmp(wrong_info.media_identity_sha256,
                                  state + 32u, 32u) != 0) &&
             process_check("sdk.state.process.stale-media-import-rejected",
                           restore_status == GN_STATUS_INVALID_MEDIA &&
                           detail.reason == GN_STATE_REASON_MEDIA_IDENTITY);
    }
    if (ok) {
        process_metrics stale_metrics;
        process_metrics reference_metrics;
        memset(&stale_metrics, 0, sizeof(stale_metrics));
        memset(&reference_metrics, 0, sizeof(reference_metrics));
        ok = strcmp(profile, "diagnostic") == 0
            ? run_diagnostic(stale_target, stale_trace, &stale_metrics) &&
              run_diagnostic(reference, reference_trace, &reference_metrics)
            : run_mvs(stale_target, stale_trace, &stale_metrics) &&
              run_mvs(reference, reference_trace, &reference_metrics);
        ok = process_check("sdk.state.process.stale-rejection-preserves-future",
                           ok && file_contents_equal(stale_trace,
                                                     reference_trace));
    }
    if (stale_trace[0] != '\0') (void)remove(stale_trace);
    if (reference_trace[0] != '\0') (void)remove(reference_trace);
    gn_destroy(reference);
    gn_destroy(stale_target);
    return ok;
}

static int distinguishable_peer_control(const char *profile,
                                        gn_instance *peer,
                                        gn_instance *reference,
                                        const char *trace_path) {
    int ok = peer != NULL && reference != NULL;
    if (ok && strcmp(profile, "mvs") == 0) {
        for (size_t index = 0u; ok && index <
             sizeof(mvs_future_inputs) / sizeof(mvs_future_inputs[0]); ++index) {
            state_fixture_observation peer_observation;
            state_fixture_observation reference_observation;
            ok = state_fixture_advance(peer, mvs_future_inputs[index],
                                       &peer_observation) &&
                 state_fixture_advance(reference, mvs_future_inputs[index],
                                       &reference_observation) &&
                 state_fixture_observation_equal(&peer_observation,
                                                 &reference_observation);
        }
        ok = process_check("sdk.state.process.mvs.peer-owner-continuation",
                           ok);
    } else if (ok) {
        char peer_trace[4096] = {0};
        char reference_trace[4096] = {0};
        process_metrics peer_metrics;
        process_metrics reference_metrics;
        memset(&peer_metrics, 0, sizeof(peer_metrics));
        memset(&reference_metrics, 0, sizeof(reference_metrics));
        ok = append_suffix(trace_path, ".peer", peer_trace,
                           sizeof(peer_trace)) &&
             append_suffix(trace_path, ".peer-reference", reference_trace,
                           sizeof(reference_trace)) &&
             run_diagnostic(peer, peer_trace, &peer_metrics) &&
             run_diagnostic(reference, reference_trace, &reference_metrics) &&
             file_contents_equal(peer_trace, reference_trace);
        ok = process_check("sdk.state.process.diagnostic.peer-owner-continuation",
                           ok);
        if (peer_trace[0] != '\0') (void)remove(peer_trace);
        if (reference_trace[0] != '\0') (void)remove(reference_trace);
    }
    return ok;
}

static gn_status restore_import(const char *profile, gn_instance *instance,
                                const uint8_t *state, size_t state_size) {
    if (strcmp(profile, "mvs") == 0)
        return state_fixture_restore(instance, state, state_size)
                   ? GN_STATUS_OK : GN_STATUS_INVALID_MEDIA;
    gn_state_detail_v1 detail;
    memset(&detail, 0, sizeof(detail));
    detail.size = (uint32_t)sizeof(detail);
    return gn_state_restore_v1(instance, state, state_size, &detail,
                               sizeof(detail));
}

static int import_process(const char *profile, const char *payload_path,
                          const char *trace_path, process_metrics *metrics) {
    gn_instance *instance = NULL;
    uint8_t *state = NULL;
    size_t state_size = 0u;
    char repeat_trace[4096];
    int ok = process_check("sdk.state.process.importer-loads-independent-media",
                           load_profile(profile, &instance, 0u)) &&
             read_state_file(payload_path, &state, &state_size) &&
             read_compatibility(instance, metrics);
    if (ok) {
        metrics->payload_bytes = (uint64_t)state_size;
        ok = process_check("sdk.state.process.payload-within-profile-envelope",
                           state_size >= 72u && state_size <=
                               STATE_PROCESS_MAX_PAYLOAD) &&
             stale_identity_control(profile, state, state_size, trace_path);
    }
    gn_instance *peer = NULL;
    gn_instance *peer_reference = NULL;
    process_metrics peer_identity;
    process_metrics peer_reference_identity;
    memset(&peer_identity, 0, sizeof(peer_identity));
    memset(&peer_reference_identity, 0, sizeof(peer_reference_identity));
    if (ok) {
        ok = load_profile(profile, &peer, 1u) &&
             load_profile(profile, &peer_reference, 1u) &&
             read_compatibility(peer, &peer_identity) &&
             read_compatibility(peer_reference, &peer_reference_identity) &&
             process_check("sdk.state.process.peer-media-is-distinguishable",
                           memcmp(metrics->media_identity,
                                  peer_identity.media_identity, 32u) != 0 &&
                           memcmp(peer_identity.media_identity,
                                  peer_reference_identity.media_identity,
                                  32u) == 0);
    }
    if (ok) {
        const gn_status status = restore_import(profile, instance, state,
                                                state_size);
        ok = process_check("sdk.state.process.public-import-succeeds",
                           status == GN_STATUS_OK);
    }
    if (ok) {
        ok = strcmp(profile, "diagnostic") == 0
                 ? run_diagnostic(instance, trace_path, metrics)
                 : run_mvs(instance, trace_path, metrics);
    }
    if (ok && append_suffix(trace_path, ".repeat", repeat_trace,
                            sizeof(repeat_trace))) {
        const gn_status status = restore_import(profile, instance, state,
                                                state_size);
        process_metrics repeat_metrics;
        memset(&repeat_metrics, 0, sizeof(repeat_metrics));
        if (status != GN_STATUS_OK) {
            ok = 0;
        } else {
            ok = strcmp(profile, "diagnostic") == 0
                     ? run_diagnostic(instance, repeat_trace, &repeat_metrics)
                     : run_mvs(instance, repeat_trace, &repeat_metrics);
            ok = ok && file_contents_equal(trace_path, repeat_trace) &&
                 process_check("sdk.state.process.repeated-import-exact-future",
                               ok && file_contents_equal(trace_path,
                                                         repeat_trace));
        }
        (void)remove(repeat_trace);
    } else if (ok) {
        ok = 0;
    }
    if (ok) {
        ok = distinguishable_peer_control(profile, peer, peer_reference,
                                            trace_path);
    }
    if (state != NULL) {
        memset(state, 0xa5, state_size);
        free(state);
    }
    gn_destroy(peer_reference);
    gn_destroy(peer);
    gn_destroy(instance);
    return ok;
}

static void print_hex(const uint8_t *bytes, size_t length, char *out) {
    static const char digits[] = "0123456789abcdef";
    for (size_t index = 0u; index < length; ++index) {
        out[index * 2u] = digits[bytes[index] >> 4];
        out[index * 2u + 1u] = digits[bytes[index] & 15u];
    }
    out[length * 2u] = '\0';
}

static void print_result(const char *mode, const char *profile,
                         const process_metrics *metrics,
                         clock_t cpu_started) {
    char media_identity[65];
    const clock_t cpu_finished = clock();
    double cpu_seconds = -1.0;
    if (cpu_started != (clock_t)-1 && cpu_finished != (clock_t)-1 &&
        cpu_finished >= cpu_started)
        cpu_seconds = (double)(cpu_finished - cpu_started) /
                      (double)CLOCKS_PER_SEC;
    print_hex(metrics->media_identity, sizeof(metrics->media_identity),
              media_identity);
    (void)printf(
        "STATE_RESULT {\"schema_version\":1,\"mode\":\"%s\","
        "\"profile\":\"%s\",\"process_id\":%lld,"
        "\"assertions\":%" PRIu64 ",\"observations\":%" PRIu64 ","
        "\"elapsed_cycles\":%" PRIu64 ",\"nonzero_guest_values\":%" PRIu64 ","
        "\"video_frames\":%" PRIu64 ",\"video_bytes\":%" PRIu64 ","
        "\"nonzero_video_bytes\":%" PRIu64 ",\"audio_frames\":%" PRIu64 ","
        "\"audio_samples\":%" PRIu64 ",\"nonzero_audio_samples\":%" PRIu64 ","
        "\"payload_bytes\":%" PRIu64 ",\"cpu_seconds\":%.6f,"
        "\"profile_id\":%u,"
        "\"configuration_id\":%u,\"media_identity_sha256\":\"%s\","
        "\"source_revision\":\"%s\",\"source_content_sha256\":\"%s\","
        "\"configuration\":\"%s\",\"compiler_id\":\"%s\","
        "\"compiler_version\":\"%s\",\"sanitizer\":\"%s\"}\n",
        mode, profile, STATE_PROCESS_ID(), process_assertions,
        metrics->observations, metrics->elapsed_cycles,
        metrics->nonzero_guest_values, metrics->video_frames,
        metrics->video_bytes, metrics->nonzero_video_bytes,
        metrics->audio_frames, metrics->audio_samples,
        metrics->nonzero_audio_samples, metrics->payload_bytes, cpu_seconds,
        metrics->profile_id, metrics->configuration_id, media_identity,
        GLUEYNEO_SOURCE_REVISION, GLUEYNEO_SOURCE_CONTENT_ID,
        GLUEYNEO_CONFIGURATION, GLUEYNEO_COMPILER_ID,
        GLUEYNEO_COMPILER_VERSION, GLUEYNEO_SANITIZER);
}

typedef struct {
    uint32_t capture_frame;
    uint32_t future_frames;
    uint32_t frame_count;
    uint32_t flags;
    uint32_t *inputs;
} state_local_schedule;

typedef struct {
    gn_mvs_frame_result_v1 result;
    gn_mvs_progress_observation progress;
    gn_mvs_private_video_activity video;
    gn_mvs_bus_fault_observation bus;
    gn_test_mvs_sound_state sound;
    gn_test_mvs_machine_state machine;
    size_t audio_frames;
    uint64_t nonzero_audio_samples;
    uint64_t nonzero_video_bytes;
    uint8_t pixels[STATE_FIXTURE_WIDTH * STATE_FIXTURE_HEIGHT * 4u];
    int16_t audio[GN_MVS_AUDIO_CAPACITY_FRAMES_V1 * 2u];
} state_local_observation;

static uint64_t state_local_read_u64be(const uint8_t *bytes) {
    return ((uint64_t)state_fixture_read_u32be(bytes) << 32) |
           state_fixture_read_u32be(bytes + 4u);
}

static int state_local_read_file(const char *path, size_t maximum,
                                 uint8_t **out_bytes, size_t *out_size) {
    *out_bytes = NULL;
    *out_size = 0u;
    FILE *file = gn_portable_fopen(path, "rb");
    if (file == NULL || fseek(file, 0, SEEK_END) != 0) {
        if (file != NULL) fclose(file);
        return 0;
    }
    const long length = ftell(file);
    if (length <= 0 || (uintmax_t)length > (uintmax_t)maximum ||
        fseek(file, 0, SEEK_SET) != 0) {
        fclose(file);
        return 0;
    }
    uint8_t *bytes = (uint8_t *)malloc((size_t)length);
    if (bytes == NULL || fread(bytes, 1u, (size_t)length, file) !=
                             (size_t)length) {
        if (bytes != NULL) {
            memset(bytes, 0xa5, (size_t)length);
            free(bytes);
        }
        fclose(file);
        return 0;
    }
    const int closed = fclose(file) == 0;
    if (!closed) {
        memset(bytes, 0xa5, (size_t)length);
        free(bytes);
        return 0;
    }
    *out_bytes = bytes;
    *out_size = (size_t)length;
    return 1;
}

static int state_local_load_bundle(const char *path, gn_instance **out_instance) {
    *out_instance = NULL;
    uint8_t *bytes = NULL;
    size_t size = 0u;
    int ok = state_local_read_file(path, STATE_LOCAL_MAX_BUNDLE_BYTES,
                                   &bytes, &size) && size >= 16u &&
             memcmp(bytes, "GNMV", 4u) == 0 &&
             state_fixture_read_u32be(bytes + 4u) ==
                 GN_MVS_MANIFEST_VERSION_ZOOM &&
             state_fixture_read_u32be(bytes + 8u) == GN_MVS_PROFILE_MSX;
    gn_mvs_manifest_v3 manifest;
    memset(&manifest, 0, sizeof(manifest));
    const uint32_t count = ok ? state_fixture_read_u32be(bytes + 12u) : 0u;
    if (ok && (count != GN_MVS_V3_MAX_REGIONS - 1u &&
               count != GN_MVS_V3_MAX_REGIONS)) ok = 0;
    if (ok) {
        manifest.version = GN_MVS_MANIFEST_VERSION_ZOOM;
        manifest.profile = GN_MVS_PROFILE_MSX;
        manifest.region_count = count;
        size_t cursor = 16u;
        for (size_t index = 0u; ok && index < count; ++index) {
            if (cursor > size || size - cursor < 12u) {
                ok = 0;
                break;
            }
            const uint32_t role = state_fixture_read_u32be(bytes + cursor);
            const uint64_t region_size = state_local_read_u64be(bytes + cursor + 4u);
            cursor += 12u;
            if (role == 0u || role > GN_MVS_V3_MAX_REGIONS ||
                region_size == 0u || region_size > SIZE_MAX ||
                region_size > size - cursor) {
                ok = 0;
                break;
            }
            manifest.regions[index] = (gn_mvs_region){
                (gn_mvs_region_role)role, bytes + cursor,
                (size_t)region_size, (size_t)region_size,
                GN_MVS_LAYOUT_LINEAR
            };
            cursor += (size_t)region_size;
        }
        if (cursor != size) ok = 0;
    }
    gn_instance *instance = NULL;
    if (ok) ok = gn_create(&instance) == GN_STATUS_OK && instance != NULL &&
                  gn_load_mvs_v3(instance, &manifest) == GN_STATUS_OK;
    if (bytes != NULL) {
        memset(bytes, 0xa5, size);
        free(bytes);
    }
    if (!ok) {
        gn_destroy(instance);
        return 0;
    }
    *out_instance = instance;
    return 1;
}

static int state_local_read_schedule(const char *path,
                                     state_local_schedule *out_schedule) {
    memset(out_schedule, 0, sizeof(*out_schedule));
    uint8_t *bytes = NULL;
    size_t size = 0u;
    if (!state_local_read_file(path,
            24u + (size_t)STATE_LOCAL_MAX_ACTIVE_FRAMES * 4u,
            &bytes, &size) || size < 24u || memcmp(bytes, "GNSL", 4u) != 0 ||
        state_fixture_read_u32be(bytes + 4u) != 1u) {
        free(bytes);
        return 0;
    }
    const uint32_t capture = state_fixture_read_u32be(bytes + 8u);
    const uint32_t future = state_fixture_read_u32be(bytes + 12u);
    const uint32_t flags = state_fixture_read_u32be(bytes + 16u);
    const uint32_t declared_frames = state_fixture_read_u32be(bytes + 20u);
    const size_t frame_count = (size - 24u) / 4u;
    if (flags > 1u || declared_frames != frame_count ||
        (size - 24u) % 4u != 0u || frame_count == 0u ||
        frame_count > STATE_LOCAL_MAX_ACTIVE_FRAMES ||
        capture >= frame_count || future == 0u ||
        future > STATE_LOCAL_MAX_FUTURE_FRAMES ||
        frame_count != (size_t)capture + 1u + (size_t)future) {
        memset(bytes, 0xa5, size);
        free(bytes);
        return 0;
    }
    uint32_t *inputs = (uint32_t *)calloc(frame_count, sizeof(*inputs));
    int ok = inputs != NULL;
    for (size_t index = 0u; ok && index < frame_count; ++index) {
        inputs[index] = state_fixture_read_u32be(bytes + 24u + index * 4u);
        if ((inputs[index] & ~UINT32_C(0x3ff)) != 0u) ok = 0;
    }
    memset(bytes, 0xa5, size);
    free(bytes);
    if (!ok) {
        free(inputs);
        return 0;
    }
    out_schedule->capture_frame = capture;
    out_schedule->future_frames = future;
    out_schedule->frame_count = (uint32_t)frame_count;
    out_schedule->flags = flags;
    out_schedule->inputs = inputs;
    return 1;
}

static int state_local_boot_to_player_start(gn_instance *instance) {
    /* Match the accepted native-scene runner: first run bounded cycle chunks
     * until the BIOS attract/start checkpoint, then apply coin@1,start@600.
     * Starting that script immediately after import skips part of the scene
     * prelude and can leave the BIOS protocol in a different state. */
    int attract_start_reached = 0;
    for (uint32_t chunk = 0u; chunk < STATE_LOCAL_MAX_ATTRACT_CHUNKS; ++chunk) {
        gn_run_result result;
        if (gn_run_mvs(instance, GN_MAX_CYCLE_BUDGET, &result) != GN_STATUS_OK ||
            result.reason == GN_RUN_ERROR || result.reason == GN_RUN_FAULT ||
            result.reason == GN_RUN_STOPPED) return 0;
        gn_mvs_attract_verdict verdict;
        memset(&verdict, 0, sizeof(verdict));
        if (gn_private_mvs_attract_verdict(instance, &verdict) != GN_STATUS_OK)
            return 0;
        if (verdict.accepted != 0u) {
            attract_start_reached = 1;
            break;
        }
    }
    if (attract_start_reached == 0) return 0;
    for (uint32_t frame = 1u; frame <= STATE_LOCAL_MAX_BOOT_FRAMES; ++frame) {
        uint32_t inputs = 0u;
        if (frame <= 8u) inputs |= GN_MVS_INPUT_COIN1;
        if (frame >= 600u) inputs |= GN_MVS_INPUT_P1_START;
        if (gn_set_mvs_inputs(instance, inputs) != GN_STATUS_OK) return 0;
        gn_run_result result;
        if (gn_mvs_run_frame_budget(instance, &result) != GN_STATUS_OK ||
            result.reason == GN_RUN_ERROR || result.reason == GN_RUN_FAULT ||
            result.reason == GN_RUN_STOPPED) return 0;
        gn_mvs_progress_observation progress;
        memset(&progress, 0, sizeof(progress));
        if (gn_observe_mvs_progress(instance, &progress,
                                    sizeof(progress)) != GN_STATUS_OK) return 0;
        if (progress.player_start_with_p1_indication != 0u) return 1;
    }
    return 0;
}

static int state_local_public_fixture_start(gn_instance *instance) {
    gn_run_result raw;
    memset(&raw, 0, sizeof(raw));
    return gn_run(instance, 1u, &raw) == GN_STATUS_OK &&
           raw.overshoot_cycles > 0u &&
           raw.elapsed_cycles == raw.requested_cycles + raw.overshoot_cycles;
}

static int state_local_advance(gn_instance *instance, uint32_t input,
                               state_local_observation *out) {
    memset(out, 0, sizeof(*out));
    const gn_mvs_frame_request_v1 request = {
        GN_MVS_FRAME_REQUEST_V1_VERSION, input, GN_PIXEL_XRGB8888,
        STATE_FIXTURE_WIDTH, STATE_FIXTURE_HEIGHT,
        STATE_FIXTURE_WIDTH * sizeof(uint32_t), out->pixels,
        sizeof(out->pixels), out->audio, GN_MVS_AUDIO_CAPACITY_FRAMES_V1
    };
    if (gn_mvs_advance_frame_v1(instance, &request, sizeof(request),
                                &out->result, sizeof(out->result)) !=
            GN_STATUS_OK ||
        out->result.video_pixels_produced !=
            STATE_FIXTURE_WIDTH * STATE_FIXTURE_HEIGHT ||
        out->result.audio_frames_generated !=
            out->result.audio_frames_delivered ||
        out->result.audio_frames_discarded != 0u ||
        out->result.audio_frames_delivered >
            GN_MVS_AUDIO_CAPACITY_FRAMES_V1 ||
        gn_observe_mvs_progress(instance, &out->progress,
                                sizeof(out->progress)) != GN_STATUS_OK ||
        gn_private_mvs_video_activity(instance, &out->video) !=
            GN_STATUS_OK ||
        gn_observe_mvs_bus_fault(instance, &out->bus,
                                 sizeof(out->bus)) != GN_STATUS_OK ||
        gn_test_mvs_sound_state_read(instance, &out->sound) !=
            GN_STATUS_OK ||
        gn_test_mvs_machine_state_read(instance, &out->machine) !=
            GN_STATUS_OK) return 0;
    out->audio_frames = out->result.audio_frames_delivered;
    for (size_t index = 0u; index < sizeof(out->pixels); ++index)
        out->nonzero_video_bytes += out->pixels[index] != 0u;
    for (size_t index = 0u; index < out->audio_frames * 2u; ++index)
        out->nonzero_audio_samples += out->audio[index] != 0;
    return 1;
}

static int state_local_write_observation(FILE *trace, uint32_t input,
                                         const state_local_observation *o) {
    const gn_mvs_frame_result_v1 *r = &o->result;
    const gn_mvs_progress_observation *p = &o->progress;
    const gn_test_mvs_machine_state *m = &o->machine;
    const gn_test_mvs_sound_state *s = &o->sound;
    int ok = write_u32be(trace, input) && write_u32be(trace, r->version) &&
        write_u64be(trace, r->requested_cycles) &&
        write_u64be(trace, r->elapsed_cycles) &&
        write_u64be(trace, r->instructions) &&
        write_u64be(trace, r->frame_time_numerator) &&
        write_u64be(trace, r->frame_time_denominator) &&
        write_u32be(trace, r->machine_clock_hz_numerator) &&
        write_u32be(trace, r->machine_clock_hz_denominator) &&
        write_u32be(trace, (uint32_t)r->reason) &&
        write_u32be(trace, (uint32_t)r->audio_format) &&
        write_u32be(trace, r->audio_sample_rate) &&
        write_u32be(trace, r->audio_channels) &&
        write_u64be(trace, (uint64_t)r->audio_frames_generated) &&
        write_u64be(trace, (uint64_t)r->audio_frames_discarded) &&
        write_u64be(trace, (uint64_t)r->audio_frames_delivered) &&
        write_u64be(trace, (uint64_t)r->video_pixels_produced) &&
        write_u32be(trace, p->version) &&
        write_u8(trace, p->attract_start_reached) &&
        write_u8(trace, p->user_request) &&
        write_u8(trace, p->player_start_entered) &&
        write_u8(trace, p->player_start_with_p1_indication) &&
        write_u32be(trace, m->frame_count) &&
        write_u32be(trace, m->frame_cycle) &&
        write_u64be(trace, m->frame_cycle_carry) &&
        write_u32be(trace, m->watchdog_pet_count) &&
        write_u32be(trace, m->watchdog_reset_count) &&
        write_u64be(trace, m->watchdog_remaining_cycles) &&
        write_u8(trace, m->irq_pending_mask) &&
        write_u8(trace, m->animation_counter) &&
        write_u8(trace, m->animation_frame_counter) &&
        write_u8(trace, m->animation_speed) &&
        write_u8(trace, m->animation_disabled) &&
        write_u64be(trace, s->filter_history_digest) &&
        write_u16be(trace, s->pcm_output_phase) &&
        write_u16be(trace, s->filter_history_next) &&
        write_u8(trace, s->main_clock_remainder) &&
        write_u8(trace, s->ym_irq) &&
        write_bytes(trace, s->banks, sizeof(s->banks)) &&
        write_u8(trace, s->failed) &&
        write_u32be(trace, o->video.nonzero_vram_words) &&
        write_u32be(trace, o->video.nonzero_fixed_tilemap_words) &&
        write_u32be(trace, o->video.nonzero_sprite_words) &&
        write_u32be(trace, o->video.nonzero_palette_entries) &&
        write_u32be(trace, o->video.visible_sprites) &&
        write_u32be(trace, o->video.visible_nonfull_y_zoom_samples) &&
        write_u32be(trace, o->video.frame_count) &&
        write_u32be(trace, o->video.frame_cycle) &&
        write_u64be(trace, o->video.frame_cycle_carry) &&
        write_u8(trace, o->video.auto_animation_counter) &&
        write_u8(trace, o->video.backdrop_palette_nonzero) &&
        write_u16be(trace, o->video.video_ram_offset) &&
        write_u16be(trace, o->video.video_ram_modulo) &&
        write_u8(trace, o->video.palette_bank_selected) &&
        write_u8(trace, o->video.screen_shadow) &&
        write_u8(trace, o->video.video_auto_animation_speed) &&
        write_u8(trace, o->video.video_auto_animation_disabled) &&
        write_u8(trace, o->video.display_position_interrupt_control) &&
        write_u8(trace, o->bus.valid) && write_u32be(trace, o->bus.address) &&
        write_u8(trace, (uint8_t)o->bus.access) &&
        write_u8(trace, o->bus.width) &&
        write_u32be(trace, o->bus.mame_unmapped_write_count) &&
        write_u32be(trace, o->bus.mame_watchdog_pet_count) &&
        write_u32be(trace, o->bus.mame_watchdog_reset_count) &&
        write_bytes(trace, o->pixels, sizeof(o->pixels));
    for (size_t index = 0u; ok && index < o->audio_frames * 2u; ++index)
        ok = write_u16be(trace, (uint16_t)o->audio[index]);
    return ok;
}

static int state_local_trace_future(gn_instance *instance,
                                   const state_local_schedule *schedule,
                                   const char *trace_path,
                                   uint64_t *out_frames,
                                   uint64_t *out_elapsed,
                                   uint64_t *out_nonzero_audio,
                                   uint64_t *out_nonzero_video) {
    *out_frames = 0u;
    *out_elapsed = 0u;
    *out_nonzero_audio = 0u;
    *out_nonzero_video = 0u;
    FILE *trace = gn_portable_fopen(trace_path, "wb");
    if (trace == NULL || !write_trace_header(trace, "GNSL",
                                             schedule->future_frames)) {
        if (trace != NULL) fclose(trace);
        return 0;
    }
    int ok = 1;
    for (uint32_t index = schedule->capture_frame + 1u;
         ok && index < schedule->frame_count; ++index) {
        state_local_observation observation;
        if (!state_local_advance(instance, schedule->inputs[index],
                                 &observation) || observation.bus.valid != 0u ||
            !state_local_write_observation(trace, schedule->inputs[index],
                                           &observation) ||
            UINT64_MAX - *out_elapsed < observation.result.elapsed_cycles) {
            ok = 0;
            break;
        }
        ++*out_frames;
        *out_elapsed += observation.result.elapsed_cycles;
        *out_nonzero_audio += observation.nonzero_audio_samples;
        *out_nonzero_video += observation.nonzero_video_bytes;
    }
    if (fclose(trace) != 0) ok = 0;
    return ok && *out_frames == schedule->future_frames;
}

static int state_frontend_read_inputs(const char *path, uint32_t inputs[STATE_FRONTEND_WINDOW_FRAMES],
                                      uint64_t cycles[STATE_FRONTEND_WINDOW_FRAMES]) {
    uint8_t *bytes = NULL;
    size_t size = 0u;
    if (!state_local_read_file(path, 12u + STATE_FRONTEND_WINDOW_FRAMES * 12u,
                               &bytes, &size) || size < 12u ||
        memcmp(bytes, "GNFI", 4u) != 0 ||
        state_fixture_read_u32be(bytes + 4u) != 1u ||
        state_fixture_read_u32be(bytes + 8u) != STATE_FRONTEND_WINDOW_FRAMES ||
        size != 12u + STATE_FRONTEND_WINDOW_FRAMES * 12u) {
        if (bytes != NULL) { memset(bytes, 0xa5, size); free(bytes); }
        return 0;
    }
    uint64_t prior_cycles = 0u;
    int ok = 1;
    for (size_t index = 0u; index < STATE_FRONTEND_WINDOW_FRAMES; ++index) {
        const size_t cursor = 12u + index * 12u;
        inputs[index] = state_fixture_read_u32be(bytes + cursor);
        cycles[index] = state_local_read_u64be(bytes + cursor + 4u);
        if ((inputs[index] & ~UINT32_C(0x3ff)) != 0u ||
            cycles[index] <= prior_cycles) {
            ok = 0;
            break;
        }
        prior_cycles = cycles[index];
    }
    memset(bytes, 0xa5, size);
    free(bytes);
    return ok;
}

static int state_frontend_write_trace(FILE *trace,
                                      const state_local_observation *observation,
                                      uint32_t input) {
    const size_t video_bytes = sizeof(observation->pixels);
    const size_t audio_bytes = observation->audio_frames * 2u * sizeof(int16_t);
    return write_u32be(trace, input) &&
           write_u64be(trace, observation->result.elapsed_cycles) &&
           write_u32be(trace, (uint32_t)observation->audio_frames) &&
           write_u32be(trace, (uint32_t)video_bytes) &&
           write_u32be(trace, (uint32_t)audio_bytes) &&
           write_bytes(trace, observation->pixels, video_bytes) &&
           write_bytes(trace, observation->audio, audio_bytes);
}

static int state_frontend_import(const char *bundle_path, const char *state_path,
                                 const char *input_path, const char *trace_path,
                                 uint64_t *out_cycles, uint64_t *out_nonzero_audio,
                                 uint64_t *out_nonzero_video, uint64_t *out_payload) {
    uint32_t inputs[STATE_FRONTEND_WINDOW_FRAMES] = {0u};
    uint64_t expected_cycles[STATE_FRONTEND_WINDOW_FRAMES] = {0u};
    gn_instance *instance = NULL;
    uint8_t *state = NULL, *roundtrip = NULL;
    size_t state_size = 0u, capacity = 0u, captured = 0u;
    int ok = state_frontend_read_inputs(input_path, inputs, expected_cycles) &&
             state_local_load_bundle(bundle_path, &instance) &&
             state_local_read_file(state_path, STATE_PROCESS_MAX_PAYLOAD,
                                   &state, &state_size) &&
             state_size >= 72u && state_size <= STATE_PROCESS_MAX_PAYLOAD &&
             gn_state_capacity_v1(instance, &capacity) == GN_STATUS_OK &&
             capacity == state_size;
    ok = process_check("sdk.state.frontend.independent-process-loads-matching-content-and-payload",
                       ok) && ok;
    gn_state_detail_v1 detail;
    memset(&detail, 0, sizeof(detail));
    detail.size = (uint32_t)sizeof(detail);
    if (ok) {
        const gn_status restored = gn_state_restore_v1(
            instance, state, state_size, &detail, sizeof(detail));
        ok = process_check("sdk.state.frontend.accepts-actual-frontend-mem-payload",
                           restored == GN_STATUS_OK);
    }
    if (ok) {
        roundtrip = (uint8_t *)malloc(state_size);
        ok = roundtrip != NULL &&
             gn_state_capture_v1(instance, roundtrip, state_size, &captured,
                                 NULL, 0u) == GN_STATUS_OK &&
             captured == state_size && memcmp(roundtrip, state, state_size) == 0;
        ok = process_check("sdk.state.frontend-restored-payload-is-exactly-capturable",
                           ok) && ok;
    }
    FILE *trace = NULL;
    if (ok) {
        const size_t maximum_trace = 12u + STATE_FRONTEND_WINDOW_FRAMES *
            (24u + STATE_FIXTURE_WIDTH * STATE_FIXTURE_HEIGHT * 4u +
             GN_MVS_AUDIO_CAPACITY_FRAMES_V1 * 2u * sizeof(int16_t));
        ok = maximum_trace <= STATE_FRONTEND_MAX_TRACE_BYTES;
        if (ok) trace = gn_portable_fopen(trace_path, "wb");
        ok = ok && trace != NULL && write_trace_header(
            trace, "GNFO", STATE_FRONTEND_WINDOW_FRAMES);
        ok = process_check("sdk.state.frontend.trace-output-is-bounded", ok) && ok;
    }
    uint64_t cycle_sum = 0u;
    for (size_t index = 0u; ok && index < STATE_FRONTEND_WINDOW_FRAMES; ++index) {
        state_local_observation observation;
        ok = state_local_advance(instance, inputs[index], &observation) &&
             observation.bus.valid == 0u &&
             UINT64_MAX - cycle_sum >= observation.result.elapsed_cycles;
        if (ok) cycle_sum += observation.result.elapsed_cycles;
        const int cycles_match = ok && cycle_sum == expected_cycles[index];
        ok = process_check("sdk.state.frontend-observed-input-order-and-cycle-boundary-match",
                           cycles_match) && ok;
        if (ok) ok = state_frontend_write_trace(trace, &observation, inputs[index]);
        if (ok) {
            *out_nonzero_audio += observation.nonzero_audio_samples;
            *out_nonzero_video += observation.nonzero_video_bytes;
        }
    }
    if (trace != NULL && fclose(trace) != 0) ok = 0;
    ok = process_check("sdk.state.frontend-four-fresh-native-observations-complete",
                       ok && cycle_sum == expected_cycles[STATE_FRONTEND_WINDOW_FRAMES - 1u]) && ok;
    *out_cycles = cycle_sum;
    *out_payload = state_size;
    if (state != NULL) { memset(state, 0xa5, state_size); free(state); }
    if (roundtrip != NULL) { memset(roundtrip, 0xa5, state_size); free(roundtrip); }
    gn_destroy(instance);
    return ok;
}

static void print_frontend_result(int passed, uint64_t cycles,
                                  uint64_t nonzero_audio,
                                  uint64_t nonzero_video,
                                  uint64_t payload_bytes) {
    (void)printf(
        "STATE_FRONTEND_RESULT {\"schema_version\":1,\"mode\":\"frontend-import\","
        "\"outcome\":\"%s\",\"assertions\":%" PRIu64
        ",\"frames\":%u,\"elapsed_cycles\":%" PRIu64
        ",\"nonzero_audio_samples\":%" PRIu64
        ",\"nonzero_video_bytes\":%" PRIu64
        ",\"state_bytes\":%" PRIu64
        ",\"source_revision\":\"%s\",\"source_content_sha256\":\"%s\","
        "\"configuration\":\"%s\",\"compiler\":\"%s %s\","
        "\"sanitizer\":\"%s\"}\n",
        passed ? "pass" : "fail", process_assertions,
        STATE_FRONTEND_WINDOW_FRAMES, cycles, nonzero_audio, nonzero_video,
        payload_bytes, GLUEYNEO_SOURCE_REVISION, GLUEYNEO_SOURCE_CONTENT_ID,
        GLUEYNEO_CONFIGURATION, GLUEYNEO_COMPILER_ID,
        GLUEYNEO_COMPILER_VERSION, GLUEYNEO_SANITIZER);
}

static int state_local_export(const char *bundle_path,
                              const char *schedule_path,
                              const char *state_path,
                              const char *witness_path,
                              const char *sram_path,
                              uint64_t *out_payload,
                              uint64_t *out_frames,
                              uint64_t *out_elapsed,
                              uint64_t *out_audio,
                              uint64_t *out_video) {
    state_local_schedule schedule;
    memset(&schedule, 0, sizeof(schedule));
    gn_instance *instance = NULL;
    uint8_t *state = NULL;
    size_t capacity = 0u, state_size = 0u;
    int ok = state_local_read_schedule(schedule_path, &schedule) &&
             state_local_load_bundle(bundle_path, &instance) &&
             (schedule.flags == 1u
                  ? state_local_public_fixture_start(instance)
                  : state_local_boot_to_player_start(instance));
    ok = process_check("sdk.state.local.selected-media-load-and-start", ok) && ok;
    uintptr_t save_ram = ok ? gn_test_mvs_save_ram_address(instance) : 0u;
    ok = process_check("sdk.state.local.save-ram-owner-present",
                       save_ram != (uintptr_t)0) && ok;
    state_local_observation boundary;
    memset(&boundary, 0, sizeof(boundary));
    for (uint32_t index = 0u; ok && index <= schedule.capture_frame; ++index) {
        ok = state_local_advance(instance, schedule.inputs[index], &boundary);
        if (index == schedule.capture_frame) break;
    }
    const uint64_t timer_writes = boundary.sound.timer_register_writes[0] +
        boundary.sound.timer_register_writes[1] +
        boundary.sound.timer_register_writes[2];
    gn_mvs_sound_observation sound;
    memset(&sound, 0, sizeof(sound));
    ok = ok && gn_private_mvs_sound_observe(instance, &sound) == GN_STATUS_OK;
    ok = process_check("sdk.state.local.capture-boundary-has-full-raw-frame",
                       ok && boundary.result.video_pixels_produced ==
                           STATE_FIXTURE_WIDTH * STATE_FIXTURE_HEIGHT &&
                       boundary.nonzero_video_bytes > 0u) && ok;
    ok = process_check("sdk.state.local.capture-boundary-has-nonzero-pcm",
                       ok && boundary.audio_frames > 0u &&
                           boundary.nonzero_audio_samples > 0u) && ok;
    ok = process_check("sdk.state.local.capture-boundary-has-filter-phase",
                       ok && boundary.sound.native_samples > 0u &&
                           boundary.sound.pcm_output_phase != 0u &&
                           boundary.sound.filter_history_next != 0u &&
                           boundary.sound.filter_history_digest != 0u) && ok;
    if (schedule.flags == 0u) {
        ok = process_check(
            "sdk.state.local.capture-boundary-has-ym-timer-activity",
            ok && timer_writes > 0u &&
                (sound.chip.timer_programs > 0u ||
                 sound.chip.timer_expirations > 0u)) && ok;
    }
    ok = process_check("sdk.state.local.capture-boundary-has-frame-and-time",
                       ok && boundary.machine.frame_count > 0u &&
                           boundary.result.elapsed_cycles > 0u) && ok;
    ok = ok && gn_state_capacity_v1(instance, &capacity) == GN_STATUS_OK &&
         capacity > 0u && capacity <= STATE_PROCESS_MAX_PAYLOAD;
    if (ok) {
        state = (uint8_t *)malloc(capacity);
        ok = state != NULL && gn_state_capture_v1(instance, state, capacity,
                                                   &state_size, NULL, 0u) ==
                                  GN_STATUS_OK && state_size == capacity;
    }
    ok = process_check("sdk.state.local.capture-selected-mvs-state", ok) && ok;
    if (ok) {
        ok = write_state_file(state_path, state, state_size) &&
             write_state_file(sram_path, (const uint8_t *)save_ram,
                              STATE_LOCAL_SAVE_RAM_BYTES);
    }
    ok = process_check("sdk.state.local.preserve-private-state-and-historical-sram",
                       ok) && ok;
    if (ok) {
        *out_payload = state_size;
        ok = state_local_trace_future(instance, &schedule, witness_path,
                                      out_frames, out_elapsed, out_audio,
                                      out_video);
    }
    ok = process_check("sdk.state.local.uninterrupted-witness-complete", ok) && ok;
    if (state != NULL) {
        memset(state, 0xa5, capacity);
        free(state);
    }
    free(schedule.inputs);
    gn_destroy(instance);
    return ok;
}

static int state_local_import(const char *bundle_path,
                              const char *schedule_path,
                              const char *state_path,
                              const char *sram_path,
                              const char *trace_path,
                              uint64_t *out_payload,
                              uint64_t *out_frames,
                              uint64_t *out_elapsed,
                              uint64_t *out_audio,
                              uint64_t *out_video) {
    state_local_schedule schedule;
    memset(&schedule, 0, sizeof(schedule));
    gn_instance *instance = NULL;
    uint8_t *state = NULL, *saved_sram = NULL, *before = NULL,
            *after = NULL, *invalid = NULL;
    size_t state_size = 0u, sram_size = 0u, capacity = 0u;
    int ok = state_local_read_schedule(schedule_path, &schedule) &&
             state_local_load_bundle(bundle_path, &instance) &&
             state_local_read_file(state_path, STATE_PROCESS_MAX_PAYLOAD,
                                   &state, &state_size) &&
             state_local_read_file(sram_path, STATE_LOCAL_SAVE_RAM_BYTES,
                                   &saved_sram, &sram_size) &&
             sram_size == STATE_LOCAL_SAVE_RAM_BYTES &&
             gn_state_capacity_v1(instance, &capacity) == GN_STATUS_OK &&
             capacity == state_size;
    ok = process_check("sdk.state.local.independently-load-matching-media", ok) && ok;
    uintptr_t save_ram = ok ? gn_test_mvs_save_ram_address(instance) : 0u;
    if (ok) {
        before = (uint8_t *)malloc(capacity);
        after = (uint8_t *)malloc(capacity);
        invalid = (uint8_t *)malloc(state_size);
        ok = before != NULL && after != NULL && invalid != NULL &&
             gn_state_capture_v1(instance, before, capacity, &capacity,
                                 NULL, 0u) == GN_STATUS_OK;
    }
    ok = process_check("sdk.state.local.capture-import-target-before-invalid", ok) && ok;
    gn_state_detail_v1 detail;
    memset(&detail, 0, sizeof(detail));
    detail.size = (uint32_t)sizeof(detail);
    gn_status rejected = GN_STATUS_OK;
    if (ok) {
        memcpy(invalid, state, state_size);
        invalid[0] ^= UINT8_C(0xff);
        rejected = gn_state_restore_v1(instance, invalid, state_size,
                                       &detail, sizeof(detail));
        ok = rejected != GN_STATUS_OK &&
             gn_state_capture_v1(instance, after, state_size, &capacity,
                                 NULL, 0u) == GN_STATUS_OK &&
             memcmp(before, after, state_size) == 0 &&
             gn_test_mvs_save_ram_address(instance) == save_ram;
    }
    ok = process_check("sdk.state.local.invalid-import-is-atomic", ok) && ok;
    if (ok) {
        memset((uint8_t *)save_ram, 0xa5, sram_size);
        memset(&detail, 0, sizeof(detail));
        detail.size = (uint32_t)sizeof(detail);
        const gn_status restore_status = gn_state_restore_v1(
            instance, state, state_size, &detail, sizeof(detail));
        if (restore_status != GN_STATUS_OK) {
            (void)fprintf(stderr,
                           "STATE_LOCAL_RESTORE status=%u reason=%u section=%u\n",
                           (unsigned)restore_status, (unsigned)detail.reason,
                           (unsigned)detail.section);
        }
        const int address_retained =
            gn_test_mvs_save_ram_address(instance) == save_ram;
        const int historical_sram_restored =
            memcmp((const uint8_t *)save_ram, saved_sram, sram_size) == 0;
        ok = process_check("sdk.state.local.valid-import-restores-status",
                           restore_status == GN_STATUS_OK) && ok;
        ok = process_check("sdk.state.local.valid-import-retains-sram-address",
                           address_retained) && ok;
        ok = process_check("sdk.state.local.valid-import-restores-historical-sram",
                           historical_sram_restored) && ok;
        size_t restored_size = 0u;
        const int restored_capture_ok =
            gn_state_capture_v1(instance, after, state_size, &restored_size,
                                NULL, 0u) == GN_STATUS_OK &&
            restored_size == state_size;
        ok = process_check("sdk.state.local.restored-state-roundtrip-equal",
                           restored_capture_ok &&
                               memcmp(state, after, state_size) == 0) && ok;
    }
    if (ok) {
        *out_payload = state_size;
        ok = state_local_trace_future(instance, &schedule, trace_path,
                                      out_frames, out_elapsed, out_audio,
                                      out_video);
    }
    ok = process_check("sdk.state.local.imported-future-observations-complete", ok) && ok;
    if (state != NULL) { memset(state, 0xa5, state_size); free(state); }
    if (saved_sram != NULL) { memset(saved_sram, 0xa5, sram_size); free(saved_sram); }
    if (before != NULL) { memset(before, 0xa5, capacity); free(before); }
    if (after != NULL) { memset(after, 0xa5, capacity); free(after); }
    if (invalid != NULL) { memset(invalid, 0xa5, state_size); free(invalid); }
    free(schedule.inputs);
    gn_destroy(instance);
    return ok;
}

static void print_local_result(const char *mode, int passed,
                               uint64_t payload_bytes, uint64_t frames,
                               uint64_t elapsed, uint64_t nonzero_audio,
                               uint64_t nonzero_video) {
    (void)printf(
        "STATE_LOCAL_RESULT {\"schema_version\":1,\"mode\":\"%s\","
        "\"outcome\":\"%s\",\"assertions\":%" PRIu64
        ",\"state_bytes\":%" PRIu64 ",\"future_frames\":%" PRIu64
        ",\"elapsed_cycles\":%" PRIu64
        ",\"nonzero_audio_samples\":%" PRIu64
        ",\"nonzero_video_bytes\":%" PRIu64
        ",\"source_revision\":\"%s\",\"source_content_sha256\":\"%s\","
        "\"configuration\":\"%s\",\"compiler\":\"%s %s\","
        "\"sanitizer\":\"%s\"}\n",
        mode, passed ? "pass" : "fail", process_assertions, payload_bytes,
        frames, elapsed, nonzero_audio, nonzero_video,
        GLUEYNEO_SOURCE_REVISION, GLUEYNEO_SOURCE_CONTENT_ID,
        GLUEYNEO_CONFIGURATION, GLUEYNEO_COMPILER_ID,
        GLUEYNEO_COMPILER_VERSION, GLUEYNEO_SANITIZER);
}

int main(int argc, char **argv) {
    if (argc == 6 && strcmp(argv[1], "frontend-import") == 0) {
        process_assertions = 0u;
        process_failures = 0u;
        uint64_t cycles = 0u, nonzero_audio = 0u, nonzero_video = 0u,
                 payload_bytes = 0u;
        const int ok = state_frontend_import(
            argv[2], argv[3], argv[4], argv[5], &cycles,
            &nonzero_audio, &nonzero_video, &payload_bytes);
        const int passed = process_check(
            "sdk.state.frontend-child-completes-observations", ok) &&
            process_failures == 0u;
        print_frontend_result(passed, cycles, nonzero_audio,
                              nonzero_video, payload_bytes);
        return passed ? 0 : 1;
    }
    if (argc == 7 &&
        (strcmp(argv[1], "local-export") == 0 ||
         strcmp(argv[1], "local-import") == 0)) {
        const clock_t cpu_started = clock();
        process_assertions = 0u;
        process_failures = 0u;
        uint64_t payload_bytes = 0u, frames = 0u, elapsed = 0u,
                 nonzero_audio = 0u, nonzero_video = 0u;
        const int exported = strcmp(argv[1], "local-export") == 0;
        int ok = exported
            ? state_local_export(argv[2], argv[3], argv[4], argv[5], argv[6],
                                 &payload_bytes, &frames, &elapsed, &nonzero_audio,
                                 &nonzero_video)
            : state_local_import(argv[2], argv[3], argv[4], argv[5], argv[6],
                                 &payload_bytes, &frames, &elapsed, &nonzero_audio,
                                 &nonzero_video);
        ok = process_check("sdk.state.local.child-completes-observations", ok) && ok;
        const int passed = ok && process_failures == 0u;
        (void)cpu_started;
        print_local_result(argv[1], passed, payload_bytes, frames, elapsed,
                           nonzero_audio, nonzero_video);
        return passed ? 0 : 1;
    }
    if (argc != 5 ||
        (strcmp(argv[1], "export") != 0 && strcmp(argv[1], "import") != 0) ||
        (strcmp(argv[2], "diagnostic") != 0 && strcmp(argv[2], "mvs") != 0)) {
        (void)fprintf(stderr,
                      "usage: sdk_state_process <export|import> "
                      "<diagnostic|mvs> <payload-path> <trace-path> or "
                      "frontend-import <bundle> <GNST> <inputs> <trace>\n");
        return 2;
    }
    const clock_t cpu_started = clock();
    UnityBegin("tests/sdk/state_process.c");
    SDK_CASE("sdk.state.process.fresh-process-continuation");
    process_metrics metrics;
    memset(&metrics, 0, sizeof(metrics));
    const int ok = strcmp(argv[1], "export") == 0
        ? export_process(argv[2], argv[3], argv[4], &metrics)
        : import_process(argv[2], argv[3], argv[4], &metrics);
    SDK_CHECK_TRUE("sdk.state.process.child-completes-observations", ok);
    const int failures = UnityEnd();
    sdk_test_result("sdk-state-process", failures, GLUEYNEO_SOURCE_REVISION,
                    GLUEYNEO_CONFIGURATION, GLUEYNEO_COMPILER_ID,
                    GLUEYNEO_COMPILER_VERSION);
    if (!ok || failures != 0) return 1;
    print_result(argv[1], argv[2], &metrics, cpu_started);
    return 0;
}
