/* SPDX-License-Identifier: MIT; private SDK persistence witness. */
#include "save_host.h"

#if defined(__APPLE__)
#include <fcntl.h>
#endif

#if defined(__APPLE__) && defined(F_FULLFSYNC)
#include <errno.h>
#include <limits.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>
#endif

#if defined(__APPLE__) && defined(F_FULLFSYNC)

static int save_host_append_stage(save_host_context *transaction,
                                  const char *stage) {
    const size_t used = strlen(transaction->stages);
    const size_t stage_length = strlen(stage);
    const size_t separator = used == 0u ? 0u : 1u;
    const int fits = separator + stage_length <
        sizeof(transaction->stages) - used;
    if (fits != 0) {
        if (separator != 0u) transaction->stages[used] = ',';
        memcpy(transaction->stages + used + separator, stage,
               stage_length + 1u);
    }
    if (transaction->stage_callback != NULL)
        transaction->stage_callback(transaction->stage_callback_context,
                                     stage);
    return fits;
}

static void save_host_notify_stage(save_host_context *transaction,
                                   const char *stage) {
    if (transaction->stage_callback != NULL)
        transaction->stage_callback(transaction->stage_callback_context,
                                     stage);
}

static void save_host_failure(save_host_context *transaction,
                              const char *stage) {
    const size_t length = strlen(stage);
    const size_t limit = sizeof(transaction->failed_stage) - 1u;
    const size_t copy_length = length < limit ? length : limit;
    memcpy(transaction->failed_stage, stage, copy_length);
    transaction->failed_stage[copy_length] = '\0';
}

static int save_host_injected_fault(save_host_context *transaction,
                                    save_host_fault_stage stage,
                                    const char *name) {
    if (transaction->initial_fault_consumed == 0 &&
        transaction->faults.fail_once == stage) {
        transaction->initial_fault_consumed = 1;
        save_host_failure(transaction, name);
        errno = EIO;
        return 1;
    }
    return 0;
}

static int save_host_write_all(save_host_context *transaction,
                               int descriptor, const uint8_t *bytes,
                               size_t length, int zero_progress_once) {
    size_t written = 0u;
    unsigned calls = 0u;
    unsigned interruptions = transaction->faults.interrupted_writes;
    int injected_zero_progress = zero_progress_once;
    int partial_notified = 0;
    while (written < length && calls < SAVE_HOST_MAX_ATTEMPTS) {
        if (interruptions != 0u) {
            --interruptions;
            ++calls;
            errno = EINTR;
            continue;
        }
        size_t request = length - written;
        if (transaction->faults.short_write_limit != 0u &&
            request > transaction->faults.short_write_limit)
            request = transaction->faults.short_write_limit;
        const ssize_t count = injected_zero_progress != 0 ? 0 :
            write(descriptor, bytes + written, request);
        injected_zero_progress = 0;
        ++calls;
        if (count < 0 && errno == EINTR) continue;
        if (count <= 0) return 0;
        written += (size_t)count;
        if (partial_notified == 0 && written < length) {
            save_host_notify_stage(transaction, "partial-write");
            partial_notified = 1;
        }
    }
    return written == length;
}

static int save_host_parent_path(const char *slot, char *directory,
                                 size_t directory_capacity) {
    char copy[SAVE_HOST_SLOT_CAPACITY];
    const size_t slot_length = strlen(slot);
    if (slot_length == 0u || slot_length >= sizeof(copy)) return 0;
    memcpy(copy, slot, slot_length + 1u);
    char *slash = strrchr(copy, '/');
    const char *basename = copy;
    const char *parent = ".";
    if (slash != NULL) {
        basename = slash + 1;
        if (slash == copy) {
            parent = "/";
        } else {
            *slash = '\0';
            parent = copy;
        }
    }
    const size_t parent_length = strlen(parent);
    if (basename[0] == '\0' || parent_length >= directory_capacity) return 0;
    memcpy(directory, parent, parent_length + 1u);
    return 1;
}

