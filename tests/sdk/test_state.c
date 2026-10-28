/* SPDX-License-Identifier: MIT */
#include "state_fixture.h"

#include <stdio.h>

void state_mutation_ym_offset_test(void);
void state_mutation_corpus_coverage_test(void);
void state_mutation_hostile_matrix_test(void);
#if defined(GLUEYNEO_STATE_MUTATION_EXECUTABLE)
void state_mutation_oom_red_test(void);
void state_oom_case_counts(uint64_t *out_cases, uint64_t *out_assertions);
#endif
void state_mutation_negative_control_z80_test(void);
void state_mutation_negative_control_ym_test(void);
void state_mutation_negative_control_ym_irq_relation_test(void);
void state_mutation_negative_control_ym_timer_relation_test(void);
void state_mutation_negative_control_ym_busy_relation_test(void);
void state_mutation_case_counts(uint64_t *out_cases,
                                uint64_t *out_assertions);

#ifndef GLUEYNEO_SOURCE_REVISION
#define GLUEYNEO_SOURCE_REVISION "unknown"
#endif
#ifndef GLUEYNEO_CONFIGURATION
#define GLUEYNEO_CONFIGURATION "unspecified"
#endif
#ifndef GLUEYNEO_COMPILER_ID
#define GLUEYNEO_COMPILER_ID "unknown"
#endif
#ifndef GLUEYNEO_COMPILER_VERSION
#define GLUEYNEO_COMPILER_VERSION "unknown"
#endif

void setUp(void) {}
void tearDown(void) {}

static int state_fixture_advance_total(gn_instance *instance, uint32_t input,
                                       uint64_t *total_cycles,
                                       state_fixture_observation *observation) {
    if (!state_fixture_advance(instance, input, observation)) return 0;
    if (UINT64_MAX - *total_cycles < observation->result.elapsed_cycles) return 0;
    *total_cycles += observation->result.elapsed_cycles;
    observation->total_cycles = *total_cycles;
    return 1;
}

