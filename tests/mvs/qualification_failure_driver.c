/* SPDX-License-Identifier: MIT */
#include "../support/portable_stdio.h"

#include "glueyneo/glueyneo.h"
#include "sdk_private.h"

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int gn_mvs_qualify_parse_bundle(const uint8_t *bytes, size_t size,
                                gn_mvs_manifest *manifest);
int gn_mvs_qualify_execute(gn_instance *instance);
int gn_mvs_qualify_test_active(gn_instance *instance, int phase,
                              const char *capture_directory);

static int load_bytes(const char *path, uint8_t **out_bytes, size_t *out_size) {
    *out_bytes = NULL;
    *out_size = 0u;
    FILE *file = gn_portable_fopen(path, "rb");
    if (file == NULL || fseek(file, 0, SEEK_END) != 0) {
        if (file != NULL) fclose(file);
        return 0;
    }
    const long length = ftell(file);
    if (length < 0 || fseek(file, 0, SEEK_SET) != 0) {
        fclose(file);
        return 0;
    }
    uint8_t *bytes = (uint8_t *)malloc((size_t)length);
    if (bytes == NULL || fread(bytes, 1u, (size_t)length, file) != (size_t)length) {
        free(bytes);
        fclose(file);
        return 0;
    }
    fclose(file);
    *out_bytes = bytes;
    *out_size = (size_t)length;
    return 1;
}

static int make_instance(const gn_mvs_manifest *manifest, gn_instance **out_instance) {
    *out_instance = NULL;
    return gn_create(out_instance) == GN_STATUS_OK && *out_instance != NULL &&
           gn_load_mvs(*out_instance, manifest) == GN_STATUS_OK;
}

static int failure_is_clear(const gn_mvs_failure *failure) {
    gn_mvs_failure empty;
    memset(&empty, 0, sizeof(empty));
    if (failure->instruction_boundary_valid > 1u) return 0;
    empty.instruction_boundary_valid = failure->instruction_boundary_valid;
    return memcmp(failure, &empty, sizeof(empty)) == 0;
}

