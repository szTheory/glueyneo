/* SPDX-License-Identifier: MIT; installed native persistence example. */
#include <glueyneo/glueyneo.h>
#include "persistence_host.h"

#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static inline FILE *gn_portable_fopen(const char *path, const char *mode) {
#if defined(_MSC_VER)
    FILE *file = NULL;
    if (fopen_s(&file, path, mode) != 0) return NULL;
    return file;
#else
    return fopen(path, mode);
#endif
}

size_t public_persistence_guest_size(void);
int public_persistence_guest_build(uint8_t *bundle, size_t capacity);

enum {
    BUNDLE_HEADER_BYTES = 16u,
    REGION_DESCRIPTOR_BYTES = 12u,
    FIXTURE_OVERHEAD_BYTES = BUNDLE_HEADER_BYTES +
        GN_MVS_V3_MAX_REGIONS * REGION_DESCRIPTOR_BYTES,
    GUEST_CYCLE_BUDGET = 5000u,
    SLOT_PATH_MAX_BYTES = 4096u,
    SCOPE_TEXT_BYTES = 32u
};

typedef struct {
    const char *mode;
    const char *role;
    const char *value;
    const char *slot;
    const char *scratch_dir;
    const char *scope;
    int no_import;
    int reopen;
    int discard;
    const char *test_fail_stage;
} options;

static uint32_t read_u32_be(const uint8_t *bytes) {
    return ((uint32_t)bytes[0] << 24) | ((uint32_t)bytes[1] << 16) |
           ((uint32_t)bytes[2] << 8) | (uint32_t)bytes[3];
}

static int parse_options(int argc, char **argv, options *out) {
    if (out == NULL) return 0;
    memset(out, 0, sizeof(*out));
    int portable = 0;
    for (int index = 1; index < argc; ++index) {
        if (strcmp(argv[index], "--mode") == 0 && index + 1 < argc) {
            out->mode = argv[++index];
            portable = strcmp(out->mode, "portable") == 0 ||
                strcmp(out->mode, "host") == 0 ||
                strcmp(out->mode, "faults") == 0;
        } else if (strcmp(argv[index], "--role") == 0 && index + 1 < argc) {
            out->role = argv[++index];
        } else if (strcmp(argv[index], "--value") == 0 && index + 1 < argc) {
            out->value = argv[++index];
        } else if (strcmp(argv[index], "--slot") == 0 && index + 1 < argc) {
            out->slot = argv[++index];
        } else if (strcmp(argv[index], "--scratch-dir") == 0 && index + 1 < argc) {
            out->scratch_dir = argv[++index];
        } else if (strcmp(argv[index], "--scope") == 0 && index + 1 < argc) {
            out->scope = argv[++index];
        } else if (strcmp(argv[index], "--no-import") == 0) {
            out->no_import = 1;
        } else if (strcmp(argv[index], "--reopen") == 0) {
            out->reopen = 1;
        } else if (strcmp(argv[index], "--discard") == 0) {
            out->discard = 1;
#ifdef GLUEYNEO_PERSISTENCE_TESTING
        } else if (strcmp(argv[index], "--test-fail-stage") == 0 &&
                   index + 1 < argc) {
            out->test_fail_stage = argv[++index];
#endif
        } else {
            return 0;
        }
    }
    if (portable == 0 || out->mode == NULL || out->role == NULL || out->slot == NULL ||
        out->slot[0] == '\0' || strlen(out->slot) >= SLOT_PATH_MAX_BYTES ||
        out->scope == NULL) return 0;
    if (strcmp(out->mode, "portable") != 0 && out->no_import != 0) return 0;
#ifndef GLUEYNEO_PERSISTENCE_TESTING
    if (strcmp(out->mode, "faults") == 0 || out->test_fail_stage != NULL)
        return 0;
#endif
    if (strcmp(out->mode, "host") == 0 &&
        strcmp(out->role, "reader") == 0 && out->reopen == 0) return 0;
    if (strcmp(out->mode, "portable") != 0 && out->scratch_dir == NULL) return 0;
    if (strcmp(out->mode, "portable") == 0 &&
        (out->reopen != 0 || out->discard != 0)) return 0;
    if (strcmp(out->role, "producer") == 0) {
        return out->value != NULL && out->no_import == 0 &&
            (strcmp(out->value, "A") == 0 || strcmp(out->value, "B") == 0);
    }
    return strcmp(out->role, "reader") == 0 && out->value == NULL;
}

