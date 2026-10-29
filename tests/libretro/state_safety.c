/* SPDX-License-Identifier: MIT */
#if !defined(_WIN32)
#define _POSIX_C_SOURCE 200809L
#endif
#include "glueyneo/glueyneo.h"
#include "libretro.h"
#include "save_fixture.h"
#include "sdk_private.h"
#include "chips/ym2610_candidate.h"
#include "unity.h"

#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#if defined(_WIN32)
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <fcntl.h>
#include <io.h>
#else
#include <errno.h>
#include <signal.h>
#include <sys/wait.h>
#include <unistd.h>
#endif

enum {
    SAFETY_WIDTH = 320,
    SAFETY_HEIGHT = 224,
    SAFETY_SAVE_RAM_BYTES = 65536,
    SAFETY_STATE_HEADER_BYTES = 72,
    SAFETY_SECTION_HEADER_BYTES = 8,
    SAFETY_YM_SECTION = 5,
    SAFETY_CHILD_OUTPUT_LIMIT = 65536
};

#define SAFETY_PITCH ((size_t)SAFETY_WIDTH * sizeof(uint32_t))
#define SAFETY_FRAME_BYTES (SAFETY_PITCH * (size_t)SAFETY_HEIGHT)

static uint32_t captured_pixels[SAFETY_WIDTH * SAFETY_HEIGHT];
static int16_t captured_audio[GN_MVS_AUDIO_CAPACITY_FRAMES_V1 * 2u];
static size_t captured_audio_frames;
static bool captured_frame_valid;
static uint32_t sampled_input;
static unsigned video_callbacks;
static unsigned audio_callbacks;
static unsigned assertion_count;
static unsigned assertion_failures;
static const char *safety_executable_path;

#define SAFETY_CHECK(condition, label) \
    safety_check((condition) ? 1 : 0, (label), (unsigned)__LINE__)

static void safety_check(int passed, const char *label, unsigned line) {
    ++assertion_count;
    if (!passed) {
        ++assertion_failures;
        (void)fprintf(stderr, "FAIL line %u: %s\n", line, label);
    }
}

static bool environment_callback(unsigned command, void *data) {
    if (command == RETRO_ENVIRONMENT_SET_PIXEL_FORMAT && data != NULL)
        return *(enum retro_pixel_format *)data == RETRO_PIXEL_FORMAT_XRGB8888;
    if (command == RETRO_ENVIRONMENT_SET_SYSTEM_AV_INFO && data != NULL)
        return true;
    return false;
}

static void video_callback(const void *data, unsigned width, unsigned height,
                           size_t pitch) {
    ++video_callbacks;
    captured_frame_valid = data != NULL && width == SAFETY_WIDTH &&
        height == SAFETY_HEIGHT && pitch == SAFETY_PITCH;
    if (captured_frame_valid) memcpy(captured_pixels, data, SAFETY_FRAME_BYTES);
}

static void audio_callback(int16_t left, int16_t right) {
    if (captured_audio_frames < GN_MVS_AUDIO_CAPACITY_FRAMES_V1) {
        captured_audio[captured_audio_frames * 2u] = left;
        captured_audio[captured_audio_frames * 2u + 1u] = right;
        ++captured_audio_frames;
    }
    ++audio_callbacks;
}

static size_t audio_batch_callback(const int16_t *data, size_t frames) {
    if (data != NULL && frames <= GN_MVS_AUDIO_CAPACITY_FRAMES_V1) {
        memcpy(captured_audio, data, frames * 2u * sizeof(int16_t));
        captured_audio_frames = frames;
    } else {
        captured_audio_frames = 0u;
    }
    ++audio_callbacks;
    return frames;
}

static void input_poll_callback(void) {}

static int16_t input_state_callback(unsigned port, unsigned device,
                                    unsigned index, unsigned id) {
    if (port != 0u || device != RETRO_DEVICE_JOYPAD || index != 0u)
        return 0;
    if (id == RETRO_DEVICE_ID_JOYPAD_B &&
        (sampled_input & GN_MVS_INPUT_P1_A) != 0u)
        return 1;
    if (id == RETRO_DEVICE_ID_JOYPAD_A &&
        (sampled_input & GN_MVS_INPUT_P1_B) != 0u)
        return 1;
    if (id == RETRO_DEVICE_ID_JOYPAD_RIGHT &&
        (sampled_input & GN_MVS_INPUT_P1_RIGHT) != 0u)
        return 1;
    return 0;
}

static uint32_t read_u32be(const uint8_t *bytes) {
    return ((uint32_t)bytes[0] << 24) | ((uint32_t)bytes[1] << 16) |
           ((uint32_t)bytes[2] << 8) | (uint32_t)bytes[3];
}

static void write_u32be(uint8_t *bytes, uint32_t value) {
    bytes[0] = (uint8_t)(value >> 24);
    bytes[1] = (uint8_t)(value >> 16);
    bytes[2] = (uint8_t)(value >> 8);
    bytes[3] = (uint8_t)value;
}

static int mutate_unused_bios_byte(uint8_t *bundle, size_t bundle_size) {
    if (bundle == NULL || bundle_size < 16u) return 0;
    const uint32_t count = read_u32be(bundle + 12u);
    size_t cursor = 16u;
    for (uint32_t index = 0u; index < count; ++index) {
        if (cursor > bundle_size || bundle_size - cursor < 12u) return 0;
        const uint32_t role = read_u32be(bundle + cursor);
        const uint32_t reserved = read_u32be(bundle + cursor + 4u);
        const uint32_t extent = read_u32be(bundle + cursor + 8u);
        cursor += 12u;
        if (reserved != 0u || (size_t)extent > bundle_size - cursor) return 0;
        if (role == GN_MVS_REGION_BIOS) {
            if (extent <= 0x800u) return 0;
            bundle[cursor + 0x800u] ^= UINT8_C(0x5a);
            return 1;
        }
        cursor += (size_t)extent;
    }
    return 0;
}

static bool load_native_from_bundle(const uint8_t *bundle, size_t bundle_size,
                                    gn_instance **out_instance) {
    if (bundle == NULL || out_instance == NULL) return false;
    *out_instance = NULL;
    gn_mvs_manifest_v3 manifest;
    if (!save_fixture_manifest_from_bundle(bundle, bundle_size, &manifest) ||
        gn_create(out_instance) != GN_STATUS_OK)
        return false;
    if (gn_load_mvs_v3(*out_instance, &manifest) == GN_STATUS_OK) return true;
    gn_destroy(*out_instance);
    *out_instance = NULL;
    return false;
}

static int find_state_section(const uint8_t *state, size_t size,
                              uint32_t wanted, size_t *out_offset,
                              size_t *out_length) {
    if (state == NULL || out_offset == NULL || out_length == NULL ||
        size < SAFETY_STATE_HEADER_BYTES)
        return 0;
    size_t cursor = SAFETY_STATE_HEADER_BYTES;
    for (size_t index = 0u; index < 5u; ++index) {
        if (cursor > size || size - cursor < SAFETY_SECTION_HEADER_BYTES)
            return 0;
        const uint32_t section = read_u32be(state + cursor);
        const uint32_t length = read_u32be(state + cursor + 4u);
        cursor += SAFETY_SECTION_HEADER_BYTES;
        if ((size_t)length > size - cursor) return 0;
        if (section == wanted) {
            *out_offset = cursor;
            *out_length = (size_t)length;
            return 1;
        }
        cursor += (size_t)length;
    }
    return 0;
}

static bool initialize_pair_variant(uint8_t **out_bundle,
                                    size_t *out_bundle_size,
                                    gn_instance **out_witness,
                                    bool variant_b) {
    if (out_bundle == NULL || out_bundle_size == NULL || out_witness == NULL)
        return false;
    *out_bundle = NULL;
    *out_bundle_size = 0u;
    *out_witness = NULL;
    const size_t bundle_size = public_save_guest_size();
    if (bundle_size == 0u) return false;
    uint8_t *bundle = (uint8_t *)malloc(bundle_size);
    if (bundle == NULL || !public_save_guest_build(bundle, bundle_size)) {
        free(bundle);
        return false;
    }
    if (variant_b && !mutate_unused_bios_byte(bundle, bundle_size)) {
        free(bundle);
        return false;
    }

    retro_set_environment(environment_callback);
    retro_set_video_refresh(video_callback);
    retro_set_audio_sample(audio_callback);
    retro_set_audio_sample_batch(audio_batch_callback);
    retro_set_input_poll(input_poll_callback);
    retro_set_input_state(input_state_callback);
    retro_init();
    const struct retro_game_info game = {NULL, bundle, bundle_size, NULL};
    if (!retro_load_game(&game) ||
        !load_native_from_bundle(bundle, bundle_size, out_witness)) {
        retro_deinit();
        gn_destroy(*out_witness);
        *out_witness = NULL;
        free(bundle);
        return false;
    }

    *out_bundle = bundle;
    *out_bundle_size = bundle_size;
    return true;
}

static bool initialize_pair(uint8_t **out_bundle, size_t *out_bundle_size,
                            gn_instance **out_witness) {
    return initialize_pair_variant(out_bundle, out_bundle_size, out_witness,
                                    false);
}

static void destroy_pair(uint8_t *bundle, gn_instance *witness) {
    /* Stop every SAVE_RAM access before the adapter unload releases its owner. */
    retro_deinit();
    gn_destroy(witness);
    free(bundle);
}

static uint8_t *capture_adapter_state(size_t expected_size) {
    const size_t size = retro_serialize_size();
    if (size == 0u || size != expected_size) return NULL;
    uint8_t *state = (uint8_t *)malloc(size);
    if (state == NULL || !retro_serialize(state, size)) {
        free(state);
        return NULL;
    }
    return state;
}

static int state_pair_equal(gn_instance *witness, size_t capacity,
                            const char *label) {
    uint8_t *adapter_state = capture_adapter_state(capacity);
    uint8_t *native_state = NULL;
    size_t native_size = 0u;
    const int native_captured = save_fixture_capture(
        witness, &native_state, &native_size);
    const int equal = adapter_state != NULL && native_captured &&
        native_size == capacity && memcmp(adapter_state, native_state,
                                           capacity) == 0;
    SAFETY_CHECK(equal, label);
    free(adapter_state);
    free(native_state);
    return equal;
}

