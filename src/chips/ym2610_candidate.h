#ifndef GLUEYNEO_YM2610_CANDIDATE_H
#define GLUEYNEO_YM2610_CANDIDATE_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#if defined(GLUEYNEO_YM2610_CANDIDATE_INTERNAL)
#if defined(__GNUC__)
#define YM2610_CANDIDATE_API __attribute__((visibility("hidden")))
#else
#define YM2610_CANDIDATE_API
#endif
#elif defined(_WIN32)
#if defined(GLUEYNEO_YM2610_CANDIDATE_BUILD)
#define YM2610_CANDIDATE_API __declspec(dllexport)
#elif defined(GLUEYNEO_YM2610_CANDIDATE_SHARED)
#define YM2610_CANDIDATE_API __declspec(dllimport)
#else
#define YM2610_CANDIDATE_API
#endif
#elif defined(__GNUC__)
#define YM2610_CANDIDATE_API __attribute__((visibility("default")))
#else
#define YM2610_CANDIDATE_API
#endif

typedef struct ym2610_candidate ym2610_candidate;

typedef enum ym2610_candidate_status {
    YM2610_CANDIDATE_OK = 0,
    YM2610_CANDIDATE_INVALID_ARGUMENT = 1,
    YM2610_CANDIDATE_NO_MEMORY = 2,
    YM2610_CANDIDATE_CALLBACK_FAILURE = 3,
    YM2610_CANDIDATE_EXCEPTION = 4,
    YM2610_CANDIDATE_CAPACITY = 5,
    YM2610_CANDIDATE_LIMIT = 6
} ym2610_candidate_status;

typedef enum ym2610_candidate_access {
    YM2610_CANDIDATE_ACCESS_ADPCM_A = 1,
    YM2610_CANDIDATE_ACCESS_ADPCM_B = 2,
    YM2610_CANDIDATE_ACCESS_IO = 3
} ym2610_candidate_access;

#if defined(GLUEYNEO_YM2610_CANDIDATE_INTERNAL) || \
    defined(GLUEYNEO_YM2610_TEST_HOOKS) || \
    defined(GLUEYNEO_SDK_TEST_HOOKS)
#define YM2610_CANDIDATE_DIAGNOSTIC_EVENT_CAPACITY 32u

typedef enum ym2610_candidate_family {
    YM2610_CANDIDATE_FAMILY_SSG = 1,
    YM2610_CANDIDATE_FAMILY_FM = 2,
    YM2610_CANDIDATE_FAMILY_ADPCM_A = 3,
    YM2610_CANDIDATE_FAMILY_ADPCM_B = 4,
    YM2610_CANDIDATE_FAMILY_CONTROL = 5
} ym2610_candidate_family;

typedef struct ym2610_candidate_register_event {
    uint64_t clock;
    uint8_t port;
    uint8_t bank;
    uint8_t reg;
    uint8_t value;
    uint8_t family;
} ym2610_candidate_register_event;

/* Private, bounded diagnostics. Clearing this record never resets chip state. */
typedef struct ym2610_candidate_observation {
    uint32_t version;
    uint32_t event_count;
    uint32_t event_dropped;
    uint64_t clocks;
    uint64_t register_writes;
    uint64_t ssg_register_writes;
    uint64_t ssg_volume_writes;
    uint64_t control_register_writes;
    uint64_t fm_register_writes;
    uint64_t fm_key_on_writes;
    uint64_t fm_key_off_writes;
    uint64_t fm_frequency_writes;
    uint64_t fm_level_writes;
    uint64_t fm_pan_writes;
    uint64_t adpcm_a_register_writes;
    uint64_t adpcm_a_control_writes;
    uint64_t adpcm_b_register_writes;
    uint64_t adpcm_b_control_writes;
    uint64_t adpcm_a_sample_reads;
    uint64_t adpcm_b_sample_reads;
    uint64_t timer_programs;
    uint64_t timer_expirations;
    uint64_t irq_assertions;
    uint64_t irq_deassertions;
    uint64_t native_frames;
    uint64_t native_nonzero_frames;
    uint64_t native_stereo_nonzero_frames;
    uint64_t native_ssg_nonzero_frames;
    uint32_t native_peak;
    ym2610_candidate_register_event events[
        YM2610_CANDIDATE_DIAGNOSTIC_EVENT_CAPACITY];
} ym2610_candidate_observation;