static int parse_hex_nibble(char byte, uint8_t *out) {
    if (byte >= '0' && byte <= '9') *out = (uint8_t)(byte - '0');
    else if (byte >= 'a' && byte <= 'f') *out = (uint8_t)(byte - 'a' + 10);
    else if (byte >= 'A' && byte <= 'F') *out = (uint8_t)(byte - 'A' + 10);
    else return 0;
    return 1;
}

static int parse_scope(const char *text, gn_mvs_save_scope_v1 *scope) {
    if (text == NULL || scope == NULL || strlen(text) != SCOPE_TEXT_BYTES)
        return 0;
    memset(scope, 0, sizeof(*scope));
    scope->size = (uint32_t)sizeof(*scope);
    uint8_t aggregate = 0u;
    for (size_t index = 0u; index < sizeof(scope->scope); ++index) {
        uint8_t high = 0u, low = 0u;
        if (!parse_hex_nibble(text[index * 2u], &high) ||
            !parse_hex_nibble(text[index * 2u + 1u], &low)) return 0;
        scope->scope[index] = (uint8_t)((high << 4) | low);
        aggregate |= scope->scope[index];
    }
    return aggregate != 0u;
}

static int create_guest(gn_instance **out_instance, size_t *out_fixture_bytes) {
    const size_t maximum = GN_MVS_MAX_MEDIA_BYTES + FIXTURE_OVERHEAD_BYTES;
    const size_t size = public_persistence_guest_size();
    if (out_instance == NULL || out_fixture_bytes == NULL || size == 0u ||
        size > maximum || size > SIZE_MAX - 1u) return 0;
    uint8_t *bundle = (uint8_t *)malloc(size);
    if (bundle == NULL || !public_persistence_guest_build(bundle, size) ||
        memcmp(bundle, "GNMV", 4u) != 0 ||
        read_u32_be(bundle + 4u) != GN_MVS_MANIFEST_VERSION_ZOOM ||
        read_u32_be(bundle + 8u) != GN_MVS_PROFILE_MSX ||
        read_u32_be(bundle + 12u) != GN_MVS_V3_MAX_REGIONS) {
        free(bundle);
        return 0;
    }

    gn_mvs_manifest_v3 manifest;
    memset(&manifest, 0, sizeof(manifest));
    manifest.version = GN_MVS_MANIFEST_VERSION_ZOOM;
    manifest.profile = GN_MVS_PROFILE_MSX;
    manifest.region_count = GN_MVS_V3_MAX_REGIONS;
    size_t cursor = BUNDLE_HEADER_BYTES;
    int valid = 1;
    for (size_t index = 0u; index < GN_MVS_V3_MAX_REGIONS; ++index) {
        if (cursor > size || size - cursor < REGION_DESCRIPTOR_BYTES) {
            valid = 0;
            break;
        }
        const uint32_t role = read_u32_be(bundle + cursor);
        const uint32_t reserved = read_u32_be(bundle + cursor + 4u);
        const uint32_t extent = read_u32_be(bundle + cursor + 8u);
        cursor += REGION_DESCRIPTOR_BYTES;
        if (role != index + 1u || reserved != 0u ||
            (size_t)extent > size - cursor) {
            valid = 0;
            break;
        }
        gn_mvs_region *region = &manifest.regions[index];
        region->role = (gn_mvs_region_role)role;
        region->source = bundle + cursor;
        region->source_size = extent;
        region->mapped_size = extent;
        region->layout = GN_MVS_LAYOUT_LINEAR;
        cursor += extent;
    }
    if (cursor != size) valid = 0;
    gn_instance *instance = NULL;
    gn_status status = valid != 0 ? gn_create(&instance) : GN_STATUS_INVALID_MEDIA;
    if (status == GN_STATUS_OK)
        status = gn_load_mvs_v3(instance, &manifest);
    free(bundle);
    if (status != GN_STATUS_OK) {
        gn_destroy(instance);
        return 0;
    }
    *out_instance = instance;
    *out_fixture_bytes = size;
    return 1;
}