static int run_adapter_and_witness(gn_instance *witness, uint32_t input_mask) {
    sampled_input = input_mask;
    captured_audio_frames = 0u;
    captured_frame_valid = false;
    memset(captured_pixels, 0, sizeof(captured_pixels));
    memset(captured_audio, 0, sizeof(captured_audio));
    const unsigned old_video_callbacks = video_callbacks;
    const unsigned old_audio_callbacks = audio_callbacks;
    retro_run();
    const unsigned adapter_video_callbacks = video_callbacks - old_video_callbacks;
    const unsigned adapter_audio_callbacks = audio_callbacks - old_audio_callbacks;

    uint32_t native_pixels[SAFETY_WIDTH * SAFETY_HEIGHT];
    int16_t native_audio[GN_MVS_AUDIO_CAPACITY_FRAMES_V1 * 2u];
    memset(native_pixels, 0, sizeof(native_pixels));
    memset(native_audio, 0, sizeof(native_audio));
    const gn_mvs_frame_request_v1 request = {
        GN_MVS_FRAME_REQUEST_V1_VERSION, input_mask, GN_PIXEL_XRGB8888,
        SAFETY_WIDTH, SAFETY_HEIGHT, SAFETY_PITCH,
        (uint8_t *)native_pixels, sizeof(native_pixels), native_audio,
        GN_MVS_AUDIO_CAPACITY_FRAMES_V1
    };
    gn_mvs_frame_result_v1 result;
    memset(&result, 0, sizeof(result));
    const gn_status status = gn_mvs_advance_frame_v1(
        witness, &request, sizeof(request), &result, sizeof(result));
    SAFETY_CHECK(status == GN_STATUS_OK, "native witness advances the same frame");
    if (status != GN_STATUS_OK) return 0;
    SAFETY_CHECK(adapter_video_callbacks == 1u && captured_frame_valid,
                 "adapter submits one valid raw frame");
    SAFETY_CHECK(adapter_audio_callbacks == 1u,
                 "adapter submits one exact core audio batch");
    SAFETY_CHECK(result.reason == GN_RUN_BUDGET && result.elapsed_cycles > 0u,
                 "native witness reports deterministic completed-frame cycles");
    SAFETY_CHECK(memcmp(captured_pixels, native_pixels,
                        sizeof(native_pixels)) == 0,
                 "adapter raw pixels match the native witness");
    SAFETY_CHECK(captured_audio_frames == result.audio_frames_delivered &&
                     result.audio_frames_generated ==
                         result.audio_frames_delivered &&
                     memcmp(captured_audio, native_audio,
                            captured_audio_frames * 2u * sizeof(int16_t)) == 0,
                 "adapter PCM matches the native witness byte-for-byte");
    return 1;
}

static int check_pair_loaded(gn_instance *witness, size_t *out_capacity,
                             uint8_t **out_sram, size_t *out_sram_size) {
    size_t native_capacity = 0u;
    uint8_t *sram = (uint8_t *)retro_get_memory_data(RETRO_MEMORY_SAVE_RAM);
    const size_t sram_size = retro_get_memory_size(RETRO_MEMORY_SAVE_RAM);
    const gn_status capacity_status = gn_state_capacity_v1(
        witness, &native_capacity);
    const bool valid = retro_serialize_size() > 0u &&
        retro_serialize_size() == native_capacity &&
        capacity_status == GN_STATUS_OK && sram != NULL &&
        sram_size == SAFETY_SAVE_RAM_BYTES;
    SAFETY_CHECK(valid,
                 "adapter and independent witness load the same bounded MVS content");
    if (!valid) return 0;
    *out_capacity = native_capacity;
    *out_sram = sram;
    *out_sram_size = sram_size;
    return 1;
}

static void state_rejection_and_continuation(void) {
    uint8_t *bundle = NULL;
    size_t bundle_size = 0u;
    gn_instance *witness = NULL;
    uint8_t *valid_state = NULL;
    uint8_t *corrupt_state = NULL;
    uint8_t *sram_before = NULL;
    uint8_t *retained_sram = NULL;
    size_t capacity = 0u;
    size_t sram_size = 0u;
    size_t ym_offset = 0u;
    size_t ym_length = 0u;
    const bool loaded = initialize_pair(&bundle, &bundle_size, &witness);
    SAFETY_CHECK(loaded, "original save guest loads in adapter and native witness");
    if (!loaded) goto cleanup;
    if (!check_pair_loaded(witness, &capacity, &retained_sram, &sram_size))
        goto cleanup;

    SAFETY_CHECK(run_adapter_and_witness(witness, GN_MVS_INPUT_P1_A),
                 "guest A establishes a matched completed-call boundary");
    valid_state = capture_adapter_state(capacity);
    SAFETY_CHECK(valid_state != NULL,
                 "adapter captures a valid state before nested corruption");
    if (valid_state == NULL) goto cleanup;
    SAFETY_CHECK(state_pair_equal(witness, capacity,
                                  "adapter and witness baseline bytes match"),
                 "independent witness has the same baseline state");
    corrupt_state = (uint8_t *)malloc(capacity);
    sram_before = (uint8_t *)malloc(sram_size);
    SAFETY_CHECK(corrupt_state != NULL && sram_before != NULL,
                 "bounded corruption and retained-memory snapshots allocate");
    if (corrupt_state == NULL || sram_before == NULL) goto cleanup;
    memcpy(corrupt_state, valid_state, capacity);
    memcpy(sram_before, retained_sram, sram_size);

    const int located = find_state_section(corrupt_state, capacity,
        SAFETY_YM_SECTION, &ym_offset, &ym_length);
    SAFETY_CHECK(located && ym_length > 0u,
                 "valid GNST mutation locates the nested YM2610 payload");
    if (!located || ym_length == 0u) goto cleanup;
    ym2610_candidate_state_detail nested_detail;
    memset(&nested_detail, 0, sizeof(nested_detail));
    const ym2610_candidate_status valid_nested =
        ym2610_candidate_state_validate(corrupt_state + ym_offset,
                                        ym_length, &nested_detail);
    SAFETY_CHECK(valid_nested == YM2610_CANDIDATE_OK,
                 "unmodified nested YM2610 payload validates");
    corrupt_state[ym_offset] ^= 1u;
    memset(&nested_detail, 0, sizeof(nested_detail));
    const ym2610_candidate_status invalid_nested =
        ym2610_candidate_state_validate(corrupt_state + ym_offset,
                                        ym_length, &nested_detail);
    SAFETY_CHECK(invalid_nested == YM2610_CANDIDATE_INVALID_ARGUMENT &&
                     nested_detail.reason ==
                         YM2610_CANDIDATE_STATE_REASON_MAGIC,
                 "mutated state reaches the nested validator's magic rejection");

    SAFETY_CHECK(!retro_unserialize(corrupt_state, capacity),
                 "libretro callback rejects the real nested-invalid GNST payload");
    SAFETY_CHECK(retro_get_memory_data(RETRO_MEMORY_SAVE_RAM) == retained_sram &&
                     retro_get_memory_size(RETRO_MEMORY_SAVE_RAM) == sram_size,
                 "rejected restore retains the original SRAM pointer and extent");
    SAFETY_CHECK(memcmp(retained_sram, sram_before, sram_size) == 0,
                 "rejected restore leaves all retained SRAM bytes unchanged");
    SAFETY_CHECK(state_pair_equal(witness, capacity,
                                  "rejected restore leaves guest state and cycles unchanged"),
                 "rejected adapter and uninterrupted witness remain byte-identical");

    SAFETY_CHECK(run_adapter_and_witness(witness, 0u),
                 "both machines continue after nested restore rejection");
    SAFETY_CHECK(state_pair_equal(witness, capacity,
                                  "future guest, raw frame, PCM, and GNST timing match"),
                 "post-rejection continuation matches the independent witness");
    SAFETY_CHECK(retro_get_memory_data(RETRO_MEMORY_SAVE_RAM) == retained_sram &&
                     retro_get_memory_size(RETRO_MEMORY_SAVE_RAM) == sram_size,
                 "original frontend pointer and extent remain available after continuation");

cleanup:
    destroy_pair(bundle, witness);
    free(sram_before);
    free(corrupt_state);
    free(valid_state);
    TEST_ASSERT_EQUAL_MESSAGE(0u, assertion_failures,
                              "state rejection safety assertions pass");
}

