# SDK original diagnostic oracle and provenance

This fixture is an original Glueyneo work, licensed under the repository MIT
license. It contains no BIOS, game ROM, commercial data, or third-party guest
bytes. The C recipe is `guest_fixture.c`; the SDK runner and native test link
that single recipe. The generated binary is a build artifact and is not
committed.

## Independent CPU oracle

Expected effects are derived from the instruction encodings and MC68000
behavior in the Motorola/NXP primary manuals below. They are not copied from
the owned CPU output or another emulator. The manual timing tables describe
the selected MC68000 instruction forms; the mapped ROM/RAM callback ordering
is the project's functional diagnostic contract, not a physical Neo Geo bus
capture.

| Guest PC | Words | Manual-derived effect |
|---|---|---|
| `0x0100` | `7007` | `MOVEQ #7,D0` gives D0 = 7 |
| `0x0102` | `5680` | `ADDQ.L #3,D0` gives D0 = 10 |
| `0x0104` | `23c0 0000 1000` | Store D0 as a big-endian long at RAM `0x1000` |
| `0x010a` | `7200` | Clear D1 before the word load |
| `0x010c` | `3239 0000 1008` | Load initialized word `0x1234` into the low word of D1 |
| `0x0112` | `5681` | Add 3, giving D1 = `0x00001237` |
| `0x0114` | `23c1 0000 1004` | Store D1 as a big-endian long at RAM `0x1004` |
| `0x011a` | `7400` | Clear D2 before the BSS load |
| `0x011c` | `3439 0000 100a` | Load the zero-filled BSS word at `0x100a` |
| `0x0122` | `5282` | Add 1, giving D2 = 1 |
| `0x0124` | `23c2 0000 1010` | Store D2 as a big-endian long at RAM `0x1010` |
| `0x012a` | `4e72 2700` | Execute privileged `STOP #$2700`; next PC is `0x012e` |

The reset vectors are big-endian SSP `0x2000` and PC `0x0100`. The ROM is 512
bytes at guest address zero. RAM is 4096 bytes at `0x1000`; its ten-byte
initialization prefix has `0x1234` at offsets 8–9. All remaining RAM starts
at zero, so the word at `0x100a` is BSS. The CPU reads this source word,
increments it, and writes a separate named result at `0x1010`.

Scenario B keeps the same program topology but changes the first immediate
pair to `700b 5a80` (11 + 5 = 16) and the initialized word to `0x2345`
(result `0x2348`). It makes per-instance ownership comparisons distinguishable.

The instruction timings are 4, 8, 20, 4, 16, 8, 20, 4, 16, 8, 20, and 4
cycles respectively: 132 instruction cycles. The MC68000 external-reset
recovery is 40 cycles, for 172 cycles through the final STOP boundary. The
following cumulative boundaries were checked through the ordinary API:

| Cumulative guest cycles | Boundary PC | Completed instructions | Event |
|---:|---:|---:|---|
| 40 | `0x0100` | 0 | Reset recovery |
| 44 | `0x0102` | 1 | MOVEQ |
| 52 | `0x0104` | 2 | ADDQ.L |
| 72 | `0x010a` | 3 | MOVE.L store |
| 76 | `0x010c` | 4 | MOVEQ |
| 92 | `0x0112` | 5 | MOVE.W load |
| 100 | `0x0114` | 6 | ADDQ.L |
| 120 | `0x011a` | 7 | MOVE.L store |
| 124 | `0x011c` | 8 | MOVEQ |
| 140 | `0x0122` | 9 | MOVE.W load |
| 148 | `0x0124` | 10 | ADDQ.L |
| 168 | `0x012a` | 11 | MOVE.L store |
| 172 | `0x012e` | 12 | STOP |

At the terminal boundary, the public observations are arithmetic `10`,
initialized-data result `0x1237`, and BSS-derived result `1` for scenario A;
scenario B returns `16`, `0x2348`, and `1`. The run requests exactly 172
cycles and reports 172 elapsed, zero overshoot, 12 instructions and STOP. A
STOP result alone is not diagnostic success: the runner checks every named
result and the terminal run fields.

## Sources and limits

- Motorola, *M68000 Family Programmer's Reference Manual* (1992), printed
  pages 4-11–4-12 (`ADDQ`), 4-116–4-117 (`MOVE`), 4-134 (`MOVEQ`) and 6-85
  (`STOP`): <https://www.nxp.com/docs/en/reference-manual/M68000PRM.pdf>.
