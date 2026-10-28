# ymfm YM2610 candidate notice and inventory

Glueyneo includes a selected source closure from `aaronsgiles/ymfm`, upstream revision `81aec25ccbb98f4873a255f7551ac4dadac59b4a` (reviewed 2026-10-07). The upstream license is reproduced verbatim in [LICENSE](LICENSE). Glueyneo keeps narrow local patches for the reset repair, checked private continuation traversal, and test-only allocation instrumentation below. The current source hashes identify the exact included bytes.

## Included source closure

All paths below are copied from upstream `src/`; SHA-256 is over the exact tracked file bytes.

| Path | SHA-256 |
|---|---|
| `LICENSE` | `2d2e9213c170a9866c616fa85b6da993a6724e10befc61f468ed9bfb84c4691c` |
| `src/ymfm.h` | `cfee36f433c6ddb705e33448f58b4792634f99f3702c3b56618727e6c871dc9b` |
| `src/ymfm_adpcm.cpp` | `c02fee503f12472e8450b24a4869dc1f4430575d9343cce7c3abdee2394b2a37` |
| `src/ymfm_adpcm.h` | `7f60f28e358265f878fa82381d61779f39a74392eea538e0a5d89ef50feb7f47` |
| `src/ymfm_fm.h` | `ea4e9d89f16208b878d70d7015ae7e2adbd01a24323d3ca3208040f78475a8e3` |
| `src/ymfm_fm.ipp` | `46a31435d24393d15f0a3c78a6c37e80e7b92f39c48f9f80b91f21f4ec86610c` |
| `src/ymfm_opn.cpp` | `7ff2a907be4af34e3422f16569b591184f93d44e682d46b2f34e91be36a56af4` |
| `src/ymfm_opn.h` | `8b5881221fa0f26712421d34454cba942a68b85e6e394c7b4cc71c8cbe09af84` |
| `src/ymfm_ssg.cpp` | `bf9911f074d4482e8ec7f07e7e227f0b5180c26442ec1ead0165a2b5ceaff196` |
| `src/ymfm_ssg.h` | `27966b0887fe98f2d06a96be2776c911107e2f2a13a64f9a349e1ffc19cf7584` |

The closure is determined by the YM2610 implementation's direct header includes and the linked object references from `ymfm_opn.cpp`: FM templates are included from `ymfm_fm.ipp`; YM2610 owns SSG and ADPCM-A/B engines implemented by the included SSG and ADPCM units. `ymfm_misc.cpp`, other chip families, examples, and the upstream repository build system are not needed. This was checked by compiling the four selected C++ units and inspecting undefined object references on Apple Clang 21.0.1; compiler/runtime support symbols are not additional ymfm source dependencies.

## Local reset patch (2026-10-23)

Plan07-01 commit `4b7896af` adds `ssg_resampler::reset()` and calls it from
`ym2610::reset()`. It clears the per-instance sample index and held SSG output
while preserving the configured ratio. A native regression showed that reset
after a partial-frame failure otherwise differed from a fresh instance at the
first PCM sample. The regression and the selected ASan/UBSan matrix pass with
the patch. This is a Glueyneo lifecycle repair, not a claim about physical chip
reset timing. It adds no global state, allocation, callback or host dependency.
The patch remains under the imported BSD-3-Clause license.

The source table above pins the exact patched bytes. Original upstream hashes
are preserved here for update review:

| Upstream path | Original SHA-256 |
|---|---|
| `src/ymfm_opn.cpp` | `8734c6d5a6e1bf49a08eeb33d260d39c17cd1d26f5db506e5d0d3e416913b489` |
| `src/ymfm_opn.h` | `1950990c3ea0c6d492a20f66a683a372a7367ef39f7830aa65b20a20d1bcbef5` |

On an upstream update, the maintainer must compare this patch with upstream
reset behavior and rerun native reset/failure continuation plus source-closure,
mutable-state, and installed-consumer checks before removing or changing it.

