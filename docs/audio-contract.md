# Native MVS PCM contract

The native MVS API returns caller-owned signed 16-bit interleaved stereo PCM at
48 kHz. This contract describes the owned YM2610 emulation and converter path.
The bounded private scene now has passing native and actual frontend recorder,
route and causal music/fire/release evidence, as scoped below. During a separate
bound normal-route session, the user confirmed recognizable music and firing
effects; see the Phase07 UAT. No broad BIOS,
full-game or physical-silicon compatibility follows.

## Installed C sound consumer

From the repository root on the selected macOS/Ninja configuration, this recipe
uses the existing C17 consumer linked only through `Glueyneo::glueyneo` and the
installed public header. The original generated GNMV sound fixture contains no
commercial ROM or BIOS bytes. It exercises SSG and ADPCM-B; generated output
stays under ignored `build/`. Keep the configured build's static/shared choice;
relocated package checks exercise both choices separately.

<!-- installed-sound:begin -->
```sh
cmake --preset owned-debug
cmake --build --preset owned-debug
cmake --install build/owned-debug --prefix build/sound-prefix
cmake -S tests/consumers -B build/sound-consumer -G Ninja -DGlueyneo_DIR="$PWD/build/sound-prefix/lib/cmake/Glueyneo" -DGLUEYNEO_CONSUMER_C_SOURCE="$PWD/examples/diagnostic.c"
cmake --build build/sound-consumer
build/sound-consumer/glueyneo-installed-sound --write-fixture build/public-sound-mvs.bin
build/sound-consumer/glueyneo-installed-sound build/public-sound-mvs.bin --trace build/installed-sound.trace
```

The compiled recipe in `tests/consumers/sound_consumer.c` calls `gn_create`,
loads immutable normalized regions through `gn_load_mvs_v3`, and queries
`gn_mvs_audio_capacity_v1` before allocating `capacity * 2` signed-16 samples.
It sets `GN_MVS_FRAME_REQUEST_V1_VERSION`, supplies caller-owned XRGB8888 and
PCM buffers, then calls `gn_mvs_advance_frame_v1` with `sizeof(request)` and
`sizeof(result)`. It checks `GN_MVS_FRAME_RESULT_V1_VERSION`, 48000 Hz, two
channels, generated/delivered/discarded counts and produced pixels. Four frames
exercise tone, firing and release; `gn_reset` repeats the same frames with fire
omitted to test cause at equal boundaries. `gn_destroy` releases the instance;
the consumer releases its file/media/output buffers.
<!-- installed-sound:end -->

The executable emits one `SDK_SOUND` record with `outcome=pass`, `frames=4` and
tone/fire/release pass only after its independent signal/omission checks. It
writes a bounded canonical little-endian trace of clocks, lengths, pixels and
PCM. `test_playable_install.py` compares real installed output with the current
native reference. Relocated static/shared package tests execute this same C
source with the original generated fixture, verify the documentation/API binding,
and compare every trace byte; shared linkage uses its actual loader checks.
This consumer has no audio-device or private-game playback claim.

## Source stream and rational conversion

The pinned `ymfm` source is revision
`81aec25ccbb98f4873a255f7551ac4dadac59b4a`, retained under
`third_party/ymfm/NOTICE.md`. At YM2610 MAX fidelity, `sample_rate()` returns
input clock divided by 16. Glueyneo clocks the candidate by two YM input clocks
per Z80 tick, with one Z80 tick per three main CPU clocks. This yields a 500 kHz
native source for the owned 8 MHz YM input. The consumer rate is 48 kHz, so the
exact conversion ratio is 12/125.

The converter keeps a causal, zero-initialized history and rational phase in
each MVS instance. It emits samples as the source advances, retains history
between calls, and does not flush or pad at frame boundaries. A 500,000-sample
source stream therefore produces exactly 48,000 output frames. The 80-tap
linear-phase midpoint is 39.5 source samples (79 microseconds, or 3.792 output
frames); startup silence is part of that delay.

