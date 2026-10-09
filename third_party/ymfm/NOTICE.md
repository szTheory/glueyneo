# ymfm YM2610 candidate notice and inventory

Glueyneo includes a selected source closure from `aaronsgiles/ymfm`, upstream revision `81aec25ccbb98f4873a255f7551ac4dadac59b4a` (reviewed 2026-10-07). The upstream license is reproduced verbatim in [LICENSE](LICENSE). No upstream source has been modified.

## Included source closure

All paths below are copied from upstream `src/`; SHA-256 is over the exact tracked file bytes.

| Path | SHA-256 |
|---|---|
| `LICENSE` | `2d2e9213c170a9866c616fa85b6da993a6724e10befc61f468ed9bfb84c4691c` |
| `src/ymfm.h` | `f5ab6fed63c8669abab8403e0e93132e1dad0ae4d8e4954e7836ab9e5b228405` |
| `src/ymfm_adpcm.cpp` | `74e5ded129ea7e532112e5b637d0a7bd4e127fd83331f1fac32011723051d4e0` |
| `src/ymfm_adpcm.h` | `5933691971493b853a9be443f6e6fd74f63869aa21225f66dd89fc20de20914d` |
| `src/ymfm_fm.h` | `1b27bfb7fa4963d7c54cb06fd9bf659450362d8ed496c6af7d487b068cac45c9` |
| `src/ymfm_fm.ipp` | `4fb7fe59d4494a19e9f9c7888eb644a63d86e109fdefb27a8117bf6a5f6ab4b9` |
| `src/ymfm_opn.cpp` | `8734c6d5a6e1bf49a08eeb33d260d39c17cd1d26f5db506e5d0d3e416913b489` |
| `src/ymfm_opn.h` | `1950990c3ea0c6d492a20f66a683a372a7367ef39f7830aa65b20a20d1bcbef5` |
| `src/ymfm_ssg.cpp` | `73a3028a77f13f3769b7705079659eb8325431a67b8164ded25e12f324f42bfd` |
| `src/ymfm_ssg.h` | `27966b0887fe98f2d06a96be2776c911107e2f2a13a64f9a349e1ffc19cf7584` |

The closure is determined by the YM2610 implementation's direct header includes and the linked object references from `ymfm_opn.cpp`: FM templates are included from `ymfm_fm.ipp`; YM2610 owns SSG and ADPCM-A/B engines implemented by the included SSG and ADPCM units. `ymfm_misc.cpp`, other chip families, examples, and the upstream repository build system are not needed. This was checked by compiling the four selected C++ units and inspecting undefined object references on Apple Clang 21.0.1; compiler/runtime support symbols are not additional ymfm source dependencies.

## State, callback, timing, and failure inventory

- **Mutable global state:** no mutable namespace/global state was found in the selected implementation units. Function-local/static tables found by source scan are immutable lookup tables (`const`); compile-time chip constants are `static constexpr`. This does not establish thread safety for shared instances: one thread per instance is required.
- **Per-chip mutable state:** `ymfm::ym2610` owns address/fidelity/channel-mask, EOS/IRQ mask, last FM output, FM engine, SSG engine/resampler, and ADPCM-A/B engines. The FM, SSG and ADPCM classes each own their register, phase/envelope/timer, resampler/decoder, and channel state; each selected instance receives its own interface reference and callback path.
- **Interface/callback state:** `ymfm_interface` stores a pointer to engine callbacks assigned during engine construction. It can call mode-write/interrupt synchronization, timer scheduling/cancellation, busy-end/current-busy, IRQ updates, external reads, and external writes. The wrapper copies the callback table, retains explicit userdata, checks ADPCM-A/ADPCM-B/I/O address lengths before forwarding reads/writes, limits userdata lifetime to the candidate instance, and rejects reentrant calls.
- **External callback access classes:** upstream uses `ACCESS_ADPCM_A`, `ACCESS_ADPCM_B`, and `ACCESS_IO`. Every address must be checked by the wrapper before forwarding; failed callbacks latch the instance in an error state.
- **Lazy initialization/races:** the selected units show no mutable lazy singleton or process-global initialization. Static lookup tables are constant. Independent-instance tests remain necessary and do not establish safety for concurrent use of a single object.
- **Exceptions/allocation:** `ymfm.h` uses standard C++ containers and allocation in `ymfm_saved_state`; object construction can allocate and upstream operations may throw. Every C ABI entry point must catch all exceptions. Any exception or callback error becomes a stable C failure status and latches failure; no C++ exception may cross the boundary.
- **State serialization:** upstream `ymfm_saved_state` is an internal byte-vector visitor, with no version, size cap, format identifier, or validation contract of its own (restore reads missing bytes as zero). Glueyneo does not expose it as public save state or promise durable snapshots. The admission test compares replay at the explicitly supported reset boundary only.
- **Clock/sample assumptions:** YM2610's documented API requires the consumer to clock the chip and call `generate`; `sample_rate(input_clock)` is clock divided by 144 for MIN/MED fidelity and divided by 16 for MAX. The candidate fixes MAX fidelity and uses an integer rational accumulator at a caller-supplied input clock; it emits only complete chip-native sample ticks. No host wall clock, resampling, or frontend audio API is used.
- **Evidence limit:** source and compile closure are reviewed; YM2610-specific determinism, reset, instance isolation, failure containment, static/shared C consumption and admission are established only by the executable gate report. None of this establishes audible game output, driver compatibility, or physical-hardware fidelity.