static void retained_pointer_success_rejection_and_quiescence(void) {
    uint8_t *bundle = NULL;
    size_t bundle_size = 0u;
    gn_instance *witness = NULL;
    uint8_t *valid_state = NULL;
    uint8_t *corrupt_state = NULL;
    uint8_t *saved_sram = NULL;
    uint8_t *retained_sram = NULL;
    size_t capacity = 0u;
    size_t sram_size = 0u;
    size_t ym_offset = 0u;
    size_t ym_length = 0u;
    const bool loaded = initialize_pair(&bundle, &bundle_size, &witness);
    SAFETY_CHECK(loaded, "retention scenario loads original public guest content");
    if (!loaded) goto cleanup;
    if (!check_pair_loaded(witness, &capacity, &retained_sram, &sram_size))
        goto cleanup;

    SAFETY_CHECK(run_adapter_and_witness(witness, GN_MVS_INPUT_P1_A),
                 "retention scenario executes guest A before capture");
    valid_state = capture_adapter_state(capacity);
    saved_sram = (uint8_t *)malloc(sram_size);
    SAFETY_CHECK(valid_state != NULL && saved_sram != NULL,
                 "state and original SRAM snapshots fit their fixed bounds");
    if (valid_state == NULL || saved_sram == NULL) goto cleanup;
    memcpy(saved_sram, retained_sram, sram_size);
    SAFETY_CHECK(state_pair_equal(witness, capacity,
                                  "retention baseline matches native witness"),
                 "independent witness remains aligned with retained baseline");

    retained_sram[0x4321u] ^= UINT8_C(0x5a);
    SAFETY_CHECK(retro_get_memory_data(RETRO_MEMORY_SAVE_RAM) == retained_sram &&
                     retained_sram[0x4321u] ==
                         (uint8_t)(saved_sram[0x4321u] ^ UINT8_C(0x5a)),
                 "quiescent frontend write remains readable through its saved pointer");
    uint8_t *native_sram = NULL;
    size_t native_sram_size = 0u;
    SAFETY_CHECK(gn_private_mvs_save_ram_view(witness, &native_sram,
                                               &native_sram_size) == GN_STATUS_OK &&
                     native_sram != NULL && native_sram_size == sram_size,
                 "native witness exposes the same modeled SRAM extent");
    if (native_sram != NULL && native_sram_size == sram_size)
        native_sram[0x4321u] ^= UINT8_C(0x5a);

    SAFETY_CHECK(retro_unserialize(valid_state, capacity),
                 "successful callback restore applies captured historical state");
    SAFETY_CHECK(gn_state_restore_v1(witness, valid_state, capacity, NULL, 0u) ==
                     GN_STATUS_OK,
                 "native witness applies the same successful restore");
    SAFETY_CHECK(retro_get_memory_data(RETRO_MEMORY_SAVE_RAM) == retained_sram &&
                     retro_get_memory_size(RETRO_MEMORY_SAVE_RAM) == sram_size,
                 "successful restore preserves the original pointer and extent");
    SAFETY_CHECK(memcmp(retained_sram, saved_sram, sram_size) == 0,
                 "successful historical restore updates the retained allocation in place");

    for (unsigned repeat = 0u; repeat < 2u; ++repeat) {
        SAFETY_CHECK(run_adapter_and_witness(witness, 0u),
                     "repeated restore trial first advances both guest instances");
        SAFETY_CHECK(retro_unserialize(valid_state, capacity) &&
                         gn_state_restore_v1(witness, valid_state, capacity,
                                             NULL, 0u) == GN_STATUS_OK,
                     "repeated callback restore reapplies the same valid state");
        SAFETY_CHECK(retro_get_memory_data(RETRO_MEMORY_SAVE_RAM) == retained_sram &&
                         retro_get_memory_size(RETRO_MEMORY_SAVE_RAM) == sram_size &&
                         memcmp(retained_sram, saved_sram, sram_size) == 0,
                     "repeated restore retains the original pointer and full SRAM bytes");
        (void)state_pair_equal(witness, capacity,
                               "repeated successful restore remains byte-identical");
    }

    corrupt_state = (uint8_t *)malloc(capacity);
    SAFETY_CHECK(corrupt_state != NULL,
                 "rejection payload stays within the loaded state capacity");
    if (corrupt_state == NULL) goto cleanup;
    memcpy(corrupt_state, valid_state, capacity);
    const int located = find_state_section(corrupt_state, capacity,
        SAFETY_YM_SECTION, &ym_offset, &ym_length);
    SAFETY_CHECK(located && ym_length > 0u,
                 "retention rejection locates nested YM2610 bytes");
    if (!located || ym_length == 0u) goto cleanup;
    corrupt_state[ym_offset] ^= 1u;
    SAFETY_CHECK(!retro_unserialize(corrupt_state, capacity),
                 "rejected callback restore is exercised through the adapter");
    SAFETY_CHECK(retro_get_memory_data(RETRO_MEMORY_SAVE_RAM) == retained_sram &&
                     retro_get_memory_size(RETRO_MEMORY_SAVE_RAM) == sram_size,
                 "rejected restore continues to retain the original pointer extent");
    SAFETY_CHECK(memcmp(retained_sram, saved_sram, sram_size) == 0,
                 "rejected restore does not replace or rewrite retained backing");
    SAFETY_CHECK(state_pair_equal(witness, capacity,
                                  "accepted and rejected restore preserve usable state"),
                 "continued adapter and independent witness remain aligned");
    SAFETY_CHECK(run_adapter_and_witness(witness, 0u),
                 "retained pointer remains usable across restore and rejection");
    SAFETY_CHECK(state_pair_equal(witness, capacity,
                                  "retained-pointer continuation matches native output"),
                 "guest, raw frame, exact PCM, and serialized timing still match");
    retained_sram[0x1234u] ^= UINT8_C(0xa5);
    SAFETY_CHECK(retained_sram[0x1234u] ==
                     (uint8_t)(saved_sram[0x1234u] ^ UINT8_C(0xa5)) &&
                     retro_get_memory_data(RETRO_MEMORY_SAVE_RAM) == retained_sram,
                 "same saved pointer remains writable at the quiescent test seam");

cleanup:
    destroy_pair(bundle, witness);
    free(corrupt_state);
    free(saved_sram);
    free(valid_state);
    TEST_ASSERT_EQUAL_MESSAGE(0u, assertion_failures,
                              "retained-memory safety assertions pass");
}

typedef struct {
    const void *bytes;
    size_t size;
    bool accepted;
} callback_restore_attempt;

static int invoke_callback_restore(void *raw) {
    callback_restore_attempt *attempt = (callback_restore_attempt *)raw;
    attempt->accepted = retro_unserialize(attempt->bytes, attempt->size);
    return attempt->accepted ? 1 : 0;
}

static bool restore_both_to_state(gn_instance *witness, const uint8_t *state,
                                  size_t capacity) {
    const bool adapter_ok = retro_unserialize(state, capacity);
    const gn_status witness_status = gn_state_restore_v1(
        witness, state, capacity, NULL, 0u);
    SAFETY_CHECK(adapter_ok, "adapter returns to the exact successful baseline");
    SAFETY_CHECK(witness_status == GN_STATUS_OK,
                 "independent witness returns to the same successful baseline");
    return adapter_ok && witness_status == GN_STATUS_OK;
}

static void rejected_callback_input_preserves_live_state(void) {
    uint8_t *bundle = NULL;
    size_t bundle_size = 0u;
    gn_instance *witness = NULL;
    uint8_t *baseline = NULL;
    uint8_t *mutated = NULL;
    uint8_t *sram_before = NULL;
    uint8_t *serialized = NULL;
    size_t capacity = 0u;
    size_t sram_size = 0u;
    uint8_t *retained_sram = NULL;
    const bool loaded = initialize_pair(&bundle, &bundle_size, &witness);
    SAFETY_CHECK(loaded, "rejection matrix loads an adapter and witness");
    if (!loaded) goto cleanup;
    if (!check_pair_loaded(witness, &capacity, &retained_sram, &sram_size))
        goto cleanup;
    SAFETY_CHECK(run_adapter_and_witness(witness, GN_MVS_INPUT_P1_A),
                 "rejection matrix starts from matched guest execution");
    baseline = capture_adapter_state(capacity);
    mutated = (uint8_t *)malloc(capacity + 1u);
    sram_before = (uint8_t *)malloc(sram_size);
    serialized = (uint8_t *)malloc(capacity + 1u);
    SAFETY_CHECK(baseline != NULL && mutated != NULL && sram_before != NULL &&
                     serialized != NULL,
                 "all malformed-input buffers fit their checked bounds");
    if (baseline == NULL || mutated == NULL || sram_before == NULL ||
        serialized == NULL)
        goto cleanup;
    memcpy(sram_before, retained_sram, sram_size);

    memset(serialized, 0x6du, capacity + 1u);
    SAFETY_CHECK(retro_serialize(serialized, capacity + 1u),
                 "capture accepts a sufficiently large valid host buffer");
    SAFETY_CHECK(serialized[capacity] == 0x6du,
                 "capture writes exactly the advertised cached capacity");
    uint8_t short_buffer[16];
    memset(short_buffer, 0x37, sizeof(short_buffer));
    SAFETY_CHECK(!retro_serialize(NULL, capacity),
                 "capture rejects a null callback buffer");
    SAFETY_CHECK(!retro_serialize(short_buffer, sizeof(short_buffer)) &&
                     short_buffer[0] == 0x37u &&
                     short_buffer[sizeof(short_buffer) - 1u] == 0x37u,
                 "capture rejects undersized valid host storage without writing");

#define CHECK_REJECTED_INPUT(bytes_, size_, label_) do { \
    SAFETY_CHECK(!retro_unserialize((bytes_), (size_)), (label_)); \
    SAFETY_CHECK(retro_get_memory_data(RETRO_MEMORY_SAVE_RAM) == retained_sram && \
                     retro_get_memory_size(RETRO_MEMORY_SAVE_RAM) == sram_size, \
                 "rejected callback input preserves the live SAVE_RAM view"); \
    SAFETY_CHECK(memcmp(retained_sram, sram_before, sram_size) == 0, \
                 "rejected callback input preserves all SRAM bytes"); \
    (void)state_pair_equal(witness, capacity, \
                           "rejected callback input preserves serialized guest state"); \
} while (0)

    CHECK_REJECTED_INPUT(NULL, capacity,
                         "adapter rejects null state input before reading");
    CHECK_REJECTED_INPUT(baseline, 0u,
                         "adapter rejects empty state input");
    CHECK_REJECTED_INPUT(baseline, capacity - 1u,
                         "adapter rejects truncated exact-format input");
    memcpy(mutated, baseline, capacity);
    mutated[capacity] = 0xa5u;
    CHECK_REJECTED_INPUT(mutated, capacity + 1u,
                         "adapter rejects trailing bytes after the exact envelope");

    static const struct {
        size_t offset;
        uint32_t value;
        const char *label;
    } incompatible[] = {
        {16u, UINT32_C(0xffffffff), "adapter rejects unknown state format"},
        {20u, UINT32_C(0xffffffff), "adapter rejects incompatible replay ID"},
        {24u, UINT32_C(0xffffffff), "adapter rejects incompatible profile ID"},
        {28u, UINT32_C(0xffffffff), "adapter rejects incompatible configuration ID"}
    };
    for (size_t index = 0u; index < sizeof(incompatible) / sizeof(incompatible[0]);
         ++index) {
        memcpy(mutated, baseline, capacity);
        write_u32be(mutated + incompatible[index].offset,
                    incompatible[index].value);
        CHECK_REJECTED_INPUT(mutated, capacity, incompatible[index].label);
    }
    memcpy(mutated, baseline, capacity);
    mutated[32u] ^= 1u;
    CHECK_REJECTED_INPUT(mutated, capacity,
                         "adapter rejects a foreign media identity");

    SAFETY_CHECK(!retro_unserialize(retained_sram, sram_size),
                 "adapter rejects its live SAVE_RAM view as a short state buffer");
    SAFETY_CHECK(!retro_serialize(retained_sram, sram_size),
                 "adapter rejects its live SAVE_RAM view as a short capture buffer");
    SAFETY_CHECK(memcmp(retained_sram, sram_before, sram_size) == 0,
                 "short alias callbacks leave the real retained storage untouched");
    (void)state_pair_equal(witness, capacity,
                           "all exact-length and compatibility rejects preserve state");