## Caller ownership, discard, and lifecycle

The capacity query is side-effect-free and returns 812 frames for a loaded
supported MVS instance. The current capacity proof uses a202,752-main-clock
logical frame and at most159 clocks of atomic event excess. Current owned
DIVS.W immediate can take160 clocks (156 plus4 EA), exceeding the earlier
RESET-only subset bound. Main/Z80 remainder2, YM divider remainder15 and
converter phase124 give at most67,637 Z80 ticks,135,274 YM clocks,8,455 native
samples and `floor((12*8455+124)/125) = 812` output frames. Frame carry repays
excess on the next call; no timing is truncated to fit the buffer. The CPU
subset and worst-case instruction regression provide source-model ancestry.

A non-null audio pointer must be aligned for `int16_t`
and advertise at least 812 stereo frames; larger capacities are accepted. A
null pointer is valid only with capacity zero. The request, result, pixel, and
audio ranges may not overlap. The caller owns all buffers for the duration of
the call and provides storage for the full advertised capacity.

`audio_frames_generated` counts output frames produced by the converter during
the call. `audio_frames_delivered` counts the prefix written into the caller's
buffer. `audio_frames_discarded` is the generated count minus the delivered
count. With `audio == NULL` and capacity zero, the YM2610, converter history,
and rational phase still advance; all generated frames are reported as
discarded, and the core retains no queued samples. `gn_run` and `gn_run_mvs`
also advance the same bounded converter state without attaching a sink.

Preflight rejects malformed versions/sizes, unsupported inputs, bad geometry,
short capacity, misalignment, overflow, and buffer overlap before changing
guest inputs, CPU state, converter state, result storage, or caller buffers.
After emulation begins, an error returns the actual consumed CPU clocks and
the valid PCM prefix already written. It does not rewind the guest or claim
that the requested frame was untouched; the caller decides whether to continue
from that state or explicitly reset it.

`gn_reset` clears guest and converter history while keeping the loaded media.
A successful load creates a fresh machine and converter state; unload releases
the image and its history. A failed replacement load leaves the prior loaded
image intact. MVS input lines remain held until changed and clear on successful
load or reset. These rules apply per instance, so resetting or reloading one
instance does not alter another instance's ongoing history.

## Mutable sound state and qualified boundaries

Each loaded image owns its `gn_mvs_sound`, Z80 candidate, YM2610 candidate,
callback context, command/reply/NMI state, sound RAM, bank selectors, timer and
IRQ state, failure latch, and audio conversion state. The sound program and
sample pointers refer to immutable bytes owned by that same image; teardown
destroys the chip objects before releasing the media. The YM2610 callback
userdata points back to the owning sound object. The static FIR coefficient
bank is read-only. Source review of the pinned Z80 and YMFM implementations
found no mutable global or lazy singleton state; this review and the tests do
not establish safety for concurrent calls on one instance.

Clock carry is owned at its respective boundary: the board retains main-clock
remainder modulo 3, the YM2610 candidate retains input-clock remainder modulo
16, and the converter retains output phase modulo 125 plus its left/right
80-sample histories and history index. The active PCM sink, its capacity, and
per-call generated/delivered counters are borrowed only for one synchronous
call. The core keeps no sample queue or caller pointer after return. An
emulated watchdog reset inside a call clears chip/filter history while keeping
that call's active sink and already-delivered prefix; external reset, unload,
and destruction happen outside capture and retain no sink.

The private native audit hook hashes both FIR histories and reads those phases,
chip IRQ, bank selectors, clock/sample counts, timer writes, and failure state.
The full-machine test uses a source-generated public fixture and two
distinguishable streams. It compares six complete frame boundaries per owner,
including guest reply, video activity and pixels, bus observations, frame
counts, every delivered PCM sample, and the sound audit. Repeated isolated
runs, interleaved runs, and native worker calls all match the corresponding
owner baseline. The concurrent case requires both calls to make frame progress
while both active intervals overlap. The fixture also records sound-bank
changes, YM timer writes, and IRQ assertion/deassertion transitions. A swapped
owner baseline is rejected. These results qualify independent handles only;
they do not claim same-handle concurrency, shared-instance safety, libretro
reentrancy, or a public snapshot format.

