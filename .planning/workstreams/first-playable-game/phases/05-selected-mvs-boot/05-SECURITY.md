---
phase: "05"
slug: "selected-mvs-boot"
status: draft
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 9
asvs_level: 1
created: "2026-10-09"
---

# Phase 05 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

## Trust Boundaries

| Boundary | Description | Data Crossing |
|---|---|---|
| Private archives to local importer and guest runner | Hostile archive bytes are bounded, validated, and kept local. | Private game/BIOS bytes and guest state |
| Guest observations to tracked/public evidence | Only generic, source-qualified outcomes may leave ignored local storage. | Sanitized status, test receipts, public source identity |
| Source and fixture data to expected output | Emulator/reference evidence is not hardware truth; fixture identity and oracle provenance remain explicit. | Diagnostic fixture bytes and expected behavior |
| Source tree to builds and hosted CI | Dependency provenance, source revision, artifact identity, and public-content policy must remain bound. | Source, build artifacts, test receipts |

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|---|---|---|---|---|---|---|
| T-05-01 | Tampering | ZIP directory, member extents, normalized region descriptors | high | mitigate | Validate metadata and spans, reject ambiguous or unsupported records, verify CRC and decoded length before commit. | closed |
| T-05-02 | Denial of service | ZIP expansion, region allocations, guest run | high | mitigate | Enforce independent input/expansion/output limits, bounded decompression and execution, checked arithmetic, allocation-failure tests. | closed |
| T-05-03 | Information disclosure | Importer diagnostics, local qualification, planning/evidence reports | high | mitigate | Use generic diagnostics, ignored local outputs, public-content scans, and staged-evidence review. | closed |
| T-05-04 | Tampering | Transactional native MVS load and instance recovery | medium | mitigate | Validate and construct before replacing accepted instance state; test rejected-load recovery. | closed |
| T-05-05 | Tampering | Guest boot device responses and MAME-derived expectations | high | mitigate | Require guest-driven requests, direct expected device tests, wrong-response controls, pinned oracle ancestry, and unresolved behavior labels. | open |
| T-05-06 | Elevation of privilege | ZIP member names and extraction | medium | mitigate | Do not extract archive members; bound and validate role identifiers and reject traversal/special/ambiguous names. | closed |
| T-05-07 | Information disclosure | Private profile/media identity in logs and docs | medium | mitigate | Keep private identity in ignored local configuration/reports and publish generic results only. | closed |
| T-05-08 | Tampering | Two-archive member selection and transforms | high | mitigate | Pin source identities and placement; validate CRC and content identity before transforms; reject ambiguous pairs. | closed |
| T-05-09 | Denial of service | Two-archive input and expansion | high | mitigate | Apply checked independent and combined ZIP/expanded/output/peak-memory caps before allocation; retain bounded decompression and sanitizer/mutation controls. | closed |
| T-05-10 | Information disclosure | Local qualification and matrix receipts | high | mitigate | Emit generic statuses, retain ignored local reports, and inspect staged data and public receipts for private-derived content. | closed |
| T-05-11 | Tampering | Matrix receipt inventory and source identity | medium | mitigate | Require the seven named MVS tests, a positive denominator, passing result, output digest, and relevant-source digest at the committed revision. | closed |
| T-05-12 | Tampering | Guest checkpoint | high | mitigate | Require a selected guest-written state and source-qualified control-flow evidence with forced-PC, wrong-bank, IRQ, protection, and sound controls. | open |
| T-05-13 | Tampering | MVS device state | high | mitigate | Keep required state per instance and deterministic; add wrong-value and isolation regressions for the selected path. | open |
| T-05-14 | Information disclosure | Local qualifier and RetroArch smoke | high | mitigate | Redact public status and keep traces/captures in ignored storage; audit staged evidence. | closed |
| T-05-15 | Denial of service | Guest run and app smoke | medium | mitigate | Bound guest cycles, app wall time, memory, and diagnostic size; distinguish exhaustion from success. | closed |
| T-05-16 | Tampering | Attract/start classifier | high | mitigate | Require a sourced guest-write predicate, correct sequence, independent observation, and spoofing controls. | open |
| T-05-17 | Information disclosure | Private trace and app capture | high | mitigate | Bound private diagnostic rings, retain local output only in ignored storage, and redact tracked results. | closed |
| T-05-18 | Denial of service | Guest qualification | medium | mitigate | Bound cycles, ring size, and report size; fail acceptance on overflow or exhaustion. | closed |
| T-05-19 | Information disclosure | Safe branch and outgoing diff | high | mitigate | Use a reviewed public base; inspect the complete outgoing diff and author identity; exclude private/local outputs. | open |
| T-05-20 | Tampering | Hosted MVS evidence | high | mitigate | Match event SHA, exact seven test names, positive denominator, source/output digests, and passing aggregate. | open |
| T-05-21 | Tampering | Oracle/manifest and guest checkpoint | high | mitigate | Independently review oracle ancestry and source identity; require direct guest-write predicate and wrong-source/value/order controls; prohibit golden refresh to clear gates. | open |
| T-05-22 | Information disclosure | Private selected qualification and public candidate | high | mitigate | Keep ignored local traces and generic tracked statuses; inspect the full outgoing diff and authors before publication. | open |
| T-05-23 | Denial of service | Guest run and hostile media | medium | mitigate | Preserve importer caps and bounded execution; justify bound changes and run affected sanitizer/fuzz controls. | closed |
| T-05-24 | Tampering | Hosted CI receipt | high | mitigate | Bind eligible event, all seven tests, positive denominator, source/output digests, and aggregate to one final SHA; reject stale/missing/duplicate artifacts. | open |
| T-05-SC (Plan 05-01) | Tampering | Pinned zlib source/dependency build | high | mitigate | Vendor pinned zlib 1.3.2 with retained license, offline build, importer-only isolation, and static/shared consumer checks. | closed |
| T-05-SC (Plan 05-02) | Tampering | Pinned zlib source/dependency build | high | mitigate | Retain pinned isolated zlib; add no package or runtime linkage. | closed |
| T-05-SC (Plan 05-03) | Tampering | Pinned zlib source/dependency build | high | mitigate | Reuse the pinned isolated source; add no dependency or runner. | closed |
| T-05-SC (Plan 05-04) | Tampering | Pinned zlib source/dependency build | high | mitigate | Reuse the pinned isolated source; add no dependency or runner. | closed |
| T-05-SC (Plan 05-05) | Tampering | Pinned zlib source/dependency build | high | mitigate | Reuse the pinned isolated source; add no package installation or new dependency. | closed |
| T-05-SC (Plan 05-06) | Tampering | Dependency provenance | high | mitigate | Retain pinned importer-only zlib; add no package installation or transitive dependency. | closed |

*Status: open · closed · open — below high threshold (non-blocking)*
*Only open threats at or above `workflow.security_block_on` count toward `threats_open`.*

## Accepted Risks Log

No accepted risks.

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|---|---:|---:|---:|---|
| 2026-10-09 | 30 plan entries | 21 | 9 blocking high | gsd-security-auditor at `9666b049ee4af65158e12421b5a25563b696e945` |

The hosted PR #2 receipt is for candidate SHA `e80672845fc60d94d8a44eab416377534c9a99f1` (run `38001400110`); it is not mitigation evidence for this audited checkout. That PR remains open with `REVIEW_REQUIRED`. The selected guest has not reached a sourced attract/start predicate. See `05-VALIDATION.md` and `05-HOSTED-QUALIFICATION.md` for evidence boundaries.

## Sign-Off

- [x] All threats have a disposition (`mitigate`)
- [x] Accepted risks documented (none accepted)
- [ ] `threats_open: 0` confirmed
- [ ] `status: verified` set in frontmatter

**Approval:** pending — nine high-severity threats remain open.
