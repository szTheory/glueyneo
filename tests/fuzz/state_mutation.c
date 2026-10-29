/* SPDX-License-Identifier: MIT */
#include "state_fixture.h"
#include "chips/ym2610_candidate.h"
#include "chips/z80_candidate.h"

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

enum {
    STATE_HEADER_BYTES = 72,
    STATE_SECTION_HEADER_BYTES = 8,
    STATE_YM_SECTION = 5
};

void state_mutation_case_counts(uint64_t *out_cases,
                                uint64_t *out_assertions) {
    if (out_cases != NULL) *out_cases = sdk_cases;
    if (out_assertions != NULL) *out_assertions = sdk_assertions;
}

typedef enum {
    MUTATION_EMPTY,
    MUTATION_TRUNCATE,
    MUTATION_EXTEND,
    MUTATION_OVERSIZE_LENGTH,
    MUTATION_SET_BYTE,
    MUTATION_XOR_BYTE,
    MUTATION_SET_U16,
    MUTATION_SET_U32,
    MUTATION_UNKNOWN_SECTION,
    MUTATION_DUPLICATE_SECTION,
    MUTATION_SECTION_LENGTH,
    MUTATION_SECTION_LENGTH_MAX,
    MUTATION_YM_WRAPPER_FORGE
} mutation_kind;

typedef enum {
    YM_WRAPPER_RUNNING_WITHOUT_ACTIVE,
    YM_WRAPPER_ACTIVE_WITHOUT_RUNNING,
    YM_WRAPPER_TIMER_DUE_BEYOND_BOUND,
    YM_WRAPPER_BUSY_END_BEYOND_WINDOW
} ym_wrapper_forge_kind;

typedef enum {
    OFFSET_ABSOLUTE,
    OFFSET_SECTION_START,
    OFFSET_SECTION_START_DELTA,
    OFFSET_INPUT_LENGTH,
    OFFSET_INPUT_CAPACITY,
    OFFSET_NESTED_DETAIL
} mutation_offset_kind;

typedef struct {
    const char *id;
    mutation_kind kind;
    uint32_t section;
    size_t offset;
    uint32_t value;
    gn_state_reason reason;
    uint32_t error_section;
    gn_status status;
    mutation_offset_kind offset_kind;
    size_t offset_delta;
    ym2610_candidate_state_reason ym_reason;
} mutation_recipe;

#define RECIPE(_id, _kind, _section, _offset, _value, _reason, _error_section, \
               _status, _offset_kind, _delta) \
    {_id, _kind, _section, _offset, _value, _reason, _error_section, _status, \
     _offset_kind, _delta, YM2610_CANDIDATE_STATE_REASON_NONE}

static const mutation_recipe mutation_recipes[] = {
    RECIPE("state.outer.empty", MUTATION_EMPTY, 0u, 0u, 0u,
        GN_STATE_REASON_TRUNCATED, 0u, GN_STATUS_INVALID_ARGUMENT,
        OFFSET_INPUT_LENGTH, 0u),
    RECIPE("state.outer.truncated", MUTATION_TRUNCATE, 0u, 0u, 0u,
        GN_STATE_REASON_TRUNCATED, 0u, GN_STATUS_INVALID_ARGUMENT,
        OFFSET_INPUT_LENGTH, 0u),
    RECIPE("state.outer.extended", MUTATION_EXTEND, 0u, 0u, 0u,
        GN_STATE_REASON_TRAILING_BYTES, 0u, GN_STATUS_INVALID_ARGUMENT,
        OFFSET_INPUT_CAPACITY, 0u),
    RECIPE("state.outer.overflow-length", MUTATION_OVERSIZE_LENGTH, 0u, 0u, 0u,
        GN_STATE_REASON_INVALID_ARGUMENT, 0u, GN_STATUS_INVALID_ARGUMENT,
        OFFSET_ABSOLUTE, 0u),
    RECIPE("state.header.format", MUTATION_SET_U32, 0u, 16u, 0u,
        GN_STATE_REASON_FORMAT, 0u, GN_STATUS_INVALID_ARGUMENT,
        OFFSET_ABSOLUTE, 4u),
    RECIPE("state.header.replay", MUTATION_SET_U32, 0u, 20u, 0u,
        GN_STATE_REASON_REPLAY_IDENTITY, 0u, GN_STATUS_UNSUPPORTED_PROFILE,
        OFFSET_ABSOLUTE, 20u),
    RECIPE("state.header.profile", MUTATION_SET_U32, 0u, 24u, 0u,
        GN_STATE_REASON_PROFILE_IDENTITY, 0u, GN_STATUS_UNSUPPORTED_PROFILE,
        OFFSET_ABSOLUTE, 24u),
    RECIPE("state.header.configuration", MUTATION_SET_U32, 0u, 28u, 0u,
        GN_STATE_REASON_CONFIGURATION_IDENTITY, 0u,
        GN_STATUS_UNSUPPORTED_PROFILE, OFFSET_ABSOLUTE, 28u),
    RECIPE("state.header.media-identity", MUTATION_XOR_BYTE, 0u, 32u, 1u,
        GN_STATE_REASON_MEDIA_IDENTITY, 0u, GN_STATUS_INVALID_MEDIA,
        OFFSET_ABSOLUTE, 32u),
    RECIPE("state.header.section-count", MUTATION_SET_U32, 0u, 64u, 4u,
        GN_STATE_REASON_SECTION, 0u, GN_STATUS_INVALID_MEDIA,
        OFFSET_ABSOLUTE, 64u),
    RECIPE("state.header.reserved", MUTATION_SET_U32, 0u, 68u, 1u,
        GN_STATE_REASON_RESERVED, 0u, GN_STATUS_INVALID_MEDIA,
        OFFSET_ABSOLUTE, 68u),
    RECIPE("state.section.unknown", MUTATION_UNKNOWN_SECTION, 0u, 4u, 99u,
        GN_STATE_REASON_SECTION, 5u, GN_STATUS_INVALID_MEDIA,
        OFFSET_ABSOLUTE, 0u),
    RECIPE("state.section.duplicate", MUTATION_DUPLICATE_SECTION, 0u, 1u, 1u,
        GN_STATE_REASON_SECTION, 2u, GN_STATUS_INVALID_MEDIA,
        OFFSET_ABSOLUTE, 0u),
    RECIPE("state.section.length", MUTATION_SECTION_LENGTH, 0u, 0u, 0u,
        GN_STATE_REASON_SECTION, 1u, GN_STATUS_INVALID_MEDIA,
        OFFSET_ABSOLUTE, 0u),
    RECIPE("state.section.length-overflow", MUTATION_SECTION_LENGTH_MAX,
        0u, 0u, 0u, GN_STATE_REASON_SECTION, 1u, GN_STATUS_INVALID_MEDIA,
        OFFSET_ABSOLUTE, 0u),
    RECIPE("state.board.program-bank", MUTATION_SET_BYTE, 3u, 10u, 4u,
        GN_STATE_REASON_RESERVED, 3u, GN_STATUS_INVALID_MEDIA,
        OFFSET_SECTION_START, 0u),
    RECIPE("state.board.video-index", MUTATION_SET_U16, 3u, 23u, 0xffffu,
        GN_STATE_REASON_RESERVED, 3u, GN_STATUS_INVALID_MEDIA,
        OFFSET_SECTION_START, 0u),
    RECIPE("state.board.boolean", MUTATION_SET_BYTE, 3u, 30u, 2u,
        GN_STATE_REASON_RESERVED, 3u, GN_STATUS_INVALID_MEDIA,
        OFFSET_SECTION_START, 0u),
    RECIPE("state.board.display-control", MUTATION_SET_BYTE, 3u, 33u, 1u,
        GN_STATE_REASON_RESERVED, 3u, GN_STATUS_INVALID_MEDIA,
        OFFSET_SECTION_START, 0u),
    RECIPE("state.sound.boolean", MUTATION_SET_BYTE, 4u, 76u, 2u,
        GN_STATE_REASON_RESERVED, 4u, GN_STATUS_INVALID_MEDIA,
        OFFSET_SECTION_START_DELTA, 76u),
    RECIPE("state.sound.clock-remainder", MUTATION_SET_BYTE, 4u, 82u, 3u,
        GN_STATE_REASON_RESERVED, 4u, GN_STATUS_INVALID_MEDIA,
        OFFSET_SECTION_START_DELTA, 76u),
    RECIPE("state.sound.filter-index", MUTATION_SET_U32, 4u, 2775u, 80u,
        GN_STATE_REASON_RESERVED, 4u, GN_STATUS_INVALID_MEDIA,
        OFFSET_SECTION_START_DELTA, 76u),
    RECIPE("state.sound.filter-phase", MUTATION_SET_U16, 4u, 2779u, 125u,
        GN_STATE_REASON_RESERVED, 4u, GN_STATUS_INVALID_MEDIA,
        OFFSET_SECTION_START_DELTA, 76u),
    RECIPE("state.sound.ym-irq-mismatch", MUTATION_XOR_BYTE, 4u, 77u, 1u,
        GN_STATE_REASON_CPU_STATE, 4u, GN_STATUS_INVALID_MEDIA,
        OFFSET_SECTION_START_DELTA, 77u),
    RECIPE("state.z80.magic", MUTATION_XOR_BYTE, 4u, 0u, 1u,
        GN_STATE_REASON_CPU_STATE, 4u, GN_STATUS_INVALID_MEDIA,
        OFFSET_SECTION_START, 0u),
    RECIPE("state.z80.interrupt-mode", MUTATION_SET_BYTE, 4u, 57u, 3u,
        GN_STATE_REASON_CPU_STATE, 4u, GN_STATUS_INVALID_MEDIA,
        OFFSET_SECTION_START, 0u),
    RECIPE("state.z80.boolean", MUTATION_SET_BYTE, 4u, 58u, 2u,
        GN_STATE_REASON_CPU_STATE, 4u, GN_STATUS_INVALID_MEDIA,
        OFFSET_SECTION_START, 0u),
    RECIPE("state.z80.decoder-step", MUTATION_SET_U16, 4u, 5u, 0xffffu,
        GN_STATE_REASON_CPU_STATE, 4u, GN_STATUS_INVALID_MEDIA,
        OFFSET_SECTION_START, 0u),
    {"state.ym.invalid-magic", MUTATION_XOR_BYTE, 5u, 0u, 1u,
     GN_STATE_REASON_CPU_STATE, 5u, GN_STATUS_INVALID_MEDIA,
     OFFSET_NESTED_DETAIL, 0u, YM2610_CANDIDATE_STATE_REASON_MAGIC},
    {"state.ym.timer-boolean", MUTATION_SET_BYTE, 5u, 40u, 2u,
     GN_STATE_REASON_CPU_STATE, 5u, GN_STATUS_INVALID_MEDIA,
     OFFSET_NESTED_DETAIL, 0u, YM2610_CANDIDATE_STATE_REASON_BOOLEAN},
    {"state.ym.clock-range", MUTATION_XOR_BYTE, 5u, 8u, 0x80u,
     GN_STATE_REASON_CPU_STATE, 5u, GN_STATUS_INVALID_MEDIA,
     OFFSET_NESTED_DETAIL, 0u, YM2610_CANDIDATE_STATE_REASON_RANGE},
    /* Held SSG resampler lane 0; INT32_MAX overflowed the signed resampler
     * sums on continuation before the amplitude-table bound was checked. */
    {"state.ym.ssg-held-range", MUTATION_SET_U32, 5u, 921u, 0x7fffffffu,
     GN_STATE_REASON_CPU_STATE, 5u, GN_STATUS_INVALID_MEDIA,
     OFFSET_NESTED_DETAIL, 0u, YM2610_CANDIDATE_STATE_REASON_RANGE}
};

