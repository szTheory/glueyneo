/* SPDX-License-Identifier: MIT; original persistence diagnostic guest. */
#if !defined(__APPLE__)

#include <stdio.h>

int main(int argc, char **argv) {
    (void)argc;
    (void)argv;
    fputs("save.process.unsupported: Darwin host commit protocol required\n", stderr);
    return 77;
}

#else

#include "glueyneo/glueyneo.h"
#include "save_host.h"
#include "sdk_private.h"

#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

size_t public_save_guest_size(void);
int public_save_guest_build(uint8_t *bundle, size_t capacity);

enum {
    SAVE_BUNDLE_HEADER_BYTES = 16u,
    SAVE_BUNDLE_DESCRIPTOR_BYTES = 12u,
    SAVE_OUTPUT_COUNT = 6u,
    SAVE_FIXTURE_MAX_BYTES = 67108976u
};

static const uint16_t values_a[SAVE_OUTPUT_COUNT] = {
    0x12u, 0x34u, 0x56u, 0x78u, 0x9au, 0xbcu
};
static const uint16_t values_b[SAVE_OUTPUT_COUNT] = {
    0xa1u, 0xb2u, 0xc3u, 0xd4u, 0xe5u, 0xf6u
};
static const uint32_t save_offsets[SAVE_OUTPUT_COUNT] = {
    0u, 1u, 0x1234u, 0x1235u, 0xfffeu, 0xffffu
};

static uint32_t read_u32_be(const uint8_t *bytes) {
    return ((uint32_t)bytes[0] << 24) | ((uint32_t)bytes[1] << 16) |
           ((uint32_t)bytes[2] << 8) | (uint32_t)bytes[3];
}

static int load_guest(gn_instance **out_instance) {
    const size_t bundle_size = public_save_guest_size();
    uint8_t *bundle = bundle_size != 0u ? (uint8_t *)malloc(bundle_size) : NULL;
    if (bundle == NULL || !public_save_guest_build(bundle, bundle_size)) {
        free(bundle);
        return 0;
    }
    gn_mvs_manifest_v3 manifest;
    memset(&manifest, 0, sizeof(manifest));
    manifest.version = GN_MVS_MANIFEST_VERSION_ZOOM;
    manifest.profile = GN_MVS_PROFILE_MSX;
    const uint32_t region_count = read_u32_be(bundle + 12u);
    if (region_count != GN_MVS_V3_MAX_REGIONS) {
        free(bundle);
        return 0;
    }
    size_t cursor = SAVE_BUNDLE_HEADER_BYTES;
    int bios_found = 0;
    for (size_t index = 0u; index < region_count; ++index) {
        const uint32_t role = read_u32_be(bundle + cursor);
        const uint32_t extent = read_u32_be(bundle + cursor + 8u);
        cursor += SAVE_BUNDLE_DESCRIPTOR_BYTES;
        if ((size_t)extent > bundle_size - cursor || role == 0u ||
            role > GN_MVS_V3_MAX_REGIONS) {
            free(bundle);
            return 0;
        }
        gn_mvs_region *region = &manifest.regions[role - 1u];
        region->role = (gn_mvs_region_role)role;
        region->source = bundle + cursor;
        region->source_size = extent;
        region->mapped_size = extent;
        region->layout = GN_MVS_LAYOUT_LINEAR;
        if (role == GN_MVS_REGION_BIOS) bios_found = 1;
        cursor += extent;
    }
    if (cursor != bundle_size || bios_found == 0) {
        free(bundle);
        return 0;
    }
    manifest.region_count = region_count;
    gn_instance *instance = NULL;
    const gn_status created = gn_create(&instance);
    const gn_status loaded = created == GN_STATUS_OK
        ? gn_load_mvs_v3(instance, &manifest) : created;
    free(bundle);
    if (loaded != GN_STATUS_OK) {
        gn_destroy(instance);
        return 0;
    }
    *out_instance = instance;
    return 1;
}

static int guest_output(gn_instance *instance, uint8_t output[SAVE_OUTPUT_COUNT]) {
    gn_run_result result;
    memset(&result, 0, sizeof(result));
    const gn_status status = gn_run_mvs(instance, UINT64_C(5000), &result);
    if (status != GN_STATUS_OK || result.reason == GN_RUN_ERROR ||
        result.reason == GN_RUN_FAULT || result.reason == GN_RUN_STOPPED) {
        fprintf(stderr, "save.runner-execution status=%u reason=%u instructions=%llu elapsed=%llu\n",
            (unsigned)status, (unsigned)result.reason,
            (unsigned long long)result.instructions,
            (unsigned long long)result.elapsed_cycles);
        return 0;
    }
    for (size_t index = 0u; index < SAVE_OUTPUT_COUNT; ++index) {
        if (gn_test_mvs_read_bus8(instance, UINT32_C(0x100000) +
                                  (uint32_t)index, &output[index]) != GN_STATUS_OK)
            return 0;
    }
    return 1;
}

static int guest_save_readback(gn_instance *instance,
                               uint8_t output[SAVE_OUTPUT_COUNT]) {
    for (size_t index = 0u; index < SAVE_OUTPUT_COUNT; ++index) {
        if (gn_test_mvs_read_bus8(instance, UINT32_C(0xd00000) +
                                  save_offsets[index], &output[index]) != GN_STATUS_OK)
            return 0;
    }
    return 1;
}

typedef save_host_outcome host_commit_outcome;
typedef save_host_read_outcome host_read_outcome;
typedef save_host_context host_pending_transaction;

#define HOST_COMMIT_NOT_COMMITTED SAVE_HOST_NOT_COMMITTED
#define HOST_COMMIT_COMMITTED SAVE_HOST_COMMITTED
#define HOST_COMMIT_OUTCOME_UNCERTAIN SAVE_HOST_OUTCOME_UNCERTAIN
#define HOST_COMMIT_UNSUPPORTED SAVE_HOST_UNSUPPORTED
#define HOST_READ_INVALID SAVE_HOST_READ_INVALID
#define HOST_READ_MISSING SAVE_HOST_READ_MISSING
#define HOST_READ_READY SAVE_HOST_READ_READY
#define HOST_READ_NOT_APPLICABLE SAVE_HOST_READ_NOT_APPLICABLE

static int append_stage(char *stages, size_t capacity, const char *stage) {
    const size_t used = strlen(stages);
    const size_t stage_size = strlen(stage);
    const size_t separator = used == 0u ? 0u : 1u;
    if (separator + stage_size >= capacity - used) return 0;
    if (separator != 0u) stages[used] = ',';
    memcpy(stages + used + separator, stage, stage_size + 1u);
    return 1;
}

static int write_all(int descriptor, const uint8_t *bytes, size_t length) {
    size_t written = 0u;
    while (written < length) {
        const ssize_t count = write(descriptor, bytes + written, length - written);
        if (count < 0 && errno == EINTR) continue;
        if (count <= 0) return 0;
        written += (size_t)count;
    }
    return 1;
}

static int write_fixture_file(const char *path) {
    const size_t size = public_save_guest_size();
    if (path == NULL || path[0] == '\0' || strlen(path) >= 4096u ||
        size == 0u || size > SAVE_FIXTURE_MAX_BYTES) {
        fputs("save.fixture-setup failed\n", stderr);
        return 2;
    }
    uint8_t *bundle = (uint8_t *)malloc(size);
    if (bundle == NULL || !public_save_guest_build(bundle, size)) {
        free(bundle);
        fputs("save.fixture-build failed\n", stderr);
        return 2;
    }
    const int descriptor = open(path, O_WRONLY | O_CREAT | O_EXCL, 0600);
    if (descriptor < 0) {
        free(bundle);
        fputs("save.fixture-open failed\n", stderr);
        return 2;
    }
    const int write_succeeded = write_all(descriptor, bundle, size);
    const int close_succeeded = close(descriptor) == 0;
    if (write_succeeded == 0 || close_succeeded == 0) {
        (void)unlink(path);
        free(bundle);
        fputs("save.fixture-write failed\n", stderr);
        return 2;
    }
    free(bundle);
    return 0;
}

