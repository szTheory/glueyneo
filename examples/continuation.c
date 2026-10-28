/* SPDX-License-Identifier: MIT; original public SDK continuation example. */
#include <glueyneo/glueyneo.h>

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

enum {
    WIDTH = 320,
    HEIGHT = 224,
    REGION_COUNT = 8,
    BUNDLE_HEADER_SIZE = 16,
    REGION_DESCRIPTOR_SIZE = 12,
    FUTURE_FRAME_COUNT = 3,
    MAX_STATE_BYTES = 4 * 1024 * 1024,
    MAX_TRACE_BYTES = 2 * 1024 * 1024
};

#define PIXEL_COUNT ((size_t)WIDTH * (size_t)HEIGHT)
#define PIXEL_BYTES (PIXEL_COUNT * sizeof(uint32_t))
#define BUNDLE_LIMIT ((size_t)GN_MVS_MAX_MEDIA_BYTES + BUNDLE_HEADER_SIZE + \
                      REGION_COUNT * REGION_DESCRIPTOR_SIZE)

static const uint32_t FUTURE_INPUTS[FUTURE_FRAME_COUNT] = {
    0u, GN_MVS_INPUT_P1_A, 0u
};

static uint32_t read_be32(const uint8_t *bytes) {
    return (uint32_t)bytes[0] << 24 | (uint32_t)bytes[1] << 16 |
           (uint32_t)bytes[2] << 8 | (uint32_t)bytes[3];
}

static uint8_t *read_bundle(const char *path, size_t *out_size) {
    FILE *file = fopen(path, "rb");
    if (file == NULL) return NULL;
    if (fseek(file, 0, SEEK_END) != 0) {
        (void)fclose(file);
        return NULL;
    }
    const long end = ftell(file);
    if (end < BUNDLE_HEADER_SIZE || (unsigned long)end > BUNDLE_LIMIT ||
        fseek(file, 0, SEEK_SET) != 0) {
        (void)fclose(file);
        return NULL;
    }
    const size_t size = (size_t)end;
    uint8_t *bytes = (uint8_t *)malloc(size);
    if (bytes == NULL) {
        (void)fclose(file);
        return NULL;
    }
    const size_t read_count = fread(bytes, 1u, size, file);
    const int trailing = fgetc(file);
    const int close_status = fclose(file);
    if (read_count != size || trailing != EOF || close_status != 0) {
        free(bytes);
        return NULL;
    }
    *out_size = size;
    return bytes;
}

static int parse_bundle(const uint8_t *bytes, size_t size,
                        gn_mvs_manifest_v3 *manifest) {
    if (size < BUNDLE_HEADER_SIZE || memcmp(bytes, "GNMV", 4u) != 0 ||
        read_be32(bytes + 4u) != GN_MVS_MANIFEST_VERSION_ZOOM ||
        read_be32(bytes + 8u) != GN_MVS_PROFILE_MSX ||
        read_be32(bytes + 12u) != REGION_COUNT || manifest == NULL) {
        return 0;
    }

    memset(manifest, 0, sizeof(*manifest));
    manifest->version = GN_MVS_MANIFEST_VERSION_ZOOM;
    manifest->profile = GN_MVS_PROFILE_MSX;
    manifest->region_count = REGION_COUNT;
    size_t offset = BUNDLE_HEADER_SIZE;
    for (size_t i = 0u; i < REGION_COUNT; ++i) {
        if (offset > size || size - offset < REGION_DESCRIPTOR_SIZE) return 0;
        const uint32_t role = read_be32(bytes + offset);
        const uint32_t high_size = read_be32(bytes + offset + 4u);
        const uint32_t region_size = read_be32(bytes + offset + 8u);
        offset += REGION_DESCRIPTOR_SIZE;
        if (role != i + 1u || high_size != 0u || region_size == 0u ||
            (size_t)region_size > size - offset) {
            return 0;
        }
        manifest->regions[i] = (gn_mvs_region){
            (gn_mvs_region_role)role, bytes + offset, region_size,
            region_size, GN_MVS_LAYOUT_LINEAR
        };
        offset += (size_t)region_size;
    }
    return offset == size;
}

static int load_bundle(gn_instance *instance, const uint8_t *bytes,
                       size_t size) {
    gn_mvs_manifest_v3 manifest;
    return parse_bundle(bytes, size, &manifest) &&
           gn_load_mvs_v3(instance, &manifest) == GN_STATUS_OK;
}