The exact-boundary partition check requests raw budgets of 10,001, 10,003, and
10,007 clocks, then sums the actual consumed clocks. For this generated guest,
the reference reaches the same 30,011-clock endpoint exactly in one call; the
comparison covers 1,250 native samples, 120 PCM frames, PCM bytes, rendered
pixels, video activity, bus observations, and the sound audit. Its intermediate
checkpoints visit nonzero modulo-3, modulo-16, and modulo-125 phases. This is a
supported point for this fixture and trace, not a promise that arbitrary
requested budgets or instruction splits are equivalent. If a future reference
endpoint cannot be reached exactly, the test reports that partition as
unsupported and does not compare unequal execution histories.

Lifecycle qualification advances the distinct peer through its isolated six
frame baseline while the other owner is rejected by a short-capacity
preflight, receives an injected sound tick failure and reset/replay, alternates
captured output with discard, survives a rejected replacement load, unloads
and reloads, and is then destroyed. Each peer boundary compares guest, video,
bus, sound state, PCM bytes, and actual cumulative clocks. The failure path
checks the valid PCM prefix, untouched pixel buffer, and audio canary; the
preflight path verifies caller buffers and the previous sound checkpoint are
unchanged. These are deterministic native test results, not claims about
physical YM2610 behavior or audible game output.

## Frontend submission and consumption

The Libretro MVS adapter queries `gn_mvs_audio_capacity_v1` for each loaded
machine and keeps one fixed, interleaved buffer sized to the published 812-frame
maximum. Each `retro_run` advances exactly one `gn_mvs_advance_frame_v1`
request, which produces video and PCM at the same emulated boundary. The
adapter submits a nonempty block once to `retro_audio_sample_batch_t` when
available. Its returned frame count records what the frontend accepted from
that submission; it does not prove device playback or that a listener heard
the samples.

A full batch return accounts for the full block. A short or zero return drops
only the unaccepted suffix: the adapter does not call the callback again, run
the guest again, or keep a queue for a later frame. A return greater than the
submitted block is clamped to that block for accounting and diagnosed. The
adapter maintains saturating generated, submitted, processed, discarded, and
over-report counters, with one bounded warning for partial acceptance and one
for impossible over-reporting during each load/reset interval. Reset and unload
clear these counters and warning flags. If the batch callback is absent, the
adapter sends every frame through the per-sample callback; if both callbacks
are absent, the produced block is discarded after bounded frame execution.

This frontend accounting is separate from the native result fields: native
`audio_frames_delivered` means written into the caller-owned buffer, while
Libretro callback return values describe submission consumption. `GNFX`
continues to use its existing 800-frame fixture path and does not share the MVS
buffer or timing behavior. The callback harness exercises full, short, zero,
over-reported, per-sample, absent-callback, reset, and unload/reload paths with
the same generated sound guest and native comparison stream.

## Qualified workloads and remaining sound evidence

