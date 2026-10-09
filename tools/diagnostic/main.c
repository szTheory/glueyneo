/* SPDX-License-Identifier: MIT */
#include "glueyneo/glueyneo.h"
#include "guest_fixture.h"

#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
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

static uint64_t assertion_count;

static int check_u64(const char *id, uint64_t expected, uint64_t observed) {
    ++assertion_count;
    (void)printf("# ASSERT %s expected=%" PRIu64 " observed=%" PRIu64 "\n",
                 id, expected, observed);
    return expected == observed;
}

static int write_fixture(const char *path, const guest_fixture_image *fixture,
                         char scenario_id) {
    FILE *output = fopen(path, "wb");
    if (output == NULL) {
        (void)fprintf(stderr, "fixture write failed\n");
        return EXIT_FAILURE;
    }
    const size_t rom_written = fwrite(fixture->rom, 1u, sizeof(fixture->rom), output);
    const size_t ram_written = fwrite(fixture->ram_seed, 1u,
                                      sizeof(fixture->ram_seed), output);
    const int close_status = fclose(output);
    const int passed = rom_written == sizeof(fixture->rom) &&
                       ram_written == sizeof(fixture->ram_seed) && close_status == 0;
    (void)printf("SDK_FIXTURE {\"schema_version\":1,\"case_id\":"
                 "\"sdk.fixture.write-%c\",\"outcome\":\"%s\","
                 "\"bytes\":%u}\n",
                 scenario_id, passed ? "pass" : "fail",
                 (unsigned)(sizeof(fixture->rom) + sizeof(fixture->ram_seed)));
    return passed ? EXIT_SUCCESS : EXIT_FAILURE;
}

static int check_fixture(const char *path, const guest_fixture_image *fixture,
                         char scenario_id) {
    uint8_t observed[sizeof(fixture->rom) + sizeof(fixture->ram_seed)];
    FILE *input = fopen(path, "rb");
    if (input == NULL) {
        (void)fprintf(stderr, "fixture check could not read expected file\n");
        return EXIT_FAILURE;
    }
    const size_t amount = fread(observed, 1u, sizeof(observed), input);
    const int trailing = fgetc(input);
    const int io_error = ferror(input);
    const int close_status = fclose(input);
    const int same_length = amount == sizeof(observed) && trailing == EOF &&
                            io_error == 0 && close_status == 0;
    const int same_rom = same_length &&
                         memcmp(observed, fixture->rom, sizeof(fixture->rom)) == 0;
    const int same_ram = same_rom &&
                         memcmp(observed + sizeof(fixture->rom), fixture->ram_seed,
                                sizeof(fixture->ram_seed)) == 0;
    const int passed = same_length && same_rom && same_ram;
    (void)printf("SDK_FIXTURE {\"schema_version\":1,\"case_id\":"
                 "\"sdk.fixture.check-%c\",\"outcome\":\"%s\","
                 "\"bytes\":%u}\n",
                 scenario_id, passed ? "pass" : "fail", (unsigned)sizeof(observed));
    return passed ? EXIT_SUCCESS : EXIT_FAILURE;
}

