# Walking Skeleton — Glueyneo

**Phase:** 1 — CPU acceptance experiment
**Generated:** 2026-10-01
**Status:** Planned; no execution or backend acceptance is established.

## Capability to Prove End-to-End

A maintainer configures and builds the private C experiment, executes an original arithmetic/store guest through an explicit CPU instance and bounded bus, and checks the observable result against an independently justified oracle.

## Architectural Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Runtime | C17, pinned Musashi 68000 closure, private opaque adapter | Qualify feasibility before public SDK commitment |
| Build/tests | Target-based CMake, CTest, pinned test-only Unity, explicit C runners | Reproducible local execution and nonempty assertions |
| State | Explicit instance, privately constructed tables/callbacks/counters/jump state | Concurrent independent machines without shared current-instance routing |
| Data layer | Bounded guest byte buffers; database not applicable | Guest memory supplies the actual read/write path |
| UI/routing/auth | Not applicable | Native experiment has no browser/service identity surface |
| Deployment | Native local executable; deployed service not applicable | Available toolchain exercises the complete selected stack |
| Host tools | Separate generator and standard-library Python evidence tools | File I/O stays outside runtime linkage |
| Layout | experiments/cpu, third_party/musashi, third_party/unity, tests/cpu, tools/cpu | Concrete private adapter, provenance and tests |
| Timing | Qualified instruction/exception boundaries | Actual progress/overshoot without unsupported board claims |
| Continuation | Explicit guest fields and fresh destination bindings | Private backend proof, no public snapshot compatibility |
| Admission | Frozen cumulative caps and accepted-only completion | Rejection blocks SDK integration |

All choices are reversible local decisions with no published ABI or durable user data.

## Stack Touched in Phase 1

- [ ] Build/test scaffold and pinned admitted source closure.
- [ ] Original guest and exact manual-qualified expectations.
- [ ] CPU instance through dispatch/callbacks to checked memory read/write.
- [ ] Guest-computed observation and consequential wrong-behavior control.
- [ ] Local run: `cmake -S . -B build/cpu -G Ninja -DGLUEYNEO_CPU_EXPERIMENT=ON`, then `cmake --build build/cpu`, then `ctest --test-dir build/cpu -L cpu --output-on-failure --no-tests=error`.
- [ ] Isolation, timing, continuation and accepted-only evidence gate.

## Out of Scope

Public native ABI/installed consumers and board bootstrap remain Phase 2; release platform matrix/hosted delivery remain Phase 3. Graphics/audio, Z80/YM2610, libretro, public snapshots/persistence and commercial BIOS/game claims retain their canonical later scope.

## Subsequent Slices

| Plan/phase | Capability |
|---|---|
| 01-01 | Frozen budget, real guest and reproducible source closure |
| 01-02 | Independent/cold instances and bounded host failures |
| 01-03 | Qualified timing and complete restored continuation |
| 01-04 | Current evidence, independent review and accepted-only admission |
| Phase 2 | Diagnostic SDK and installed consumers after accepted backend |
| Phase 3 | Relocated/offline artifacts and commit-bound unsigned release |

Four sequential waves share adapter/CMake/evidence ownership. The first tracer's coupled-file exception is authorized and documented in 01-01-PLAN.md; subsequent tasks list at most five files. Every plan has two tasks and an end-to-end leading tracer. Independent review uses another agent under standing authorization.