static const char *host_read_outcome_name(host_read_outcome outcome) {
    switch (outcome) {
        case HOST_READ_MISSING: return "missing";
        case HOST_READ_READY: return "readable";
        case HOST_READ_NOT_APPLICABLE: return "not_applicable";
        case HOST_READ_INVALID:
        default: return "invalid";
    }
}

static host_commit_outcome host_resolve_uncertain_transaction(
    host_pending_transaction *transaction, const char *initial_action,
    char *resolution, size_t resolution_capacity) {
    if (transaction == NULL || transaction->unresolved == 0 ||
        resolution == NULL || resolution_capacity < sizeof("discard"))
        return HOST_COMMIT_OUTCOME_UNCERTAIN;
    fputs("save.host-outcome=outcome_uncertain; type retry or discard to resolve\n",
          stderr);
    fflush(stderr);
    int use_initial_action = initial_action != NULL;
    unsigned actions = 0u;
    while (transaction->unresolved != 0 && actions < SAVE_HOST_MAX_ATTEMPTS) {
        char action[32] = {0};
        if (use_initial_action != 0) {
            const size_t action_length = strlen(initial_action);
            if (action_length >= sizeof(action)) break;
            memcpy(action, initial_action, action_length + 1u);
            use_initial_action = 0;
        } else if (fgets(action, (int)sizeof(action), stdin) == NULL) {
            clearerr(stdin);
            break;
        }
        ++actions;
        char *newline = strchr(action, '\n');
        if (newline != NULL) *newline = '\0';
        if (strcmp(action, "retry") == 0) {
            if (save_host_reconcile(transaction) == HOST_COMMIT_COMMITTED) {
                memcpy(resolution, "retry", sizeof("retry"));
                return HOST_COMMIT_COMMITTED;
            }
            fputs("save.host-retry=still_uncertain; type retry or discard\n", stderr);
            fflush(stderr);
        } else if (strcmp(action, "discard") == 0) {
            transaction->unresolved = 0;
            transaction->active = 0;
            memcpy(resolution, "discard", sizeof("discard"));
            return HOST_COMMIT_OUTCOME_UNCERTAIN;
        } else {
            fputs("save.host-resolution=invalid; type retry or discard\n", stderr);
            fflush(stderr);
        }
    }
    if (actions >= SAVE_HOST_MAX_ATTEMPTS && transaction->unresolved != 0)
        fputs("save.host-resolution=attempt-bound; transaction remains blocked\n",
              stderr);
    return HOST_COMMIT_OUTCOME_UNCERTAIN;
}

static int new_scope(gn_mvs_save_scope_v1 *scope) {
    if (scope == NULL) return 0;
    memset(scope, 0, sizeof(*scope));
    scope->size = (uint32_t)sizeof(*scope);
    arc4random_buf(scope->scope, sizeof(scope->scope));
    uint8_t aggregate = 0u;
    for (size_t index = 0u; index < sizeof(scope->scope); ++index)
        aggregate |= scope->scope[index];
    if (aggregate == 0u) scope->scope[0] = 1u;
    return 1;
}

static int query_save(const gn_instance *instance, gn_mvs_save_info_v1 *info) {
    memset(info, 0, sizeof(*info));
    return gn_mvs_save_query_v1(instance, info, sizeof(*info), NULL, 0u) ==
        GN_STATUS_OK && info->supported != 0u;
}

static int compatibility_has_save_id(const gn_instance *instance) {
    gn_state_compatibility_info_v1 info;
    memset(&info, 0, sizeof(info));
    return gn_state_compatibility_v1(instance, &info, sizeof(info)) ==
        GN_STATUS_OK && info.durable_save_id == GN_MVS_SAVE_ID_V1;
}

static int export_rejection_is_atomic(gn_instance *instance, uint8_t *buffer) {
    gn_mvs_save_receipt_v1 receipt;
    memset(&receipt, 0xa5, sizeof(receipt));
    memset(buffer, 0xa5, GN_MVS_SAVE_ENVELOPE_V1_BYTES);
    size_t written = 123u;
    const gn_status capacity_status = gn_mvs_save_export_v1(instance, buffer,
        GN_MVS_SAVE_ENVELOPE_V1_BYTES - 1u, &written, &receipt,
        sizeof(receipt), NULL, 0u);
    if (capacity_status != GN_STATUS_INVALID_ARGUMENT || written != 0u ||
        buffer[0] != 0xa5u || buffer[GN_MVS_SAVE_ENVELOPE_V1_BYTES - 1u] != 0xa5u)
        return 0;
    for (size_t index = 0u; index < sizeof(receipt); ++index)
        if (((const uint8_t *)&receipt)[index] != 0xa5u) return 0;

    memset(buffer, 0x5au, GN_MVS_SAVE_ENVELOPE_V1_BYTES);
    memset(&receipt, 0x3cu, sizeof(receipt));
    const gn_status alias_status = gn_mvs_save_export_v1(instance, buffer,
        GN_MVS_SAVE_ENVELOPE_V1_BYTES, (size_t *)buffer, &receipt,
        sizeof(receipt), NULL, 0u);
    if (alias_status != GN_STATUS_INVALID_ARGUMENT || buffer[0] != 0x5au ||
        buffer[sizeof(size_t) - 1u] != 0x5au ||
        buffer[GN_MVS_SAVE_ENVELOPE_V1_BYTES - 1u] != 0x5au) return 0;
    for (size_t index = 0u; index < sizeof(receipt); ++index)
        if (((const uint8_t *)&receipt)[index] != 0x3cu) return 0;
    return 1;
}

static int corrupt_import_is_atomic(gn_instance *instance, uint8_t *bytes) {
    const uintptr_t save_address = gn_test_mvs_save_ram_address(instance);
    if (save_address == (uintptr_t)0) return 0;
    const uint8_t saved_digest_byte = bytes[64];
    bytes[64] ^= 1u;
    gn_mvs_save_detail_v1 detail;
    memset(&detail, 0, sizeof(detail));
    const gn_status status = gn_mvs_save_import_baseline_v1(instance, bytes,
        GN_MVS_SAVE_ENVELOPE_V1_BYTES, &detail, sizeof(detail));
    bytes[64] = saved_digest_byte;
    gn_mvs_save_info_v1 info;
    uint8_t first_byte = 0xffu;
    return status == GN_STATUS_INVALID_MEDIA &&
        detail.reason == GN_MVS_SAVE_REASON_INTEGRITY &&
        gn_test_mvs_save_ram_address(instance) == save_address &&
        gn_test_mvs_read_bus8(instance, UINT32_C(0xd00000), &first_byte) ==
            GN_STATUS_OK && first_byte == 0u && query_save(instance, &info) &&
        info.dirty == 0u && info.baseline_known == 0u &&
        info.startup_import_allowed != 0u;
}

static const char *host_outcome_name(host_commit_outcome outcome) {
    switch (outcome) {
        case HOST_COMMIT_NOT_COMMITTED: return "not_committed";
        case HOST_COMMIT_COMMITTED: return "committed";
        case HOST_COMMIT_OUTCOME_UNCERTAIN: return "outcome_uncertain";
        case HOST_COMMIT_UNSUPPORTED: return "unsupported";
        default: return "unknown";
    }
}