static int write_slot_new(const char *path, const uint8_t *bytes, size_t size) {
    FILE *file = gn_portable_fopen(path, "wbx");
    if (file == NULL) return 0;
    const size_t written = fwrite(bytes, 1u, size, file);
    const int write_error = ferror(file);
    const int close_status = fclose(file);
    if (written == size && write_error == 0 && close_status == 0) return 1;
    (void)remove(path);
    return 0;
}

static int read_slot(const char *path, uint8_t *bytes, size_t size) {
    FILE *file = gn_portable_fopen(path, "rb");
    if (file == NULL) return 0;
    const size_t count = fread(bytes, 1u, size, file);
    const int extra = fgetc(file);
    const int read_error = ferror(file);
    const int close_status = fclose(file);
    return count == size && extra == EOF && read_error == 0 &&
        close_status == 0;
}

static int guest_run(gn_instance *instance, gn_run_result *result) {
    memset(result, 0, sizeof(*result));
    const gn_status status = gn_run_mvs(instance, GUEST_CYCLE_BUDGET, result);
    if (status != GN_STATUS_OK || result->reason != GN_RUN_STOPPED) {
        (void)fprintf(stderr,
            "persistence.guest-run status=%u reason=%u instructions=%" PRIu64
            " pc=%" PRIu32 " fault_pc=%" PRIu32 " ir=%u\n",
            (unsigned)status, (unsigned)result->reason, result->instructions,
            result->boundary_pc, result->fault_pc,
            (unsigned)result->instruction_register);
        return 0;
    }
    return 1;
}

static int resolve_lifecycle(gn_instance **instance,
                             gn_mvs_save_lifecycle_policy_v1 policy) {
    gn_mvs_save_lifecycle_result_v1 result;
    gn_mvs_save_detail_v1 detail;
    memset(&result, 0, sizeof(result));
    memset(&detail, 0, sizeof(detail));
    return gn_destroy_checked_v1(instance, policy, 1u, &result, sizeof(result),
        &detail, sizeof(detail)) == GN_STATUS_OK && *instance == NULL;
}

