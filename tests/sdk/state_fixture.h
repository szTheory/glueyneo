/* SPDX-License-Identifier: MIT */
#ifndef GLUEYNEO_SDK_STATE_FIXTURE_H
#define GLUEYNEO_SDK_STATE_FIXTURE_H

#include "glueyneo/glueyneo.h"
#include "sdk_private.h"
#include "test_support.h"

#include <stdlib.h>
#include <string.h>

/* This test fixture is generated from the original, locally authored
 * public_sound_guest.c fixture. It contains no firmware or game bytes. */
size_t public_sound_guest_size(void);
int public_sound_guest_build(uint8_t *bundle, size_t capacity);

enum {
    STATE_FIXTURE_HEADER_BYTES = 16,
    STATE_FIXTURE_REGION_COUNT = 8,
    STATE_FIXTURE_DESCRIPTOR_BYTES = 12,
    STATE_FIXTURE_WIDTH = 320,
    STATE_FIXTURE_HEIGHT = 224,
    STATE_FIXTURE_FRAMES = 4,
    STATE_FIXTURE_VARIANT_ALTERNATE = 1,
    STATE_FIXTURE_VARIANT_REVERSED_SAMPLES = 2,
    STATE_FIXTURE_VARIANT_ACTIVE_TIMER = 3
};

typedef struct {
    uint8_t *bytes;
    size_t size;
    size_t offsets[STATE_FIXTURE_REGION_COUNT];
    size_t lengths[STATE_FIXTURE_REGION_COUNT];
} state_fixture_bundle;

typedef struct {
    gn_mvs_frame_result_v1 result;
    gn_mvs_private_video_activity video;
    gn_mvs_bus_fault_observation bus;
    gn_mvs_calendar calendar;
    gn_test_mvs_sound_state sound;
    gn_test_mvs_machine_state machine;
    uint8_t guest_reply;
    uint64_t total_cycles;
    size_t audio_frames;
    uint8_t pixels[STATE_FIXTURE_WIDTH * STATE_FIXTURE_HEIGHT * 4];
    int16_t audio[GN_MVS_AUDIO_CAPACITY_FRAMES_V1 * 2];
} state_fixture_observation;

static uint32_t state_fixture_read_u32be(const uint8_t *bytes) {
    return ((uint32_t)bytes[0] << 24) | ((uint32_t)bytes[1] << 16) |
           ((uint32_t)bytes[2] << 8) | (uint32_t)bytes[3];
}

static void state_fixture_write_u32be(uint8_t *bytes, uint32_t value) {
    bytes[0] = (uint8_t)(value >> 24);
    bytes[1] = (uint8_t)(value >> 16);
    bytes[2] = (uint8_t)(value >> 8);
    bytes[3] = (uint8_t)value;
}

static int state_fixture_patch(uint8_t *region, size_t region_size,
                               const uint8_t *from, size_t length,
                               const uint8_t *to, size_t expected_count) {
    size_t count = 0u;
    for (size_t index = 0u; index + length <= region_size; ++index) {
        if (memcmp(region + index, from, length) == 0) {
            memcpy(region + index, to, length);
            ++count;
            index += length - 1u;
        }
    }
    return count == expected_count;
}

static void state_fixture_destroy(state_fixture_bundle *bundle) {
    if (bundle == NULL) return;
    if (bundle->bytes != NULL) {
        memset(bundle->bytes, 0xa5, bundle->size);
        free(bundle->bytes);
    }
    memset(bundle, 0, sizeof(*bundle));
}

