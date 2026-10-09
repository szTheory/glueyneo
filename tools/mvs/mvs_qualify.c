/* SPDX-License-Identifier: MIT */
#include "glueyneo/glueyneo.h"

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define HEADER_BYTES 16u
#define REGION_HEADER_BYTES 12u
#define MAX_BUNDLE_BYTES (GN_MVS_MAX_MEDIA_BYTES + HEADER_BYTES + \
                          GN_MVS_MAX_REGIONS * REGION_HEADER_BYTES)
#define MAX_RUN_CHUNKS 128u

static uint32_t read32be(const uint8_t *p) {
    return ((uint32_t)p[0] << 24) | ((uint32_t)p[1] << 16) |
           ((uint32_t)p[2] << 8) | p[3];
}
static uint64_t read64be(const uint8_t *p) {
    return ((uint64_t)read32be(p) << 32) | read32be(p + 4u);
}

static int load_bundle(const uint8_t *bytes, size_t size, gn_mvs_manifest *manifest) {
    if (size < HEADER_BYTES || memcmp(bytes, "GNMV", 4u) != 0 ||
        read32be(bytes + 4u) != 1u ||
        read32be(bytes + 8u) != GN_MVS_PROFILE_MSX ||
        read32be(bytes + 12u) != GN_MVS_MAX_REGIONS) return 0;
    memset(manifest, 0, sizeof(*manifest));
    manifest->version = GN_MVS_MANIFEST_VERSION;
    manifest->profile = GN_MVS_PROFILE_MSX;
    manifest->region_count = GN_MVS_MAX_REGIONS;
    size_t cursor = HEADER_BYTES;
    for (size_t i = 0u; i < manifest->region_count; ++i) {
        if (cursor > size || size - cursor < REGION_HEADER_BYTES) return 0;
        const uint32_t role = read32be(bytes + cursor);
        const uint64_t length = read64be(bytes + cursor + 4u);
        cursor += REGION_HEADER_BYTES;
        if (length > SIZE_MAX || length > size - cursor) return 0;
        manifest->regions[i] = (gn_mvs_region){
            (gn_mvs_region_role)role, bytes + cursor, (size_t)length,
            (size_t)length, GN_MVS_LAYOUT_LINEAR};
        cursor += (size_t)length;
    }
    return cursor == size;
}

int main(int argc, char **argv) {
    if (argc != 2) return 2;
    FILE *file = fopen(argv[1], "rb");
    if (file == NULL || fseek(file, 0, SEEK_END) != 0) {
        if (file != NULL) fclose(file);
        puts("{\"status\":\"normalized_bundle_unavailable\"}");
        return 1;
    }
    const long length = ftell(file);
    if (length < 0 || (unsigned long)length > MAX_BUNDLE_BYTES ||
        fseek(file, 0, SEEK_SET) != 0) {
        fclose(file); puts("{\"status\":\"normalized_bundle_out_of_bounds\"}"); return 1;
    }
    uint8_t *bytes = (uint8_t *)malloc((size_t)length);
    if (bytes == NULL || fread(bytes, 1u, (size_t)length, file) != (size_t)length) {
        free(bytes); fclose(file);
        puts("{\"status\":\"normalized_bundle_read_failed\"}"); return 1;
    }
    fclose(file);
    gn_mvs_manifest manifest;
    if (!load_bundle(bytes, (size_t)length, &manifest)) {
        free(bytes); puts("{\"status\":\"normalized_bundle_malformed\"}"); return 1;
    }
    gn_instance *instance = NULL;
    if (gn_create(&instance) != GN_STATUS_OK || instance == NULL) {
        free(bytes); puts("{\"status\":\"native_instance_unavailable\"}"); return 1;
    }
    const gn_status load_status = gn_load_mvs(instance, &manifest);
    free(bytes);
    if (load_status != GN_STATUS_OK) {
        gn_destroy(instance); puts("{\"status\":\"normalized_profile_rejected\"}"); return 1;
    }
    for (size_t iteration = 0u; iteration < MAX_RUN_CHUNKS; ++iteration) {
        gn_run_result result;
        const gn_status status = gn_run_mvs(instance, GN_MAX_CYCLE_BUDGET, &result);
        if (status != GN_STATUS_OK || result.reason == GN_RUN_ERROR) {
            gn_destroy(instance); puts("{\"status\":\"native_execution_error\"}"); return 1;
        }
        if (result.reason == GN_RUN_FAULT) {
            printf("{\"status\":\"unsupported_guest_event\",\"guest_executed\":true,"
                   "\"first_unsupported_event\":{\"pc\":%u,\"opcode\":%u}}\n",
                   result.fault_pc, (unsigned)result.instruction_register);
            gn_destroy(instance); return 0;
        }
        if (result.reason == GN_RUN_STOPPED) {
            gn_destroy(instance);
            puts("{\"status\":\"guest_stopped\",\"guest_executed\":true}");
            return 0;
        }
    }
    gn_destroy(instance);
    puts("{\"status\":\"guest_instruction_budget_exhausted\",\"guest_executed\":true}");
    return 0;
}