static int run_portable(const options *args) {
    gn_instance *instance = NULL;
    size_t fixture_bytes = 0u;
    if (!create_guest(&instance, &fixture_bytes)) {
        fputs("persistence.fixture-load failed\n", stderr);
        return 2;
    }
    gn_mvs_save_scope_v1 scope;
    if (!parse_scope(args->scope, &scope) ||
        gn_mvs_save_scope_renew_v1(instance, &scope, sizeof(scope), NULL, 0u) !=
            GN_STATUS_OK) {
        (void)resolve_lifecycle(&instance, GN_MVS_SAVE_LIFECYCLE_ALLOW_DISCARD);
        fputs("persistence.scope-invalid\n", stderr);
        return 2;
    }

    uint8_t envelope[GN_MVS_SAVE_ENVELOPE_V1_BYTES];
    if (strcmp(args->role, "reader") == 0 && args->no_import == 0 &&
        !read_slot(args->slot, envelope, sizeof(envelope))) {
        (void)resolve_lifecycle(&instance, GN_MVS_SAVE_LIFECYCLE_ALLOW_DISCARD);
        fputs("persistence.slot-invalid\n", stderr);
        return 2;
    }
    if (strcmp(args->role, "reader") == 0 && args->no_import == 0 &&
        gn_mvs_save_import_baseline_v1(instance, envelope, sizeof(envelope),
            NULL, 0u) != GN_STATUS_OK) {
        (void)resolve_lifecycle(&instance, GN_MVS_SAVE_LIFECYCLE_ALLOW_DISCARD);
        fputs("persistence.slot-rejected\n", stderr);
        return 2;
    }

    if (strcmp(args->role, "producer") == 0) {
        const uint32_t input = strcmp(args->value, "A") == 0
            ? GN_MVS_INPUT_P1_A : GN_MVS_INPUT_P1_B;
        if (gn_set_mvs_inputs(instance, input) != GN_STATUS_OK) {
            (void)resolve_lifecycle(&instance, GN_MVS_SAVE_LIFECYCLE_ALLOW_DISCARD);
            fputs("persistence.input-invalid\n", stderr);
            return 2;
        }
    } else if (gn_set_mvs_inputs(instance, 0u) != GN_STATUS_OK) {
        (void)resolve_lifecycle(&instance, GN_MVS_SAVE_LIFECYCLE_ALLOW_DISCARD);
        fputs("persistence.input-invalid\n", stderr);
        return 2;
    }

    gn_run_result observation;
    if (!guest_run(instance, &observation)) {
        (void)resolve_lifecycle(&instance, GN_MVS_SAVE_LIFECYCLE_ALLOW_DISCARD);
        fputs("persistence.guest-run failed\n", stderr);
        return 3;
    }
    uint64_t assertions = 6u;
    if (strcmp(args->role, "producer") == 0) {
        gn_mvs_save_info_v1 info;
        gn_mvs_save_receipt_v1 receipt;
        size_t written = 0u;
        memset(&info, 0, sizeof(info));
        memset(&receipt, 0, sizeof(receipt));
        const gn_status query_status = gn_mvs_save_query_v1(
            instance, &info, sizeof(info), NULL, 0u);
        if (query_status != GN_STATUS_OK || info.supported == 0u ||
            info.dirty == 0u) {
            (void)fprintf(stderr,
                "persistence.save-query status=%u supported=%u dirty=%u\n",
                (unsigned)query_status, (unsigned)info.supported,
                (unsigned)info.dirty);
            (void)resolve_lifecycle(&instance, GN_MVS_SAVE_LIFECYCLE_ALLOW_DISCARD);
            return 4;
        }
        const gn_status export_status = gn_mvs_save_export_v1(instance, envelope,
            sizeof(envelope), &written, &receipt, sizeof(receipt), NULL, 0u);
        if (export_status != GN_STATUS_OK || written != sizeof(envelope)) {
            (void)fprintf(stderr,
                "persistence.save-export status=%u written=%zu expected=%zu\n",
                (unsigned)export_status, written, sizeof(envelope));
            (void)resolve_lifecycle(&instance, GN_MVS_SAVE_LIFECYCLE_ALLOW_DISCARD);
            return 4;
        }
        if (!write_slot_new(args->slot, envelope, sizeof(envelope))) {
            fputs("persistence.transfer-write failed\n", stderr);
            (void)resolve_lifecycle(&instance, GN_MVS_SAVE_LIFECYCLE_ALLOW_DISCARD);
            return 4;
        }
        const gn_status ack_status = gn_mvs_save_ack_v1(instance, &receipt,
            sizeof(receipt), NULL, 0u);
        if (ack_status != GN_STATUS_OK) {
            (void)fprintf(stderr, "persistence.save-ack status=%u\n",
                          (unsigned)ack_status);
            (void)resolve_lifecycle(&instance, GN_MVS_SAVE_LIFECYCLE_ALLOW_DISCARD);
            return 4;
        }
        assertions += 5u;
    } else {
        gn_mvs_save_info_v1 info;
        memset(&info, 0, sizeof(info));
        if (gn_mvs_save_query_v1(instance, &info, sizeof(info), NULL, 0u) !=
                GN_STATUS_OK || info.supported == 0u ||
            (args->no_import == 0 && info.baseline_known == 0u)) {
            (void)resolve_lifecycle(&instance, GN_MVS_SAVE_LIFECYCLE_ALLOW_DISCARD);
            fputs("persistence.import-state failed\n", stderr);
            return 4;
        }
        assertions += 2u;
    }

    if (!resolve_lifecycle(&instance, GN_MVS_SAVE_LIFECYCLE_REQUIRE_RESOLVED)) {
        (void)resolve_lifecycle(&instance, GN_MVS_SAVE_LIFECYCLE_ALLOW_DISCARD);
        fputs("persistence.lifecycle failed\n", stderr);
        return 4;
    }
    printf("SDK_PERSISTENCE {\"schema_version\":1,"
           "\"case_id\":\"sdk.persistence.portable\","
           "\"role\":\"%s\",\"outcome\":\"pass\","
           "\"assertions\":%" PRIu64 ",\"fixture_bytes\":%zu,"
           "\"transfer_bytes\":%zu,\"host_file_commit\":\"not_claimed\","
           "\"public_observation\":{\"instructions\":%" PRIu64 ","
           "\"boundary_pc\":%" PRIu32 ",\"reason\":%u}}\n",
           args->role, assertions, fixture_bytes,
           (size_t)GN_MVS_SAVE_ENVELOPE_V1_BYTES, observation.instructions,
           observation.boundary_pc, (unsigned)observation.reason);
    return 0;
}

