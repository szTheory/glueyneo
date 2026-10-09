/* SPDX-License-Identifier: MIT; original diagnostic consumer example. */
#include <glueyneo/glueyneo.h>

#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

enum {
    DIAGNOSTIC_ROM_BYTES = 512,
    DIAGNOSTIC_RAM_SEED_BYTES = 10,
    DIAGNOSTIC_FIXTURE_BYTES = DIAGNOSTIC_ROM_BYTES + DIAGNOSTIC_RAM_SEED_BYTES
};

static uint64_t assertion_count;

static int read_fixture(const char *path, uint8_t bytes[DIAGNOSTIC_FIXTURE_BYTES]) {
    FILE *input = fopen(path, "rb");
    if (input == NULL) {
        (void)fprintf(stderr, "cannot open diagnostic fixture: %s\n", path);
        return 0;
    }
    const size_t count = fread(bytes, 1u, DIAGNOSTIC_FIXTURE_BYTES, input);
    const int extra = fgetc(input);
    const int read_error = ferror(input);
    const int close_error = fclose(input);
    if (count != DIAGNOSTIC_FIXTURE_BYTES || extra != EOF || read_error != 0 ||
        close_error != 0) {
        (void)fprintf(stderr,
                      "diagnostic fixture must contain exactly %d bytes\n",
                      DIAGNOSTIC_FIXTURE_BYTES);
        return 0;
    }
    return 1;
}

static int check_status(const char *name, gn_status expected, gn_status observed) {
    ++assertion_count;
    if (expected == observed) return 1;
    (void)fprintf(stderr, "CONSUMER_ASSERT %s expected=%s observed=%s\n", name,
                  gn_status_string(expected), gn_status_string(observed));
    return 0;
}

static int check_u64(const char *name, uint64_t expected, uint64_t observed) {
    ++assertion_count;
    if (expected == observed) return 1;
    (void)fprintf(stderr,
                  "CONSUMER_ASSERT %s expected=%" PRIu64 " observed=%" PRIu64
                  "\n",
                  name, expected, observed);
    return 0;
}

static int parse_expected_arithmetic(const char *text, uint32_t *expected) {
    char *end = NULL;
    const unsigned long value = strtoul(text, &end, 10);
    if (text[0] == '\0' || end == text || *end != '\0' || value > UINT32_MAX) {
        return 0;
    }
    *expected = (uint32_t)value;
    return 1;
}

