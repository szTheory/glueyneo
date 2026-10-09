#include "ym2610_candidate.h"

#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "unity.h"

enum { TEST_SAMPLES = 256, TEST_MAX_CLOCKS = 4096 };

void setUp(void) {}
void tearDown(void) {}

typedef struct {
    int fail_read;
    int read_calls;
    int irq_calls;
    int irq_level;
    int reenter;
    int nested_status;
    ym2610_candidate *candidate;
} test_callbacks;

static int callback_read(void *userdata, uint32_t access, uint32_t address,
                         uint8_t *value) {
    test_callbacks *state = userdata;
    (void)access;
    (void)address;
    ++state->read_calls;
    if (state->reenter) {
        state->nested_status = ym2610_candidate_reset(state->candidate);
    }
    if (state->fail_read) return 1;
    *value = 0u;
    return 0;
}

static int callback_write(void *userdata, uint32_t access, uint32_t address,
                          uint8_t value) {
    (void)userdata;
    (void)access;
    (void)address;
    (void)value;
    return 0;
}

static void callback_irq(void *userdata, int asserted) {
    test_callbacks *state = userdata;
    ++state->irq_calls;
    state->irq_level = asserted;
}

static const ym2610_candidate_callbacks CALLBACKS = {
    callback_read, callback_write, callback_irq, 0x10000u, 0x10000u, 2u
};

static void write_register(ym2610_candidate *candidate, uint8_t reg,
                           uint8_t value) {
    TEST_ASSERT_EQUAL_INT(YM2610_CANDIDATE_OK,
                          ym2610_candidate_write(candidate, 0u, reg));
    TEST_ASSERT_EQUAL_INT(YM2610_CANDIDATE_OK,
                          ym2610_candidate_write(candidate, 1u, value));
}

static void program_ssg_tone(ym2610_candidate *candidate) {
    write_register(candidate, 0u, 1u);
    write_register(candidate, 1u, 0u);
    write_register(candidate, 7u, 0x3eu);
    write_register(candidate, 8u, 0x0fu);
}

static int run_trace(ym2610_candidate *candidate, uint32_t total_clocks,
                     int32_t *samples, size_t *frame_count) {
    size_t produced = 0u;
    *frame_count = 0u;
    while (total_clocks != 0u) {
        uint32_t clocks = total_clocks > TEST_MAX_CLOCKS
            ? TEST_MAX_CLOCKS : total_clocks;
        size_t capacity = TEST_SAMPLES - *frame_count;
        if (ym2610_candidate_clock(candidate, clocks,
                                   samples + (*frame_count * 3u), capacity,
                                   &produced) != YM2610_CANDIDATE_OK) {
            return 0;
        }
        *frame_count += produced;
        total_clocks -= clocks;
    }
    return 1;
}

static uint64_t sample_fingerprint(const int32_t *samples, size_t sample_count,
                                   size_t *nonzero_count) {
    uint64_t hash = UINT64_C(14695981039346656037);
    *nonzero_count = 0u;
    for (size_t index = 0u; index < sample_count; ++index) {
        uint32_t value = (uint32_t)samples[index];
        if (samples[index] != 0) ++*nonzero_count;
        for (unsigned byte = 0u; byte < 4u; ++byte) {
            hash ^= (uint8_t)(value >> (byte * 8u));
            hash *= UINT64_C(1099511628211);
        }
    }
    return hash;
}