static int state_fixture_build(state_fixture_bundle *bundle, unsigned variant) {
    memset(bundle, 0, sizeof(*bundle));
    bundle->size = public_sound_guest_size();
    if (bundle->size == 0u) return 0;
    bundle->bytes = (uint8_t *)malloc(bundle->size);
    if (bundle->bytes == NULL ||
        !public_sound_guest_build(bundle->bytes, bundle->size)) goto fail;

    size_t cursor = STATE_FIXTURE_HEADER_BYTES;
    for (size_t index = 0u; index < STATE_FIXTURE_REGION_COUNT; ++index) {
        if (cursor > bundle->size ||
            bundle->size - cursor < STATE_FIXTURE_DESCRIPTOR_BYTES) goto fail;
        const uint8_t *descriptor = bundle->bytes + cursor;
        if (state_fixture_read_u32be(descriptor) != index + 1u ||
            state_fixture_read_u32be(descriptor + 4u) != 0u) goto fail;
        const uint32_t length = state_fixture_read_u32be(descriptor + 8u);
        cursor += STATE_FIXTURE_DESCRIPTOR_BYTES;
        if (length == 0u || (size_t)length > bundle->size - cursor) goto fail;
        bundle->offsets[index] = cursor;
        bundle->lengths[index] = (size_t)length;
        cursor += (size_t)length;
    }
    if (cursor != bundle->size) goto fail;

    uint8_t *main_bios = bundle->bytes + bundle->offsets[0];
    uint8_t *audio_bios = bundle->bytes + bundle->offsets[6];
    static const uint8_t start_music[] = {
        0x13u, 0xfcu, 0x00u, 0x3cu, 0x00u, 0x32u, 0x00u, 0x00u
    };
    static const uint8_t start_music_variant[] = {
        0x13u, 0xfcu, 0x00u, 0x3du, 0x00u, 0x32u, 0x00u, 0x00u
    };
    static const uint8_t music_compare[] = {0x0cu, 0x00u, 0x00u, 0x3cu};
    static const uint8_t music_compare_variant[] = {
        0x0cu, 0x00u, 0x00u, 0x3du
    };
    if ((variant == STATE_FIXTURE_VARIANT_ALTERNATE ||
         variant == STATE_FIXTURE_VARIANT_REVERSED_SAMPLES) &&
        (!state_fixture_patch(main_bios, bundle->lengths[0], start_music,
                              sizeof(start_music), start_music_variant, 2u) ||
         !state_fixture_patch(main_bios, bundle->lengths[0], music_compare,
                              sizeof(music_compare), music_compare_variant, 2u)))
        goto fail;

    /* Start the Z80 from a deterministic stack, exercise its bank latch, then
     * program and service YM Timer A while the authored SSG/ADPCM guest runs. */
    static const uint8_t startup[] = {
        0x31u, 0xffu, 0xffu, 0x01u, 0x08u, 0x0au, 0xedu, 0x78u
    };
    size_t audio_cursor = sizeof(startup);
    memcpy(audio_bios, startup, sizeof(startup));
    static const uint8_t timer_setup_default[][8] = {
        {0x3eu, 0x24u, 0xd3u, 0x04u, 0x3eu, 0xffu, 0xd3u, 0x05u},
        {0x3eu, 0x25u, 0xd3u, 0x04u, 0x3eu, 0x03u, 0xd3u, 0x05u},
        {0x3eu, 0x27u, 0xd3u, 0x04u, 0x3eu, 0x05u, 0xd3u, 0x05u}
    };
    static const uint8_t timer_setup_active[][8] = {
        {0x3eu, 0x24u, 0xd3u, 0x04u, 0x3eu, 0x00u, 0xd3u, 0x05u},
        {0x3eu, 0x25u, 0xd3u, 0x04u, 0x3eu, 0x00u, 0xd3u, 0x05u},
        {0x3eu, 0x27u, 0xd3u, 0x04u, 0x3eu, 0x05u, 0xd3u, 0x05u}
    };
    const uint8_t (*timer_setup)[8] =
        variant == STATE_FIXTURE_VARIANT_ACTIVE_TIMER
            ? timer_setup_active : timer_setup_default;
    for (size_t index = 0u; index < 3u;
         ++index) {
        memcpy(audio_bios + audio_cursor, timer_setup[index],
               sizeof(timer_setup[index]));
        audio_cursor += sizeof(timer_setup[index]);
    }
    static const uint8_t finish[] = {
        0x3eu, 0x00u, 0xd3u, 0x08u, 0xedu, 0x56u,
        0xfbu, 0x76u, 0x18u, 0xfdu
    };
    if (audio_cursor + sizeof(finish) >= 0x38u) goto fail;
    memcpy(audio_bios + audio_cursor, finish, sizeof(finish));
    audio_bios[0x38u] = 0xc3u;
    audio_bios[0x39u] = 0x00u;
    audio_bios[0x3au] = 0x01u;
    static const uint8_t timer_isr_default[] = {
        0xf5u, 0x3eu, 0x27u, 0xd3u, 0x04u, 0x3eu, 0x10u, 0xd3u,
        0x05u, 0xf1u, 0xfbu, 0xedu, 0x4du
    };
    static const uint8_t timer_isr_active[] = {
        0xf5u, 0x3eu, 0x27u, 0xd3u, 0x04u, 0x3eu, 0x11u, 0xd3u,
        0x05u, 0xf1u, 0xfbu, 0xedu, 0x4du
    };
    const uint8_t *timer_isr =
        variant == STATE_FIXTURE_VARIANT_ACTIVE_TIMER
            ? timer_isr_active : timer_isr_default;
    memcpy(audio_bios + 0x100u, timer_isr, 13u);
    if (variant == STATE_FIXTURE_VARIANT_ALTERNATE ||
        variant == STATE_FIXTURE_VARIANT_REVERSED_SAMPLES) {
        static const uint8_t audio_compare[] = {0xfeu, 0x3cu};
        static const uint8_t audio_compare_variant[] = {0xfeu, 0x3du};
        static const uint8_t ssg_pitch[] = {
            0x3eu, 0x00u, 0xd3u, 0x04u, 0x3eu, 0x7du, 0xd3u, 0x05u
        };
        static const uint8_t ssg_pitch_variant[] = {
            0x3eu, 0x00u, 0xd3u, 0x04u, 0x3eu, 0x61u, 0xd3u, 0x05u
        };
        static const uint8_t adpcm_pan[] = {
            0x3eu, 0x11u, 0xd3u, 0x04u, 0x3eu, 0xc0u, 0xd3u, 0x05u
        };
        static const uint8_t adpcm_pan_variant[] = {
            0x3eu, 0x11u, 0xd3u, 0x04u, 0x3eu, 0x80u, 0xd3u, 0x05u
        };
        if (!state_fixture_patch(audio_bios, bundle->lengths[6],
                audio_compare, sizeof(audio_compare),
                audio_compare_variant, 1u) ||
            !state_fixture_patch(audio_bios, bundle->lengths[6],
                ssg_pitch, sizeof(ssg_pitch), ssg_pitch_variant, 2u) ||
            !state_fixture_patch(audio_bios, bundle->lengths[6],
                adpcm_pan, sizeof(adpcm_pan), adpcm_pan_variant, 1u))
            goto fail;
    }
    if (variant == STATE_FIXTURE_VARIANT_REVERSED_SAMPLES) {
        uint8_t *samples = bundle->bytes + bundle->offsets[4];
        for (size_t index = 0u; index < 256u; ++index)
            samples[index] = (uint8_t)((samples[index] << 4) |
                                       (samples[index] >> 4));
    }
    return 1;
fail:
    state_fixture_destroy(bundle);
    return 0;
}