#undef CHECK_REJECTED_INPUT

cleanup:
    destroy_pair(bundle, witness);
    free(serialized);
    free(sram_before);
    free(mutated);
    free(baseline);
    TEST_ASSERT_EQUAL_MESSAGE(0u, assertion_failures,
                              "callback input rejection assertions pass");
}

static void callback_restore_rejects_each_reachable_allocation_failure(void) {
    uint8_t *bundle = NULL;
    size_t bundle_size = 0u;
    gn_instance *witness = NULL;
    gn_instance *adapter_instance = NULL;
    uint8_t *baseline = NULL;
    uint8_t *sram_before = NULL;
    uint8_t *retained_sram = NULL;
    size_t capacity = 0u;
    size_t sram_size = 0u;
    size_t c_attempted = 0u;
    size_t c_reached = 0u;
    size_t ym_reached = 0u;
    const bool loaded = initialize_pair(&bundle, &bundle_size, &witness);
    SAFETY_CHECK(loaded, "allocation matrix loads the real adapter callback");
    if (!loaded) goto cleanup;
    if (!check_pair_loaded(witness, &capacity, &retained_sram, &sram_size))
        goto cleanup;
    adapter_instance = gn_test_libretro_instance();
    SAFETY_CHECK(adapter_instance != NULL,
                 "test-only adapter handle exposes its real native instance");
    if (adapter_instance == NULL) goto cleanup;
    SAFETY_CHECK(run_adapter_and_witness(witness, GN_MVS_INPUT_P1_A),
                 "allocation matrix begins at matched guest state");
    baseline = capture_adapter_state(capacity);
    sram_before = (uint8_t *)malloc(sram_size);
    SAFETY_CHECK(baseline != NULL && sram_before != NULL,
                 "allocation matrix snapshots use bounded host buffers");
    if (baseline == NULL || sram_before == NULL) goto cleanup;
    memcpy(sram_before, retained_sram, sram_size);

    gn_test_state_failpoint_info c_info;
    memset(&c_info, 0, sizeof(c_info));
    SAFETY_CHECK(gn_test_state_failpoint_arm(adapter_instance, 0u) ==
                     GN_STATUS_OK,
                 "C staging measurement arms the target instance");
    callback_restore_attempt attempt = {baseline, capacity, false};
    int operation_result = -1;
    size_t ym_points = 0u;
    size_t ym_high_water = 0u;
    size_t ym_bytes = 0u;
    int64_t ym_lifetime = 0;
    uint32_t ym_failed_site = 0u;
    SAFETY_CHECK(ym2610_candidate_test_invoke_with_failpoint(
                     invoke_callback_restore, &attempt, SIZE_MAX,
                     &operation_result, &ym_points, &ym_lifetime,
                     &ym_bytes, &ym_high_water, &ym_failed_site) ==
                     YM2610_CANDIDATE_OK,
                 "allocation measurement reaches the real restore callback");
    SAFETY_CHECK(operation_result == 1 && attempt.accepted,
                 "measurement succeeds when no YM failure is injected");
    SAFETY_CHECK(gn_test_state_failpoint_disarm(adapter_instance) ==
                     GN_STATUS_OK &&
                     gn_test_state_failpoint_read(adapter_instance, &c_info) ==
                     GN_STATUS_OK,
                 "C failpoint measurement disarms and reports actual attempts");
    c_attempted = c_info.attempts;
    SAFETY_CHECK(c_attempted > 0u && c_attempted < 64u,
                 "restore exposes a bounded nonempty set of C allocation sites");
    SAFETY_CHECK(ym_points > 0u && ym_points < 1024u && ym_bytes > 0u &&
                     ym_high_water > 0u,
                 "nested YM staging exposes bounded reached allocation points");
    const size_t measured_ym_points = ym_points;
    (void)restore_both_to_state(witness, baseline, capacity);

    for (size_t fail_at = 1u; fail_at <= c_attempted; ++fail_at) {
        SAFETY_CHECK(restore_both_to_state(witness, baseline, capacity),
                     "C failure trial starts from the identical valid state");
        SAFETY_CHECK(gn_test_state_failpoint_arm(adapter_instance, fail_at) ==
                         GN_STATUS_OK,
                     "C failure trial arms one measured allocation site");
        attempt = (callback_restore_attempt){baseline, capacity, true};
        operation_result = -1;
        ym_points = 0u;
        ym_lifetime = 0;
        ym_bytes = 0u;
        ym_high_water = 0u;
        ym_failed_site = 0u;
        SAFETY_CHECK(ym2610_candidate_test_invoke_with_failpoint(
                         invoke_callback_restore, &attempt, SIZE_MAX,
                         &operation_result, &ym_points, &ym_lifetime,
                         &ym_bytes, &ym_high_water, &ym_failed_site) ==
                         YM2610_CANDIDATE_OK,
                     "C failpoint reaches the real libretro restore callback");
        SAFETY_CHECK(!attempt.accepted && operation_result == 0,
                     "callback rejects each injected C allocation failure");
        SAFETY_CHECK(gn_test_state_failpoint_disarm(adapter_instance) ==
                         GN_STATUS_OK &&
                         gn_test_state_failpoint_read(adapter_instance,
                                                      &c_info) == GN_STATUS_OK,
                     "C failure trial disarms and reads actual attempts");
        SAFETY_CHECK(c_info.attempts == fail_at &&
                         c_info.failed_site == fail_at,
                     "each counted C failure reaches its intended allocation");
        SAFETY_CHECK(c_info.allocations == c_info.frees &&
                         c_info.live_bytes == 0u,
                     "failed C staging unwinds every temporary allocation");
        if (c_info.failed_site == fail_at) ++c_reached;
        SAFETY_CHECK(retro_serialize_size() == capacity &&
                         retro_get_memory_data(RETRO_MEMORY_SAVE_RAM) ==
                             retained_sram &&
                         memcmp(retained_sram, sram_before, sram_size) == 0,
                     "C allocation rejection retains cached size and SRAM view");
        (void)state_pair_equal(witness, capacity,
                               "C OOM rejection leaves machine bytes unchanged");
        SAFETY_CHECK(run_adapter_and_witness(witness, 0u),
                     "C OOM target continues against uninterrupted witness");
        (void)state_pair_equal(witness, capacity,
                               "C OOM continuation has identical guest timing");
    }

    for (size_t fail_at = 0u; fail_at < measured_ym_points; ++fail_at) {
        SAFETY_CHECK(restore_both_to_state(witness, baseline, capacity),
                     "YM failure trial starts from the identical valid state");
        SAFETY_CHECK(gn_test_state_failpoint_arm(adapter_instance, 0u) ==
                         GN_STATUS_OK,
                     "YM failure trial enables C reached-attempt measurement");
        attempt = (callback_restore_attempt){baseline, capacity, true};
        operation_result = -1;
        ym_points = 0u;
        ym_lifetime = 0;
        ym_bytes = 0u;
        ym_high_water = 0u;
        ym_failed_site = 0u;
        SAFETY_CHECK(ym2610_candidate_test_invoke_with_failpoint(
                         invoke_callback_restore, &attempt, fail_at,
                         &operation_result, &ym_points, &ym_lifetime,
                         &ym_bytes, &ym_high_water, &ym_failed_site) ==
                         YM2610_CANDIDATE_OK,
                     "YM failpoint reaches the real libretro restore callback");
        SAFETY_CHECK(!attempt.accepted && operation_result == 0,
                     "callback rejects each injected YM construction failure");
        SAFETY_CHECK(ym_points == fail_at + 1u && ym_failed_site != 0u,
                     "each counted YM failure reaches the intended constructor");
        SAFETY_CHECK(gn_test_state_failpoint_disarm(adapter_instance) ==
                         GN_STATUS_OK &&
                         gn_test_state_failpoint_read(adapter_instance,
                                                      &c_info) == GN_STATUS_OK,
                     "YM failure trial disarms and reads C staging attempts");
        SAFETY_CHECK(c_info.attempts > 0u && c_info.failed_site == 0u,
                     "YM rejection also completes its C staging sites safely");
        if (ym_points == fail_at + 1u && ym_failed_site != 0u) ++ym_reached;
        SAFETY_CHECK(retro_serialize_size() == capacity &&
                         retro_get_memory_data(RETRO_MEMORY_SAVE_RAM) ==
                             retained_sram &&
                         memcmp(retained_sram, sram_before, sram_size) == 0,
                     "YM allocation rejection retains cached size and SRAM view");
        (void)state_pair_equal(witness, capacity,
                               "YM OOM rejection leaves machine bytes unchanged");
        SAFETY_CHECK(run_adapter_and_witness(witness, 0u),
                     "YM OOM target continues against uninterrupted witness");
        (void)state_pair_equal(witness, capacity,
                               "YM OOM continuation has identical guest timing");
    }
    SAFETY_CHECK(c_reached == c_attempted && ym_reached == measured_ym_points,
                 "every measured C and YM allocation failpoint was reached");
    (void)printf("LIBRETRO_MVS_OOM_COUNTS c_attempted=%zu c_reached=%zu "
                 "ym_attempted=%zu ym_reached=%zu\n",
                 c_attempted, c_reached, measured_ym_points, ym_reached);
    SAFETY_CHECK(restore_both_to_state(witness, baseline, capacity),
                 "positive callback restore still succeeds after the full sweep");

cleanup:
    if (adapter_instance != NULL)
        (void)gn_test_state_failpoint_disarm(adapter_instance);
    destroy_pair(bundle, witness);
    free(sram_before);
    free(baseline);
    TEST_ASSERT_EQUAL_MESSAGE(0u, assertion_failures,
                              "callback allocation-failure assertions pass");
}