static save_host_outcome save_host_publish(save_host_context *transaction,
                                           int reconciliation) {
    if (transaction->publish_attempts != UINT_MAX)
        ++transaction->publish_attempts;
    char directory[SAVE_HOST_SLOT_CAPACITY];
    char temporary[SAVE_HOST_SLOT_CAPACITY + 80u];
    if (!save_host_parent_path(transaction->slot, directory,
                               sizeof(directory))) {
        save_host_failure(transaction, "slot-path");
        return SAVE_HOST_NOT_COMMITTED;
    }

    int descriptor = -1;
    unsigned temp_tries = 0u;
    while (descriptor < 0 && temp_tries < SAVE_HOST_MAX_ATTEMPTS) {
        if (transaction->temp_sequence == UINT_MAX) {
            save_host_failure(transaction, "temporary-sequence");
            return SAVE_HOST_NOT_COMMITTED;
        }
        ++transaction->temp_sequence;
        const int temporary_length = snprintf(temporary, sizeof(temporary),
            "%s.tmp.%ld.%u", transaction->slot, (long)getpid(),
            transaction->temp_sequence);
        if (temporary_length < 0 || (size_t)temporary_length >= sizeof(temporary)) {
            save_host_failure(transaction, "temporary-path");
            return SAVE_HOST_NOT_COMMITTED;
        }
        ++temp_tries;
        if (save_host_injected_fault(transaction, SAVE_HOST_FAULT_CREATE,
                                     "exclusive-create"))
            return SAVE_HOST_NOT_COMMITTED;
        descriptor = open(temporary, O_WRONLY | O_CREAT | O_EXCL, 0600);
        if (descriptor < 0 && errno != EEXIST) {
            save_host_failure(transaction, "exclusive-create");
            return SAVE_HOST_NOT_COMMITTED;
        }
    }
    if (descriptor < 0) {
        save_host_failure(transaction, "temporary-collision-bound");
        return SAVE_HOST_NOT_COMMITTED;
    }
    (void)save_host_append_stage(transaction, "temp-created");

    const int injected_write_stall = save_host_injected_fault(transaction,
        SAVE_HOST_FAULT_WRITE, "write");
    if (!save_host_write_all(transaction, descriptor,
            transaction->immutable_bytes, transaction->bytes_length,
            injected_write_stall)) {
        if (transaction->failed_stage[0] == '\0')
            save_host_failure(transaction, "write");
        (void)close(descriptor);
        (void)unlink(temporary);
        return SAVE_HOST_NOT_COMMITTED;
    }
    (void)save_host_append_stage(transaction, "write");

    if (save_host_injected_fault(transaction, SAVE_HOST_FAULT_FILE_SYNC,
                                 "file-fullfsync") ||
        fcntl(descriptor, F_FULLFSYNC) != 0) {
        if (transaction->failed_stage[0] == '\0')
            save_host_failure(transaction, "file-fullfsync");
        (void)close(descriptor);
        (void)unlink(temporary);
        return SAVE_HOST_NOT_COMMITTED;
    }
    (void)save_host_append_stage(transaction, "file-fullfsync");

    const int injected_close = save_host_injected_fault(transaction,
        SAVE_HOST_FAULT_FILE_CLOSE, "file-close");
    const int file_close_status = close(descriptor);
    descriptor = -1;
    if (injected_close != 0 || file_close_status != 0) {
        if (transaction->failed_stage[0] == '\0')
            save_host_failure(transaction, "file-close");
        (void)unlink(temporary);
        return SAVE_HOST_NOT_COMMITTED;
    }
    (void)save_host_append_stage(transaction, "file-close");

    if (save_host_injected_fault(transaction, SAVE_HOST_FAULT_RENAME, "rename") ||
        rename(temporary, transaction->slot) != 0) {
        if (transaction->failed_stage[0] == '\0')
            save_host_failure(transaction, "rename");
        (void)unlink(temporary);
        return SAVE_HOST_NOT_COMMITTED;
    }
    (void)save_host_append_stage(transaction, "rename");
    if (reconciliation == 0 && transaction->faults.fail_after_rename != 0) {
        transaction->faults.fail_after_rename = 0;
        save_host_failure(transaction, "after-rename");
        return SAVE_HOST_OUTCOME_UNCERTAIN;
    }

    if (save_host_injected_fault(transaction, SAVE_HOST_FAULT_DIRECTORY_OPEN,
                                 "directory-open"))
        return SAVE_HOST_OUTCOME_UNCERTAIN;
    const int directory_fd = open(directory, O_RDONLY);
    if (directory_fd < 0) {
        save_host_failure(transaction, "directory-open");
        return SAVE_HOST_OUTCOME_UNCERTAIN;
    }
    (void)save_host_append_stage(transaction, "directory-open");

    int sync_failed = 0;
    if (reconciliation != 0 &&
        transaction->faults.retry_directory_sync_failures != 0u) {
        --transaction->faults.retry_directory_sync_failures;
        errno = EIO;
        sync_failed = 1;
    } else if (save_host_injected_fault(transaction,
                   SAVE_HOST_FAULT_DIRECTORY_SYNC, "directory-fsync")) {
        sync_failed = 1;
    } else if (fsync(directory_fd) != 0) {
        save_host_failure(transaction, "directory-fsync");
        sync_failed = 1;
    }
    if (sync_failed != 0) {
        if (transaction->failed_stage[0] == '\0')
            save_host_failure(transaction, "directory-fsync");
        (void)close(directory_fd);
        return SAVE_HOST_OUTCOME_UNCERTAIN;
    }
    (void)save_host_append_stage(transaction, "directory-fsync");

    const int injected_directory_close = save_host_injected_fault(transaction,
        SAVE_HOST_FAULT_DIRECTORY_CLOSE, "directory-close");
    const int directory_close_status = close(directory_fd);
    if (injected_directory_close != 0 || directory_close_status != 0) {
        if (transaction->failed_stage[0] == '\0')
            save_host_failure(transaction, "directory-close");
        return SAVE_HOST_OUTCOME_UNCERTAIN;
    }
    (void)save_host_append_stage(transaction, "directory-close");

    save_host_notify_stage(transaction, "protocol-complete");

    if (save_host_injected_fault(transaction, SAVE_HOST_FAULT_ACK, "ack"))
        return SAVE_HOST_OUTCOME_UNCERTAIN;
    gn_mvs_save_detail_v1 detail;
    memset(&detail, 0, sizeof(detail));
    if (gn_mvs_save_ack_v1(transaction->owner, &transaction->receipt,
            sizeof(transaction->receipt), &detail, sizeof(detail)) != GN_STATUS_OK) {
        save_host_failure(transaction, "ack");
        return SAVE_HOST_OUTCOME_UNCERTAIN;
    }
    (void)save_host_append_stage(transaction, "ack");
    return SAVE_HOST_COMMITTED;
}