static uint8_t *make_foreign_bundle(const uint8_t *bytes, size_t size) {
    uint8_t *foreign = (uint8_t *)malloc(size);
    if (foreign == NULL) return NULL;
    memcpy(foreign, bytes, size);
    gn_mvs_manifest_v3 manifest;
    if (!parse_bundle(foreign, size, &manifest)) {
        free(foreign);
        return NULL;
    }
    for (size_t i = 0u; i < manifest.region_count; ++i) {
        if (manifest.regions[i].role == GN_MVS_REGION_SAMPLES &&
            manifest.regions[i].source_size > 0u) {
            uint8_t *sample_bytes = (uint8_t *)manifest.regions[i].source;
            sample_bytes[manifest.regions[i].source_size - 1u] ^= UINT8_C(1);
            return foreign;
        }
    }
    free(foreign);
    return NULL;
}

static int write_le(FILE *file, uint64_t value, size_t width) {
    for (size_t i = 0u; i < width; ++i) {
        if (fputc((int)(value & UINT64_C(0xff)), file) == EOF) return 0;
        value >>= 8;
    }
    return 1;
}

static int write_frame(FILE *file, uint32_t input_mask,
                       const gn_mvs_frame_result_v1 *result,
                       const uint32_t *pixels, const int16_t *audio) {
    if (!write_le(file, input_mask, 4u) ||
        !write_le(file, result->elapsed_cycles, 8u) ||
        !write_le(file, result->audio_frames_delivered, 4u) ||
        !write_le(file, result->video_pixels_produced, 4u)) {
        return 0;
    }
    for (size_t i = 0u; i < PIXEL_COUNT; ++i) {
        if (!write_le(file, pixels[i], 4u)) return 0;
    }
    const size_t sample_count = result->audio_frames_delivered * 2u;
    for (size_t i = 0u; i < sample_count; ++i) {
        if (!write_le(file, (uint16_t)audio[i], 2u)) return 0;
    }
    return 1;
}

static int tone_present(const int16_t *audio, size_t frames) {
    if (frames < 800u) return 0;
    int64_t best = 0;
    for (size_t phase = 0u; phase < 48u; ++phase) {
        int64_t correlation = 0;
        for (size_t i = 32u; i < 800u; ++i) {
            if (audio[2u * i] != audio[2u * i + 1u]) return 0;
            const int sign = ((i + phase) % 48u < 24u) ? 1 : -1;
            correlation += (int64_t)audio[2u * i] * sign;
        }
        if (correlation < 0) correlation = -correlation;
        if (correlation > best) best = correlation;
    }
    return best / 768 >= 256;
}

static int advance(gn_instance *instance, uint32_t input_mask,
                   uint32_t *pixels, int16_t *audio, size_t audio_capacity,
                   gn_mvs_frame_result_v1 *result) {
    const gn_mvs_frame_request_v1 request = {
        GN_MVS_FRAME_REQUEST_V1_VERSION,
        input_mask,
        GN_PIXEL_XRGB8888,
        WIDTH,
        HEIGHT,
        WIDTH * sizeof(uint32_t),
        (uint8_t *)pixels,
        PIXEL_BYTES,
        audio,
        audio_capacity
    };
    memset(result, 0, sizeof(*result));
    if (gn_mvs_advance_frame_v1(instance, &request, sizeof(request), result,
                                sizeof(*result)) != GN_STATUS_OK) {
        return 0;
    }
    return result->version == GN_MVS_FRAME_RESULT_V1_VERSION &&
           result->elapsed_cycles > 0u && result->audio_sample_rate == 48000u &&
           result->audio_channels == 2u &&
           result->audio_frames_generated >= 800u &&
           result->audio_frames_generated <= audio_capacity &&
           result->audio_frames_delivered == result->audio_frames_generated &&
           result->audio_frames_discarded == 0u &&
           result->video_pixels_produced == PIXEL_COUNT &&
           pixels[0] == 0u && pixels[1] == UINT32_C(0x00ffffff);
}

static int same_frame(const gn_mvs_frame_result_v1 *left,
                      const gn_mvs_frame_result_v1 *right,
                      const uint32_t *left_pixels, const uint32_t *right_pixels,
                      const int16_t *left_audio, const int16_t *right_audio) {
    return left->requested_cycles == right->requested_cycles &&
           left->elapsed_cycles == right->elapsed_cycles &&
           left->instructions == right->instructions &&
           left->reason == right->reason &&
           left->audio_format == right->audio_format &&
           left->audio_sample_rate == right->audio_sample_rate &&
           left->audio_channels == right->audio_channels &&
           left->audio_frames_generated == right->audio_frames_generated &&
           left->audio_frames_discarded == right->audio_frames_discarded &&
           left->audio_frames_delivered == right->audio_frames_delivered &&
           left->video_pixels_produced == right->video_pixels_produced &&
           memcmp(left_pixels, right_pixels, PIXEL_BYTES) == 0 &&
           memcmp(left_audio, right_audio,
                  left->audio_frames_delivered * 2u * sizeof(*left_audio)) == 0;
}

