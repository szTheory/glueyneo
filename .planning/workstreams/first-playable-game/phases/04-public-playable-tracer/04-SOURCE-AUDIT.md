# Phase 04 source coverage audit

| Source | Item | Plans | Status |
|---|---|---|---|
| GOAL | Original visible input-driven guest through native API and actual pinned RetroArch; sound admission before integration | 01, 02, 04, 05, 06 | COVERED |
| REQ | TRAC-01 | 01, 03, 06 | COVERED |
| REQ | TRAC-02 | 01, 02 | COVERED |
| REQ | TRAC-03 | 01, 02, 03 | COVERED |
| REQ | HOST-02 | 02, 06 | COVERED |
| REQ | API-05 | 01 | COVERED |
| REQ | SND-01 | 04, 06 | COVERED |
| REQ | SND-02 | 05, 06 | COVERED |
| REQ | QUAL-03 | 06 | COVERED |
| CONTEXT | P04-C-01 ordinary content load and BIOS-free guest entry | 01, 02, 03 | COVERED |
| CONTEXT | P04-C-02 fixed backdrop, guest marker, sampled direction, state/pixels and wrong control | 01, 02 | COVERED |
| CONTEXT | P04-C-03 tracked canonical source/assets, one CMake output, same artifact and one verification command | 01, 03, 06 | COVERED |
| RESEARCH | C17/target-based CMake/CTest, own 68000 bounded subset, local generator | 01, 03 | COVERED |
| RESEARCH | Frame buffer/time/silent-audio contract and malformed-content checks | 01, 02 | COVERED |
| RESEARCH | Actual RetroArch load/input/video/unload; callback harness separately | 02 | COVERED |
| RESEARCH | Z80 source/state/cycle/IRQ/bus/continuation/isolation admission | 04 | COVERED |
| RESEARCH | ymfm source/state/clock/sample/isolation/failure/C static/shared admission | 05 | COVERED |
| RESEARCH | Public rights/oracle ancestry and exact macOS clean-build identities | 03, 06 | COVERED |

The eleven unresolved spec-less edge-probe items remain explicitly flagged in `must_haves.assumptions` across plans 01, 02, 04, 05 and 06; these flags do not replace the requirements. Later production BIOS boot, private game graphics/scrolling, and audible sound are excluded by the active roadmap allocation to Phases 05–07. No Phase 04 source item is missing.