static int prepare_latest_export(
    gn_instance *instance, uint8_t *save_bytes,
    gn_mvs_save_receipt_v1 *out_receipt,
    gn_mvs_save_info_v1 *out_export_info,
    int *out_reset_preserved_sram, int *out_restore_branched,
    int *out_stale_ack_preserved_dirty) {
    size_t state_capacity = 0u;
    size_t state_written = 0u;
    if (gn_state_capacity_v1(instance, &state_capacity) != GN_STATUS_OK ||
        state_capacity == 0u) return 0;
    uint8_t *state = (uint8_t *)malloc(state_capacity);
    if (state == NULL) return 0;
    gn_status status = gn_state_capture_v1(instance, state, state_capacity,
                                            &state_written, NULL, 0u);
    if (status == GN_STATUS_OK && state_written != state_capacity)
        status = GN_STATUS_INVALID_MEDIA;
    gn_mvs_save_receipt_v1 old_receipt;
    memset(&old_receipt, 0, sizeof(old_receipt));
    size_t save_written = 0u;
    if (status == GN_STATUS_OK)
        status = gn_mvs_save_export_v1(instance, save_bytes,
            GN_MVS_SAVE_ENVELOPE_V1_BYTES, &save_written, &old_receipt,
            sizeof(old_receipt), NULL, 0u);
    if (status != GN_STATUS_OK || save_written != GN_MVS_SAVE_ENVELOPE_V1_BYTES) {
        free(state);
        return 0;
    }

    gn_mvs_save_info_v1 after_reset;
    uint8_t values_before_reset[SAVE_OUTPUT_COUNT] = {0};
    uint8_t reset_values[SAVE_OUTPUT_COUNT] = {0};
    const int read_before_reset = guest_save_readback(instance,
                                                       values_before_reset);
    *out_reset_preserved_sram = read_before_reset != 0 &&
        gn_reset(instance) == GN_STATUS_OK &&
        query_save(instance, &after_reset) && after_reset.dirty != 0u &&
        after_reset.startup_import_allowed == 0u &&
        guest_save_readback(instance, reset_values) &&
        memcmp(values_before_reset, reset_values, sizeof(reset_values)) == 0;
    if (*out_reset_preserved_sram == 0) {
        free(state);
        return 0;
    }

    status = gn_state_restore_v1(instance, state, state_written, NULL, 0u);
    free(state);
    if (status != GN_STATUS_OK) return 0;
    *out_restore_branched = 1;
    gn_mvs_save_detail_v1 detail;
    memset(&detail, 0, sizeof(detail));
    const gn_status stale_status = gn_mvs_save_ack_v1(
        instance, &old_receipt, sizeof(old_receipt), &detail, sizeof(detail));
    gn_mvs_save_info_v1 after_stale;
    *out_stale_ack_preserved_dirty = stale_status == GN_STATUS_INVALID_STATE &&
        detail.reason == GN_MVS_SAVE_REASON_STALE_RECEIPT &&
        query_save(instance, &after_stale) && after_stale.dirty != 0u;
    if (*out_stale_ack_preserved_dirty == 0) return 0;

    save_written = 0u;
    memset(out_receipt, 0, sizeof(*out_receipt));
    status = gn_mvs_save_export_v1(instance, save_bytes,
        GN_MVS_SAVE_ENVELOPE_V1_BYTES, &save_written, out_receipt,
        sizeof(*out_receipt), NULL, 0u);
    if (status != GN_STATUS_OK || save_written != GN_MVS_SAVE_ENVELOPE_V1_BYTES ||
        out_receipt->mutation_sequence != SAVE_OUTPUT_COUNT - 2u ||
        out_receipt->restore_branch != 1u || out_receipt->export_sequence != 2u ||
        !query_save(instance, out_export_info)) return 0;
    return out_export_info->dirty != 0u;
}

static void print_hex(const char *name, const uint8_t *bytes, size_t length) {
    printf("%s=", name);
    for (size_t index = 0u; index < length; ++index) printf("%02x", bytes[index]);
    fputc('\n', stdout);
}

static void print_observation(const char *mode,
                              host_read_outcome startup_read,
                              const gn_mvs_save_info_v1 *before,
                              const gn_mvs_save_info_v1 *after_import,
                              const gn_mvs_save_info_v1 *after_guest,
                              const gn_mvs_save_info_v1 *after_export,
                              const gn_mvs_save_info_v1 *after_ack,
                              const gn_mvs_save_receipt_v1 *receipt,
                              int reset_preserved_sram,
                              int restore_branched,
                              int stale_ack_preserved_dirty,
                              int duplicate_ack_rejected,
                              int closed_import_rejected,
                              const char *host_outcome,
                              const char *host_resolution,
                              const char *host_failed_stage,
                              uint32_t barrier_probe_mask,
                              int obsolete_stale_ack_rejected,
                              const char *obsolete_publication_outcome,
                              const char *stages) {
    printf("SAVE_OBSERVATION {\"mode\":\"%s\",\"scope_bytes\":%zu,"
           "\"receipt_bytes\":%zu,\"info_bytes\":%zu,\"detail_bytes\":%zu,"
           "\"envelope_bytes\":%zu,\"header_bytes\":%zu,\"payload_bytes\":%zu,"
           "\"before_dirty\":%u,\"before_baseline_known\":%u,"
           "\"before_startup_import_allowed\":%u,"
           "\"after_import_dirty\":%u,\"after_import_baseline_known\":%u,"
           "\"after_import_startup_import_allowed\":%u,"
           "\"after_guest_dirty\":%u,\"after_guest_baseline_known\":%u,"
           "\"after_guest_startup_import_allowed\":%u,"
           "\"after_export_dirty\":%u,\"after_ack_dirty\":%u,"
           "\"after_ack_baseline_known\":%u,"
           "\"receipt_mutation_sequence\":%llu,"
           "\"receipt_restore_branch\":%llu,"
           "\"receipt_export_sequence\":%llu,"
           "\"reset_preserved_sram\":%d,\"restore_branched\":%d,"
           "\"stale_ack_preserved_dirty\":%d,"
           "\"duplicate_ack_rejected\":%d,"
           "\"closed_import_rejected\":%d,\"startup_read_result\":\"%s\","
           "\"host_outcome\":\"%s\",\"host_resolution\":\"%s\","
           "\"failed_stage\":\"%s\",\"barrier_probe_mask\":%u,"
           "\"obsolete_stale_ack_rejected\":%d,"
           "\"obsolete_publication_outcome\":\"%s\",\"stages\":\"%s\"}\n",
        mode, sizeof(gn_mvs_save_scope_v1), sizeof(gn_mvs_save_receipt_v1),
        sizeof(gn_mvs_save_info_v1), sizeof(gn_mvs_save_detail_v1),
        GN_MVS_SAVE_ENVELOPE_V1_BYTES, GN_MVS_SAVE_HEADER_V1_BYTES,
        GN_MVS_SAVE_PAYLOAD_V1_BYTES, before->dirty, before->baseline_known,
        before->startup_import_allowed, after_import->dirty,
        after_import->baseline_known, after_import->startup_import_allowed,
        after_guest->dirty, after_guest->baseline_known,
        after_guest->startup_import_allowed, after_export->dirty,
        after_ack->dirty, after_ack->baseline_known,
        (unsigned long long)(receipt != NULL ? receipt->mutation_sequence : 0u),
        (unsigned long long)(receipt != NULL ? receipt->restore_branch : 0u),
        (unsigned long long)(receipt != NULL ? receipt->export_sequence : 0u),
        reset_preserved_sram, restore_branched, stale_ack_preserved_dirty,
        duplicate_ack_rejected, closed_import_rejected,
        host_read_outcome_name(startup_read), host_outcome, host_resolution,
        host_failed_stage, barrier_probe_mask, obsolete_stale_ack_rejected,
        obsolete_publication_outcome, stages);
}