static int read_file(const char *path, size_t limit, uint8_t **out_bytes,
                     size_t *out_size) {
    *out_bytes = NULL;
    *out_size = 0u;
    FILE *file = fopen(path, "rb");
    if (file == NULL) return 0;
    if (fseek(file, 0, SEEK_END) != 0) {
        (void)fclose(file);
        return 0;
    }
    const long end = ftell(file);
    if (end <= 0 || (unsigned long)end > limit ||
        fseek(file, 0, SEEK_SET) != 0) {
        (void)fclose(file);
        return 0;
    }
    const size_t size = (size_t)end;
    uint8_t *bytes = (uint8_t *)malloc(size);
    if (bytes == NULL) {
        (void)fclose(file);
        return 0;
    }
    const size_t read_count = fread(bytes, 1u, size, file);
    const int trailing = fgetc(file);
    const int close_status = fclose(file);
    if (read_count != size || trailing != EOF || close_status != 0) {
        free(bytes);
        return 0;
    }
    *out_bytes = bytes;
    *out_size = size;
    return 1;
}

static int write_file(const char *path, const uint8_t *bytes, size_t size) {
    FILE *file = fopen(path, "wb");
    if (file == NULL) return 0;
    const int written = fwrite(bytes, 1u, size, file) == size;
    const int closed = fclose(file) == 0;
    return written && closed;
}

static int capture_state(gn_instance *instance, uint8_t **out_state,
                         size_t *out_size) {
    *out_state = NULL;
    *out_size = 0u;
    size_t capacity = 0u;
    if (gn_state_capacity_v1(instance, &capacity) != GN_STATUS_OK ||
        capacity == 0u || capacity > MAX_STATE_BYTES) {
        return 0;
    }
    uint8_t *state = (uint8_t *)malloc(capacity);
    if (state == NULL) return 0;
    size_t written = 0u;
    if (gn_state_capture_v1(instance, state, capacity, &written, NULL, 0u) !=
            GN_STATUS_OK || written != capacity) {
        free(state);
        return 0;
    }
    *out_state = state;
    *out_size = written;
    return 1;
}

static int restore_valid_state(gn_instance *destination, const uint8_t *state,
                               size_t state_size) {
    gn_state_detail_v1 detail;
    memset(&detail, 0, sizeof(detail));
    detail.size = sizeof(detail);
    return gn_state_restore_v1(destination, state, state_size,
                               &detail, sizeof(detail)) == GN_STATUS_OK;
}

static int capture_equals(gn_instance *instance, const uint8_t *expected,
                          size_t expected_size) {
    uint8_t *actual = NULL;
    size_t actual_size = 0u;
    const int captured = capture_state(instance, &actual, &actual_size);
    const int equal = captured && actual_size == expected_size &&
                      memcmp(actual, expected, expected_size) == 0;
    free(actual);
    return equal;
}

static int write_trace_header(FILE *file) {
    return fwrite("GNCT", 1u, 4u, file) == 4u && write_le(file, 1u, 4u) &&
           write_le(file, FUTURE_FRAME_COUNT, 4u);
}