## Checked private YM2610 continuation patch (2026-10-25)

Plan 04-03 adds a narrow canonical big-endian mode to `ymfm_saved_state`; legacy
consumers keep the original little-endian visitor. The checked mode detects sticky
underflow, trailing bytes, invalid booleans/enums, numeric range failures, and
reports consumed length/offset. It adds no public YMFM API promise. The YM2610
candidate owns the private `GYM1` wrapper/chip traversal described field-by-field in
[`docs/state-ym-inventory.md`](../../docs/state-ym-inventory.md). That traversal
includes future-affecting wrapper clocks/timers, the SSG resampler position and held
output, and the YM2610 held FM value omitted by upstream `ym2610::save_restore`.
Restore stages a private candidate with inert callbacks; destination callbacks are
assigned only by the no-allocation/no-callback rebind operation. The patch preserves
the existing C ABI boundary and maps C++ allocation/exception failures to C status
codes.

For the exact patch applied by plan 04-03, SHA-256 of
`git diff 1872445 -- third_party/ymfm/src` is
`e887a5e53dfcedeefcbcc91d0ba54e67e9158cc1a9c5c1a588d77e928e5dc137`. The modified
YMFM files are `ymfm.h`, `ymfm_adpcm.cpp`, `ymfm_adpcm.h`, `ymfm_fm.h`,
`ymfm_fm.ipp`, `ymfm_opn.cpp`, `ymfm_opn.h`, and `ymfm_ssg.cpp`; the table above
records their current source hashes. The initial plan-base SHA-256 values are
retained here for patch review:

| Path | SHA-256 at plan base `1872445` |
|---|---|
| `src/ymfm.h` | `f5ab6fed63c8669abab8403e0e93132e1dad0ae4d8e4954e7836ab9e5b228405` |
| `src/ymfm_adpcm.cpp` | `74e5ded129ea7e532112e5b637d0a7bd4e127fd83331f1fac32011723051d4e0` |
| `src/ymfm_adpcm.h` | `5933691971493b853a9be443f6e6fd74f63869aa21225f66dd89fc20de20914d` |
| `src/ymfm_fm.h` | `1b27bfb7fa4963d7c54cb06fd9bf659450362d8ed496c6af7d487b068cac45c9` |
| `src/ymfm_fm.ipp` | `4fb7fe59d4494a19e9f9c7888eb644a63d86e109fdefb27a8117bf6a5f6ab4b9` |
| `src/ymfm_opn.cpp` | `d4f5b1bb05dbd697e9bc428fe6bcf208436bcece451dc48832365e034803ffbe` |
| `src/ymfm_opn.h` | `e32dc9432f0c79a008e952a1af5d03ebc330353c14592f2fde1b8f91d5ee4ed6` |
| `src/ymfm_ssg.cpp` | `73a3028a77f13f3769b7705079659eb8325431a67b8164ded25e12f324f42bfd` |

The source changes are Glueyneo-owned, limited to private save/restore validation,
read-only cache handling, the missing held-output field, and test-only allocation /
lifetime hooks. No package is added. The source map derives from the upstream
`save_restore` implementations and checked consumer operations; state v1 remains
private and requires review and a version decision if the selected YMFM revision or
candidate configuration changes.

## Test-only allocation-site instrumentation (2026-10-26)

Plan 04-06 adds allocation-site callbacks only when Glueyneo test-hook compile
definitions are enabled. They run immediately before the actual ADPCM-A,
ADPCM-B, FM-channel, FM-operator, and checked saved-state vector allocations;
the private candidate wrapper also marks its own staged object creation. The
callback throws `std::bad_alloc` at one selected point so the C ABI restore path
can verify cleanup and status translation. Its thread-local measurement scope
records point index, source site, requested object bytes, high-water object
bytes, and object lifetime balance. The vector observer records its real
capacity after growth. Production builds omit the hook calls and API. These
hooks add no dependency, production mutable state, serialization change, or
callback to the live chip.