static void state_restore_continues_full_guest_video_pcm_and_time(void) {
    SDK_CASE("sdk.state.continuation.full-observation");
    gn_instance *source = NULL;
    gn_instance *destination = NULL;
    uint8_t *transfer = NULL;
    size_t transfer_size = 0u;
    state_fixture_observation expected;
    state_fixture_observation actual;
    uint64_t source_cycles = 0u;
    uint64_t destination_cycles = 0u;
    SDK_CHECK_TRUE("sdk.state.fixture.source-load", state_fixture_load(&source, 0u));
    SDK_CHECK_TRUE("sdk.state.fixture.destination-load",
                   state_fixture_load(&destination, 0u));
    if (source == NULL || destination == NULL) goto cleanup;
    gn_test_mvs_machine_state initial_machine;
    SDK_CHECK_STATUS("sdk.state.initial-machine-state", GN_STATUS_OK,
                     gn_test_mvs_machine_state_read(source, &initial_machine));
    gn_run_result raw;
    SDK_CHECK_STATUS("sdk.state.raw-budget-status", GN_STATUS_OK,
                     gn_run(source, 1u, &raw));
    SDK_CHECK_TRUE("sdk.state.raw-budget-overshoot-observed",
                   raw.overshoot_cycles > 0u &&
                   raw.elapsed_cycles == raw.requested_cycles +
                       raw.overshoot_cycles);
    SDK_CHECK_TRUE("sdk.state.warmup-1",
                   state_fixture_advance_total(source, 0u, &source_cycles,
                                                &expected));
    SDK_CHECK_TRUE("sdk.state.warmup-2",
                   state_fixture_advance_total(source, GN_MVS_INPUT_P1_A,
                                               &source_cycles, &expected));
    gn_test_mvs_sound_state seeded;
    SDK_CHECK_STATUS("sdk.state.seeded-sound-state", GN_STATUS_OK,
                     gn_test_mvs_sound_state_read(source, &seeded));
    SDK_CHECK_TRUE("sdk.state.nontrivial-sound-and-filter",
                   seeded.native_samples > 0u && seeded.filter_history_digest != 0u &&
                   seeded.timer_register_writes[0] > 0u &&
                   seeded.irq_assertions > 0u && seeded.bank_changes > 0u);
    gn_mvs_private_video_activity video;
    SDK_CHECK_STATUS("sdk.state.seeded-video-state", GN_STATUS_OK,
                     gn_private_mvs_video_activity(source, &video));
    SDK_CHECK_TRUE("sdk.state.nontrivial-video-and-carry",
                   video.nonzero_vram_words > 0u && video.frame_count > 0u &&
                   video.frame_cycle_carry > 0u);
    SDK_CHECK_TRUE("sdk.state.nontrivial-calendar-watchdog-and-irq",
                   expected.calendar.tick_remainder != 0u &&
                   expected.machine.watchdog_remaining_cycles > 0u &&
                   expected.machine.watchdog_remaining_cycles <
                       initial_machine.watchdog_remaining_cycles &&
                   expected.machine.watchdog_pet_count >=
                       initial_machine.watchdog_pet_count &&
                   expected.machine.irq_pending_mask != 0u);
    SDK_CHECK_TRUE("sdk.state.capture-source", state_fixture_capture(
                       source, &transfer, &transfer_size));
    if (transfer == NULL) goto cleanup;
    const uintptr_t retained_save_ram = gn_test_mvs_save_ram_address(destination);
    SDK_CHECK_TRUE("sdk.state.destination-save-ram-address",
                   retained_save_ram != (uintptr_t)0);
    SDK_CHECK_TRUE("sdk.state.expected-raw-frame-pcm-time",
                   state_fixture_advance_total(source, 0u, &source_cycles,
                                               &expected));
    SDK_CHECK_TRUE("sdk.state.restore-public-api",
                   state_fixture_restore(destination, transfer, transfer_size));
    SDK_CHECK_TRUE("sdk.state.save-ram-owner-address-retained",
                  retained_save_ram == gn_test_mvs_save_ram_address(destination));
    SDK_CHECK_TRUE("sdk.state.transfer-host-sentinel-retained",
                   state_fixture_guard_valid(transfer, transfer_size));
    memset(transfer, 0x96, transfer_size);
    free(transfer);
    transfer = NULL;
    SDK_CHECK_TRUE("sdk.state.restored-raw-frame-pcm-time",
                   state_fixture_advance_total(destination, 0u,
                                               &destination_cycles, &actual));
    actual.total_cycles = source_cycles;
    SDK_CHECK_TRUE("sdk.state.future-full-frame-pcm-guest-time-match",
                   state_fixture_observation_equal(&expected, &actual));
cleanup:
    if (transfer != NULL) {
        memset(transfer, 0x96, transfer_size);
        free(transfer);
    }
    gn_destroy(destination);
    gn_destroy(source);
}

static int state_fixture_section(uint8_t *state, size_t size,
                                 uint32_t wanted, size_t *out_payload,
                                 size_t *out_length) {
    if (state == NULL || size < 72u || out_payload == NULL || out_length == NULL)
        return 0;
    size_t cursor = 72u;
    while (cursor + 8u <= size) {
        const uint32_t section = state_fixture_read_u32be(state + cursor);
        const uint32_t length = state_fixture_read_u32be(state + cursor + 4u);
        cursor += 8u;
        if ((size_t)length > size - cursor) return 0;
        if (section == wanted) {
            *out_payload = cursor;
            *out_length = (size_t)length;
            return 1;
        }
        cursor += (size_t)length;
    }
    return 0;
}

static void state_fixture_write_u64be(uint8_t *bytes, uint64_t value) {
    state_fixture_write_u32be(bytes, (uint32_t)(value >> 32));
    state_fixture_write_u32be(bytes + 4u, (uint32_t)value);
}