static void callback_fault_keeps_capacity_and_reset_recovers(void) {
    uint8_t *bundle = NULL;
    size_t bundle_size = 0u;
    gn_instance *witness = NULL;
    uint8_t *baseline = NULL;
    uint8_t *blocked = NULL;
    uint8_t *sram_before = NULL;
    uint8_t *retained_sram = NULL;
    size_t capacity = 0u;
    size_t sram_size = 0u;
    const bool loaded = initialize_pair(&bundle, &bundle_size, &witness);
    SAFETY_CHECK(loaded, "fault test loads the real adapter and native witness");
    if (!loaded) goto cleanup;
    if (!check_pair_loaded(witness, &capacity, &retained_sram, &sram_size))
        goto cleanup;
    SAFETY_CHECK(run_adapter_and_witness(witness, GN_MVS_INPUT_P1_A),
                 "fault test establishes a healthy matched state");
    baseline = capture_adapter_state(capacity);
    blocked = (uint8_t *)malloc(capacity);
    sram_before = (uint8_t *)malloc(sram_size);
    SAFETY_CHECK(baseline != NULL && blocked != NULL && sram_before != NULL,
                 "fault recovery buffers fit the cached state and SRAM bounds");
    if (baseline == NULL || blocked == NULL || sram_before == NULL) goto cleanup;
    memcpy(sram_before, retained_sram, sram_size);
    gn_instance *adapter_instance = gn_test_libretro_instance();
    SAFETY_CHECK(adapter_instance != NULL,
                 "fault hook reaches the adapter's own native instance");
    if (adapter_instance == NULL) goto cleanup;
    SAFETY_CHECK(gn_test_mvs_set_failure(adapter_instance,
                     GN_TEST_MVS_FAILURE_SOUND_TICK_LIMIT) == GN_STATUS_OK,
                 "known sound-device fault is armed on the adapter instance");
    sampled_input = 0u;
    retro_run();
    SAFETY_CHECK(retro_serialize_size() == capacity,
                 "capture-blocking fault does not alter cached state capacity");
    memset(blocked, 0x6du, capacity);
    SAFETY_CHECK(!retro_serialize(blocked, capacity) && blocked[0] == 0x6du &&
                     blocked[capacity - 1u] == 0x6du,
                 "faulted callback capture is ineligible and leaves bytes intact");
    SAFETY_CHECK(retro_unserialize(baseline, capacity),
                 "valid historical restore recovers the supported guest fault");
    SAFETY_CHECK(gn_state_restore_v1(witness, baseline, capacity, NULL, 0u) ==
                     GN_STATUS_OK,
                 "native witness restores the same known healthy boundary");
    SAFETY_CHECK(retro_serialize(blocked, capacity),
                 "eligible restore makes adapter capture available again");
    SAFETY_CHECK(retro_serialize_size() == capacity &&
                     retro_get_memory_data(RETRO_MEMORY_SAVE_RAM) == retained_sram &&
                     retro_get_memory_size(RETRO_MEMORY_SAVE_RAM) == sram_size &&
                     memcmp(retained_sram, sram_before, sram_size) == 0,
                 "validated fault recovery keeps capacity and retained SRAM stable");
    (void)state_pair_equal(witness, capacity,
                           "validated restore recovers identical machine state");

    SAFETY_CHECK(gn_test_mvs_set_failure(adapter_instance,
                     GN_TEST_MVS_FAILURE_SOUND_TICK_LIMIT) == GN_STATUS_OK,
                 "second one-shot fault is armed to check reset recovery");
    retro_run();
    SAFETY_CHECK(retro_serialize_size() == capacity &&
                     !retro_serialize(blocked, capacity),
                 "second capture-blocking fault preserves capacity and rejects capture");

    retro_reset();
    SAFETY_CHECK(gn_reset(witness) == GN_STATUS_OK,
                 "independent witness resets to the same healthy boundary");
    SAFETY_CHECK(retro_serialize_size() == capacity &&
                     retro_serialize(blocked, capacity),
                 "healthy reset restores capture eligibility at cached capacity");
    SAFETY_CHECK(retro_get_memory_data(RETRO_MEMORY_SAVE_RAM) == retained_sram &&
                     retro_get_memory_size(RETRO_MEMORY_SAVE_RAM) == sram_size &&
                     memcmp(retained_sram, sram_before, sram_size) == 0,
                 "reset preserves the exact retained SRAM allocation and bytes");
    (void)state_pair_equal(witness, capacity,
                           "reset adapter and witness have identical healthy state");
    SAFETY_CHECK(run_adapter_and_witness(witness, 0u),
                 "healthy reset continues with identical guest and output timing");
    (void)state_pair_equal(witness, capacity,
                           "post-reset callback state matches native continuation");

cleanup:
    destroy_pair(bundle, witness);
    free(sram_before);
    free(blocked);
    free(baseline);
    TEST_ASSERT_EQUAL_MESSAGE(0u, assertion_failures,
                              "faulted capture recovery assertions pass");
}

static void native_instance_a_b_memory_isolation(void) {
    uint8_t *bundle_a = NULL;
    uint8_t *bundle_b = NULL;
    size_t size_a = public_save_guest_size();
    size_t size_b = size_a;
    gn_instance *instance_a = NULL;
    gn_instance *instance_b = NULL;
    uint8_t *state_a = NULL;
    uint8_t *state_b = NULL;
    size_t state_size_a = 0u;
    size_t state_size_b = 0u;
    uint8_t expected_a[SAVE_FIXTURE_OUTPUT_COUNT] = {
        0x12u, 0x34u, 0x56u, 0x78u, 0x9au, 0xbcu
    };
    uint8_t expected_b[SAVE_FIXTURE_OUTPUT_COUNT] = {
        0xa1u, 0xb2u, 0xc3u, 0xd4u, 0xe5u, 0xf6u
    };
    uint8_t observed_a[SAVE_FIXTURE_OUTPUT_COUNT] = {0};
    uint8_t observed_b[SAVE_FIXTURE_OUTPUT_COUNT] = {0};
    uint8_t *ram_a = NULL;
    uint8_t *ram_b = NULL;
    size_t ram_size_a = 0u;
    size_t ram_size_b = 0u;
    bundle_a = (uint8_t *)malloc(size_a);
    bundle_b = (uint8_t *)malloc(size_b);
    SAFETY_CHECK(bundle_a != NULL && bundle_b != NULL &&
                     public_save_guest_build(bundle_a, size_a) &&
                     public_save_guest_build(bundle_b, size_b) &&
                     mutate_unused_bios_byte(bundle_b, size_b),
                 "native isolation uses two valid distinguishable public bundles");
    if (bundle_a == NULL || bundle_b == NULL) goto cleanup;
    SAFETY_CHECK(load_native_from_bundle(bundle_a, size_a, &instance_a) &&
                     load_native_from_bundle(bundle_b, size_b, &instance_b),
                 "two independent native instances load successfully");
    if (instance_a == NULL || instance_b == NULL) goto cleanup;
    SAFETY_CHECK(save_fixture_run_guest(instance_a, GN_MVS_INPUT_P1_A) &&
                     save_fixture_run_guest(instance_b, GN_MVS_INPUT_P1_B),
                 "independent A/B guests execute different SRAM writes");
    SAFETY_CHECK(gn_private_mvs_save_ram_view(instance_a, &ram_a,
                                               &ram_size_a) == GN_STATUS_OK &&
                     gn_private_mvs_save_ram_view(instance_b, &ram_b,
                                               &ram_size_b) == GN_STATUS_OK &&
                     ram_a != NULL && ram_b != NULL && ram_a != ram_b &&
                     ram_size_a == SAFETY_SAVE_RAM_BYTES &&
                     ram_size_b == ram_size_a,
                 "native instances own distinct retained SRAM allocations");
    SAFETY_CHECK(save_fixture_read_sram(instance_a, observed_a) &&
                     save_fixture_read_sram(instance_b, observed_b) &&
                     memcmp(observed_a, expected_a, sizeof(expected_a)) == 0 &&
                     memcmp(observed_b, expected_b, sizeof(expected_b)) == 0,
                 "A and B guest SRAM values remain distinguishable");
    SAFETY_CHECK(save_fixture_capture(instance_a, &state_a, &state_size_a) &&
                     save_fixture_capture(instance_b, &state_b, &state_size_b) &&
                     state_size_a == state_size_b &&
                     memcmp(state_a + 32u, state_b + 32u, 32u) != 0,
                 "A/B state identities reflect their distinct media content");
    const uint8_t b_before = ram_b[0];
    ram_a[0] ^= UINT8_C(0x7f);
    SAFETY_CHECK(ram_b[0] == b_before,
                 "quiescent mutation of instance A does not modify instance B");
    SAFETY_CHECK(save_fixture_read_sram(instance_b, observed_b) &&
                     memcmp(observed_b, expected_b, sizeof(expected_b)) == 0,
                 "instance B guest-visible SRAM survives A's external write");

cleanup:
    free(state_b);
    free(state_a);
    gn_destroy(instance_b);
    gn_destroy(instance_a);
    free(bundle_b);
    free(bundle_a);
    TEST_ASSERT_EQUAL_MESSAGE(0u, assertion_failures,
                              "native A/B instance isolation assertions pass");
}

static int adapter_read_guest_output(uint8_t output[SAVE_FIXTURE_OUTPUT_COUNT]) {
    gn_instance *instance = gn_test_libretro_instance();
    if (instance == NULL || output == NULL) return 0;
    for (size_t index = 0u; index < SAVE_FIXTURE_OUTPUT_COUNT; ++index) {
        if (gn_test_mvs_read_bus8(instance, UINT32_C(0x100000) +
                                  (uint32_t)index, &output[index]) != GN_STATUS_OK)
            return 0;
    }
    return 1;
}

static int save_ram_guest_values_match(
    const uint8_t *ram, size_t ram_size,
    const uint8_t expected[SAVE_FIXTURE_OUTPUT_COUNT]) {
    static const size_t offsets[SAVE_FIXTURE_OUTPUT_COUNT] = {
        0u, 1u, 0x1234u, 0x1235u, 0xfffeu, 0xffffu
    };
    if (ram == NULL || expected == NULL) return 0;
    for (size_t index = 0u; index < SAVE_FIXTURE_OUTPUT_COUNT; ++index) {
        if (offsets[index] >= ram_size || ram[offsets[index]] != expected[index])
            return 0;
    }
    return 1;
}