static int find_section(uint8_t *state, size_t size, uint32_t wanted,
                        size_t *out_offset, size_t *out_length);
static uint64_t read_u64be(const uint8_t *bytes);
static void write_u64be(uint8_t *bytes, uint64_t value);

void state_mutation_corpus_coverage_test(void) {
    SDK_CASE("sdk.state.hostile.corpus-coverage");
    const size_t recipes = sizeof(mutation_recipes) / sizeof(mutation_recipes[0]);
    SDK_CHECK_TRUE("sdk.state.hostile.corpus-has-all-recipe-classes",
                   recipes >= 20u);
}

typedef enum {
    STATE_VALIDATOR_Z80,
    STATE_VALIDATOR_YM,
    STATE_VALIDATOR_YM_IRQ_RELATION,
    STATE_VALIDATOR_YM_TIMER_RELATION,
    STATE_VALIDATOR_YM_BUSY_RELATION
} state_validator_selector;

static const char *state_validator_name(state_validator_selector validator) {
    switch (validator) {
    case STATE_VALIDATOR_Z80: return "z80";
    case STATE_VALIDATOR_YM: return "ym";
    case STATE_VALIDATOR_YM_IRQ_RELATION: return "ym-irq-relation";
    case STATE_VALIDATOR_YM_TIMER_RELATION: return "ym-timer-relation";
    case STATE_VALIDATOR_YM_BUSY_RELATION: return "ym-busy-relation";
    }
    return "unknown";
}

