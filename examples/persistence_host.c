/* SPDX-License-Identifier: MIT
 * Derived from tests/sdk/save_host.[ch] at a73a9f543d8743896a5e4b7d2b28d0189f3e94c8.
 * Glueyneo Maintainers own this sample copy and review drift against that source.
 */
#include "persistence_host.h"

#include <errno.h>
#include <string.h>
#include <sys/stat.h>

#if defined(__APPLE__)
#include <dirent.h>
#include <fcntl.h>
#include <stdio.h>
#include <sys/mount.h>
#include <unistd.h>
#endif

#if defined(__APPLE__) && defined(F_FULLFSYNC)

#ifdef GLUEYNEO_PERSISTENCE_TESTING
#define PERSISTENCE_HOST_FAILURE_UNSET(transaction) \
    ((transaction)->failed_stage[0] == '\0')
#else
#define PERSISTENCE_HOST_FAILURE_UNSET(transaction) 1
#endif
#include <limits.h>
#endif

#if defined(__APPLE__) && defined(F_FULLFSYNC)

static void persistence_host_reason(char *reason, size_t capacity,
                                    const char *value) {
    if (reason == NULL || capacity == 0u) return;
    const size_t length = strlen(value);
    const size_t count = length < capacity - 1u ? length : capacity - 1u;
    memcpy(reason, value, count);
    reason[count] = '\0';
}

int persistence_host_support_reason(const char *directory, char *reason,
                                    size_t reason_capacity) {
    if (reason != NULL && reason_capacity != 0u) reason[0] = '\0';
    if (directory == NULL || directory[0] == '\0') {
        persistence_host_reason(reason, reason_capacity, "scratch_directory_required");
        return 0;
    }
    struct statfs filesystem;
    if (statfs(directory, &filesystem) != 0) {
        persistence_host_reason(reason, reason_capacity, "scratch_directory_unreadable");
        return 0;
    }
    if (strcmp(filesystem.f_fstypename, "apfs") != 0) {
        persistence_host_reason(reason, reason_capacity, "filesystem_not_apfs");
        return 0;
    }
    struct stat status;
    if (stat(directory, &status) != 0 || !S_ISDIR(status.st_mode)) {
        persistence_host_reason(reason, reason_capacity, "scratch_directory_invalid");
        return 0;
    }
    return 1;
}

int persistence_host_scratch_is_fresh(const char *directory) {
    if (directory == NULL || directory[0] == '\0') return 0;
    DIR *stream = opendir(directory);
    if (stream == NULL) return 0;
    int fresh = 1;
    struct dirent *entry;
    errno = 0;
    while ((entry = readdir(stream)) != NULL) {
        if (strcmp(entry->d_name, ".") != 0 &&
            strcmp(entry->d_name, "..") != 0) {
            fresh = 0;
            break;
        }
    }
    if (errno != 0) fresh = 0;
    if (closedir(stream) != 0) fresh = 0;
    return fresh;
}

#else

int persistence_host_support_reason(const char *directory, char *reason,
                                    size_t reason_capacity) {
    (void)directory;
    if (reason != NULL && reason_capacity != 0u) {
#if !defined(__APPLE__)
        const char *value = "host_protocol_requires_darwin_apfs";
#else
        const char *value = "host_protocol_requires_fullfsync";
#endif
        const size_t length = strlen(value);
        const size_t count = length < reason_capacity - 1u
            ? length : reason_capacity - 1u;
        memcpy(reason, value, count);
        reason[count] = '\0';
    }
    return 0;
}

int persistence_host_scratch_is_fresh(const char *directory) {
    (void)directory;
    return 0;
}

#endif

#if defined(__APPLE__) && defined(F_FULLFSYNC)

#ifndef GLUEYNEO_PERSISTENCE_TESTING
typedef enum {
    PERSISTENCE_HOST_FAULT_NONE = 0,
    PERSISTENCE_HOST_FAULT_CREATE,
    PERSISTENCE_HOST_FAULT_WRITE,
    PERSISTENCE_HOST_FAULT_FILE_SYNC,
    PERSISTENCE_HOST_FAULT_FILE_CLOSE,
    PERSISTENCE_HOST_FAULT_RENAME,
    PERSISTENCE_HOST_FAULT_DIRECTORY_OPEN,
    PERSISTENCE_HOST_FAULT_DIRECTORY_SYNC,
    PERSISTENCE_HOST_FAULT_DIRECTORY_CLOSE,
    PERSISTENCE_HOST_FAULT_ACK
} persistence_host_fault_stage;
#endif

