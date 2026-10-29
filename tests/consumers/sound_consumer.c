/* SPDX-License-Identifier: MIT; original public-fixture installed C consumer. */
#include "glueyneo/glueyneo.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int public_sound_guest_write(const char *path);

enum { WIDTH = 320, HEIGHT = 224, REGIONS = 8, HEADER = 16, DESCRIPTOR = 12 };
#define PIXEL_BYTES ((size_t)WIDTH * HEIGHT * sizeof(uint32_t))
#define CONTENT_LIMIT (GN_MVS_MAX_MEDIA_BYTES + HEADER + REGIONS * DESCRIPTOR)

static FILE *open_file(const char *path, const char *mode) {
#if defined(_MSC_VER)
    FILE *file = NULL;
    if (fopen_s(&file, path, mode) != 0) return NULL;
    return file;
#else
    return fopen(path, mode);
#endif
}

static uint32_t be32(const uint8_t *p) {
    return (uint32_t)p[0] << 24 | (uint32_t)p[1] << 16 |
           (uint32_t)p[2] << 8 | p[3];
}

static uint8_t *read_bundle(const char *path, size_t *size) {
    FILE *f = open_file(path, "rb");
    if (!f) return NULL;
    if (fseek(f, 0, SEEK_END) != 0) { fclose(f); return NULL; }
    const long n = ftell(f);
    if (n < HEADER || (unsigned long)n > CONTENT_LIMIT || fseek(f, 0, SEEK_SET) != 0) {
        fclose(f); return NULL;
    }
    uint8_t *bytes = malloc((size_t)n);
    if (!bytes) { fclose(f); return NULL; }
    const size_t count = fread(bytes, 1, (size_t)n, f);
    const int extra = fgetc(f), closed = fclose(f);
    if (count != (size_t)n || extra != EOF || closed != 0) { free(bytes); return NULL; }
    *size = count;
    return bytes;
}

static int load_bundle(gn_instance *instance, const uint8_t *bytes, size_t size) {
    if (size < HEADER || memcmp(bytes, "GNMV", 4) ||
        be32(bytes + 4) != GN_MVS_MANIFEST_VERSION_ZOOM ||
        be32(bytes + 8) != GN_MVS_PROFILE_MSX || be32(bytes + 12) != REGIONS) return 0;
    gn_mvs_manifest_v3 m;
    memset(&m, 0, sizeof(m));
    m.version = GN_MVS_MANIFEST_VERSION_ZOOM;
    m.profile = GN_MVS_PROFILE_MSX;
    m.region_count = REGIONS;
    size_t at = HEADER;
    for (size_t i = 0; i < REGIONS; ++i) {
        if (at > size || size - at < DESCRIPTOR) return 0;
        const uint32_t role = be32(bytes + at), high = be32(bytes + at + 4), n = be32(bytes + at + 8);
        at += DESCRIPTOR;
        if (role != i + 1 || high || !n || n > size - at) return 0;
        m.regions[i] = (gn_mvs_region){(gn_mvs_region_role)role, bytes + at, n, n, GN_MVS_LAYOUT_LINEAR};
        at += n;
    }
    return at == size && gn_load_mvs_v3(instance, &m) == GN_STATUS_OK;
}

/* Canonical little-endian trace includes lengths, elapsed clocks, pixels and PCM.
 * Compare bytes with the fresh in-tree native reference; no golden is blessed. */
static int put_integer(FILE *f, uint64_t value, size_t width) {
    for (size_t i = 0; i < width; ++i) {
        if (fputc((int)(value & 255u), f) == EOF) return 0;
        value >>= 8;
    }
    return 1;
}

static int write_frame(FILE *f, const gn_mvs_frame_result_v1 *r,
                       const uint32_t *pixels, const int16_t *audio) {
    if (!put_integer(f, r->audio_frames_delivered, 4) ||
        !put_integer(f, r->elapsed_cycles, 8)) return 0;
    for (size_t i = 0; i < (size_t)WIDTH * HEIGHT; ++i)
        if (!put_integer(f, pixels[i], 4)) return 0;
    for (size_t i = 0; i < r->audio_frames_delivered * 2; ++i)
        if (!put_integer(f, (uint16_t)audio[i], 2)) return 0;
    return 1;
}

/* Independent period from the fixture's programmed SSG clock/divider, retained
 * from tests/fixture/test_public_sound_guest.c; waveform phase is unrestricted. */
static int tone_present(const int16_t *audio, size_t frames) {
    if (frames < 800) return 0;
    int64_t best = 0;
    for (size_t phase = 0; phase < 48; ++phase) {
        int64_t correlation = 0;
        for (size_t i = 32; i < 800; ++i) {
            if (audio[2*i] != audio[2*i+1]) return 0;
            correlation += (int64_t)audio[2*i] * (((i+phase)%48 < 24) ? 1 : -1);
        }
        if (correlation < 0) correlation = -correlation;
        if (correlation > best) best = correlation;
    }
    return best / 768 >= 256;
}