static void state_mutation_nested_validator_disabled_test(
    state_validator_selector validator) {
    const char *name = state_validator_name(validator);
    SDK_CASE(validator == STATE_VALIDATOR_Z80
        ? "sdk.state.hostile.negative-control-disable-z80-validator"
        : validator == STATE_VALIDATOR_YM
            ? "sdk.state.hostile.negative-control-disable-ym-validator"
            : validator == STATE_VALIDATOR_YM_IRQ_RELATION
                ? "sdk.state.hostile.negative-control-disable-ym-irq-relation"
                : validator == STATE_VALIDATOR_YM_TIMER_RELATION
                    ? "sdk.state.hostile.negative-control-disable-ym-timer-relation"
                    : "sdk.state.hostile.negative-control-disable-ym-busy-relation");
    gn_instance *target = NULL;
    uint8_t *state = NULL;
    uint8_t *working = NULL;
    uint8_t *after_precheck = NULL;
    size_t state_size = 0u;
    size_t section_offset = 0u;
    size_t section_length = 0u;
    gn_state_detail_v1 detail;
    gn_status imported = GN_STATUS_INVALID_STATE;
    const unsigned fixture_variant =
        validator == STATE_VALIDATOR_YM_TIMER_RELATION ||
        validator == STATE_VALIDATOR_YM_BUSY_RELATION
            ? STATE_FIXTURE_VARIANT_ACTIVE_TIMER : 0u;
    SDK_CHECK_TRUE("sdk.state.hostile.negative-control-target-load",
                   state_fixture_load(&target, fixture_variant));
    if (target == NULL) goto cleanup;
    if (fixture_variant == STATE_FIXTURE_VARIANT_ACTIVE_TIMER) {
        state_fixture_observation observation;
        SDK_CHECK_TRUE("sdk.state.hostile.negative-control-timer-setup",
                       state_fixture_advance(target, 0u, &observation));
    }
    SDK_CHECK_TRUE("sdk.state.hostile.negative-control-capture",
                   state_fixture_capture(target, &state, &state_size));
    if (state == NULL) goto cleanup;
    working = (uint8_t *)malloc(state_size);
    SDK_CHECK_TRUE("sdk.state.hostile.negative-control-storage",
                   working != NULL);
    if (working == NULL) goto cleanup;
    memcpy(working, state, state_size);
    const uint32_t section_id =
        validator == STATE_VALIDATOR_Z80 ||
        validator == STATE_VALIDATOR_YM_IRQ_RELATION ? 4u : STATE_YM_SECTION;
    SDK_CHECK_TRUE("sdk.state.hostile.negative-control-find-section",
        find_section(working, state_size, section_id,
                     &section_offset, &section_length));

    if (validator == STATE_VALIDATOR_YM) {
        working[section_offset] ^= 1u;
        ym2610_candidate_state_detail ym_detail;
        SDK_CHECK_STATUS("sdk.state.hostile.negative-control-ym-validator-is-active",
            YM2610_CANDIDATE_INVALID_ARGUMENT,
            ym2610_candidate_state_validate(working + section_offset,
                                             section_length, &ym_detail));
        SDK_CHECK_U64("sdk.state.hostile.negative-control-ym-reason-is-magic",
            YM2610_CANDIDATE_STATE_REASON_MAGIC, ym_detail.reason);
        ym2610_candidate_test_bypass_next_state_validation();
    } else if (validator == STATE_VALIDATOR_Z80) {
        if (section_length < 76u) goto cleanup;
        working[section_offset + 5u] = 0xffu;
        working[section_offset + 6u] = 0xffu;
        z80_candidate_state *invalid_stage = NULL;
        SDK_CHECK_STATUS("sdk.state.hostile.negative-control-z80-validator-is-active",
            Z80_CANDIDATE_INVALID_SNAPSHOT,
            z80_candidate_state_stage(working + section_offset, 76u,
                                      &invalid_stage));
        z80_candidate_state_discard(invalid_stage);
        SDK_CHECK_STATUS("sdk.state.hostile.negative-control-arm-z80-bypass",
            GN_STATUS_OK, gn_test_state_validation_bypass_arm(
                target, GN_TEST_STATE_BYPASS_Z80_VALIDATOR));
    } else if (validator == STATE_VALIDATOR_YM_IRQ_RELATION) {
        if (section_length <= 77u) goto cleanup;
        working[section_offset + 77u] ^= 1u;
        memset(&detail, 0, sizeof(detail));
        const gn_status precheck = gn_state_restore_v1(
            target, working, state_size, &detail, sizeof(detail));
        SDK_CHECK_STATUS(
            "sdk.state.hostile.negative-control-ym-irq-relation-is-active",
            GN_STATUS_INVALID_MEDIA, precheck);
        SDK_CHECK_U64("sdk.state.hostile.negative-control-ym-irq-reason",
                      GN_STATE_REASON_CPU_STATE, detail.reason);
        SDK_CHECK_U64("sdk.state.hostile.negative-control-ym-irq-section",
                      4u, detail.section);
        size_t after_size = 0u;
        SDK_CHECK_TRUE("sdk.state.hostile.negative-control-ym-irq-target-intact",
            state_fixture_capture(target, &after_precheck, &after_size) &&
            after_size == state_size &&
            memcmp(after_precheck, state, state_size) == 0);
        SDK_CHECK_STATUS(
            "sdk.state.hostile.negative-control-arm-ym-irq-relation-bypass",
            GN_STATUS_OK, gn_test_state_validation_bypass_arm(
                target, GN_TEST_STATE_BYPASS_YM_IRQ_RELATION));
    } else {
        uint32_t timer = 2u;
        for (uint32_t index = 0u; index < 2u; ++index) {
            if (working[section_offset + 40u + index] != 0u) {
                timer = index;
                break;
            }
        }
        SDK_CHECK_TRUE("sdk.state.hostile.negative-control-active-timer-found",
                      timer < 2u);
        if (timer >= 2u) goto cleanup;
        ym2610_candidate_state_detail ym_detail;
        if (validator == STATE_VALIDATOR_YM_TIMER_RELATION) {
            working[section_offset + 40u + timer] = 0u;
            SDK_CHECK_STATUS(
                "sdk.state.hostile.negative-control-ym-timer-relation-is-active",
                YM2610_CANDIDATE_INVALID_ARGUMENT,
                ym2610_candidate_state_validate(working + section_offset,
                                                section_length, &ym_detail));
            SDK_CHECK_U64("sdk.state.hostile.negative-control-ym-timer-reason",
                          YM2610_CANDIDATE_STATE_REASON_INVARIANT,
                          ym_detail.reason);
            SDK_CHECK_U64("sdk.state.hostile.negative-control-ym-timer-offset",
                          40u + timer, ym_detail.offset);
        } else {
            const uint64_t now = read_u64be(working + section_offset + 8u);
            if (now > UINT64_MAX - UINT64_C(193)) goto cleanup;
            write_u64be(working + section_offset + 16u,
                        now + UINT64_C(193));
            SDK_CHECK_STATUS(
                "sdk.state.hostile.negative-control-ym-busy-relation-is-active",
                YM2610_CANDIDATE_INVALID_ARGUMENT,
                ym2610_candidate_state_validate(working + section_offset,
                                                section_length, &ym_detail));
            SDK_CHECK_U64("sdk.state.hostile.negative-control-ym-busy-reason",
                          YM2610_CANDIDATE_STATE_REASON_INVARIANT,
                          ym_detail.reason);
            SDK_CHECK_U64("sdk.state.hostile.negative-control-ym-busy-offset",
                          16u, ym_detail.offset);
        }
        ym2610_candidate_test_bypass_next_state_relation();
    }

    memset(&detail, 0, sizeof(detail));
    imported = gn_state_restore_v1(target, working, state_size, &detail,
                                   sizeof(detail));
    if (imported == GN_STATUS_OK) {
        (void)printf("SDK_STATE_NEGATIVE_CONTROL accepted_disabled_validator=%s\n",
                     name);
        /* The intentional bypass accepted malformed input. Tear down the
         * candidate before the expected assertion makes this test fail. */
        if (validator == STATE_VALIDATOR_Z80)
            (void)gn_test_state_failpoint_disarm(target);
        (void)gn_unload(target);
        (void)state_fixture_reload(target, fixture_variant);
    }

cleanup:
    free(after_precheck);
    free(working);
    free(state);
    gn_destroy(target);
    SDK_CHECK_STATUS("sdk.state.hostile.negative-control.expected-rejection",
                     GN_STATUS_INVALID_MEDIA, imported);
}

void state_mutation_negative_control_z80_test(void) {
    state_mutation_nested_validator_disabled_test(STATE_VALIDATOR_Z80);
}

void state_mutation_negative_control_ym_test(void) {
    state_mutation_nested_validator_disabled_test(STATE_VALIDATOR_YM);
}

void state_mutation_negative_control_ym_irq_relation_test(void) {
    state_mutation_nested_validator_disabled_test(
        STATE_VALIDATOR_YM_IRQ_RELATION);
}

void state_mutation_negative_control_ym_timer_relation_test(void) {
    state_mutation_nested_validator_disabled_test(
        STATE_VALIDATOR_YM_TIMER_RELATION);
}

void state_mutation_negative_control_ym_busy_relation_test(void) {
    state_mutation_nested_validator_disabled_test(
        STATE_VALIDATOR_YM_BUSY_RELATION);
}

static uint32_t read_u32be(const uint8_t *bytes) {
    return ((uint32_t)bytes[0] << 24) | ((uint32_t)bytes[1] << 16) |
           ((uint32_t)bytes[2] << 8) | (uint32_t)bytes[3];
}

static uint64_t read_u64be(const uint8_t *bytes) {
    uint64_t value = 0u;
    for (size_t index = 0u; index < 8u; ++index)
        value = (value << 8) | bytes[index];
    return value;
}

static int find_section(uint8_t *state, size_t size, uint32_t wanted,
                        size_t *out_offset, size_t *out_length) {
    if (state == NULL || size < STATE_HEADER_BYTES || out_offset == NULL ||
        out_length == NULL) return 0;
    size_t cursor = STATE_HEADER_BYTES;
    for (uint32_t index = 0u; index < 5u; ++index) {
        if (cursor > size || size - cursor < STATE_SECTION_HEADER_BYTES)
            return 0;
        const uint32_t section = read_u32be(state + cursor);
        const uint32_t length = read_u32be(state + cursor + 4u);
        cursor += STATE_SECTION_HEADER_BYTES;
        if ((size_t)length > size - cursor) return 0;
        if (section == wanted) {
            *out_offset = cursor;
            *out_length = (size_t)length;
            return 1;
        }
        cursor += length;
    }
    return 0;
}

