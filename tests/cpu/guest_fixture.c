/* SPDX-License-Identifier: MIT; original diagnostic, no firmware required. */
#include "guest_fixture.h"
#include <string.h>
void guest_fixture(uint8_t rom[512], unsigned scenario, int mutate) {
 const uint8_t program[]={0x70,7,0x56,0x80,0x23,0xc0,0,0,0x10,0,0x4e,0x72,0x27,0};
 memset(rom,0,512); rom[2]=0x20; rom[6]=1;
 memcpy(rom+0x100,program,sizeof(program));
 if(scenario) {rom[0x101]=11; rom[0x102]=0x5a; rom[0x109]=4;}
 if(mutate) rom[0x101]++;
}