static int expected_guest_output(int use_b, uint8_t output[SAVE_OUTPUT_COUNT]) {
    const uint16_t *values = use_b != 0 ? values_b : values_a;
    for (size_t index = 0u; index < SAVE_OUTPUT_COUNT; ++index)
        output[index] = (uint8_t)values[index];
    return 1;
}

typedef struct {
    const char *target_stage;
    int notify_fd;
    int release_fd;
    int failed;
    int probe_barriers;
    uint32_t barrier_mask;
    int observed_active;
    int observed_publication_in_flight;
    int observed_unresolved;
    int destroy_owner_preserved;
    save_host_context *transaction;
    const uint8_t *state_bytes;
    size_t state_length;
} save_stage_gate;

static uint32_t probe_host_transition_barriers(save_stage_gate *gate) {
    if (gate == NULL || gate->transaction == NULL || gate->state_bytes == NULL ||
        gate->state_length == 0u) return 0u;
    uint32_t mask = 0u;
    gn_state_detail_v1 state_detail;
    memset(&state_detail, 0, sizeof(state_detail));
    if (save_host_restore(gate->transaction, gate->state_bytes,
            gate->state_length, &state_detail, sizeof(state_detail)) ==
            GN_STATUS_INVALID_STATE) mask |= UINT32_C(1) << 0;

    gn_mvs_save_scope_v1 scope;
    gn_mvs_save_detail_v1 detail;
    memset(&detail, 0, sizeof(detail));
    if (new_scope(&scope) && save_host_renew_scope(gate->transaction, &scope,
            sizeof(scope), &detail, sizeof(detail)) == GN_STATUS_INVALID_STATE)
        mask |= UINT32_C(1) << 1;

    if (!save_host_change_slot(gate->transaction,
                               "blocked-transition-slot.gnsave"))
        mask |= UINT32_C(1) << 2;
    if (!save_host_replace(gate->transaction,
            gate->transaction->immutable_bytes,
            gate->transaction->bytes_length, &gate->transaction->receipt,
            gate->transaction->owner)) mask |= UINT32_C(1) << 3;

    gn_mvs_save_lifecycle_result_v1 result;
    memset(&result, 0, sizeof(result));
    memset(&detail, 0, sizeof(detail));
    if (save_host_unload(gate->transaction,
            GN_MVS_SAVE_LIFECYCLE_ALLOW_DISCARD, &result, sizeof(result),
            &detail, sizeof(detail)) == GN_STATUS_INVALID_STATE)
        mask |= UINT32_C(1) << 4;

    gn_instance *const original_owner = gate->transaction->owner;
    memset(&result, 0, sizeof(result));
    memset(&detail, 0, sizeof(detail));
    const gn_status destroy_status = save_host_destroy(gate->transaction,
        GN_MVS_SAVE_LIFECYCLE_ALLOW_DISCARD, &result, sizeof(result),
        &detail, sizeof(detail));
    gate->destroy_owner_preserved = destroy_status == GN_STATUS_INVALID_STATE &&
        gate->transaction->owner == original_owner;
    if (gate->destroy_owner_preserved != 0)
        mask |= UINT32_C(1) << 5;
    return mask;
}

static uint32_t probe_failed_commit_transition_barriers(save_stage_gate *gate) {
    if (gate == NULL || gate->transaction == NULL || gate->state_bytes == NULL ||
        gate->state_length == 0u) return 0u;
    uint32_t mask = 0u;
    gn_state_detail_v1 state_detail;
    memset(&state_detail, 0, sizeof(state_detail));
    if (save_host_restore(gate->transaction, gate->state_bytes,
            gate->state_length, &state_detail, sizeof(state_detail)) ==
            GN_STATUS_INVALID_STATE) mask |= UINT32_C(1) << 0;

    gn_mvs_save_scope_v1 scope;
    gn_mvs_save_detail_v1 detail;
    memset(&detail, 0, sizeof(detail));
    if (new_scope(&scope) && save_host_renew_scope(gate->transaction, &scope,
            sizeof(scope), &detail, sizeof(detail)) == GN_STATUS_INVALID_STATE)
        mask |= UINT32_C(1) << 1;
    if (!save_host_change_slot(gate->transaction,
                               "blocked-transition-slot.gnsave"))
        mask |= UINT32_C(1) << 2;
    if (!save_host_replace(gate->transaction,
            gate->transaction->immutable_bytes,
            gate->transaction->bytes_length, &gate->transaction->receipt,
            gate->transaction->owner)) mask |= UINT32_C(1) << 3;

    gn_mvs_save_lifecycle_result_v1 result;
    memset(&result, 0, sizeof(result));
    memset(&detail, 0, sizeof(detail));
    if (save_host_unload(gate->transaction,
            GN_MVS_SAVE_LIFECYCLE_REQUIRE_RESOLVED, &result, sizeof(result),
            &detail, sizeof(detail)) == GN_STATUS_INVALID_STATE)
        mask |= UINT32_C(1) << 4;

    gn_instance *const original_owner = gate->transaction->owner;
    memset(&result, 0, sizeof(result));
    memset(&detail, 0, sizeof(detail));
    const gn_status destroy_status = save_host_destroy(gate->transaction,
        GN_MVS_SAVE_LIFECYCLE_REQUIRE_RESOLVED, &result, sizeof(result),
        &detail, sizeof(detail));
    gate->destroy_owner_preserved = destroy_status == GN_STATUS_INVALID_STATE &&
        gate->transaction->owner == original_owner;
    if (gate->destroy_owner_preserved != 0)
        mask |= UINT32_C(1) << 5;
    return mask;
}

static int stage_write_all(int descriptor, const char *bytes, size_t length) {
    size_t written = 0u;
    unsigned attempts = 0u;
    while (written < length && attempts < 8u) {
        const ssize_t count = write(descriptor, bytes + written, length - written);
        ++attempts;
        if (count < 0 && errno == EINTR) continue;
        if (count <= 0) return 0;
        written += (size_t)count;
    }
    return written == length;
}

static void save_stage_gate_callback(void *opaque, const char *stage) {
    save_stage_gate *gate = (save_stage_gate *)opaque;
    if (gate == NULL || gate->target_stage == NULL || stage == NULL ||
        strcmp(stage, gate->target_stage) != 0) return;
    if (gate->probe_barriers != 0) {
        gate->observed_active = gate->transaction->active;
        gate->observed_publication_in_flight =
            gate->transaction->publication_in_flight;
        gate->observed_unresolved = gate->transaction->unresolved;
        gate->barrier_mask = probe_host_transition_barriers(gate);
        printf("SAVE_BARRIER_STATE {\"active\":%d,\"publication_in_flight\":%d,"
               "\"unresolved\":%d,\"barrier_mask\":%u,"
               "\"destroy_owner_preserved\":%d}\n",
               gate->observed_active, gate->observed_publication_in_flight,
               gate->observed_unresolved, gate->barrier_mask,
               gate->destroy_owner_preserved);
        fflush(stdout);
    }
    const size_t stage_length = strlen(stage);
    char message[64];
    if (stage_length + 1u >= sizeof(message)) {
        gate->failed = 1;
        return;
    }
    memcpy(message, stage, stage_length);
    message[stage_length] = '\n';
    if (!stage_write_all(gate->notify_fd, message, stage_length + 1u)) {
        gate->failed = 1;
        return;
    }
    char release = '\0';
    ssize_t count;
    do {
        count = read(gate->release_fd, &release, 1u);
    } while (count < 0 && errno == EINTR);
    if (count != 1 || release != 'R') gate->failed = 1;
}