static int run_reset_isolation(const gn_mvs_manifest *manifest) {
    gn_instance *first = NULL;
    gn_instance *second = NULL;
    gn_mvs_failure observer_failure;
    memset(&observer_failure, 0xa5, sizeof(observer_failure));
    if (gn_private_mvs_failure(NULL, &observer_failure) !=
            GN_STATUS_INVALID_ARGUMENT || !failure_is_clear(&observer_failure))
        return 0;
    gn_instance *unloaded = NULL;
    if (gn_create(&unloaded) != GN_STATUS_OK || unloaded == NULL) return 0;
    memset(&observer_failure, 0xa5, sizeof(observer_failure));
    const gn_status unloaded_status =
        gn_private_mvs_failure(unloaded, &observer_failure);
    gn_destroy(unloaded);
    if (unloaded_status != GN_STATUS_INVALID_STATE ||
        !failure_is_clear(&observer_failure)) return 0;
    if (!make_instance(manifest, &first) || !make_instance(manifest, &second)) {
        gn_destroy(first);
        gn_destroy(second);
        return 0;
    }
    if (gn_test_mvs_set_failure(first, GN_TEST_MVS_FAILURE_MAIN_OBSERVE) !=
            GN_STATUS_OK ||
        gn_test_mvs_set_failure(second, GN_TEST_MVS_FAILURE_SOUND_BUS) !=
            GN_STATUS_OK) goto failed;
    gn_run_result run;
    if (gn_run_mvs(first, GN_MAX_CYCLE_BUDGET, &run) != GN_STATUS_CPU_FAILURE)
        goto failed;
    gn_mvs_failure first_failure;
    gn_mvs_failure second_failure;
    if (gn_private_mvs_failure(first, &first_failure) != GN_STATUS_OK ||
        first_failure.valid == 0u ||
        gn_private_mvs_failure(second, &second_failure) != GN_STATUS_OK ||
        second_failure.valid != 0u) goto failed;
    const gn_mvs_failure first_observer_failure = first_failure;
    if (gn_run_mvs(second, GN_MAX_CYCLE_BUDGET, &run) != GN_STATUS_CPU_FAILURE ||
        gn_private_mvs_failure(second, &second_failure) != GN_STATUS_OK ||
        second_failure.component != GN_MVS_FAILURE_COMPONENT_SOUND_CPU ||
        second_failure.site != GN_MVS_FAILURE_SITE_SOUND_IO_WRITE ||
        second_failure.underlying_status != GN_MVS_FAILURE_STATUS_Z80_BUS_FAILURE ||
        second_failure.bus_address != UINT32_C(0x5a02)) goto failed;
    const gn_mvs_failure second_sound_failure = second_failure;
    if (gn_private_mvs_failure(first, &first_failure) != GN_STATUS_OK ||
        memcmp(&first_observer_failure, &first_failure,
               sizeof(first_failure)) != 0) goto failed;
    if (gn_reset(first) != GN_STATUS_OK) goto failed;
    if (gn_private_mvs_failure(first, &first_failure) != GN_STATUS_OK ||
        !failure_is_clear(&first_failure)) goto failed;
    if (gn_private_mvs_failure(second, &second_failure) != GN_STATUS_OK ||
        memcmp(&second_sound_failure, &second_failure,
               sizeof(second_failure)) != 0) goto failed;
    if (gn_test_mvs_set_failure(first,
            GN_TEST_MVS_FAILURE_MAIN_AFTER_INSTRUCTION) != GN_STATUS_OK ||
        gn_run_mvs(first, GN_MAX_CYCLE_BUDGET, &run) != GN_STATUS_CPU_FAILURE ||
        gn_private_mvs_failure(first, &first_failure) != GN_STATUS_OK ||
        first_failure.component != GN_MVS_FAILURE_COMPONENT_MAIN_CPU ||
        first_failure.site != GN_MVS_FAILURE_SITE_MAIN_EXECUTION ||
        first_failure.completed_main_instructions != 1u) goto failed;
    if (gn_unload(first) != GN_STATUS_OK) goto failed;
    memset(&first_failure, 0xa5, sizeof(first_failure));
    if (gn_private_mvs_failure(first, &first_failure) != GN_STATUS_INVALID_STATE ||
        !failure_is_clear(&first_failure) ||
        gn_load_mvs(first, manifest) != GN_STATUS_OK ||
        gn_private_mvs_failure(first, &first_failure) != GN_STATUS_OK ||
        !failure_is_clear(&first_failure)) goto failed;
    if (gn_test_mvs_set_failure(first,
            GN_TEST_MVS_FAILURE_SOUND_TICK_LIMIT) != GN_STATUS_OK ||
        gn_run_mvs(first, GN_MAX_CYCLE_BUDGET, &run) != GN_STATUS_CPU_FAILURE ||
        gn_private_mvs_failure(first, &first_failure) != GN_STATUS_OK ||
        first_failure.component != GN_MVS_FAILURE_COMPONENT_SOUND_CPU ||
        first_failure.site != GN_MVS_FAILURE_SITE_SOUND_TICK ||
        first_failure.underlying_status != GN_MVS_FAILURE_STATUS_Z80_CYCLE_LIMIT ||
        gn_private_mvs_failure(second, &second_failure) != GN_STATUS_OK ||
        memcmp(&second_sound_failure, &second_failure,
               sizeof(second_failure)) != 0) goto failed;
    puts("{\"status\":\"diagnostic_reset_isolation_pass\","
         "\"coverage\":{\"unloaded_observation\":true,"
         "\"reset_then_distinct_failure\":true,"
         "\"unload_reload_clears_detail\":true,"
         "\"interleaved_instances\":true}}");
    gn_destroy(second);
    gn_destroy(first);
    return 1;

failed:
    puts("{\"status\":\"diagnostic_reset_isolation_failed\"}");
    gn_destroy(second);
    gn_destroy(first);
    return 0;
}

static int select_failure(gn_instance *instance, const char *name) {
    if (strcmp(name, "main_failure_before_instruction") == 0)
        return gn_test_mvs_set_failure(instance, GN_TEST_MVS_FAILURE_MAIN_OBSERVE) ==
               GN_STATUS_OK;
    if (strcmp(name, "main_failure_after_instruction") == 0)
        return gn_test_mvs_set_failure(instance,
            GN_TEST_MVS_FAILURE_MAIN_AFTER_INSTRUCTION) == GN_STATUS_OK;
    if (strcmp(name, "sound_tick_limit") == 0)
        return gn_test_mvs_set_failure(instance,
            GN_TEST_MVS_FAILURE_SOUND_TICK_LIMIT) == GN_STATUS_OK;
    if (strcmp(name, "sound_before_main_progress") == 0)
        return gn_test_mvs_set_failure(instance,
            GN_TEST_MVS_FAILURE_SOUND_BEFORE_MAIN_PROGRESS) == GN_STATUS_OK;
    if (strcmp(name, "first_error_precedence") == 0)
        return gn_test_mvs_set_failure(instance,
            GN_TEST_MVS_FAILURE_FIRST_ERROR_PRECEDENCE) == GN_STATUS_OK;
    if (strcmp(name, "main_first_precedence") == 0)
        return gn_test_mvs_set_failure(instance,
            GN_TEST_MVS_FAILURE_MAIN_AFTER_INSTRUCTION_THEN_SOUND_TICK_LIMIT) ==
               GN_STATUS_OK;
    if (strcmp(name, "sound_bus_failure") == 0)
        return gn_test_mvs_set_failure(instance, GN_TEST_MVS_FAILURE_SOUND_BUS) ==
               GN_STATUS_OK;
    if (strcmp(name, "unsupported_first_instruction") == 0 ||
        strcmp(name, "main_bus_read_first_instruction") == 0 ||
        strcmp(name, "main_bus_write_after_instruction") == 0)
        return 1;
    return 0;
}

