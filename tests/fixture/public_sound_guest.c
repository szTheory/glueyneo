/* SPDX-License-Identifier: MIT; original fixture source, no firmware required. */
#include "glueyneo/glueyneo.h"

#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static inline FILE *gn_portable_fopen(const char *path, const char *mode) {
#if defined(_MSC_VER)
    FILE *file = NULL;
    if (fopen_s(&file, path, mode) != 0) return NULL;
    return file;
#else
    return fopen(path, mode);
#endif
}

enum {
    SOUND_HEADER_BYTES = 16u,
    SOUND_REGION_COUNT = 8u,
    SOUND_DESCRIPTOR_BYTES = 12u,
    MAIN_ENTRY_OFFSET = 0x100u,
    VIDEO_WIDTH = 320u,
    VIDEO_HEIGHT = 224u
};

static const size_t sound_region_sizes[SOUND_REGION_COUNT] = {
    GN_MVS_BIOS_BYTES, GN_MVS_PROGRAM_BYTES, GN_MVS_FIXED_BYTES,
    GN_MVS_AUDIO_PROGRAM_BYTES, GN_MVS_SAMPLES_BYTES,
    GN_MVS_SPRITES_BYTES, GN_MVS_AUDIO_BIOS_BYTES, GN_MVS_Y_ZOOM_BYTES
};

static void put_u32_be(uint8_t *out, uint32_t value) {
    out[0] = (uint8_t)(value >> 24);
    out[1] = (uint8_t)(value >> 16);
    out[2] = (uint8_t)(value >> 8);
    out[3] = (uint8_t)value;
}

static uint8_t *emit16(uint8_t *at, uint16_t value) {
    at[0] = (uint8_t)(value >> 8);
    at[1] = (uint8_t)value;
    return at + 2;
}

static uint8_t *emit32(uint8_t *at, uint32_t value) {
    return emit16(emit16(at, (uint16_t)(value >> 16)), (uint16_t)value);
}

static uint8_t *emit_move_b_immediate(uint8_t *at, uint8_t value,
                                     uint32_t address) {
    return emit32(emit16(emit16(at, UINT16_C(0x13fc)), value), address);
}

static uint8_t *emit_move_b_absolute_to_d0(uint8_t *at, uint32_t address) {
    return emit32(emit16(at, UINT16_C(0x1039)), address);
}

static uint8_t *emit_move_w_immediate(uint8_t *at, uint16_t value,
                                     uint32_t address) {
    return emit32(emit16(emit16(at, UINT16_C(0x33fc)), value), address);
}

static uint8_t *emit_video_ram_word(uint8_t *at, uint16_t offset,
                                    uint16_t value) {
    at = emit_move_w_immediate(at, offset, UINT32_C(0x3c0000));
    return emit_move_w_immediate(at, value, UINT32_C(0x3c0002));
}

static uint8_t *emit_cmp_b_d0(uint8_t *at, uint8_t value) {
    return emit16(emit16(at, UINT16_C(0x0c00)), value);
}

static void patch_short_branch(uint8_t *branch, const uint8_t *target) {
    const ptrdiff_t displacement = target - (branch + 2);
    branch[1] = (uint8_t)(int8_t)displacement;
}

static void emit_ym_write(uint8_t **cursor, uint8_t reg, uint8_t value) {
    uint8_t *at = *cursor;
    at[0] = 0x3eu; at[1] = reg; at[2] = 0xd3u; at[3] = 0x04u;
    at[4] = 0x3eu; at[5] = value; at[6] = 0xd3u; at[7] = 0x05u;
    *cursor = at + 8;
}

static void emit_z80_branch(uint8_t **cursor, uint8_t opcode,
                            uint8_t displacement) {
    (*cursor)[0] = opcode;
    (*cursor)[1] = displacement;
    *cursor += 2;
}

static void emit_z80_ym_write(uint8_t **cursor, uint8_t reg, uint8_t value) {
    emit_ym_write(cursor, reg, value);
}

static void emit_ssg_tone(uint8_t **cursor) {
    emit_z80_ym_write(cursor, 0u, 0x7du); /* SSG A period 125: source-derived 1 kHz. */
    emit_z80_ym_write(cursor, 1u, 0u);
    emit_z80_ym_write(cursor, 7u, 0x3eu); /* Enable only channel A tone. */
    emit_z80_ym_write(cursor, 8u, 0x0fu);
}

static void emit_adpcm_b_burst(uint8_t **cursor) {
    emit_z80_ym_write(cursor, 0x11u, 0xc0u); /* Route to left and right. */
    emit_z80_ym_write(cursor, 0x12u, 0u);    /* Start block 0. */
    emit_z80_ym_write(cursor, 0x13u, 0u);
    emit_z80_ym_write(cursor, 0x14u, 0u);    /* End block 0 (256 original bytes). */
    emit_z80_ym_write(cursor, 0x15u, 0u);
    emit_z80_ym_write(cursor, 0x19u, 0xffu); /* Delta-N = 65535. */
    emit_z80_ym_write(cursor, 0x1au, 0xffu);
    emit_z80_ym_write(cursor, 0x1bu, 0xffu); /* Full level. */
    emit_z80_ym_write(cursor, 0x10u, 0x80u);  /* Start external ROM playback. */
}

