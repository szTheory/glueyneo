# Plan 01-17 independent ILLEGAL saved-PC adjudication

## Baseline and evidence binding

This fresh non-author reviewer owns this report only. Verdict: **ambiguous**. The question is whether original MC68000 exact `0x4afc` at `$100` stacks `$100` or `$102` for vector 4, under the unchanged diagnostic contract.

Task 1 commit: `23291ff`. Independently read committed acquisition JSON SHA-256: `4278e050a270d8ba662dc7ba4c89eeed58e950166cc7ae5b4cf1af1c425d6adf`; its bytes equal the working copy. Baseline revision: `f0af6bc3815d35c52c06db3c04cf75da6f147991`. All 181 recorded protected-file hashes match. Original reconciliation SHA-256 remains `03130a6b9499c176842ce489ed12ab92afa81e682a45182914baefda8f32fee4`. Strict base64 decoding of its frozen contract reproduces active CONTRACT byte-for-byte, SHA-256 `6ec5b901efb87618b2a03e348bd3fc068e28ae0fc24665a4c041067a1f0c2f73`.

The baseline ledger Git blob independently hashes to `7c4d47c31d173c7874835cae8f5743b652344163cf77f14f91a8f8132f334b09`; all 19 preceding entries remain an equal prefix and every non-entry field is unchanged. Task 1 reports 37,034 charged seconds, no pause, against the frozen 115,200-second cap. The executor owns subsequent review/closeout charges. No budget, contract, historical evidence or finding is amended here.

Read scope includes AGENTS, PROJECT/STATE, METHODOLOGY, exact Task 2, CONTRACT, original reconciliation/archive, active REVIEW F14-03, SECURITY T-01-15-03, actual `tests/owned_cpu/ORACLE.md`, and Plan 01-16 SUMMARY. The frozen row requires next PC; the preserved runtime/fixture/oracle expect fault PC. Earlier native passes and seals are historical observations, not new adjudication evidence.

## New authority and applicability

Independently hashed all ten acquired candidates and reopened all eight PDFs with available `pdftotext`, using one-based extraction pages mapped to zero-based PDF indices. Local raw bytes remain outside repository distribution. No additional distinct document, installation, native execution, physical capture or vendor contact was used. The following digests match the committed acquisition record:

| ID | SHA-256 |
|---|---|
| UM | `89b690b1923f8a3cff508567090bcab0bcd07511c2deff8ffa393a08efda18e1` |
| PRM | `06e4864b78da0e815054cead9326b7ec9914661f240fd39a455f2061ff47c4e8` |
| PRMER | `8ae8228b3e2e54169a4e50310eafcbc14531740c57638b8c419c9751f4e88dc9` |
| UMAD | `269a7543362ac2dba88e8fe1f9e6f674ad0008be352ab05d2f4ccc2692b2870c` |
| MCUMAD | `1736b083d91ea67e5aee377f4e849868d67b0d24896d49c01ee7360e22e931f0` |
| EC000 | `7d1aa05639541888de8b2ca45d6b34f4c75d3c963d9abc092e522d32d4b04929` |
| REV8 | `e41cbe7e14dc7cb853f1185adb1dcd7043d2a2a3f43cdc909e0f6c146007a8e5` |
| APR83 | `10352b5c90cd4674384adcc3771526511d4b16244e47ab0671e0972eec829d88` |
| ELECTRELIC | `3237de931cffb5ea0dd36e3f0973a3e5e401c3eb68476dfeb2479082c66f7d84` |
| CPUTEST | `10dfbbd56a16a2e080c8b2f9f2d5e7089afd7eca89fbfe7c6227baf61f73a514` |