static void identical_clock_and_register_traces_match_non_silent_samples(void) {
    test_callbacks callbacks_a = {0};
    test_callbacks callbacks_b = {0};
    ym2610_candidate *a = NULL;
    ym2610_candidate *b = NULL;
    int32_t samples_a[TEST_SAMPLES * 3] = {0};
    int32_t samples_b[TEST_SAMPLES * 3] = {0};
    size_t frames_a = 0u;
    size_t frames_b = 0u;
    TEST_ASSERT_EQUAL_INT(YM2610_CANDIDATE_OK,
        ym2610_candidate_create(&CALLBACKS, &callbacks_a, &a));
    TEST_ASSERT_EQUAL_INT(YM2610_CANDIDATE_OK,
        ym2610_candidate_create(&CALLBACKS, &callbacks_b, &b));
    program_ssg_tone(a);
    program_ssg_tone(b);
    TEST_ASSERT_TRUE(run_trace(a, 4096u, samples_a, &frames_a));
    TEST_ASSERT_TRUE(run_trace(b, 4096u, samples_b, &frames_b));
    TEST_ASSERT_EQUAL_UINT(frames_a, frames_b);
    TEST_ASSERT_EQUAL_UINT(256u, frames_a);
    TEST_ASSERT_EQUAL_MEMORY(samples_a, samples_b,
                             frames_a * 3u * sizeof(samples_a[0]));
    size_t nonzero = 0u;
    uint64_t fingerprint = sample_fingerprint(samples_a, frames_a * 3u, &nonzero);
    TEST_ASSERT_TRUE_MESSAGE(nonzero != 0u, "programmed YM2610 produced only silence");
    printf("ym2610_sample_frames=%zu nonzero_values=%zu fnv1a64=%016llx\n",
           frames_a, nonzero, (unsigned long long)fingerprint);
    ym2610_candidate_destroy(a);
    ym2610_candidate_destroy(b);
}

static void independent_interleaved_instances_match_isolated_baselines(void) {
    test_callbacks userdata[2] = {{0}, {0}};
    ym2610_candidate *instances[2] = {NULL, NULL};
    int32_t baseline[2][TEST_SAMPLES * 3] = {{0}};
    int32_t interleaved[2][TEST_SAMPLES * 3] = {{0}};
    size_t baseline_frames[2] = {0u, 0u};
    size_t interleaved_frames[2] = {0u, 0u};
    for (size_t owner = 0u; owner < 2u; ++owner) {
        TEST_ASSERT_EQUAL_INT(YM2610_CANDIDATE_OK,
            ym2610_candidate_create(&CALLBACKS, &userdata[owner], &instances[owner]));
        program_ssg_tone(instances[owner]);
        TEST_ASSERT_TRUE(run_trace(instances[owner], 512u, baseline[owner],
                                   &baseline_frames[owner]));
        TEST_ASSERT_EQUAL_INT(YM2610_CANDIDATE_OK,
                              ym2610_candidate_reset(instances[owner]));
        program_ssg_tone(instances[owner]);
    }
    for (uint32_t turn = 0u; turn < 32u; ++turn) {
        for (size_t offset = 0u; offset < 2u; ++offset) {
            size_t owner = (offset + (turn & 1u)) & 1u;
            size_t produced = 0u;
            TEST_ASSERT_EQUAL_INT(YM2610_CANDIDATE_OK,
                ym2610_candidate_clock(instances[owner], 16u,
                    interleaved[owner] + interleaved_frames[owner] * 3u,
                    TEST_SAMPLES - interleaved_frames[owner], &produced));
            interleaved_frames[owner] += produced;
        }
    }
    for (size_t owner = 0u; owner < 2u; ++owner) {
        TEST_ASSERT_EQUAL_UINT(baseline_frames[owner], interleaved_frames[owner]);
        TEST_ASSERT_EQUAL_MEMORY(baseline[owner], interleaved[owner],
            baseline_frames[owner] * 3u * sizeof(baseline[owner][0]));
        ym2610_candidate_destroy(instances[owner]);
    }
}

