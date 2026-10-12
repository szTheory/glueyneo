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

## Gap-closure audit (Plans 04-07 and 04-08)

| Source | Item | Existing coverage | Closure plan | Status |
|---|---|---|---|---|
| GOAL | Original fixture through native API and actual pinned frontend; bounded sound admissions | 01–06 (native and sound verified; frontend unknown) | 08 actual frontend observations | COVERED |
| REQ | QUAL-03 exact clean build/source identity | 06 incomplete | 07 immutable snapshot and 08 final receipt | COVERED |
| REQ | HOST-02 actual load/input/video/unload | 02/06 unobserved | 08 direct pinned-app diagnosis and smoke | COVERED |
| REQ | TRAC-01, TRAC-03 fixture and controls used by the frontend | 01/03 verified natively | 08 same generated fixture and frontend controls | COVERED |
| REQ | TRAC-02, API-05, SND-01, SND-02 | 01/04/05/06 verified at stated bounded scope | unchanged; full regression in 08 | COVERED |
| RESEARCH | Clean build, exact environment/dependency identities, actual app observation | 06 incomplete | 07/08 | COVERED |
| CONTEXT | P04-C-01 ordinary BIOS-free content path | 01–03 | 08 preserves actual path | COVERED |
| CONTEXT | P04-C-02 visible marker and wrong-input control | 01/02 | 08 actual frontend observation | COVERED |
| CONTEXT | P04-C-03 one generated artifact and maintainer command | 01/03/06 | 07/08 snapshot and receipt | COVERED |

The spec-less probe's eleven applicable unresolved items remain flagged in existing plan assumptions; gap-specific HOST-02 concurrency and QUAL-03 identity questions are carried into Plans 04-07/08. The four unclassified items (TRAC-01, TRAC-03, SND-02, QUAL-03) retain their prior flagged classification. API-05 boundary/precision/concurrency and SND-01 boundary/precision/concurrency are covered by executed plans and are not new verification gaps. No deferred Phase 05–07 scope is included. The deterministic external-API detector examined the Phase 04 roadmap scope and returned `detected:false`; the existing Libretro ABI `COVERAGE.md` remains the coverage contract. Existing and new plans contain no ORM schema path; no schema-push task applies.