static int slot_directory(const char *slot, char *directory, size_t capacity) {
    const size_t length = strlen(slot);
    if (length == 0u || length >= capacity) return 0;
    memcpy(directory, slot, length + 1u);
    char *slash = strrchr(directory, '/');
    if (slash == NULL) {
        if (capacity < 2u) return 0;
        directory[0] = '.';
        directory[1] = '\0';
    } else if (slash == directory) {
        slash[1] = '\0';
    } else {
        *slash = '\0';
    }
    return 1;
}

#ifdef GLUEYNEO_PERSISTENCE_TESTING
static unsigned probe_uncertain_transitions(persistence_host_context *host) {
    unsigned mask = 0u;
    gn_state_detail_v1 state_detail;
    gn_mvs_save_detail_v1 save_detail;
    memset(&state_detail, 0, sizeof(state_detail));
    memset(&save_detail, 0, sizeof(save_detail));
    if (persistence_host_restore(host, NULL, 0u, &state_detail,
            sizeof(state_detail)) == GN_STATUS_INVALID_STATE) mask |= 1u;
    if (persistence_host_renew_scope(host, NULL, 0u, &save_detail,
            sizeof(save_detail)) == GN_STATUS_INVALID_STATE) mask |= 2u;
    if (!persistence_host_change_slot(host, "blocked.gnsave")) mask |= 4u;
    if (!persistence_host_replace(host, host->immutable_bytes,
            host->bytes_length, &host->receipt, host->owner)) mask |= 8u;
    gn_mvs_save_lifecycle_result_v1 result;
    memset(&result, 0, sizeof(result));
    if (persistence_host_unload(host, GN_MVS_SAVE_LIFECYCLE_ALLOW_DISCARD,
            &result, sizeof(result), &save_detail, sizeof(save_detail)) ==
            GN_STATUS_INVALID_STATE) mask |= 16u;
    gn_instance *owner = host->owner;
    memset(&result, 0, sizeof(result));
    if (persistence_host_destroy(host, GN_MVS_SAVE_LIFECYCLE_ALLOW_DISCARD,
            &result, sizeof(result), &save_detail, sizeof(save_detail)) ==
            GN_STATUS_INVALID_STATE && host->owner == owner) mask |= 32u;
    return mask;
}