static int run_process(const char *mode, int use_b, const char *save_path,
                       int skip_import, int false_ack_control,
                       int barrier_ordering, int obsolete_publication_control,
                       int disk_latest_branch_control,
                       int print_immutable_export,
                       int probe_failed_barriers,
                       int retry_failed_commit,
                       int expect_invalid_authoritative,
                       const char *stage_name, int stage_notify_fd,
                       int stage_release_fd,
                       const char *resolve_action,
                       const save_host_faults *faults) {
    gn_instance *instance = NULL;
    const int writer = strcmp(mode, "write") == 0;
    if ((!writer && strcmp(mode, "read") != 0) || save_path == NULL ||
        strlen(save_path) >= 4096u ||
        (stage_name != NULL && writer == 0) ||
        (barrier_ordering != 0 && (writer == 0 ||
            (strcmp(stage_name, "file-close") != 0 &&
             strcmp(stage_name, "unresolved") != 0))) ||
        (obsolete_publication_control != 0 && writer == 0) ||
        (disk_latest_branch_control != 0 && writer != 0) ||
        (print_immutable_export != 0 && writer == 0) ||
        (expect_invalid_authoritative != 0 &&
         (writer != 0 || skip_import != 0)) ||
        (false_ack_control != 0 && barrier_ordering != 0) ||
        !load_guest(&instance)) {
        fputs("save.runner-setup failed\n", stderr);
        return 2;
    }
    if (!compatibility_has_save_id(instance)) {
        gn_destroy(instance);
        fputs("save.compatibility-identity failed\n", stderr);
        return 2;
    }
    if (writer != 0 && gn_set_mvs_inputs(instance,
            use_b != 0 ? GN_MVS_INPUT_P1_B : GN_MVS_INPUT_P1_A) != GN_STATUS_OK) {
        gn_destroy(instance);
        fputs("save.input-setup failed\n", stderr);
        return 2;
    }
    gn_mvs_save_scope_v1 scope;
    gn_mvs_save_detail_v1 detail;
    memset(&detail, 0, sizeof(detail));
    if (!new_scope(&scope) ||
        gn_mvs_save_scope_renew_v1(instance, &scope, sizeof(scope),
                                   &detail, sizeof(detail)) != GN_STATUS_OK) {
        gn_destroy(instance);
        fputs("save.scope-bind failed\n", stderr);
        return 2;
    }
    gn_mvs_save_info_v1 before, after_import, after_guest, after_export, after_ack;
    if (!query_save(instance, &before)) {
        gn_destroy(instance);
        fputs("save.query failed\n", stderr);
        return 2;
    }
    after_import = before;
    after_guest = before;
    after_export = before;
    after_ack = before;
    char stages[SAVE_HOST_STAGE_CAPACITY] = {0};
    host_commit_outcome outcome = HOST_COMMIT_NOT_COMMITTED;
    gn_mvs_save_receipt_v1 receipt;
    memset(&receipt, 0, sizeof(receipt));
    host_pending_transaction pending_transaction;
    memset(&pending_transaction, 0, sizeof(pending_transaction));
    save_stage_gate stage_gate;
    memset(&stage_gate, 0, sizeof(stage_gate));
    stage_gate.target_stage = stage_name;
    stage_gate.notify_fd = stage_notify_fd;
    stage_gate.release_fd = stage_release_fd;
    stage_gate.probe_barriers = barrier_ordering;
    stage_gate.transaction = &pending_transaction;
    uint8_t *barrier_state = NULL;
    size_t barrier_state_length = 0u;
    uint32_t barrier_probe_mask = 0u;
    int obsolete_stale_ack_rejected = 0;
    host_commit_outcome obsolete_publication_outcome = HOST_COMMIT_NOT_COMMITTED;
    char host_resolution[16] = "none";
    int reset_preserved_sram = 0;
    int restore_branched = 0;
    int stale_ack_preserved_dirty = 0;
    int duplicate_ack_rejected = 0;
    int closed_import_rejected = 0;
    host_read_outcome startup_read = HOST_READ_NOT_APPLICABLE;
    uint8_t *save_bytes = (uint8_t *)malloc(GN_MVS_SAVE_ENVELOPE_V1_BYTES);
    if (save_bytes == NULL) {
        gn_destroy(instance);
        fputs("save.runner-allocation failed\n", stderr);
        return 2;
    }
    if (!export_rejection_is_atomic(instance, save_bytes)) {
        free(save_bytes);
        gn_destroy(instance);
        fputs("save.export-rejection-atomic failed\n", stderr);
        return 4;
    }

    if (writer == 0) {
        startup_read = save_host_read_authoritative(save_path, save_bytes,
                                                GN_MVS_SAVE_ENVELOPE_V1_BYTES);
        if (startup_read == HOST_READ_INVALID) {
            free(save_bytes);
            gn_destroy(instance);
            fputs("save.authoritative-read failed outcome=invalid\n", stderr);
            return 2;
        }
        (void)append_stage(stages, sizeof(stages),
                           startup_read == HOST_READ_MISSING ? "missing" : "read");
        if (startup_read == HOST_READ_READY &&
            expect_invalid_authoritative == 0) {
            if (!corrupt_import_is_atomic(instance, save_bytes)) {
                free(save_bytes);
                gn_destroy(instance);
                fputs("save.import-validation-atomic failed\n", stderr);
                return 4;
            }
        }
        if (skip_import == 0 && startup_read == HOST_READ_READY) {
            if (gn_mvs_save_import_baseline_v1(instance, save_bytes,
                    GN_MVS_SAVE_ENVELOPE_V1_BYTES, &detail,
                    sizeof(detail)) != GN_STATUS_OK) {
                fprintf(stderr, "save.baseline-import failed host-read=readable "
                    "outcome=invalid reason=%u (%s)\n",
                    (unsigned)detail.reason,
                    gn_mvs_save_reason_string(detail.reason));
                free(save_bytes);
                gn_destroy(instance);
                return 2;
            }
            (void)append_stage(stages, sizeof(stages), "import");
        }
        if (!query_save(instance, &after_import)) {
            free(save_bytes);
            gn_destroy(instance);
            fputs("save.query failed\n", stderr);
            return 2;
        }
    }

    if (writer != 0 && (barrier_ordering != 0 || probe_failed_barriers != 0)) {
        if (gn_state_capacity_v1(instance, &barrier_state_length) !=
                GN_STATUS_OK || barrier_state_length == 0u) {
            free(save_bytes);
            gn_destroy(instance);
            fputs("save.barrier-state-capacity failed\n", stderr);
            return 4;
        }
        barrier_state = (uint8_t *)malloc(barrier_state_length);
        size_t barrier_state_written = 0u;
        if (barrier_state == NULL || gn_state_capture_v1(instance,
                barrier_state, barrier_state_length,
                &barrier_state_written, NULL, 0u) != GN_STATUS_OK ||
            barrier_state_written != barrier_state_length) {
            free(barrier_state);
            free(save_bytes);
            gn_destroy(instance);
            fputs("save.barrier-state-capture failed\n", stderr);
            return 4;
        }
        stage_gate.state_bytes = barrier_state;
        stage_gate.state_length = barrier_state_length;
    }

    uint8_t output[SAVE_OUTPUT_COUNT] = {0};
    int ok = guest_output(instance, output);
    if (!ok) {
        free(barrier_state);
        free(save_bytes);
        gn_destroy(instance);
        fputs("save.runner-execution failed\n", stderr);
        return 3;
    }
    print_hex("save.guest-output", output, sizeof(output));
    printf("save.process-id=%ld\n", (long)getpid());
    if (writer != 0) {
        uint8_t written[SAVE_OUTPUT_COUNT] = {0};
        const uint16_t *values = use_b != 0 ? values_b : values_a;
        uint8_t expected_write[SAVE_OUTPUT_COUNT];
        for (size_t index = 0u; index < SAVE_OUTPUT_COUNT; ++index)
            expected_write[index] = (uint8_t)values[index];
        ok = guest_save_readback(instance, written) &&
            memcmp(written, expected_write, sizeof(written)) == 0;
        if (ok) print_hex("save.writer-readback", written, sizeof(written));
    }
    if (!ok || !query_save(instance, &after_guest)) {
        free(barrier_state);
        free(save_bytes);
        gn_destroy(instance);
        fputs("save.guest-write failed\n", stderr);
        return 3;
    }

    if (writer != 0) {
        if (!prepare_latest_export(instance, save_bytes, &receipt,
                &after_export, &reset_preserved_sram, &restore_branched,
                &stale_ack_preserved_dirty)) {
            free(barrier_state);
            free(save_bytes);
            gn_destroy(instance);
            fputs("save.ownership-lineage failed\n", stderr);
            return 4;
        }
        if (print_immutable_export != 0)
            print_hex("save.immutable-export", save_bytes,
                      GN_MVS_SAVE_ENVELOPE_V1_BYTES);
        if (!save_host_context_init(&pending_transaction, save_path, save_bytes,
                GN_MVS_SAVE_ENVELOPE_V1_BYTES, &receipt, instance, faults)) {
            free(barrier_state);
            free(save_bytes);
            gn_destroy(instance);
            fputs("save.transaction-setup failed\n", stderr);
            return 4;
        }
        if (stage_name != NULL)
            save_host_set_stage_callback(&pending_transaction,
                save_stage_gate_callback, &stage_gate);
        outcome = save_host_commit(&pending_transaction);
        if (outcome == HOST_COMMIT_OUTCOME_UNCERTAIN &&
            stage_name != NULL && strcmp(stage_name, "unresolved") == 0)
            save_stage_gate_callback(&stage_gate, "unresolved");
        barrier_probe_mask = stage_gate.barrier_mask;
        if (stage_gate.failed != 0) {
            free(barrier_state);
            free(save_bytes);
            gn_destroy(instance);
            fputs("save.stage-gate failed\n", stderr);
            return 5;
        }
        if (probe_failed_barriers != 0 &&
            outcome == HOST_COMMIT_NOT_COMMITTED) {
            stage_gate.observed_active = pending_transaction.active;
            stage_gate.observed_publication_in_flight =
                pending_transaction.publication_in_flight;
            stage_gate.observed_unresolved = pending_transaction.unresolved;
            const int observed_commit_failed = pending_transaction.commit_failed;
            barrier_probe_mask = probe_failed_commit_transition_barriers(&stage_gate);
            if (retry_failed_commit != 0) {
                outcome = save_host_commit(&pending_transaction);
                (void)query_save(instance, &after_ack);
                printf("SAVE_FAILED_RETRY_STATE {\"retry_outcome\":\"%s\","
                       "\"commit_failed\":%d,\"transition_ready\":%d,"
                       "\"after_ack_dirty\":%u}\n",
                       host_outcome_name(outcome), pending_transaction.commit_failed,
                       save_host_before_transition(&pending_transaction),
                       (unsigned)after_ack.dirty);
            } else {
                gn_mvs_save_lifecycle_result_v1 discard_result;
                gn_mvs_save_detail_v1 discard_detail;
                memset(&discard_result, 0, sizeof(discard_result));
                memset(&discard_detail, 0, sizeof(discard_detail));
                const gn_status discard_status = save_host_unload(
                    &pending_transaction, GN_MVS_SAVE_LIFECYCLE_ALLOW_DISCARD,
                    &discard_result, sizeof(discard_result), &discard_detail,
                    sizeof(discard_detail));
                printf("SAVE_FAILED_BARRIER_STATE {\"active\":%d,"
                       "\"commit_failed\":%d,\"unresolved\":%d,"
                       "\"barrier_mask\":%u,\"explicit_discard\":\"%s\","
                       "\"discarded_pending\":%u,"
                       "\"after_discard_transition_ready\":%d}\n",
                       stage_gate.observed_active, observed_commit_failed,
                       stage_gate.observed_unresolved, barrier_probe_mask,
                       discard_status == GN_STATUS_OK ? "ok" : "failed",
                       discard_result.discarded_pending,
                       save_host_before_transition(&pending_transaction));
            }
            fflush(stdout);
        }
        if (false_ack_control != 0 && outcome != HOST_COMMIT_COMMITTED) {
            uint8_t readable[GN_MVS_SAVE_ENVELOPE_V1_BYTES];
            const save_host_read_outcome read_outcome =
                save_host_read_authoritative(save_path, readable, sizeof(readable));
            if (read_outcome == SAVE_HOST_READ_READY &&
                gn_mvs_save_ack_v1(instance, &pending_transaction.receipt,
                    sizeof(pending_transaction.receipt), &detail,
                    sizeof(detail)) == GN_STATUS_OK) {
                fputs("ASSERTION FAILED save.no-false-ack\n", stderr);
                free(barrier_state);
                free(save_bytes);
                gn_destroy(instance);
                return 1;
            }
        }
        if (false_ack_control == 0 && outcome == HOST_COMMIT_OUTCOME_UNCERTAIN) {
            outcome = host_resolve_uncertain_transaction(&pending_transaction,
                resolve_action, host_resolution, sizeof(host_resolution));
        }
        (void)snprintf(stages, sizeof(stages), "%s", pending_transaction.stages);
        if (outcome == HOST_COMMIT_COMMITTED) {
            const gn_status duplicate_status = gn_mvs_save_ack_v1(
                pending_transaction.owner, &pending_transaction.receipt,
                sizeof(pending_transaction.receipt), &detail, sizeof(detail));
            duplicate_ack_rejected = duplicate_status == GN_STATUS_INVALID_STATE &&
                detail.reason == GN_MVS_SAVE_REASON_RECEIPT_CONSUMED;
            (void)query_save(instance, &after_ack);
        } else {
            after_ack = after_export;
        }
        if (barrier_ordering != 0 && outcome == HOST_COMMIT_COMMITTED) {
            const uint32_t all_barriers = (UINT32_C(1) << 6) - 1u;
            if (barrier_probe_mask != all_barriers) {
                free(barrier_state);
                free(save_bytes);
                gn_destroy(instance);
                fputs("save.transition-barrier-probe failed\n", stderr);
                return 4;
            }
            gn_state_detail_v1 state_detail;
            memset(&state_detail, 0, sizeof(state_detail));
            if (save_host_restore(&pending_transaction, barrier_state,
                    barrier_state_length, &state_detail,
                    sizeof(state_detail)) != GN_STATUS_OK ||
                gn_set_mvs_inputs(instance, GN_MVS_INPUT_P1_B) != GN_STATUS_OK) {
                free(barrier_state);
                free(save_bytes);
                gn_destroy(instance);
                fputs("save.restored-branch-b-setup failed\n", stderr);
                return 4;
            }
            uint8_t branch_output[SAVE_OUTPUT_COUNT] = {0};
            uint8_t expected_b[SAVE_OUTPUT_COUNT];
            (void)expected_guest_output(1, expected_b);
            if (!guest_output(instance, output) ||
                !guest_save_readback(instance, branch_output) ||
                memcmp(branch_output, expected_b, sizeof(branch_output)) != 0) {
                free(barrier_state);
                free(save_bytes);
                gn_destroy(instance);
                fputs("ASSERTION FAILED save.disk-latest-branch restored B guest output\n",
                      stderr);
                return 1;
            }
            gn_mvs_save_receipt_v1 branch_receipt;
            memset(&branch_receipt, 0, sizeof(branch_receipt));
            size_t branch_written = 0u;
            if (gn_mvs_save_export_v1(instance, save_bytes,
                    GN_MVS_SAVE_ENVELOPE_V1_BYTES, &branch_written,
                    &branch_receipt, sizeof(branch_receipt), NULL, 0u) !=
                    GN_STATUS_OK || branch_written !=
                        GN_MVS_SAVE_ENVELOPE_V1_BYTES ||
                !query_save(instance, &after_export)) {
                free(barrier_state);
                free(save_bytes);
                gn_destroy(instance);
                fputs("save.restored-branch-b-export failed\n", stderr);
                return 4;
            }
            host_pending_transaction branch_transaction;
            memset(&branch_transaction, 0, sizeof(branch_transaction));
            if (!save_host_context_init(&branch_transaction, save_path,
                    save_bytes, GN_MVS_SAVE_ENVELOPE_V1_BYTES,
                    &branch_receipt, instance, NULL) ||
                save_host_commit(&branch_transaction) != HOST_COMMIT_COMMITTED ||
                !query_save(instance, &after_ack)) {
                free(barrier_state);
                free(save_bytes);
                gn_destroy(instance);
                fputs("save.restored-branch-b-commit failed\n", stderr);
                return 4;
            }
            outcome = HOST_COMMIT_COMMITTED;
            if (obsolete_publication_control != 0) {
                memset(&state_detail, 0, sizeof(state_detail));
                if (save_host_restore(&branch_transaction, barrier_state,
                        barrier_state_length, &state_detail,
                        sizeof(state_detail)) != GN_STATUS_OK ||
                    gn_set_mvs_inputs(instance, GN_MVS_INPUT_P1_A) != GN_STATUS_OK) {
                    free(barrier_state);
                    free(save_bytes);
                    gn_destroy(instance);
                    fputs("save.obsolete-control-branch-a-setup failed\n", stderr);
                    return 4;
                }
                uint8_t old_output[SAVE_OUTPUT_COUNT] = {0};
                uint8_t expected_a[SAVE_OUTPUT_COUNT];
                (void)expected_guest_output(0, expected_a);
                gn_mvs_save_receipt_v1 current_a_receipt;
                memset(&current_a_receipt, 0, sizeof(current_a_receipt));
                size_t current_a_written = 0u;
                if (!guest_output(instance, output) ||
                    !guest_save_readback(instance, old_output) ||
                    memcmp(old_output, expected_a, sizeof(old_output)) != 0 ||
                    gn_mvs_save_export_v1(instance, save_bytes,
                        GN_MVS_SAVE_ENVELOPE_V1_BYTES, &current_a_written,
                        &current_a_receipt, sizeof(current_a_receipt), NULL,
                        0u) != GN_STATUS_OK || current_a_written !=
                            GN_MVS_SAVE_ENVELOPE_V1_BYTES) {
                    free(barrier_state);
                    free(save_bytes);
                    gn_destroy(instance);
                    fputs("save.obsolete-control-branch-a-export failed\n", stderr);
                    return 4;
                }
                host_pending_transaction obsolete_transaction;
                memset(&obsolete_transaction, 0, sizeof(obsolete_transaction));
                if (!save_host_context_init(&obsolete_transaction, save_path,
                        save_bytes, GN_MVS_SAVE_ENVELOPE_V1_BYTES,
                        &receipt, instance, NULL)) {
                    free(barrier_state);
                    free(save_bytes);
                    gn_destroy(instance);
                    fputs("save.obsolete-control-transaction failed\n", stderr);
                    return 4;
                }
                obsolete_publication_outcome =
                    save_host_commit(&obsolete_transaction);
                gn_mvs_save_detail_v1 stale_detail;
                memset(&stale_detail, 0, sizeof(stale_detail));
                const gn_status stale_status = gn_mvs_save_ack_v1(instance,
                    &receipt, sizeof(receipt), &stale_detail,
                    sizeof(stale_detail));
                obsolete_stale_ack_rejected =
                    stale_status == GN_STATUS_INVALID_STATE &&
                    (stale_detail.reason == GN_MVS_SAVE_REASON_STALE_RECEIPT ||
                     stale_detail.reason == GN_MVS_SAVE_REASON_RECEIPT_CONSUMED);
                if (obsolete_publication_outcome !=
                        HOST_COMMIT_OUTCOME_UNCERTAIN ||
                    !obsolete_stale_ack_rejected) {
                    free(barrier_state);
                    free(save_bytes);
                    gn_destroy(instance);
                    fputs("save.obsolete-control-stale-ack failed\n", stderr);
                    return 4;
                }
            }
        }
    } else {
        if (skip_import == 0 && startup_read == HOST_READ_READY) {
            memset(&detail, 0, sizeof(detail));
            const gn_status closed_status = gn_mvs_save_import_baseline_v1(
                instance, save_bytes, GN_MVS_SAVE_ENVELOPE_V1_BYTES,
                &detail, sizeof(detail));
            gn_mvs_save_info_v1 after_closed_attempt;
            closed_import_rejected = closed_status == GN_STATUS_INVALID_STATE &&
                detail.reason == GN_MVS_SAVE_REASON_STARTUP_CLOSED &&
                query_save(instance, &after_closed_attempt) &&
                after_closed_attempt.dirty == after_guest.dirty &&
                after_closed_attempt.baseline_known == after_guest.baseline_known &&
                after_closed_attempt.startup_import_allowed ==
                    after_guest.startup_import_allowed;
        }
        after_export = after_guest;
        after_ack = after_guest;
        outcome = HOST_COMMIT_NOT_COMMITTED;
    }

    print_observation(mode, startup_read, &before, &after_import, &after_guest,
                      &after_export, &after_ack, writer != 0 ? &receipt : NULL,
                      reset_preserved_sram, restore_branched,
                      stale_ack_preserved_dirty, duplicate_ack_rejected,
                      closed_import_rejected,
                      writer != 0 ? host_outcome_name(outcome) : "not_applicable",
                      host_resolution,
                      writer != 0 ? pending_transaction.failed_stage : "",
                      barrier_probe_mask, obsolete_stale_ack_rejected,
                      host_outcome_name(obsolete_publication_outcome), stages);
    if (obsolete_publication_control != 0 &&
        obsolete_publication_outcome == HOST_COMMIT_OUTCOME_UNCERTAIN) {
        fflush(stdout);
        return 0;
    }
    if (pending_transaction.unresolved != 0) {
        fputs("save.lifecycle-blocked: unresolved host transaction\n", stderr);
        for (;;) (void)sleep(1u);
    }
    free(barrier_state);
    free(save_bytes);
    gn_destroy(instance);

    if (writer == 0) {
        uint8_t expected[SAVE_OUTPUT_COUNT];
        (void)expected_guest_output(use_b, expected);
        if (startup_read == HOST_READ_MISSING)
            memset(expected, 0, sizeof(expected));
        if (memcmp(output, expected, sizeof(output)) != 0) {
            fputs(disk_latest_branch_control != 0
                    ? "ASSERTION FAILED save.disk-latest-branch expected="
                    : "ASSERTION FAILED save.guest-output expected=", stderr);
            for (size_t index = 0u; index < sizeof(expected); ++index)
                fprintf(stderr, "%02x", expected[index]);
            fputs(" actual=", stderr);
            for (size_t index = 0u; index < sizeof(output); ++index)
                fprintf(stderr, "%02x", output[index]);
            fputc('\n', stderr);
            return 1;
        }
    }
    if (writer != 0 && outcome != HOST_COMMIT_COMMITTED) {
        fprintf(stderr, "save.host-outcome=%s\n", host_outcome_name(outcome));
        return outcome == HOST_COMMIT_UNSUPPORTED ? 77 : 4;
    }
    return 0;
}