[UM](https://www.nxp.com/docs/en/reference-manual/MC68000UM.pdf) is Motorola's printed Ninth Edition, copyright 1993, with Freescale watermark. Rev. 9.1/date labels in catalogs and historical project references do not establish a separately printed revised exception rule. Independently confirmed §6.2.3 at printed 6-8/PDF 92; Table 6-3 and §6.2.4 at 6-9/PDF 93; §6.2.5 at 6-11/PDF 95; §6.3.5 at 6-13/PDF 97; §6.3.6 at 6-14/PDF 98; and privilege/tracing §6.3.7/8 at 6-15/PDF 99. Original MC68000 applicability is explicit. The historical §6.2.2/Table-at-6-8 locators are incorrect; Task 1 correctly preserves history while correcting these locators.

[PRM](https://www.nxp.com/docs/en/reference-manual/M68000PRM.pdf), Motorola copyright 1992, §1.1.3 at 1-3/PDF 13 and ILLEGAL at 4-107/PDF 210, gives encoding/vector/stack operation without explicitly specifying which address the stored PC denotes. Its family operation includes a vector-offset word expressly excluded for MC68000/MC68008, so generic family frame details cannot override original-model wording. The copyright is independently printed; a separately printed edition/revision remains unknown. [PRMER](https://www.nxp.com/docs/en/reference-manual/M68000PRMER.pdf), Freescale Rev. 1, 03/2007, page 1/PDF 0 and correction tables page 2/PDF 1, addresses floating-point entries. All four pages provide no ILLEGAL-PC clarification. Silence cannot endorse either rule.

[UMAD](https://www.nxp.com/docs/en/reference-manual/M68000UMAD.pdf), Motorola August 7, 1997/copyright 1997, explicitly supplements M68000UM/AD Revision 8. Its 26 pages address variants, bus/electrical and low-power operation, with no ILLEGAL entry. Independent locator correction: acquisition references PDF 4/printed 4 and PDF 7/printed 7 are wrong. PDF 4 is printed **5**, MC68SEC000 low-power circuitry; PDF 7 is printed **8**, the example trap routine and transition to §3.0 electrical specifications. The latter is not a bus-arbitration heading. These errors do not supply missing saved-PC authority; this verdict uses corrected pages and full-document inspection, not the mistaken summaries. [MCUMAD](https://www.nxp.com/docs/en/reference-manual/MC68000UMAD.pdf), Freescale copyright 2004, four pages, corrects abbreviation, bus-arbitration diagram and package data, without a saved-PC amendment. Revision beyond printed identity remains unknown.

[EC000](https://www.nxp.com/docs/en/reference-manual/EC000UM.pdf), Motorola copyright 1995, is the SCM68000/EC000 **core** manual. Overview 1-1/PDF 13 identifies its MC68000 relationship and delegates instruction detail to UM; 1-2/PDF 14 specifies user-code compatibility and additional core functions. §4.2.3 at 4-13/PDF 97 repeats pre-execution illegal detection. §4.3.3/4 at 4-21/PDF 105 repeats following-PC for traps and the group-2-frame analogy for illegal instructions. This is useful comparative primary text, but neither user-code compatibility nor shared ancestry proves identical supervisor exception-PC semantics on original MC68000 silicon. Even accepting transfer would repeat the ambiguity. MC68010/68020/CPU32 rules and formats are not substituted.

[REV8 archive](https://www.bitsavers.org/components/motorola/68000/68000/M68000UM_AD_M68000_Microprocessor_Users_Manual_Rev8_1993.pdf) is Motorola's printed Ninth Edition/copyright 1993 (PDF 0 and 3), irrespective of filename. Independently checked 6-8/9/11/14 at PDF 100/101/103/106. It repeats the same classification and frame analogy; an independently stored copy of the same edition is not an independent behavioral oracle.

[APR83](https://www.bitsavers.org/components/motorola/68000/68000/MC68000_16-Bit_Microprocessor_Apr83.pdf), Motorola April 1983, ADI-814-R4, copyright 1983, is advance information explicitly about the original MC68000. §5.2.3/Fig. 5-4 at 5-5/PDF 56 gives the usual next-unexecuted PC; §5.2.4 begins there and continues at 5-6/PDF 57 with illegal detected before execution. §5.3.5/6 at 5-9/PDF 60 and §5.3.6/8 at 5-10/PDF 61 identify reserved customer 4AFC and distinguish illegal instructions from executed instructions for tracing. This is genuinely earlier, direct-model primary evidence favoring fault PC. Advance-information status, absence of an instruction-specific PC sentence, and absence of an explicit correction of later wording limit it; earlier omission of the later analogy is not proof of supersession.

[ELECTRELIC](https://electrelic.com/electrelic/node/1625), H. Asano's dated 2021-03-20 article, explicitly narrates fault-PC semantics and shows handler code fetching the opcode through the saved PC. That narrative matters: it is positive corroboration for `$100`, not silence. But there are **zero qualified exact original-silicon frame captures** in the acquired record: no identified original CPU/mask plus known 4AFC site plus raw SR/PC frame plus capture procedure bound together. Handler source and mixed MC68000/8/68010 discussion are not that receipt. [CPUTEST README](https://raw.githubusercontent.com/tonioni/WinUAE/master/cputest/readme.txt) expressly derives CPU logic/expectations from UAE and describes hardware testing capability; this hashed mutable-master README contains no attached exact 4AFC original-silicon result. Contributor attribution is repository context, not proof of a named author printed in these bytes. Neither candidate qualifies as vendor authority or an independent silicon oracle.

All manufacturer documents retain their owners' copyright. Archive hosting is not redistribution permission. This report contains original summaries, public references and digests only. The four search routes have inspectable results; the original-silicon route remains unavailable as qualifying evidence, even though its two candidate documents were accessible. The finite search does not prove no clarifying document or receipt exists elsewhere.

## Competing derivations

**Fault PC `$100`:** combine UM pre-execution illegal detection, usual next-unexecuted PC and absence of instruction execution for tracing. UM's explicit privilege-PC rule and near-identical processing analogy add support. APR83 provides earlier direct-model corroboration. Shared group-1/2 SR16/PC32 frame layout permits the §6.3.6 group-2-frame wording to describe structure without importing trap return-address selection. This is the stronger derivation. Its remaining premise is that the usual rule applies to canonical customer 4AFC without a special saved-PC exception. Neither a priority table nor lack of tracing logically fixes the address stored during exception sequencing. Privilege similarity likewise does not prove every field's value identical.

**Sequential PC `$102`:** treat canonical ILLEGAL's deliberate trap terminology and specific §6.3.6 trap/group-2 wording as importing §6.3.5's following-PC rule. The frozen specific table requires next PC, giving this interpretation local contractual weight. However, the manual classifies illegal as pre-execution group 1, never explicitly reclassifies 4AFC as an executed group-2 instruction, and shares the physical short frame between both groups. A shared frame does not entail shared return address. §6.2.4's next-to-execute-after-processing phrase also need not mean next sequential word. PRM's PC definition does not resolve internal advancement when exception entry stacks it. Thus the sequential derivation is materially weaker, but rejecting it as impossible would still require an interpretive judgment on the scope of the specific analogy.

The issue is saved-PC **selection**, not uncertainty about short-frame layout or vector 4. Neither local frozen prose, implementation agreement, a passing fixture, EC000 repetition, nor emulator consensus independently supplies original-hardware authority.

## Independent verdict

**Verdict: ambiguous**

Applicable sources were available and inspected, so unavailable is not the overall verdict. No resource gate stopped review. No acquired explicit primary statement or qualified silicon receipt settles exact 4AFC saved PC; the stronger fault-PC derivation still relies on the disputed applicability of the general rule. Calling it sufficient against the competing specific wording would require the human judgment expressly reserved by Task 2. I therefore do not issue resolved-fault-pc or resolved-sequential-pc under the unchanged standard.

Confidence is high in provenance binding and retained ambiguity; confidence favors fault PC as an inference, but does not establish an admitted original-silicon claim. Nothing here establishes that the existing C implementation is unsafe or that silicon saves the wrong value.

## Role synthesis

| Role | Recommendation and concrete cost/risk |
|---|---|
| Hardware/oracle | Preserve ambiguity; fault-PC derivation is strongest alternative, with unresolved special-4AFC premise. Qualified authority would resolve it; repeated consensus cannot. |
| C/host safety | Preserve unchanged per-instance code. A premature semantic edit risks changing a correct implementation while adding no safety evidence. |
| Timing/state | Separate architectural PC, functional frame/bus order and pin/board timing. A future semantic decision requires refreshed continuation/source identity and direct frame assertions. |
| Test reliability | Existing `$100` fixture is correlated with implementation/oracle. Direct wrong-PC control remains withheld; it can enforce a chosen contract but cannot choose hardware truth. |
| Provenance/licensing | Exact hashes and corrected locators are reproducible; dated/catalog labels and copied editions are not additional authority. No copyrighted source redistribution or new dependency. |
| Maintenance/product | Retained unknown avoids unsupported claims but blocks SDK admission. An explicit bounded assumption could make progress at the cost of reducing the hardware claim and revising scope through user-reviewed planning. |

Coherent recommendation: keep admission blocked and ask for the exact claim/authority decision below. Strongest alternative is an explicitly labeled fault-PC assumption, not an unqualified hardware resolution. No further search or capture is presently promised as available. Reopening evidence would be an applicable original-MC68000 sentence/correction specifying the 4AFC saved address and resolving the analogy, or a legitimately accessible original-silicon receipt identifying CPU/revision, opcode/address, actual frame bytes, capture method and oracle ancestry. Independent review of a derivation may also reopen the question if its premises defeat the rival reading under the existing standard.

## Remaining finding and admission gates

F14-03 and T-01-15-03 remain **HIGH/open**. CPU-01–05 remain **Pending**. Phase 01 remains **GAPS_FOUND/open**; Phase 02 remains gated. A documentary verdict alone would not implement the declared mitigation. Any later authorized revision/repair must preserve history, reconcile canonical and direct frame/bus behavior, refresh exact source closure and qualification, receive independent review and security reassessment, then pass separate phase-goal verification. No seal, admission, requirement completion, native rerun or next named workflow occurs here.

## Terminal handoff

Return **checkpoint:decision**, **gate: blocking-human**, for original MC68000 `4AFC@$100`: does §6.3.6 import the following-PC selection from §6.3.5, or describe only processing/shared layout while §6.2.3/5 leaves the unexecuted opcode at `$100`? The ten-document finite search and independent challenge leave that premise disputed.

| Choice | Required explicit decision and consequence |
|---|---|
| Preserve unknown (recommended under unchanged claim) | Keep both saved-PC candidates unadjudicated and admission blocked; do not schedule another identical unresolved seal. |
| Bounded claim revision | Explicitly approve: “For this private diagnostic experiment, assume exact original-MC68000 ILLEGAL 4AFC stacks its opcode address (`$100` for this fixture), based on the stronger primary derivation; original-silicon correctness of this saved-PC value remains unverified.” This selects `$100` as an assumption, revises the specific frozen next-PC requirement through a preserved amendment, and narrows the conformance claim. Risk: hardware may contradict the assumption; consumers and return behavior could be affected. User must approve this exact assumption/claim reduction and same-phase replanning; the reviewer cannot apply it or decide how downstream admission criteria change. |
| Identified authoritative route | User identifies a genuinely available clarifying primary document or existing qualified capture and authorizes its bounded adjudication. No such additional route is established by this record; commissioning a new capture needs a concrete separate scope/authority decision. |

Generic continue, silence, or accepting this report does not select an assumption. Following an explicit claim decision or subsequently resolved authority, the concrete separate planning command is `$gsd-plan-phase 01 --gaps`; no repair begins before that workflow. Plan 01-17's bounded evidence work can finish with this terminal decision unresolved; Phase 01 itself is incomplete.

Recorded active review UTC interval: **2026-10-03T15:37:32Z–2026-10-03T15:43:01Z**, **329 seconds**, no inactive wait and no parallel reviewer. Initial AGENTS/PROJECT/STATE read preceded the first recorded clock; add **60 seconds conservative uninstrumented initial-read allowance**, explicitly an estimate rather than a measured interval. Total review charge handed to executor: **389 seconds**. Subsequent report-finalization/commit handling belongs to executor closeout accounting. The measured interval and allowance together remain below the 1,800-second review bound and available frozen headroom.

Final read-only Task 2 structural/preservation command passed **8/8**, exit 0. Independent checks also passed committed evidence equality, **10/10** candidate byte hashes, **181/181** protected hashes, strict frozen archive equality, **19/19** ledger-prefix entries and all non-entry ledger fields. No native tests were run; these are document/provenance checks. Sole repository write is this report; observed other working-tree changes belong to the orchestrator and were left untouched.
