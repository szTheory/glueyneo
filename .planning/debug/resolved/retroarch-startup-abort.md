---
status: resolved
trigger: "to look into the RetroArch startup abort on its own, since it doesn't depend on selected media."
created: 2026-10-09
updated: 2026-10-10
goal: find_and_fix
---

# Debug: pinned RetroArch 1.22.2 startup abort (media-independent)

## Symptoms

Prefilled from recorded Phase 04/05 evidence (not re-asked):

- **expected:** The pinned local `/Applications/RetroArch.app` (Info.plist version 1.22.2, executable SHA-256 `ed90b54434a2899de0ddbfed59f335255fb462c8691bd970a1a761ebb5656d65`, bundle id `com.libretro.dist.RetroArch`) starts, answers `--version`, and can be driven by `tests/libretro/retroarch_smoke.py` to load a core/content, take a screenshot, accept input, unload and exit.
- **actual:** The executable aborts with exit `-6` (SIGABRT) before any frame/screenshot. Even the CLI `--version` probe aborted (04-RESEARCH.md A6 / env table). `/usr/bin/open -n -W -a` returned `kLSNoExecutableErr` despite valid bundle metadata, an executable file, and passing code-signature verification (04-08-SUMMARY.md).
- **errors:** exit status -6 / SIGABRT; LaunchServices `kLSNoExecutableErr`. Unified-log inspection was blocked by the sandbox in prior runs, so no crash reason was captured.
- **timeline:** Never observed working in this project. First seen during Phase 04 research/planning (04-02); not retried since because the launch context was unchanged.
- **repro:** `/Applications/RetroArch.app/Contents/MacOS/RetroArch --version` (no core or content needed). Full smoke: `python3 tests/libretro/retroarch_smoke.py --retroarch /Applications/RetroArch.app --core build/sdk-debug/glueyneo_libretro.dylib --content build/sdk-debug/public-playable.bin`.

## Constraints

- Independent of selected media: do not use private ROM/BIOS or `local/` data for this investigation.
- Prior attempts ran inside an agent sandbox (unified log blocked). Whether the abort is a sandbox/launch-context artifact versus an installation defect is unknown.
- Diagnosing the launch context does not by itself change Phase 04 HOST-02/QUAL-03 or Phase 05 verdicts; record findings as evidence only. Do not edit 04-/05- phase artifacts' verdicts.
- Do not publish personal absolute paths/machine identifiers in committed docs beyond what is already recorded.
- Crash reports may be read from `~/Library/Logs/DiagnosticReports`; keep any copies out of Git.
- **Single-instance rule (user, 2026-10-09):** never run more than one RetroArch at a time. Before every launch run `pgrep -fl RetroArch`; quit leftovers gracefully (`osascript -e 'quit app id "com.libretro.dist.RetroArch"'`), then kill the PID only if it is still there. After each probe confirm none remain. Do not kill an instance this session did not launch; report it at a checkpoint.

## Confounders

- 2026-10-09 21:44 EDT: a RetroArch instance (`/Applications/RetroArch.app/Contents/MacOS/RetroArch`, no args, PPID 1/launchd, started 21:43:10, still alive after >1 min) was running while the debugger's GUI probes were in progress. The session manager did not launch it directly; ownership (debugger probe vs. user) is unconfirmed, so it was not killed. Overlapping instances may affect WindowServer/LaunchServices registration, so any probe result taken while it was alive must be treated as potentially confounded and re-run with zero instances present.
- Follow-up check: pid 14777 had exited by the next `pgrep -fl RetroArch` (no instances remained), without the session manager sending it any signal. That fits a debugger probe that cleaned up after itself, but this is not proven.
- Debugger clarification: the debugger ended pid 14777 with the rule's graceful `osascript -e 'quit app id "com.libretro.dist.RetroArch"'` (no kill). Its origin is still unexplained. H2 (the smoke's AppleScript quit spawning a LaunchServices instance) was tested and refuted. Every result relied on below was re-taken with `pgrep` showing zero instances before launch and none after.

## Current Focus

bug_class: Bohrbug conditioned on launch context (startup abort); Bohrbug (smoke input/screenshot defects)
status_note: Startup abort root cause CONFIRMED (launch context; no host change needed). Three downstream smoke-harness defects (B1 held keys, B2 raw capture, B3 screenshot retry) fixed in the working tree, uncommitted; self-verified 5/5 smoke passes.