static int state_fixture_splice_section(uint8_t *target, const uint8_t *donor,
                                        size_t size, uint32_t section) {
    size_t target_offset = 0u, target_length = 0u;
    size_t donor_offset = 0u, donor_length = 0u;
    if (!state_fixture_section(target, size, section, &target_offset,
                               &target_length) ||
        !state_fixture_section((uint8_t *)donor, size, section, &donor_offset,
                               &donor_length) || target_length != donor_length)
        return 0;
    memcpy(target + target_offset, donor + donor_offset, target_length);
    return 1;
}

static int state_fixture_nonzero(const void *bytes, size_t size) {
    const uint8_t *values = (const uint8_t *)bytes;
    for (size_t index = 0u; index < size; ++index) {
        if (values[index] != 0u) return 1;
    }
    return 0;
}

static const char *selected_control;
static int sdk_state_invalid_suite;

static void state_omission_control(const char *selector) {
    gn_instance *expected_instance = NULL;
    gn_instance *subject = NULL;
    uint8_t *expected_state = NULL;
    uint8_t *donor_state = NULL;
    size_t expected_size = 0u, donor_size = 0u;
    uint32_t section = 0u;
    const char *assertion = NULL;
    if (strcmp(selector, "cpu") == 0) {
        section = 1u;
        assertion = "sdk.state.omission.cpu.guest-output";
    } else if (strcmp(selector, "memory") == 0) {
        section = 2u;
        assertion = "sdk.state.omission.memory.raw-video";
    } else if (strcmp(selector, "board") == 0) {
        section = 3u;
        assertion = "sdk.state.omission.board.frame-time-carry";
    } else if (strcmp(selector, "sound") == 0) {
        section = 4u;
        assertion = "sdk.state.omission.sound.delivered-pcm";
    } else if (strcmp(selector, "ym2610") == 0) {
        section = 5u;
        assertion = "sdk.state.omission.ym2610.delivered-pcm";
    } else {
        (void)fprintf(stderr, "unknown omission selector: %s\n", selector);
        TEST_FAIL_MESSAGE("unknown omission selector");
        return;
    }
    SDK_CASE(assertion);
    uint64_t expected_cycles = 0u, subject_cycles = 0u;
    state_fixture_observation expected;
    state_fixture_observation actual;
    if (!state_fixture_load(&expected_instance, 0u) ||
        !state_fixture_load(&subject, 0u)) goto cleanup;
    if (!state_fixture_advance_total(expected_instance, 0u, &expected_cycles,
                                     &expected) ||
        !state_fixture_advance_total(subject, 0u, &subject_cycles, &actual) ||
        !state_fixture_capture(expected_instance, &expected_state,
                               &expected_size)) goto cleanup;
    for (unsigned index = 0u; index < 2u; ++index) {
        const uint32_t input = index == 0u ? GN_MVS_INPUT_P1_A : 0u;
        if (!state_fixture_advance_total(subject, input, &subject_cycles,
                                         &actual)) goto cleanup;
    }
    if (!state_fixture_capture(subject, &donor_state, &donor_size) ||
        donor_size != expected_size ||
        !state_fixture_splice_section(expected_state, donor_state, expected_size,
                                      section))
        goto cleanup;
    size_t payload = 0u, payload_length = 0u;
    if (section == 1u) {
        if (!state_fixture_section(expected_state, expected_size, section,
                                   &payload, &payload_length) ||
            payload_length < 68u) goto cleanup;
        /* A lost CPU continuation resumes at the public fixture reset entry. */
        state_fixture_write_u32be(expected_state + payload + 64u,
                                  UINT32_C(0x00c00100));
    } else if (section == 2u) {
        if (!state_fixture_section(expected_state, expected_size, section,
                                   &payload, &payload_length) ||
            payload_length <= (size_t)0x24000u + (size_t)0x7002u * 2u + 1u)
            goto cleanup;
        /* Recolor every active public fixture pen; pixels remain visible. */
        for (size_t pen = 0x11u; pen <= 0x18u; ++pen) {
            expected_state[payload + (size_t)0x20000u + pen * 2u] = 0u;
            expected_state[payload + (size_t)0x20000u + pen * 2u + 1u] = 0x1fu;
        }
    } else if (section == 3u) {
        if (!state_fixture_section(expected_state, expected_size, section,
                                   &payload, &payload_length) ||
            payload_length < 47u) goto cleanup;
        /* Legal nonzero frame carry forces a different next-call time budget. */
        state_fixture_write_u64be(expected_state + payload + 39u, 4096u);
    }
    if (!state_fixture_restore(subject, expected_state, expected_size) ||
        !state_fixture_advance_total(expected_instance, 0u, &expected_cycles,
                                     &expected) ||
        !state_fixture_advance_total(subject, 0u, &subject_cycles, &actual))
        goto cleanup;
    if (section == 4u || section == 5u) {
        SDK_CHECK_TRUE("sdk.state.omission.pcm-is-nonzero",
                       expected.audio_frames > 0u && actual.audio_frames > 0u &&
                       state_fixture_nonzero(expected.audio,
                           expected.audio_frames * 2u * sizeof(int16_t)) &&
                       state_fixture_nonzero(actual.audio,
                           actual.audio_frames * 2u * sizeof(int16_t)));
        SDK_CHECK_TRUE(assertion,
                       expected.audio_frames == actual.audio_frames &&
                       memcmp(expected.audio, actual.audio,
                           expected.audio_frames * 2u * sizeof(int16_t)) == 0);
    } else if (section == 3u) {
        SDK_CHECK_TRUE("sdk.state.omission.board.nonzero-time",
                       expected.result.elapsed_cycles > 0u &&
                       actual.result.elapsed_cycles > 0u);
        SDK_CHECK_TRUE(assertion,
                       expected.video.frame_cycle_carry ==
                           actual.video.frame_cycle_carry &&
                       expected.result.elapsed_cycles ==
                           actual.result.elapsed_cycles);
    } else if (section == 2u) {
        SDK_CHECK_TRUE("sdk.state.omission.video.nonzero-frames",
                       expected.result.video_pixels_produced > 0u &&
                       actual.result.video_pixels_produced > 0u &&
                       state_fixture_nonzero(expected.pixels,
                           sizeof(expected.pixels)) &&
                       state_fixture_nonzero(actual.pixels,
                           sizeof(actual.pixels)));
        SDK_CHECK_TRUE(assertion,
                       memcmp(expected.pixels, actual.pixels,
                              sizeof(expected.pixels)) == 0);
    } else {
        SDK_CHECK_TRUE("sdk.state.omission.cpu.nonzero-observations",
                       expected.result.instructions > 0u &&
                       actual.result.instructions > 0u &&
                       expected.guest_reply != 0u && actual.guest_reply != 0u);
        SDK_CHECK_TRUE(assertion,
                       expected.result.instructions ==
                           actual.result.instructions &&
                       expected.guest_reply == actual.guest_reply);
    }
cleanup:
    free(donor_state);
    free(expected_state);
    gn_destroy(subject);
    gn_destroy(expected_instance);
}