YM2610_CANDIDATE_API ym2610_candidate_status
ym2610_candidate_diagnostics_clear(ym2610_candidate *candidate);
YM2610_CANDIDATE_API ym2610_candidate_status ym2610_candidate_observe(
    const ym2610_candidate *candidate, ym2610_candidate_observation *out);
#endif

typedef int (*ym2610_candidate_read_fn)(void *userdata, uint32_t access,
                                        uint32_t address, uint8_t *value);
typedef int (*ym2610_candidate_write_fn)(void *userdata, uint32_t access,
                                          uint32_t address, uint8_t value);
typedef void (*ym2610_candidate_irq_fn)(void *userdata, int asserted);

typedef struct ym2610_candidate_callbacks {
    ym2610_candidate_read_fn read;
    ym2610_candidate_write_fn write;
    ym2610_candidate_irq_fn irq;
    uint32_t adpcm_a_size;
    uint32_t adpcm_b_size;
    uint32_t io_size;
} ym2610_candidate_callbacks;

/* The callback table is copied; userdata must outlive the candidate instance. */
YM2610_CANDIDATE_API ym2610_candidate_status ym2610_candidate_create(
    const ym2610_candidate_callbacks *callbacks, void *userdata,
    ym2610_candidate **out_candidate);
YM2610_CANDIDATE_API void ym2610_candidate_destroy(ym2610_candidate *candidate);
YM2610_CANDIDATE_API ym2610_candidate_status ym2610_candidate_reset(ym2610_candidate *candidate);
YM2610_CANDIDATE_API ym2610_candidate_status ym2610_candidate_write(ym2610_candidate *candidate,
                                                uint32_t port, uint8_t value);
YM2610_CANDIDATE_API ym2610_candidate_status ym2610_candidate_read(ym2610_candidate *candidate,
                                               uint32_t port, uint8_t *value);
/* Produces at most capacity_frames interleaved L/R/SSG int32 triplets. */
YM2610_CANDIDATE_API ym2610_candidate_status ym2610_candidate_clock(
    ym2610_candidate *candidate, uint32_t input_clocks, int32_t *samples,
    size_t capacity_frames, size_t *produced_frames);
YM2610_CANDIDATE_API ym2610_candidate_status ym2610_candidate_sample_rate(uint32_t input_clock,
                                                      uint32_t *rate);

#if defined(GLUEYNEO_YM2610_CANDIDATE_INTERNAL) || \
    defined(GLUEYNEO_YM2610_TEST_HOOKS) || \
    defined(GLUEYNEO_SDK_TEST_HOOKS)
typedef enum ym2610_candidate_state_reason {
    YM2610_CANDIDATE_STATE_REASON_NONE = 0,
    YM2610_CANDIDATE_STATE_REASON_ARGUMENT = 1,
    YM2610_CANDIDATE_STATE_REASON_TRUNCATED = 2,
    YM2610_CANDIDATE_STATE_REASON_TRAILING = 3,
    YM2610_CANDIDATE_STATE_REASON_MAGIC = 4,
    YM2610_CANDIDATE_STATE_REASON_VERSION = 5,
    YM2610_CANDIDATE_STATE_REASON_BOOLEAN = 6,
    YM2610_CANDIDATE_STATE_REASON_ENUM = 7,
    YM2610_CANDIDATE_STATE_REASON_RANGE = 8,
    YM2610_CANDIDATE_STATE_REASON_INVARIANT = 9
} ym2610_candidate_state_reason;

typedef struct ym2610_candidate_state_detail {
    ym2610_candidate_state_reason reason;
    size_t offset;
    size_t consumed;
} ym2610_candidate_state_detail;

/* Private native-state seams. A staged candidate owns only private chip state
 * and callback bindings; rebind supplies destination-owned callbacks before
 * the caller replaces its live candidate pointer. */