static int set_test_fault(persistence_host_context *host, const char *name) {
    persistence_host_faults faults;
    memset(&faults, 0, sizeof(faults));
    if (name == NULL) return 1;
    if (strcmp(name, "create") == 0) faults.fail_once = PERSISTENCE_HOST_FAULT_CREATE;
    else if (strcmp(name, "write") == 0) faults.fail_once = PERSISTENCE_HOST_FAULT_WRITE;
    else if (strcmp(name, "file-sync") == 0) faults.fail_once = PERSISTENCE_HOST_FAULT_FILE_SYNC;
    else if (strcmp(name, "file-close") == 0) faults.fail_once = PERSISTENCE_HOST_FAULT_FILE_CLOSE;
    else if (strcmp(name, "rename") == 0) faults.fail_once = PERSISTENCE_HOST_FAULT_RENAME;
    else if (strcmp(name, "directory-open") == 0) faults.fail_once = PERSISTENCE_HOST_FAULT_DIRECTORY_OPEN;
    else if (strcmp(name, "directory-sync") == 0) faults.fail_once = PERSISTENCE_HOST_FAULT_DIRECTORY_SYNC;
    else if (strcmp(name, "directory-close") == 0) faults.fail_once = PERSISTENCE_HOST_FAULT_DIRECTORY_CLOSE;
    else if (strcmp(name, "ack") == 0) faults.fail_once = PERSISTENCE_HOST_FAULT_ACK;
    else if (strcmp(name, "after-rename") == 0) faults.fail_after_rename = 1;
    else return 0;
    persistence_host_test_set_faults(host, &faults);
    return 1;
}
#endif

static void emit_host_result(const options *args, const char *outcome,
    const char *host_file_commit, const char *reason, unsigned receipt_acked,
    unsigned transition_mask, const char *stages, uint64_t assertions,
    size_t fixture_bytes, const gn_run_result *observation) {
    printf("SDK_PERSISTENCE {\"schema_version\":1,"
           "\"case_id\":\"sdk.persistence.host\","
           "\"role\":\"%s\",\"outcome\":\"%s\","
           "\"assertions\":%" PRIu64 ",\"fixture_bytes\":%zu,"
           "\"host_file_commit\":\"%s\",\"reason\":\"%s\","
           "\"receipt_acked\":%u,\"transition_barrier_mask\":%u,"
           "\"stages\":\"%s\",\"public_observation\":{"
           "\"instructions\":%" PRIu64 ",\"boundary_pc\":%" PRIu32 "}}\n",
           args->role, outcome, assertions, fixture_bytes, host_file_commit,
           reason == NULL ? "" : reason, receipt_acked, transition_mask,
           stages == NULL ? "" : stages,
           observation == NULL ? 0u : observation->instructions,
           observation == NULL ? 0u : observation->boundary_pc);
}