static void state_omission_control_case(void) {
    state_omission_control(selected_control);
}

static void state_fixture_repeated_restore_is_idempotent(void) {
    SDK_CASE("sdk.state.repeat.restore-after-progress");
    gn_instance *source = NULL;
    gn_instance *subject = NULL;
    uint8_t *state = NULL;
    size_t state_size = 0u;
    state_fixture_observation expected;
    state_fixture_observation actual;
    uint64_t source_cycles = 0u, subject_cycles = 0u;
    SDK_CHECK_TRUE("sdk.state.repeat.source-load", state_fixture_load(&source, 0u));
    SDK_CHECK_TRUE("sdk.state.repeat.subject-load", state_fixture_load(&subject, 0u));
    if (source == NULL || subject == NULL) goto cleanup;
    SDK_CHECK_TRUE("sdk.state.repeat.source-prefix",
                   state_fixture_advance_total(source, 0u, &source_cycles,
                                               &expected));
    SDK_CHECK_TRUE("sdk.state.repeat.subject-prefix",
                   state_fixture_advance_total(subject, 0u, &subject_cycles,
                                               &actual));
    SDK_CHECK_TRUE("sdk.state.repeat.capture", state_fixture_capture(
                       source, &state, &state_size));
    if (state == NULL) goto cleanup;
    SDK_CHECK_TRUE("sdk.state.repeat.expected", state_fixture_advance_total(
                       source, GN_MVS_INPUT_P1_A, &source_cycles, &expected));
    for (unsigned restore = 0u; restore < 3u; ++restore) {
        uint8_t *transfer = (uint8_t *)malloc(state_size);
        SDK_CHECK_TRUE("sdk.state.repeat.transfer-copy", transfer != NULL);
        if (transfer == NULL) goto cleanup;
        memcpy(transfer, state, state_size);
        SDK_CHECK_TRUE("sdk.state.repeat.restore",
                       state_fixture_restore(subject, transfer, state_size));
        memset(transfer, (int)(0x30u + restore), state_size);
        free(transfer);
        SDK_CHECK_TRUE("sdk.state.repeat.future",
                       state_fixture_advance_total(subject, GN_MVS_INPUT_P1_A,
                                                   &subject_cycles, &actual));
        actual.total_cycles = expected.total_cycles;
        SDK_CHECK_TRUE("sdk.state.repeat.full-observation",
                       state_fixture_observation_equal(&expected, &actual));
        SDK_CHECK_TRUE("sdk.state.repeat.restore-after-progress",
                       state_fixture_restore(subject, state, state_size));
    }
    uint8_t *rejected = (uint8_t *)malloc(state_size);
    SDK_CHECK_TRUE("sdk.state.repeat.rejection-buffer", rejected != NULL);
    if (rejected != NULL) {
        memcpy(rejected, state, state_size);
        rejected[68u] = 1u;
        for (unsigned attempt = 0u; attempt < 2u; ++attempt) {
            SDK_CHECK_TRUE("sdk.state.repeat.seed-source-before-rejection",
                           state_fixture_restore(source, state, state_size));
            SDK_CHECK_TRUE("sdk.state.repeat.seed-subject-before-rejection",
                           state_fixture_restore(subject, state, state_size));
            gn_state_detail_v1 detail;
            SDK_CHECK_STATUS("sdk.state.repeat.same-payload-rejected",
                             GN_STATUS_INVALID_MEDIA,
                             gn_state_restore_v1(subject, rejected, state_size,
                                                 &detail, sizeof(detail)));
            SDK_CHECK_U64("sdk.state.repeat.rejected-reserved-reason",
                          GN_STATE_REASON_RESERVED, detail.reason);
            SDK_CHECK_TRUE("sdk.state.repeat.source-after-rejection",
                           state_fixture_advance(source, GN_MVS_INPUT_P1_A,
                                                 &expected));
            SDK_CHECK_TRUE("sdk.state.repeat.subject-after-rejection",
                           state_fixture_advance(subject, GN_MVS_INPUT_P1_A,
                                                 &actual));
            actual.total_cycles = expected.total_cycles;
            SDK_CHECK_TRUE("sdk.state.repeat.rejection-preserves-future",
                           state_fixture_observation_equal(&expected, &actual));
        }
        free(rejected);
    }
    SDK_CHECK_TRUE("sdk.state.repeat.state-host-sentinel-retained",
                   state_fixture_guard_valid(state, state_size));
cleanup:
    free(state);
    gn_destroy(subject);
    gn_destroy(source);
}

