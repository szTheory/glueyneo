/* SPDX-License-Identifier: MIT */
#ifndef GLUEYNEO_SDK_TEST_SUPPORT_H
#define GLUEYNEO_SDK_TEST_SUPPORT_H

#include "unity.h"

#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>

static uint64_t sdk_assertions;
static uint64_t sdk_cases;

#define SDK_CHECK_STATUS(id, expected, actual)                                      \
    do {                                                                            \
        const int sdk_expected_value = (int)(expected);                             \
        const int sdk_actual_value = (int)(actual);                                 \
        ++sdk_assertions;                                                           \
        (void)printf("# ASSERT %s expected=%d observed=%d\n", (id),               \
                     sdk_expected_value, sdk_actual_value);                         \
        TEST_ASSERT_EQUAL_INT_MESSAGE(sdk_expected_value, sdk_actual_value, (id));  \
    } while (0)

#define SDK_CHECK_U64(id, expected, actual)                                         \
    do {                                                                            \
        const uint64_t sdk_expected_value = (uint64_t)(expected);                   \
        const uint64_t sdk_actual_value = (uint64_t)(actual);                       \
        ++sdk_assertions;                                                           \
        (void)printf("# ASSERT %s expected=%" PRIu64 " observed=%" PRIu64 "\n", \
                     (id), sdk_expected_value, sdk_actual_value);                   \
        TEST_ASSERT_EQUAL_UINT64_MESSAGE(sdk_expected_value, sdk_actual_value, (id));\
    } while (0)

#define SDK_CHECK_TRUE(id, expression)                                              \
    do {                                                                            \
        const int sdk_observed_value = (expression) ? 1 : 0;                        \
        ++sdk_assertions;                                                           \
        (void)printf("# ASSERT %s expected=1 observed=%d\n", (id),                \
                     sdk_observed_value);                                           \
        TEST_ASSERT_TRUE_MESSAGE(sdk_observed_value != 0, (id));                    \
    } while (0)

#define SDK_CASE(id)                       \
    do {                                   \
        ++sdk_cases;                        \
        (void)printf("# CASE %s\n", (id)); \
    } while (0)

static void sdk_test_result(const char *suite, int failures,
                            const char *source_revision,
                            const char *configuration,
                            const char *compiler_id,
                            const char *compiler_version) {
    (void)printf(
        "SDK_RESULT {\"schema_version\":1,\"suite\":\"%s\","
        "\"outcome\":\"%s\",\"outcomes\":[\"pass\",\"fail\","
        "\"skipped\",\"unsupported\",\"unknown\"],\"cases\":%" PRIu64
        ",\"assertions\":%" PRIu64 ",\"identity\":{\"source_revision\":\"%s\","
        "\"configuration\":\"%s\",\"compiler\":\"%s %s\"}}\n",
        suite, failures == 0 ? "pass" : "fail", sdk_cases, sdk_assertions,
        source_revision, configuration, compiler_id, compiler_version);
}

#endif