static int run_scenario(guest_fixture_scenario scenario, const char *fixture_path,
                        int check_canonical_fixture) {
    assertion_count = 0u;
    guest_fixture_image fixture;
    guest_fixture_build(&fixture, scenario);
    const char scenario_id = scenario == GUEST_FIXTURE_SCENARIO_A ? 'a' : 'b';
    if (check_canonical_fixture &&
        check_fixture(fixture_path, &fixture, scenario_id) != EXIT_SUCCESS) {
        return EXIT_FAILURE;
    }

    gn_manifest manifest;
    memset(&manifest, 0, sizeof(manifest));
    manifest.version = GN_MANIFEST_VERSION;
    manifest.profile = GN_PROFILE_DIAGNOSTIC;
    manifest.region_count = GN_MAX_REGIONS;
    manifest.regions[0] = (gn_region){0u, GUEST_FIXTURE_ROM_SIZE, fixture.rom,
                                      sizeof(fixture.rom), GN_REGION_ROM};
    manifest.regions[1] = (gn_region){0x1000u, 4096u, fixture.ram_seed,
                                      sizeof(fixture.ram_seed), GN_REGION_RAM};

    gn_instance *instance = NULL;
    gn_status status = gn_create(&instance);
    int passes = check_u64("sdk.instance.create", GN_STATUS_OK, status);
    if (status == GN_STATUS_OK) {
        status = gn_load(instance, &manifest);
    }
    passes &= check_u64("sdk.media.load", GN_STATUS_OK, status);
    memset(&fixture, 0xa5, sizeof(fixture));

    gn_run_result run;
    memset(&run, 0, sizeof(run));
    gn_status run_status = GN_STATUS_INVALID_STATE;
    if (status == GN_STATUS_OK) run_status = gn_run(instance, 196u, &run);
    passes &= check_u64("sdk.run.status", GN_STATUS_OK, run_status);
    passes &= check_u64("sdk.run.requested-cycles", 196u, run.requested_cycles);
    passes &= check_u64("sdk.run.elapsed-cycles", 196u, run.elapsed_cycles);
    passes &= check_u64("sdk.run.overshoot-cycles", 0u, run.overshoot_cycles);
    passes &= check_u64("sdk.run.instructions", 12u, run.instructions);
    passes &= check_u64("sdk.run.reason-stopped", GN_RUN_STOPPED, run.reason);
    passes &= check_u64("sdk.run.boundary-pc", 0x12eu, run.boundary_pc);

    gn_observations observations;
    memset(&observations, 0, sizeof(observations));
    gn_status observe_status = GN_STATUS_INVALID_STATE;
    if (status == GN_STATUS_OK) observe_status = gn_observe(instance, &observations);
    passes &= check_u64("sdk.observe.status", GN_STATUS_OK, observe_status);
    const uint32_t expected_arithmetic =
        scenario == GUEST_FIXTURE_SCENARIO_A ? 10u : 16u;
    const uint32_t expected_initialized =
        scenario == GUEST_FIXTURE_SCENARIO_A ? 0x1237u : 0x2348u;
    passes &= check_u64("sdk.observe.arithmetic", expected_arithmetic,
                        observations.arithmetic_result);
    passes &= check_u64("sdk.observe.initialized", expected_initialized,
                        observations.initialized_result);
    passes &= check_u64("sdk.observe.bss", 1u, observations.bss_result);
    passes &= check_u64("sdk.observe.ready", 1u, observations.ready);

    (void)printf(
        "SDK_DIAGNOSTIC {\"schema_version\":1,\"case_id\":"
        "\"sdk.diagnostic.original-%c\",\"outcome\":\"%s\","
        "\"assertions\":%" PRIu64 ",\"expected\":{"
        "\"arithmetic\":%" PRIu32 ",\"initialized\":%" PRIu32
        ",\"bss\":1,\"cycles\":196,\"instructions\":12,\"pc\":302},"
        "\"observed\":{\"arithmetic\":%" PRIu32 ",\"initialized\":%" PRIu32
        ",\"bss\":%" PRIu32 ",\"cycles\":%" PRIu64 ",\"instructions\":%" PRIu64
        ",\"pc\":%" PRIu32 ",\"reason\":%d},\"identity\":{"
        "\"source_revision\":\"%s\",\"configuration\":\"%s\","
        "\"compiler\":\"%s %s\"}}\n",
        scenario_id, passes ? "pass" : "fail", assertion_count, expected_arithmetic,
        expected_initialized, observations.arithmetic_result,
        observations.initialized_result, observations.bss_result, run.elapsed_cycles,
        run.instructions, run.boundary_pc, (int)run.reason, GLUEYNEO_SOURCE_REVISION,
        GLUEYNEO_CONFIGURATION, GLUEYNEO_COMPILER_ID, GLUEYNEO_COMPILER_VERSION);
    if (!passes) {
        (void)fprintf(stderr, "diagnostic failed: %s\n", gn_status_string(status));
    }
    gn_destroy(instance);
    return passes ? EXIT_SUCCESS : EXIT_FAILURE;
}

static int print_usage(void) {
    (void)fprintf(stderr,
                  "usage: glueyneo-diagnostic [--scenario-b] | "
                  "--write-fixture PATH [--scenario-b] | "
                  "--check-fixture PATH [--scenario-b]\n");
    return EXIT_FAILURE;
}

int main(int argc, char **argv) {
    guest_fixture_scenario scenario = GUEST_FIXTURE_SCENARIO_A;
    const char *fixture_path = NULL;
    int write_mode = 0;
    int check_mode = 0;
    for (int index = 1; index < argc; ++index) {
        if (strcmp(argv[index], "--scenario-b") == 0) {
            scenario = GUEST_FIXTURE_SCENARIO_B;
        } else if (strcmp(argv[index], "--write-fixture") == 0) {
            if (write_mode || check_mode || index + 1 >= argc) return print_usage();
            write_mode = 1;
            fixture_path = argv[++index];
        } else if (strcmp(argv[index], "--check-fixture") == 0) {
            if (write_mode || check_mode || index + 1 >= argc) return print_usage();
            check_mode = 1;
            fixture_path = argv[++index];
        } else {
            return print_usage();
        }
    }

    guest_fixture_image fixture;
    guest_fixture_build(&fixture, scenario);
    if (write_mode) {
        const char scenario_id = scenario == GUEST_FIXTURE_SCENARIO_A ? 'a' : 'b';
        return write_fixture(fixture_path, &fixture, scenario_id);
    }
    return run_scenario(scenario, fixture_path, check_mode);
}