static int find_section_header(uint8_t *state, size_t size, size_t wanted_index,
                               size_t *out_header) {
    if (state == NULL || size < STATE_HEADER_BYTES || out_header == NULL)
        return 0;
    size_t cursor = STATE_HEADER_BYTES;
    for (size_t index = 0u; index <= wanted_index; ++index) {
        if (cursor > size || size - cursor < STATE_SECTION_HEADER_BYTES)
            return 0;
        if (index == wanted_index) {
            *out_header = cursor;
            return 1;
        }
        const size_t section_length = read_u32be(state + cursor + 4u);
        cursor += STATE_SECTION_HEADER_BYTES;
        if (section_length > size - cursor) return 0;
        cursor += section_length;
    }
    return 0;
}

static void write_u16be(uint8_t *bytes, uint16_t value) {
    bytes[0] = (uint8_t)(value >> 8);
    bytes[1] = (uint8_t)value;
}

static void write_u32be(uint8_t *bytes, uint32_t value) {
    bytes[0] = (uint8_t)(value >> 24);
    bytes[1] = (uint8_t)(value >> 16);
    bytes[2] = (uint8_t)(value >> 8);
    bytes[3] = (uint8_t)value;
}

static void write_u64be(uint8_t *bytes, uint64_t value) {
    for (size_t index = 0u; index < 8u; ++index) {
        bytes[7u - index] = (uint8_t)value;
        value >>= 8;
    }
}

static int mutation_apply(const mutation_recipe *recipe, uint8_t *state,
                          size_t state_size, size_t *out_length,
                          size_t *out_mutated_offset) {
    *out_length = state_size;
    *out_mutated_offset = 0u;
    if (recipe->kind == MUTATION_TRUNCATE) {
        *out_length = state_size - 1u;
        *out_mutated_offset = state_size - 1u;
        return state_size > 0u;
    }
    if (recipe->kind == MUTATION_EMPTY) {
        *out_length = 0u;
        return 1;
    }
    if (recipe->kind == MUTATION_EXTEND) {
        state[state_size] = 0xa5u;
        *out_length = state_size + 1u;
        *out_mutated_offset = state_size;
        return 1;
    }
    if (recipe->kind == MUTATION_OVERSIZE_LENGTH) {
        *out_length = SIZE_MAX;
        return 1;
    }

    if (recipe->kind == MUTATION_YM_WRAPPER_FORGE) {
        static const uint64_t timer_max_duration[2] = {
            UINT64_C(147456), UINT64_C(589824)
        };
        size_t ym_offset = 0u;
        size_t ym_length = 0u;
        if (!find_section(state, state_size, STATE_YM_SECTION,
                          &ym_offset, &ym_length) || ym_length < 42u)
            return 0;
        const uint64_t now = read_u64be(state + ym_offset + 8u);
        size_t field_offset = 0u;
        uint64_t delta = 0u;
        switch ((ym_wrapper_forge_kind)recipe->value) {
            case YM_WRAPPER_RUNNING_WITHOUT_ACTIVE:
                if (recipe->offset >= 2u) return 0;
                field_offset = 40u + recipe->offset;
                state[ym_offset + field_offset] = 0u;
                break;
            case YM_WRAPPER_ACTIVE_WITHOUT_RUNNING:
                if (recipe->offset >= 2u || now == UINT64_MAX) return 0;
                field_offset = 40u + recipe->offset;
                write_u64be(state + ym_offset + 24u + recipe->offset * 8u,
                            now + 1u);
                state[ym_offset + field_offset] = 1u;
                break;
            case YM_WRAPPER_TIMER_DUE_BEYOND_BOUND:
                if (recipe->offset >= 2u) return 0;
                delta = timer_max_duration[recipe->offset] + 1u;
                if (delta > UINT64_MAX - now) return 0;
                field_offset = 24u + recipe->offset * 8u;
                write_u64be(state + ym_offset + field_offset, now + delta);
                break;
            case YM_WRAPPER_BUSY_END_BEYOND_WINDOW:
                delta = UINT64_C(193);
                if (delta > UINT64_MAX - now) return 0;
                field_offset = 16u;
                write_u64be(state + ym_offset + field_offset, now + delta);
                break;
            default:
                return 0;
        }
        *out_mutated_offset = ym_offset + field_offset;
        return 1;
    }

    if (recipe->kind == MUTATION_UNKNOWN_SECTION ||
        recipe->kind == MUTATION_DUPLICATE_SECTION ||
        recipe->kind == MUTATION_SECTION_LENGTH ||
        recipe->kind == MUTATION_SECTION_LENGTH_MAX) {
        size_t header = 0u;
        if (!find_section_header(state, state_size, recipe->offset, &header))
            return 0;
        *out_mutated_offset = header;
        if (recipe->kind == MUTATION_UNKNOWN_SECTION) {
            write_u32be(state + header, recipe->value);
        } else if (recipe->kind == MUTATION_DUPLICATE_SECTION) {
            write_u32be(state + header, recipe->value);
        } else if (recipe->kind == MUTATION_SECTION_LENGTH_MAX) {
            write_u32be(state + header + 4u, UINT32_MAX);
        } else {
            const uint32_t length = read_u32be(state + header + 4u);
            if (length == 0u) return 0;
            write_u32be(state + header + 4u, length - 1u);
        }
        return 1;
    }

    size_t offset = recipe->offset;
    if (recipe->section != 0u) {
        size_t section_offset = 0u;
        size_t section_length = 0u;
        if (!find_section(state, state_size, recipe->section,
                          &section_offset, &section_length) ||
            offset > section_length)
            return 0;
        offset += section_offset;
    }
    *out_mutated_offset = offset;
    if (offset >= state_size) return 0;
    switch (recipe->kind) {
        case MUTATION_SET_BYTE:
            state[offset] = (uint8_t)recipe->value;
            return 1;
        case MUTATION_XOR_BYTE:
            state[offset] ^= (uint8_t)recipe->value;
            return 1;
        case MUTATION_SET_U16:
            if (state_size - offset < 2u) return 0;
            write_u16be(state + offset, (uint16_t)recipe->value);
            return 1;
        case MUTATION_SET_U32:
            if (state_size - offset < 4u) return 0;
            write_u32be(state + offset, recipe->value);
            return 1;
        default:
            return 0;
    }
}

typedef struct {
    gn_instance *target;
    const uint8_t *input;
    size_t length;
    gn_state_detail_v1 *detail;
} measured_mutation_import;

static int invoke_mutation_import(void *raw) {
    measured_mutation_import *operation = (measured_mutation_import *)raw;
    return (int)gn_state_restore_v1(operation->target, operation->input,
        operation->length, operation->detail, sizeof(*operation->detail));
}

