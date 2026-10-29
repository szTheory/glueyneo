/* SPDX-License-Identifier: MIT; original persistence diagnostic guest. */
#include "glueyneo/glueyneo.h"

#include <stddef.h>
#include <stdint.h>
#include <string.h>

size_t public_sound_guest_size(void);
int public_sound_guest_build(uint8_t *bundle, size_t capacity);

enum {
    SAVE_BUNDLE_HEADER_BYTES = 16u,
    SAVE_BUNDLE_DESCRIPTOR_BYTES = 12u,
    SAVE_GUEST_ENTRY_OFFSET = 0x100u,
    SAVE_OUTPUT_COUNT = 6u
};

static const uint16_t values_a[SAVE_OUTPUT_COUNT] = {
    0x12u, 0x34u, 0x56u, 0x78u, 0x9au, 0xbcu
};
static const uint16_t values_b[SAVE_OUTPUT_COUNT] = {
    0xa1u, 0xb2u, 0xc3u, 0xd4u, 0xe5u, 0xf6u
};
static const uint32_t save_offsets[SAVE_OUTPUT_COUNT] = {
    0u, 1u, 0x1234u, 0x1235u, 0xfffeu, 0xffffu
};

static uint32_t read_u32_be(const uint8_t *bytes) {
    return ((uint32_t)bytes[0] << 24) | ((uint32_t)bytes[1] << 16) |
           ((uint32_t)bytes[2] << 8) | (uint32_t)bytes[3];
}

static void write_u32_be(uint8_t *bytes, uint32_t value) {
    bytes[0] = (uint8_t)(value >> 24);
    bytes[1] = (uint8_t)(value >> 16);
    bytes[2] = (uint8_t)(value >> 8);
    bytes[3] = (uint8_t)value;
}

static uint8_t *emit16(uint8_t *at, uint16_t value) {
    at[0] = (uint8_t)(value >> 8);
    at[1] = (uint8_t)value;
    return at + 2;
}

static uint8_t *emit32(uint8_t *at, uint32_t value) {
    return emit16(emit16(at, (uint16_t)(value >> 16)), (uint16_t)value);
}

static uint8_t *emit_read_sram(uint8_t *at, uint32_t offset,
                               uint32_t output_offset) {
    at = emit32(emit16(at, UINT16_C(0x1039)), UINT32_C(0xd00000) + offset);
    return emit32(emit16(at, UINT16_C(0x13c0)),
                  UINT32_C(0x100000) + output_offset);
}

static uint8_t *emit_write_byte(uint8_t *at, uint8_t value, uint32_t offset) {
    at = emit16(at, UINT16_C(0x13fc));
    at = emit16(at, value);
    return emit32(at, UINT32_C(0xd00000) + offset);
}

static uint8_t *emit_write_word(uint8_t *at, uint16_t value, uint32_t offset) {
    at = emit16(at, UINT16_C(0x33fc));
    at = emit16(at, value);
    return emit32(at, UINT32_C(0xd00000) + offset);
}

static void patch_short_branch(uint8_t *branch, const uint8_t *target) {
    branch[1] = (uint8_t)(int8_t)(target - (branch + 2));
}

static uint8_t *emit_save_writer(uint8_t *code, const uint16_t *values,
                                 int duplicate_effective_store) {
    /* A locked store must be ignored without advancing persistence lineage. */
    code = emit_write_byte(code, 0x5au, 0x5555u);
    code = emit16(code, UINT16_C(0x13fc));
    code = emit16(code, 0u);
    code = emit32(code, UINT32_C(0x003a001d));
    code = emit_write_byte(code, (uint8_t)values[0], save_offsets[0]);
    code = emit_write_byte(code, (uint8_t)values[1], save_offsets[1]);
    code = emit_write_word(code,
        (uint16_t)(((uint16_t)values[2] << 8) | values[3]),
        save_offsets[2]);
    code = emit_write_word(code,
        (uint16_t)(((uint16_t)values[4] << 8) | values[5]),
        save_offsets[4]);
    if (duplicate_effective_store != 0) {
        /* Same-value byte and word stores must not advance the lineage. */
        code = emit_write_byte(code, (uint8_t)values[0], save_offsets[0]);
        code = emit_write_word(code,
            (uint16_t)(((uint16_t)values[2] << 8) | values[3]),
            save_offsets[2]);
    }
    return code;
}

