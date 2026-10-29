/* SPDX-License-Identifier: MIT */
#include "glueyneo/glueyneo.h"
#include "../sdk_private.h"
#include "../chips/z80_candidate.h"
#include "../chips/ym2610_candidate.h"

#include <stddef.h>
#include <stdint.h>
#include <string.h>

/* Original Glueyneo Q1.30 12/125 coefficients, derived by
 * tools/audio/design_mvs_pcm.py using its documented 20 kHz, beta-5 Kaiser
 * fractional-delay sinc recipe. Store phases 0..6; phases 7..11 are the
 * reversed complements of phases 5..1. The generated table is MIT-licensed. */
static const int32_t gn_mvs_pcm_q30_coefficients[7][80] = {
    {
        -118330, -55311, 72989, 274876, 550493, 889410, 1268988, 1653867,
        1996884, 2241585, 2326387, 2190222, 1779345, 1054818, 0, -1372677,
        -3016426, -4847049, -6742713, -8546981, -10075264, -11124558, -11486038, -10959757,
        -9370471, -6583386, -2518567, 2837282, 9422800, 17098639, 25649411, 34791119,
        44183842, 53449003, 62190178, 70016067, 76564030, 81522500, 84650642, 85793776,
        84893424, 81991186, 77226177, 70826187, 63093246, 54384657, 45090926, 35612183,
        26334823, 17609964, 9735202, 2940782, -2619029, -6869062, -9810926, -11515800,
        -12113160, -11776591, -10707925, -9121036, -7226504, -5218233, -3262826, -1492253,
        0, 1159376, 1967678, 2438059, 2608290, 2533110, 2276411, 1903973,
        1477283, 1048835, 659100, 335192, 91056, -71068, -158293, -184215
    },
    {
        -124284, -64320, 60729, 259646, 533175, 871571, 1252898, 1642435,
        1993492, 2249842, 2349778, 2231692, 1840848, 1136851, 101189, -1255910,
        -2890058, -4719478, -6624581, -8450778, -10014720, -11113847, -11538839, -11088223,
        -9584184, -6888383, -2916507, 2349721, 8854235, 16462960, 24965402, 34081726,
        43475112, 52768765, 61566544, 69475839, 76131138, 81216575, 84485819, 85777822,
        85027251, 82268789, 77634995, 71347869, 63704759, 55059663, 45801319, 36329699,
        27032579, 18263860, 10325069, 3451230, -2198126, -6542429, -9578114, -11371713,
        -12048841, -11780175, -10765694, -9218475, -7349301, -5353137, -3398336, -1619081,
        -111329, 1067859, 1897934, 2389997, 2580177, 2522039, 2278781, 1915936,
        1495125, 1069276, 679495, 353627, 106359, -59395, -150189, -179218
    },
    {
        -130159, -73261, 48502, 244381, 515719, 853459, 1236370, 1630377,
        1989287, 2257113, 2372049, 2271976, 1901192, 1217870, 201644, -1139448,
        -2763419, -4590924, -6504640, -8351864, -9950536, -11098602, -11586304, -11210714,
        -9791509, -7186858, -3308113, 1867959, 8290583, 15830975, 24283579, 33372778,
        42764937, 52085139, 60937622, 68928575, 75689712, 80900951, 84310533, 85751090,
        85150452, 82536375, 78034828, 71861962, 64310361, 55730624, 46509623, 37047059,
        27731998, 18921033, 10919555, 3967312, -1770922, -6209184, -9338717, -11221372,
        -11978848, -11778855, -10819450, -9312850, -7469975, -5486802, -3533383, -1746092,
        -223336, 975324, 1826976, 2340655, 2550826, 2509853, 2280210, 1927156,
        1512427, 1089367, 699700, 371996, 121683, -47647, -141990, -174126
    },
    {
        -135954, -82131, 36311, 229086, 498134, 835081, 1219411, 1617704,
        1984275, 2263400, 2393199, 2311069, 1960363, 1297853, 301337, -1023330,
        -2636555, -4461438, -6382946, -8250298, -9882770, -11078870, -11628474, -11327257,
        -9992455, -7478800, -3693353, 1392051, 7731921, 15202783, 23604053, 32664399,
        42053447, 51398252, 60303535, 68374384, 75239839, 80575691, 84124823, 85713588,
        85263003, 82793892, 78425599, 72368365, 64909936, 56397415, 47215705, 37764136,
        28432961, 19581379, 11518571, 4488963, -1337461, -5869350, -9092738, -11064759,
        -11903147, -11772585, -10869140, -9404103, -7588468, -5619169, -3667917, -1873242,
        -335985, 881796, 1754823, 2290045, 2520242, 2496549, 2280692, 1937627,
        1529182, 1109097, 719704, 390292, 137023, -35830, -133697, -168940
    },
    {
        -141666, -90927, 24161, 213768, 480426, 816447, 1202030, 1604422,
        1978463, 2268708, 2413228, 2348962, 2018349, 1376779, 400235, -907595,
        -2509513, -4331073, -6259557, -8146137, -9811477, -11054703, -11665387, -11437878,
        -10187031, -7764198, -4072192, 922053, 7178327, 14578479, 22926937, 31956712,
        41340772, 50708233, 59664403, 67813374, 74781610, 80240863, 83928724, 85665323,
        85364883, 83041289, 78807229, 72866979, 65503367, 57059909, 47919435, 38480801,
        29135347, 20244790, 12122030, 5016114, -897789, -5522950, -8840177, -10901855,
        -11821704, -11761317, -10914708, -9492173, -7704720, -5750182, -3801885, -2000487,
        -449241, 787303, 1681492, 2238177, 2488428, 2482127, 2280220, 1947340,
        1545379, 1128458, 739501, 408507, 152374, -23947, -125314, -163663
    },
    {
        -147295, -99646, 12056, 198432, 462602, 797563, 1184235, 1590541,
        1971856, 2273039, 2432135, 2385650, 2075136, 1454626, 498310, -792280,
        -2382340, -4199884, -6134528, -8039439, -9736713, -11026152, -11697086, -11542604,
        -10375246, -8043042, -4444601, 458019, 6629876, 13958159, 22252343, 31249841,
        40627041, 50015213, 59020351, 67245656, 74315117, 79896532, 83722279, 85606307,
        85456072, 83278517, 79179643, 73357706, 66090540, 57717980, 48620684, 39196926,
        29839037, 20911160, 12729842, 5548697, -451952, -5170008, -8581038, -10732645,
        -11734487, -11745008, -10956102, -9577004, -7818672, -5879784, -3935237, -2127781,
        -563066, 691873, 1607003, 2185062, 2455388, 2466584, 2278791, 1956287,
        1561010, 1147440, 759082, 426636, 167729, -12002, -116842, -158295
    },
    {
        -152839, -108285, 0, 183084, 444670, 778439, 1166036, 1576067,
        1964461, 2276399, 2449921, 2421127, 2130711, 1531374, 595532, -677425,
        -2255080, -4067921, -6007918, -7930265, -9658537, -10993267, -11723612, -11641463,
        -10557114, -8315325, -4810549, 0, 6086642, 13341915, 21580381, 30543909,
        39912382, 49319319, 58371502, 66671341, 73840451, 79542768, 83505529, 85536552,
        85536552, 83505529, 79542768, 73840451, 66671341, 58371502, 49319319, 39912382,
        30543909, 21580381, 13341915, 6086642, 0, -4810549, -8315325, -10557114,
        -11641463, -11723612, -10993267, -9658537, -7930265, -6007918, -4067921, -2255080,
        -677425, 595532, 1531374, 2130711, 2421127, 2449921, 2276399, 1964461,
        1576067, 1166036, 778439, 444670, 183084, 0, -108285, -152839
    }
};