static void state_mutation_apply_recipe(
    gn_instance *target, gn_instance *witness, const uint8_t *valid_state,
    size_t state_size, uint8_t *working, uint8_t *snapshot,
    const mutation_recipe *recipe, uintptr_t target_save_ram,
    uintptr_t witness_save_ram) {
    SDK_CASE(recipe->id);
    SDK_CHECK_TRUE("sdk.state.hostile.reset-target-to-independent-witness",
        state_fixture_restore(target, valid_state, state_size) &&
        state_fixture_restore(witness, valid_state, state_size));
    memcpy(working, valid_state, state_size);
    size_t input_length = state_size;
    size_t mutation_offset = 0u;
    SDK_CHECK_TRUE("sdk.state.hostile.recipe-applies-to-current-format",
        mutation_apply(recipe, working, state_size, &input_length,
                       &mutation_offset));

    ym2610_candidate_state_detail nested_detail;
    memset(&nested_detail, 0, sizeof(nested_detail));
    size_t ym_offset = 0u;
    size_t ym_length = 0u;
    int check_staged_relation = 0;
    if (recipe->ym_reason != YM2610_CANDIDATE_STATE_REASON_NONE) {
        SDK_CHECK_TRUE("sdk.state.hostile.locate-nested-ym",
            find_section(working, state_size, STATE_YM_SECTION,
                         &ym_offset, &ym_length));
        if (recipe->ym_reason == YM2610_CANDIDATE_STATE_REASON_INVARIANT) {
            /* This cross-field check belongs to stage, not the read-only
             * traversal validator. Defer it until after the outer restore
             * assertion so a pre-fix RED identifies the accepted snapshot. */
            check_staged_relation = 1;
        } else {
            const ym2610_candidate_status nested_status =
                ym2610_candidate_state_validate(
                working + ym_offset, ym_length, &nested_detail);
            SDK_CHECK_STATUS("sdk.state.hostile.expected-nested-validator-rejects",
                             YM2610_CANDIDATE_INVALID_ARGUMENT, nested_status);
            SDK_CHECK_U64("sdk.state.hostile.expected-nested-reason",
                          recipe->ym_reason, nested_detail.reason);
        }
    }
    const size_t readable_input_length = input_length > state_size + 1u
        ? state_size : input_length;
    memcpy(snapshot, working, readable_input_length);
    gn_state_detail_v1 detail;
    memset(&detail, 0, sizeof(detail));
    measured_mutation_import operation = {target, working, input_length, &detail};
    size_t ym_points = 0u, ym_requested = 0u, ym_peak = 0u;
    int64_t ym_lifetime = 0;
    uint32_t ym_failed_site = 0u;
    int import_result = -1;
    gn_test_state_failpoint_info c_allocations;
    gn_test_state_resources resources;
    SDK_CHECK_STATUS("sdk.state.resources.hostile-arm-c-measurement",
        GN_STATUS_OK, gn_test_state_failpoint_arm(target, 0u));
    SDK_CHECK_STATUS("sdk.state.resources.hostile-measure-real-import",
        YM2610_CANDIDATE_OK, ym2610_candidate_test_invoke_with_failpoint(
            invoke_mutation_import, &operation, SIZE_MAX, &import_result,
            &ym_points, &ym_lifetime, &ym_requested, &ym_peak, &ym_failed_site));
    const gn_status status = (gn_status)import_result;
    STATE_RESOURCE_CHECK(target);
    SDK_CHECK_STATUS("sdk.state.resources.hostile-read-c", GN_STATUS_OK,
        gn_test_state_failpoint_read(target, &c_allocations));
    SDK_CHECK_STATUS("sdk.state.resources.hostile-read-budget", GN_STATUS_OK,
        gn_test_state_resources_read(target, &resources));
    SDK_CHECK_TRUE("sdk.state.resources.hostile-measured-aggregate-bounded",
        resources.stack_staging_bytes + c_allocations.high_water_bytes +
            ym_peak <= resources.staging_bytes);
    SDK_CHECK_TRUE("sdk.state.resources.hostile-fixed-constructors-bounded",
        ym_points <= ym2610_candidate_state_allocation_bound() &&
        c_allocations.attempts <= 2u);
    SDK_CHECK_STATUS("sdk.state.resources.hostile-disarm-c", GN_STATUS_OK,
        gn_test_state_failpoint_disarm(target));
    SDK_CHECK_STATUS("sdk.state.hostile.expected-status", recipe->status,
                     status);
    SDK_CHECK_U64("sdk.state.hostile.expected-reason", recipe->reason,
                  detail.reason);
    SDK_CHECK_U64("sdk.state.hostile.expected-section", recipe->error_section,
                  detail.section);
    if (check_staged_relation) {
        ym2610_candidate *staged_ym = NULL;
        const ym2610_candidate_status nested_status =
            ym2610_candidate_state_stage(working + ym_offset, ym_length,
                                         &staged_ym, &nested_detail);
        ym2610_candidate_destroy(staged_ym);
        SDK_CHECK_STATUS("sdk.state.hostile.expected-nested-validator-rejects",
                         YM2610_CANDIDATE_INVALID_ARGUMENT, nested_status);
        SDK_CHECK_U64("sdk.state.hostile.expected-nested-reason",
                      recipe->ym_reason, nested_detail.reason);
    }

    size_t expected_offset = 0u;
    switch (recipe->offset_kind) {
        case OFFSET_ABSOLUTE:
            expected_offset = recipe->kind == MUTATION_UNKNOWN_SECTION ||
                    recipe->kind == MUTATION_DUPLICATE_SECTION ||
                    recipe->kind == MUTATION_SECTION_LENGTH ||
                    recipe->kind == MUTATION_SECTION_LENGTH_MAX
                ? mutation_offset : recipe->offset_delta;
            break;
        case OFFSET_SECTION_START: {
            size_t section_length = 0u;
            SDK_CHECK_TRUE("sdk.state.hostile.locate-error-section",
                find_section(working, state_size, recipe->error_section,
                             &expected_offset, &section_length));
            break;
        }
        case OFFSET_SECTION_START_DELTA: {
            size_t section_length = 0u;
            SDK_CHECK_TRUE("sdk.state.hostile.locate-error-section",
                find_section(working, state_size, recipe->error_section,
                             &expected_offset, &section_length));
            expected_offset += recipe->offset_delta;
            break;
        }
        case OFFSET_INPUT_LENGTH:
            expected_offset = input_length;
            break;
        case OFFSET_INPUT_CAPACITY:
            expected_offset = state_size;
            break;
        case OFFSET_NESTED_DETAIL:
            expected_offset = ym_offset + nested_detail.offset;
            break;
    }
    SDK_CHECK_U64("sdk.state.hostile.expected-offset", expected_offset,
                  detail.offset);
    SDK_CHECK_TRUE("sdk.state.hostile.read-only-import-input",
                   memcmp(working, snapshot, readable_input_length) == 0);

    if (status != GN_STATUS_OK) {
        state_fixture_observation expected;
        state_fixture_observation actual;
        SDK_CHECK_TRUE("sdk.state.hostile.rejection-witness-advance",
            state_fixture_advance(witness, GN_MVS_INPUT_P1_A, &expected));
        SDK_CHECK_TRUE("sdk.state.hostile.rejected-target-advance",
            state_fixture_advance(target, GN_MVS_INPUT_P1_A, &actual));
        SDK_CHECK_TRUE("sdk.state.hostile.reject-preserves-full-continuation",
            state_fixture_observation_equal(&expected, &actual));
        SDK_CHECK_TRUE("sdk.state.hostile.reject-retains-save-ram-owner",
            target_save_ram == gn_test_mvs_save_ram_address(target));
        SDK_CHECK_TRUE("sdk.state.hostile.reject-retains-peer-owner",
            witness_save_ram == gn_test_mvs_save_ram_address(witness));
    } else {
        /* A bad input accepted by the importer must never be advanced. */
        SDK_CHECK_STATUS("sdk.state.hostile.accepted-mutation-reset",
                         GN_STATUS_OK, gn_unload(target));
        SDK_CHECK_TRUE("sdk.state.hostile.accepted-mutation-reload",
                       state_fixture_reload(target, 0u));
    }
}

static int state_mutation_find_ym_reason(
    const uint8_t *valid_ym, size_t ym_length, size_t first_offset,
    size_t last_offset, ym2610_candidate_state_reason wanted_reason,
    size_t *out_offset, uint8_t *out_value) {
    static const uint8_t probes[] = {0xffu, 0x80u, 0x7fu, 0x40u,
                                     0x02u, 0x01u, 0x00u};
    uint8_t *candidate = (uint8_t *)malloc(ym_length);
    if (candidate == NULL || first_offset >= last_offset ||
        last_offset > ym_length) {
        free(candidate);
        return 0;
    }
    for (size_t offset = first_offset; offset < last_offset; ++offset) {
        for (size_t probe = 0u; probe < sizeof(probes); ++probe) {
            if (valid_ym[offset] == probes[probe]) continue;
            memcpy(candidate, valid_ym, ym_length);
            candidate[offset] = probes[probe];
            ym2610_candidate_state_detail detail;
            const ym2610_candidate_status status =
                ym2610_candidate_state_validate(candidate, ym_length, &detail);
            if (status == YM2610_CANDIDATE_INVALID_ARGUMENT &&
                detail.reason == wanted_reason) {
                *out_offset = offset;
                *out_value = probes[probe];
                free(candidate);
                return 1;
            }
        }
    }
    free(candidate);
    return 0;
}