- Motorola, *M68000 8-/16-/32-Bit Microprocessors User's Manual*, ninth
  edition (1993), section 6.3.1 (reset vectors), tables 8-2, 8-3 and 8-5
  (instruction timings), table 8-12 (`STOP`) and table 8-14 (external reset
  recovery): <https://www.nxp.com/docs/en/reference-manual/MC68000UM.pdf>.
- The Phase 01 admission report independently records the bounded accepted
  C17 backend and corrects WR-01's old user-mode MOVE-to-SR prose. This
  fixture does not use that privileged sequence or alter its frozen receipts:
  `.planning/phases/01-cpu-acceptance-experiment/01-VERIFICATION.md` and
  `01-29-ADMISSION-REVIEW.md`.
- The backend source is the repository-owned MIT candidate accepted only for
  its bounded diagnostic subset. Its source identity used by this build is
  SHA-256 `f11a282d5f571a67fff687c08cc90a44f5b6ff54bb5334b9c21bf17a4abcbee7`.
- Test assertions use the retained Unity source at immutable commit
  `b6763fbd9cedfacaa89e2ad9fd00d615a234e355`. Its copied-file hashes and
  upstream MIT notice are recorded in `third_party/unity/PROVENANCE.md`;
  Unity is linked only into test executables, never the SDK runtime.

The manuals establish CPU instruction effects and the cited MC68000 timings,
not Neo Geo board behavior, original-silicon qualification, BIOS boot, game
compatibility, or bus-pin timing. The accepted backend's timing remains a
bounded candidate contract. A reference emulator is not this oracle's source.

## Reproduction and exact identities

From the repository root:

```sh
cmake --preset sdk-debug
cmake --build --preset sdk-debug
ctest --preset sdk-debug -L 'sdk-provenance|sdk-diagnostic' --output-on-failure --no-tests=error
build/sdk-debug/glueyneo-diagnostic
build/sdk-debug/glueyneo-diagnostic --scenario-b
build/sdk-debug/glueyneo-diagnostic --write-fixture build/sdk-debug/diagnostic-original-a.bin
build/sdk-debug/glueyneo-diagnostic --check-fixture build/sdk-debug/diagnostic-original-a.bin
build/sdk-debug/glueyneo-diagnostic --write-fixture build/sdk-debug/diagnostic-original-b.bin --scenario-b
build/sdk-debug/glueyneo-diagnostic --check-fixture build/sdk-debug/diagnostic-original-b.bin --scenario-b
```

The fixture file is exactly `ROM[512] || RAM_INITIALIZATION[10]`; no runtime
archive/parser or firmware is involved. SHA-256 identities measured from the
generated scenario files are:

| Item | Length | SHA-256 |
|---|---:|---|
| Scenario A ROM + RAM prefix | 522 bytes | `495eb195089d0ee7e73f4090514980b47a5fd4a55869d9e7f46376bce1646948` |
| Scenario B ROM + RAM prefix | 522 bytes | `be1d769bc7c89530a5e09ac60f8cd89858454b0ae604dd0fe506dcd52b154855` |
| Recipe source `tests/sdk/guest_fixture.c` | — | `bf647458d5bb8e362d66876432f30c774924600de44c7ac97a4110d57174d8cb` |
| Recipe interface `tests/sdk/guest_fixture.h` | — | `09811d20d1556a2a356ee0ee86afeb1b811ff8b3f764a160e76c2de94f1865a1` |

The output digest uses no C struct layout, padding, or host byte order. Encode
the following fields in this order as three big-endian `u32`, four big-endian
`u64`, then two big-endian `u32`: arithmetic result, initialized result, BSS
result, requested cycles, elapsed cycles, overshoot cycles, instruction
count, terminal PC, and numeric STOP reason (`1`). The resulting 52-byte
scenario A record hashes to
`e0cb8ba07f599ed85a8217d196f577e539cddbba86f2c930da0ed5f468a806bf`; scenario
B hashes to
`b551afb0fd32171001a3155599f3ee51521a95b7994b4f94fdbb1861790c0cfb`.

The recorded execution environment was Darwin arm64, AppleClang
21.0.0.21000101, CMake 4.4.3, Ninja 1.13.2, schema-2 `sdk-debug` preset and
Debug configuration. CMake 3.20 is the retained provisional minimum and was
not exercised here. These identities describe the local diagnostic run;
they are not a supported-platform matrix or gameplay performance claim.