static int parse_fault_stage(const char *text, save_host_fault_stage *stage) {
    if (text == NULL || stage == NULL) return 0;
    static const struct {
        const char *name;
        save_host_fault_stage value;
    } names[] = {
        {"create", SAVE_HOST_FAULT_CREATE},
        {"write", SAVE_HOST_FAULT_WRITE},
        {"file-sync", SAVE_HOST_FAULT_FILE_SYNC},
        {"file-close", SAVE_HOST_FAULT_FILE_CLOSE},
        {"rename", SAVE_HOST_FAULT_RENAME},
        {"directory-open", SAVE_HOST_FAULT_DIRECTORY_OPEN},
        {"directory-sync", SAVE_HOST_FAULT_DIRECTORY_SYNC},
        {"directory-close", SAVE_HOST_FAULT_DIRECTORY_CLOSE},
        {"ack", SAVE_HOST_FAULT_ACK}
    };
    for (size_t index = 0u; index < sizeof(names) / sizeof(names[0]); ++index) {
        if (strcmp(text, names[index].name) == 0) {
            *stage = names[index].value;
            return 1;
        }
    }
    return 0;
}

static int parse_stage_name(const char *text) {
    static const char *const names[] = {
        "temp-created", "partial-write", "write", "file-fullfsync",
        "file-close", "rename", "directory-open", "directory-fsync",
        "directory-close", "protocol-complete", "ack", "unresolved"
    };
    for (size_t index = 0u; index < sizeof(names) / sizeof(names[0]); ++index)
        if (text != NULL && strcmp(text, names[index]) == 0) return 1;
    return 0;
}