static int persistence_host_append_stage(persistence_host_context *transaction,
                                  const char *stage) {
#ifdef GLUEYNEO_PERSISTENCE_TESTING
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
#else
    (void)transaction;
    (void)stage;
    return 1;
#endif
}

static void persistence_host_notify_stage(persistence_host_context *transaction,
                                   const char *stage) {
#ifdef GLUEYNEO_PERSISTENCE_TESTING
    if (transaction->stage_callback != NULL)
        transaction->stage_callback(transaction->stage_callback_context,
                                     stage);
#else
    (void)transaction;
    (void)stage;
#endif
}

static void persistence_host_failure(persistence_host_context *transaction,
                              const char *stage) {
#ifdef GLUEYNEO_PERSISTENCE_TESTING
    const size_t length = strlen(stage);
    const size_t limit = sizeof(transaction->failed_stage) - 1u;
    const size_t copy_length = length < limit ? length : limit;
    memcpy(transaction->failed_stage, stage, copy_length);
    transaction->failed_stage[copy_length] = '\0';
#else
    (void)transaction;
    (void)stage;
#endif
}

static int persistence_host_injected_fault(persistence_host_context *transaction,
                                    persistence_host_fault_stage stage,
                                    const char *name) {
#ifdef GLUEYNEO_PERSISTENCE_TESTING
    if (transaction->initial_fault_consumed == 0 &&
        transaction->faults.fail_once == stage) {
        transaction->initial_fault_consumed = 1;
        persistence_host_failure(transaction, name);
        errno = EIO;
        return 1;
    }
#else
    (void)transaction;
    (void)stage;
    (void)name;
#endif
    return 0;
}

#ifdef GLUEYNEO_PERSISTENCE_TESTING
void persistence_host_test_set_faults(persistence_host_context *transaction,
    const persistence_host_faults *faults) {
    if (transaction != NULL && faults != NULL) transaction->faults = *faults;
}
#endif

static int persistence_host_write_all(persistence_host_context *transaction,
                               int descriptor, const uint8_t *bytes,
                               size_t length, int zero_progress_once) {
    size_t written = 0u;
    unsigned calls = 0u;
    unsigned interruptions = 0u;
#ifdef GLUEYNEO_PERSISTENCE_TESTING
    interruptions = transaction->faults.interrupted_writes;
#endif
    int injected_zero_progress = zero_progress_once;
    int partial_notified = 0;
    while (written < length && calls < PERSISTENCE_HOST_MAX_ATTEMPTS) {
        if (interruptions != 0u) {
            --interruptions;
            ++calls;
            errno = EINTR;
            continue;
        }
        size_t request = length - written;
#ifdef GLUEYNEO_PERSISTENCE_TESTING
        if (transaction->faults.short_write_limit != 0u &&
            request > transaction->faults.short_write_limit)
            request = transaction->faults.short_write_limit;
#endif
        const ssize_t count = injected_zero_progress != 0 ? 0 :
            write(descriptor, bytes + written, request);
        injected_zero_progress = 0;
        ++calls;
        if (count < 0 && errno == EINTR) continue;
        if (count <= 0) return 0;
        written += (size_t)count;
        if (partial_notified == 0 && written < length) {
            persistence_host_notify_stage(transaction, "partial-write");
            partial_notified = 1;
        }
    }
    return written == length;
}