static void simulate_frontend_policy_copies(unsigned preserve_current_sram) {
    static const uint8_t expected_a[SAVE_FIXTURE_OUTPUT_COUNT] = {
        0x12u, 0x34u, 0x56u, 0x78u, 0x9au, 0xbcu
    };
    static const uint8_t expected_b[SAVE_FIXTURE_OUTPUT_COUNT] = {
        0xa1u, 0xb2u, 0xc3u, 0xd4u, 0xe5u, 0xf6u
    };
    uint8_t *bundle = NULL;
    size_t bundle_size = 0u;
    gn_instance *witness = NULL;
    uint8_t *state_a = NULL;
    uint8_t *state_b = NULL;
    uint8_t *sram_a = NULL;
    uint8_t *sram_b = NULL;
    uint8_t *policy_copy = NULL;
    uint8_t *retained_sram = NULL;
    uint8_t native_output[SAVE_FIXTURE_OUTPUT_COUNT] = {0};
    uint8_t adapter_output[SAVE_FIXTURE_OUTPUT_COUNT] = {0};
    size_t capacity = 0u;
    size_t sram_size = 0u;
    size_t state_a_size = 0u;
    size_t state_b_size = 0u;
    const bool loaded = initialize_pair(&bundle, &bundle_size, &witness);
    SAFETY_CHECK(loaded,
                 "quiescent SRAM policy scenario loads a matching adapter/witness");
    if (!loaded) goto cleanup;
    if (!check_pair_loaded(witness, &capacity, &retained_sram, &sram_size))
        goto cleanup;
    sram_a = (uint8_t *)malloc(sram_size);
    sram_b = (uint8_t *)malloc(sram_size);
    policy_copy = (uint8_t *)malloc(sram_size);
    SAFETY_CHECK(sram_a != NULL && sram_b != NULL &&
                     policy_copy != NULL,
                 "A/B state and policy copies allocate the full bounded SRAM size");
    if (sram_a == NULL || sram_b == NULL || policy_copy == NULL)
        goto cleanup;
    SAFETY_CHECK(run_adapter_and_witness(witness, GN_MVS_INPUT_P1_A),
                 "guest writes SRAM A before the first policy state capture");
    state_a = capture_adapter_state(capacity);
    state_a_size = capacity;
    memcpy(sram_a, retained_sram, sram_size);
    SAFETY_CHECK(save_ram_guest_values_match(sram_a, sram_size, expected_a),
                 "the first state retains the exact guest-written SRAM A values");
    retro_reset();
    SAFETY_CHECK(gn_reset(witness) == GN_STATUS_OK &&
                     retro_get_memory_data(RETRO_MEMORY_SAVE_RAM) == retained_sram &&
                     memcmp(retained_sram, sram_a, sram_size) == 0,
                 "reset preserves SRAM A while rewinding the guest for B");
    SAFETY_CHECK(run_adapter_and_witness(witness, GN_MVS_INPUT_P1_B),
                 "guest changes SRAM to B before restore and undo simulation");
    state_b = capture_adapter_state(capacity);
    state_b_size = capacity;
    memcpy(sram_b, retained_sram, sram_size);
    SAFETY_CHECK(state_a != NULL && state_b != NULL &&
                     state_a_size == state_b_size &&
                     memcmp(sram_a, sram_b, sram_size) != 0 &&
                     save_ram_guest_values_match(sram_b, sram_size, expected_b),
                 "saved state A and current state B carry distinct guest SRAM");

    if (preserve_current_sram != 0u)
        memcpy(policy_copy, retained_sram, sram_size);
    SAFETY_CHECK(retro_unserialize(state_a, state_a_size),
                 "frontend load simulation accepts historical state A");
    SAFETY_CHECK(gn_state_restore_v1(witness, state_a, state_a_size, NULL, 0u) ==
                     GN_STATUS_OK,
                 "native witness applies the same historical state A");
    uint8_t *native_sram = NULL;
    size_t native_sram_size = 0u;
    SAFETY_CHECK(gn_private_mvs_save_ram_view(witness, &native_sram,
                                               &native_sram_size) == GN_STATUS_OK &&
                     native_sram != NULL && native_sram_size == sram_size,
                 "native witness keeps the original A/B policy backing extent");
    if (native_sram == NULL || native_sram_size != sram_size) goto cleanup;
    if (preserve_current_sram != 0u) {
        memcpy(retained_sram, policy_copy, sram_size);
        memcpy(native_sram, policy_copy, sram_size);
    }
    const uint8_t *expected_after_load = preserve_current_sram != 0u
        ? expected_b : expected_a;
    SAFETY_CHECK(save_ram_guest_values_match(retained_sram, sram_size,
                                              expected_after_load) &&
                     retro_get_memory_data(RETRO_MEMORY_SAVE_RAM) == retained_sram,
                 "load policy either restores historical A or preserves current B");
    retro_reset();
    SAFETY_CHECK(gn_reset(witness) == GN_STATUS_OK,
                 "load policy witness resets to re-read current SRAM");
    SAFETY_CHECK(run_adapter_and_witness(witness, 0u),
                 "post-load guest reads the policy-selected SRAM image");
    SAFETY_CHECK(adapter_read_guest_output(adapter_output) &&
                     save_fixture_read_guest_output(witness, native_output) &&
                     memcmp(adapter_output, expected_after_load,
                            sizeof(adapter_output)) == 0 &&
                     memcmp(native_output, expected_after_load,
                            sizeof(native_output)) == 0,
                 "guest A/B output proves the selected current-SRAM policy");
    (void)state_pair_equal(witness, capacity,
                           "load and current-SRAM copy keep machines aligned");

    if (preserve_current_sram != 0u)
        memcpy(policy_copy, retained_sram, sram_size);
    SAFETY_CHECK(retro_unserialize(state_b, state_b_size),
                 "undo-load simulation accepts the distinct state B snapshot");
    SAFETY_CHECK(gn_state_restore_v1(witness, state_b, state_b_size, NULL, 0u) ==
                     GN_STATUS_OK,
                 "native witness applies the same undo state B");
    if (preserve_current_sram != 0u) {
        memcpy(retained_sram, policy_copy, sram_size);
        memcpy(native_sram, policy_copy, sram_size);
    }
    SAFETY_CHECK(save_ram_guest_values_match(retained_sram, sram_size,
                                              expected_b) &&
                     retro_get_memory_data(RETRO_MEMORY_SAVE_RAM) == retained_sram &&
                     retro_get_memory_size(RETRO_MEMORY_SAVE_RAM) == sram_size,
                 "undo path retains state B at the original live SRAM allocation");
    retro_reset();
    SAFETY_CHECK(gn_reset(witness) == GN_STATUS_OK,
                 "undo policy witness resets to re-read B SRAM");
    SAFETY_CHECK(run_adapter_and_witness(witness, 0u),
                 "post-undo guest reads the restored B SRAM image");
    SAFETY_CHECK(adapter_read_guest_output(adapter_output) &&
                     save_fixture_read_guest_output(witness, native_output) &&
                     memcmp(adapter_output, expected_b, sizeof(adapter_output)) == 0 &&
                     memcmp(native_output, expected_b, sizeof(native_output)) == 0,
                 "undo guest output reflects B under the selected SRAM policy");
    (void)state_pair_equal(witness, capacity,
                           "undo transition preserves exact continuation alignment");

cleanup:
    destroy_pair(bundle, witness);
    free(policy_copy);
    free(sram_b);
    free(sram_a);
    free(state_b);
    free(state_a);
}

static void adapter_replacement_unload_reload_and_deinit(void) {
    uint8_t *bundle_a = NULL;
    uint8_t *bundle_b = NULL;
    size_t bundle_a_size = 0u;
    size_t bundle_b_size = public_save_guest_size();
    gn_instance *witness = NULL;
    uint8_t *baseline = NULL;
    uint8_t *retained_sram = NULL;
    size_t capacity = 0u;
    size_t sram_size = 0u;
    size_t capacity_b = 0u;
    const bool loaded = initialize_pair(&bundle_a, &bundle_a_size, &witness);
    SAFETY_CHECK(loaded, "lifecycle test starts from a loaded adapter/witness pair");
    if (!loaded) goto cleanup;
    if (!check_pair_loaded(witness, &capacity, &retained_sram, &sram_size))
        goto cleanup;
    SAFETY_CHECK(run_adapter_and_witness(witness, GN_MVS_INPUT_P1_A),
                 "lifecycle test establishes live guest and SRAM state");
    baseline = capture_adapter_state(capacity);
    bundle_b = (uint8_t *)malloc(bundle_b_size);
    SAFETY_CHECK(baseline != NULL && bundle_b != NULL &&
                     public_save_guest_build(bundle_b, bundle_b_size) &&
                     mutate_unused_bios_byte(bundle_b, bundle_b_size),
                 "replacement bundle B is valid and content-distinguishable");
    if (baseline == NULL || bundle_b == NULL) goto cleanup;
    const struct retro_game_info replacement = {
        NULL, bundle_b, bundle_b_size, NULL
    };
    SAFETY_CHECK(!retro_load_game(&replacement),
                 "loaded adapter rejects a second simultaneous content load");
    SAFETY_CHECK(retro_get_memory_data(RETRO_MEMORY_SAVE_RAM) == retained_sram &&
                     retro_get_memory_size(RETRO_MEMORY_SAVE_RAM) == sram_size &&
                     retro_serialize_size() == capacity,
                 "failed replacement leaves the existing pointer and capacity live");
    (void)state_pair_equal(witness, capacity,
                           "failed replacement leaves existing machine state intact");

    /* Quiescent endpoint: no saved pointer is read after this unload call. */
    retro_unload_game();
    retained_sram = NULL;
    SAFETY_CHECK(retro_get_memory_data(RETRO_MEMORY_SAVE_RAM) == NULL &&
                     retro_get_memory_size(RETRO_MEMORY_SAVE_RAM) == 0u &&
                     retro_serialize_size() == 0u,
                 "unload ends retained-pointer access and clears adapter views");
    gn_destroy(witness);
    witness = NULL;
    SAFETY_CHECK(retro_load_game(&replacement),
                 "valid replacement content loads after quiescent unload");
    SAFETY_CHECK(load_native_from_bundle(bundle_b, bundle_b_size, &witness),
                 "independent witness loads the same replacement identity");
    if (witness == NULL) goto cleanup;
    capacity_b = retro_serialize_size();
    retained_sram = (uint8_t *)retro_get_memory_data(RETRO_MEMORY_SAVE_RAM);
    SAFETY_CHECK(capacity_b == capacity && retained_sram != NULL &&
                     retro_get_memory_size(RETRO_MEMORY_SAVE_RAM) == sram_size,
                 "replacement publishes a fresh view with the expected fixed extents");
    SAFETY_CHECK(run_adapter_and_witness(witness, GN_MVS_INPUT_P1_B),
                 "replacement guest and independent witness continue together");
    (void)state_pair_equal(witness, capacity_b,
                           "replacement state reflects the new media identity");

    /* retro_deinit is a second explicit endpoint; stale memory is never touched. */
    retained_sram = NULL;
    retro_deinit();
    SAFETY_CHECK(retro_get_memory_data(RETRO_MEMORY_SAVE_RAM) == NULL &&
                     retro_get_memory_size(RETRO_MEMORY_SAVE_RAM) == 0u &&
                     retro_serialize_size() == 0u,
                 "deinit clears adapter availability after all pointer users stop");
    gn_destroy(witness);
    witness = NULL;
    retro_set_environment(environment_callback);
    retro_set_video_refresh(video_callback);
    retro_set_audio_sample(audio_callback);
    retro_set_audio_sample_batch(audio_batch_callback);
    retro_set_input_poll(input_poll_callback);
    retro_set_input_state(input_state_callback);
    retro_init();
    SAFETY_CHECK(retro_load_game(&replacement),
                 "adapter reloads valid content after deinit and fresh init");
    SAFETY_CHECK(load_native_from_bundle(bundle_b, bundle_b_size, &witness),
                 "fresh-init witness reloads the same public media");
    if (witness == NULL) goto cleanup;
    retained_sram = (uint8_t *)retro_get_memory_data(RETRO_MEMORY_SAVE_RAM);
    capacity_b = retro_serialize_size();
    SAFETY_CHECK(retained_sram != NULL && capacity_b == capacity &&
                     retro_get_memory_size(RETRO_MEMORY_SAVE_RAM) == sram_size,
                 "fresh reload publishes a live retained pointer and cached capacity");
    SAFETY_CHECK(run_adapter_and_witness(witness, 0u),
                 "freshly reloaded adapter remains usable after lifecycle transitions");

cleanup:
    retained_sram = NULL;
    destroy_pair(bundle_a, witness);
    free(baseline);
    free(bundle_b);
    TEST_ASSERT_EQUAL_MESSAGE(0u, assertion_failures,
                              "adapter lifecycle retention assertions pass");
}

