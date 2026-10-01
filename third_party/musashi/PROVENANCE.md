# Musashi experimental source provenance

Candidate status: **under investigation, not admitted**. The second attempt
builds and executes the private guest. Native unoptimized/optimized source
closure passes; full reentrancy, timing and state qualification remain ahead.

Official repository: https://github.com/kstenerud/Musashi
Immutable pin: `313ebf1bd9f4d0d93341eb5ce21fd8a119e9dbdd`.
Six files were explicitly retrieved from raw.githubusercontent.com at this
revision on 2026-10-01, after the freeze commit. No configure-time acquisition.

| Pristine file | SHA-256 |
|---|---|
| m68k.h | 7fb10f51ee36d45f6e2be38d72aa0c57853810a816f1cf19e0f0c600bd1afa4a |
| m68k_in.c | 7a5836fa60ac5c59f77adbcfe086a288d5356c3d373ab15d337986a4e51e0132 |
| m68kconf.h | 8193cf670f6bfe61ad373055e7f44039427174195109bee78167ff3e0630dca4 |
| m68kcpu.c | 0d98c1bfd104929ca393ab6020c05adaa3de5433961cbf924d0ab78a82778405 |
| m68kcpu.h | 372d2086a9c39aadf87d9e0fa42104c5849bd4972ce74b191c0d458208193635 |
| m68kmake.c | c6da040b9f9b4a2a30aabc7b26f7228796ef6090934002d9c8a788d754904788 |

Each copied file retains its complete Karl Stenerud copyright and permissive
grant/disclaimer. The generator also credits R. Belmont for FPU/MMU work.
Those notices remain even though the FPU/MMU dependency files were not copied.
The modified template injects the full upstream grant into both generated
files. There is no SoftFloat, FPU, MMU, disassembler or MAME file in this
vendored subset. The Task 2 audit checks actual compiler dependencies,
preprocessed include ancestry, AST function references, archive members,
undefined symbols and a consumer link map in both optimization lanes.

Recipe: `python3 tools/cpu/adapt.py PRISTINE_DIRECTORY third_party/musashi`,
then compile m68kmake.c as a separate C17 host executable and invoke it with
output directory `third_party/musashi` and input `third_party/musashi/m68k_in.c`.
Only m68kops.c and m68kops.h are generator output; neither was hand-edited.
Generator execution reported 1,967 handlers from 518 primitives.

The attempted patch propagates context arguments, puts mutable dispatch/cycle
storage in the context, removes global default-callback observations and
excludes external FPU/MMU calls. The second attempt repairs direct immediate
context calls, namespaces private statuses, and replaces excluded SoftFloat
integer aliases with existing signed core types in the template. A runtime
archive and real guest execution now pass; this is not backend admission.

The host generator performs allocation, file I/O, logging and process exit.
It is a separate executable; `m68k_in.c` is its input, not a C translation
unit. The native runtime archive contains only adapter, core and generated
opcode objects. Observed host calls are memory operations and current-call
jump-frame operations. Clang emits checked memset in the unoptimized lane
and zero/pattern-fill helpers in the optimized lane; each has an explicit
manifest disposition. No generator or Unity object appears in the linked
private consumer. Other compiler/platform closures remain unqualified.

`tools/cpu/source-manifest.json` records each source, notice, immutable origin,
generated status, compilation role and distributed hash. `audit.py regenerate`
runs two independent parallel scratch generations and compares admitted bytes.
`audit.py budget` replays historical edits, verifies the current recipe from
pristine sources and binds semantic review to the current source identities.
Historical failures remain in the attempt evidence; no source or cap is
silently replaced by these passing narrow checks.

The reproducible source diff and exact adapted/generated identities are in
`experiments/cpu/evidence/attempt-1/`. `record_attempt.py` accepts the six
hash-checked pristine files and writes a fresh receipt directory; its output
is evidence of the failed attempt, not an acceptance result.