static void build_synthetic_sound_bios(uint8_t *bios, size_t size) {
    memset(bios, 0, size);
    const uint8_t boot[] = {
        0x31u, 0xffu, 0xffu,       /* LD SP,$ffff */
        0x3eu, 0x00u, 0xd3u, 0x08u, /* Enable the MVS command NMI. */
        0xfbu, 0x76u, 0x18u, 0xfdu /* EI; HALT; JR HALT. */
    };
    memcpy(bios, boot, sizeof(boot));

    uint8_t *handler = bios + 0x66u;
    uint8_t *cursor = handler;
    cursor[0] = 0xdbu; cursor[1] = 0x00u; /* IN A,($00): consume command. */
    cursor[2] = 0xd3u; cursor[3] = 0x0cu; /* OUT ($0c),A: expose guest command. */
    cursor += 4;
    cursor[0] = 0xfeu; cursor[1] = 0x3cu; /* CP $3c: sustained music tone. */
    cursor += 2;
    uint8_t *tone_branch = cursor;
    emit_z80_branch(&cursor, 0x28u, 0u); /* JR Z, tone. */
    cursor[0] = 0xfeu; cursor[1] = 0xa5u; /* CP $a5: action sample burst. */
    cursor += 2;
    uint8_t *burst_branch = cursor;
    emit_z80_branch(&cursor, 0x28u, 0u); /* JR Z, burst. */
    emit_z80_ym_write(&cursor, 8u, 0u);
    emit_z80_ym_write(&cursor, 0x10u, 0u);
    cursor[0] = 0xedu; cursor[1] = 0x45u; /* RETN. */
    cursor += 2;

    uint8_t *tone = cursor;
    emit_ssg_tone(&cursor);
    emit_z80_ym_write(&cursor, 0x10u, 0u); /* Music state releases ADPCM-B. */
    cursor[0] = 0xedu; cursor[1] = 0x45u;
    cursor += 2;

    uint8_t *burst = cursor;
    emit_ssg_tone(&cursor);
    emit_adpcm_b_burst(&cursor);
    cursor[0] = 0xedu; cursor[1] = 0x45u;
    cursor += 2;

    tone_branch[1] = (uint8_t)(int8_t)(tone - (tone_branch + 2));
    burst_branch[1] = (uint8_t)(int8_t)(burst - (burst_branch + 2));
    (void)cursor;
}

static uint8_t *build_main_guest(uint8_t *bios, size_t bios_size) {
    memset(bios, 0, bios_size);
    /* Original reset vectors enter the first-party fixture setup at $c00100. */
    static const uint8_t vectors[] = {
        0x00u, 0x10u, 0xffu, 0xfeu, 0x00u, 0xc0u, 0x01u, 0x00u
    };
    memcpy(bios, vectors, sizeof(vectors));
    uint8_t *code = bios + MAIN_ENTRY_OFFSET;

    /* Draw one fixed-layer landmark; its pen and color are first-party bytes. */
    for (uint16_t pen = 1u; pen <= 8u; ++pen) {
        const uint32_t palette = UINT32_C(0x400000) +
            (UINT32_C(0x10) + (uint32_t)pen) * UINT32_C(2);
        code = emit_move_w_immediate(code, UINT16_C(0x7fff), palette);
    }
    code = emit_video_ram_word(code, UINT16_C(0x7002), UINT16_C(0x1001));

    code = emit_move_b_immediate(code, 0x3cu, UINT32_C(0x00320000));
    uint8_t *wait_music = code;
    code = emit_move_b_absolute_to_d0(code, UINT32_C(0x00320000));
    code = emit_cmp_b_d0(code, 0x3cu);
    uint8_t *music_wait = code;
    code = emit16(code, UINT16_C(0x6600)); /* Wait for one handled command. */

    uint8_t *poll = code;
    code = emit_move_b_absolute_to_d0(code, UINT32_C(0x00300000));
    code = emit_cmp_b_d0(code, 0xefu); /* P1 A is active low on bit 4. */
    uint8_t *release_branch = code;
    code = emit16(code, UINT16_C(0x6600)); /* BNE.s release branch. */

    code = emit_move_b_absolute_to_d0(code, UINT32_C(0x00320000));
    code = emit_cmp_b_d0(code, 0xa5u);
    uint8_t *fire_unchanged = code;
    code = emit16(code, UINT16_C(0x6700)); /* Already handled. */
    code = emit_move_b_immediate(code, 0xa5u, UINT32_C(0x00320000));
    uint8_t *fire_wait_branch = code;
    code = emit16(code, UINT16_C(0x6000)); /* Wait for action reply. */

    uint8_t *release = code;
    code = emit_move_b_absolute_to_d0(code, UINT32_C(0x00320000));
    code = emit_cmp_b_d0(code, 0x3cu);
    uint8_t *music_unchanged = code;
    code = emit16(code, UINT16_C(0x6700)); /* Already handled. */
    code = emit_move_b_immediate(code, 0x3cu, UINT32_C(0x00320000));
    uint8_t *music_back = code;
    code = emit16(code, UINT16_C(0x6000)); /* Wait for music reply. */

    uint8_t *wait_fire = code;
    code = emit_move_b_absolute_to_d0(code, UINT32_C(0x00320000));
    code = emit_cmp_b_d0(code, 0xa5u);
    uint8_t *fire_wait = code;
    code = emit16(code, UINT16_C(0x6600)); /* Wait without resending. */
    uint8_t *fire_back = code;
    code = emit16(code, UINT16_C(0x6000)); /* Return to input polling. */

    patch_short_branch(music_wait, wait_music);
    patch_short_branch(release_branch, release);
    patch_short_branch(fire_unchanged, poll);
    patch_short_branch(fire_wait_branch, wait_fire);
    patch_short_branch(music_unchanged, poll);
    patch_short_branch(music_back, wait_music);
    patch_short_branch(fire_wait, wait_fire);
    patch_short_branch(fire_back, poll);
    return code;
}

