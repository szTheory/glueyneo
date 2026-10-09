/* SPDX-License-Identifier: MIT */
#include "glueyneo/glueyneo.h"

#include <stddef.h>
#include <stdint.h>

typedef struct {
    uint8_t *bytes;
    size_t size;
    gn_mvs_region_role role;
} gn_mvs_owned_region;

static const gn_mvs_owned_region *find_region(
    const gn_mvs_owned_region *regions, size_t count, gn_mvs_region_role role) {
    for (size_t index = 0u; index < count; ++index) {
        if (regions[index].role == role) return &regions[index];
    }
    return NULL;
}

int gn_mvs_bus_read8(const gn_mvs_owned_region *regions, size_t count,
                     uint8_t *work_ram, size_t work_ram_size,
                     uint8_t *save_ram, size_t save_ram_size,
                     uint32_t address, uint8_t *value) {
    if (regions == NULL || value == NULL) return 0;
    if (save_ram != NULL && save_ram_size >= UINT32_C(0x10000) &&
        address >= UINT32_C(0xd00000) && address <= UINT32_C(0xdfffff)) {
        *value = save_ram[(size_t)(address & UINT32_C(0xffff))];
        return 1;
    }
    const gn_mvs_owned_region *bios = find_region(regions, count,
                                                  GN_MVS_REGION_BIOS);
    if (bios != NULL && bios->size >= UINT32_C(0x20000) &&
        address >= UINT32_C(0xc00000) && address <= UINT32_C(0xcfffff)) {
        const size_t offset = (size_t)(address - UINT32_C(0xc00000)) & 0x1ffffu;
        *value = bios->bytes[offset];
        return 1;
    }
    if (work_ram != NULL && address >= UINT32_C(0x100000) &&
        (uint64_t)address - UINT32_C(0x100000) < work_ram_size) {
        *value = work_ram[(size_t)(address - UINT32_C(0x100000))];
        return 1;
    }
    const gn_mvs_owned_region *program = find_region(regions, count,
                                                     GN_MVS_REGION_PROGRAM);
    if (program != NULL && address >= UINT32_C(0x200000) &&
        (uint64_t)address - UINT32_C(0x200000) < program->size) {
        *value = program->bytes[(size_t)(address - UINT32_C(0x200000))];
        return 1;
    }
    return 0;
}

int gn_mvs_bus_read16(const gn_mvs_owned_region *regions, size_t count,
                      uint8_t *work_ram, size_t work_ram_size,
                      uint8_t *save_ram, size_t save_ram_size,
                      uint32_t address, uint16_t *value) {
    if (regions == NULL || value == NULL || (address & UINT32_C(1)) != 0u) {
        return 0;
    }
    if (save_ram != NULL && save_ram_size >= UINT32_C(0x10000) &&
        address >= UINT32_C(0xd00000) && address <= UINT32_C(0xdffffe)) {
        const size_t offset = (size_t)(address & UINT32_C(0xffff));
        *value = (uint16_t)(((uint16_t)save_ram[offset] << 8) | save_ram[offset + 1u]);
        return 1;
    }
    const gn_mvs_owned_region *bios = find_region(regions, count,
                                                  GN_MVS_REGION_BIOS);
    /* MAME neogeo_main_map exposes only the banked vector words in this low
     * window; the remaining BIOS bytes are available at the high mirror. */
    if (bios != NULL && bios->size >= UINT32_C(0x80) &&
        address <= UINT32_C(0x7e)) {
        *value = (uint16_t)(((uint16_t)bios->bytes[address] << 8) |
                            bios->bytes[address + 1u]);
        return 1;
    }
    /* MAME neogeo.cpp at 31e52312c59e4d60d70235118bcbccd220f5232e,
     * ngarcade_base_state::neogeo_main_map lines 1722-1736, maps the BIOS
     * at 0xc00000-0xc1ffff mirrored by 0x0e0000. This is differential source
     * evidence; physical board behavior still needs independent validation. */
    if (bios != NULL && bios->size >= UINT32_C(0x20000) &&
        address >= UINT32_C(0xc00000) && address <= UINT32_C(0xcffffe)) {
        const size_t offset = (size_t)(address - UINT32_C(0xc00000)) & 0x1ffffu;
        *value = (uint16_t)(((uint16_t)bios->bytes[offset] << 8) |
                            bios->bytes[offset + 1u]);
        return 1;
    }
    if (work_ram_size >= 2u && address >= UINT32_C(0x100000) &&
        (uint64_t)address - UINT32_C(0x100000) <= work_ram_size - 2u) {
        const size_t offset = (size_t)(address - UINT32_C(0x100000));
        *value = (uint16_t)(((uint16_t)work_ram[offset] << 8) |
                            work_ram[offset + 1u]);
        return 1;
    }
    const gn_mvs_owned_region *program = find_region(regions, count,
                                                     GN_MVS_REGION_PROGRAM);
    if (program != NULL && program->size >= 2u &&
        address >= UINT32_C(0x200000) &&
        (uint64_t)address - UINT32_C(0x200000) <= program->size - 2u) {
        const size_t offset = (size_t)(address - UINT32_C(0x200000));
        *value = (uint16_t)(((uint16_t)program->bytes[offset] << 8) |
                            program->bytes[offset + 1u]);
        return 1;
    }
    return 0;
}

int gn_mvs_bus_write16(uint8_t *work_ram, size_t work_ram_size,
                       uint32_t address, uint16_t value) {
    if (work_ram == NULL || (address & UINT32_C(1)) != 0u ||
        address < UINT32_C(0x100000) || work_ram_size < 2u ||
        (uint64_t)address - UINT32_C(0x100000) > work_ram_size - 2u) {
        return 0;
    }
    const size_t offset = (size_t)(address - UINT32_C(0x100000));
    work_ram[offset] = (uint8_t)(value >> 8);
    work_ram[offset + 1u] = (uint8_t)value;
    return 1;
}

int gn_mvs_bus_write8(uint8_t *work_ram, size_t work_ram_size,
                      uint32_t address, uint8_t value) {
    if (work_ram == NULL || address < UINT32_C(0x100000) ||
        (uint64_t)address - UINT32_C(0x100000) >= work_ram_size) return 0;
    work_ram[(size_t)(address - UINT32_C(0x100000))] = value;
    return 1;
}
