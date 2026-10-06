/* SPDX-License-Identifier: MIT; original diagnostic, no firmware required. */
#include "guest_fixture.h"

#include <string.h>

void guest_fixture_build(guest_fixture_image *image,
                         guest_fixture_scenario scenario) {
    static const uint16_t words[] = {
        UINT16_C(0x7007), UINT16_C(0x5680), UINT16_C(0x23c0), UINT16_C(0x0000),
        UINT16_C(0x1000), UINT16_C(0x7200), UINT16_C(0x3239), UINT16_C(0x0000),
        UINT16_C(0x1008), UINT16_C(0x5681), UINT16_C(0x23c1), UINT16_C(0x0000),
        UINT16_C(0x1004), UINT16_C(0x7400), UINT16_C(0x3439), UINT16_C(0x0000),
        UINT16_C(0x100a), UINT16_C(0x5282), UINT16_C(0x23c2), UINT16_C(0x0000),
        UINT16_C(0x1010), UINT16_C(0x4e72), UINT16_C(0x2700)
    };
    if (image == NULL) return;

    memset(image, 0, sizeof(*image));
    image->rom[2] = 0x20u;
    image->rom[6] = 0x01u;
    for (size_t index = 0u; index < sizeof(words) / sizeof(words[0]); ++index) {
        const size_t offset = 0x100u + index * 2u;
        image->rom[offset] = (uint8_t)(words[index] >> 8);
        image->rom[offset + 1u] = (uint8_t)words[index];
    }
    image->ram_seed[8] = scenario == GUEST_FIXTURE_SCENARIO_A ? 0x12u : 0x23u;
    image->ram_seed[9] = scenario == GUEST_FIXTURE_SCENARIO_A ? 0x34u : 0x45u;
    if (scenario == GUEST_FIXTURE_SCENARIO_B) {
        image->rom[0x101u] = 0x0bu;
        image->rom[0x102u] = 0x5au;
    }
}
