/* SPDX-License-Identifier: MIT
 * Derived from tests/sdk/save_host.[ch] at a73a9f543d8743896a5e4b7d2b28d0189f3e94c8.
 * Glueyneo Maintainers own this sample copy and review drift against that source.
 */
#ifndef GLUEYNEO_EXAMPLE_PERSISTENCE_HOST_H
#define GLUEYNEO_EXAMPLE_PERSISTENCE_HOST_H

#include "glueyneo/glueyneo.h"

#include <stddef.h>
#include <stdint.h>

enum {
    PERSISTENCE_HOST_SLOT_CAPACITY = 4096u,
    PERSISTENCE_HOST_STAGE_CAPACITY = 2048u,
    PERSISTENCE_HOST_MAX_ATTEMPTS = 32u
};

typedef enum {
    PERSISTENCE_HOST_NOT_COMMITTED = 0,
    PERSISTENCE_HOST_COMMITTED,
    PERSISTENCE_HOST_OUTCOME_UNCERTAIN,
    PERSISTENCE_HOST_UNSUPPORTED
} persistence_host_outcome;

typedef enum {
    PERSISTENCE_HOST_READ_INVALID = 0,
    PERSISTENCE_HOST_READ_MISSING,
    PERSISTENCE_HOST_READ_READY,
    PERSISTENCE_HOST_READ_NOT_APPLICABLE
} persistence_host_read_outcome;

#ifdef GLUEYNEO_PERSISTENCE_TESTING
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

typedef struct {
    persistence_host_fault_stage fail_once;
    unsigned short_write_limit;
    unsigned interrupted_writes;
    unsigned retry_directory_sync_failures;
    int fail_after_rename;
} persistence_host_faults;

typedef void (*persistence_host_stage_callback)(void *context, const char *stage);
#endif

/* Host-owned transaction. The caller retains immutable_bytes until resolved. */
typedef struct {
    char slot[PERSISTENCE_HOST_SLOT_CAPACITY];
    const uint8_t *immutable_bytes;
    size_t bytes_length;
    gn_mvs_save_receipt_v1 receipt;
    gn_instance *owner;
    persistence_host_outcome outcome;
#ifdef GLUEYNEO_PERSISTENCE_TESTING
    persistence_host_faults faults;
    char stages[PERSISTENCE_HOST_STAGE_CAPACITY];
    char failed_stage[32];
    persistence_host_stage_callback stage_callback;
    void *stage_callback_context;
#endif
    unsigned publish_attempts;
    unsigned retry_attempts;
    unsigned temp_sequence;
    int replace_existing;
    int active;
    int commit_failed;
    int unresolved;
    int publication_in_flight;
#ifdef GLUEYNEO_PERSISTENCE_TESTING
    int initial_fault_consumed;
#endif
} persistence_host_context;

persistence_host_read_outcome persistence_host_read_authoritative(
    const char *path, uint8_t *bytes, size_t capacity);

int persistence_host_context_init(persistence_host_context *transaction,
    const char *slot, const uint8_t *immutable_bytes, size_t bytes_length,
    const gn_mvs_save_receipt_v1 *receipt, gn_instance *owner,
    int replace_existing);

#ifdef GLUEYNEO_PERSISTENCE_TESTING
void persistence_host_test_set_faults(persistence_host_context *transaction,
    const persistence_host_faults *faults);
void persistence_host_set_stage_callback(persistence_host_context *transaction,
    persistence_host_stage_callback callback, void *callback_context);
#endif

int persistence_host_support_reason(const char *directory,
    char *reason, size_t reason_capacity);
int persistence_host_scratch_is_fresh(const char *directory);
gn_status persistence_host_discard(persistence_host_context *transaction,
    gn_mvs_save_lifecycle_result_v1 *result, size_t result_size,
    gn_mvs_save_detail_v1 *detail, size_t detail_size);

persistence_host_outcome persistence_host_commit(persistence_host_context *transaction);
persistence_host_outcome persistence_host_reconcile(persistence_host_context *transaction);
int persistence_host_before_transition(const persistence_host_context *transaction);
gn_status persistence_host_restore(persistence_host_context *transaction, const void *state,
    size_t state_length, gn_state_detail_v1 *detail, size_t detail_size);
gn_status persistence_host_renew_scope(persistence_host_context *transaction,
    const gn_mvs_save_scope_v1 *scope, size_t scope_size,
    gn_mvs_save_detail_v1 *detail, size_t detail_size);
int persistence_host_change_slot(persistence_host_context *transaction, const char *slot);
int persistence_host_replace(persistence_host_context *transaction,
    const uint8_t *immutable_bytes, size_t bytes_length,
    const gn_mvs_save_receipt_v1 *receipt, gn_instance *owner);
gn_status persistence_host_unload(persistence_host_context *transaction,
    gn_mvs_save_lifecycle_policy_v1 policy,
    gn_mvs_save_lifecycle_result_v1 *result, size_t result_size,
    gn_mvs_save_detail_v1 *detail, size_t detail_size);
gn_status persistence_host_destroy(persistence_host_context *transaction,
    gn_mvs_save_lifecycle_policy_v1 policy,
    gn_mvs_save_lifecycle_result_v1 *result, size_t result_size,
    gn_mvs_save_detail_v1 *detail, size_t detail_size);

#endif
