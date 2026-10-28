/* SPDX-License-Identifier: MIT; deterministic original diagnostic inputs. */
#include "glueyneo/glueyneo.h"
#include "guest_fixture.h"
#include "test_support.h"

#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

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

#define MUTATION_SEED UINT64_C(0x6e656f67656f3235)
#define MUTATION_ITERATIONS 1024u
#define MUTATION_INPUT_LIMIT 4096u
#define MUTATION_OPERATIONS_LIMIT 64u
#define MUTATION_LIVE_LIMIT 4u
#define MUTATION_CYCLE_LIMIT UINT64_C(1000000)
#define MUTATION_TRACE_LIMIT 256u
#define MUTATION_INPUT_BYTES 64u
#define MUTATION_CANARY_SIZE 16u

typedef struct {
    uint8_t before[MUTATION_CANARY_SIZE];
    uint8_t rom[GUEST_FIXTURE_ROM_SIZE + 1u];
    uint8_t middle[MUTATION_CANARY_SIZE];
    uint8_t ram[GUEST_FIXTURE_RAM_INIT_SIZE + 1u];
    uint8_t after[MUTATION_CANARY_SIZE];
} guarded_sources;

typedef struct {
    gn_run_result run;
    gn_observations observations;
} public_snapshot;

typedef struct {
    gn_instance *instance;
    int loaded;
    unsigned scenario;
} sequence_owner;

static const char *selected_mode;
static const char *mutation_failure_id;
static uint8_t active_input[MUTATION_INPUT_LIMIT];
static size_t active_input_size;
static uint64_t active_seed;
static uint64_t active_iteration;
static uint64_t sdk_mutation_operations;
static uint64_t sdk_mutation_guest_cycles;
static uint64_t sdk_mutation_cases;
static uint64_t sdk_mutation_unique_inputs;
static uint64_t sdk_mutation_peak_live;
static uint64_t sdk_mutation_peak_storage;
static uint64_t sdk_mutation_peak_guest_cycles;
static uint64_t sdk_mutation_max_operations;
static size_t sdk_mutation_max_input_bytes;
static const uint8_t *replay_input;
static size_t replay_input_size;
static volatile int startup_thread_value;

void setUp(void) {}
void tearDown(void) {}

static void mutation_check_u64(const char *id, uint64_t expected,
                               uint64_t observed) {
    ++sdk_assertions;
    (void)printf("# ASSERT %s expected=%" PRIu64 " observed=%" PRIu64 "\n",
                 id, expected, observed);
    if (expected != observed && mutation_failure_id == NULL) {
        mutation_failure_id = id;
    }
}

static void mutation_check_status(const char *id, gn_status expected,
                                  gn_status observed) {
    mutation_check_u64(id, (uint64_t)expected, (uint64_t)observed);
}

static void mutation_check_true(const char *id, int observed) {
    mutation_check_u64(id, UINT64_C(1), observed != 0 ? UINT64_C(1) : UINT64_C(0));
}

static uint64_t next_random(uint64_t *state) {
    uint64_t value = *state;
    value ^= value << 13;
    value ^= value >> 7;
    value ^= value << 17;
    *state = value;
    return value;
}

static void fill_input(uint8_t input[MUTATION_INPUT_BYTES], uint64_t *state) {
    for (size_t index = 0u; index < MUTATION_INPUT_BYTES; ++index) {
        input[index] = (uint8_t)next_random(state);
    }
}

static uint64_t input_hash(const uint8_t *input, size_t length) {
    uint64_t hash = UINT64_C(14695981039346656037);
    for (size_t index = 0u; index < length; ++index) {
        hash ^= input[index];
        hash *= UINT64_C(1099511628211);
    }
    return hash;
}

static void activate_input(const uint8_t *input, size_t length,
                           uint64_t seed, uint64_t iteration) {
    active_input_size = length;
    if (length > 0u) memcpy(active_input, input, length);
    active_seed = seed;
    active_iteration = iteration;
    mutation_failure_id = NULL;
}

static void print_failure(void) {
    if (mutation_failure_id == NULL) return;
    (void)printf("SDK_MUTATION_FAILURE id=%s seed=%" PRIu64
                 " iteration=%" PRIu64 " input_hex=",
                 mutation_failure_id, active_seed, active_iteration);
    for (size_t index = 0u; index < active_input_size; ++index) {
        (void)printf("%02x", active_input[index]);
    }
    (void)printf("\n");
}

static void fill_guard(guarded_sources *sources, uint8_t value) {
    memset(sources, value, sizeof(*sources));
}

static void make_guarded_sources(guarded_sources *sources,
                                 guest_fixture_scenario scenario) {
    guest_fixture_image fixture;
    fill_guard(sources, UINT8_C(0xc3));
    guest_fixture_build(&fixture, scenario);
    memcpy(sources->rom, fixture.rom, sizeof(fixture.rom));
    sources->rom[GUEST_FIXTURE_ROM_SIZE] = UINT8_C(0x5a);
    memcpy(sources->ram, fixture.ram_seed, sizeof(fixture.ram_seed));
    sources->ram[GUEST_FIXTURE_RAM_INIT_SIZE] = UINT8_C(0xa5);
}

static void make_guarded_manifest(gn_manifest *manifest,
                                  const guarded_sources *sources) {
    memset(manifest, 0, sizeof(*manifest));
    manifest->version = GN_MANIFEST_VERSION;
    manifest->profile = GN_PROFILE_DIAGNOSTIC;
    manifest->region_count = GN_MAX_REGIONS;
    manifest->regions[0] = (gn_region){
        0u, GUEST_FIXTURE_ROM_SIZE, sources->rom,
        GUEST_FIXTURE_ROM_SIZE, GN_REGION_ROM
    };
    manifest->regions[1] = (gn_region){
        UINT32_C(0x1000), UINT32_C(4096), sources->ram,
        GUEST_FIXTURE_RAM_INIT_SIZE, GN_REGION_RAM
    };
}