static int run_future_trace(gn_instance *control, gn_instance *restored,
                            gn_instance *peer, uint32_t *control_pixels,
                            uint32_t *restored_pixels, uint32_t *peer_pixels,
                            int16_t *control_audio, int16_t *restored_audio,
                            int16_t *peer_audio, size_t audio_capacity,
                            uint64_t warm_cycles, const char *trace_path,
                            size_t *out_assertions, size_t *out_audio_frames,
                            size_t *out_nonzero_samples,
                            uint64_t *out_elapsed_cycles) {
    FILE *trace = fopen(trace_path, "wb");
    if (trace == NULL) return 0;
    int ok = write_trace_header(trace);
    size_t assertions = 10u;
    size_t total_audio_frames = 0u;
    size_t nonzero_samples = 0u;
    uint64_t elapsed_cycles = warm_cycles;
    int tone_ok = 0, fire_ok = 0, release_ok = 0;
    int16_t neutral[GN_MVS_AUDIO_CAPACITY_FRAMES_V1 * 2u];
    int16_t fired[GN_MVS_AUDIO_CAPACITY_FRAMES_V1 * 2u];
    size_t neutral_frames = 0u, fire_frames = 0u;

    for (size_t frame = 0u; ok && frame < FUTURE_FRAME_COUNT; ++frame) {
        gn_mvs_frame_result_v1 control_result, restored_result, peer_result;
        ok = advance(control, FUTURE_INPUTS[frame], control_pixels,
                     control_audio, audio_capacity, &control_result);
        if (ok && restored != NULL) {
            ok = advance(restored, FUTURE_INPUTS[frame], restored_pixels,
                         restored_audio, audio_capacity, &restored_result) &&
                 same_frame(&control_result, &restored_result, control_pixels,
                            restored_pixels, control_audio, restored_audio);
            assertions += 5u;
        }
        if (ok && peer != NULL) {
            ok = advance(peer, FUTURE_INPUTS[frame], peer_pixels,
                         peer_audio, audio_capacity, &peer_result) &&
                 same_frame(&control_result, &peer_result, control_pixels,
                            peer_pixels, control_audio, peer_audio);
            assertions += 5u;
        }
        if (!ok || !write_frame(trace, FUTURE_INPUTS[frame], &control_result,
                                control_pixels, control_audio)) {
            ok = 0;
            break;
        }
        assertions += 4u;
        total_audio_frames += control_result.audio_frames_delivered;
        elapsed_cycles += control_result.elapsed_cycles;
        for (size_t i = 0u; i < control_result.audio_frames_delivered * 2u; ++i)
            nonzero_samples += control_audio[i] != 0;
        if (frame == 0u) {
            tone_ok = tone_present(control_audio,
                                   control_result.audio_frames_delivered);
            neutral_frames = control_result.audio_frames_delivered;
            memcpy(neutral, control_audio,
                   neutral_frames * 2u * sizeof(*neutral));
            ok = tone_ok;
        } else if (frame == 1u) {
            fire_ok = control_result.audio_frames_delivered == neutral_frames &&
                      memcmp(neutral, control_audio,
                             neutral_frames * 2u * sizeof(*neutral)) != 0;
            fire_frames = control_result.audio_frames_delivered;
            memcpy(fired, control_audio, fire_frames * 2u * sizeof(*fired));
            ok = fire_ok;
        } else {
            release_ok = control_result.audio_frames_delivered == fire_frames &&
                         tone_present(control_audio,
                                      control_result.audio_frames_delivered) &&
                         memcmp(fired, control_audio,
                                fire_frames * 2u * sizeof(*fired)) != 0;
            ok = release_ok;
        }
        assertions += 3u;
    }
    if (fclose(trace) != 0) ok = 0;
    ok = ok && tone_ok && fire_ok && release_ok && total_audio_frames > 0u &&
         nonzero_samples > 0u;
    if (ok) {
        assertions += 6u;
        *out_assertions = assertions;
        *out_audio_frames = total_audio_frames;
        *out_nonzero_samples = nonzero_samples;
        *out_elapsed_cycles = elapsed_cycles;
    }
    return ok;
}

static int run_process_producer(const char *media_path, const char *state_path,
                                const char *trace_path) {
    uint8_t *media = NULL, *state = NULL;
    size_t media_size = 0u, state_size = 0u, audio_capacity = 0u;
    uint32_t *pixels = NULL;
    int16_t *audio = NULL;
    gn_instance *instance = NULL;
    int exit_code = 1;
    size_t assertions = 0u, audio_frames = 0u, nonzero_samples = 0u;
    uint64_t elapsed_cycles = 0u;
    if (!read_file(media_path, BUNDLE_LIMIT, &media, &media_size)) {
        exit_code = 2;
        goto done;
    }
    pixels = (uint32_t *)malloc(PIXEL_BYTES);
    if (pixels == NULL || gn_create(&instance) != GN_STATUS_OK ||
        !load_bundle(instance, media, media_size) ||
        gn_mvs_audio_capacity_v1(instance, &audio_capacity) != GN_STATUS_OK ||
        audio_capacity != GN_MVS_AUDIO_CAPACITY_FRAMES_V1) {
        exit_code = 2;
        goto done;
    }
    audio = (int16_t *)malloc(audio_capacity * 2u * sizeof(*audio));
    if (audio == NULL) {
        exit_code = 2;
        goto done;
    }
    gn_mvs_frame_result_v1 warm;
    if (!advance(instance, 0u, pixels, audio, audio_capacity, &warm) ||
        !capture_state(instance, &state, &state_size)) {
        goto done;
    }
    if (!write_file(state_path, state, state_size)) {
        exit_code = 2;
        goto done;
    }
    if (!run_future_trace(instance, NULL, NULL, pixels, NULL, NULL, audio,
                          NULL, NULL, audio_capacity, warm.elapsed_cycles,
                          trace_path, &assertions, &audio_frames,
                          &nonzero_samples, &elapsed_cycles)) {
        goto done;
    }
    printf("SDK_CONTINUATION {\"schema_version\":1,\"case_id\":\"sdk.continuation.process\","
           "\"role\":\"producer\",\"outcome\":\"pass\",\"assertions\":%zu,"
           "\"frames\":%u,\"elapsed_cycles\":%llu,\"state_bytes\":%zu,"
           "\"audio_frames\":%zu,\"nonzero_audio_samples\":%zu}\n",
           assertions, FUTURE_FRAME_COUNT, (unsigned long long)elapsed_cycles,
           state_size, audio_frames, nonzero_samples);
    exit_code = 0;
done:
    gn_destroy(instance);
    free(media);
    free(state);
    free(pixels);
    free(audio);
    if (exit_code != 0) fputs("installed continuation producer failed\n", stderr);
    return exit_code;
}

