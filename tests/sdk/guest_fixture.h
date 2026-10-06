/* SPDX-License-Identifier: MIT */
#ifndef GLUEYNEO_SDK_GUEST_FIXTURE_H
#define GLUEYNEO_SDK_GUEST_FIXTURE_H

#include <stdint.h>

#define GUEST_FIXTURE_ROM_SIZE 512u
#define GUEST_FIXTURE_RAM_INIT_SIZE 10u

typedef enum {
    GUEST_FIXTURE_SCENARIO_A = 0,
    GUEST_FIXTURE_SCENARIO_B = 1
} guest_fixture_scenario;

typedef struct {
    uint8_t rom[GUEST_FIXTURE_ROM_SIZE];
    uint8_t ram_seed[GUEST_FIXTURE_RAM_INIT_SIZE];
} guest_fixture_image;

void guest_fixture_build(guest_fixture_image *image,
                         guest_fixture_scenario scenario);

#endif