static int guards_unchanged(const guarded_sources *sources) {
    for (size_t index = 0u; index < MUTATION_CANARY_SIZE; ++index) {
        if (sources->before[index] != UINT8_C(0xc3) ||
            sources->middle[index] != UINT8_C(0xc3) ||
            sources->after[index] != UINT8_C(0xc3)) {
            return 0;
        }
    }
    return sources->rom[GUEST_FIXTURE_ROM_SIZE] == UINT8_C(0x5a) &&
           sources->ram[GUEST_FIXTURE_RAM_INIT_SIZE] == UINT8_C(0xa5);
}

static void check_snapshot(const char *prefix, gn_instance *instance,
                           public_snapshot *snapshot) {
    memset(snapshot, 0, sizeof(*snapshot));
    mutation_check_status("sdk.mutation.snapshot.observe", GN_STATUS_OK,
                          gn_observe(instance, &snapshot->observations));
    mutation_check_status("sdk.mutation.snapshot.zero-run", GN_STATUS_OK,
                          gn_run(instance, 0u, &snapshot->run));
    (void)prefix;
}

static void compare_snapshots(const char *prefix,
                              const public_snapshot *expected,
                              const public_snapshot *observed) {
    (void)prefix;
    mutation_check_u64("sdk.mutation.snapshot.pc",
                       expected->run.boundary_pc, observed->run.boundary_pc);
    mutation_check_u64("sdk.mutation.snapshot.reason",
                       (uint64_t)expected->run.reason,
                       (uint64_t)observed->run.reason);
    mutation_check_u64("sdk.mutation.snapshot.arithmetic",
                       expected->observations.arithmetic_result,
                       observed->observations.arithmetic_result);
    mutation_check_u64("sdk.mutation.snapshot.initialized",
                       expected->observations.initialized_result,
                       observed->observations.initialized_result);
    mutation_check_u64("sdk.mutation.snapshot.bss",
                       expected->observations.bss_result,
                       observed->observations.bss_result);
    mutation_check_u64("sdk.mutation.snapshot.ready",
                       expected->observations.ready,
                       observed->observations.ready);
}

static void check_canaries(const guarded_sources *sources) {
    mutation_check_true("sdk.mutation.media.canaries", guards_unchanged(sources));
}

static void execute_wrap_sign_regressions(void) {
    static const struct {
        uint8_t immediate;
        uint32_t expected;
        const char *id;
    } vectors[] = {
        {UINT8_C(0x7f), UINT32_C(0x00000082), "integer-moveq-7f"},
        {UINT8_C(0x80), UINT32_C(0xffffff83), "integer-moveq-80"},
        {UINT8_C(0xff), UINT32_C(0x00000002), "integer-moveq-ff"}
    };

    SDK_CASE("sdk.mutation.integer-wrap-sign-regressions");
    gn_instance *instance = NULL;
    mutation_check_status("sdk.mutation.integer.create", GN_STATUS_OK,
                          gn_create(&instance));
    if (instance == NULL) return;
    for (size_t index = 0u; index < sizeof(vectors) / sizeof(vectors[0]); ++index) {
        guest_fixture_image fixture;
        guest_fixture_build(&fixture, GUEST_FIXTURE_SCENARIO_A);
        fixture.rom[0x101u] = vectors[index].immediate;
        gn_manifest manifest;
        memset(&manifest, 0, sizeof(manifest));
        manifest.version = GN_MANIFEST_VERSION;
        manifest.profile = GN_PROFILE_DIAGNOSTIC;
        manifest.region_count = GN_MAX_REGIONS;
        manifest.regions[0] = (gn_region){
            0u, GUEST_FIXTURE_ROM_SIZE, fixture.rom,
            sizeof(fixture.rom), GN_REGION_ROM
        };
        manifest.regions[1] = (gn_region){
            UINT32_C(0x1000), UINT32_C(4096), fixture.ram_seed,
            sizeof(fixture.ram_seed), GN_REGION_RAM
        };
        mutation_check_status("sdk.mutation.integer.load", GN_STATUS_OK,
                              gn_load(instance, &manifest));
        gn_run_result run;
        gn_observations observations;
        memset(&run, 0, sizeof(run));
        memset(&observations, 0, sizeof(observations));
        mutation_check_status("sdk.mutation.integer.run", GN_STATUS_OK,
                              gn_run(instance, 172u, &run));
        sdk_mutation_guest_cycles += UINT64_C(172);
        mutation_check_u64("sdk.mutation.integer.stop", GN_RUN_STOPPED,
                           (uint64_t)run.reason);
        mutation_check_status("sdk.mutation.integer.observe", GN_STATUS_OK,
                              gn_observe(instance, &observations));
        mutation_check_u64(vectors[index].id, vectors[index].expected,
                           observations.arithmetic_result);
        if (mutation_failure_id != NULL) break;
    }
    if (mutation_failure_id == NULL) {
        guest_fixture_image fixture;
        guest_fixture_build(&fixture, GUEST_FIXTURE_SCENARIO_A);
        fixture.rom[0x100u] = UINT8_C(0x70);
        fixture.rom[0x101u] = UINT8_C(0xff);
        fixture.rom[0x102u] = UINT8_C(0x52);
        fixture.rom[0x103u] = UINT8_C(0x80);
        gn_manifest manifest;
        memset(&manifest, 0, sizeof(manifest));
        manifest.version = GN_MANIFEST_VERSION;
        manifest.profile = GN_PROFILE_DIAGNOSTIC;
        manifest.region_count = GN_MAX_REGIONS;
        manifest.regions[0] = (gn_region){
            0u, GUEST_FIXTURE_ROM_SIZE, fixture.rom,
            sizeof(fixture.rom), GN_REGION_ROM
        };
        manifest.regions[1] = (gn_region){
            UINT32_C(0x1000), UINT32_C(4096), fixture.ram_seed,
            sizeof(fixture.ram_seed), GN_REGION_RAM
        };
        mutation_check_status("sdk.mutation.integer.load-wrap", GN_STATUS_OK,
                              gn_load(instance, &manifest));
        gn_run_result run;
        gn_observations observations;
        memset(&run, 0, sizeof(run));
        memset(&observations, 0, sizeof(observations));
        mutation_check_status("sdk.mutation.integer.run-wrap", GN_STATUS_OK,
                              gn_run(instance, 172u, &run));
        sdk_mutation_guest_cycles += UINT64_C(172);
        mutation_check_status("sdk.mutation.integer.observe-wrap", GN_STATUS_OK,
                              gn_observe(instance, &observations));
        mutation_check_u64("integer-addq-unsigned-wrap", 0u,
                           observations.arithmetic_result);
        mutation_check_u64("sdk.mutation.integer.stop-wrap", GN_RUN_STOPPED,
                           (uint64_t)run.reason);
    }
    gn_destroy(instance);
}