static int32_t gn_mvs_pcm_coefficient(unsigned phase, size_t tap) {
    if (phase < 7u) return gn_mvs_pcm_q30_coefficients[phase][tap];
    return gn_mvs_pcm_q30_coefficients[12u - phase][79u - tap];
}

_Static_assert(GN_MVS_PCM_MAX_OUTPUT_FRAMES ==
                   GN_MVS_AUDIO_CAPACITY_FRAMES_V1,
               "public PCM capacity must match the checked private bound");

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

/* Cartridge P1 fixed window. The 68000 reads 0x000080-0x0fffff as the cartridge
 * program bytes at the same offset (the BIOS reaches the "NEO-GEO" signature at
 * 0x100 and the USER entry jump at 0x122 here). Sources, docs/mvs-media.md
 * "Predicate sources (fetched)": S6 (68k program header, oldid 9154) for the
 * header offsets, and S7 (pinned MAME neogeo.cpp install_rom of 0x000080-0x0fffff
 * from the cartridge base, differential evidence only per D-02). 0x000000-0x00007f
 * keeps the vector-latch selection handled by the callers. The window is
 * read-only; writes are dropped by the caller as MAME's unmapped-write default.
 * The MSX profile requires a program region larger than the window, so no read
 * inside it falls beyond the loaded bytes; the bound check keeps that explicit. */
#define GN_MVS_P1_WINDOW_START UINT32_C(0x000080)
#define GN_MVS_P1_WINDOW_END UINT32_C(0x0fffff)

/* Cartridge P2/bank window. Pinned MAME 31e52312 neogeo.cpp, neogeo_main_map
 * comment at line 1728 ("it appears to map to cart space") and the cartridge
 * install_* handlers at 0x200000-0x2fffff (lines 1515-1535) bound this window
 * to 0x200000-0x2fffff. Everything from $300000 up belongs to the I/O map
 * (lines 1709-1736), so those reads must not fall through to program bytes
 * (plan 05-12, D-07: an I/O address is served by a cited register or faults). */
#define GN_MVS_P2_WINDOW_START UINT32_C(0x200000)
#define GN_MVS_P2_WINDOW_END UINT32_C(0x2fffff)
#define GN_MVS_PROGRAM_BANK_BYTES UINT64_C(0x100000)

int gn_mvs_bus_read8(const gn_mvs_owned_region *regions, size_t count,
                     uint8_t *work_ram, size_t work_ram_size,
                     uint8_t *save_ram, size_t save_ram_size,
                     uint8_t program_bank,
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
    if (program != NULL && address >= GN_MVS_P1_WINDOW_START &&
        address <= GN_MVS_P1_WINDOW_END && address < program->size) {
        *value = program->bytes[(size_t)address];
        return 1;
    }
    if (program != NULL && address >= GN_MVS_P2_WINDOW_START &&
        address <= GN_MVS_P2_WINDOW_END) {
        const uint64_t offset =
            ((uint64_t)program_bank + UINT64_C(1)) * GN_MVS_PROGRAM_BANK_BYTES +
            ((uint64_t)address - GN_MVS_P2_WINDOW_START);
        if (offset < program->size) {
            *value = program->bytes[(size_t)offset];
            return 1;
        }
    }
    return 0;
}