reasoning_checkpoint:
  hypothesis: "(A) Startup SIGABRT: AppKit `_RegisterApplication` aborts during `-[NSApplication init]` when RetroArch is spawned from the prior agent launch context (Codex seatbelt sandbox / CTest/Python children of it), which lacks GUI-session registration access. (B) After startup works, the smoke still can't pass because (B1) `inject_key` uses System Events `key code`, which posts keyDown+keyUp back-to-back; RetroArch's cocoa driver samples key state once per frame, so the press is never seen (F8 screenshot hotkey, arrows, Escape all ignored); (B2) RetroArch's default GPU/viewport screenshot (1280x896) includes the OSD 'screenshot saved' notification drawn over the guest marker, so marker detection fails even when input works."
  confirming_evidence:
    - "26/26 crash reports share the _RegisterApplication abort stack under NSApplication init, all from agent/CTest/Python/zsh children of the old context; today `--version`, --diagnose GUI probes, and direct launches succeed both inside and outside the Claude sandbox with zero new .ips."
    - "Single-instance A/B: System Events key code 53 (Escape) x2 -> RetroArch still running; CGEvent keyDown, 150 ms hold, keyUp x2 -> RetroArch exited rc 0. Held F8 -> one PNG per press; System Events F8 -> none."
    - "After held Right presses, the screenshot shows the marker displaced right but overlapped by the OSD text, and decode gives 1280x896 (viewport), not 320x224."
  falsification_test: "(A) A new RetroArch startup .ips with the same stack from this context would refute A. (B1) If held-CGEvent F8 also failed to screenshot with one instance, B1 would be refuted. (B2) If video_gpu_screenshot=false still produced a viewport capture with OSD, B2's fix would be wrong."
  fix_rationale: "(A) is environmental: document the launch-context requirement; no host change is needed in this context. (B1) Post real held key events (CGEventPost keyDown, hold >= several frames, keyUp) so the per-frame state sampler sees them; keep System Events only for bringing RetroArch frontmost, and use CGPreflightPostEventAccess to report missing permission as unavailable instead of silently passing. (B2) Set `video_gpu_screenshot = false` (raw core frame, matches WIDTH/HEIGHT 320x224 constants) and `notification_show_screenshot = false` in the per-run config."
  blind_spots: "Not re-run inside a Codex sandbox to reproduce (A) directly (that runtime is no longer configured); the origin of the 21:43:10 leftover no-arg instance is unexplained (H2 refuted); CGEventPost goes to the frontmost app, so focus stealing by another app during the run could misdirect input."
  candidate_causes:
    - "environment: agent sandbox denies WindowServer/LaunchServices Mach registration (confirmed for A)"
    - "config: quarantine/Gatekeeper/notarization (eliminated: spctl accepted, direct exec works)"
    - "code: smoke input injection timing (confirmed B1); smoke screenshot config (confirmed B2)"
    - "data: core/fixture (eliminated: no-content startup aborted identically in old crash set; fixture loads now)"
  and_gate: "yes for the end-to-end smoke: A, B1 and B2 must all be addressed for a pass; each was independently observed. For the startup abort alone: no, A is sufficient."

next_action: await human verification. The user runs the fixed smoke from their own terminal and confirms `status: pass`; then archive the session and commit through a branch/PR.

## Evidence

- timestamp: 2026-10-09
  checked: `RetroArch --version` inside the Claude Code Bash sandbox and with the sandbox disabled.
  found: Both print `Version: 1.22.2 (Git 69a4f0ea) Nov 20 2025` and exit 0. No abort.
  implication: The original A6 symptom (`--version` aborting) does not reproduce in this launch context; the installation is runnable.

- timestamp: 2026-10-09
  checked: Installation identity — executable SHA-256, `codesign -dv`, `spctl -a -vv`, `xattr -l`.
  found: SHA-256 matches the pin (ed90b544...). Signed Developer ID (team UK699V5ZS8), hardened runtime; `spctl`: accepted, Notarized Developer ID. `com.apple.quarantine` xattr present (Homebrew Cask origin) plus `com.apple.provenance`.
  implication: Not a signature/Gatekeeper/corruption defect. Quarantine is present but notarized apps run with it; the successful `--version` shows it does not block direct exec.

- timestamp: 2026-10-09
  checked: 26 `RetroArch-*.ips` reports in the user DiagnosticReports dir (2026-10-06 .. 2026-10-08), summarized locally (not copied into Git).
  found: Every report is EXC_CRASH SIGABRT, asi "abort() called", with an identical faulting stack: `abort <- HIServices ___RegisterApplication_block_invoke <- _RegisterApplication <- GetCurrentProcess <- AppKit NSMenuBarPresentationInstance _isMenuBarVisible <- _NSInitializeAppContext <- -[NSApplication init]`. Parent processes: cmake (CTest), codex, Python (smoke script), zsh, and "Exited process"; responsibleProc Terminal.
  implication: The abort is AppKit failing to register the process with the window server / LaunchServices during NSApplication init, before RetroArch's own code or any core loads. That is the signature of a context lacking GUI-session Mach service access (e.g. a seatbelt sandbox), not of media, core, config or installation defects. It also explains why `--version` aborted earlier: RetroArch's macOS main creates NSApplication before parsing CLI options.