## ADPCM-B EOS continuation range fix (2026-10-26)

The checked YM2610 state traversal no longer rejects EOS status bit 7. Upstream's
`ym2610::clock_fm_and_adpcm` records ADPCM-B's internal EOS latch in bit 6 and
its visible edge in bit 7, so both bits can be present in a valid continuation.
The earlier `m_eos_status <= 0x7f` check rejected those captured states even
though the same implementation sets the high bit. The regression validates a
state carrying all EOS bits and retains the independent address, boolean, enum,
and nested range rejections. This changes only private state validation; it
does not change register behavior, state layout, or the public API.

For the exact instrumentation patch from the supplied plan baseline
`8e823e98902b3adc5398e93e98cafadf679783a2`, SHA-256 of
`git diff 8e823e98 -- third_party/ymfm/src` is
`3bf205f4948cb3e08ad2ec42660063648e49f233a28b2c27bb8d1819c0143c17`.
Immediately before this patch, the three changed files had these SHA-256 values:

| Path | SHA-256 before 04-06 |
|---|---|
| `src/ymfm.h` | `94a7ffc0e2034a18bab58aaed80006bd715a7453e9e5eed735a205134e25f398` |
| `src/ymfm_adpcm.cpp` | `5c4ac7688163e3d13808964ff34391528339434489a7b91b24327aedeae8aedf` |
| `src/ymfm_fm.ipp` | `ee34c061329ad0cdd9fea0acb6257a7283639fc2f1b437b112f2856041e81ff3` |

The callback edits are Glueyneo-owned test instrumentation under the
BSD-3-Clause license. Reported object-byte totals exclude allocator metadata.

## SSG resampler held-output range check (2026-10-26)

The phase 04 security audit (threat T-04-06) found that the checked traversal
accepted arbitrary signed SSG resampler held outputs (`m_last.data`). With the
sample index odd, MAX-fidelity resampling consumes those lanes before the next
refresh, so a crafted `INT32_MAX` lane overflows the signed sums in
`add_last`/`write_to_output`. `ssg_resampler::save_restore` now requires each
held lane to lie in `0..16382`. That is the full range of `ssg_engine::output()`'s
`s_amplitudes` table, the only source of these values. The hostile matrix adds the
nested `state.ym.ssg-held-range` recipe and per-lane boundary checks (16382
accepted; 16383 and `0xffffffff` rejected). Only private state validation
changes. Register behavior, state layout, and the public API stay the same.
`src/ymfm_opn.cpp` SHA-256 before this patch:
`5ff5d9ffcbe82d444f86bea2d8c3b7ba4dcd7bfdb7ac4f3d2732138d41a5cad4`.

## Read-only relation accessors (2026-10-26)

Plan 04-09 adds `fm_engine_base::irq_state()` and
`fm_engine_base::timer_running(uint32_t)` in `src/ymfm_fm.h`, plus
`ym2610::fm_engine_state()` in `src/ymfm_opn.h`. They let the staged native
restore compare wrapper state with chip state in plans 04-09 and 04-10. These
accessors only read existing fields: they add no state, allocation, callback,
or timing side effect. On an upstream update or relation-check change, review
the accessor field semantics and all staged callers, rerun positive captured
state and the affected hostile relation regressions, and update the recorded
hashes and rights inventory.

## State, callback, timing, and failure inventory