static void apply_media_mutation(unsigned kind, gn_manifest *manifest,
                                 guarded_sources *sources) {
    switch (kind) {
    case 0u:
        sources->rom[0x101u] = (uint8_t)(sources->rom[0x101u] ^ UINT8_C(0x5a));
        break;
    case 1u:
        manifest->version += 1u;
        break;
    case 2u:
        manifest->profile += 1u;
        break;
    case 3u:
        manifest->region_count = 1u;
        break;
    case 4u:
        manifest->regions[0].guest_base = 2u;
        break;
    case 5u:
        manifest->regions[0].source_size -= 1u;
        break;
    case 6u:
        manifest->regions[0].source_size += 1u;
        break;
    case 7u:
        manifest->regions[1].guest_base = UINT32_C(0x1f0);
        break;
    case 8u:
        manifest->regions[1].guest_base = UINT32_MAX - 3u;
        manifest->regions[1].mapped_size = UINT32_C(8);
        manifest->regions[1].source_size = 0u;
        break;
    default:
        manifest->regions[1].kind = GN_REGION_ROM;
        break;
    }
}

static const char *media_case_id(unsigned kind) {
    static const char *const ids[] = {
        "media-payload-owned-copy", "media-version", "media-profile",
        "media-region-count", "media-rom-base", "media-short-rom",
        "media-long-rom-readable", "media-overlap", "media-endpoint-wrap",
        "media-duplicate-region-kind"
    };
    return ids[kind % (sizeof(ids) / sizeof(ids[0]))];
}

static int start_media_instances(gn_instance **target, gn_instance **peer,
                                 guarded_sources *target_sources,
                                 guarded_sources *peer_sources) {
    make_guarded_sources(target_sources, GUEST_FIXTURE_SCENARIO_A);
    make_guarded_sources(peer_sources, GUEST_FIXTURE_SCENARIO_B);
    mutation_check_status("sdk.mutation.media.create-target", GN_STATUS_OK,
                          gn_create(target));
    mutation_check_status("sdk.mutation.media.create-peer", GN_STATUS_OK,
                          gn_create(peer));
    if (*target == NULL || *peer == NULL) return 0;
    if (sdk_mutation_peak_live < 2u) sdk_mutation_peak_live = 2u;
    gn_manifest target_manifest;
    gn_manifest peer_manifest;
    make_guarded_manifest(&target_manifest, target_sources);
    make_guarded_manifest(&peer_manifest, peer_sources);
    mutation_check_status("sdk.mutation.media.load-target", GN_STATUS_OK,
                          gn_load(*target, &target_manifest));
    mutation_check_status("sdk.mutation.media.load-peer", GN_STATUS_OK,
                          gn_load(*peer, &peer_manifest));
    gn_run_result progress;
    mutation_check_status("sdk.mutation.media.progress-target", GN_STATUS_OK,
                          gn_run(*target, 44u, &progress));
    memset(&progress, 0, sizeof(progress));
    mutation_check_status("sdk.mutation.media.progress-peer", GN_STATUS_OK,
                          gn_run(*peer, 44u, &progress));
    sdk_mutation_guest_cycles += UINT64_C(88);
    mutation_check_u64("sdk.mutation.media.peer-progress-pc", UINT32_C(0x102),
                       progress.boundary_pc);
    return mutation_failure_id == NULL;
}