| Workload or stage | Current bounded evidence | Limit |
| --- | --- | --- |
| Original GNMV sound guest | Z80-programmed SSG tone and ADPCM-B firing block; independent period/correlation, input-omission/release and source-built fixture checks | No FM or ADPCM-A coverage follows from this guest; generated BIOS-role setup is original test code, not SNK firmware |
| Native and installed C | Caller-owned PCM, actual-boundary native/libretro equality, relocated static/shared C signal/control checks and exact fresh-reference PCM/video traces | Same-handle concurrency and a public snapshot/replay format are unsupported |
| Selected private scene | First character on foot in the Mission1 opening, with horizontal movement, firing away from melee, release, combined direction/fire and a short scroll segment | No later level, full title, arbitrary profile or reference-emulator-as-hardware-truth claim |
| Actual pinned RetroArch1.22.2 | Four source-bound normal/action, fire-omission, mute and disabled-route observations; complete callback PCM/RGB replay; exact shared pre-action music; ten fresh visual roles support causal music/fire/release predicates | This is an exact local configuration/workload result; other frontend/OS/architecture/driver configurations remain untested |
| Device and listener | Enabled CoreAudio route is initialized; recorder receipt and adapter delivery are checked separately; a bound normal-route user listening observation confirms recognizable music and firing | The built-in S16LE stereo48000 recorder is upstream of device flush and mute and cannot itself establish physical audibility; the listening result is specific to the observed setup |

The final local collection revalidated four already acquired actual audio traces
before ten fresh visual roles. A reviewed private one-time driver supplied only
those trace objects to the unchanged full runner; every current source, contract,
schedule, replay, PCM and chip check remained active. Its hash-bound owner-only
manifest distinguishes previous audio acquisition from fresh visual acquisition.
No audio window was repeated or relabeled a new observation. All eight visual
predicates and the music/fire/release aggregate pass. Exact code/dependency,
configuration, media, input and output identities remain bound in ignored local
records; no private identities, PCM, captures or derived features are published.
The execution record is [Plan07-05](../.planning/milestones/ws-first-playable-game-2026-10-24/phases/07-sound-and-scenario-qualification/07-05-SUMMARY.md).

The separate listening observation confirms representative scene music and
firing effects during brief normal-route playback. Recorder non-silence, an
active route and byte equality alone cannot supply that judgment. Muted/disabled
recording can stay non-silent at this upstream stage; no physical silence is
asserted. [Phase07 UAT](../.planning/milestones/ws-first-playable-game-2026-10-24/phases/07-sound-and-scenario-qualification/07-UAT.md)
records the observation and acceptance. Intermittent slowdown under reported
heavy host load was not diagnosed or qualified as performance.

The MVS logical frame uses the source-qualified hardware-clock model; host pacing
is frontend-owned. Modeled original guest slowdown is preserved. The original
GNFX diagnostic fixture keeps its separate60Hz/800-frame audio behavior. Neither
these checks nor the development-loop timings establish emulator throughput or
portable performance.

## Filter design and independent response

`tools/audio/design_mvs_pcm.py` derives the coefficients using only Python's
standard library. For each of 12 phases it evaluates

`0.08 * sinc(0.08 * (k - 39.5 + 0.5 - phase/12)) * Kaiser(k, beta=5)`

for each tap `k`, then normalizes each phase by its floating-point sum. The
normalized coefficients are quantized ties away from zero to signed Q1.30.
Phases 0 through 6 are stored in C; phases 7 through 11 are their reversed
complements. The Python test independently derives the bank and checks every
expanded integer coefficient against `src/mvs/mvs_bus.c`.

The response check directly sums the analytic frequency response of every
floating-point phase. It measures DC through 12 kHz in 50 Hz steps, relative to
the mean phase magnitude at 1 kHz. The 30 kHz rejection is the worst phase
magnitude relative to that same reference. These fixed acceptance limits were
set before the public guest-to-PCM tracer: passband deviation at most 1 dB and
30 kHz rejection at least 40 dB.

| Taps | Worst passband deviation | 30 kHz rejection | Stereo MACs per output frame | Result |
| ---: | ---: | ---: | ---: | --- |
| 48 | 1.387119 dB | 21.058337 dB | 96 | Fails both limits |
| 64 | 0.638353 dB | 31.068987 dB | 128 | Fails rejection |
| 72 | 0.410923 dB | 37.994974 dB | 144 | Fails rejection |
| 80 | 0.248329 dB | 51.349654 dB | 160 | Shortest passing candidate evaluated |
| 96 | 0.056964 dB | 54.555501 dB | 192 | Passes |
| 224 | 0.007969 dB | 64.175647 dB | 448 | Passes |