int main(int argc, char **argv) {
    if (argc == 3 && !strcmp(argv[1], "--write-fixture"))
        return public_sound_guest_write(argv[2]) ? 0 : 1;
    if (argc != 4 || strcmp(argv[2], "--trace")) return 2;
    int ok = 0;
    size_t size = 0, capacity = 0;
    uint8_t *bytes = read_bundle(argv[1], &size);
    gn_instance *instance = NULL;
    uint32_t *pixels = malloc(PIXEL_BYTES);
    int16_t *audio = NULL;
    FILE *trace = NULL;
    if (!bytes || !pixels || gn_create(&instance) != GN_STATUS_OK ||
        !load_bundle(instance, bytes, size) ||
        gn_mvs_audio_capacity_v1(instance, &capacity) != GN_STATUS_OK ||
        capacity != GN_MVS_AUDIO_CAPACITY_FRAMES_V1) goto done;
    audio = malloc(capacity * 2 * sizeof(*audio));
    if (!audio || !(trace = open_file(argv[3], "wb"))) goto done;
    int16_t neutral[GN_MVS_AUDIO_CAPACITY_FRAMES_V1 * 2];
    int16_t fired[GN_MVS_AUDIO_CAPACITY_FRAMES_V1 * 2];
    size_t neutral_frames = 0, fire_frames = 0;
    const uint32_t masks[] = {0, 0, GN_MVS_INPUT_P1_A, 0};
    size_t generated = 0;
    for (size_t i = 0; i < sizeof(masks)/sizeof(masks[0]); ++i) {
        const gn_mvs_frame_request_v1 request = {
            GN_MVS_FRAME_REQUEST_V1_VERSION, masks[i], GN_PIXEL_XRGB8888,
            WIDTH, HEIGHT, WIDTH*sizeof(uint32_t), (uint8_t *)pixels,
            PIXEL_BYTES, audio, capacity
        };
        gn_mvs_frame_result_v1 result;
        memset(&result, 0, sizeof(result));
        if (gn_mvs_advance_frame_v1(instance, &request, sizeof(request),
            &result, sizeof(result)) != GN_STATUS_OK ||
            result.version != GN_MVS_FRAME_RESULT_V1_VERSION ||
            result.audio_sample_rate != 48000 || result.audio_channels != 2 ||
            result.audio_frames_generated < 800 || result.audio_frames_generated > capacity ||
            result.audio_frames_delivered != result.audio_frames_generated ||
            result.audio_frames_discarded || result.video_pixels_produced != (size_t)WIDTH*HEIGHT ||
            pixels[0] != 0 || pixels[1] != UINT32_C(0x00ffffff) ||
            !write_frame(trace, &result, pixels, audio)) goto done;
        generated += result.audio_frames_delivered;
        if (i == 1) {
            if (!tone_present(audio, result.audio_frames_delivered)) goto done;
            neutral_frames = result.audio_frames_delivered;
            memcpy(neutral, audio, neutral_frames * 2 * sizeof(*audio));
        } else if (i == 2) {
            if (result.audio_frames_delivered != neutral_frames ||
                !memcmp(neutral, audio, neutral_frames * 2 * sizeof(*audio))) goto done;
            fire_frames = result.audio_frames_delivered;
            memcpy(fired, audio, fire_frames * 2 * sizeof(*audio));
        } else if (i == 3) {
            if (result.audio_frames_delivered != fire_frames ||
                !tone_present(audio, result.audio_frames_delivered) ||
                !memcmp(fired, audio, fire_frames * 2 * sizeof(*audio))) goto done;
        }
    }
    /* Fire-omission control at the same guest frame, not a comparison against
     * an earlier tone phase. Reset also checks the ordinary lifecycle path. */
    if (gn_reset(instance) != GN_STATUS_OK) goto done;
    for (size_t i = 0; i < 3; ++i) {
        const gn_mvs_frame_request_v1 request = {
            GN_MVS_FRAME_REQUEST_V1_VERSION, 0, GN_PIXEL_XRGB8888,
            WIDTH, HEIGHT, WIDTH*sizeof(uint32_t), (uint8_t *)pixels,
            PIXEL_BYTES, audio, capacity
        };
        gn_mvs_frame_result_v1 r;
        if (gn_mvs_advance_frame_v1(instance, &request, sizeof(request), &r, sizeof(r)) != GN_STATUS_OK ||
            r.audio_frames_delivered != neutral_frames) goto done;
        if (i == 1 && memcmp(neutral, audio, neutral_frames * 2 * sizeof(*audio))) goto done;
        if (i == 2 && !memcmp(fired, audio, fire_frames * 2 * sizeof(*audio))) goto done;
    }
    if (fclose(trace)) { trace = NULL; goto done; }
    trace = NULL;
    printf("SDK_SOUND {\"outcome\":\"pass\",\"frames\":4,\"sample_frames\":%zu,"
           "\"tone\":\"pass\",\"fire\":\"pass\",\"release\":\"pass\"}\n", generated);
    ok = 1;
done:
    if (trace) fclose(trace);
    gn_destroy(instance);
    free(bytes); free(pixels); free(audio);
    if (!ok) fprintf(stderr, "public sound consumer failed\n");
    return ok ? 0 : 1;
}