static int run_media_input(const uint8_t *input, size_t length,
                           unsigned corpus_index) {
    guarded_sources target_sources;
    guarded_sources peer_sources;
    gn_instance *target = NULL;
    gn_instance *peer = NULL;
    const unsigned kind = length == 0u ? 0u : (unsigned)(input[0] % 10u);
    const char *case_id = corpus_index < 10u
                              ? media_case_id(corpus_index)
                              : media_case_id(kind);
    gn_status expected_status = GN_STATUS_INVALID_MEDIA;
    uint64_t input_guest_cycles = UINT64_C(88);

    (void)case_id;
    if (length > MUTATION_INPUT_LIMIT) {
        mutation_check_u64("sdk.mutation.input-byte-cap", MUTATION_INPUT_LIMIT,
                           length);
        return 0;
    }
    if (length > sdk_mutation_max_input_bytes) sdk_mutation_max_input_bytes = length;
    if (sdk_mutation_max_operations < 1u) sdk_mutation_max_operations = 1u;
    if (!start_media_instances(&target, &peer, &target_sources, &peer_sources)) {
        gn_destroy(target);
        gn_destroy(peer);
        return 0;
    }

    public_snapshot target_before;
    public_snapshot peer_before;
    check_snapshot("target-before", target, &target_before);
    check_snapshot("peer-before", peer, &peer_before);
    gn_manifest candidate;
    make_guarded_manifest(&candidate, &target_sources);
    const size_t media_storage =
        candidate.regions[0].mapped_size + candidate.regions[0].source_size +
        candidate.regions[1].mapped_size + candidate.regions[1].source_size;
    mutation_check_true("sdk.mutation.media.storage-cap",
                        media_storage <= GN_MAX_MEDIA_BYTES);
    if (kind == 0u) {
        const uint8_t replacement = length > 1u ? input[1] : UINT8_C(0x7f);
        target_sources.rom[0x101u] = replacement;
        expected_status = GN_STATUS_OK;
    }
    apply_media_mutation(kind, &candidate, &target_sources);
    if (kind == 2u) expected_status = GN_STATUS_UNSUPPORTED_PROFILE;
    const gn_status load_status = gn_load(target, &candidate);
    mutation_check_status(case_id, expected_status, load_status);
    check_canaries(&target_sources);

    if (expected_status == GN_STATUS_OK && load_status == GN_STATUS_OK) {
        const uint8_t immediate = target_sources.rom[0x101u];
        const uint32_t sign_extended = immediate < UINT8_C(0x80)
                                           ? (uint32_t)immediate
                                           : UINT32_C(0xffffff00) | immediate;
        const uint32_t expected_result = sign_extended + UINT32_C(3);
        gn_run_result first_run;
        gn_observations first_observations;
        memset(&first_run, 0, sizeof(first_run));
        memset(&first_observations, 0, sizeof(first_observations));
        mutation_check_status("sdk.mutation.media.success-reset",
                              GN_STATUS_OK, gn_reset(target));
        mutation_check_status("sdk.mutation.media.success-run",
                              GN_STATUS_OK, gn_run(target, 172u, &first_run));
        sdk_mutation_guest_cycles += UINT64_C(172);
        input_guest_cycles += UINT64_C(172);
        mutation_check_u64("sdk.mutation.media.success-stop", GN_RUN_STOPPED,
                           (uint64_t)first_run.reason);
        mutation_check_status("sdk.mutation.media.success-observe",
                              GN_STATUS_OK,
                              gn_observe(target, &first_observations));
        mutation_check_u64("sdk.mutation.media.success-expected-result",
                           expected_result,
                           first_observations.arithmetic_result);
        memset(target_sources.rom, 0xa5, GUEST_FIXTURE_ROM_SIZE);
        memset(target_sources.ram, 0x5a, GUEST_FIXTURE_RAM_INIT_SIZE);
        mutation_check_status("sdk.mutation.media.copy-reset",
                              GN_STATUS_OK, gn_reset(target));
        gn_run_result repeated_run;
        gn_observations repeated_observations;
        memset(&repeated_run, 0, sizeof(repeated_run));
        memset(&repeated_observations, 0, sizeof(repeated_observations));
        mutation_check_status("sdk.mutation.media.copy-run",
                              GN_STATUS_OK, gn_run(target, 172u, &repeated_run));
        sdk_mutation_guest_cycles += UINT64_C(172);
        input_guest_cycles += UINT64_C(172);
        mutation_check_status("sdk.mutation.media.copy-observe",
                              GN_STATUS_OK,
                              gn_observe(target, &repeated_observations));
        mutation_check_u64("sdk.mutation.media.repeat-pc",
                           first_run.boundary_pc, repeated_run.boundary_pc);
        mutation_check_u64("sdk.mutation.media.repeat-cycles",
                           first_run.elapsed_cycles, repeated_run.elapsed_cycles);
        mutation_check_u64("sdk.mutation.media.repeat-instructions",
                           first_run.instructions, repeated_run.instructions);
        mutation_check_u64("sdk.mutation.media.repeat-arithmetic",
                           first_observations.arithmetic_result,
                           repeated_observations.arithmetic_result);
        mutation_check_u64("sdk.mutation.media.repeat-initialized",
                           first_observations.initialized_result,
                           repeated_observations.initialized_result);
        mutation_check_u64("sdk.mutation.media.repeat-bss",
                           first_observations.bss_result,
                           repeated_observations.bss_result);
    } else {
        public_snapshot target_after;
        check_snapshot("target-after-rejected-load", target, &target_after);
        compare_snapshots("target-rejected-load", &target_before, &target_after);
    }

    public_snapshot peer_after;
    check_snapshot("peer-after", peer, &peer_after);
    compare_snapshots("peer-unchanged", &peer_before, &peer_after);
    check_canaries(&target_sources);
    check_canaries(&peer_sources);
    mutation_check_true("sdk.mutation.media.cycle-cap",
                        input_guest_cycles <= MUTATION_CYCLE_LIMIT);
    if (input_guest_cycles > sdk_mutation_peak_guest_cycles) {
        sdk_mutation_peak_guest_cycles = input_guest_cycles;
    }
    gn_destroy(target);
    gn_destroy(peer);
    ++sdk_mutation_cases;
    ++sdk_mutation_operations;
    return mutation_failure_id == NULL;
}

static gn_status load_sequence_owner(sequence_owner *owner, unsigned scenario) {
    guarded_sources sources;
    make_guarded_sources(&sources, (guest_fixture_scenario)scenario);
    gn_manifest manifest;
    make_guarded_manifest(&manifest, &sources);
    const gn_status result = gn_load(owner->instance, &manifest);
    if (result == GN_STATUS_OK) {
        owner->loaded = 1;
        owner->scenario = scenario;
        memset(sources.rom, 0xa5, GUEST_FIXTURE_ROM_SIZE);
        memset(sources.ram, 0x5a, GUEST_FIXTURE_RAM_INIT_SIZE);
    }
    mutation_check_true("sdk.mutation.sequence.source-canaries",
                        guards_unchanged(&sources));
    return result;
}

static void capture_sequence_peers(sequence_owner owners[MUTATION_LIVE_LIMIT],
                                   unsigned target,
                                   public_snapshot snapshots[MUTATION_LIVE_LIMIT],
                                   int active[MUTATION_LIVE_LIMIT]) {
    for (unsigned index = 0u; index < MUTATION_LIVE_LIMIT; ++index) {
        active[index] = owners[index].instance != NULL &&
                        owners[index].loaded != 0 && index != target;
        if (active[index] != 0) {
            check_snapshot("sequence-peer-before", owners[index].instance,
                           &snapshots[index]);
        }
    }
}

static void compare_sequence_peers(sequence_owner owners[MUTATION_LIVE_LIMIT],
                                   unsigned target,
                                   const public_snapshot snapshots[MUTATION_LIVE_LIMIT],
                                   const int active[MUTATION_LIVE_LIMIT]) {
    for (unsigned index = 0u; index < MUTATION_LIVE_LIMIT; ++index) {
        if (active[index] != 0 && index != target && owners[index].instance != NULL) {
            public_snapshot after;
            check_snapshot("sequence-peer-after", owners[index].instance, &after);
            compare_snapshots("sequence-peer-unchanged", &snapshots[index], &after);
        }
    }
}