save_host_read_outcome save_host_read_authoritative(
    const char *path, uint8_t *bytes, size_t capacity) {
    if (path == NULL || bytes == NULL ||
        capacity != GN_MVS_SAVE_ENVELOPE_V1_BYTES) return SAVE_HOST_READ_INVALID;
    const int descriptor = open(path, O_RDONLY | O_NONBLOCK);
    if (descriptor < 0)
        return errno == ENOENT ? SAVE_HOST_READ_MISSING : SAVE_HOST_READ_INVALID;
    struct stat file_status;
    int ok = fstat(descriptor, &file_status) == 0 &&
        S_ISREG(file_status.st_mode) &&
        file_status.st_size == (off_t)GN_MVS_SAVE_ENVELOPE_V1_BYTES;
    size_t offset = 0u;
    while (ok && offset < capacity) {
        const ssize_t count = read(descriptor, bytes + offset, capacity - offset);
        if (count < 0 && errno == EINTR) continue;
        if (count <= 0) {
            ok = 0;
            break;
        }
        offset += (size_t)count;
    }
    uint8_t trailing = 0u;
    if (ok) {
        ssize_t count;
        do {
            count = read(descriptor, &trailing, sizeof(trailing));
        } while (count < 0 && errno == EINTR);
        ok = count == 0;
    }
    if (close(descriptor) != 0) ok = 0;
    return ok && offset == capacity ? SAVE_HOST_READ_READY
                                    : SAVE_HOST_READ_INVALID;
}