size_t public_sound_guest_size(void) {
    size_t total = SOUND_HEADER_BYTES + SOUND_REGION_COUNT * SOUND_DESCRIPTOR_BYTES;
    for (size_t index = 0u; index < SOUND_REGION_COUNT; ++index) {
        if (sound_region_sizes[index] > SIZE_MAX - total) return 0u;
        total += sound_region_sizes[index];
    }
    return total;
}

int public_sound_guest_build(uint8_t *bundle, size_t capacity) {
    const size_t total = public_sound_guest_size();
    if (bundle == NULL || total == 0u || capacity != total) return 0;
    memset(bundle, 0, total);
    memcpy(bundle, "GNMV", 4u);
    put_u32_be(bundle + 4u, GN_MVS_MANIFEST_VERSION_ZOOM);
    put_u32_be(bundle + 8u, GN_MVS_PROFILE_MSX);
    put_u32_be(bundle + 12u, SOUND_REGION_COUNT);

    uint8_t *regions[SOUND_REGION_COUNT];
    size_t cursor = SOUND_HEADER_BYTES;
    for (size_t index = 0u; index < SOUND_REGION_COUNT; ++index) {
        put_u32_be(bundle + cursor, (uint32_t)(index + 1u));
        put_u32_be(bundle + cursor + 4u, 0u);
        put_u32_be(bundle + cursor + 8u, (uint32_t)sound_region_sizes[index]);
        cursor += SOUND_DESCRIPTOR_BYTES;
        regions[index] = bundle + cursor;
        cursor += sound_region_sizes[index];
    }

    (void)build_main_guest(regions[GN_MVS_REGION_BIOS - 1u],
                           sound_region_sizes[GN_MVS_REGION_BIOS - 1u]);
    uint8_t *fixed = regions[GN_MVS_REGION_FIXED - 1u];
    fixed[0x20u] = 0x05u;
    fixed[0x28u] = 0x07u;
    fixed[0x30u] = 0x20u;
    fixed[0x38u] = 0x03u;
    build_synthetic_sound_bios(regions[GN_MVS_REGION_AUDIO_BIOS - 1u],
                               sound_region_sizes[GN_MVS_REGION_AUDIO_BIOS - 1u]);

    /* Original 256-byte ADPCM-B sample, one YM2610 address block. */
    uint8_t *sample = regions[GN_MVS_REGION_SAMPLES - 1u];
    for (size_t index = 0u; index < 256u; ++index) {
        const uint8_t high = (uint8_t)((index * 3u + 5u) & 0x0fu);
        const uint8_t low = (uint8_t)((index * 7u + 2u) & 0x0fu);
        sample[index] = (uint8_t)((uint8_t)(high << 4) | low);
    }
    return cursor == total;
}

int public_sound_guest_write(const char *path) {
    const size_t total = public_sound_guest_size();
    if (path == NULL || total == 0u) return 0;
    uint8_t *bundle = (uint8_t *)malloc(total);
    if (bundle == NULL) return 0;
    if (!public_sound_guest_build(bundle, total)) {
        free(bundle);
        return 0;
    }
    FILE *file = gn_portable_fopen(path, "wb");
    if (file == NULL) {
        free(bundle);
        return 0;
    }
    const size_t written = fwrite(bundle, 1u, total, file);
    const int close_status = fclose(file);
    free(bundle);
    return written == total && close_status == 0;
}
