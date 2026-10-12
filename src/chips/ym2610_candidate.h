#ifndef GLUEYNEO_YM2610_CANDIDATE_H
#define GLUEYNEO_YM2610_CANDIDATE_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#if defined(_WIN32)
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
/* Produces at most capacity_frames interleaved L/R/SSG int32 triplets. */
YM2610_CANDIDATE_API ym2610_candidate_status ym2610_candidate_clock(
    ym2610_candidate *candidate, uint32_t input_clocks, int32_t *samples,
    size_t capacity_frames, size_t *produced_frames);
YM2610_CANDIDATE_API ym2610_candidate_status ym2610_candidate_sample_rate(uint32_t input_clock,
                                                      uint32_t *rate);

#ifdef GLUEYNEO_YM2610_TEST_HOOKS
YM2610_CANDIDATE_API ym2610_candidate_status ym2610_candidate_test_probe_read(
    ym2610_candidate *candidate, uint32_t access, uint32_t address);
YM2610_CANDIDATE_API ym2610_candidate_status ym2610_candidate_test_throw(void);
#endif

#ifdef __cplusplus
}
#endif

#endif