typedef struct {
    gn_instance *instance;
    const uint8_t *state;
    size_t state_size;
    uint32_t input;
    uint64_t prior_cycles;
    state_fixture_observation actual;
    int passed;
} state_isolation_thread_argument;

static SDK_TEST_THREAD_RESULT SDK_TEST_THREAD_CALL state_isolation_thread(void *raw) {
    state_isolation_thread_argument *argument =
        (state_isolation_thread_argument *)raw;
    gn_state_compatibility_info_v1 compatibility;
    gn_state_detail_v1 detail;
    memset(&compatibility, 0, sizeof(compatibility));
    argument->passed = gn_state_compatibility_v1(
                           argument->instance, &compatibility,
                           sizeof(compatibility)) == GN_STATUS_OK &&
        gn_state_restore_v1(argument->instance, argument->state,
                            argument->state_size, &detail,
                            sizeof(detail)) == GN_STATUS_OK &&
        state_fixture_guard_valid(argument->state, argument->state_size) &&
        state_fixture_advance(argument->instance, argument->input,
                              &argument->actual);
    if (argument->passed != 0) {
        argument->passed = UINT64_MAX - argument->prior_cycles >=
            argument->actual.result.elapsed_cycles;
        if (argument->passed != 0)
            argument->actual.total_cycles = argument->prior_cycles +
                argument->actual.result.elapsed_cycles;
    }
    return SDK_TEST_THREAD_DONE;
}

