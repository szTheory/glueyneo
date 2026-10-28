/* SPDX-License-Identifier: MIT; original persistence diagnostic guest. */
#include <glueyneo/glueyneo.h>

#include <stddef.h>
#include <stdint.h>
#include <string.h>

size_t public_sound_guest_size(void);
int public_sound_guest_build(uint8_t *bundle, size_t capacity);

enum {
    BUNDLE_HEADER_BYTES = 16u,
    REGION_DESCRIPTOR_BYTES = 12u,
    GUEST_ENTRY_OFFSET = 0x100u
};

static const uint8_t save_a[2] = {0x12u, 0x34u};
static const uint8_t save_b[2] = {0xa1u, 0xb2u};

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

static uint8_t *emit_move_byte_to_d0(uint8_t *at, uint32_t address) {
    return emit32(emit16(at, UINT16_C(0x1039)), address);
}

static uint8_t *emit_compare_byte_immediate(uint8_t *at, uint8_t value) {
    return emit16(emit16(at, UINT16_C(0x0c00)), value);
}

static uint8_t *emit_branch(uint8_t *at, uint16_t opcode,
                            uint8_t **out_branch) {
    *out_branch = at;
    return emit16(emit16(at, opcode), 0u);
}

static void patch_branch(uint8_t *branch, const uint8_t *target) {
    const ptrdiff_t displacement = target - (branch + 2);
    branch[2] = (uint8_t)((uint16_t)displacement >> 8);
    branch[3] = (uint8_t)displacement;
}

static uint8_t *emit_write_byte_absolute(uint8_t *at, uint8_t value,
                                         uint32_t address) {
    at = emit16(at, UINT16_C(0x13fc));
    at = emit16(at, value);
    return emit32(at, address);
}

static uint8_t *emit_sram_write(uint8_t *at, uint8_t value, uint32_t offset) {
    return emit_write_byte_absolute(at, value, UINT32_C(0xd00000) + offset);
}

static uint8_t *emit_stop(uint8_t *at) {
    return emit16(emit16(at, UINT16_C(0x4e72)), UINT16_C(0x2700));
}

static int build_guest(uint8_t *bios, size_t size) {
    if (bios == NULL || size <= GUEST_ENTRY_OFFSET + 512u) return 0;
    memset(bios, 0, size);
    write_u32_be(bios, UINT32_C(0x0010fffe));
    write_u32_be(bios + 4u, UINT32_C(0x00c00100));

    uint8_t *code = bios + GUEST_ENTRY_OFFSET;
    code = emit_move_byte_to_d0(code, UINT32_C(0xd00000));
    code = emit_compare_byte_immediate(code, save_a[0]);
    uint8_t *from_a = NULL;
    code = emit_branch(code, UINT16_C(0x6700), &from_a);
    code = emit_compare_byte_immediate(code, save_b[0]);
    uint8_t *from_b = NULL;
    code = emit_branch(code, UINT16_C(0x6700), &from_b);

    uint8_t *unknown = code;
    code = emit_move_byte_to_d0(code, UINT32_C(0x00300000));
    code = emit_compare_byte_immediate(code, UINT8_C(0xef));
    uint8_t *write_a_branch = NULL;
    code = emit_branch(code, UINT16_C(0x6700), &write_a_branch);
    code = emit_move_byte_to_d0(code, UINT32_C(0x00300000));
    code = emit_compare_byte_immediate(code, UINT8_C(0xdf));
    uint8_t *write_b_branch = NULL;
    code = emit_branch(code, UINT16_C(0x6700), &write_b_branch);
    uint8_t *unknown_stop = code;
    code = emit_stop(code);
    uint8_t *unknown_end = code;
    uint8_t *loop_branch = NULL;
    code = emit_branch(code, UINT16_C(0x6000), &loop_branch);

    uint8_t *read_a = code;
    code = emit_stop(code);
    uint8_t *read_a_end = code;
    uint8_t *read_a_loop = NULL;
    code = emit_branch(code, UINT16_C(0x6000), &read_a_loop);

    uint8_t *read_b = code;
    code = emit_stop(code);
    uint8_t *read_b_end = code;
    uint8_t *read_b_loop = NULL;
    code = emit_branch(code, UINT16_C(0x6000), &read_b_loop);

    uint8_t *write_a = code;
    code = emit_write_byte_absolute(code, 0u, UINT32_C(0x003a001d));
    code = emit_sram_write(code, save_a[0], 0u);
    code = emit_sram_write(code, save_a[1], 1u);
    code = emit_stop(code);
    uint8_t *write_a_end = code;
    uint8_t *write_a_loop = NULL;
    code = emit_branch(code, UINT16_C(0x6000), &write_a_loop);

    uint8_t *write_b = code;
    code = emit_write_byte_absolute(code, 0u, UINT32_C(0x003a001d));
    code = emit_sram_write(code, save_b[0], 0u);
    code = emit_sram_write(code, save_b[1], 1u);
    code = emit_stop(code);
    uint8_t *write_b_end = code;
    uint8_t *write_b_loop = NULL;
    code = emit_branch(code, UINT16_C(0x6000), &write_b_loop);

    (void)unknown_stop;
    (void)unknown_end;
    patch_branch(from_a, read_a);
    patch_branch(from_b, read_b);
    patch_branch(write_a_branch, write_a);
    patch_branch(write_b_branch, write_b);
    patch_branch(loop_branch, unknown_end);
    patch_branch(read_a_loop, read_a_end);
    patch_branch(read_b_loop, read_b_end);
    patch_branch(write_a_loop, write_a_end);
    patch_branch(write_b_loop, write_b_end);
    return code < bios + size;
}

size_t public_persistence_guest_size(void) {
    return public_sound_guest_size();
}

int public_persistence_guest_build(uint8_t *bundle, size_t capacity) {
    const size_t total = public_persistence_guest_size();
    const size_t maximum = GN_MVS_MAX_MEDIA_BYTES + BUNDLE_HEADER_BYTES +
        GN_MVS_V3_MAX_REGIONS * REGION_DESCRIPTOR_BYTES;
    if (bundle == NULL || total == 0u || total > maximum || capacity != total ||
        !public_sound_guest_build(bundle, capacity) ||
        memcmp(bundle, "GNMV", 4u) != 0 ||
        read_u32_be(bundle + 4u) != GN_MVS_MANIFEST_VERSION_ZOOM ||
        read_u32_be(bundle + 8u) != GN_MVS_PROFILE_MSX ||
        read_u32_be(bundle + 12u) != GN_MVS_V3_MAX_REGIONS) return 0;

    size_t cursor = BUNDLE_HEADER_BYTES;
    int bios_found = 0;
    for (size_t index = 0u; index < GN_MVS_V3_MAX_REGIONS; ++index) {
        if (cursor > total || total - cursor < REGION_DESCRIPTOR_BYTES)
            return 0;
        const uint32_t role = read_u32_be(bundle + cursor);
        const uint32_t reserved = read_u32_be(bundle + cursor + 4u);
        const uint32_t extent = read_u32_be(bundle + cursor + 8u);
        cursor += REGION_DESCRIPTOR_BYTES;
        if (role != index + 1u || reserved != 0u ||
            (size_t)extent > total - cursor) return 0;
        if (role == GN_MVS_REGION_BIOS) {
            if (extent != GN_MVS_BIOS_BYTES ||
                !build_guest(bundle + cursor, extent)) return 0;
            bios_found = 1;
        }
        cursor += extent;
    }
    return cursor == total && bios_found;
}
