/* SPDX-License-Identifier: MIT; original fixture source, no firmware required. */
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>

#define PUBLIC_GUEST_HEADER_SIZE 16u
#define PUBLIC_GUEST_ROM_SIZE 512u
#define PUBLIC_GUEST_RAM_SEED_SIZE 10u
#define PUBLIC_GUEST_TILE_SIZE 64u
#define PUBLIC_GUEST_PAYLOAD_SIZE \
    (PUBLIC_GUEST_ROM_SIZE + PUBLIC_GUEST_RAM_SEED_SIZE + PUBLIC_GUEST_TILE_SIZE)
#define PUBLIC_GUEST_CONTENT_SIZE (PUBLIC_GUEST_HEADER_SIZE + PUBLIC_GUEST_PAYLOAD_SIZE)

static void put_u32_be(uint8_t *out, uint32_t value) {
    out[0] = (uint8_t)(value >> 24);
    out[1] = (uint8_t)(value >> 16);
    out[2] = (uint8_t)(value >> 8);
    out[3] = (uint8_t)value;
}

static void put_u16_be(uint8_t *out, uint16_t value) {
    out[0] = (uint8_t)(value >> 8);
    out[1] = (uint8_t)value;
}

void public_guest_build(uint8_t out[PUBLIC_GUEST_CONTENT_SIZE]) {
    static const uint16_t words[] = {
        UINT16_C(0x3039), UINT16_C(0x0030), UINT16_C(0x0000), /* MOVE.W input,D0 */
        UINT16_C(0x3239), UINT16_C(0x0000), UINT16_C(0x1000), /* MOVE.W x,D1 */
        UINT16_C(0xd240),                                     /* ADD.W D0,D1 */
        UINT16_C(0x33c1), UINT16_C(0x0000), UINT16_C(0x1000), /* MOVE.W D1,x */
        UINT16_C(0x4e72), UINT16_C(0x2700)                    /* STOP #$2700 */
    };
    uint8_t *rom = out + PUBLIC_GUEST_HEADER_SIZE;
    uint8_t *ram = rom + PUBLIC_GUEST_ROM_SIZE;
    uint8_t *tile = ram + PUBLIC_GUEST_RAM_SEED_SIZE;

    for (size_t i = 0u; i < PUBLIC_GUEST_CONTENT_SIZE; ++i) out[i] = 0u;
    out[0] = (uint8_t)'G'; out[1] = (uint8_t)'N';
    out[2] = (uint8_t)'F'; out[3] = (uint8_t)'X';
    put_u32_be(out + 4u, UINT32_C(1));
    put_u32_be(out + 8u, PUBLIC_GUEST_PAYLOAD_SIZE);
    put_u32_be(out + 12u, PUBLIC_GUEST_HEADER_SIZE);
    put_u32_be(rom, UINT32_C(0x2000));
    put_u32_be(rom + 4u, UINT32_C(0x0100));
    for (size_t i = 0u; i < sizeof(words) / sizeof(words[0]); ++i) {
        put_u16_be(rom + 0x100u + i * 2u, words[i]);
    }
    put_u16_be(ram, UINT16_C(16));
    put_u16_be(ram + 2u, UINT16_C(16));
    for (size_t i = 0u; i < PUBLIC_GUEST_TILE_SIZE; ++i) tile[i] = UINT8_C(0xff);
}

int public_guest_write(const char *path) {
    uint8_t content[PUBLIC_GUEST_CONTENT_SIZE];
    if (path == NULL) return 0;
    public_guest_build(content);
    FILE *file = fopen(path, "wb");
    if (file == NULL) return 0;
    const size_t written = fwrite(content, 1u, sizeof(content), file);
    const int close_status = fclose(file);
    return written == sizeof(content) && close_status == 0;
}

size_t public_guest_content_size(void) { return PUBLIC_GUEST_CONTENT_SIZE; }