int save_host_context_init(save_host_context *transaction,
    const char *slot, const uint8_t *immutable_bytes, size_t bytes_length,
    const gn_mvs_save_receipt_v1 *receipt, gn_instance *owner,
    const save_host_faults *faults) {
    if (transaction == NULL || slot == NULL || immutable_bytes == NULL ||
        receipt == NULL || owner == NULL || bytes_length !=
            GN_MVS_SAVE_ENVELOPE_V1_BYTES || slot[0] == '\0' ||
        strlen(slot) >= SAVE_HOST_SLOT_CAPACITY)
        return 0;
    memset(transaction, 0, sizeof(*transaction));
    memcpy(transaction->slot, slot, strlen(slot) + 1u);
    transaction->immutable_bytes = immutable_bytes;
    transaction->bytes_length = bytes_length;
    transaction->receipt = *receipt;
    transaction->owner = owner;
    transaction->outcome = SAVE_HOST_NOT_COMMITTED;
    if (faults != NULL) transaction->faults = *faults;
    transaction->active = 1;
    return 1;
}

void save_host_set_stage_callback(save_host_context *transaction,
    save_host_stage_callback callback, void *callback_context) {
    if (transaction == NULL) return;
    transaction->stage_callback = callback;
    transaction->stage_callback_context = callback_context;
}

save_host_outcome save_host_commit(save_host_context *transaction) {
    if (transaction == NULL || transaction->active == 0 ||
        transaction->unresolved != 0 || transaction->owner == NULL ||
        transaction->immutable_bytes == NULL || transaction->bytes_length !=
            GN_MVS_SAVE_ENVELOPE_V1_BYTES) return SAVE_HOST_NOT_COMMITTED;
    transaction->failed_stage[0] = '\0';
    transaction->publication_in_flight = 1;
    transaction->outcome = save_host_publish(transaction, 0);
    transaction->publication_in_flight = 0;
    transaction->unresolved =
        transaction->outcome == SAVE_HOST_OUTCOME_UNCERTAIN;
    transaction->commit_failed =
        transaction->outcome == SAVE_HOST_NOT_COMMITTED;
    transaction->active = transaction->commit_failed;
    return transaction->outcome;
}

save_host_outcome save_host_reconcile(save_host_context *transaction) {
    if (transaction == NULL || transaction->unresolved == 0 ||
        transaction->owner == NULL ||
        transaction->immutable_bytes == NULL || transaction->bytes_length !=
            GN_MVS_SAVE_ENVELOPE_V1_BYTES) return SAVE_HOST_OUTCOME_UNCERTAIN;
    if (transaction->retry_attempts != UINT_MAX)
        ++transaction->retry_attempts;
    const size_t stage_base = strlen(transaction->stages);
    transaction->failed_stage[0] = '\0';
    transaction->active = 1;
    transaction->publication_in_flight = 1;
    save_host_outcome outcome = save_host_publish(transaction, 1);
    transaction->publication_in_flight = 0;
    transaction->active = 0;
    if (outcome == SAVE_HOST_COMMITTED) {
        transaction->unresolved = 0;
        transaction->commit_failed = 0;
        transaction->outcome = outcome;
        return outcome;
    }
    transaction->stages[stage_base] = '\0';
    transaction->unresolved = 1;
    transaction->outcome = SAVE_HOST_OUTCOME_UNCERTAIN;
    return transaction->outcome;
}