- timestamp: 2026-10-09 ~21:40
  checked: `retroarch_smoke.py --diagnose` (public GNFX fixture) inside the Claude Bash sandbox.
  found: finding `both-launch-probes-survived`; no_content and core_content both survived the window, cleanup_return_code 0, GL context "cocoagl" created, no new .ips.
  implication: GUI startup (NSApplication init) works in this context. H1 supported: startup abort is launch-context specific.

- timestamp: 2026-10-09 ~21:42
  checked: full `retroarch_smoke.py` (public fixture) inside the sandbox and again with the sandbox disabled.
  found: Both: `blocked_or_unknown`, stage `video`, `survived_before_screenshot: true`, return_code null, reason "RetroArch did not create a software-video screenshot"; no new .ips.
  implication: The startup abort does not occur; the smoke now blocks at a later, different stage (screenshot). CONFOUNDED: see the next entries — a second RetroArch instance may have been alive.

- timestamp: 2026-10-09 ~21:43-21:46
  checked: manual RetroArch launch with the smoke config (scratchpad, outside Git); System Events `key code 100` (F8), a CGEvent held-key F8 (150 ms), and Escape (expected exit_emulator) through both injectors.
  found: No screenshot; RetroArch did not exit on Escape for either injector. `pgrep` then showed a leftover no-arg instance PID 14777, PPID 1, started 21:43:10, still running.
  implication: CONFOUNDED. System Events `set frontmost of process "RetroArch"` / key injection is ambiguous with two RetroArch processes, so these input results can't be trusted. The leftover's shape (no args, PPID launchd) is consistent with a LaunchServices launch, possibly from the smoke's `tell application id ... to quit` (H2).

- timestamp: 2026-10-09 ~21:47
  checked: H2. Zero instances; direct-exec launch; then the smoke's exact `tell application id "com.libretro.dist.RetroArch" to quit`; PIDs sampled each second.
  found: The direct instance exited rc 0 and no new instance appeared.
  implication: H2 refuted. The quit path does not spawn a second instance when the target is alive.

- timestamp: 2026-10-09 ~21:48
  checked: Original smoke (HEAD script) with zero instances and a 1 s PID monitor.
  found: Still `blocked_or_unknown` at stage `video`; exactly one PID for the whole run; none left over.
  implication: The screenshot blocker is real and independent of the confounder.

- timestamp: 2026-10-09 ~21:48
  checked: Single instance. Escape (exit_emulator) via System Events `key code 53` x2, vs a CGEvent held 150 ms x2.
  found: System Events: RetroArch kept running. Held CGEvent: RetroArch exited rc 0.
  implication: B1 confirmed. Instantaneous taps are missed by the per-frame key-state poll; held events are seen.

- timestamp: 2026-10-09 ~21:47-21:49
  checked: Held F8, Left and Right with the default config, then with `video_gpu_screenshot=false` and `notification_show_screenshot=false`.
  found: Default config: 1280x896 viewport PNGs; after Right, the OSD "screenshot saved" text covered the marker and `find_marker` failed. Raw config: 320x224 PNGs, marker (16,16,1) -> Left (16,16,1) -> Right 250 ms (45,16,1).
  implication: B2 confirmed and fixed by config.

- timestamp: 2026-10-09 ~21:50
  checked: Smoke with B1+B2 applied, outside and inside the sandbox.
  found: Still `video` blocked. A manual timing probe from 0.5 s after launch: F8 at about 1 s produced no capture; every F8 from about 3 s on produced one.
  implication: B3 confirmed. The single first screenshot request is lost before the window and frame loop are ready; the old script never retried within its 20 s wait.

- timestamp: 2026-10-09 ~21:52-21:56
  checked: Fixed smoke (B1+B2+B3): 4 runs outside the sandbox and 1 inside the Claude sandbox; zero instances before and after each; DiagnosticReports checked afterwards.
  found: 5/5 `status: pass`, exit 0, `input_response: observed`, marker_before [16,16,1], marker_after_right [46|43,16,1], `frontend_unloaded: true`, no leftover instance, no new .ips.
  implication: The expected smoke flow (launch, screenshot, no-input/wrong-input/right-input controls, quit) runs end-to-end in this launch context.

- timestamp: 2026-10-09 ~21:57
  checked: Regression suites.
  found: test_retroarch_smoke.py 35/35 OK (4 new tests: 2 error and 1 fail against the HEAD script, and the retry test exercises the new loop). test_verify_playable.py 27/27 OK. test_check_phase04_validation_map.py 24/24 OK. CTest (build/sdk-debug) 41/41 passed. `verify_playable.check_docs` OK on the updated guide. Note: the live `check_phase04_validation_map.py` already failed before these changes (`tools/verify_playable.py` differs from its reviewed revision). It will also report `retroarch_smoke.py` as differing; that checker pins Phase 04 reviewed sources and is not run by CTest or CI.
  implication: No regressions in the covered suites.