static void state_mutation_ym_relation_bounds_accepted_test(void) {
    SDK_CASE("sdk.state.hostile.ym-relation-bounds-accepted");
    ym2610_candidate_callbacks callbacks = {0};
    ym2610_candidate *candidate = NULL;
    uint8_t *bytes = NULL;
    size_t state_size = 0u;
    size_t written = 0u;
    ym2610_candidate_state_detail detail;
    SDK_CHECK_STATUS("sdk.state.hostile.ym-bounds-candidate-create",
        YM2610_CANDIDATE_OK,
        ym2610_candidate_create(&callbacks, NULL, &candidate));
    if (candidate == NULL) goto cleanup;
    SDK_CHECK_STATUS("sdk.state.hostile.ym-bounds-size",
        YM2610_CANDIDATE_OK,
        ym2610_candidate_state_size(candidate, &state_size));
    bytes = (uint8_t *)malloc(state_size);
    SDK_CHECK_TRUE("sdk.state.hostile.ym-bounds-storage", bytes != NULL);
    if (bytes == NULL) goto cleanup;

    for (uint32_t timer = 0u; timer < 2u; ++timer) {
        uint64_t timer_bound = 0u;
        uint64_t busy_bound = 0u;
        const uint64_t expected_timer_bound = timer == 0u
            ? UINT64_C(147456) : UINT64_C(589824);
        SDK_CHECK_STATUS("sdk.state.hostile.ym-bounds-reset",
            YM2610_CANDIDATE_OK, ym2610_candidate_reset(candidate));
        if (timer == 0u) {
            SDK_CHECK_STATUS("sdk.state.hostile.ym-bounds-timer-a-value-low",
                YM2610_CANDIDATE_OK,
                ym2610_candidate_write(candidate, 0u, 0x24u));
            SDK_CHECK_STATUS("sdk.state.hostile.ym-bounds-timer-a-value-low-data",
                YM2610_CANDIDATE_OK,
                ym2610_candidate_write(candidate, 1u, 0u));
            SDK_CHECK_STATUS("sdk.state.hostile.ym-bounds-timer-a-value-high",
                YM2610_CANDIDATE_OK,
                ym2610_candidate_write(candidate, 0u, 0x25u));
            SDK_CHECK_STATUS("sdk.state.hostile.ym-bounds-timer-a-value-high-data",
                YM2610_CANDIDATE_OK,
                ym2610_candidate_write(candidate, 1u, 0u));
            SDK_CHECK_STATUS("sdk.state.hostile.ym-bounds-timer-a-control",
                YM2610_CANDIDATE_OK,
                ym2610_candidate_write(candidate, 0u, 0x27u));
            SDK_CHECK_STATUS("sdk.state.hostile.ym-bounds-timer-a-control-data",
                YM2610_CANDIDATE_OK,
                ym2610_candidate_write(candidate, 1u, 0x05u));
        } else {
            SDK_CHECK_STATUS("sdk.state.hostile.ym-bounds-timer-b-value",
                YM2610_CANDIDATE_OK,
                ym2610_candidate_write(candidate, 0u, 0x26u));
            SDK_CHECK_STATUS("sdk.state.hostile.ym-bounds-timer-b-value-data",
                YM2610_CANDIDATE_OK,
                ym2610_candidate_write(candidate, 1u, 0u));
            SDK_CHECK_STATUS("sdk.state.hostile.ym-bounds-timer-b-control",
                YM2610_CANDIDATE_OK,
                ym2610_candidate_write(candidate, 0u, 0x27u));
            SDK_CHECK_STATUS("sdk.state.hostile.ym-bounds-timer-b-control-data",
                YM2610_CANDIDATE_OK,
                ym2610_candidate_write(candidate, 1u, 0x0au));
        }
        SDK_CHECK_STATUS("sdk.state.hostile.ym-bounds-timer-accessor",
            YM2610_CANDIDATE_OK,
            ym2610_candidate_state_timer_bound(timer, &timer_bound));
        SDK_CHECK_U64("sdk.state.hostile.ym-bounds-timer-value",
                      expected_timer_bound, timer_bound);
        SDK_CHECK_STATUS("sdk.state.hostile.ym-bounds-busy-accessor",
            YM2610_CANDIDATE_OK,
            ym2610_candidate_state_busy_bound(&busy_bound));
        SDK_CHECK_U64("sdk.state.hostile.ym-bounds-busy-value", 192u,
                      busy_bound);
        SDK_CHECK_STATUS("sdk.state.hostile.ym-bounds-capture",
            YM2610_CANDIDATE_OK,
            ym2610_candidate_state_capture(candidate, bytes, state_size,
                                          &written));
        SDK_CHECK_TRUE("sdk.state.hostile.ym-bounds-capture-complete",
                       written == state_size);
        SDK_CHECK_U64("sdk.state.hostile.ym-bounds-captured-timer-active", 1u,
                      bytes[40u + timer]);

        const uint64_t now = read_u64be(bytes + 8u);
        SDK_CHECK_TRUE("sdk.state.hostile.ym-bounds-clock-no-overflow",
            now <= UINT64_MAX - timer_bound &&
            now <= UINT64_MAX - busy_bound);
        write_u64be(bytes + 24u + 8u * timer, now + timer_bound);
        write_u64be(bytes + 16u, now + busy_bound);
        SDK_CHECK_STATUS("sdk.state.hostile.ym-bounds-exact-maximum-accepted",
            YM2610_CANDIDATE_OK,
            ym2610_candidate_state_validate(bytes, state_size, &detail));

        write_u64be(bytes + 16u, 0u);
        SDK_CHECK_STATUS("sdk.state.hostile.ym-bounds-expired-busy-accepted",
            YM2610_CANDIDATE_OK,
            ym2610_candidate_state_validate(bytes, state_size, &detail));
    }

cleanup:
    free(bytes);
    ym2610_candidate_destroy(candidate);
}