int save_host_before_transition(const save_host_context *transaction) {
    return transaction == NULL || (transaction->active == 0 &&
        transaction->commit_failed == 0 &&
        transaction->publication_in_flight == 0 && transaction->unresolved == 0);
}

gn_status save_host_restore(save_host_context *transaction, const void *state,
    size_t state_length, gn_state_detail_v1 *detail, size_t detail_size) {
    if (transaction == NULL || transaction->owner == NULL)
        return GN_STATUS_INVALID_ARGUMENT;
    if (!save_host_before_transition(transaction)) return GN_STATUS_INVALID_STATE;
    return gn_state_restore_v1(transaction->owner, state, state_length,
                               detail, detail_size);
}

gn_status save_host_renew_scope(save_host_context *transaction,
    const gn_mvs_save_scope_v1 *scope, size_t scope_size,
    gn_mvs_save_detail_v1 *detail, size_t detail_size) {
    if (transaction == NULL || transaction->owner == NULL)
        return GN_STATUS_INVALID_ARGUMENT;
    if (!save_host_before_transition(transaction)) return GN_STATUS_INVALID_STATE;
    return gn_mvs_save_scope_renew_v1(transaction->owner, scope, scope_size,
                                      detail, detail_size);
}

int save_host_change_slot(save_host_context *transaction, const char *slot) {
    if (transaction == NULL || !save_host_before_transition(transaction) || slot == NULL ||
        slot[0] == '\0' || strlen(slot) >= sizeof(transaction->slot))
        return 0;
    memcpy(transaction->slot, slot, strlen(slot) + 1u);
    return 1;
}

int save_host_replace(save_host_context *transaction,
    const uint8_t *immutable_bytes, size_t bytes_length,
    const gn_mvs_save_receipt_v1 *receipt, gn_instance *owner) {
    if (transaction == NULL || !save_host_before_transition(transaction) ||
        immutable_bytes == NULL ||
        bytes_length != GN_MVS_SAVE_ENVELOPE_V1_BYTES || receipt == NULL ||
        owner == NULL) return 0;
    transaction->immutable_bytes = immutable_bytes;
    transaction->bytes_length = bytes_length;
    transaction->receipt = *receipt;
    transaction->owner = owner;
    transaction->active = 1;
    return 1;
}

gn_status save_host_unload(save_host_context *transaction,
    gn_mvs_save_lifecycle_policy_v1 policy,
    gn_mvs_save_lifecycle_result_v1 *result, size_t result_size,
    gn_mvs_save_detail_v1 *detail, size_t detail_size) {
    if (transaction == NULL || transaction->owner == NULL)
        return GN_STATUS_INVALID_ARGUMENT;
    const int explicit_failed_discard = policy == GN_MVS_SAVE_LIFECYCLE_ALLOW_DISCARD &&
        transaction->commit_failed != 0 &&
        transaction->publication_in_flight == 0 && transaction->unresolved == 0;
    if (!save_host_before_transition(transaction) && !explicit_failed_discard)
        return GN_STATUS_INVALID_STATE;
    const gn_status status = gn_unload_checked_v1(transaction->owner, policy, 1u,
        result, result_size, detail, detail_size);
    if (status == GN_STATUS_OK) {
        transaction->active = 0;
        transaction->commit_failed = 0;
    }
    return status;
}

gn_status save_host_destroy(save_host_context *transaction,
    gn_mvs_save_lifecycle_policy_v1 policy,
    gn_mvs_save_lifecycle_result_v1 *result, size_t result_size,
    gn_mvs_save_detail_v1 *detail, size_t detail_size) {
    if (transaction == NULL || transaction->owner == NULL)
        return GN_STATUS_INVALID_ARGUMENT;
    const int explicit_failed_discard = policy == GN_MVS_SAVE_LIFECYCLE_ALLOW_DISCARD &&
        transaction->commit_failed != 0 &&
        transaction->publication_in_flight == 0 && transaction->unresolved == 0;
    if (!save_host_before_transition(transaction) && !explicit_failed_discard)
        return GN_STATUS_INVALID_STATE;
    const gn_status status = gn_destroy_checked_v1(&transaction->owner,
        policy, 1u, result, result_size, detail, detail_size);
    if (status == GN_STATUS_OK) {
        transaction->active = 0;
        transaction->commit_failed = 0;
    }
    return status;
}