- **Mutable global state:** no mutable namespace/global state was found in the selected implementation units. Function-local/static tables found by source scan are immutable lookup tables (`const`); compile-time chip constants are `static constexpr`. This does not establish thread safety for shared instances: one thread per instance is required.
- **Per-chip mutable state:** `ymfm::ym2610` owns address/fidelity/channel-mask, EOS/IRQ mask, last FM output, FM engine, SSG engine/resampler, and ADPCM-A/B engines. The FM, SSG and ADPCM classes each own their register, phase/envelope/timer, resampler/decoder, and channel state; each selected instance receives its own interface reference and callback path.
- **Interface/callback state:** `ymfm_interface` stores a pointer to engine callbacks assigned during engine construction. It can call mode-write/interrupt synchronization, timer scheduling/cancellation, busy-end/current-busy, IRQ updates, external reads, and external writes. The wrapper copies the callback table, retains explicit userdata, checks ADPCM-A/ADPCM-B/I/O address lengths before forwarding reads/writes, limits userdata lifetime to the candidate instance, and rejects reentrant calls.
- **External callback access classes:** upstream uses `ACCESS_ADPCM_A`, `ACCESS_ADPCM_B`, and `ACCESS_IO`. Every address must be checked by the wrapper before forwarding; failed callbacks latch the instance in an error state.
- **Lazy initialization/races:** the selected units show no mutable lazy singleton or process-global initialization. Static lookup tables are constant. Independent-instance tests remain necessary and do not establish safety for concurrent use of a single object.
- **Exceptions/allocation:** `ymfm.h` uses standard C++ containers and allocation in `ymfm_saved_state`; object construction can allocate and upstream operations may throw. Every C ABI entry point must catch all exceptions. Any exception or callback error becomes a stable C failure status and latches failure; no C++ exception may cross the boundary.
- **State serialization:** upstream `ymfm_saved_state` remains an internal visitor. Glueyneo's explicit checked mode and private `GYM1` candidate state are described in [`docs/state-ym-inventory.md`](../../docs/state-ym-inventory.md); they are not exported save-state APIs or a durable snapshot promise. The bounded YM continuation gate compares nonzero future PCM/timer/IRQ after staged restore and destination callback rebinding; it does not establish broad driver/game compatibility.
- **Clock/sample assumptions:** YM2610's documented API requires the consumer to clock the chip and call `generate`; `sample_rate(input_clock)` is clock divided by 144 for MIN/MED fidelity and divided by 16 for MAX. The candidate fixes MAX fidelity and uses an integer rational accumulator at a caller-supplied input clock; it emits only complete chip-native sample ticks. No host wall clock, resampling, or frontend audio API is used.
- **Evidence limit:** source and compile closure are reviewed; YM2610-specific determinism, reset, instance isolation, failure containment, static/shared C consumption and admission are established only by the executable gate report. None of this establishes audible game output, driver compatibility, or physical-hardware fidelity.

## MVS board integration inventory (2026-10-15)

The owned C17 `gn_mvs_sound` owns one opaque candidate per instance, its IRQ
level, and borrowed immutable sample pointer/size. The image owns those sample
bytes and destroys the chip before releasing its media. The copied callback
table points back to that same sound instance; no global owner or singleton is
introduced. ADPCM-A and B reads use checked offsets into the normalized sample
region (the pinned MAME fallback is documented as S26 in docs/mvs-media.md).
Missing or out-of-bounds sample reads latch failure instead of substituting
bytes. This does not claim the mapped span covers all chip address patterns.

At each Z80 edge the board clocks two YM input clocks before the CPU bus
operation; the existing three-main-clock remainder carries between calls.
The wrapper retains its own clock/sample remainder, busy end, timer due/active
state, failure latch, chip registers/engines and callback reentry flag. IRQ
updates affect only the owning Z80's next tick. Reset clears the wrapper's
timing/failure state and invokes the chip's reset; destroy releases ownership.
The C read entry has the same argument, callback and exception containment as
write/clock and writes the output byte only after successful completion.

The runtime embeds this same pinned source closure with hidden symbols and
C++14 behind the private C interface, including builds with admission tests
disabled. At the original integration boundary samples were discarded. Phase07 now
streams samples into the per-instance bounded PCM converter described in
`docs/audio-contract.md`; discard remains an explicit caller option. No frontend device, host timing, audible-output, snapshot format,
selected-driver or physical-hardware claim is added.