static int find_free_slot(sequence_owner owners[MUTATION_LIVE_LIMIT]) {
    for (unsigned index = 0u; index < MUTATION_LIVE_LIMIT; ++index) {
        if (owners[index].instance == NULL) return (int)index;
    }
    return -1;
}

static int find_live_slot(sequence_owner owners[MUTATION_LIVE_LIMIT]) {
    for (unsigned index = 0u; index < MUTATION_LIVE_LIMIT; ++index) {
        if (owners[index].instance != NULL) return (int)index;
    }
    return -1;
}

static uint64_t count_live_slots(sequence_owner owners[MUTATION_LIVE_LIMIT]) {
    uint64_t live = 0u;
    for (unsigned index = 0u; index < MUTATION_LIVE_LIMIT; ++index) {
        if (owners[index].instance != NULL) ++live;
    }
    return live;
}

static int normalize_target(sequence_owner owners[MUTATION_LIVE_LIMIT],
                            unsigned *action, unsigned requested_target) {
    int target = (int)(requested_target % MUTATION_LIVE_LIMIT);
    if (*action == 0u) {
        if (owners[target].instance == NULL) return target;
        const int free_slot = find_free_slot(owners);
        if (free_slot >= 0) return free_slot;
        *action = 5u;
        return target;
    }
    if (owners[target].instance == NULL) {
        const int free_slot = find_free_slot(owners);
        if (free_slot >= 0) {
            *action = 0u;
            return free_slot;
        }
        target = find_live_slot(owners);
        if (target < 0) return 0;
    }
    if ((*action == 2u || *action == 3u || *action == 4u) &&
        owners[target].loaded == 0) {
        *action = 1u;
    }
    return target;
}

static int run_sequence_operation(sequence_owner owners[MUTATION_LIVE_LIMIT],
                                  const uint8_t *input, size_t length,
                                  size_t index, uint64_t *guest_cycles) {
    unsigned action = (unsigned)(input[index] & UINT8_C(7));
    if (action > 5u) action %= 6u;
    const unsigned requested_target = (unsigned)(input[index] >> 3);
    const unsigned target = (unsigned)normalize_target(owners, &action,
                                                       requested_target);
    public_snapshot peers_before[MUTATION_LIVE_LIMIT];
    int peer_active[MUTATION_LIVE_LIMIT] = {0, 0, 0, 0};
    capture_sequence_peers(owners, target, peers_before, peer_active);

    if (action == 0u) {
        gn_instance *instance = NULL;
        mutation_check_status("sdk.mutation.sequence.create", GN_STATUS_OK,
                              gn_create(&instance));
        if (instance != NULL) {
            owners[target].instance = instance;
            owners[target].loaded = 0;
            const uint64_t live = count_live_slots(owners);
            if (live > sdk_mutation_peak_live) sdk_mutation_peak_live = live;
        }
    } else if (action == 1u) {
        const unsigned source = length == 0u ? 0u :
                                (unsigned)(input[(index + 1u) % length] & 1u);
        mutation_check_status("sdk.mutation.sequence.load", GN_STATUS_OK,
                              load_sequence_owner(&owners[target], source));
    } else if (action == 2u) {
        mutation_check_status("sdk.mutation.sequence.reset", GN_STATUS_OK,
                              gn_reset(owners[target].instance));
    } else if (action == 3u) {
        uint64_t request = 0u;
        if (length > 0u) {
            const uint64_t high = input[(index + 1u) % length];
            const uint64_t low = input[(index + 2u) % length];
            request = ((high << 8) | low) % UINT64_C(513);
        }
        if (request > MUTATION_CYCLE_LIMIT - *guest_cycles) {
            request = MUTATION_CYCLE_LIMIT - *guest_cycles;
        }
        *guest_cycles += request;
        sdk_mutation_guest_cycles += request;
        gn_run_result result;
        memset(&result, 0, sizeof(result));
        mutation_check_status("sdk.mutation.sequence.run", GN_STATUS_OK,
                              gn_run(owners[target].instance, request, &result));
        mutation_check_u64("sdk.mutation.sequence.requested",
                           request, result.requested_cycles);
        mutation_check_true("sdk.mutation.sequence.run-reason",
                            result.reason <= GN_RUN_ERROR);
    } else if (action == 4u) {
        mutation_check_status("sdk.mutation.sequence.unload", GN_STATUS_OK,
                              gn_unload(owners[target].instance));
        owners[target].loaded = 0;
    } else {
        gn_destroy(owners[target].instance);
        owners[target].instance = NULL;
        owners[target].loaded = 0;
    }
    uint64_t loaded_storage = 0u;
    for (unsigned owner_index = 0u; owner_index < MUTATION_LIVE_LIMIT; ++owner_index) {
        if (owners[owner_index].instance != NULL && owners[owner_index].loaded != 0) {
            loaded_storage += UINT64_C(5130);
        }
    }
    if (loaded_storage > sdk_mutation_peak_storage) {
        sdk_mutation_peak_storage = loaded_storage;
    }
    mutation_check_true("sdk.mutation.sequence.storage-cap",
                        loaded_storage <= GN_MAX_MEDIA_BYTES);
    compare_sequence_peers(owners, target, peers_before, peer_active);
    ++sdk_mutation_operations;
    return mutation_failure_id == NULL;
}

