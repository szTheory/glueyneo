# Owned diagnostic source and rights closure

The source manifest is the current distribution inventory. Each record identifies
exact bytes, origin, MIT notice, update owner, compilation and host-call role.
The earlier state inventory remains the field/callback audit; its source hashes
are dated audit evidence. The current manifest owns refreshed source identities.
Regenerate explicitly with `python3 tools/owned_cpu/inventory.py refresh-manifest`
after reviewed source changes, then run `check` against the actual build closure.
Generated build products are local outputs, not generated runtime source.

Only `cpu.c` enters the owned runtime archive. It uses explicit caller allocator
and bus callbacks and standard C memory operations. Unity is test-only, pinned at
`b6763fbd9cedfacaa89e2ad9fd00d615a234e355`; its three copied source/header files
and MIT notice are retained. No imported CPU, Musashi generator, FPU or SoftFloat
enters this closure. Mechanical source checks are bounded and require independent
review; they are not a complete C parser or a hardware-equivalence proof.

The original MIT guest recipe is `tests/cpu/guest_fixture.c`. Its two four-byte
big-endian stores are `0000000a` and `00000010`; the manifest records their output
digests and recipe identity. No commercial ROM, BIOS, private capture or manual
bytes are distributed. Original test expectations and boundary cases are grounded
in the Motorola/NXP manuals cited with revision, date, sections and limitations
in `ORACLE.md` and `CONTRACT.md`. Instruction shifts, widths and sign extension
use the existing manual-derived semantics boundaries under UBSan.

Musashi and MAME comparison receipts remain historical. SingleStepTests m68000
is generated from MAME; Rocket68 describes Musashi and that corpus as test inputs.
Agreement within this ancestry cannot establish independent hardware truth.
No physical silicon capture, full instruction-set, board timing, public ABI,
durable-save, gameplay-performance or additional-platform claim is made.

Derived acceptance records, ledger and independent review are excluded from the
source manifest to avoid recursive digests. The collector separately binds these
evidence identities. Build caches, executables and logs remain ignored local
products; their digests and sanitized observations are recorded in run receipts.