static int run_host(const options *args) {
    char directory[SLOT_PATH_MAX_BYTES];
    char unsupported_reason[64] = {0};
    if (!slot_directory(args->slot, directory, sizeof(directory)) ||
        strcmp(directory, args->scratch_dir) != 0) return 2;
    if (!persistence_host_support_reason(args->scratch_dir, unsupported_reason,
                                         sizeof(unsupported_reason))) {
        emit_host_result(args, "unsupported", "unsupported", unsupported_reason,
                         0u, 0u, "", 1u, 0u, NULL);
        return 0;
    }

    uint8_t envelope[GN_MVS_SAVE_ENVELOPE_V1_BYTES];
    persistence_host_read_outcome startup =
        persistence_host_read_authoritative(args->slot, envelope, sizeof(envelope));
    const int producer = strcmp(args->role, "producer") == 0;
    const int needs_existing = !producer || args->reopen != 0;
    if ((needs_existing && startup != PERSISTENCE_HOST_READ_READY) ||
        (producer && args->reopen == 0 && startup != PERSISTENCE_HOST_READ_MISSING)) {
        const char *reason = startup == PERSISTENCE_HOST_READ_MISSING
            ? "slot_missing" : startup == PERSISTENCE_HOST_READ_INVALID
            ? "slot_invalid" : "slot_already_exists";
        (void)fprintf(stderr, "persistence.host-startup %s\n", reason);
        emit_host_result(args, "invalid", "not_committed", reason, 0u, 0u,
                         "", 1u, 0u, NULL);
        return 2;
    }
    if (producer && args->reopen == 0 &&
        !persistence_host_scratch_is_fresh(args->scratch_dir)) {
        emit_host_result(args, "invalid", "not_committed", "scratch_directory_not_fresh",
                         0u, 0u, "", 1u, 0u, NULL);
        return 2;
    }

    gn_instance *instance = NULL;
    size_t fixture_bytes = 0u;
    if (!create_guest(&instance, &fixture_bytes)) {
        fputs("persistence.fixture-load failed\n", stderr);
        return 2;
    }
    gn_mvs_save_scope_v1 scope;
    if (!parse_scope(args->scope, &scope) ||
        gn_mvs_save_scope_renew_v1(instance, &scope, sizeof(scope), NULL, 0u) !=
            GN_STATUS_OK) {
        (void)resolve_lifecycle(&instance, GN_MVS_SAVE_LIFECYCLE_ALLOW_DISCARD);
        fputs("persistence.scope-invalid\n", stderr);
        return 2;
    }
    if (needs_existing && gn_mvs_save_import_baseline_v1(instance, envelope,
            sizeof(envelope), NULL, 0u) != GN_STATUS_OK) {
        (void)resolve_lifecycle(&instance, GN_MVS_SAVE_LIFECYCLE_ALLOW_DISCARD);
        fputs("persistence.slot-rejected\n", stderr);
        emit_host_result(args, "invalid", "not_committed", "slot_format_invalid",
                         0u, 0u, "", 1u, fixture_bytes, NULL);
        return 2;
    }
    const uint32_t input = producer && strcmp(args->value, "A") == 0
        ? GN_MVS_INPUT_P1_A : producer ? GN_MVS_INPUT_P1_B : 0u;
    if (gn_set_mvs_inputs(instance, input) != GN_STATUS_OK) {
        (void)resolve_lifecycle(&instance, GN_MVS_SAVE_LIFECYCLE_ALLOW_DISCARD);
        fputs("persistence.input-invalid\n", stderr);
        return 2;
    }
    gn_run_result observation;
    if (!guest_run(instance, &observation)) {
        (void)resolve_lifecycle(&instance, GN_MVS_SAVE_LIFECYCLE_ALLOW_DISCARD);
        return 3;
    }

    if (!producer) {
        gn_mvs_save_info_v1 info;
        memset(&info, 0, sizeof(info));
        const int clean = gn_mvs_save_query_v1(instance, &info, sizeof(info),
            NULL, 0u) == GN_STATUS_OK && info.baseline_known != 0u && info.dirty == 0u;
        if (!clean || !resolve_lifecycle(&instance,
                GN_MVS_SAVE_LIFECYCLE_REQUIRE_RESOLVED)) return 4;
        emit_host_result(args, "pass", "read_only_reopen", "", 0u, 0u,
                         "read,import", 8u, fixture_bytes, &observation);
        return 0;
    }

    gn_mvs_save_info_v1 info;
    gn_mvs_save_receipt_v1 receipt;
    size_t written = 0u;
    memset(&info, 0, sizeof(info));
    memset(&receipt, 0, sizeof(receipt));
    if (gn_mvs_save_query_v1(instance, &info, sizeof(info), NULL, 0u) !=
            GN_STATUS_OK || info.supported == 0u || info.dirty == 0u ||
        gn_mvs_save_export_v1(instance, envelope, sizeof(envelope), &written,
            &receipt, sizeof(receipt), NULL, 0u) != GN_STATUS_OK ||
        written != sizeof(envelope)) {
        (void)resolve_lifecycle(&instance, GN_MVS_SAVE_LIFECYCLE_ALLOW_DISCARD);
        emit_host_result(args, "invalid", "not_committed", "save_export_failed",
                         0u, 0u, "", 2u, fixture_bytes, &observation);
        return 4;
    }

    persistence_host_context transaction;
    if (!persistence_host_context_init(&transaction, args->slot, envelope,
            sizeof(envelope), &receipt, instance, args->reopen)) {
        emit_host_result(args, "invalid", "not_committed", "slot_already_exists",
                         0u, 0u, "", 1u, fixture_bytes, &observation);
        (void)resolve_lifecycle(&instance, GN_MVS_SAVE_LIFECYCLE_ALLOW_DISCARD);
        return 2;
    }
#ifdef GLUEYNEO_PERSISTENCE_TESTING
    if (strcmp(args->mode, "faults") == 0 &&
        !set_test_fault(&transaction, args->test_fail_stage)) {
        (void)resolve_lifecycle(&instance, GN_MVS_SAVE_LIFECYCLE_ALLOW_DISCARD);
        fputs("persistence.test-fail-stage invalid\n", stderr);
        return 2;
    }
#endif
    const persistence_host_outcome host_outcome =
        persistence_host_commit(&transaction);
    unsigned barrier_mask = 0u;
#ifdef GLUEYNEO_PERSISTENCE_TESTING
    if (host_outcome == PERSISTENCE_HOST_OUTCOME_UNCERTAIN)
        barrier_mask = probe_uncertain_transitions(&transaction);
#endif
    const char *commit_name = host_outcome == PERSISTENCE_HOST_COMMITTED
        ? "committed_darwin_apfs"
        : host_outcome == PERSISTENCE_HOST_OUTCOME_UNCERTAIN
        ? "outcome_uncertain" : "not_committed";
    unsigned acked = host_outcome == PERSISTENCE_HOST_COMMITTED ? 1u : 0u;
    const char *outcome_name = host_outcome == PERSISTENCE_HOST_COMMITTED
        ? "pass" : host_outcome == PERSISTENCE_HOST_OUTCOME_UNCERTAIN
        ? "uncertain" : "not_committed";
    int result_code = host_outcome == PERSISTENCE_HOST_COMMITTED ? 0 : 4;
    if (result_code != 0 && args->discard != 0) {
        gn_mvs_save_lifecycle_result_v1 result;
        gn_mvs_save_detail_v1 detail;
        memset(&result, 0, sizeof(result));
        memset(&detail, 0, sizeof(detail));
        if (persistence_host_discard(&transaction, &result, sizeof(result),
                &detail, sizeof(detail)) == GN_STATUS_OK) {
            commit_name = "discarded";
            outcome_name = "discarded";
            result_code = 0;
        }
    }
    if (host_outcome == PERSISTENCE_HOST_COMMITTED) {
        memset(&info, 0, sizeof(info));
        gn_mvs_save_lifecycle_result_v1 lifecycle_result;
        gn_mvs_save_detail_v1 lifecycle_detail;
        memset(&lifecycle_result, 0, sizeof(lifecycle_result));
        memset(&lifecycle_detail, 0, sizeof(lifecycle_detail));
        if (gn_mvs_save_query_v1(instance, &info, sizeof(info), NULL, 0u) !=
                GN_STATUS_OK || info.dirty != 0u || info.baseline_known == 0u ||
            persistence_host_destroy(&transaction,
                GN_MVS_SAVE_LIFECYCLE_REQUIRE_RESOLVED, &lifecycle_result,
                sizeof(lifecycle_result), &lifecycle_detail,
                sizeof(lifecycle_detail)) != GN_STATUS_OK) {
            fputs("persistence.host-lifecycle failed\n", stderr);
            return 4;
        }
        instance = NULL;
        acked = 1u;
    }
#ifdef GLUEYNEO_PERSISTENCE_TESTING
    emit_host_result(args, outcome_name, commit_name,
        transaction.failed_stage, acked, barrier_mask, transaction.stages,
        20u + barrier_mask, fixture_bytes, &observation);
#else
    emit_host_result(args, outcome_name, commit_name, "", acked, 0u, "",
        12u, fixture_bytes, &observation);
#endif
    if (host_outcome == PERSISTENCE_HOST_COMMITTED && result_code == 0) return 0;
    if (args->discard != 0 && result_code == 0) return 0;
    return result_code;
}

int main(int argc, char **argv) {
    options args;
    if (!parse_options(argc, argv, &args)) {
        fputs("usage: glueyneo-installed-persistence --mode portable|host|faults "
              "--role producer --value A|B --slot NEW_PATH --scope HEX32\n"
              "   or: glueyneo-installed-persistence --mode portable "
              "--role reader --slot PATH --scope HEX32 [--no-import]\n"
              "Host mode requires --scratch-dir matching the slot parent; readers require --reopen.\n",
              stderr);
        return 2;
    }
    return strcmp(args.mode, "portable") == 0 ? run_portable(&args)
                                               : run_host(&args);
}