static int audit_sequence_owners(sequence_owner owners[MUTATION_LIVE_LIMIT],
                                 uint64_t *guest_cycles) {
    static const uint32_t expected_arithmetic[] = {10u, 16u};
    static const uint32_t expected_initialized[] = {0x1237u, 0x2348u};
    for (unsigned index = 0u; index < MUTATION_LIVE_LIMIT; ++index) {
        sequence_owner *owner = &owners[index];
        if (owner->instance == NULL || owner->loaded == 0) continue;
        mutation_check_true("sdk.mutation.sequence.audit-budget",
                            *guest_cycles <= MUTATION_CYCLE_LIMIT - 344u);
        mutation_check_status("sdk.mutation.sequence.audit-reset-a",
                              GN_STATUS_OK, gn_reset(owner->instance));
        gn_run_result first_run;
        gn_observations first_observations;
        memset(&first_run, 0, sizeof(first_run));
        memset(&first_observations, 0, sizeof(first_observations));
        *guest_cycles += 172u;
        sdk_mutation_guest_cycles += 172u;
        mutation_check_status("sdk.mutation.sequence.audit-run-a",
                              GN_STATUS_OK,
                              gn_run(owner->instance, 172u, &first_run));
        mutation_check_status("sdk.mutation.sequence.audit-observe-a",
                              GN_STATUS_OK,
                              gn_observe(owner->instance, &first_observations));
        mutation_check_status("sdk.mutation.sequence.audit-reset-b",
                              GN_STATUS_OK, gn_reset(owner->instance));
        gn_run_result second_run;
        gn_observations second_observations;
        memset(&second_run, 0, sizeof(second_run));
        memset(&second_observations, 0, sizeof(second_observations));
        *guest_cycles += 172u;
        sdk_mutation_guest_cycles += 172u;
        mutation_check_status("sdk.mutation.sequence.audit-run-b",
                              GN_STATUS_OK,
                              gn_run(owner->instance, 172u, &second_run));
        mutation_check_status("sdk.mutation.sequence.audit-observe-b",
                              GN_STATUS_OK,
                              gn_observe(owner->instance, &second_observations));
        mutation_check_u64("sdk.mutation.sequence.audit-stop", GN_RUN_STOPPED,
                           (uint64_t)first_run.reason);
        mutation_check_u64("sdk.mutation.sequence.audit-arithmetic",
                           expected_arithmetic[owner->scenario],
                           first_observations.arithmetic_result);
        mutation_check_u64("sdk.mutation.sequence.audit-initialized",
                           expected_initialized[owner->scenario],
                           first_observations.initialized_result);
        mutation_check_u64("sdk.mutation.sequence.audit-bss", 1u,
                           first_observations.bss_result);
        mutation_check_u64("sdk.mutation.sequence.audit-repeat-pc",
                           first_run.boundary_pc, second_run.boundary_pc);
        mutation_check_u64("sdk.mutation.sequence.audit-repeat-cycles",
                           first_run.elapsed_cycles, second_run.elapsed_cycles);
        mutation_check_u64("sdk.mutation.sequence.audit-repeat-result",
                           first_observations.arithmetic_result,
                           second_observations.arithmetic_result);
    }
    return mutation_failure_id == NULL;
}

static int run_sequence_input(const uint8_t *input, size_t length) {
    sequence_owner owners[MUTATION_LIVE_LIMIT] = {
        {NULL, 0, 0u}, {NULL, 0, 0u}, {NULL, 0, 0u}, {NULL, 0, 0u}
    };
    uint64_t guest_cycles = 0u;
    if (length > MUTATION_INPUT_LIMIT) {
        mutation_check_u64("sdk.mutation.input-byte-cap", MUTATION_INPUT_LIMIT,
                           length);
        return 0;
    }
    if (length > MUTATION_OPERATIONS_LIMIT) length = MUTATION_OPERATIONS_LIMIT;
    if (length > sdk_mutation_max_input_bytes) sdk_mutation_max_input_bytes = length;
    if (length > sdk_mutation_max_operations) {
        sdk_mutation_max_operations = length;
    }
    mutation_check_true("sdk.mutation.sequence.operation-cap",
                        length <= MUTATION_OPERATIONS_LIMIT);
    const uint64_t live_before = sdk_mutation_peak_live;
    for (size_t index = 0u; index < length; ++index) {
        if (!run_sequence_operation(owners, input, length, index, &guest_cycles)) {
            break;
        }
    }
    if (mutation_failure_id == NULL) (void)audit_sequence_owners(owners, &guest_cycles);
    for (unsigned index = 0u; index < MUTATION_LIVE_LIMIT; ++index) {
        gn_destroy(owners[index].instance);
        owners[index].instance = NULL;
    }
    mutation_check_true("sdk.mutation.sequence.cycle-cap",
                        guest_cycles <= MUTATION_CYCLE_LIMIT);
    if (guest_cycles > sdk_mutation_peak_guest_cycles) {
        sdk_mutation_peak_guest_cycles = guest_cycles;
    }
    mutation_check_true("sdk.mutation.sequence.live-cap",
                        sdk_mutation_peak_live <= MUTATION_LIVE_LIMIT);
    mutation_check_true("sdk.mutation.sequence.live-observed",
                        sdk_mutation_peak_live >= live_before);
    ++sdk_mutation_cases;
    return mutation_failure_id == NULL;
}

static void execute_corpus_case(const char *id, const char *harness,
                                const uint8_t *bytes, size_t length,
                                uint64_t iteration) {
    if (mutation_failure_id != NULL) return;
    activate_input(bytes, length, MUTATION_SEED, iteration);
    SDK_CASE(id);
    if (strcmp(harness, "media") == 0) {
        (void)run_media_input(bytes, length, 10u);
    } else {
        (void)run_sequence_input(bytes, length);
    }
    if (mutation_failure_id == NULL) {
        (void)printf("# MUTATION_CASE id=%s harness=%s bytes=%zu outcome=pass\n",
                     id, harness, length);
    }
    print_failure();
}