static void reset_and_chunked_continuation_reproduce_baseline(void) {
    test_callbacks userdata = {0};
    ym2610_candidate *candidate = NULL;
    int32_t whole[TEST_SAMPLES * 3] = {0};
    int32_t chunks[TEST_SAMPLES * 3] = {0};
    int32_t replay[TEST_SAMPLES * 3] = {0};
    size_t whole_frames = 0u, chunks_frames = 0u, replay_frames = 0u;
    TEST_ASSERT_EQUAL_INT(YM2610_CANDIDATE_OK,
        ym2610_candidate_create(&CALLBACKS, &userdata, &candidate));
    program_ssg_tone(candidate);
    TEST_ASSERT_TRUE(run_trace(candidate, 4096u, whole, &whole_frames));
    TEST_ASSERT_EQUAL_INT(YM2610_CANDIDATE_OK,
                          ym2610_candidate_reset(candidate));
    program_ssg_tone(candidate);
    TEST_ASSERT_TRUE(run_trace(candidate, 2048u, chunks, &chunks_frames));
    TEST_ASSERT_TRUE(run_trace(candidate, 2048u,
                               chunks + chunks_frames * 3u, &replay_frames));
    chunks_frames += replay_frames;
    TEST_ASSERT_EQUAL_UINT(whole_frames, chunks_frames);
    TEST_ASSERT_EQUAL_MEMORY(whole, chunks,
                             whole_frames * 3u * sizeof(whole[0]));
    TEST_ASSERT_EQUAL_INT(YM2610_CANDIDATE_OK,
                          ym2610_candidate_reset(candidate));
    program_ssg_tone(candidate);
    TEST_ASSERT_TRUE(run_trace(candidate, 4096u, replay, &replay_frames));
    TEST_ASSERT_EQUAL_UINT(whole_frames, replay_frames);
    TEST_ASSERT_EQUAL_MEMORY(whole, replay,
                             whole_frames * 3u * sizeof(whole[0]));
    ym2610_candidate_destroy(candidate);
}

static void callback_failure_latches_until_reset_and_exceptions_are_contained(void) {
    test_callbacks userdata = {0};
    ym2610_candidate *candidate = NULL;
    int32_t samples[3] = {0};
    size_t produced = 0u;
    TEST_ASSERT_EQUAL_INT(YM2610_CANDIDATE_OK,
        ym2610_candidate_create(&CALLBACKS, &userdata, &candidate));
    userdata.candidate = candidate;
    TEST_ASSERT_EQUAL_INT(YM2610_CANDIDATE_CALLBACK_FAILURE,
        ym2610_candidate_test_probe_read(candidate,
            YM2610_CANDIDATE_ACCESS_ADPCM_A, CALLBACKS.adpcm_a_size));
    TEST_ASSERT_EQUAL_INT(0, userdata.read_calls);
    TEST_ASSERT_EQUAL_INT(YM2610_CANDIDATE_OK,
                          ym2610_candidate_reset(candidate));
    userdata.reenter = 1;
    TEST_ASSERT_EQUAL_INT(YM2610_CANDIDATE_CALLBACK_FAILURE,
        ym2610_candidate_test_probe_read(candidate,
            YM2610_CANDIDATE_ACCESS_ADPCM_A, 0u));
    TEST_ASSERT_EQUAL_INT(YM2610_CANDIDATE_CALLBACK_FAILURE,
                          userdata.nested_status);
    TEST_ASSERT_EQUAL_INT(YM2610_CANDIDATE_OK,
                          ym2610_candidate_reset(candidate));
    userdata.reenter = 0;
    userdata.fail_read = 1;
    TEST_ASSERT_EQUAL_INT(YM2610_CANDIDATE_CALLBACK_FAILURE,
        ym2610_candidate_test_probe_read(candidate,
            YM2610_CANDIDATE_ACCESS_ADPCM_A, 0u));
    TEST_ASSERT_EQUAL_INT(2, userdata.read_calls);
    TEST_ASSERT_EQUAL_INT(YM2610_CANDIDATE_CALLBACK_FAILURE,
        ym2610_candidate_clock(candidate, 16u, samples, 1u, &produced));
    TEST_ASSERT_EQUAL_UINT(0u, produced);
    TEST_ASSERT_EQUAL_INT(YM2610_CANDIDATE_OK,
                          ym2610_candidate_reset(candidate));
    TEST_ASSERT_EQUAL_INT(YM2610_CANDIDATE_EXCEPTION,
        ym2610_candidate_test_throw());
    TEST_ASSERT_EQUAL_INT(YM2610_CANDIDATE_OK,
        ym2610_candidate_clock(candidate, 16u, samples, 1u, &produced));
    TEST_ASSERT_EQUAL_UINT(1u, produced);
    ym2610_candidate_destroy(candidate);
}