static void adapter_policy_and_isolation_matrix(void) {
    native_instance_a_b_memory_isolation();
    simulate_frontend_policy_copies(0u);
    simulate_frontend_policy_copies(1u);
    adapter_replacement_unload_reload_and_deinit();
    SAFETY_CHECK(assertion_failures == 0u,
                 "all quiescent policy, instance, and lifecycle assertions pass");
}

typedef struct safety_process {
    FILE *output;
#if defined(_WIN32)
    HANDLE process;
#else
    pid_t process;
#endif
} safety_process_t;

#if defined(_WIN32)
static int append_command_byte(char *command, size_t capacity, size_t *used,
                               char byte) {
    if (*used + 1u >= capacity) return 0;
    command[*used] = byte;
    ++*used;
    command[*used] = '\0';
    return 1;
}

/* Quote one argument using the Microsoft C runtime command-line rules. */
static int append_windows_argument(char *command, size_t capacity,
                                   size_t *used, const char *argument) {
    if (!append_command_byte(command, capacity, used, '"')) return 0;
    size_t backslashes = 0u;
    for (const char *cursor = argument;; ++cursor) {
        if (*cursor == '\\') {
            ++backslashes;
            continue;
        }
        if (*cursor == '"' || *cursor == '\0') {
            const size_t slash_count = backslashes *
                ((*cursor == '"') ? 2u : 2u) +
                ((*cursor == '"') ? 1u : 0u);
            for (size_t index = 0u; index < slash_count; ++index) {
                if (!append_command_byte(command, capacity, used, '\\'))
                    return 0;
            }
            backslashes = 0u;
            if (*cursor == '"') {
                if (!append_command_byte(command, capacity, used, '"'))
                    return 0;
                continue;
            }
            return append_command_byte(command, capacity, used, '"');
        }
        for (size_t index = 0u; index < backslashes; ++index) {
            if (!append_command_byte(command, capacity, used, '\\'))
                return 0;
        }
        backslashes = 0u;
        if (!append_command_byte(command, capacity, used, *cursor)) return 0;
    }
}
#else
static void exec_without_shell(const char *executable, char *const arguments[]) {
    if (strchr(executable, '/') != NULL) {
        execv(executable, arguments);
        _exit(127);
    }

    const char *search_path = getenv("PATH");
    if (search_path == NULL) search_path = "/bin:/usr/bin";
    int last_error = ENOENT;
    const char *entry = search_path;
    for (;;) {
        const char *separator = strchr(entry, ':');
        const size_t directory_length = separator == NULL
            ? strlen(entry) : (size_t)(separator - entry);
        const size_t executable_length = strlen(executable);
        if (directory_length <= SIZE_MAX - executable_length - 2u) {
            const size_t candidate_length = directory_length == 0u
                ? executable_length
                : directory_length + 1u + executable_length;
            char *candidate = (char *)malloc(candidate_length + 1u);
            if (candidate == NULL) _exit(127);
            if (directory_length == 0u) {
                memcpy(candidate, executable, executable_length + 1u);
            } else {
                memcpy(candidate, entry, directory_length);
                candidate[directory_length] = '/';
                memcpy(candidate + directory_length + 1u, executable,
                       executable_length + 1u);
            }
            execv(candidate, arguments);
            if (errno != ENOENT && errno != ENOTDIR) last_error = errno;
            free(candidate);
        }
        if (separator == NULL) break;
        entry = separator + 1;
    }
    errno = last_error;
    _exit(127);
}
#endif

/* Start an executable with an argv vector and capture only its output pipe. */
static int safety_process_start(safety_process_t *child, const char *executable,
                                char *const arguments[]) {
    if (child == NULL || executable == NULL || arguments == NULL) return 0;
    child->output = NULL;
#if defined(_WIN32)
    child->process = NULL;
    SECURITY_ATTRIBUTES security;
    memset(&security, 0, sizeof(security));
    security.nLength = sizeof(security);
    security.bInheritHandle = TRUE;
    HANDLE read_handle = NULL;
    HANDLE write_handle = NULL;
    if (!CreatePipe(&read_handle, &write_handle, &security, 0u)) return 0;
    if (!SetHandleInformation(read_handle, HANDLE_FLAG_INHERIT, 0u)) {
        CloseHandle(read_handle);
        CloseHandle(write_handle);
        return 0;
    }

    char command[4096] = {0};
    size_t used = 0u;
    int command_valid = append_windows_argument(command, sizeof(command),
                                                  &used, arguments[0]);
    for (size_t index = 1u; command_valid && arguments[index] != NULL; ++index) {
        command_valid = append_command_byte(command, sizeof(command), &used, ' ') &&
            append_windows_argument(command, sizeof(command), &used,
                                    arguments[index]);
    }
    if (!command_valid) {
        CloseHandle(read_handle);
        CloseHandle(write_handle);
        return 0;
    }

    STARTUPINFOA startup;
    PROCESS_INFORMATION information;
    memset(&startup, 0, sizeof(startup));
    memset(&information, 0, sizeof(information));
    startup.cb = sizeof(startup);
    startup.dwFlags = STARTF_USESTDHANDLES;
    startup.hStdInput = GetStdHandle(STD_INPUT_HANDLE);
    startup.hStdOutput = write_handle;
    startup.hStdError = write_handle;
    const BOOL created = CreateProcessA(executable, command, NULL, NULL, TRUE, 0u,
                                        NULL, NULL, &startup, &information);
    CloseHandle(write_handle);
    if (!created) {
        CloseHandle(read_handle);
        return 0;
    }
    CloseHandle(information.hThread);
    const int output_fd = _open_osfhandle((intptr_t)read_handle,
                                          _O_RDONLY | _O_BINARY);
    if (output_fd < 0) {
        CloseHandle(read_handle);
        (void)TerminateProcess(information.hProcess, 127u);
        (void)WaitForSingleObject(information.hProcess, INFINITE);
        CloseHandle(information.hProcess);
        return 0;
    }
    child->output = _fdopen(output_fd, "r");
    if (child->output == NULL) {
        (void)_close(output_fd);
        (void)TerminateProcess(information.hProcess, 127u);
        (void)WaitForSingleObject(information.hProcess, INFINITE);
        CloseHandle(information.hProcess);
        return 0;
    }
    child->process = information.hProcess;
    return 1;
#else
    child->process = (pid_t)-1;
    int descriptors[2];
    if (pipe(descriptors) != 0) return 0;
    const pid_t process = fork();
    if (process < 0) {
        (void)close(descriptors[0]);
        (void)close(descriptors[1]);
        return 0;
    }
    if (process == 0) {
        (void)close(descriptors[0]);
        if (dup2(descriptors[1], STDOUT_FILENO) < 0) _exit(126);
        (void)close(descriptors[1]);
        exec_without_shell(executable, arguments);
    }
    (void)close(descriptors[1]);
    child->output = fdopen(descriptors[0], "r");
    if (child->output == NULL) {
        (void)close(descriptors[0]);
        (void)kill(process, SIGTERM);
        int status;
        while (waitpid(process, &status, 0) < 0 && errno == EINTR) {}
        return 0;
    }
    child->process = process;
    return 1;
#endif
}

static int safety_process_finish(safety_process_t *child) {
    if (child == NULL || child->output == NULL) return 0;
    int success = fclose(child->output) == 0;
    child->output = NULL;
#if defined(_WIN32)
    DWORD status = 127u;
    if (child->process == NULL ||
        WaitForSingleObject(child->process, INFINITE) != WAIT_OBJECT_0 ||
        !GetExitCodeProcess(child->process, &status) || status != 0u)
        success = 0;
    if (child->process != NULL) CloseHandle(child->process);
    child->process = NULL;
#else
    int status = 0;
    pid_t result;
    do {
        result = waitpid(child->process, &status, 0);
    } while (result < 0 && errno == EINTR);
    child->process = (pid_t)-1;
    if (result < 0 || !WIFEXITED(status) || WEXITSTATUS(status) != 0)
        success = 0;
#endif
    return success;
}