static void state_instances_are_isolated_when_interleaved_and_concurrent(void) {
    SDK_CASE("sdk.state.isolation.distinguishable-instances");
    gn_instance *instances[3] = {NULL, NULL, NULL};
    gn_instance *reload_reference = NULL;
    uint8_t *states[3] = {NULL, NULL, NULL};
    size_t state_sizes[3] = {0u, 0u, 0u};
    state_fixture_observation *expected = NULL;
    state_isolation_thread_argument *arguments = NULL;
    sdk_test_thread threads[3];
    uintptr_t save_addresses[3] = {0u, 0u, 0u};
    unsigned started = 0u;
    uint64_t cycles[3] = {0u, 0u, 0u};
    uint8_t identities[3][32];
    unsigned ym_remainder_mask = 0u;
    static const uint32_t inputs[3] = {
        0u, GN_MVS_INPUT_P1_A, GN_MVS_INPUT_P1_A | GN_MVS_INPUT_P1_B
    };
    static const uint32_t prefix_inputs[3][6] = {
        {0u, GN_MVS_INPUT_P1_A, 0u, 0u, GN_MVS_INPUT_P1_A, 0u},
        {0u, 0u, GN_MVS_INPUT_P1_A, 0u, 0u, GN_MVS_INPUT_P1_A},
        {GN_MVS_INPUT_P1_A | GN_MVS_INPUT_P1_B, GN_MVS_INPUT_P1_B,
         0u, GN_MVS_INPUT_P1_A, GN_MVS_INPUT_P1_B, 0u}
    };
    expected = (state_fixture_observation *)calloc(3u, sizeof(*expected));
    arguments = (state_isolation_thread_argument *)calloc(3u,
                                                          sizeof(*arguments));
    SDK_CHECK_TRUE("sdk.state.isolation.observation-storage",
                   expected != NULL && arguments != NULL);
    if (expected == NULL || arguments == NULL) goto cleanup;
    for (unsigned owner = 0u; owner < 3u; ++owner) {
        SDK_CHECK_TRUE("sdk.state.isolation.load-distinct-media",
                       state_fixture_load(&instances[owner], owner));
        if (instances[owner] == NULL) goto cleanup;
        for (size_t frame = 0u; frame < 6u; ++frame) {
            SDK_CHECK_TRUE("sdk.state.isolation.input-schedule-prefix",
                           state_fixture_advance_total(instances[owner],
                               prefix_inputs[owner][frame], &cycles[owner],
                               &expected[owner]));
            ym_remainder_mask |= 1u << expected[owner].sound.ym_clock_remainder;
        }
        SDK_CHECK_TRUE("sdk.state.isolation.nonzero-sound-state",
                       expected[owner].sound.native_samples > 0u &&
                       expected[owner].sound.filter_history_digest != 0u &&
                       expected[owner].sound.timer_register_writes[0] > 0u);
        SDK_CHECK_TRUE("sdk.state.isolation.capture-owner-state",
                       state_fixture_capture(instances[owner], &states[owner],
                                             &state_sizes[owner]));
        if (states[owner] == NULL) goto cleanup;
        save_addresses[owner] = gn_test_mvs_save_ram_address(instances[owner]);
        SDK_CHECK_TRUE("sdk.state.isolation.save-ram-owner-address",
                       save_addresses[owner] != (uintptr_t)0);
        gn_state_compatibility_info_v1 compatibility;
        SDK_CHECK_STATUS("sdk.state.isolation.compatibility",
                         GN_STATUS_OK,
                         gn_state_compatibility_v1(instances[owner],
                             &compatibility, sizeof(compatibility)));
        memcpy(identities[owner], compatibility.media_identity_sha256, 32u);
    }

    /* Serial references use the same state and inputs as the independent
     * worker calls. Restore again before each thread starts. */
    for (unsigned owner = 0u; owner < 3u; ++owner) {
        SDK_CHECK_TRUE("sdk.state.isolation.serial-restore",
                       state_fixture_restore(instances[owner], states[owner],
                                              state_sizes[owner]));
        SDK_CHECK_TRUE("sdk.state.isolation.serial-reference",
                       state_fixture_advance(instances[owner], inputs[owner],
                                             &expected[owner]));
        expected[owner].total_cycles = cycles[owner] +
            expected[owner].result.elapsed_cycles;
        /* Snapshot the starting state again after the reference call. */
        SDK_CHECK_TRUE("sdk.state.isolation.rewind-owner",
                       state_fixture_restore(instances[owner], states[owner],
                                              state_sizes[owner]));
    }

    for (unsigned owner = 0u; owner < 3u; ++owner) {
        arguments[owner] = (state_isolation_thread_argument){
            instances[owner], states[owner], state_sizes[owner], inputs[owner],
            cycles[owner], {0}, 0};
        if (!sdk_test_thread_start(&threads[owner], state_isolation_thread,
                                   &arguments[owner])) break;
        ++started;
    }
    for (unsigned owner = 0u; owner < started; ++owner)
        SDK_CHECK_TRUE("sdk.state.isolation.thread-joined",
                       sdk_test_thread_join(threads[owner]));
    SDK_CHECK_U64("sdk.state.isolation.all-workers-started", 3u, started);
    for (unsigned owner = 0u; owner < 3u; ++owner) {
        SDK_CHECK_TRUE("sdk.state.isolation.thread-status", arguments[owner].passed);
        SDK_CHECK_TRUE("sdk.state.isolation.host-sentinel-retained",
                       state_fixture_guard_valid(states[owner],
                                                  state_sizes[owner]));
        SDK_CHECK_U64("sdk.state.isolation.save-ram-address-retained",
                      save_addresses[owner],
                      gn_test_mvs_save_ram_address(instances[owner]));
        SDK_CHECK_TRUE("sdk.state.isolation.serial-output-match",
                       state_fixture_observation_equal(&expected[owner],
                                                       &arguments[owner].actual));
    }
    SDK_CHECK_TRUE("sdk.state.isolation.distinct-media-identities",
                   memcmp(identities[0], identities[1], 32u) != 0 &&
                   memcmp(identities[0], identities[2], 32u) != 0 &&
                   memcmp(identities[1], identities[2], 32u) != 0);
    SDK_CHECK_TRUE("sdk.state.isolation.nonzero-ym-clock-phase",
                   (ym_remainder_mask & ~1u) != 0u);
    SDK_CHECK_STATUS("sdk.state.isolation.unload-before-reload", GN_STATUS_OK,
                     gn_unload(instances[0]));
    SDK_CHECK_TRUE("sdk.state.isolation.reload-same-owner",
                   state_fixture_reload(instances[0], 0u));
    SDK_CHECK_TRUE("sdk.state.isolation.reload-reference-load",
                   state_fixture_load(&reload_reference, 0u));
    if (reload_reference != NULL) {
        state_fixture_observation reloaded;
        state_fixture_observation fresh;
        SDK_CHECK_TRUE("sdk.state.isolation.reload-frame",
                       state_fixture_advance(instances[0], 0u, &reloaded));
        SDK_CHECK_TRUE("sdk.state.isolation.fresh-frame",
                       state_fixture_advance(reload_reference, 0u, &fresh));
        SDK_CHECK_TRUE("sdk.state.isolation.clean-reload-match",
                       state_fixture_observation_equal(&fresh, &reloaded));
    }
    gn_destroy(reload_reference);
    reload_reference = NULL;
cleanup:
    gn_destroy(reload_reference);
    for (unsigned owner = 0u; owner < 3u; ++owner) {
        free(states[owner]);
        gn_destroy(instances[owner]);
    }
    free(arguments);
    free(expected);
}