static void capacities_and_clock_limits_fail_before_mutation(void) {
    test_callbacks userdata_a = {0}, userdata_b = {0};
    ym2610_candidate *a = NULL, *b = NULL;
    int32_t samples_a[3] = {0}, samples_b[3] = {0};
    size_t produced_a = 0u, produced_b = 0u;
    uint32_t rate = 0u;
    TEST_ASSERT_EQUAL_INT(YM2610_CANDIDATE_OK,
        ym2610_candidate_create(&CALLBACKS, &userdata_a, &a));
    TEST_ASSERT_EQUAL_INT(YM2610_CANDIDATE_OK,
        ym2610_candidate_create(&CALLBACKS, &userdata_b, &b));
    program_ssg_tone(a);
    program_ssg_tone(b);
    TEST_ASSERT_EQUAL_INT(YM2610_CANDIDATE_CAPACITY,
        ym2610_candidate_clock(a, 16u, samples_a, 0u, &produced_a));
    TEST_ASSERT_EQUAL_UINT(0u, produced_a);
    TEST_ASSERT_EQUAL_INT(YM2610_CANDIDATE_OK,
        ym2610_candidate_clock(a, 16u, samples_a, 1u, &produced_a));
    TEST_ASSERT_EQUAL_INT(YM2610_CANDIDATE_OK,
        ym2610_candidate_clock(b, 16u, samples_b, 1u, &produced_b));
    TEST_ASSERT_EQUAL_MEMORY(samples_a, samples_b, sizeof(samples_a));
    TEST_ASSERT_EQUAL_UINT(1u, produced_a);
    TEST_ASSERT_EQUAL_INT(YM2610_CANDIDATE_LIMIT,
        ym2610_candidate_clock(a, 1000001u, samples_a, 1u, &produced_a));
    TEST_ASSERT_EQUAL_INT(YM2610_CANDIDATE_INVALID_ARGUMENT,
        ym2610_candidate_sample_rate(0u, &rate));
    TEST_ASSERT_EQUAL_INT(YM2610_CANDIDATE_OK,
        ym2610_candidate_sample_rate(8000000u, &rate));
    TEST_ASSERT_EQUAL_UINT(500000u, rate);
    ym2610_candidate_destroy(a);
    ym2610_candidate_destroy(b);
}

static int run_red_create(void) {
    test_callbacks userdata = {0};
    ym2610_candidate *candidate = NULL;
    int result = ym2610_candidate_create(&CALLBACKS, &userdata, &candidate);
    int passed = result == YM2610_CANDIDATE_OK && candidate != NULL;
    printf("TAP version 13\n%s 1 - create returns an independent YM2610 instance\n",
           passed ? "ok" : "not ok");
    if (!passed) printf("# expected status 0 and non-null instance; got status %d\n", result);
    if (candidate != NULL) ym2610_candidate_destroy(candidate);
    puts("1..1");
    return passed ? 0 : 1;
}

int main(int argc, char **argv) {
    if (argc == 2 && strcmp(argv[1], "--tdd-create") == 0) return run_red_create();
    if (argc != 1) return 2;
    UNITY_BEGIN();
    RUN_TEST(identical_clock_and_register_traces_match_non_silent_samples);
    RUN_TEST(independent_interleaved_instances_match_isolated_baselines);
    RUN_TEST(reset_and_chunked_continuation_reproduce_baseline);
    RUN_TEST(callback_failure_latches_until_reset_and_exceptions_are_contained);
    RUN_TEST(capacities_and_clock_limits_fail_before_mutation);
    return UNITY_END();
}