void state_mutation_hostile_matrix_test(void) {
    SDK_CASE("sdk.state.hostile.outer-and-nested-matrix");
    gn_instance *target = NULL;
    gn_instance *witness = NULL;
    uint8_t *valid_state = NULL;
    uint8_t *working = NULL;
    uint8_t *snapshot = NULL;
    size_t state_size = 0u;
    state_fixture_observation accepted_expected;
    state_fixture_observation accepted_actual;
    SDK_CHECK_TRUE("sdk.state.hostile.matrix-target-load",
                   state_fixture_load(&target,
                       STATE_FIXTURE_VARIANT_ACTIVE_TIMER));
    SDK_CHECK_TRUE("sdk.state.hostile.matrix-witness-load",
                   state_fixture_load(&witness,
                       STATE_FIXTURE_VARIANT_ACTIVE_TIMER));
    if (target == NULL || witness == NULL) goto cleanup;
    SDK_CHECK_TRUE("sdk.state.hostile.matrix-target-timer-setup",
        state_fixture_advance(target, 0u, &accepted_actual));
    SDK_CHECK_TRUE("sdk.state.hostile.matrix-witness-timer-setup",
        state_fixture_advance(witness, 0u, &accepted_expected));
    gn_mvs_sound_observation timer_observation;
    SDK_CHECK_STATUS("sdk.state.hostile.matrix-target-timer-observation",
        GN_STATUS_OK, gn_private_mvs_sound_observe(target, &timer_observation));
    SDK_CHECK_TRUE("sdk.state.hostile.matrix-timer-setup-leaves-programmed-timer",
        timer_observation.chip.timer_programs >
            timer_observation.chip.timer_expirations);
    uint8_t *captured = NULL;
    SDK_CHECK_TRUE("sdk.state.hostile.matrix-capture",
                   state_fixture_capture(target, &captured, &state_size));
    if (captured == NULL) goto cleanup;
    valid_state = (uint8_t *)malloc(state_size);
    working = (uint8_t *)malloc(state_size + 1u);
    snapshot = (uint8_t *)malloc(state_size + 1u);
    SDK_CHECK_TRUE("sdk.state.hostile.matrix-storage",
                   valid_state != NULL && working != NULL && snapshot != NULL);
    if (valid_state == NULL || working == NULL || snapshot == NULL) {
        free(captured);
        goto cleanup;
    }
    memcpy(valid_state, captured, state_size);
    free(captured);
    const uintptr_t target_save_ram = gn_test_mvs_save_ram_address(target);
    const uintptr_t witness_save_ram = gn_test_mvs_save_ram_address(witness);
    SDK_CHECK_TRUE("sdk.state.hostile.matrix-owner-addresses",
                   target_save_ram != (uintptr_t)0 &&
                   witness_save_ram != (uintptr_t)0 &&
                   target_save_ram != witness_save_ram);

    SDK_CASE("sdk.state.hostile.valid-public-snapshot-roundtrip");
    SDK_CHECK_TRUE("sdk.state.hostile.accept-exact-current-snapshot",
                   state_fixture_restore(target, valid_state, state_size));
    SDK_CHECK_TRUE("sdk.state.hostile.accepted-target-advance",
        state_fixture_advance(target, GN_MVS_INPUT_P1_A, &accepted_actual));
    SDK_CHECK_TRUE("sdk.state.hostile.accepted-independent-witness-advance",
        state_fixture_advance(witness, GN_MVS_INPUT_P1_A, &accepted_expected));
    SDK_CHECK_TRUE("sdk.state.hostile.accepted-continuation-equal",
        state_fixture_observation_equal(&accepted_expected, &accepted_actual));
    SDK_CHECK_TRUE("sdk.state.hostile.accepted-target-owner-retained",
                  target_save_ram == gn_test_mvs_save_ram_address(target));
    SDK_CHECK_TRUE("sdk.state.hostile.accepted-peer-owner-retained",
                  witness_save_ram == gn_test_mvs_save_ram_address(witness));

    size_t ym_offset = 0u;
    size_t ym_length = 0u;
    SDK_CHECK_TRUE("sdk.state.hostile.matrix-valid-ym-accepted",
        find_section(valid_state, state_size, STATE_YM_SECTION,
                     &ym_offset, &ym_length));
    ym2610_candidate_state_detail valid_ym_detail;
    SDK_CHECK_STATUS("sdk.state.hostile.matrix-valid-ym-schema",
        YM2610_CANDIDATE_OK,
        ym2610_candidate_state_validate(valid_state + ym_offset, ym_length,
                                        &valid_ym_detail));
    SDK_CHECK_TRUE("sdk.state.hostile.valid-ym-checked-traversal-consumes",
                   valid_ym_detail.consumed == ym_length);

    size_t active_timer = 2u;
    size_t inactive_timer = 2u;
    for (size_t timer = 0u; timer < 2u; ++timer) {
        if (valid_state[ym_offset + 40u + timer] == 1u && active_timer == 2u)
            active_timer = timer;
        if (valid_state[ym_offset + 40u + timer] == 0u && inactive_timer == 2u)
            inactive_timer = timer;
    }
    SDK_CHECK_TRUE("sdk.state.hostile.matrix-finds-active-ym-timer",
                   active_timer < 2u);
    SDK_CHECK_TRUE("sdk.state.hostile.matrix-finds-inactive-ym-timer",
                   inactive_timer < 2u);
    state_mutation_ym_relation_bounds_accepted_test();

    /* Direct nested length controls prove the YM parser's underflow and
     * exact-consumption errors independently of the fixed outer descriptor. */
    ym2610_candidate_state_detail boundary_detail;
    SDK_CHECK_STATUS("sdk.state.hostile.ym-underflow-rejected",
        YM2610_CANDIDATE_INVALID_ARGUMENT,
        ym2610_candidate_state_validate(valid_state + ym_offset,
                                        ym_length - 1u, &boundary_detail));
    SDK_CHECK_U64("sdk.state.hostile.ym-underflow-reason",
        YM2610_CANDIDATE_STATE_REASON_TRUNCATED, boundary_detail.reason);
    SDK_CHECK_TRUE("sdk.state.hostile.ym-underflow-offset-bounded",
                   boundary_detail.offset <= ym_length);
    memcpy(working, valid_state, state_size);
    working[state_size] = 0x5au;
    SDK_CHECK_STATUS("sdk.state.hostile.ym-trailing-byte-rejected",
        YM2610_CANDIDATE_INVALID_ARGUMENT,
        ym2610_candidate_state_validate(working + ym_offset,
                                        ym_length + 1u, &boundary_detail));
    SDK_CHECK_U64("sdk.state.hostile.ym-trailing-reason",
        YM2610_CANDIDATE_STATE_REASON_TRAILING, boundary_detail.reason);
    SDK_CHECK_TRUE("sdk.state.hostile.ym-trailing-offset-bounded",
                   boundary_detail.offset <= ym_length + 1u);
    /* Held SSG lanes follow the sample index at 917; the largest table
     * amplitude (16382) is admissible and one above it is not. */
    int ssg_held_max_accepted = 1;
    int ssg_held_above_rejected = 1;
    for (size_t lane = 0u; lane < 3u; ++lane) {
        const size_t held = ym_offset + 921u + lane * 4u;
        memcpy(working, valid_state, state_size);
        write_u32be(working + ym_offset + 917u, 1u);
        write_u32be(working + held, 16382u);
        if (ym2610_candidate_state_validate(working + ym_offset, ym_length,
                &boundary_detail) != YM2610_CANDIDATE_OK)
            ssg_held_max_accepted = 0;
        write_u32be(working + held, 16383u);
        if (ym2610_candidate_state_validate(working + ym_offset, ym_length,
                &boundary_detail) != YM2610_CANDIDATE_INVALID_ARGUMENT ||
            boundary_detail.reason != YM2610_CANDIDATE_STATE_REASON_RANGE)
            ssg_held_above_rejected = 0;
        write_u32be(working + held, 0xffffffffu);
        if (ym2610_candidate_state_validate(working + ym_offset, ym_length,
                &boundary_detail) != YM2610_CANDIDATE_INVALID_ARGUMENT)
            ssg_held_above_rejected = 0;
    }
    SDK_CHECK_TRUE("sdk.state.hostile.ym-ssg-held-table-max-accepted",
                   ssg_held_max_accepted);
    SDK_CHECK_TRUE("sdk.state.hostile.ym-ssg-held-out-of-table-rejected",
                   ssg_held_above_rejected);

    size_t sound_offset = 0u;
    size_t sound_length = 0u;
    z80_candidate_state *valid_z80_stage = NULL;
    SDK_CHECK_TRUE("sdk.state.hostile.locate-valid-z80-section",
        find_section(valid_state, state_size, 4u, &sound_offset,
                     &sound_length));
    SDK_CHECK_TRUE("sdk.state.hostile.z80-section-includes-fixed-payload",
                   sound_length >= 76u);
    SDK_CHECK_STATUS("sdk.state.hostile.valid-z80-stage-accepted",
        Z80_CANDIDATE_OK,
        z80_candidate_state_stage(valid_state + sound_offset, 76u,
                                  &valid_z80_stage));
    z80_candidate_state_discard(valid_z80_stage);

    for (size_t index = 0u;
         index < sizeof(mutation_recipes) / sizeof(mutation_recipes[0]);
         ++index) {
        state_mutation_apply_recipe(target, witness, valid_state, state_size,
            working, snapshot, &mutation_recipes[index], target_save_ram,
            witness_save_ram);
    }

    if (active_timer < 2u && inactive_timer < 2u) {
        const mutation_recipe ym_relation_recipes[] = {
            {"state.ym.timer-running-without-active",
             MUTATION_YM_WRAPPER_FORGE, STATE_YM_SECTION, active_timer,
             YM_WRAPPER_RUNNING_WITHOUT_ACTIVE, GN_STATE_REASON_CPU_STATE,
             STATE_YM_SECTION, GN_STATUS_INVALID_MEDIA, OFFSET_NESTED_DETAIL,
             0u, YM2610_CANDIDATE_STATE_REASON_INVARIANT},
            {"state.ym.timer-active-without-running",
             MUTATION_YM_WRAPPER_FORGE, STATE_YM_SECTION, inactive_timer,
             YM_WRAPPER_ACTIVE_WITHOUT_RUNNING, GN_STATE_REASON_CPU_STATE,
             STATE_YM_SECTION, GN_STATUS_INVALID_MEDIA, OFFSET_NESTED_DETAIL,
             0u, YM2610_CANDIDATE_STATE_REASON_INVARIANT},
            {"state.ym.timer-due-beyond-period",
             MUTATION_YM_WRAPPER_FORGE, STATE_YM_SECTION, active_timer,
             YM_WRAPPER_TIMER_DUE_BEYOND_BOUND, GN_STATE_REASON_CPU_STATE,
             STATE_YM_SECTION, GN_STATUS_INVALID_MEDIA, OFFSET_NESTED_DETAIL,
             0u, YM2610_CANDIDATE_STATE_REASON_INVARIANT},
            {"state.ym.busy-end-beyond-window",
             MUTATION_YM_WRAPPER_FORGE, STATE_YM_SECTION, 0u,
             YM_WRAPPER_BUSY_END_BEYOND_WINDOW, GN_STATE_REASON_CPU_STATE,
             STATE_YM_SECTION, GN_STATUS_INVALID_MEDIA, OFFSET_NESTED_DETAIL,
             0u, YM2610_CANDIDATE_STATE_REASON_INVARIANT}
        };
        for (size_t index = 0u;
             index < sizeof(ym_relation_recipes) /
                 sizeof(ym_relation_recipes[0]); ++index) {
            state_mutation_apply_recipe(target, witness, valid_state,
                state_size, working, snapshot, &ym_relation_recipes[index],
                target_save_ram, witness_save_ram);
        }
    }

    size_t nested_offset = 0u;
    uint8_t nested_value = 0u;
    const int enum_found = state_mutation_find_ym_reason(
        valid_state + ym_offset, ym_length,
            53u, ym_length, YM2610_CANDIDATE_STATE_REASON_ENUM,
            &nested_offset, &nested_value);
    SDK_CHECK_TRUE("sdk.state.hostile.matrix-finds-ym-enum", enum_found);
    if (enum_found) {
        const mutation_recipe enum_recipe = {
            "state.ym.enum", MUTATION_SET_BYTE, STATE_YM_SECTION,
            nested_offset, nested_value, GN_STATE_REASON_CPU_STATE,
            STATE_YM_SECTION, GN_STATUS_INVALID_MEDIA, OFFSET_NESTED_DETAIL,
            0u, YM2610_CANDIDATE_STATE_REASON_ENUM
        };
        state_mutation_apply_recipe(target, witness, valid_state, state_size,
            working, snapshot, &enum_recipe, target_save_ram,
            witness_save_ram);
    }

    const size_t adpcm_start = ym_length > 320u ? ym_length - 320u : 53u;
    nested_offset = SIZE_MAX;
    nested_value = 0u;
    const int adpcm_range_found = state_mutation_find_ym_reason(
        valid_state + ym_offset, ym_length,
            adpcm_start, ym_length > 8u ? ym_length - 8u : ym_length,
            YM2610_CANDIDATE_STATE_REASON_RANGE,
            &nested_offset, &nested_value);
    SDK_CHECK_TRUE("sdk.state.hostile.matrix-finds-adpcm-range",
                   adpcm_range_found);
    if (adpcm_range_found) {
        const mutation_recipe adpcm_recipe = {
            "state.ym.adpcm-range", MUTATION_SET_BYTE, STATE_YM_SECTION,
            nested_offset, nested_value, GN_STATE_REASON_CPU_STATE,
            STATE_YM_SECTION, GN_STATUS_INVALID_MEDIA, OFFSET_NESTED_DETAIL,
            0u, YM2610_CANDIDATE_STATE_REASON_RANGE
        };
        state_mutation_apply_recipe(target, witness, valid_state, state_size,
            working, snapshot, &adpcm_recipe, target_save_ram,
            witness_save_ram);
    }

cleanup:
    free(snapshot);
    free(working);
    free(valid_state);
    gn_destroy(witness);
    gn_destroy(target);
}