static int run_process_consumer(const char *media_path, const char *state_path,
                                const char *expected_trace_path,
                                const char *observed_trace_path) {
    uint8_t *media = NULL, *state = NULL, *foreign_media = NULL;
    uint8_t *foreign_state = NULL;
    uint8_t *expected_trace = NULL, *observed_trace = NULL;
    uint8_t *peer_state_before = NULL;
    size_t media_size = 0u, state_size = 0u, foreign_size = 0u;
    size_t expected_trace_size = 0u, observed_trace_size = 0u;
    size_t peer_state_before_size = 0u;
    size_t audio_capacity = 0u, state_capacity = 0u;
    uint32_t *control_pixels = NULL, *destination_pixels = NULL, *peer_pixels = NULL;
    int16_t *control_audio = NULL, *destination_audio = NULL, *peer_audio = NULL;
    gn_instance *control = NULL, *destination = NULL, *peer = NULL, *foreign = NULL;
    int exit_code = 1;
    gn_status truncated_status = GN_STATUS_OK, foreign_status = GN_STATUS_OK;
    gn_state_reason truncated_reason = GN_STATE_REASON_NONE;
    gn_state_reason foreign_reason = GN_STATE_REASON_NONE;
    size_t assertions = 0u, audio_frames = 0u, nonzero_samples = 0u;
    uint64_t elapsed_cycles = 0u;
    if (!read_file(media_path, BUNDLE_LIMIT, &media, &media_size) ||
        !read_file(state_path, MAX_STATE_BYTES, &state, &state_size) ||
        !read_file(expected_trace_path, MAX_TRACE_BYTES, &expected_trace,
                   &expected_trace_size)) {
        exit_code = 2;
        goto done;
    }
    if (expected_trace_size < 12u || memcmp(expected_trace, "GNCT", 4u) != 0 ||
        expected_trace[4] != 1u || expected_trace[5] != 0u ||
        expected_trace[6] != 0u || expected_trace[7] != 0u ||
        expected_trace[8] != FUTURE_FRAME_COUNT || expected_trace[9] != 0u ||
        expected_trace[10] != 0u || expected_trace[11] != 0u) {
        exit_code = 2;
        goto done;
    }

    control_pixels = (uint32_t *)malloc(PIXEL_BYTES);
    destination_pixels = (uint32_t *)malloc(PIXEL_BYTES);
    peer_pixels = (uint32_t *)malloc(PIXEL_BYTES);
    if (control_pixels == NULL || destination_pixels == NULL || peer_pixels == NULL ||
        gn_create(&control) != GN_STATUS_OK || gn_create(&destination) != GN_STATUS_OK ||
        gn_create(&peer) != GN_STATUS_OK || gn_create(&foreign) != GN_STATUS_OK ||
        !load_bundle(control, media, media_size) ||
        !load_bundle(destination, media, media_size) ||
        !load_bundle(peer, media, media_size) ||
        gn_mvs_audio_capacity_v1(control, &audio_capacity) != GN_STATUS_OK ||
        audio_capacity != GN_MVS_AUDIO_CAPACITY_FRAMES_V1 ||
        gn_state_capacity_v1(control, &state_capacity) != GN_STATUS_OK ||
        state_capacity == 0u || state_capacity != state_size ||
        state_capacity > MAX_STATE_BYTES) {
        exit_code = 2;
        goto done;
    }
    audio_capacity = GN_MVS_AUDIO_CAPACITY_FRAMES_V1;
    control_audio = (int16_t *)malloc(audio_capacity * 2u * sizeof(*control_audio));
    destination_audio = (int16_t *)malloc(audio_capacity * 2u * sizeof(*destination_audio));
    peer_audio = (int16_t *)malloc(audio_capacity * 2u * sizeof(*peer_audio));
    if (control_audio == NULL || destination_audio == NULL || peer_audio == NULL) {
        exit_code = 2;
        goto done;
    }

    gn_mvs_frame_result_v1 control_warm, peer_warm;
    if (control_audio == NULL || destination_audio == NULL || peer_audio == NULL ||
        !advance(control, 0u, control_pixels, control_audio, audio_capacity,
                 &control_warm) ||
        !advance(peer, 0u, peer_pixels, peer_audio, audio_capacity, &peer_warm)) {
        goto done;
    }
    if (control_warm.elapsed_cycles != peer_warm.elapsed_cycles ||
        !same_frame(&control_warm, &peer_warm, control_pixels, peer_pixels,
                    control_audio, peer_audio)) {
        goto done;
    }
    if (!capture_state(peer, &peer_state_before, &peer_state_before_size))
        goto done;
    assertions += 7u;

    gn_state_detail_v1 detail;
    memset(&detail, 0, sizeof(detail));
    detail.size = sizeof(detail);
    truncated_status = gn_state_restore_v1(peer, state, state_size - 1u,
                                           &detail, sizeof(detail));
    truncated_reason = detail.reason;
    if (truncated_status != GN_STATUS_INVALID_ARGUMENT ||
        truncated_reason != GN_STATE_REASON_TRUNCATED ||
        !capture_equals(peer, peer_state_before, peer_state_before_size)) {
        goto done;
    }
    assertions += 3u;

    foreign_media = make_foreign_bundle(media, media_size);
    if (foreign_media == NULL || !load_bundle(foreign, foreign_media, media_size) ||
        !capture_state(foreign, &foreign_state, &foreign_size) ||
        foreign_size != state_capacity) {
        goto done;
    }
    memset(&detail, 0, sizeof(detail));
    detail.size = sizeof(detail);
    foreign_status = gn_state_restore_v1(peer, foreign_state, foreign_size,
                                         &detail, sizeof(detail));
    foreign_reason = detail.reason;
    if (foreign_status != GN_STATUS_INVALID_MEDIA ||
        foreign_reason != GN_STATE_REASON_MEDIA_IDENTITY ||
        !capture_equals(peer, peer_state_before, peer_state_before_size)) {
        goto done;
    }
    assertions += 4u;

    if (!restore_valid_state(destination, state, state_size) ||
        !restore_valid_state(destination, state, state_size) ||
        !capture_equals(destination, state, state_size) ||
        !capture_equals(peer, peer_state_before, peer_state_before_size)) {
        goto done;
    }
    assertions += 4u;

    if (!run_future_trace(control, destination, peer, control_pixels,
                          destination_pixels, peer_pixels, control_audio,
                          destination_audio, peer_audio, audio_capacity,
                          control_warm.elapsed_cycles, observed_trace_path,
                          &assertions, &audio_frames, &nonzero_samples,
                          &elapsed_cycles) ||
        !read_file(observed_trace_path, MAX_TRACE_BYTES, &observed_trace,
                   &observed_trace_size) ||
        observed_trace_size != expected_trace_size ||
        memcmp(observed_trace, expected_trace, expected_trace_size) != 0) {
        goto done;
    }
    assertions += 4u;
    printf("SDK_CONTINUATION {\"schema_version\":1,\"case_id\":\"sdk.continuation.process\","
           "\"role\":\"reader\",\"outcome\":\"pass\",\"assertions\":%zu,"
           "\"frames\":%u,\"elapsed_cycles\":%llu,\"audio_frames\":%zu,"
           "\"truncated_status\":%u,\"truncated_reason\":%u,"
           "\"foreign_status\":%u,\"foreign_reason\":%u,"
           "\"control\":\"pass\"}\n",
           assertions, FUTURE_FRAME_COUNT, (unsigned long long)elapsed_cycles,
           audio_frames, (unsigned)truncated_status, (unsigned)truncated_reason,
           (unsigned)foreign_status, (unsigned)foreign_reason);
    exit_code = 0;
done:
    gn_destroy(control);
    gn_destroy(destination);
    gn_destroy(peer);
    gn_destroy(foreign);
    free(media);
    free(state);
    free(foreign_media);
    free(foreign_state);
    free(expected_trace);
    free(observed_trace);
    free(peer_state_before);
    free(control_pixels);
    free(destination_pixels);
    free(peer_pixels);
    free(control_audio);
    free(destination_audio);
    free(peer_audio);
    if (exit_code != 0) fputs("installed continuation reader failed\n", stderr);
    return exit_code;
}