static void media_mutation_entrypoint(void) {
    static const char *const regression_ids[] = {
        "media-payload-owned-copy", "media-version", "media-profile",
        "media-region-count", "media-rom-base", "media-short-rom",
        "media-long-rom-readable", "media-overlap", "media-endpoint-wrap",
        "media-duplicate-region-kind"
    };
    const clock_t start = clock();
    const uint64_t guest_cycles_before = sdk_mutation_guest_cycles;
    uint8_t integer_input[MUTATION_INPUT_BYTES] = {0};
    activate_input(integer_input, sizeof(integer_input), MUTATION_SEED, 0u);
    (void)execute_wrap_sign_regressions();
    if (mutation_failure_id != NULL) {
        print_failure();
        TEST_FAIL_MESSAGE("integer wrap/sign regression failed");
        return;
    }
    for (unsigned kind = 0u; kind < sizeof(regression_ids) / sizeof(regression_ids[0]);
         ++kind) {
        uint8_t input[MUTATION_INPUT_BYTES] = {0};
        input[0] = (uint8_t)kind;
        input[1] = UINT8_C(0x7f);
        execute_corpus_case(regression_ids[kind], "media", input,
                            sizeof(input), kind);
        if (mutation_failure_id != NULL) break;
    }
    uint64_t random = MUTATION_SEED;
    uint64_t hashes[MUTATION_ITERATIONS];
    unsigned iterations_completed = 0u;
    for (unsigned iteration = 0u; iteration < MUTATION_ITERATIONS; ++iteration) {
        uint8_t input[MUTATION_INPUT_BYTES];
        fill_input(input, &random);
        activate_input(input, sizeof(input), MUTATION_SEED, iteration);
        (void)run_media_input(input, sizeof(input), 10u);
        hashes[iteration] = input_hash(input, sizeof(input));
        ++iterations_completed;
        if (mutation_failure_id != NULL) {
            print_failure();
            break;
        }
    }
    for (unsigned index = 0u; index < iterations_completed; ++index) {
        int seen = 0;
        for (unsigned prior = 0u; prior < index; ++prior) {
            if (hashes[index] == hashes[prior]) {
                seen = 1;
                break;
            }
        }
        if (seen == 0) ++sdk_mutation_unique_inputs;
    }
    const clock_t elapsed = clock() - start;
    (void)printf("SDK_MUTATION suite=media seed=%" PRIu64
                 " iterations=%u corpus_cases=%zu unique_inputs=%" PRIu64
                 " operations=%" PRIu64 " guest_requested_cycles_total=%" PRIu64
                 " max_guest_requested_cycles_per_input=%" PRIu64
                 " input_bytes_limit=%u max_input_bytes_observed=%zu"
                 " operations_limit=%u max_operations_observed=%" PRIu64
                 " max_live_instances=%" PRIu64 " live_instance_limit=%u"
                 " trace_events=%u elapsed_cpu_ms=%.3f\n",
                 MUTATION_SEED, iterations_completed,
                 sizeof(regression_ids) / sizeof(regression_ids[0]),
                 sdk_mutation_unique_inputs, sdk_mutation_operations,
                 sdk_mutation_guest_cycles - guest_cycles_before,
                 sdk_mutation_peak_guest_cycles, MUTATION_INPUT_LIMIT,
                 sdk_mutation_max_input_bytes, MUTATION_OPERATIONS_LIMIT,
                 sdk_mutation_max_operations, sdk_mutation_peak_live,
                 MUTATION_LIVE_LIMIT, 0u,
                 start == (clock_t)-1 || elapsed == (clock_t)-1
                     ? 0.0
                     : 1000.0 * (double)elapsed / (double)CLOCKS_PER_SEC);
    mutation_check_true("sdk.mutation.input-cap",
                        MUTATION_INPUT_BYTES <= MUTATION_INPUT_LIMIT);
    const size_t observed_trace_events = 0u;
    mutation_check_true("sdk.mutation.trace-cap",
                        observed_trace_events <= MUTATION_TRACE_LIMIT);
    if (mutation_failure_id != NULL) TEST_FAIL_MESSAGE("bounded media mutation failed");
}

static void sequence_mutation_entrypoint(void) {
    static const uint8_t recovery[] = {0u, 1u, 3u, 2u, 4u, 1u, 5u};
    static const uint8_t four_live[] = {
        0u, 8u, 16u, 24u, 1u, 9u, 17u, 25u, 3u, 11u, 19u, 27u,
        5u, 13u, 21u, 29u
    };
    const clock_t start = clock();
    const uint64_t guest_cycles_before = sdk_mutation_guest_cycles;
    uint64_t random = MUTATION_SEED ^ UINT64_C(0xa17f00d5);
    uint64_t hashes[MUTATION_ITERATIONS];
    unsigned iterations_completed = 0u;
    execute_corpus_case("sequence-unload-reload-recovery", "sequence",
                        recovery, sizeof(recovery), 0u);
    execute_corpus_case("sequence-four-live-owners", "sequence",
                        four_live, sizeof(four_live), 1u);
    for (unsigned iteration = 0u; iteration < MUTATION_ITERATIONS; ++iteration) {
        uint8_t input[MUTATION_INPUT_BYTES];
        fill_input(input, &random);
        const size_t length = 1u + (size_t)(input[0] % MUTATION_OPERATIONS_LIMIT);
        activate_input(input, length, MUTATION_SEED ^ UINT64_C(0xa17f00d5),
                       iteration);
        (void)run_sequence_input(input, length);
        hashes[iteration] = input_hash(input, length);
        ++iterations_completed;
        if (mutation_failure_id != NULL) {
            print_failure();
            break;
        }
    }
    for (unsigned index = 0u; index < iterations_completed; ++index) {
        int seen = 0;
        for (unsigned prior = 0u; prior < index; ++prior) {
            if (hashes[index] == hashes[prior]) {
                seen = 1;
                break;
            }
        }
        if (seen == 0) ++sdk_mutation_unique_inputs;
    }
    const clock_t elapsed = clock() - start;
    (void)printf("SDK_MUTATION suite=sequence seed=%" PRIu64
                 " iterations=%u corpus_cases=2 unique_inputs=%" PRIu64
                 " operations=%" PRIu64 " guest_requested_cycles_total=%" PRIu64
                 " max_guest_requested_cycles_per_input=%" PRIu64
                 " input_bytes_limit=%u max_input_bytes_observed=%zu"
                 " operations_limit=%u max_operations_observed=%" PRIu64
                 " max_live_instances=%" PRIu64 " live_instance_limit=%u"
                 " trace_events=%u elapsed_cpu_ms=%.3f\n",
                 MUTATION_SEED ^ UINT64_C(0xa17f00d5), iterations_completed,
                 sdk_mutation_unique_inputs, sdk_mutation_operations,
                 sdk_mutation_guest_cycles - guest_cycles_before,
                 sdk_mutation_peak_guest_cycles, MUTATION_INPUT_LIMIT,
                 sdk_mutation_max_input_bytes, MUTATION_OPERATIONS_LIMIT,
                 sdk_mutation_max_operations, sdk_mutation_peak_live,
                 MUTATION_LIVE_LIMIT, 0u,
                 start == (clock_t)-1 || elapsed == (clock_t)-1
                     ? 0.0
                     : 1000.0 * (double)elapsed / (double)CLOCKS_PER_SEC);
    (void)printf("SDK_MUTATION_STORAGE suite=sequence peak_media_bytes=%" PRIu64
                 " storage_limit=%zu\n", sdk_mutation_peak_storage,
                 GN_MAX_MEDIA_BYTES);
    mutation_check_true("sdk.mutation.input-cap",
                        MUTATION_INPUT_BYTES <= MUTATION_INPUT_LIMIT);
    const size_t observed_trace_events = 0u;
    mutation_check_true("sdk.mutation.trace-cap",
                        observed_trace_events <= MUTATION_TRACE_LIMIT);
    if (mutation_failure_id != NULL) TEST_FAIL_MESSAGE("bounded sequence mutation failed");
}