static int build_save_guest(uint8_t *bios, size_t size) {
    if (bios == NULL || size <= SAVE_GUEST_ENTRY_OFFSET + 128u) return 0;
    memset(bios, 0, size);
    /* Reset vectors enter this first-party program at the standard BIOS entry. */
    write_u32_be(bios, UINT32_C(0x0010fffe));
    write_u32_be(bios + 4u, UINT32_C(0x00c00100));
    uint8_t *code = bios + SAVE_GUEST_ENTRY_OFFSET;
    for (size_t index = 0u; index < SAVE_OUTPUT_COUNT; ++index)
        code = emit_read_sram(code, save_offsets[index], (uint32_t)index);
    code = emit32(emit16(code, UINT16_C(0x1039)), UINT32_C(0x00300000));
    code = emit16(code, UINT16_C(0x0c00));
    code = emit16(code, UINT16_C(0x00ef));
    uint8_t *branch_a = code;
    code = emit16(code, UINT16_C(0x6700));
    code = emit16(code, UINT16_C(0x0c00));
    code = emit16(code, UINT16_C(0x00df));
    uint8_t *branch_b = code;
    code = emit16(code, UINT16_C(0x6700));
    uint8_t *skip_write = code;
    code = emit16(code, UINT16_C(0x6000));
    uint8_t *write_a = code;
    code = emit_save_writer(code, values_a, 1);
    uint8_t *after_a = code;
    code = emit16(code, UINT16_C(0x6000));
    uint8_t *write_b = code;
    code = emit_save_writer(code, values_b, 0);
    uint8_t *end = code;
    patch_short_branch(branch_a, write_a);
    patch_short_branch(branch_b, write_b);
    patch_short_branch(skip_write, end);
    patch_short_branch(after_a, end);
    /* A tight self-branch gives the bounded run a stable, non-faulting tail. */
    (void)emit16(code, UINT16_C(0x60fe));
    return 1;
}

size_t public_save_guest_size(void) {
    return public_sound_guest_size();
}

int public_save_guest_build(uint8_t *bundle, size_t capacity) {
    const size_t total = public_save_guest_size();
    if (bundle == NULL || total == 0u || capacity != total ||
        !public_sound_guest_build(bundle, capacity) || total < SAVE_BUNDLE_HEADER_BYTES ||
        memcmp(bundle, "GNMV", 4u) != 0 ||
        read_u32_be(bundle + 4u) != GN_MVS_MANIFEST_VERSION_ZOOM ||
        read_u32_be(bundle + 8u) != GN_MVS_PROFILE_MSX ||
        read_u32_be(bundle + 12u) != GN_MVS_V3_MAX_REGIONS) return 0;

    size_t cursor = SAVE_BUNDLE_HEADER_BYTES;
    int bios_found = 0;
    for (size_t index = 0u; index < GN_MVS_V3_MAX_REGIONS; ++index) {
        if (cursor > total || total - cursor < SAVE_BUNDLE_DESCRIPTOR_BYTES)
            return 0;
        const uint32_t role = read_u32_be(bundle + cursor);
        const uint32_t reserved = read_u32_be(bundle + cursor + 4u);
        const uint32_t extent = read_u32_be(bundle + cursor + 8u);
        cursor += SAVE_BUNDLE_DESCRIPTOR_BYTES;
        if (role != index + 1u || reserved != 0u ||
            (size_t)extent > total - cursor) return 0;
        if (role == GN_MVS_REGION_BIOS) {
            if (extent != GN_MVS_BIOS_BYTES ||
                !build_save_guest(bundle + cursor, extent)) return 0;
            bios_found = 1;
        }
        cursor += extent;
    }
    return cursor == total && bios_found;
}