int gn_mvs_bus_read16(const gn_mvs_owned_region *regions, size_t count,
                      uint8_t *work_ram, size_t work_ram_size,
                      uint8_t *save_ram, size_t save_ram_size,
                      uint8_t program_bank,
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
        address >= GN_MVS_P1_WINDOW_START && address < GN_MVS_P1_WINDOW_END &&
        address <= program->size - 2u) {
        *value = (uint16_t)(((uint16_t)program->bytes[address] << 8) |
                            program->bytes[address + 1u]);
        return 1;
    }
    if (program != NULL && program->size >= 2u &&
        address >= GN_MVS_P2_WINDOW_START && address < GN_MVS_P2_WINDOW_END) {
        const uint64_t offset =
            ((uint64_t)program_bank + UINT64_C(1)) * GN_MVS_PROGRAM_BANK_BYTES +
            ((uint64_t)address - GN_MVS_P2_WINDOW_START);
        if (offset <= (uint64_t)program->size - 2u) {
            const size_t byte_offset = (size_t)offset;
            *value = (uint16_t)(((uint16_t)program->bytes[byte_offset] << 8) |
                                program->bytes[byte_offset + 1u]);
            return 1;
        }
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

/* Pinned MAME 31e52312 audio_map uses a fixed 0x0000-0x7fff bank, four
 * cartridge windows, and 0xf800-0xffff RAM. Its initial cartridge-bank values
 * are emulator defaults for non-banked cartridges; reads from the bank ports
 * update those windows from the Z80 port address. This remains emulator-
 * differential evidence, not measured board behavior. */
static int gn_mvs_sound_rom_offset(const gn_mvs_sound *sound, uint16_t address,
                                   size_t *out_offset) {
    size_t window_base;
    unsigned region;
    unsigned shift;
    if (address < UINT16_C(0x8000)) {
        *out_offset = (size_t)address;
        return *out_offset < sound->program_size;
    }
    if (address >= UINT16_C(0xf000)) {
        window_base = 0xf000u;
        region = 0u;
        shift = 11u;
    } else if (address >= UINT16_C(0xe000)) {
        window_base = 0xe000u;
        region = 1u;
        shift = 12u;
    } else if (address >= UINT16_C(0xc000)) {
        window_base = 0xc000u;
        region = 2u;
        shift = 13u;
    } else {
        window_base = 0x8000u;
        region = 3u;
        shift = 14u;
    }
    if (sound->program_size == 0u) return 0;
    /* MAME's NEO_BIOS_AUDIO_* macros reload the compact source at 0x10000
     * before bank selection (neogeo.cpp, pinned profile). The importer keeps
     * only the original compact bytes, so translate the expanded bank index
     * back by that reload base instead of indexing the duplicated layout. */
    const size_t bank_mask = (sound->program_size - 1u) & 0x3ffffu;
    const size_t bank_base = ((size_t)sound->banks[region] << shift) & bank_mask;
    *out_offset = bank_base + ((size_t)address - window_base);
    return *out_offset < sound->program_size;
}

static void gn_mvs_sound_record_failure(gn_mvs_sound *sound,
                                        gn_mvs_failure_stage stage,
                                        gn_mvs_failure_reason reason,
                                        gn_mvs_failure_status status,
                                        gn_mvs_failure_site site,
                                        gn_mvs_failure_cause cause) {
    if (sound == NULL || sound->failure_reason != GN_MVS_FAILURE_REASON_NONE) return;
    sound->failure_stage = (uint8_t)stage;
    sound->failure_reason = (uint8_t)reason;
    sound->failure_status = status;
    sound->failure_site = (uint8_t)site;
    sound->failure_cause = (uint8_t)cause;
}

static gn_mvs_failure_status gn_mvs_sound_z80_status(
    z80_candidate_status status) {
    switch (status) {
        case Z80_CANDIDATE_INVALID_ARGUMENT:
            return GN_MVS_FAILURE_STATUS_Z80_INVALID_ARGUMENT;
        case Z80_CANDIDATE_OUT_OF_MEMORY:
            return GN_MVS_FAILURE_STATUS_Z80_OUT_OF_MEMORY;
        case Z80_CANDIDATE_CYCLE_LIMIT:
            return GN_MVS_FAILURE_STATUS_Z80_CYCLE_LIMIT;
        case Z80_CANDIDATE_BUS_FAILURE:
            return GN_MVS_FAILURE_STATUS_Z80_BUS_FAILURE;
        case Z80_CANDIDATE_INVALID_SNAPSHOT:
            return GN_MVS_FAILURE_STATUS_Z80_INVALID_SNAPSHOT;
        case Z80_CANDIDATE_OK:
        default:
            return GN_MVS_FAILURE_STATUS_UNKNOWN;
    }
}

static gn_mvs_failure_status gn_mvs_sound_ym_status(
    ym2610_candidate_status status) {
    switch (status) {
        case YM2610_CANDIDATE_INVALID_ARGUMENT:
            return GN_MVS_FAILURE_STATUS_YM2610_INVALID_ARGUMENT;
        case YM2610_CANDIDATE_NO_MEMORY:
            return GN_MVS_FAILURE_STATUS_YM2610_NO_MEMORY;
        case YM2610_CANDIDATE_CALLBACK_FAILURE:
            return GN_MVS_FAILURE_STATUS_YM2610_CALLBACK_FAILURE;
        case YM2610_CANDIDATE_EXCEPTION:
            return GN_MVS_FAILURE_STATUS_YM2610_EXCEPTION;
        case YM2610_CANDIDATE_CAPACITY:
            return GN_MVS_FAILURE_STATUS_YM2610_CAPACITY;
        case YM2610_CANDIDATE_LIMIT:
            return GN_MVS_FAILURE_STATUS_YM2610_LIMIT;
        case YM2610_CANDIDATE_OK:
        default:
            return GN_MVS_FAILURE_STATUS_UNKNOWN;
    }
}

static int gn_mvs_sound_bus_failure(gn_mvs_sound *sound,
                                    z80_candidate_bus_kind kind,
                                    uint16_t address) {
    if (sound == NULL) return 0;
    gn_mvs_failure_site site = GN_MVS_FAILURE_SITE_UNKNOWN;
    gn_mvs_failure_bus_operation operation = GN_MVS_FAILURE_BUS_UNKNOWN;
    switch (kind) {
        case Z80_CANDIDATE_BUS_MEMORY_READ:
            site = GN_MVS_FAILURE_SITE_SOUND_MEMORY_READ;
            operation = GN_MVS_FAILURE_BUS_READ;
            break;
        case Z80_CANDIDATE_BUS_MEMORY_WRITE:
            site = GN_MVS_FAILURE_SITE_SOUND_MEMORY_WRITE;
            operation = GN_MVS_FAILURE_BUS_WRITE;
            break;
        case Z80_CANDIDATE_BUS_IO_READ:
            site = GN_MVS_FAILURE_SITE_SOUND_IO_READ;
            operation = GN_MVS_FAILURE_BUS_READ;
            break;
        case Z80_CANDIDATE_BUS_IO_WRITE:
            site = GN_MVS_FAILURE_SITE_SOUND_IO_WRITE;
            operation = GN_MVS_FAILURE_BUS_WRITE;
            break;
        case Z80_CANDIDATE_BUS_INTERRUPT_ACK:
            site = GN_MVS_FAILURE_SITE_SOUND_INTERRUPT_ACK;
            operation = GN_MVS_FAILURE_BUS_INTERRUPT_ACK;
            break;
    }
    const int is_first = sound->failure_reason == GN_MVS_FAILURE_REASON_NONE;
    gn_mvs_sound_record_failure(
        sound, GN_MVS_FAILURE_STAGE_BUS_ACCESS,
        GN_MVS_FAILURE_REASON_BUS_FAILURE,
        GN_MVS_FAILURE_STATUS_Z80_BUS_FAILURE, site,
        GN_MVS_FAILURE_CAUSE_SOUND_BUS_CALLBACK);
    if (is_first && site != GN_MVS_FAILURE_SITE_UNKNOWN &&
        operation != GN_MVS_FAILURE_BUS_UNKNOWN) {
        sound->failure_bus_valid = 1u;
        sound->failure_operation = (uint8_t)operation;
        sound->failure_address = address;
        sound->failure_width = 1u;
    }
    return 0;
}

static int gn_mvs_sound_ym_bus_failure(gn_mvs_sound *sound,
                                      z80_candidate_bus_kind kind,
                                      uint16_t address,
                                      ym2610_candidate_status status) {
    if (sound == NULL) return 0;
    const gn_mvs_failure_site site = kind == Z80_CANDIDATE_BUS_IO_READ
        ? GN_MVS_FAILURE_SITE_SOUND_IO_READ
        : GN_MVS_FAILURE_SITE_SOUND_IO_WRITE;
    const gn_mvs_failure_bus_operation operation =
        kind == Z80_CANDIDATE_BUS_IO_READ ? GN_MVS_FAILURE_BUS_READ
                                          : GN_MVS_FAILURE_BUS_WRITE;
    const int is_first = sound->failure_reason == GN_MVS_FAILURE_REASON_NONE;
    gn_mvs_sound_record_failure(
        sound, GN_MVS_FAILURE_STAGE_BUS_ACCESS,
        GN_MVS_FAILURE_REASON_BUS_FAILURE, gn_mvs_sound_ym_status(status),
        site, GN_MVS_FAILURE_CAUSE_YM2610_CALLBACK);
    if (is_first) {
        sound->failure_bus_valid = 1u;
        sound->failure_operation = (uint8_t)operation;
        sound->failure_address = address;
        sound->failure_width = 1u;
    }
    return 0;
}

static int gn_mvs_sound_sample_read(void *userdata, uint32_t access,
                                    uint32_t address, uint8_t *value);

static int gn_mvs_sound_sample_read(void *userdata, uint32_t access,
                                    uint32_t address, uint8_t *value) {
    gn_mvs_sound *sound = (gn_mvs_sound *)userdata;
    /* Selected normalized media has one ADPCM-A region. Pinned MAME
     * ymopn.cpp device_start maps absent ADPCM-B to that same region. */
    if (sound == NULL || value == NULL || sound->samples == NULL ||
        (access != YM2610_CANDIDATE_ACCESS_ADPCM_A &&
         access != YM2610_CANDIDATE_ACCESS_ADPCM_B) ||
        address >= sound->samples_size) {
        gn_mvs_sound_record_failure(
            sound, GN_MVS_FAILURE_STAGE_SOUND_CATCHUP,
            GN_MVS_FAILURE_REASON_INTERNAL_FAILURE,
            GN_MVS_FAILURE_STATUS_YM2610_CALLBACK_FAILURE,
            GN_MVS_FAILURE_SITE_YM2610_SAMPLE_READ,
            GN_MVS_FAILURE_CAUSE_YM2610_CALLBACK);
        return 1;
    }
    *value = sound->samples[address];
    return 0;
}

static void gn_mvs_sound_ym_irq(void *userdata, int asserted) {
    gn_mvs_sound *sound = (gn_mvs_sound *)userdata;
    const uint8_t next = (uint8_t)(asserted != 0);
#if defined(GLUEYNEO_SDK_TEST_HOOKS)
    if (sound->ym_irq == 0u && next != 0u) ++sound->test_irq_assertions;
    if (sound->ym_irq != 0u && next == 0u) ++sound->test_irq_deassertions;
#endif
    sound->ym_irq = next;
}

static int gn_mvs_sound_bus(void *userdata, z80_candidate_bus_kind kind,
                            uint16_t address, uint8_t *data) {
    gn_mvs_sound *sound = (gn_mvs_sound *)userdata;
    if (sound == NULL || data == NULL)
        return gn_mvs_sound_bus_failure(sound, kind, address);
#if defined(GLUEYNEO_SDK_TEST_HOOKS)
    if (sound->test_fail_bus != 0u &&
        (kind == Z80_CANDIDATE_BUS_IO_READ ||
         kind == Z80_CANDIDATE_BUS_IO_WRITE)) {
        sound->test_fail_bus = 0u;
        return gn_mvs_sound_bus_failure(sound, kind, address);
    }
#endif
    if (kind == Z80_CANDIDATE_BUS_MEMORY_READ ||
        kind == Z80_CANDIDATE_BUS_MEMORY_WRITE) {
        if (address >= UINT16_C(0xf800)) {
            const size_t offset = (size_t)(address - UINT16_C(0xf800));
            if (kind == Z80_CANDIDATE_BUS_MEMORY_READ) *data = sound->ram[offset];
            else sound->ram[offset] = *data;
            return 1;
        }
        size_t offset = 0u;
        if (!gn_mvs_sound_rom_offset(sound, address, &offset))
            return gn_mvs_sound_bus_failure(sound, kind, address);
        if (address < UINT16_C(0x8000) && sound->cart_selected == 0u) {
            /* S25n-S25p: a missing normalized BIOS is an unsupported source,
             * never permission to substitute cartridge bytes. */
            if (sound->bios_program == NULL || offset >= sound->bios_program_size)
                return gn_mvs_sound_bus_failure(sound, kind, address);
            if (kind == Z80_CANDIDATE_BUS_MEMORY_READ)
                *data = sound->bios_program[offset];
        } else if (kind == Z80_CANDIDATE_BUS_MEMORY_READ) {
            *data = sound->program[offset];
        }
        /* The mapped audio program is ROM; writes are discarded by this
         * read-only window, as with the source map's banked ROM entries. */
        return 1;
    }
    if (kind == Z80_CANDIDATE_BUS_IO_READ) {
        const uint8_t port = (uint8_t)address;
        if (port >= 4u && port <= 7u) {
            const ym2610_candidate_status status =
                ym2610_candidate_read(sound->ym, port - 4u, data);
            if (status != YM2610_CANDIDATE_OK)
                return gn_mvs_sound_ym_bus_failure(sound, kind, address, status);
            return 1;
        }
        if (port == 0u) {
            *data = sound->command;
            sound->command_pending = 0u;
            return 1;
        }
        const uint8_t port_low = (uint8_t)(port & 0x0fu);
        if (port_low >= 8u && port_low <= 11u) {
            const unsigned region = (unsigned)(port_low - 8u);
            const uint8_t selected = (uint8_t)(address >> 8);
#if defined(GLUEYNEO_SDK_TEST_HOOKS)
            if (sound->banks[region] != selected) ++sound->test_bank_changes;
#endif
            sound->banks[region] = selected;
            *data = 0u;
            return 1;
        }
        return gn_mvs_sound_bus_failure(sound, kind, address);
    }
    if (kind == Z80_CANDIDATE_BUS_IO_WRITE) {
        const uint8_t port = (uint8_t)address;
        if (port == 0u) {
            sound->command_pending = 0u;
            return 1;
        }
        if ((port & UINT8_C(0xef)) == UINT8_C(0x08)) {
            sound->nmi_enabled = (uint8_t)((port & UINT8_C(0x10)) == 0u);
            return 1;
        }
        if (port == UINT8_C(0x0c)) {
            sound->reply = *data;
            return 1;
        }
        if (port >= 4u && port <= 7u) {
#if defined(GLUEYNEO_SDK_TEST_HOOKS)
            if (port == 4u || port == 6u)
                sound->test_ym_selected_register = *data;
            else if (port == 5u) {
                if (sound->test_ym_selected_register == 0x24u)
                    ++sound->test_timer_register_writes[0];
                else if (sound->test_ym_selected_register == 0x25u)
                    ++sound->test_timer_register_writes[1];
                else if (sound->test_ym_selected_register == 0x27u)
                    ++sound->test_timer_register_writes[2];
            }
#endif
            const ym2610_candidate_status status =
                ym2610_candidate_write(sound->ym, port - 4u, *data);
            if (status != YM2610_CANDIDATE_OK)
                return gn_mvs_sound_ym_bus_failure(sound, kind, address, status);
            return 1;
        }
        /* S31-S31e: the pinned audio I/O map leaves other writes on MAME's
         * default unmapped-write handler, which discards their data. A port
         * with no write target is not a transport failure. This is emulator-
         * differential behavior; reads retain their explicit boundary. */
        return 1;
    }
    if (kind == Z80_CANDIDATE_BUS_INTERRUPT_ACK) {
        *data = UINT8_C(0xff);
        return 1;
    }
    return gn_mvs_sound_bus_failure(sound, kind, address);
}

gn_status gn_mvs_sound_create(gn_mvs_sound *sound, const uint8_t *program,
                              size_t program_size) {
    if (sound == NULL || program == NULL || program_size < 0x20000u)
        return GN_STATUS_INVALID_MEDIA;
    memset(sound, 0, sizeof(*sound));
    sound->program = program;
    sound->program_size = program_size;
    const z80_candidate_status status = z80_candidate_create(
        gn_mvs_sound_bus, sound, &sound->cpu);
    if (status == Z80_CANDIDATE_OUT_OF_MEMORY) return GN_STATUS_OUT_OF_MEMORY;
    if (status != Z80_CANDIDATE_OK) return GN_STATUS_CPU_FAILURE;
    const ym2610_candidate_callbacks callbacks = {
        gn_mvs_sound_sample_read, NULL, gn_mvs_sound_ym_irq,
        (uint32_t)GN_MVS_SAMPLES_BYTES, (uint32_t)GN_MVS_SAMPLES_BYTES, 0u
    };
    const ym2610_candidate_status ym_status = ym2610_candidate_create(
        &callbacks, sound, &sound->ym);
    if (ym_status != YM2610_CANDIDATE_OK) {
        gn_mvs_sound_destroy(sound);
        return ym_status == YM2610_CANDIDATE_NO_MEMORY
            ? GN_STATUS_OUT_OF_MEMORY : GN_STATUS_CPU_FAILURE;
    }
    const gn_status reset_status = gn_mvs_sound_reset(sound);
    if (reset_status != GN_STATUS_OK) gn_mvs_sound_destroy(sound);
    return reset_status;
}

gn_status gn_mvs_sound_prepare_state_rebind(
    gn_mvs_sound *sound, ym2610_candidate *staged_ym,
#if defined(Z80_CANDIDATE_TEST_HOOKS)
    z80_candidate_test_failpoint *failpoint,
#endif
    z80_candidate **out_healthy_cpu) {
    if (out_healthy_cpu == NULL) return GN_STATUS_INVALID_ARGUMENT;
    *out_healthy_cpu = NULL;
    if (sound == NULL || staged_ym == NULL || sound->program == NULL ||
        sound->samples == NULL) return GN_STATUS_INVALID_STATE;
    z80_candidate *candidate = NULL;
    const z80_candidate_status cpu_status =
#if defined(Z80_CANDIDATE_TEST_HOOKS)
        failpoint != NULL
            ? z80_candidate_test_create(gn_mvs_sound_bus, sound, failpoint,
                                        &candidate)
            :
#endif
              z80_candidate_create(gn_mvs_sound_bus, sound, &candidate);
    if (cpu_status != Z80_CANDIDATE_OK)
        return cpu_status == Z80_CANDIDATE_OUT_OF_MEMORY
            ? GN_STATUS_OUT_OF_MEMORY : GN_STATUS_CPU_FAILURE;
    const ym2610_candidate_callbacks callbacks = {
        gn_mvs_sound_sample_read, NULL, gn_mvs_sound_ym_irq,
        (uint32_t)GN_MVS_SAMPLES_BYTES, (uint32_t)GN_MVS_SAMPLES_BYTES, 0u
    };
    const ym2610_candidate_status ym_status = ym2610_candidate_state_rebind(
        staged_ym, &callbacks, sound);
    if (ym_status != YM2610_CANDIDATE_OK) {
        z80_candidate_destroy(candidate);
        return ym_status == YM2610_CANDIDATE_NO_MEMORY
            ? GN_STATUS_OUT_OF_MEMORY : GN_STATUS_CPU_FAILURE;
    }
    *out_healthy_cpu = candidate;
    return GN_STATUS_OK;
}

void gn_mvs_sound_destroy(gn_mvs_sound *sound) {
    if (sound == NULL) return;
    z80_candidate_destroy(sound->cpu);
    ym2610_candidate_destroy(sound->ym);
    sound->ym = NULL;
    sound->cpu = NULL;
    sound->program = NULL;
    sound->program_size = 0u;
    sound->pcm_active_sink = NULL;
    sound->pcm_active_capacity_frames = 0u;
    sound->pcm_capture_active = 0u;
}

gn_status gn_mvs_sound_reset(gn_mvs_sound *sound) {
    if (sound == NULL || sound->cpu == NULL || sound->program == NULL)
        return GN_STATUS_INVALID_STATE;
    const uint8_t capture_active = sound->pcm_capture_active;
    int16_t *const active_sink = capture_active != 0u
        ? sound->pcm_active_sink : NULL;
    const size_t active_capacity = capture_active != 0u
        ? sound->pcm_active_capacity_frames : 0u;
    const size_t call_generated = sound->pcm_call_generated_frames;
    const size_t call_delivered = sound->pcm_call_delivered_frames;
    memset(sound->ram, 0, sizeof(sound->ram));
    sound->banks[0] = UINT8_C(0x1e);
    sound->banks[1] = UINT8_C(0x0e);
    sound->banks[2] = UINT8_C(0x06);
    sound->banks[3] = UINT8_C(0x02);
    sound->command = 0u;
    sound->reply = 0u;
    sound->command_pending = 0u;
    sound->nmi_enabled = 0u;
    sound->ym_irq = 0u;
    /* S25r: HC259 reset clears output5, selecting the audio BIOS. Slot-init
     * entry1 (S25o) is not the reset source. Missing BIOS stays unsupported. */
    sound->cart_selected = 0u;
    sound->main_clock_remainder = 0u;
    memset(sound->pcm_history, 0, sizeof(sound->pcm_history));
    memset(sound->pcm_right_history, 0, sizeof(sound->pcm_right_history));
    sound->pcm_history_next = 0u;
    sound->pcm_output_phase = 0u;
    /* An emulated reset inside a synchronous frame call resets chip/filter
     * state, but the caller still owns this live output block. Preserve its
     * sink and prefix so the remaining generated samples append exactly once.
     * External reset has capture_active == 0 and cannot retain a sink. */
    sound->pcm_active_sink = active_sink;
    sound->pcm_active_capacity_frames = active_capacity;
    sound->pcm_call_generated_frames = call_generated;
    sound->pcm_call_delivered_frames = call_delivered;
    sound->pcm_capture_active = capture_active;
#if defined(GLUEYNEO_SDK_TEST_HOOKS)
    sound->test_main_cycles_advanced = 0u;
    sound->test_ym_input_clocks = 0u;
    sound->test_native_samples = 0u;
    sound->test_irq_assertions = 0u;
    sound->test_irq_deassertions = 0u;
    sound->test_bank_changes = 0u;
    memset(sound->test_timer_register_writes, 0,
           sizeof(sound->test_timer_register_writes));
    sound->test_ym_selected_register = 0u;
#endif
    sound->failed = 0u;
    sound->failure_stage = 0u;
    sound->failure_reason = 0u;
    sound->failure_status = GN_MVS_FAILURE_STATUS_UNKNOWN;
    sound->failure_site = GN_MVS_FAILURE_SITE_UNKNOWN;
    sound->failure_cause = GN_MVS_FAILURE_CAUSE_UNKNOWN;
    sound->failure_bus_valid = 0u;
    sound->failure_operation = GN_MVS_FAILURE_BUS_UNKNOWN;
    sound->failure_address = 0u;
    sound->failure_width = 0u;
#if defined(GLUEYNEO_SDK_TEST_HOOKS)
    sound->test_fail_bus = 0u;
    sound->test_fail_tick_limit = 0u;
#endif
    const ym2610_candidate_status ym_status =
        ym2610_candidate_reset(sound->ym);
    if (ym_status != YM2610_CANDIDATE_OK) {
        gn_mvs_sound_record_failure(sound, GN_MVS_FAILURE_STAGE_SOUND_CATCHUP,
                                    GN_MVS_FAILURE_REASON_INTERNAL_FAILURE,
                                    gn_mvs_sound_ym_status(ym_status),
                                    GN_MVS_FAILURE_SITE_SOUND_RESET,
                                    GN_MVS_FAILURE_CAUSE_YM2610_CALLBACK);
        sound->failed = 1u;
        return GN_STATUS_CPU_FAILURE;
    }
    const z80_candidate_status status = z80_candidate_reset(sound->cpu);
    if (status != Z80_CANDIDATE_OK) {
        gn_mvs_sound_record_failure(sound, GN_MVS_FAILURE_STAGE_SOUND_CATCHUP,
                                    GN_MVS_FAILURE_REASON_INVALID_STATE,
                                    gn_mvs_sound_z80_status(status),
                                    GN_MVS_FAILURE_SITE_SOUND_RESET,
                                    GN_MVS_FAILURE_CAUSE_Z80_RESET);
        sound->failed = 1u;
        return GN_STATUS_CPU_FAILURE;
    }
    return GN_STATUS_OK;
}

static int64_t gn_mvs_pcm_round_away(int64_t numerator, int64_t denominator) {
    if (numerator >= 0) return (numerator + denominator / 2) / denominator;
    return -((-numerator + denominator / 2) / denominator);
}

static int16_t gn_mvs_pcm_saturate_s16(int64_t accumulator) {
    const int64_t scale = INT64_C(1) << 30;
    const int64_t rounded = gn_mvs_pcm_round_away(accumulator, scale);
    if (rounded > INT16_MAX) return INT16_MAX;
    if (rounded < INT16_MIN) return INT16_MIN;
    return (int16_t)rounded;
}

/* Capture the source YM triplet at the same edge at which it is generated,
 * before the next Z80 bus tick. This causal converter keeps all latency and
 * rational phase in the owning instance and also advances in discard mode. */
static int gn_mvs_pcm_push(gn_mvs_sound *sound, const int32_t samples[3]) {
    const int64_t left_numerator = (int64_t)samples[0] * 2 + samples[2];
    const int64_t right_numerator = (int64_t)samples[1] * 2 + samples[2];
    const int32_t mixed_left = (int32_t)gn_mvs_pcm_round_away(
        left_numerator, INT64_C(4));
    const int32_t mixed_right = (int32_t)gn_mvs_pcm_round_away(
        right_numerator, INT64_C(4));

    sound->pcm_history[sound->pcm_history_next] = mixed_left;
    sound->pcm_right_history[sound->pcm_history_next] = mixed_right;
    sound->pcm_history_next =
        (sound->pcm_history_next + 1u) % GN_MVS_PCM_FILTER_TAPS;

    const unsigned next_phase = (unsigned)sound->pcm_output_phase + 12u;
    if (next_phase < 125u) {
        sound->pcm_output_phase = (uint16_t)next_phase;
        return 1;
    }
    sound->pcm_output_phase = (uint16_t)(next_phase - 125u);
    if (sound->pcm_capture_active != 0u) {
        if (sound->pcm_call_generated_frames >= GN_MVS_PCM_MAX_OUTPUT_FRAMES ||
            (sound->pcm_active_sink != NULL &&
             sound->pcm_call_delivered_frames >=
                 sound->pcm_active_capacity_frames)) {
            sound->failed = 1u;
            gn_mvs_sound_record_failure(
                sound, GN_MVS_FAILURE_STAGE_SOUND_CATCHUP,
                GN_MVS_FAILURE_REASON_INTERNAL_FAILURE,
                GN_MVS_FAILURE_STATUS_UNKNOWN,
                GN_MVS_FAILURE_SITE_SOUND_TICK,
                GN_MVS_FAILURE_CAUSE_YM2610_CALLBACK);
            return 0;
        }
        ++sound->pcm_call_generated_frames;
    }
    if (sound->pcm_capture_active == 0u || sound->pcm_active_sink == NULL)
        return 1;

    const unsigned phase = (unsigned)sound->pcm_output_phase;
    int64_t left_accumulator = 0;
    int64_t right_accumulator = 0;
    size_t history_index = sound->pcm_history_next == 0u
        ? GN_MVS_PCM_FILTER_TAPS - 1u : sound->pcm_history_next - 1u;
    for (size_t tap = 0u; tap < GN_MVS_PCM_FILTER_TAPS; ++tap) {
        const int32_t coefficient = gn_mvs_pcm_coefficient(phase, tap);
        left_accumulator +=
            (int64_t)sound->pcm_history[history_index] * coefficient;
        right_accumulator +=
            (int64_t)sound->pcm_right_history[history_index] * coefficient;
        if (history_index == 0u) history_index = GN_MVS_PCM_FILTER_TAPS - 1u;
        else --history_index;
    }
    const int16_t left = gn_mvs_pcm_saturate_s16(left_accumulator);
    const int16_t right = gn_mvs_pcm_saturate_s16(right_accumulator);
    const size_t frame = sound->pcm_call_delivered_frames;
    sound->pcm_active_sink[frame * 2u] = left;
    sound->pcm_active_sink[frame * 2u + 1u] = right;
    ++sound->pcm_call_delivered_frames;
    return 1;
}

#if defined(GLUEYNEO_SDK_TEST_HOOKS)
int gn_test_mvs_pcm_convert(const int32_t *triplets, size_t source_frames,
                            const size_t *partitions, size_t partition_count,
                            int16_t *stereo_output,
                            size_t output_capacity_frames,
                            size_t *out_output_frames) {
    if (out_output_frames == NULL ||
        (source_frames != 0u && triplets == NULL) ||
        (partition_count != 0u && partitions == NULL) ||
        (source_frames != 0u &&
         (partition_count == 0u || stereo_output == NULL)) ||
        source_frames > SIZE_MAX / (size_t)3u ||
        output_capacity_frames > SIZE_MAX / (size_t)2u)
        return 0;
    *out_output_frames = 0u;
    if (source_frames == 0u) return partition_count == 0u;

    size_t partitioned_frames = 0u;
    for (size_t index = 0u; index < partition_count; ++index) {
        const size_t partition = partitions[index];
        if (partition > (size_t)8454u ||
            partition > source_frames - partitioned_frames)
            return 0;
        partitioned_frames += partition;
    }
    if (partitioned_frames != source_frames) return 0;

    gn_mvs_sound converter;
    memset(&converter, 0, sizeof(converter));
    size_t source_offset = 0u;
    size_t output_offset = 0u;
    for (size_t segment = 0u; segment < partition_count; ++segment) {
        converter.pcm_capture_active = 1u;
        converter.pcm_call_generated_frames = 0u;
        converter.pcm_call_delivered_frames = 0u;
        converter.pcm_active_sink = stereo_output + output_offset * (size_t)2u;
        converter.pcm_active_capacity_frames =
            output_capacity_frames - output_offset;
        for (size_t frame = 0u; frame < partitions[segment]; ++frame) {
            const int32_t *sample = triplets +
                (source_offset + frame) * (size_t)3u;
            if (!gn_mvs_pcm_push(&converter, sample)) return 0;
        }
        if (converter.pcm_call_generated_frames !=
            converter.pcm_call_delivered_frames)
            return 0;
        output_offset += converter.pcm_call_delivered_frames;
        source_offset += partitions[segment];
    }
    converter.pcm_active_sink = NULL;
    converter.pcm_capture_active = 0u;
    *out_output_frames = output_offset;
    return 1;
}
#endif

gn_status gn_mvs_sound_advance(gn_mvs_sound *sound, uint64_t main_cycles) {
    if (sound == NULL || sound->cpu == NULL || sound->failed != 0u)
        return GN_STATUS_CPU_FAILURE;
    if (main_cycles > UINT64_MAX - sound->main_clock_remainder) {
        sound->failed = 1u;
        gn_mvs_sound_record_failure(sound, GN_MVS_FAILURE_STAGE_SOUND_CATCHUP,
                                    GN_MVS_FAILURE_REASON_CLOCK_OVERFLOW,
                                    GN_MVS_FAILURE_STATUS_UNKNOWN,
                                    GN_MVS_FAILURE_SITE_SOUND_TICK,
                                    GN_MVS_FAILURE_CAUSE_Z80_TICK);
        return GN_STATUS_CPU_FAILURE;
    }
#if defined(GLUEYNEO_SDK_TEST_HOOKS)
    sound->test_main_cycles_advanced += main_cycles;
#endif
    /* S25q with S9/S9b: master/2 main, master/6 audio. Emulator
     * differential clock contract; not a physical timing qualification. */
    const uint64_t scaled = main_cycles + sound->main_clock_remainder;
    const uint64_t ticks = scaled / UINT64_C(3);
    sound->main_clock_remainder = (uint8_t)(scaled % UINT64_C(3));
#if defined(GLUEYNEO_SDK_TEST_HOOKS)
    if (sound->test_fail_tick_limit != 0u && ticks != 0u) {
        sound->test_fail_tick_limit = 0u;
        sound->failed = 1u;
        gn_mvs_sound_record_failure(sound, GN_MVS_FAILURE_STAGE_SOUND_CATCHUP,
                                    GN_MVS_FAILURE_REASON_CYCLE_LIMIT,
                                    GN_MVS_FAILURE_STATUS_Z80_CYCLE_LIMIT,
                                    GN_MVS_FAILURE_SITE_SOUND_TICK,
                                    GN_MVS_FAILURE_CAUSE_Z80_TICK);
        return GN_STATUS_CPU_FAILURE;
    }
#endif
    for (uint64_t tick = 0u; tick < ticks; ++tick) {
        /* Pinned neogeo.h: YM master/3, Z80 master/6. Advance the old
         * register/timer state to the Z80 bus edge before servicing it.
         * MAX fidelity generates at most one sample per two input clocks. */
        int32_t samples[3];
        size_t produced = 0u;
        const ym2610_candidate_status ym_status =
            ym2610_candidate_clock(sound->ym, 2u, samples, 1u, &produced);
#if defined(GLUEYNEO_SDK_TEST_HOOKS)
        sound->test_ym_input_clocks += 2u;
        sound->test_native_samples += produced;
#endif
        if (ym_status != YM2610_CANDIDATE_OK) {
            sound->failed = 1u;
            gn_mvs_sound_record_failure(sound, GN_MVS_FAILURE_STAGE_SOUND_CATCHUP,
                                        GN_MVS_FAILURE_REASON_INTERNAL_FAILURE,
                                        gn_mvs_sound_ym_status(ym_status),
                                        GN_MVS_FAILURE_SITE_SOUND_TICK,
                                        GN_MVS_FAILURE_CAUSE_YM2610_CALLBACK);
            return GN_STATUS_CPU_FAILURE;
        }
        if (produced != 0u && !gn_mvs_pcm_push(sound, samples))
            return GN_STATUS_CPU_FAILURE;
        z80_candidate_tick_result result;
        const z80_candidate_status status = z80_candidate_tick(
            sound->cpu, sound->ym_irq != 0u,
            sound->command_pending != 0u && sound->nmi_enabled != 0u,
            &result);
        if (status != Z80_CANDIDATE_OK) {
            sound->failed = 1u;
            if (status == Z80_CANDIDATE_CYCLE_LIMIT) {
                gn_mvs_sound_record_failure(
                    sound, GN_MVS_FAILURE_STAGE_SOUND_CATCHUP,
                    GN_MVS_FAILURE_REASON_CYCLE_LIMIT,
                    gn_mvs_sound_z80_status(status),
                    GN_MVS_FAILURE_SITE_SOUND_TICK,
                    GN_MVS_FAILURE_CAUSE_Z80_TICK);
            } else if (status == Z80_CANDIDATE_BUS_FAILURE) {
                gn_mvs_sound_record_failure(
                    sound, GN_MVS_FAILURE_STAGE_BUS_ACCESS,
                    GN_MVS_FAILURE_REASON_BUS_FAILURE,
                    gn_mvs_sound_z80_status(status),
                    GN_MVS_FAILURE_SITE_SOUND_TICK,
                    GN_MVS_FAILURE_CAUSE_Z80_TICK);
            } else {
                gn_mvs_sound_record_failure(
                    sound, GN_MVS_FAILURE_STAGE_SOUND_CATCHUP,
                    GN_MVS_FAILURE_REASON_INVALID_STATE,
                    gn_mvs_sound_z80_status(status),
                    GN_MVS_FAILURE_SITE_SOUND_TICK,
                    GN_MVS_FAILURE_CAUSE_Z80_TICK);
            }
            return GN_STATUS_CPU_FAILURE;
        }
    }
    return GN_STATUS_OK;
}

int gn_mvs_sound_write_command(gn_mvs_sound *sound, uint32_t address,
                               uint8_t command) {
    if (sound == NULL || sound->cpu == NULL ||
        (address & ~UINT32_C(0x01fffe)) != UINT32_C(0x320000)) return 0;
    sound->command = command;
    sound->command_pending = 1u;
    return 1;
}

int gn_mvs_sound_read_reply(const gn_mvs_sound *sound, uint32_t address,
                            uint8_t *reply) {
    if (sound == NULL || reply == NULL ||
        (address & ~UINT32_C(0x01fffe)) != UINT32_C(0x320000)) return 0;
    *reply = sound->reply;
    return 1;
}