void state_mutation_ym_offset_test(void) {
    SDK_CASE("sdk.state.hostile.ym-nested-offset");
    gn_instance *target = NULL;
    gn_instance *witness = NULL;
    uint8_t *state = NULL;
    uint8_t *valid_state = NULL;
    size_t state_size = 0u;
    size_t ym_offset = 0u;
    size_t ym_length = 0u;
    const uint8_t input = GN_MVS_INPUT_P1_A;
    uintptr_t witness_save_ram = 0u;
    state_fixture_observation expected;
    state_fixture_observation actual;
    gn_state_detail_v1 detail;

    SDK_CHECK_TRUE("sdk.state.hostile.target-load",
                   state_fixture_load(&target, 0u));
    SDK_CHECK_TRUE("sdk.state.hostile.witness-load",
                   state_fixture_load(&witness, 0u));
    if (target == NULL || witness == NULL) goto cleanup;
    const uintptr_t retained_save_ram = gn_test_mvs_save_ram_address(target);
    witness_save_ram = gn_test_mvs_save_ram_address(witness);
    SDK_CHECK_TRUE("sdk.state.hostile.save-ram-owner",
                   retained_save_ram != (uintptr_t)0);
    SDK_CHECK_TRUE("sdk.state.hostile.capture",
                   state_fixture_capture(target, &state, &state_size));
    if (state == NULL) goto cleanup;
    valid_state = (uint8_t *)malloc(state_size);
    SDK_CHECK_TRUE("sdk.state.hostile.valid-witness-copy", valid_state != NULL);
    if (valid_state == NULL) goto cleanup;
    memcpy(valid_state, state, state_size);
    SDK_CHECK_TRUE("sdk.state.hostile.locate-ym",
                   find_section(state, state_size, STATE_YM_SECTION,
                                &ym_offset, &ym_length));
    SDK_CHECK_TRUE("sdk.state.hostile.ym-section-nonempty", ym_length > 0u);
    if (ym_length == 0u) goto cleanup;

    /* Invalid nested magic must stop in the YM validator and report the
     * bounded absolute offset of the nested section, without its contents. */
    state_fixture_write_u32be(state + 12u, read_u32be(state + 12u));
    const size_t invalid_magic_offset = ym_offset;
    state[invalid_magic_offset] ^= 0x01u;
    memset(&detail, 0, sizeof(detail));
    const gn_status rejected = gn_state_restore_v1(target, state, state_size,
                                                    &detail, sizeof(detail));
    SDK_CHECK_TRUE("sdk.state.hostile.reject-ym-magic",
                   rejected != GN_STATUS_OK);
    SDK_CHECK_U64("sdk.state.hostile.ym-section", STATE_YM_SECTION,
                  detail.section);
    SDK_CHECK_U64("sdk.state.hostile.ym-offset", invalid_magic_offset + 8u,
                  detail.offset);

    SDK_CHECK_TRUE("sdk.state.hostile.bad-input-guard",
                   state_fixture_guard_valid(state, state_size));
    SDK_CHECK_TRUE("sdk.state.hostile.restore-independent-witness",
                   state_fixture_restore(witness, valid_state, state_size));
    SDK_CHECK_TRUE("sdk.state.hostile.expected-next-frame",
                   state_fixture_advance(witness, input, &expected));
    SDK_CHECK_TRUE("sdk.state.hostile.actual-next-frame",
                   state_fixture_advance(target, input, &actual));
    SDK_CHECK_TRUE("sdk.state.hostile.reject-preserves-continuation",
                   state_fixture_observation_equal(&expected, &actual));
    SDK_CHECK_TRUE("sdk.state.hostile.save-ram-retained",
                  retained_save_ram == gn_test_mvs_save_ram_address(target));
    SDK_CHECK_TRUE("sdk.state.hostile.peer-save-ram-retained",
                  witness_save_ram == gn_test_mvs_save_ram_address(witness));
    (void)sdk_test_result;

cleanup:
    free(valid_state);
    free(state);
    gn_destroy(witness);
    gn_destroy(target);
}