static int persistence_host_parent_path(const char *slot, char *directory,
                                 size_t directory_capacity) {
    char copy[PERSISTENCE_HOST_SLOT_CAPACITY];
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

static int persistence_host_rename(const char *temporary, const char *slot,
                                   int exclusive) {
    if (exclusive != 0) {
#ifdef RENAME_EXCL
        return renamex_np(temporary, slot, RENAME_EXCL);
#else
        errno = ENOTSUP;
        return -1;
#endif
    }
    return rename(temporary, slot);
}

static persistence_host_outcome persistence_host_publish(persistence_host_context *transaction,
                                           int reconciliation) {
    if (transaction->publish_attempts != UINT_MAX)
        ++transaction->publish_attempts;
    char directory[PERSISTENCE_HOST_SLOT_CAPACITY];
    char temporary[PERSISTENCE_HOST_SLOT_CAPACITY + 80u];
    if (!persistence_host_parent_path(transaction->slot, directory,
                               sizeof(directory))) {
        persistence_host_failure(transaction, "slot-path");
        return PERSISTENCE_HOST_NOT_COMMITTED;
    }

    int descriptor = -1;
    unsigned temp_tries = 0u;
    while (descriptor < 0 && temp_tries < PERSISTENCE_HOST_MAX_ATTEMPTS) {
        if (transaction->temp_sequence == UINT_MAX) {
            persistence_host_failure(transaction, "temporary-sequence");
            return PERSISTENCE_HOST_NOT_COMMITTED;
        }
        ++transaction->temp_sequence;
        const int temporary_length = snprintf(temporary, sizeof(temporary),
            "%s.tmp.%ld.%u", transaction->slot, (long)getpid(),
            transaction->temp_sequence);
        if (temporary_length < 0 || (size_t)temporary_length >= sizeof(temporary)) {
            persistence_host_failure(transaction, "temporary-path");
            return PERSISTENCE_HOST_NOT_COMMITTED;
        }
        ++temp_tries;
        if (persistence_host_injected_fault(transaction, PERSISTENCE_HOST_FAULT_CREATE,
                                     "exclusive-create"))
            return PERSISTENCE_HOST_NOT_COMMITTED;
        descriptor = open(temporary, O_WRONLY | O_CREAT | O_EXCL, 0600);
        if (descriptor < 0 && errno != EEXIST) {
            persistence_host_failure(transaction, "exclusive-create");
            return PERSISTENCE_HOST_NOT_COMMITTED;
        }
    }
    if (descriptor < 0) {
        persistence_host_failure(transaction, "temporary-collision-bound");
        return PERSISTENCE_HOST_NOT_COMMITTED;
    }
    (void)persistence_host_append_stage(transaction, "temp-created");

    const int injected_write_stall = persistence_host_injected_fault(transaction,
        PERSISTENCE_HOST_FAULT_WRITE, "write");
    if (!persistence_host_write_all(transaction, descriptor,
            transaction->immutable_bytes, transaction->bytes_length,
            injected_write_stall)) {
        if (PERSISTENCE_HOST_FAILURE_UNSET(transaction))
            persistence_host_failure(transaction, "write");
        (void)close(descriptor);
        (void)unlink(temporary);
        return PERSISTENCE_HOST_NOT_COMMITTED;
    }
    (void)persistence_host_append_stage(transaction, "write");

    if (persistence_host_injected_fault(transaction, PERSISTENCE_HOST_FAULT_FILE_SYNC,
                                 "file-fullfsync") ||
        fcntl(descriptor, F_FULLFSYNC) != 0) {
        if (PERSISTENCE_HOST_FAILURE_UNSET(transaction))
            persistence_host_failure(transaction, "file-fullfsync");
        (void)close(descriptor);
        (void)unlink(temporary);
        return PERSISTENCE_HOST_NOT_COMMITTED;
    }
    (void)persistence_host_append_stage(transaction, "file-fullfsync");

    const int injected_close = persistence_host_injected_fault(transaction,
        PERSISTENCE_HOST_FAULT_FILE_CLOSE, "file-close");
    const int file_close_status = close(descriptor);
    descriptor = -1;
    if (injected_close != 0 || file_close_status != 0) {
        if (PERSISTENCE_HOST_FAILURE_UNSET(transaction))
            persistence_host_failure(transaction, "file-close");
        (void)unlink(temporary);
        return PERSISTENCE_HOST_NOT_COMMITTED;
    }
    (void)persistence_host_append_stage(transaction, "file-close");

    if (persistence_host_injected_fault(transaction, PERSISTENCE_HOST_FAULT_RENAME, "rename") ||
        persistence_host_rename(temporary, transaction->slot,
            transaction->replace_existing == 0 && reconciliation == 0) != 0) {
        if (PERSISTENCE_HOST_FAILURE_UNSET(transaction))
            persistence_host_failure(transaction, "rename");
        (void)unlink(temporary);
        return PERSISTENCE_HOST_NOT_COMMITTED;
    }
    (void)persistence_host_append_stage(transaction, "rename");
#ifdef GLUEYNEO_PERSISTENCE_TESTING
    if (reconciliation == 0 && transaction->faults.fail_after_rename != 0) {
        transaction->faults.fail_after_rename = 0;
        persistence_host_failure(transaction, "after-rename");
        return PERSISTENCE_HOST_OUTCOME_UNCERTAIN;
    }
#endif

    if (persistence_host_injected_fault(transaction, PERSISTENCE_HOST_FAULT_DIRECTORY_OPEN,
                                 "directory-open"))
        return PERSISTENCE_HOST_OUTCOME_UNCERTAIN;
    const int directory_fd = open(directory, O_RDONLY);
    if (directory_fd < 0) {
        persistence_host_failure(transaction, "directory-open");
        return PERSISTENCE_HOST_OUTCOME_UNCERTAIN;
    }
    (void)persistence_host_append_stage(transaction, "directory-open");

    int sync_failed = 0;
#ifdef GLUEYNEO_PERSISTENCE_TESTING
    if (reconciliation != 0 &&
        transaction->faults.retry_directory_sync_failures != 0u) {
        --transaction->faults.retry_directory_sync_failures;
        errno = EIO;
        sync_failed = 1;
    } else
#endif
    if (persistence_host_injected_fault(transaction,
                   PERSISTENCE_HOST_FAULT_DIRECTORY_SYNC, "directory-fsync")) {
        sync_failed = 1;
    } else if (fsync(directory_fd) != 0) {
        persistence_host_failure(transaction, "directory-fsync");
        sync_failed = 1;
    }
    if (sync_failed != 0) {
        if (PERSISTENCE_HOST_FAILURE_UNSET(transaction))
            persistence_host_failure(transaction, "directory-fsync");
        (void)close(directory_fd);
        return PERSISTENCE_HOST_OUTCOME_UNCERTAIN;
    }
    (void)persistence_host_append_stage(transaction, "directory-fsync");

    const int injected_directory_close = persistence_host_injected_fault(transaction,
        PERSISTENCE_HOST_FAULT_DIRECTORY_CLOSE, "directory-close");
    const int directory_close_status = close(directory_fd);
    if (injected_directory_close != 0 || directory_close_status != 0) {
        if (PERSISTENCE_HOST_FAILURE_UNSET(transaction))
            persistence_host_failure(transaction, "directory-close");
        return PERSISTENCE_HOST_OUTCOME_UNCERTAIN;
    }
    (void)persistence_host_append_stage(transaction, "directory-close");

    persistence_host_notify_stage(transaction, "protocol-complete");

    if (persistence_host_injected_fault(transaction, PERSISTENCE_HOST_FAULT_ACK, "ack"))
        return PERSISTENCE_HOST_OUTCOME_UNCERTAIN;
    gn_mvs_save_detail_v1 detail;
    memset(&detail, 0, sizeof(detail));
    if (gn_mvs_save_ack_v1(transaction->owner, &transaction->receipt,
            sizeof(transaction->receipt), &detail, sizeof(detail)) != GN_STATUS_OK) {
        persistence_host_failure(transaction, "ack");
        return PERSISTENCE_HOST_OUTCOME_UNCERTAIN;
    }
    (void)persistence_host_append_stage(transaction, "ack");
    return PERSISTENCE_HOST_COMMITTED;
}

persistence_host_read_outcome persistence_host_read_authoritative(
    const char *path, uint8_t *bytes, size_t capacity) {
    if (path == NULL || bytes == NULL ||
        capacity != GN_MVS_SAVE_ENVELOPE_V1_BYTES) return PERSISTENCE_HOST_READ_INVALID;
    const int descriptor = open(path, O_RDONLY | O_NONBLOCK);
    if (descriptor < 0)
        return errno == ENOENT ? PERSISTENCE_HOST_READ_MISSING : PERSISTENCE_HOST_READ_INVALID;
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
    return ok && offset == capacity ? PERSISTENCE_HOST_READ_READY
                                    : PERSISTENCE_HOST_READ_INVALID;
}

int persistence_host_context_init(persistence_host_context *transaction,
    const char *slot, const uint8_t *immutable_bytes, size_t bytes_length,
    const gn_mvs_save_receipt_v1 *receipt, gn_instance *owner,
    int replace_existing) {
    if (transaction == NULL || slot == NULL || immutable_bytes == NULL ||
        receipt == NULL || owner == NULL || bytes_length !=
            GN_MVS_SAVE_ENVELOPE_V1_BYTES || slot[0] == '\0' ||
        strlen(slot) >= PERSISTENCE_HOST_SLOT_CAPACITY)
        return 0;
    memset(transaction, 0, sizeof(*transaction));
    memcpy(transaction->slot, slot, strlen(slot) + 1u);
    transaction->immutable_bytes = immutable_bytes;
    transaction->bytes_length = bytes_length;
    transaction->receipt = *receipt;
    transaction->owner = owner;
    transaction->outcome = PERSISTENCE_HOST_NOT_COMMITTED;
    transaction->replace_existing = replace_existing != 0;
    if (replace_existing == 0) {
        struct stat existing;
        if (lstat(slot, &existing) == 0 || errno != ENOENT) return 0;
    }
    transaction->active = 1;
    return 1;
}

#ifdef GLUEYNEO_PERSISTENCE_TESTING
void persistence_host_set_stage_callback(persistence_host_context *transaction,
    persistence_host_stage_callback callback, void *callback_context) {
    if (transaction == NULL) return;
    transaction->stage_callback = callback;
    transaction->stage_callback_context = callback_context;
}
#endif

persistence_host_outcome persistence_host_commit(persistence_host_context *transaction) {
    if (transaction == NULL || transaction->active == 0 ||
        transaction->unresolved != 0 || transaction->owner == NULL ||
        transaction->immutable_bytes == NULL || transaction->bytes_length !=
            GN_MVS_SAVE_ENVELOPE_V1_BYTES) return PERSISTENCE_HOST_NOT_COMMITTED;
#ifdef GLUEYNEO_PERSISTENCE_TESTING
    transaction->failed_stage[0] = '\0';
#endif
    transaction->publication_in_flight = 1;
    transaction->outcome = persistence_host_publish(transaction, 0);
    transaction->publication_in_flight = 0;
    transaction->unresolved =
        transaction->outcome == PERSISTENCE_HOST_OUTCOME_UNCERTAIN;
    transaction->commit_failed =
        transaction->outcome == PERSISTENCE_HOST_NOT_COMMITTED;
    transaction->active = transaction->commit_failed;
    return transaction->outcome;
}

persistence_host_outcome persistence_host_reconcile(persistence_host_context *transaction) {
    if (transaction == NULL || transaction->unresolved == 0 ||
        transaction->owner == NULL ||
        transaction->immutable_bytes == NULL || transaction->bytes_length !=
            GN_MVS_SAVE_ENVELOPE_V1_BYTES) return PERSISTENCE_HOST_OUTCOME_UNCERTAIN;
    if (transaction->retry_attempts != UINT_MAX)
        ++transaction->retry_attempts;
#ifdef GLUEYNEO_PERSISTENCE_TESTING
    const size_t stage_base = strlen(transaction->stages);
    transaction->failed_stage[0] = '\0';
#endif
    transaction->active = 1;
    transaction->publication_in_flight = 1;
    persistence_host_outcome outcome = persistence_host_publish(transaction, 1);
    transaction->publication_in_flight = 0;
    transaction->active = 0;
    if (outcome == PERSISTENCE_HOST_COMMITTED) {
        transaction->unresolved = 0;
        transaction->commit_failed = 0;
        transaction->outcome = outcome;
        return outcome;
    }
#ifdef GLUEYNEO_PERSISTENCE_TESTING
    transaction->stages[stage_base] = '\0';
#endif
    transaction->unresolved = 1;
    transaction->outcome = PERSISTENCE_HOST_OUTCOME_UNCERTAIN;
    return transaction->outcome;
}

int persistence_host_before_transition(const persistence_host_context *transaction) {
    return transaction == NULL || (transaction->active == 0 &&
        transaction->commit_failed == 0 &&
        transaction->publication_in_flight == 0 && transaction->unresolved == 0);
}

gn_status persistence_host_restore(persistence_host_context *transaction, const void *state,
    size_t state_length, gn_state_detail_v1 *detail, size_t detail_size) {
    if (transaction == NULL || transaction->owner == NULL)
        return GN_STATUS_INVALID_ARGUMENT;
    if (!persistence_host_before_transition(transaction)) return GN_STATUS_INVALID_STATE;
    return gn_state_restore_v1(transaction->owner, state, state_length,
                               detail, detail_size);
}

gn_status persistence_host_renew_scope(persistence_host_context *transaction,
    const gn_mvs_save_scope_v1 *scope, size_t scope_size,
    gn_mvs_save_detail_v1 *detail, size_t detail_size) {
    if (transaction == NULL || transaction->owner == NULL)
        return GN_STATUS_INVALID_ARGUMENT;
    if (!persistence_host_before_transition(transaction)) return GN_STATUS_INVALID_STATE;
    return gn_mvs_save_scope_renew_v1(transaction->owner, scope, scope_size,
                                      detail, detail_size);
}

int persistence_host_change_slot(persistence_host_context *transaction, const char *slot) {
    if (transaction == NULL || !persistence_host_before_transition(transaction) || slot == NULL ||
        slot[0] == '\0' || strlen(slot) >= sizeof(transaction->slot))
        return 0;
    memcpy(transaction->slot, slot, strlen(slot) + 1u);
    return 1;
}

int persistence_host_replace(persistence_host_context *transaction,
    const uint8_t *immutable_bytes, size_t bytes_length,
    const gn_mvs_save_receipt_v1 *receipt, gn_instance *owner) {
    if (transaction == NULL || !persistence_host_before_transition(transaction) ||
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

gn_status persistence_host_unload(persistence_host_context *transaction,
    gn_mvs_save_lifecycle_policy_v1 policy,
    gn_mvs_save_lifecycle_result_v1 *result, size_t result_size,
    gn_mvs_save_detail_v1 *detail, size_t detail_size) {
    if (transaction == NULL || transaction->owner == NULL)
        return GN_STATUS_INVALID_ARGUMENT;
    const int explicit_failed_discard = policy == GN_MVS_SAVE_LIFECYCLE_ALLOW_DISCARD &&
        transaction->commit_failed != 0 &&
        transaction->publication_in_flight == 0 && transaction->unresolved == 0;
    if (!persistence_host_before_transition(transaction) && !explicit_failed_discard)
        return GN_STATUS_INVALID_STATE;
    const gn_status status = gn_unload_checked_v1(transaction->owner, policy, 1u,
        result, result_size, detail, detail_size);
    if (status == GN_STATUS_OK) {
        transaction->active = 0;
        transaction->commit_failed = 0;
    }
    return status;
}

gn_status persistence_host_destroy(persistence_host_context *transaction,
    gn_mvs_save_lifecycle_policy_v1 policy,
    gn_mvs_save_lifecycle_result_v1 *result, size_t result_size,
    gn_mvs_save_detail_v1 *detail, size_t detail_size) {
    if (transaction == NULL || transaction->owner == NULL)
        return GN_STATUS_INVALID_ARGUMENT;
    const int explicit_failed_discard = policy == GN_MVS_SAVE_LIFECYCLE_ALLOW_DISCARD &&
        transaction->commit_failed != 0 &&
        transaction->publication_in_flight == 0 && transaction->unresolved == 0;
    if (!persistence_host_before_transition(transaction) && !explicit_failed_discard)
        return GN_STATUS_INVALID_STATE;
    const gn_status status = gn_destroy_checked_v1(&transaction->owner,
        policy, 1u, result, result_size, detail, detail_size);
    if (status == GN_STATUS_OK) {
        transaction->active = 0;
        transaction->commit_failed = 0;
    }
    return status;
}

gn_status persistence_host_discard(persistence_host_context *transaction,
    gn_mvs_save_lifecycle_result_v1 *result, size_t result_size,
    gn_mvs_save_detail_v1 *detail, size_t detail_size) {
    if (transaction == NULL || transaction->owner == NULL ||
        transaction->publication_in_flight != 0) return GN_STATUS_INVALID_STATE;
    transaction->unresolved = 0;
    transaction->active = 0;
    return persistence_host_destroy(transaction,
        GN_MVS_SAVE_LIFECYCLE_ALLOW_DISCARD, result, result_size,
        detail, detail_size);
}

#else

persistence_host_read_outcome persistence_host_read_authoritative(
    const char *path, uint8_t *bytes, size_t capacity) {
    (void)path;
    (void)bytes;
    (void)capacity;
    return PERSISTENCE_HOST_READ_INVALID;
}

int persistence_host_context_init(persistence_host_context *transaction,
    const char *slot, const uint8_t *immutable_bytes, size_t bytes_length,
    const gn_mvs_save_receipt_v1 *receipt, gn_instance *owner,
    int replace_existing) {
    (void)transaction;
    (void)slot;
    (void)immutable_bytes;
    (void)bytes_length;
    (void)receipt;
    (void)owner;
    (void)replace_existing;
    return 0;
}

#ifdef GLUEYNEO_PERSISTENCE_TESTING
void persistence_host_test_set_faults(persistence_host_context *transaction,
    const persistence_host_faults *faults) {
    (void)transaction;
    (void)faults;
}

void persistence_host_set_stage_callback(persistence_host_context *transaction,
    persistence_host_stage_callback callback, void *callback_context) {
    (void)transaction;
    (void)callback;
    (void)callback_context;
}
#endif

persistence_host_outcome persistence_host_commit(persistence_host_context *transaction) {
    (void)transaction;
    return PERSISTENCE_HOST_UNSUPPORTED;
}

persistence_host_outcome persistence_host_reconcile(persistence_host_context *transaction) {
    (void)transaction;
    return PERSISTENCE_HOST_UNSUPPORTED;
}

int persistence_host_before_transition(const persistence_host_context *transaction) {
    (void)transaction;
    return 1;
}

gn_status persistence_host_restore(persistence_host_context *transaction, const void *state,
    size_t state_length, gn_state_detail_v1 *detail, size_t detail_size) {
    (void)transaction;
    (void)state;
    (void)state_length;
    (void)detail;
    (void)detail_size;
    return GN_STATUS_UNSUPPORTED_PROFILE;
}

gn_status persistence_host_renew_scope(persistence_host_context *transaction,
    const gn_mvs_save_scope_v1 *scope, size_t scope_size,
    gn_mvs_save_detail_v1 *detail, size_t detail_size) {
    (void)transaction;
    (void)scope;
    (void)scope_size;
    (void)detail;
    (void)detail_size;
    return GN_STATUS_UNSUPPORTED_PROFILE;
}

int persistence_host_change_slot(persistence_host_context *transaction, const char *slot) {
    (void)transaction;
    (void)slot;
    return 0;
}

int persistence_host_replace(persistence_host_context *transaction,
    const uint8_t *immutable_bytes, size_t bytes_length,
    const gn_mvs_save_receipt_v1 *receipt, gn_instance *owner) {
    (void)transaction;
    (void)immutable_bytes;
    (void)bytes_length;
    (void)receipt;
    (void)owner;
    return 0;
}

gn_status persistence_host_unload(persistence_host_context *transaction,
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

gn_status persistence_host_destroy(persistence_host_context *transaction,
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

gn_status persistence_host_discard(persistence_host_context *transaction,
    gn_mvs_save_lifecycle_result_v1 *result, size_t result_size,
    gn_mvs_save_detail_v1 *detail, size_t detail_size) {
    (void)transaction;
    (void)result;
    (void)result_size;
    (void)detail;
    (void)detail_size;
    return GN_STATUS_UNSUPPORTED_PROFILE;
}

#endif