static int state_fixture_reload(gn_instance *instance, unsigned variant);

static int state_fixture_load(gn_instance **out_instance, unsigned variant) {
    if (out_instance == NULL) return 0;
    *out_instance = NULL;
    if (gn_create(out_instance) != GN_STATUS_OK || *out_instance == NULL) {
        gn_destroy(*out_instance);
        *out_instance = NULL;
        return 0;
    }
    if (!state_fixture_reload(*out_instance, variant)) {
        gn_destroy(*out_instance);
        *out_instance = NULL;
        return 0;
    }
    return 1;
}

static int state_fixture_reload(gn_instance *instance, unsigned variant) {
    if (instance == NULL) return 0;
    state_fixture_bundle bundle;
    if (!state_fixture_build(&bundle, variant)) return 0;
    gn_mvs_manifest_v3 manifest;
    memset(&manifest, 0, sizeof(manifest));
    manifest.version = GN_MVS_MANIFEST_VERSION_ZOOM;
    manifest.profile = GN_MVS_PROFILE_MSX;
    manifest.region_count = STATE_FIXTURE_REGION_COUNT;
    for (size_t index = 0u; index < STATE_FIXTURE_REGION_COUNT; ++index) {
        manifest.regions[index] = (gn_mvs_region){
            (gn_mvs_region_role)(index + 1u),
            bundle.bytes + bundle.offsets[index], bundle.lengths[index],
            bundle.lengths[index], GN_MVS_LAYOUT_LINEAR};
    }
    const gn_status status = gn_load_mvs_v3(instance, &manifest);
    state_fixture_destroy(&bundle);
    return status == GN_STATUS_OK;
}