static int run_competing_failure(gn_instance *instance) {
    gn_run_result run;
    if (gn_run_mvs(instance, GN_MAX_CYCLE_BUDGET, &run) !=
            GN_STATUS_CPU_FAILURE || run.reason != GN_RUN_ERROR) {
        puts("{\"status\":\"diagnostic_precedence_failed\"}");
        return 1;
    }
    gn_mvs_failure first;
    gn_mvs_failure after_retry;
    if (gn_private_mvs_failure(instance, &first) != GN_STATUS_OK ||
        first.valid == 0u ||
        gn_run_mvs(instance, GN_MAX_CYCLE_BUDGET, &run) != GN_STATUS_CPU_FAILURE ||
        gn_private_mvs_failure(instance, &after_retry) != GN_STATUS_OK ||
        memcmp(&first, &after_retry, sizeof(first)) != 0) {
        puts("{\"status\":\"diagnostic_precedence_changed\"}");
        return 1;
    }
    const int result = gn_mvs_qualify_execute(instance);
    if (result != 1 ||
        gn_private_mvs_failure(instance, &after_retry) != GN_STATUS_OK ||
        memcmp(&first, &after_retry, sizeof(first)) != 0) {
        puts("{\"status\":\"diagnostic_precedence_changed_after_format\"}");
        return 1;
    }
    return result;
}

int main(int argc, char **argv) {
    if (argc != 3 && argc != 4) return 2;
    if (argc == 4 &&
        strcmp(argv[2], "active_prelude_error") != 0 &&
        strcmp(argv[2], "active_scripted_error") != 0 &&
        strcmp(argv[2], "active_immediate_error") != 0 &&
        strcmp(argv[2], "active_scripted_fault") != 0 &&
        strcmp(argv[2], "active_partial_bus_error") != 0) return 2;
    uint8_t *bytes = NULL;
    size_t size = 0u;
    if (!load_bytes(argv[1], &bytes, &size)) {
        puts("{\"status\":\"diagnostic_driver_input_failed\"}");
        return 2;
    }
    gn_mvs_manifest manifest;
    if (!gn_mvs_qualify_parse_bundle(bytes, size, &manifest)) {
        free(bytes);
        puts("{\"status\":\"diagnostic_driver_input_failed\"}");
        return 2;
    }
    if (strcmp(argv[2], "diagnostic_reset_isolation") == 0) {
        const int passed = run_reset_isolation(&manifest);
        free(bytes);
        return passed ? 0 : 1;
    }
    gn_instance *instance = NULL;
    if (!make_instance(&manifest, &instance)) {
        gn_destroy(instance);
        free(bytes);
        puts("{\"status\":\"diagnostic_driver_load_failed\"}");
        return 2;
    }
    free(bytes);
    if (argc == 4) {
        const int before_active = strcmp(argv[2], "active_prelude_error") == 0;
        const int scripted = strcmp(argv[2], "active_scripted_error") == 0 ||
                             strcmp(argv[2], "active_scripted_fault") == 0;
        const int inject = before_active ||
            strcmp(argv[2], "active_scripted_error") == 0 ||
            strcmp(argv[2], "active_immediate_error") == 0;
        if (inject && gn_test_mvs_set_failure(instance,
                GN_TEST_MVS_FAILURE_MAIN_OBSERVE) != GN_STATUS_OK) {
            gn_destroy(instance);
            return 2;
        }
        const int result = gn_mvs_qualify_test_active(instance,
            before_active ? 0 : (scripted ? 1 : 2), argv[3]);
        gn_destroy(instance);
        return result;
    }
    if (!select_failure(instance, argv[2])) {
        gn_destroy(instance);
        puts("{\"status\":\"diagnostic_driver_case_rejected\"}");
        return 2;
    }
    const int result = strcmp(argv[2], "first_error_precedence") == 0 ||
                       strcmp(argv[2], "main_first_precedence") == 0
        ? run_competing_failure(instance)
        : gn_mvs_qualify_execute(instance);
    gn_destroy(instance);
    return result;
}