static int process_child_mode(const char *selector) {
    if (selector == NULL || (selector[0] != 'A' && selector[0] != 'B') ||
        selector[1] != '\0')
        return 2;
    const bool variant_b = selector[0] == 'B';
    const uint32_t input = variant_b ? GN_MVS_INPUT_P1_B : GN_MVS_INPUT_P1_A;
    static const uint8_t expected_a[SAVE_FIXTURE_OUTPUT_COUNT] = {
        0x12u, 0x34u, 0x56u, 0x78u, 0x9au, 0xbcu
    };
    static const uint8_t expected_b[SAVE_FIXTURE_OUTPUT_COUNT] = {
        0xa1u, 0xb2u, 0xc3u, 0xd4u, 0xe5u, 0xf6u
    };
    const uint8_t *expected = variant_b ? expected_b : expected_a;
    const size_t bundle_size = public_save_guest_size();
    uint8_t *bundle = (uint8_t *)malloc(bundle_size);
    if (bundle == NULL || !public_save_guest_build(bundle, bundle_size) ||
        (variant_b && !mutate_unused_bios_byte(bundle, bundle_size))) {
        free(bundle);
        return 3;
    }
    retro_set_environment(environment_callback);
    retro_set_video_refresh(video_callback);
    retro_set_audio_sample(audio_callback);
    retro_set_audio_sample_batch(audio_batch_callback);
    retro_set_input_poll(input_poll_callback);
    retro_set_input_state(input_state_callback);
    retro_init();
    const struct retro_game_info game = {NULL, bundle, bundle_size, NULL};
    if (!retro_load_game(&game)) {
        retro_deinit();
        free(bundle);
        return 4;
    }
    sampled_input = input;
    retro_run();
    uint8_t *state = capture_adapter_state(retro_serialize_size());
    uint8_t *ram = (uint8_t *)retro_get_memory_data(RETRO_MEMORY_SAVE_RAM);
    const size_t ram_size = retro_get_memory_size(RETRO_MEMORY_SAVE_RAM);
    if (state == NULL || !save_ram_guest_values_match(ram, ram_size, expected)) {
        free(state);
        retro_deinit();
        free(bundle);
        return 5;
    }
    (void)printf("SAFETY_PROCESS_RESULT=%c:", selector[0]);
    for (size_t index = 0u; index < 32u; ++index)
        (void)printf("%02x", (unsigned)state[32u + index]);
    (void)putchar(':');
    for (size_t index = 0u; index < SAVE_FIXTURE_OUTPUT_COUNT; ++index)
        (void)printf("%02x", (unsigned)expected[index]);
    (void)putchar('\n');
    (void)fflush(stdout);
    free(state);
    retro_deinit();
    free(bundle);
    return 0;
}

static int run_fresh_adapter_process(const char *selector, char *line,
                                     size_t line_capacity) {
    if (safety_executable_path == NULL || selector == NULL || line == NULL ||
        line_capacity == 0u)
        return 0;
    char *arguments[] = {(char *)safety_executable_path, "--process-child",
                         (char *)selector, NULL};
    safety_process_t child;
    if (!safety_process_start(&child, safety_executable_path, arguments)) return 0;
    line[0] = '\0';
    size_t output_bytes = 0u;
    int output_valid = 1;
    char buffer[512];
    while (fgets(buffer, sizeof(buffer), child.output) != NULL) {
        const size_t length = strlen(buffer);
        if (length > SAFETY_CHILD_OUTPUT_LIMIT - output_bytes) {
            output_valid = 0;
            break;
        }
        output_bytes += length;
        if (strncmp(buffer, "SAFETY_PROCESS_RESULT=", 22u) == 0) {
            if (length >= line_capacity) {
                output_valid = 0;
                break;
            }
            memcpy(line, buffer, length + 1u);
        }
    }
    if (ferror(child.output)) output_valid = 0;
    const int child_status_ok = safety_process_finish(&child);
    return output_valid && child_status_ok && line[0] != '\0';
}

static int is_lowercase_hex_digit(char value) {
    return (value >= '0' && value <= '9') ||
        (value >= 'a' && value <= 'f');
}

static int parse_process_result(const char *line, char *selector,
                                char identity[65], char sram_values[13]) {
    static const char prefix[] = "SAFETY_PROCESS_RESULT=";
    const size_t prefix_length = sizeof(prefix) - 1u;
    const size_t expected_length = prefix_length + 2u + 64u + 1u + 12u;
    if (line == NULL || selector == NULL || identity == NULL ||
        sram_values == NULL) {
        return 0;
    }
    const size_t line_length = strlen(line);
    const int has_line_feed =
        (line_length == expected_length + 1u &&
         line[expected_length] == '\n') ||
        (line_length == expected_length + 2u &&
         line[expected_length] == '\r' &&
         line[expected_length + 1u] == '\n');
    if ((line_length != expected_length && !has_line_feed) ||
        memcmp(line, prefix, prefix_length) != 0) {
        return 0;
    }

    const char *cursor = line + prefix_length;
    const char parsed_selector = cursor[0];
    if (cursor[1] != ':') return 0;
    cursor += 2u;

    char parsed_identity[65];
    for (size_t index = 0; index < 64u; ++index) {
        if (!is_lowercase_hex_digit(cursor[index])) return 0;
        parsed_identity[index] = cursor[index];
    }
    parsed_identity[64] = '\0';
    cursor += 64u;
    if (*cursor++ != ':') return 0;

    char parsed_sram_values[13];
    for (size_t index = 0; index < 12u; ++index) {
        if (!is_lowercase_hex_digit(cursor[index])) return 0;
        parsed_sram_values[index] = cursor[index];
    }
    parsed_sram_values[12] = '\0';

    *selector = parsed_selector;
    memcpy(identity, parsed_identity, sizeof(parsed_identity));
    memcpy(sram_values, parsed_sram_values, sizeof(parsed_sram_values));
    return 1;
}

static void fresh_adapter_processes_keep_distinct_content_and_sram(void) {
    char line_a[512];
    char line_b[512];
    char line_a_again[512];
    char identity_a[65] = {0};
    char identity_b[65] = {0};
    char identity_a_again[65] = {0};
    char sram_a[13] = {0};
    char sram_b[13] = {0};
    char sram_a_again[13] = {0};
    char selector_a = '\0';
    char selector_b = '\0';
    char selector_a_again = '\0';
    const int child_a_ok = run_fresh_adapter_process("A", line_a,
                                                      sizeof(line_a));
    const int child_b_ok = run_fresh_adapter_process("B", line_b,
                                                      sizeof(line_b));
    const int child_a_again_ok = run_fresh_adapter_process(
        "A", line_a_again, sizeof(line_a_again));
    SAFETY_CHECK(child_a_ok && child_b_ok && child_a_again_ok,
                 "three fresh adapter processes complete their public guest runs");
    if (!child_a_ok || !child_b_ok || !child_a_again_ok) goto done;
    char malformed_line[512];
    char malformed_selector = '\0';
    char malformed_identity[65] = {0};
    char malformed_sram_values[13] = {0};
    memcpy(malformed_line, line_a, strlen(line_a) + 1u);
    malformed_line[sizeof("SAFETY_PROCESS_RESULT=") - 1u + 2u] = 'G';
    SAFETY_CHECK(!parse_process_result(malformed_line, &malformed_selector,
                                      malformed_identity, malformed_sram_values),
                 "fresh process parser rejects uppercase non-hex identity bytes");
    memcpy(malformed_line, line_a, strlen(line_a) + 1u);
    malformed_line[sizeof("SAFETY_PROCESS_RESULT=") - 1u + 2u +
                   64u + 1u + 11u] = '\0';
    SAFETY_CHECK(!parse_process_result(malformed_line, &malformed_selector,
                                      malformed_identity, malformed_sram_values),
                 "fresh process parser rejects truncated SRAM values");
    SAFETY_CHECK(parse_process_result(line_a, &selector_a, identity_a, sram_a) &&
                     parse_process_result(line_b, &selector_b, identity_b, sram_b) &&
                     parse_process_result(line_a_again, &selector_a_again,
                                          identity_a_again, sram_a_again),
                 "fresh process results include complete state identity and SRAM");
    SAFETY_CHECK(selector_a == 'A' && selector_b == 'B' &&
                     selector_a_again == 'A' && strcmp(identity_a, identity_b) != 0,
                 "fresh processes load distinguishable media identities");
    SAFETY_CHECK(strcmp(sram_a, "123456789abc") == 0 &&
                     strcmp(sram_b, "a1b2c3d4e5f6") == 0 &&
                     strcmp(sram_a, sram_b) != 0,
                 "fresh A/B processes expose distinct guest-written SRAM values");
    SAFETY_CHECK(strcmp(identity_a, identity_a_again) == 0 &&
                     strcmp(sram_a, sram_a_again) == 0,
                 "intervening process B cannot contaminate fresh process A state");
done:
    TEST_ASSERT_EQUAL_MESSAGE(0u, assertion_failures,
                              "fresh adapter process isolation assertions pass");
}

void setUp(void) {}
void tearDown(void) {}

int main(int argc, char **argv) {
    if (argc == 3 && strcmp(argv[1], "--process-child") == 0)
        return process_child_mode(argv[2]);
    if (argc != 2) {
        (void)fprintf(stderr, "usage: libretro_mvs_state_safety_test "
            "--state-rejection|--retention\n");
        return 2;
    }
    safety_executable_path = argv[0];
    assertion_count = 0u;
    assertion_failures = 0u;
    (void)UnityBegin("libretro_mvs_state_safety_test");
    if (strcmp(argv[1], "--state-rejection") == 0) {
        RUN_TEST(state_rejection_and_continuation);
        RUN_TEST(rejected_callback_input_preserves_live_state);
        RUN_TEST(callback_restore_rejects_each_reachable_allocation_failure);
        RUN_TEST(callback_fault_keeps_capacity_and_reset_recovers);
        RUN_TEST(fresh_adapter_processes_keep_distinct_content_and_sram);
    } else if (strcmp(argv[1], "--retention") == 0) {
        RUN_TEST(retained_pointer_success_rejection_and_quiescence);
        RUN_TEST(adapter_policy_and_isolation_matrix);
    } else {
        (void)fprintf(stderr, "unknown state-safety selection: %s\n", argv[1]);
        (void)UnityEnd();
        return 2;
    }
    const int result = UnityEnd();
    (void)printf("LIBRETRO_MVS_SAFETY_COUNTS assertions=%u failures=%u\n",
                 assertion_count, assertion_failures);
    return result;
}