YM2610_CANDIDATE_API ym2610_candidate_status
ym2610_candidate_state_size(const ym2610_candidate *candidate, size_t *size);
YM2610_CANDIDATE_API ym2610_candidate_status
ym2610_candidate_state_capture(const ym2610_candidate *candidate,
                               uint8_t *destination, size_t capacity,
                               size_t *written);
YM2610_CANDIDATE_API ym2610_candidate_status
ym2610_candidate_state_validate(const uint8_t *bytes, size_t length,
                                ym2610_candidate_state_detail *detail);
YM2610_CANDIDATE_API ym2610_candidate_status
ym2610_candidate_state_stage(const uint8_t *bytes, size_t length,
                             ym2610_candidate **staged,
                             ym2610_candidate_state_detail *detail);
YM2610_CANDIDATE_API ym2610_candidate_status
ym2610_candidate_state_irq_line(const ym2610_candidate *candidate,
                                uint8_t *out_asserted);
YM2610_CANDIDATE_API ym2610_candidate_status
ym2610_candidate_state_timer_bound(uint32_t timer, uint64_t *out_bound);
YM2610_CANDIDATE_API ym2610_candidate_status
ym2610_candidate_state_busy_bound(uint64_t *out_bound);
YM2610_CANDIDATE_API ym2610_candidate_status
ym2610_candidate_state_rebind(ym2610_candidate *staged,
                              const ym2610_candidate_callbacks *callbacks,
                              void *userdata);
#endif

#if defined(GLUEYNEO_YM2610_TEST_HOOKS) || defined(GLUEYNEO_SDK_TEST_HOOKS)
typedef int (*ym2610_candidate_test_operation)(void *userdata);
YM2610_CANDIDATE_API void
ym2610_candidate_test_bypass_next_state_validation(void);
YM2610_CANDIDATE_API void
ym2610_candidate_test_bypass_next_state_relation(void);
YM2610_CANDIDATE_API ym2610_candidate_status ym2610_candidate_test_create_oom(void);
YM2610_CANDIDATE_API ym2610_candidate_status ym2610_candidate_test_probe_read(
    ym2610_candidate *candidate, uint32_t access, uint32_t address);
YM2610_CANDIDATE_API ym2610_candidate_status ym2610_candidate_test_throw(void);
YM2610_CANDIDATE_API ym2610_candidate_status
ym2610_candidate_test_state_create_failpoint(size_t fail_at,
                                              size_t *allocation_points,
                                              int64_t *lifetime_balance);
YM2610_CANDIDATE_API ym2610_candidate_status
ym2610_candidate_test_state_stage_failpoint(const uint8_t *bytes, size_t length,
                                             size_t fail_at,
                                             size_t *allocation_points,
                                             int64_t *lifetime_balance);
YM2610_CANDIDATE_API ym2610_candidate_status
ym2610_candidate_test_state_capture_failpoint(
    const ym2610_candidate *candidate, uint8_t *destination, size_t capacity,
    size_t *written, size_t fail_at, size_t *allocation_points,
    int64_t *lifetime_balance);
YM2610_CANDIDATE_API ym2610_candidate_status
ym2610_candidate_test_state_rebind_failpoint(
    ym2610_candidate *staged, const ym2610_candidate_callbacks *callbacks,
    void *userdata, size_t fail_at, size_t *allocation_points,
    int64_t *lifetime_balance);
YM2610_CANDIDATE_API ym2610_candidate_status
ym2610_candidate_test_invoke_with_failpoint(
    ym2610_candidate_test_operation operation, void *userdata,
    size_t fail_at, int *operation_result, size_t *allocation_points,
    int64_t *lifetime_balance, size_t *requested_bytes,
    size_t *high_water_bytes, uint32_t *failed_site);
#endif

/* Fixed import graph; excludes allocator metadata and compiler stack frames. */
YM2610_CANDIDATE_API size_t ym2610_candidate_state_heap_bound(void);
YM2610_CANDIDATE_API size_t ym2610_candidate_state_stack_bound(void);
YM2610_CANDIDATE_API size_t ym2610_candidate_state_allocation_bound(void);

#ifdef __cplusplus
}
#endif

#endif