static int state_fixture_advance(gn_instance *instance, uint32_t input,
                                 state_fixture_observation *observation) {
    if (instance == NULL || observation == NULL) return 0;
    int16_t audio[GN_MVS_AUDIO_CAPACITY_FRAMES_V1 * 2u];
    memset(observation, 0, sizeof(*observation));
    const gn_mvs_frame_request_v1 request = {
        GN_MVS_FRAME_REQUEST_V1_VERSION, input, GN_PIXEL_XRGB8888,
        STATE_FIXTURE_WIDTH, STATE_FIXTURE_HEIGHT,
        STATE_FIXTURE_WIDTH * sizeof(uint32_t), observation->pixels,
        sizeof(observation->pixels), audio, GN_MVS_AUDIO_CAPACITY_FRAMES_V1
    };
    if (gn_mvs_advance_frame_v1(instance, &request, sizeof(request),
                                &observation->result,
                                sizeof(observation->result)) != GN_STATUS_OK ||
        observation->result.video_pixels_produced !=
            STATE_FIXTURE_WIDTH * STATE_FIXTURE_HEIGHT ||
        observation->result.audio_frames_generated !=
            observation->result.audio_frames_delivered ||
        observation->result.audio_frames_discarded != 0u ||
        observation->result.audio_frames_delivered >
            GN_MVS_AUDIO_CAPACITY_FRAMES_V1 ||
        gn_private_mvs_video_activity(instance, &observation->video) !=
            GN_STATUS_OK ||
        gn_observe_mvs_bus_fault(instance, &observation->bus,
                                 sizeof(observation->bus)) != GN_STATUS_OK ||
        gn_test_mvs_calendar(instance, &observation->calendar) != GN_STATUS_OK ||
        gn_test_mvs_sound_state_read(instance, &observation->sound) !=
            GN_STATUS_OK ||
        gn_test_mvs_machine_state_read(instance, &observation->machine) !=
            GN_STATUS_OK ||
        gn_test_mvs_read_bus8(instance, UINT32_C(0x320000),
                              &observation->guest_reply) != GN_STATUS_OK)
        return 0;
    observation->audio_frames = observation->result.audio_frames_delivered;
    memcpy(observation->audio, audio,
           observation->audio_frames * 2u * sizeof(int16_t));
    observation->total_cycles = observation->result.elapsed_cycles;
    return 1;
}

static int state_fixture_observation_equal(
    const state_fixture_observation *left,
    const state_fixture_observation *right) {
    if (left == NULL || right == NULL ||
        memcmp(&left->result, &right->result, sizeof(left->result)) != 0 ||
        memcmp(left->pixels, right->pixels, sizeof(left->pixels)) != 0 ||
        left->audio_frames != right->audio_frames ||
        memcmp(left->audio, right->audio,
               left->audio_frames * 2u * sizeof(int16_t)) != 0 ||
        left->guest_reply != right->guest_reply ||
        left->total_cycles != right->total_cycles ||
        memcmp(&left->video, &right->video, sizeof(left->video)) != 0 ||
        memcmp(&left->bus, &right->bus, sizeof(left->bus)) != 0 ||
        memcmp(&left->calendar, &right->calendar, sizeof(left->calendar)) != 0)
        return 0;
    if (memcmp(&left->machine, &right->machine,
               sizeof(left->machine)) != 0) return 0;
    gn_test_mvs_sound_state a = left->sound;
    gn_test_mvs_sound_state b = right->sound;
    a.main_cycles_advanced = b.main_cycles_advanced = 0u;
    a.ym_input_clocks = b.ym_input_clocks = 0u;
    a.native_samples = b.native_samples = 0u;
    a.irq_assertions = b.irq_assertions = 0u;
    a.irq_deassertions = b.irq_deassertions = 0u;
    a.bank_changes = b.bank_changes = 0u;
    memset(a.timer_register_writes, 0, sizeof(a.timer_register_writes));
    memset(b.timer_register_writes, 0, sizeof(b.timer_register_writes));
    a.ym_clock_remainder = b.ym_clock_remainder = 0u;
    return memcmp(&a, &b, sizeof(a)) == 0;
}

static int state_fixture_capture(gn_instance *instance, uint8_t **out_state,
                                 size_t *out_size) {
    *out_state = NULL;
    *out_size = 0u;
    size_t capacity = 0u;
    if (gn_state_capacity_v1(instance, &capacity) != GN_STATUS_OK ||
        capacity == 0u) return 0;
    if (capacity > SIZE_MAX - 16u) return 0;
    uint8_t *state = (uint8_t *)malloc(capacity + 16u);
    if (state == NULL) return 0;
    memset(state + capacity, 0x5au, 16u);
    size_t written = 0u;
    gn_state_detail_v1 detail;
    if (gn_state_capture_v1(instance, state, capacity, &written, &detail,
                            sizeof(detail)) != GN_STATUS_OK ||
        written != capacity) {
        free(state);
        return 0;
    }
    *out_state = state;
    *out_size = written;
    return 1;
}

static int state_fixture_guard_valid(const uint8_t *state, size_t size) {
    if (state == NULL) return 0;
    for (size_t index = 0u; index < 16u; ++index) {
        if (state[size + index] != 0x5au) return 0;
    }
    return 1;
}

static int state_fixture_restore(gn_instance *instance, const uint8_t *state,
                                 size_t size) {
    gn_state_detail_v1 detail;
    return gn_state_restore_v1(instance, state, size, &detail,
                               sizeof(detail)) == GN_STATUS_OK;
}

#endif