#else

save_host_read_outcome save_host_read_authoritative(
    const char *path, uint8_t *bytes, size_t capacity) {
    (void)path;
    (void)bytes;
    (void)capacity;
    return SAVE_HOST_READ_INVALID;
}

int save_host_context_init(save_host_context *transaction,
    const char *slot, const uint8_t *immutable_bytes, size_t bytes_length,
    const gn_mvs_save_receipt_v1 *receipt, gn_instance *owner,
    const save_host_faults *faults) {
    (void)transaction;
    (void)slot;
    (void)immutable_bytes;
    (void)bytes_length;
    (void)receipt;
    (void)owner;
    (void)faults;
    return 0;
}

void save_host_set_stage_callback(save_host_context *transaction,
    save_host_stage_callback callback, void *callback_context) {
    (void)transaction;
    (void)callback;
    (void)callback_context;
}

save_host_outcome save_host_commit(save_host_context *transaction) {
    (void)transaction;
    return SAVE_HOST_UNSUPPORTED;
}

save_host_outcome save_host_reconcile(save_host_context *transaction) {
    (void)transaction;
    return SAVE_HOST_UNSUPPORTED;
}

int save_host_before_transition(const save_host_context *transaction) {
    (void)transaction;
    return 1;
}

gn_status save_host_restore(save_host_context *transaction, const void *state,
    size_t state_length, gn_state_detail_v1 *detail, size_t detail_size) {
    (void)transaction;
    (void)state;
    (void)state_length;
    (void)detail;
    (void)detail_size;
    return GN_STATUS_UNSUPPORTED_PROFILE;
}

gn_status save_host_renew_scope(save_host_context *transaction,
    const gn_mvs_save_scope_v1 *scope, size_t scope_size,
    gn_mvs_save_detail_v1 *detail, size_t detail_size) {
    (void)transaction;
    (void)scope;
    (void)scope_size;
    (void)detail;
    (void)detail_size;
    return GN_STATUS_UNSUPPORTED_PROFILE;
}

int save_host_change_slot(save_host_context *transaction, const char *slot) {
    (void)transaction;
    (void)slot;
    return 0;
}

int save_host_replace(save_host_context *transaction,
    const uint8_t *immutable_bytes, size_t bytes_length,
    const gn_mvs_save_receipt_v1 *receipt, gn_instance *owner) {
    (void)transaction;
    (void)immutable_bytes;
    (void)bytes_length;
    (void)receipt;
    (void)owner;
    return 0;
}

gn_status save_host_unload(save_host_context *transaction,
    gn_mvs_save_lifecycle_policy_v1 policy,
    gn_mvs_save_lifecycle_result_v1 *result, size_t result_size,
    gn_mvs_save_detail_v1 *detail, size_t detail_size) {
    (void)transaction;
    (void)policy;
    (void)result;
    (void)result_size;
    (void)detail;
    (void)detail_size;
    return GN_STATUS_UNSUPPORTED_PROFILE;
}

gn_status save_host_destroy(save_host_context *transaction,
    gn_mvs_save_lifecycle_policy_v1 policy,
    gn_mvs_save_lifecycle_result_v1 *result, size_t result_size,
    gn_mvs_save_detail_v1 *detail, size_t detail_size) {
    (void)transaction;
    (void)policy;
    (void)result;
    (void)result_size;
    (void)detail;
    (void)detail_size;
    return GN_STATUS_UNSUPPORTED_PROFILE;
}

#endif