The 80-tap filter costs 7.68 million multiply-accumulates per second at 48 kHz.
“Shortest” applies only to the candidate lengths listed above; no claim is made
about every possible tap count or every frequency outside the measured points.
Directly selecting samples at 48 kHz would fold a 30 kHz input to 18 kHz; the
chosen low-pass response attenuates the tested 30 kHz input by more than 51 dB.

Each floating coefficient is rounded with an error no greater than half a
Q1.30 unit. With 80 taps and the frozen 28,671 mixed-sample bound, the total
coefficient quantization contribution is below 0.002 S16 counts. The largest
quantized phase L1 norm is about 1.333409; the integer proof uses the looser
strict bound of 2.

## Routing, arithmetic, and saturation

The YMFM candidate supplies separate FM left and right samples plus one mono
SSG sample. Each output channel uses

`round_away_from_zero((2 * FM_channel + SSG_mono) / 4)`.

The mixer therefore preserves FM stereo and places the same SSG signal in both
channels. Every source sample enters its channel's 80-sample history. Each
output is an int64 Q1.30 dot product, rounded ties away from zero, then clamped
to signed 16-bit range. The output clamp is part of the defined conversion.

The pinned `ymfm` YM2610 FM path clamps its FM samples to signed 16-bit values.
The SSG output uses the source's three-channel table, whose largest channel
entry is 16,382. A conservative prefilter bound treats the mono lane as no
larger than the sum of all three channel peaks (49,146), even though YMFM's
`MixTo1` resampler scales that sum down. Thus the mixer numerator is bounded by
`2*32,768 + 3*16,382 = 114,682`, and the ties-away mixed sample magnitude is at
most 28,671. With the phase L1 norm below 2, the absolute Q1.30 accumulator is
less than `28,671 * 2 * 2^30`, or 6.2e13, safely within `INT64_MAX`.

The tool tests the 12/125 count, ties-away behavior, alias control, phase L1
norm, group delay, and this accumulator bound. The native C suite feeds
synthetic FM/SSG triplets through the production converter seam to check
500,000-to-48,000 frame count, distinct stereo routing, impulse delay, and
identical output across different source partitions. These synthetic samples
are mathematical converter fixtures, not YM2610 recordings or game-derived
goldens.

## Evidence ancestry and limits

The 500 kHz source rate and triplet ordering come from the pinned `ymfm`
YM2610 API plus Glueyneo's `src/chips/ym2610_candidate.cpp` and
`src/mvs/mvs_bus.c` clock sequence. The SSG channel amplitude table and the
YM2610 MAX-fidelity 2:1 SSG resampler are in `third_party/ymfm/src/ymfm_ssg.cpp`
and `third_party/ymfm/src/ymfm_opn.cpp`; FM clamping and the left/right sample
assignment are also in `ymfm_opn.cpp`. The test tone's 1 kHz register setting is
derived from these emulation-source rules and the original synthetic BIOS
substitute. Analytic response and arithmetic bounds come from the formulas and
code in `tools/audio/design_mvs_pcm.py`.

These references establish source lineage for this emulator path. They do not
establish electrical YM2610 response, original BIOS behavior, full-game sound
or whether a listener heard audio. Adapter submission is established separately
by callback/actual-frontend evidence above; no claim is inferred from source
lineage alone.


### Internal watchdog reset during output

A watchdog reset is an emulated event inside the synchronous frame call. It
resets chip/filter state while preserving that call's active caller-owned sink,
capacity and delivered prefix. Later samples append once; the reset does not
turn an output request into discard. External `gn_reset`, unload and teardown
run outside active capture and retain no caller sink. The native watchdog test
positions expiry inside a block and verifies18 frames, at least two resets,
exact generated/delivered accounting and output canaries; the adapter observer
regression also preserves uninterrupted successful-video numbering.
