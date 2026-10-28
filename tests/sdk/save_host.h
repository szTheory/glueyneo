/* SPDX-License-Identifier: MIT; private SDK persistence witness. */
#ifndef GLUEYNEO_TESTS_SDK_SAVE_HOST_H
#define GLUEYNEO_TESTS_SDK_SAVE_HOST_H

#include "glueyneo/glueyneo.h"

#include <stddef.h>
#include <stdint.h>

enum {
    SAVE_HOST_SLOT_CAPACITY = 4096u,
    SAVE_HOST_STAGE_CAPACITY = 2048u,
    SAVE_HOST_MAX_ATTEMPTS = 32u
};

typedef enum {
    SAVE_HOST_NOT_COMMITTED = 0,
    SAVE_HOST_COMMITTED,
    SAVE_HOST_OUTCOME_UNCERTAIN,
    SAVE_HOST_UNSUPPORTED
} save_host_outcome;

typedef enum {
    SAVE_HOST_READ_INVALID = 0,
    SAVE_HOST_READ_MISSING,
    SAVE_HOST_READ_READY,
    SAVE_HOST_READ_NOT_APPLICABLE
} save_host_read_outcome;

typedef enum {
    SAVE_HOST_FAULT_NONE = 0,
    SAVE_HOST_FAULT_CREATE,
    SAVE_HOST_FAULT_WRITE,
    SAVE_HOST_FAULT_FILE_SYNC,
    SAVE_HOST_FAULT_FILE_CLOSE,
    SAVE_HOST_FAULT_RENAME,
    SAVE_HOST_FAULT_DIRECTORY_OPEN,
    SAVE_HOST_FAULT_DIRECTORY_SYNC,
    SAVE_HOST_FAULT_DIRECTORY_CLOSE,
    SAVE_HOST_FAULT_ACK
} save_host_fault_stage;

typedef struct {
    save_host_fault_stage fail_once;
    unsigned short_write_limit;
    unsigned interrupted_writes;
    unsigned retry_directory_sync_failures;
    int fail_after_rename;
} save_host_faults;

typedef void (*save_host_stage_callback)(void *context, const char *stage);

/* Host-owned transaction. The caller retains immutable_bytes until resolved. */
typedef struct {
    char slot[SAVE_HOST_SLOT_CAPACITY];
    const uint8_t *immutable_bytes;
    size_t bytes_length;
    gn_mvs_save_receipt_v1 receipt;
    gn_instance *owner;
    save_host_outcome outcome;
    save_host_faults faults;
    char stages[SAVE_HOST_STAGE_CAPACITY];
    char failed_stage[32];
    save_host_stage_callback stage_callback;
    void *stage_callback_context;
    unsigned publish_attempts;
    unsigned retry_attempts;
    unsigned temp_sequence;
    int active;
    int commit_failed;
    int unresolved;
    int publication_in_flight;
    int initial_fault_consumed;
} save_host_context;

save_host_read_outcome save_host_read_authoritative(
    const char *path, uint8_t *bytes, size_t capacity);

int save_host_context_init(save_host_context *transaction,
    const char *slot, const uint8_t *immutable_bytes, size_t bytes_length,
    const gn_mvs_save_receipt_v1 *receipt, gn_instance *owner,
    const save_host_faults *faults);

void save_host_set_stage_callback(save_host_context *transaction,
    save_host_stage_callback callback, void *callback_context);

save_host_outcome save_host_commit(save_host_context *transaction);
save_host_outcome save_host_reconcile(save_host_context *transaction);
int save_host_before_transition(const save_host_context *transaction);
gn_status save_host_restore(save_host_context *transaction, const void *state,
    size_t state_length, gn_state_detail_v1 *detail, size_t detail_size);
gn_status save_host_renew_scope(save_host_context *transaction,
    const gn_mvs_save_scope_v1 *scope, size_t scope_size,
    gn_mvs_save_detail_v1 *detail, size_t detail_size);
int save_host_change_slot(save_host_context *transaction, const char *slot);
int save_host_replace(save_host_context *transaction,
    const uint8_t *immutable_bytes, size_t bytes_length,
    const gn_mvs_save_receipt_v1 *receipt, gn_instance *owner);
gn_status save_host_unload(save_host_context *transaction,
    gn_mvs_save_lifecycle_policy_v1 policy,
    gn_mvs_save_lifecycle_result_v1 *result, size_t result_size,
    gn_mvs_save_detail_v1 *detail, size_t detail_size);
gn_status save_host_destroy(save_host_context *transaction,
    gn_mvs_save_lifecycle_policy_v1 policy,
    gn_mvs_save_lifecycle_result_v1 *result, size_t result_size,
    gn_mvs_save_detail_v1 *detail, size_t detail_size);

#endif
