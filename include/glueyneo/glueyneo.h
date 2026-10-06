/* SPDX-License-Identifier: MIT */
#ifndef GLUEYNEO_GLUEYNEO_H
#define GLUEYNEO_GLUEYNEO_H

#include <stddef.h>
#include <stdint.h>

#if defined(_WIN32) && defined(GLUEYNEO_SHARED)
#  if defined(GLUEYNEO_BUILDING)
#    define GN_API __declspec(dllexport)
#  else
#    define GN_API __declspec(dllimport)
#  endif
#elif defined(__GNUC__) || defined(__clang__)
#  define GN_API __attribute__((visibility("default")))
#else
#  define GN_API
#endif

#ifdef __cplusplus
extern "C" {
#endif

#define GN_MANIFEST_VERSION UINT32_C(1)
#define GN_PROFILE_DIAGNOSTIC UINT32_C(1)
#define GN_MAX_REGIONS 2u
#define GN_MAX_MEDIA_BYTES ((size_t)1024u * (size_t)1024u)
#define GN_MAX_CYCLE_BUDGET UINT64_C(1000000)

typedef struct gn_instance gn_instance;

typedef enum {
    GN_STATUS_OK = 0,
    GN_STATUS_INVALID_ARGUMENT,
    GN_STATUS_INVALID_STATE,
    GN_STATUS_INVALID_MEDIA,
    GN_STATUS_UNSUPPORTED_PROFILE,
    GN_STATUS_OUT_OF_MEMORY,
    GN_STATUS_CPU_FAILURE
} gn_status;

typedef enum {
    GN_REGION_ROM = 1,
    GN_REGION_RAM = 2
} gn_region_kind;

typedef struct {
    uint32_t guest_base;
    uint32_t mapped_size;
    const uint8_t *source;
    size_t source_size;
    gn_region_kind kind;
} gn_region;

typedef struct {
    uint32_t version;
    uint32_t profile;
    size_t region_count;
    gn_region regions[GN_MAX_REGIONS];
} gn_manifest;

typedef enum {
    GN_RUN_BUDGET = 0,
    GN_RUN_STOPPED,
    GN_RUN_FAULT,
    GN_RUN_ERROR
} gn_run_reason;

typedef struct {
    uint64_t requested_cycles;
    uint64_t elapsed_cycles;
    uint64_t overshoot_cycles;
    uint64_t instructions;
    gn_run_reason reason;
    uint32_t boundary_pc;
    uint32_t fault_pc;
    uint16_t instruction_register;
} gn_run_result;

typedef struct {
    uint32_t arithmetic_result;
    uint32_t initialized_result;
    uint32_t bss_result;
    uint8_t ready;
} gn_observations;

/* All pointers in a manifest must reference readable caller storage for the
 * duration of gn_load. Successful loads copy every source byte. One instance
 * is single-threaded and non-reentrant; distinct instances may run in parallel.
 * The supported diagnostic maps 512-byte ROM at 0 and 4096-byte RAM at 0x1000.
 * RAM source bytes are an initialization prefix; the remainder is zero-filled. */
GN_API gn_status gn_create(gn_instance **out_instance);
GN_API gn_status gn_load(gn_instance *instance, const gn_manifest *manifest);
GN_API gn_status gn_reset(gn_instance *instance);
GN_API gn_status gn_run(gn_instance *instance, uint64_t cycle_budget,
                        gn_run_result *out_result);
GN_API gn_status gn_observe(const gn_instance *instance,
                            gn_observations *out_observations);
GN_API gn_status gn_unload(gn_instance *instance);
GN_API void gn_destroy(gn_instance *instance);
GN_API const char *gn_status_string(gn_status status);

#ifdef __cplusplus
}
#endif

#endif