static int parse_fd(const char *text, int *descriptor) {
    if (text == NULL || descriptor == NULL) return 0;
    char *end = NULL;
    errno = 0;
    const long parsed = strtol(text, &end, 10);
    if (errno != 0 || end == text || *end != '\0' || parsed < 0 ||
        parsed > INT_MAX) return 0;
    *descriptor = (int)parsed;
    return 1;
}

int main(int argc, char **argv) {
    if (argc == 3 && strcmp(argv[1], "--write-fixture") == 0)
        return write_fixture_file(argv[2]);
    const char *mode = NULL;
    const char *save_path = NULL;
    const char *resolve_action = NULL;
    const char *stage_name = NULL;
    int use_b = 0;
    int skip_import = 0;
    int false_ack_control = 0;
    int barrier_ordering = 0;
    int obsolete_publication_control = 0;
    int disk_latest_branch_control = 0;
    int print_immutable_export = 0;
    int probe_failed_barriers = 0;
    int retry_failed_commit = 0;
    int expect_invalid_authoritative = 0;
    int stage_notify_fd = -1;
    int stage_release_fd = -1;
    save_host_faults faults;
    memset(&faults, 0, sizeof(faults));
    for (int index = 1; index < argc; ++index) {
        if (strcmp(argv[index], "--mode") == 0 && index + 1 < argc) {
            mode = argv[++index];
        } else if (strcmp(argv[index], "--value") == 0 && index + 1 < argc) {
            const char *value = argv[++index];
            if (strcmp(value, "A") != 0 && strcmp(value, "B") != 0) return 2;
            use_b = strcmp(value, "B") == 0;
        } else if (strcmp(argv[index], "--save-file") == 0 && index + 1 < argc) {
            save_path = argv[++index];
        } else if (strcmp(argv[index], "--no-import") == 0) {
            skip_import = 1;
        } else if (strcmp(argv[index], "--test-fail-after-rename") == 0) {
            faults.fail_after_rename = 1;
        } else if (strcmp(argv[index], "--test-retry-fsync-failures") == 0 &&
                   index + 1 < argc) {
            char *end = NULL;
            errno = 0;
            const unsigned long parsed = strtoul(argv[++index], &end, 10);
            if (errno != 0 || end == argv[index] || *end != '\0' ||
                parsed > UINT_MAX) return 2;
            faults.retry_directory_sync_failures = (unsigned)parsed;
        } else if (strcmp(argv[index], "--test-fail-stage") == 0 &&
                   index + 1 < argc) {
            if (!parse_fault_stage(argv[++index], &faults.fail_once)) return 2;
        } else if (strcmp(argv[index], "--test-short-write-limit") == 0 &&
                   index + 1 < argc) {
            char *end = NULL;
            errno = 0;
            const unsigned long parsed = strtoul(argv[++index], &end, 10);
            if (errno != 0 || end == argv[index] || *end != '\0' ||
                parsed == 0u || parsed > UINT_MAX) return 2;
            faults.short_write_limit = (unsigned)parsed;
        } else if (strcmp(argv[index], "--test-interrupted-writes") == 0 &&
                   index + 1 < argc) {
            char *end = NULL;
            errno = 0;
            const unsigned long parsed = strtoul(argv[++index], &end, 10);
            if (errno != 0 || end == argv[index] || *end != '\0' ||
                parsed > SAVE_HOST_MAX_ATTEMPTS) return 2;
            faults.interrupted_writes = (unsigned)parsed;
        } else if (strcmp(argv[index], "--test-control-false-ack") == 0) {
            false_ack_control = 1;
        } else if (strcmp(argv[index], "--test-stage-name") == 0 &&
                   index + 1 < argc) {
            stage_name = argv[++index];
            if (!parse_stage_name(stage_name)) return 2;
        } else if (strcmp(argv[index], "--test-stage-notify-fd") == 0 &&
                   index + 1 < argc) {
            if (!parse_fd(argv[++index], &stage_notify_fd)) return 2;
        } else if (strcmp(argv[index], "--test-stage-release-fd") == 0 &&
                   index + 1 < argc) {
            if (!parse_fd(argv[++index], &stage_release_fd)) return 2;
        } else if (strcmp(argv[index], "--test-barrier-ordering") == 0) {
            barrier_ordering = 1;
        } else if (strcmp(argv[index], "--test-probe-failed-barriers") == 0) {
            probe_failed_barriers = 1;
        } else if (strcmp(argv[index], "--test-retry-failed-commit") == 0) {
            retry_failed_commit = 1;
        } else if (strcmp(argv[index], "--test-control-obsolete-publication") == 0) {
            obsolete_publication_control = 1;
        } else if (strcmp(argv[index], "--test-control-disk-latest-branch") == 0) {
            disk_latest_branch_control = 1;
        } else if (strcmp(argv[index], "--test-print-immutable-export") == 0) {
            print_immutable_export = 1;
        } else if (strcmp(argv[index], "--test-control-invalid-authoritative") == 0) {
            expect_invalid_authoritative = 1;
        } else if (strcmp(argv[index], "--resolve-uncertain") == 0 &&
                   index + 1 < argc) {
            resolve_action = argv[++index];
            if (strcmp(resolve_action, "retry") != 0 &&
                strcmp(resolve_action, "discard") != 0) return 2;
        } else {
            fputs("usage: sdk_save_process --mode write|read --save-file PATH "
                  "[--value A|B] [--no-import] [--test-fail-after-rename] "
                  "[--test-retry-fsync-failures N] [--test-fail-stage STAGE] "
                  "[--test-short-write-limit N] [--test-interrupted-writes N] "
                  "[--resolve-uncertain retry|discard]\n", stderr);
            return 2;
        }
    }
    if (mode == NULL || save_path == NULL) return 2;
    if ((stage_name == NULL && (stage_notify_fd >= 0 || stage_release_fd >= 0)) ||
        (stage_name != NULL && (stage_notify_fd < 0 || stage_release_fd < 0)) ||
        (barrier_ordering != 0 && stage_name == NULL) ||
        (obsolete_publication_control != 0 && barrier_ordering == 0)) return 2;
    return run_process(mode, use_b, save_path, skip_import, false_ack_control,
                       barrier_ordering, obsolete_publication_control,
                       disk_latest_branch_control, print_immutable_export,
                       probe_failed_barriers, retry_failed_commit,
                       expect_invalid_authoritative, stage_name,
                       stage_notify_fd, stage_release_fd, resolve_action,
                       &faults);
}

#endif