static int run_instance_mode(const char *media_path, const char *trace_path) {

    int exit_code = 1;
    size_t media_size = 0u;
    size_t audio_capacity = 0u;
    size_t state_capacity = 0u;
    size_t state_written = 0u;
    uint8_t *media = read_bundle(media_path, &media_size);
    uint8_t *state = NULL;
    uint8_t *destination_before = NULL;
    uint8_t *destination_after = NULL;
    uint32_t *source_pixels = NULL;
    uint32_t *destination_pixels = NULL;
    int16_t *source_audio = NULL;
    int16_t *destination_audio = NULL;
    gn_instance *source = NULL;
    gn_instance *destination = NULL;
    FILE *trace = NULL;

    if (media == NULL) {
        exit_code = 2;
        goto done;
    }
    source_pixels = (uint32_t *)malloc(PIXEL_BYTES);
    destination_pixels = (uint32_t *)malloc(PIXEL_BYTES);
    if (source_pixels == NULL || destination_pixels == NULL ||
        gn_create(&source) != GN_STATUS_OK || gn_create(&destination) != GN_STATUS_OK ||
        !load_bundle(source, media, media_size) ||
        !load_bundle(destination, media, media_size) ||
        gn_mvs_audio_capacity_v1(source, &audio_capacity) != GN_STATUS_OK ||
        audio_capacity != GN_MVS_AUDIO_CAPACITY_FRAMES_V1) {
        exit_code = 2;
        goto done;
    }
    source_audio = (int16_t *)malloc(audio_capacity * 2u * sizeof(*source_audio));
    destination_audio = (int16_t *)malloc(audio_capacity * 2u * sizeof(*destination_audio));
    if (source_audio == NULL || destination_audio == NULL ||
        gn_state_capacity_v1(source, &state_capacity) != GN_STATUS_OK ||
        state_capacity == 0u) {
        exit_code = 2;
        goto done;
    }
    size_t destination_capacity = 0u;
    if (gn_state_capacity_v1(destination, &destination_capacity) != GN_STATUS_OK ||
        destination_capacity != state_capacity) {
        exit_code = 1;
        goto done;
    }
    state = (uint8_t *)malloc(state_capacity);
    destination_before = (uint8_t *)malloc(state_capacity);
    destination_after = (uint8_t *)malloc(state_capacity);
    if (state == NULL || destination_before == NULL || destination_after == NULL) {
        exit_code = 2;
        goto done;
    }

    gn_mvs_frame_result_v1 warm_result;
    if (!advance(source, 0u, source_pixels, source_audio, audio_capacity,
                 &warm_result) ||
        gn_state_capture_v1(source, state, state_capacity, &state_written,
                            NULL, 0u) != GN_STATUS_OK ||
        state_written != state_capacity ||
        gn_state_capture_v1(destination, destination_before, state_capacity,
                            &state_written, NULL, 0u) != GN_STATUS_OK ||
        state_written != state_capacity) {
        goto done;
    }

    gn_state_detail_v1 detail;
    memset(&detail, 0, sizeof(detail));
    detail.size = sizeof(detail);
    if (gn_state_restore_v1(destination, state, state_capacity - 1u, &detail,
                            sizeof(detail)) != GN_STATUS_INVALID_ARGUMENT ||
        detail.reason != GN_STATE_REASON_TRUNCATED ||
        gn_state_capture_v1(destination, destination_after, state_capacity,
                            &state_written, NULL, 0u) != GN_STATUS_OK ||
        state_written != state_capacity ||
        memcmp(destination_before, destination_after, state_capacity) != 0) {
        goto done;
    }
    if (!restore_valid_state(destination, state, state_capacity) ||
        gn_state_capture_v1(destination, destination_after, state_capacity,
                            &state_written, NULL, 0u) != GN_STATUS_OK ||
        state_written != state_capacity ||
        memcmp(state, destination_after, state_capacity) != 0) {
        goto done;
    }

    trace = fopen(trace_path, "wb");
    if (trace == NULL) {
        exit_code = 2;
        goto done;
    }
    if (fwrite("GNCT", 1u, 4u, trace) != 4u || !write_le(trace, 1u, 4u) ||
        !write_le(trace, FUTURE_FRAME_COUNT, 4u)) {
        goto done;
    }

    size_t total_audio_frames = 0u;
    size_t nonzero_audio_samples = 0u;
    uint64_t total_elapsed_cycles = warm_result.elapsed_cycles;
    size_t assertions = 12u;
    int tone_ok = 0;
    int fire_ok = 0;
    int release_ok = 0;
    int16_t neutral_audio[GN_MVS_AUDIO_CAPACITY_FRAMES_V1 * 2u];
    int16_t fire_audio[GN_MVS_AUDIO_CAPACITY_FRAMES_V1 * 2u];
    size_t neutral_frames = 0u;
    size_t fire_frames = 0u;
    for (size_t frame = 0u; frame < FUTURE_FRAME_COUNT; ++frame) {
        gn_mvs_frame_result_v1 source_result;
        gn_mvs_frame_result_v1 destination_result;
        if (!advance(source, FUTURE_INPUTS[frame], source_pixels, source_audio,
                     audio_capacity, &source_result) ||
            !advance(destination, FUTURE_INPUTS[frame], destination_pixels,
                     destination_audio, audio_capacity, &destination_result)) {
            goto done;
        }
        assertions += 4u;
        if (!same_frame(&source_result, &destination_result, source_pixels,
                        destination_pixels, source_audio, destination_audio) ||
            !write_frame(trace, FUTURE_INPUTS[frame], &source_result,
                         source_pixels, source_audio)) {
            goto done;
        }
        assertions += 2u;
        total_audio_frames += source_result.audio_frames_delivered;
        total_elapsed_cycles += source_result.elapsed_cycles;
        for (size_t i = 0u; i < source_result.audio_frames_delivered * 2u; ++i) {
            if (source_audio[i] != 0) ++nonzero_audio_samples;
        }
        if (frame == 0u) {
            tone_ok = tone_present(source_audio, source_result.audio_frames_delivered);
            neutral_frames = source_result.audio_frames_delivered;
            memcpy(neutral_audio, source_audio,
                   neutral_frames * 2u * sizeof(*neutral_audio));
            if (!tone_ok) goto done;
        } else if (frame == 1u) {
            fire_ok = source_result.audio_frames_delivered == neutral_frames &&
                      memcmp(neutral_audio, source_audio,
                             neutral_frames * 2u * sizeof(*neutral_audio)) != 0;
            fire_frames = source_result.audio_frames_delivered;
            memcpy(fire_audio, source_audio, fire_frames * 2u * sizeof(*fire_audio));
            if (!fire_ok) goto done;
        } else {
            release_ok = source_result.audio_frames_delivered == fire_frames &&
                         tone_present(source_audio, source_result.audio_frames_delivered) &&
                         memcmp(fire_audio, source_audio,
                                fire_frames * 2u * sizeof(*fire_audio)) != 0;
            if (!release_ok) goto done;
        }
        assertions += 3u;
    }
    if (fclose(trace) != 0) {
        trace = NULL;
        goto done;
    }
    trace = NULL;
    if (total_audio_frames == 0u || nonzero_audio_samples == 0u ||
        !tone_ok || !fire_ok || !release_ok) {
        goto done;
    }
    assertions += 6u;
    printf("SDK_CONTINUATION {\"schema_version\":1,\"case_id\":\"sdk.continuation.instance\","
           "\"outcome\":\"pass\",\"assertions\":%zu,\"frames\":%u,"
           "\"elapsed_cycles\":%llu,\"video_pixels\":%zu,"
           "\"audio_frames\":%zu,\"nonzero_audio_samples\":%zu,"
           "\"tone\":\"pass\",\"fire\":\"pass\",\"release\":\"pass\"}\n",
           assertions, FUTURE_FRAME_COUNT,
           (unsigned long long)total_elapsed_cycles,
           PIXEL_COUNT, total_audio_frames, nonzero_audio_samples);
    exit_code = 0;

done:
    if (trace != NULL && fclose(trace) != 0 && exit_code == 0) exit_code = 1;
    gn_destroy(source);
    gn_destroy(destination);
    free(media);
    free(state);
    free(destination_before);
    free(destination_after);
    free(source_pixels);
    free(destination_pixels);
    free(source_audio);
    free(destination_audio);
    if (exit_code != 0) fputs("installed continuation example failed\n", stderr);
    return exit_code;
}

int main(int argc, char **argv) {
    if (argc == 3) return run_instance_mode(argv[1], argv[2]);
    if (argc == 5 && strcmp(argv[1], "--produce") == 0)
        return run_process_producer(argv[2], argv[3], argv[4]);
    if (argc == 6 && strcmp(argv[1], "--consume") == 0)
        return run_process_consumer(argv[2], argv[3], argv[4], argv[5]);
    return 2;
}