static int read_input_file(const char *path, uint8_t input[MUTATION_INPUT_LIMIT],
                           size_t *length) {
    FILE *file = fopen(path, "rb");
    if (file == NULL) return 0;
    const size_t count = fread(input, 1u, MUTATION_INPUT_LIMIT, file);
    const int extra_byte = fgetc(file);
    const int close_status = fclose(file);
    if (close_status != 0 || extra_byte != EOF) return 0;
    *length = count;
    return 1;
}

static void replay_entrypoint(void) {
    SDK_CASE("sdk.mutation.replay-exact-input");
    if (strcmp(selected_mode, "media") == 0) {
        (void)run_media_input(replay_input, replay_input_size, 10u);
    } else {
        (void)run_sequence_input(replay_input, replay_input_size);
    }
    if (mutation_failure_id != NULL) {
        print_failure();
        TEST_FAIL_MESSAGE("replayed mutation invariant failed");
    }
}

static SDK_TEST_THREAD_RESULT SDK_TEST_THREAD_CALL startup_thread(void *context) {
    (void)context;
    startup_thread_value = 1;
    return SDK_TEST_THREAD_DONE;
}

static int startup_probe(const char *lane) {
    const int is_tsan = strcmp(lane, "tsan") == 0;
    const int is_asan_ubsan = strcmp(lane, "asan-ubsan") == 0;
    if (!is_tsan && !is_asan_ubsan) return 2;
    volatile uint8_t *memory = (volatile uint8_t *)malloc(16u);
    if (memory == NULL) return 1;
    for (size_t index = 0u; index < 16u; ++index) memory[index] = (uint8_t)index;
    uint64_t sum = 0u;
    for (size_t index = 0u; index < 16u; ++index) sum += memory[index];
    free((void *)memory);
    if (sum != UINT64_C(120)) return 1;
    unsigned startup_checks = 17u;
    if (is_tsan) {
        sdk_test_thread thread;
        startup_thread_value = 0;
        if (!sdk_test_thread_start(&thread, startup_thread, NULL)) return 1;
        if (!sdk_test_thread_join(thread)) return 1;
        if (startup_thread_value != 1) return 1;
        ++startup_checks;
    }
    (void)printf("SANITIZER_STARTUP {\"lane\":\"%s\",\"outcome\":\"pass\","
                 "\"startup_checks\":%u,\"compiler\":\"%s %s\","
                 "\"configuration\":\"%s\",\"sanitizer\":\"%s\"}\n",
                 lane, startup_checks, GLUEYNEO_COMPILER_ID,
                 GLUEYNEO_COMPILER_VERSION, GLUEYNEO_CONFIGURATION,
                 GLUEYNEO_SANITIZER);
    return 0;
}

int main(int argc, char **argv) {
    if (argc == 3 && strcmp(argv[1], "--startup-probe") == 0) {
        return startup_probe(argv[2]);
    }
    if (argc == 4 && strcmp(argv[1], "--replay") == 0) {
        uint8_t input[MUTATION_INPUT_LIMIT];
        size_t length = 0u;
        if (!read_input_file(argv[3], input, &length)) {
            (void)fprintf(stderr, "cannot read bounded replay input\n");
            return 2;
        }
        selected_mode = argv[2];
        replay_input = input;
        replay_input_size = length;
        activate_input(input, length, MUTATION_SEED, 0u);
        (void)UNITY_BEGIN();
        if (strcmp(selected_mode, "media") != 0 &&
            strcmp(selected_mode, "sequence") != 0) {
            (void)fprintf(stderr, "unknown replay harness: %s\n", selected_mode);
            return 2;
        }
        RUN_TEST(replay_entrypoint);
        const int failures = UNITY_END();
        sdk_test_result("mutation-replay", failures, GLUEYNEO_SOURCE_REVISION,
                        GLUEYNEO_CONFIGURATION, GLUEYNEO_COMPILER_ID,
                        GLUEYNEO_COMPILER_VERSION);
        if (mutation_failure_id != NULL) return 1;
        return failures;
    }
    if (argc != 2 || (strcmp(argv[1], "--media") != 0 &&
                      strcmp(argv[1], "--sequence") != 0)) {
        (void)fprintf(stderr,
                      "usage: %s --media|--sequence|--startup-probe LANE|"
                      "--replay media|sequence INPUT\n", argv[0]);
        return 2;
    }
    selected_mode = argv[1];
    (void)UNITY_BEGIN();
    if (strcmp(selected_mode, "--media") == 0) {
        RUN_TEST(media_mutation_entrypoint);
    } else {
        RUN_TEST(sequence_mutation_entrypoint);
    }
    const int failures = UNITY_END();
    sdk_test_result(strcmp(selected_mode, "--media") == 0
                        ? "sdk-mutation-media" : "sdk-mutation-sequence",
                    failures, GLUEYNEO_SOURCE_REVISION, GLUEYNEO_CONFIGURATION,
                    GLUEYNEO_COMPILER_ID, GLUEYNEO_COMPILER_VERSION);
    return failures;
}