static void run_suite(const char *suite) {
    UnityBegin("tests/sdk/test_state.c");
    if (strcmp(suite, "continuation") == 0)
        RUN_TEST(state_restore_continues_full_guest_video_pcm_and_time);
    else if (strcmp(suite, "controls") == 0)
        RUN_TEST(state_restore_continues_full_guest_video_pcm_and_time);
    else if (strcmp(suite, "repeat") == 0)
        RUN_TEST(state_fixture_repeated_restore_is_idempotent);
    else if (strcmp(suite, "isolation") == 0)
        RUN_TEST(state_instances_are_isolated_when_interleaved_and_concurrent);
    else if (strcmp(suite, "hostile") == 0) {
        RUN_TEST(state_mutation_ym_offset_test);
        RUN_TEST(state_mutation_corpus_coverage_test);
        RUN_TEST(state_mutation_hostile_matrix_test);
    }
    #if defined(GLUEYNEO_STATE_MUTATION_EXECUTABLE)
    else if (strcmp(suite, "oom") == 0)
        RUN_TEST(state_mutation_oom_red_test);
    #endif
    else if (strcmp(suite, "negative-control-z80") == 0)
        RUN_TEST(state_mutation_negative_control_z80_test);
    else if (strcmp(suite, "negative-control-ym") == 0)
        RUN_TEST(state_mutation_negative_control_ym_test);
    else if (strcmp(suite, "negative-control-ym-irq-relation") == 0)
        RUN_TEST(state_mutation_negative_control_ym_irq_relation_test);
    else if (strcmp(suite, "negative-control-ym-timer-relation") == 0)
        RUN_TEST(state_mutation_negative_control_ym_timer_relation_test);
    else if (strcmp(suite, "negative-control-ym-busy-relation") == 0)
        RUN_TEST(state_mutation_negative_control_ym_busy_relation_test);
    else if (strncmp(suite, "control-", 8u) == 0) {
        selected_control = suite + 8u;
        RUN_TEST(state_omission_control_case);
    } else {
        (void)fprintf(stderr, "unknown sdk state suite: %s\n", suite);
        sdk_state_invalid_suite = 1;
        (void)UnityEnd();
        return;
    }
    const int failures = UnityEnd();
    uint64_t mutation_cases = 0u;
    uint64_t mutation_assertions = 0u;
    state_mutation_case_counts(&mutation_cases, &mutation_assertions);
    sdk_cases += mutation_cases;
    sdk_assertions += mutation_assertions;
    #if defined(GLUEYNEO_STATE_MUTATION_EXECUTABLE)
    uint64_t oom_cases = 0u;
    uint64_t oom_assertions = 0u;
    state_oom_case_counts(&oom_cases, &oom_assertions);
    sdk_cases += oom_cases;
    sdk_assertions += oom_assertions;
    #endif
    sdk_test_result("sdk-state", failures, GLUEYNEO_SOURCE_REVISION,
                    GLUEYNEO_CONFIGURATION, GLUEYNEO_COMPILER_ID,
                    GLUEYNEO_COMPILER_VERSION);
}

int main(int argc, char **argv) {
    if (argc != 2) {
        (void)fprintf(stderr, "usage: sdk_state_test <suite>\n");
        return 2;
    }
    run_suite(argv[1]);
    if (sdk_state_invalid_suite != 0) return 2;
    return Unity.TestFailures == 0 ? 0 : 1;
}