## Eliminated

- hypothesis: Installation defect (corrupt binary, signature, Gatekeeper or quarantine block).
  evidence: Digest matches the pin; codesign is valid; spctl accepts it as Notarized Developer ID; with quarantine present, `--version` and GUI launches succeed.
  timestamp: 2026-10-09
- hypothesis: The core or fixture causes the abort.
  evidence: The crash stack is in NSApplication init before core load; no-content probes aborted identically in the old context; core and content probes succeed now.
  timestamp: 2026-10-09
- hypothesis: H2, the smoke's `tell application id ... to quit` launches a stray second instance.
  evidence: Controlled zero-instance test: the quit closed the direct instance (rc 0) and spawned nothing.
  timestamp: 2026-10-09
- hypothesis: The Claude Bash sandbox blocks GUI startup or HID event posting.
  evidence: `--version`, the --diagnose probes and the fixed full smoke all pass inside the sandbox; `CGPreflightPostEventAccess` returns true there.
  timestamp: 2026-10-09

## Resolution

root_cause: "Startup abort: launch context. AppKit `_RegisterApplication` called abort() during `-[NSApplication init]` because RetroArch was spawned from the earlier agent-sandboxed context (Codex and its CMake/Python children), which could not register with the logged-in window server. No installation, core or fixture defect. Downstream, three independent smoke-harness defects stopped the expected flow even once startup worked: (B1) System Events `key code` taps were too short for RetroArch's per-frame key-state poll; (B2) the default viewport screenshot (scaled, with OSD notifications) obscured the marker; (B3) the single screenshot request sent 0.5 s after launch was dropped before the window was ready and was never retried."
fix: "No host change. tests/libretro/retroarch_smoke.py: inject_key uses System Events only for frontmost, then posts held Quartz HID key events via ctypes CGEventPost (100 ms hotkey, 250 ms arrows; CGPreflightPostEventAccess denial -> input unavailable); request_screenshot repeats the F8 hotkey every 1 s until a fresh capture appears or the timeout expires; the per-run config adds video_gpu_screenshot=false and notification_show_screenshot=false. Four unit tests were added. docs/first-playable-build.md gets a dated 2026-10-09 note: launch-context requirement plus harness changes; HOST-02 is unchanged (still needs the committed-snapshot receipt)."
verification: "signal_reproduction: original smoke fails at `video` with one instance; fixed smoke passes 5/5 (4 unsandboxed + 1 sandboxed), no leftover instances, no new crash reports. signal_revert: new tests fail against the HEAD script (2 errors, 1 failure) and pass with the fix. signal_regression: smoke 35/35, verify_playable 27/27, validation-map tests 24/24, CTest 41/41, check_docs OK. signal_mechanism: A/B held vs tap Escape; raw vs viewport capture; screenshot readiness timing. signal_scope: diff limited to the smoke harness, its tests and one doc section; Phase 04/05 verdict artifacts untouched."
guardrail_verdict: accepted
oracle_type: specified (marker position and screenshot geometry 320x224 from the GNFX fixture contract); boundary: hold >= 3 frames asserted; retry count bounded by timeout/interval.
session_manager_reverification (2026-10-09, independent re-run after the debugger returned): `pgrep -fl RetroArch` empty before; smoke unit tests 35/35; tests/tools suites (verify_playable + validation-map) 51/51; CTest build/sdk-debug 41/41; live full public-fixture smoke (unsandboxed, exactly one instance) exit 0, status pass, input_response observed, marker [16,16] -> [46,16], frontend_unloaded true; `pgrep -fl RetroArch` empty after; no new RetroArch .ips (newest remains the 2026-10-06 report). User own-terminal confirmation received 2026-10-10 (see human_verification). Phase 04/05 verdicts unchanged; HOST-02 still needs the `tools/verify_playable.py --clean` receipt from a committed snapshot.
files_changed:
  - tests/libretro/retroarch_smoke.py
  - tests/libretro/test_retroarch_smoke.py
  - docs/first-playable-build.md
human_verification: "2026-10-10, user's own terminal outside any agent sandbox: `pgrep -fl RetroArch` empty before; full public-fixture smoke printed status pass, input_response observed, marker [16,16] -> [46,16], frontend_unloaded true; `pgrep -fl RetroArch` empty after. User visually observed RetroArch open and the white marker move horizontally. This confirms the harness in this launch context only; HOST-02 still requires the committed-snapshot receipt."