int main(int argc, char **argv) {
    const int recovery_mode = argc == 3 && strcmp(argv[2], "--recovery") == 0;
    if (argc != 2 && argc != 4 && !recovery_mode) {
        (void)fprintf(stderr,
                      "usage: glueyneo-installed-c FIXTURE [--recovery | "
                      "--expect-arithmetic N]\n");
        return 2;
    }
    uint32_t expected_arithmetic = 10u;
    if (argc == 4 &&
        (strcmp(argv[2], "--expect-arithmetic") != 0 ||
         !parse_expected_arithmetic(argv[3], &expected_arithmetic))) {
        (void)fprintf(stderr, "invalid expected arithmetic value\n");
        return 2;
    }

    uint8_t fixture[DIAGNOSTIC_FIXTURE_BYTES];
    if (!read_fixture(argv[1], fixture)) return 2;

    gn_manifest manifest;
    memset(&manifest, 0, sizeof(manifest));
    manifest.version = GN_MANIFEST_VERSION;
    manifest.profile = GN_PROFILE_DIAGNOSTIC;
    manifest.region_count = GN_MAX_REGIONS;
    manifest.regions[0] = (gn_region){
        .guest_base = 0u,
        .mapped_size = DIAGNOSTIC_ROM_BYTES,
        .source = fixture,
        .source_size = DIAGNOSTIC_ROM_BYTES,
        .kind = GN_REGION_ROM,
    };
    manifest.regions[1] = (gn_region){
        .guest_base = 0x1000u,
        .mapped_size = 4096u,
        .source = fixture + DIAGNOSTIC_ROM_BYTES,
        .source_size = DIAGNOSTIC_RAM_SEED_BYTES,
        .kind = GN_REGION_RAM,
    };

    gn_instance *instance = NULL;
    gn_status status = gn_create(&instance);
    int passed = check_status("sdk.instance.create", GN_STATUS_OK, status);
    if (status == GN_STATUS_OK) status = gn_load(instance, &manifest);
    passed &= check_status("sdk.media.load", GN_STATUS_OK, status);

    if (recovery_mode && status == GN_STATUS_OK) {
        manifest.regions[0].mapped_size = DIAGNOSTIC_ROM_BYTES - 1u;
        const gn_status rejected_status = gn_load(instance, &manifest);
        ++assertion_count;
        if (rejected_status != GN_STATUS_INVALID_MEDIA) {
            passed = 0;
            (void)fprintf(stderr,
                          "CONSUMER_ASSERT sdk.recovery.malformed-manifest "
                          "expected=%s observed=%s\n",
                          gn_status_string(GN_STATUS_INVALID_MEDIA),
                          gn_status_string(rejected_status));
        } else {
            (void)puts(
                "SDK_RECOVERY {\"schema_version\":1,\"case_id\":"
                "\"sdk.recovery.malformed-manifest\",\"outcome\":\"pass\","
                "\"expected_status\":\"invalid diagnostic media\","
                "\"observed_status\":\"invalid diagnostic media\","
                "\"assertions\":1}");
        }
        manifest.regions[0].mapped_size = DIAGNOSTIC_ROM_BYTES;
        if (rejected_status != GN_STATUS_INVALID_MEDIA) status = rejected_status;
    }

    gn_run_result run;
    memset(&run, 0, sizeof(run));
    status = status == GN_STATUS_OK ? gn_run(instance, 196u, &run) : status;
    passed &= check_status("sdk.run.status", GN_STATUS_OK, status);
    passed &= check_u64("sdk.run.elapsed-cycles", 196u, run.elapsed_cycles);
    passed &= check_u64("sdk.run.instructions", 12u, run.instructions);
    passed &= check_u64("sdk.run.reason-stopped", GN_RUN_STOPPED, run.reason);
    passed &= check_u64("sdk.run.boundary-pc", 0x12eu, run.boundary_pc);
    const gn_run_result diagnostic_run = run;

    gn_observations observations;
    memset(&observations, 0, sizeof(observations));
    status = status == GN_STATUS_OK ? gn_observe(instance, &observations) : status;
    passed &= check_status("sdk.observe.status", GN_STATUS_OK, status);
    passed &= check_u64("sdk.observe.arithmetic", expected_arithmetic,
                        observations.arithmetic_result);
    passed &= check_u64("sdk.observe.initialized", 0x1237u,
                        observations.initialized_result);
    passed &= check_u64("sdk.observe.bss", 1u, observations.bss_result);
    passed &= check_u64("sdk.observe.ready", 1u, observations.ready);

    const gn_status reset_status = gn_reset(instance);
    passed &= check_status("sdk.reset", GN_STATUS_OK, reset_status);
    memset(&run, 0, sizeof(run));
    status = reset_status == GN_STATUS_OK ? gn_run(instance, 196u, &run) : reset_status;
    passed &= check_status("sdk.reset-run.status", GN_STATUS_OK, status);
    passed &= check_u64("sdk.reset-run.elapsed-cycles", 196u, run.elapsed_cycles);
    memset(&observations, 0, sizeof(observations));
    status = status == GN_STATUS_OK ? gn_observe(instance, &observations) : status;
    passed &= check_status("sdk.reset-observe.status", GN_STATUS_OK, status);
    passed &= check_u64("sdk.reset-observe.arithmetic", expected_arithmetic,
                        observations.arithmetic_result);

    const gn_status unload_status = gn_unload(instance);
    passed &= check_status("sdk.unload", GN_STATUS_OK, unload_status);
    memset(&run, 0xa5, sizeof(run));
    status = gn_run(instance, 196u, &run);
    passed &= check_status("sdk.unloaded-run.status", GN_STATUS_INVALID_STATE, status);
    passed &= check_u64("sdk.unloaded-run.cleared-cycles", 0u, run.elapsed_cycles);

    (void)printf(
        "SDK_CONSUMER {\"schema_version\":1,\"case_id\":\"sdk.consumer.c\","
        "\"outcome\":\"%s\",\"assertions\":%" PRIu64 ",\"arithmetic\":%" PRIu32
        ",\"initialized\":%" PRIu32 ",\"bss\":%" PRIu32
        ",\"cycles\":%" PRIu64 ",\"instructions\":%" PRIu64
        ",\"pc\":%" PRIu32 "}\n",
        passed ? "pass" : "fail", assertion_count, observations.arithmetic_result,
        observations.initialized_result, observations.bss_result,
        diagnostic_run.elapsed_cycles, diagnostic_run.instructions,
        diagnostic_run.boundary_pc);
    gn_destroy(instance);
    return passed ? 0 : 1;
}
