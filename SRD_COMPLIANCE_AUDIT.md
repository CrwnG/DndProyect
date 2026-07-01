# SRD 5.2.1 Compliance Audit (Batch B1)

> **Status:** candidate inventory — **not legal advice.** Our content boundary is the **System
> Reference Document 5.2.1** (D&D 2024 rules), licensed **CC-BY-4.0**. Mechanics/rules are not
> copyrightable; the risk is **Product Identity** names/creatures and verbatim descriptive text.
> See root `CLAUDE.md` §6 and memory `dnd-srd-licensing`. **Cross-reference every entry below
> against the official SRD 5.2.1 monster list and get a lawyer before commercial release.**

Generated 2026-06-26 by `scratchpad/srd_audit.py` (re-runnable). Content scanned: ~287 monster
entries, 432 spells, 12 classes, 16 backgrounds, 10 species under `dnd-web-game/backend/app/data/`.

## Why this matters
The repo ships substantially more content than a minimal SRD subset. The 2024 SRD 5.2.1 is broad
(it *added* creatures that were Product Identity in SRD 5.1, e.g. **displacer beast**, **umber
hulk**), but a set of iconic creatures remain **WotC Product Identity, excluded from every SRD**.
Shipping those by name is the main licensing exposure.

## TIER 1 — HIGH confidence Product Identity — ✅ REMOVED (Batch B2, PR pending)
These iconic creatures have **never** appeared in any SRD. All 11 were **deleted** from the
bestiary (`rules/2024/monsters/aberrations.json` + `undead.json`) — pure removal, no other
content reformatted. They were reference-bestiary only (the live `data/enemies/` templates don't
include them and no campaign references them), so gameplay is unaffected. Guarded by
`tests/test_batch49_srd_no_product_identity.py`.

| Family | Entries (id) — removed |
|---|---|
| Beholder-kin | `beholder`, `beholder_zombie`, `gauth`, `gazer`, `spectator` |
| Mind flayer / illithid | `mind_flayer`, `mind_flayer_arcanist`, `elder_brain`, `intellect_devourer`, `cranium_rat`, `neothelid` |

## TIER 2 — MEDIUM confidence (verify against SRD 5.2.1, likely excluded)
| Entry | File | Note |
|---|---|---|
| `star_spawn_hulk`, `star_spawn_mangler`, `star_spawn_seer` | aberrations.json | Mordenkainen's content — likely PI |
| `grell`, `nothic` | aberrations.json | MM/Volo's aberrations — verify |

## TIER 3 — LIKELY OK (scan false-positives; classic SRD or added in 5.2.1 — DO NOT remove without checking)
`displacer_beast`, `umber_hulk` (added to SRD 5.2.1), `bulette`, `grick`, `xorn` (classic SRD 5.1),
`flumph`, `myconid_sprout/adult/sovereign` (verify — plausibly in 5.2.1). Listed only so a reviewer
knows they were considered and cleared.

## B3b — Spells / subclasses / backgrounds / species vs the SRD 5.2.1 lists (2026-07-01)

Diffed by `dnd-web-game/backend/scripts/srd_audit.py` (checked in, re-runnable:
`cd dnd-web-game/backend && python scripts/srd_audit.py`) against
`scripts/srd_521_content.json` — the SRD 5.2.1 name lists extracted from the CC-BY-4.0
SRD text (339 spells — each `####` header validated by its level/school metadata line —
12 subclasses, 4 backgrounds, 9 species; apostrophes stripped in name normalization so
"Hunter's Mark" matches `hunters_mark`). **Name-matching only; verbatim-text similarity
of descriptions is a separate follow-up, and these are extraction results to cross-check
against the official SRD PDF, not conclusions.**

| Content | Shipped | Matching SRD names | NOT in SRD |
|---|---|---|---|
| Spells | 432 | 310 (+15 rename-only) | **107** |
| Subclasses | 48 | 12 (one per class) | **36** |
| Backgrounds | 16 | 4 (Acolyte, Criminal, Sage, Soldier) | **12** |
| Species | 10 | 9 | **1** (`aasimar` — WotC's SRD FAQ explicitly lists it as excluded) |

**Total: 156 entries not matching the SRD lists** — likely sourced from the full 2024
PHB (plus some Xanathar's/Tasha's-era spells, e.g. `steel_wind_strike`, `toll_the_dead`,
the `summon_*` family). Run the scanner for the exact per-entry lists.

**Rename-only (15 spells shipped; 17 mappings):** the same spell exists in the SRD under
a de-branded name (the SRD drops the wizard names) — `bigbys_hand`→`arcane_hand`,
`tashas_hideous_laughter`→`hideous_laughter`, `melfs_acid_arrow`→`acid_arrow`,
`leomunds_tiny_hut`→`tiny_hut`, the four `mordenkainens_*`, both `otilukes_*`,
`ottos_irresistible_dance`, `rarys_telepathic_bond`, `drawmijs_instant_summons`,
`evards_black_tentacles`, `leomunds_secret_chest` (+precautionary `nystuls_magic_aura`→
`arcanists_magic_aura`, `tensers_floating_disk`→`floating_disk`, not currently shipped).
Full map in `scripts/srd_audit.py`.

### Remediation options (product decision — pick one per content type)
1. **Restrict to SRD** — remove the 156 non-SRD entries (safest; biggest content loss:
   36 subclasses → 12 hits character variety hardest).
2. **Rewrite** — keep the rules mechanics, rewrite all descriptive prose in our own words
   and drop PI names. More work; keeps the content breadth. (Commonly held that rules
   mechanics aren't copyrightable, but that's a legal question for a lawyer, not this doc.)
3. **Hybrid (likely)** — restrict backgrounds/species (cheap, low player impact), rewrite
   the high-value subclasses/spells prose over time. The 15 renames look safe and
   mechanical either way.

## Recommended remediation order
1. ✅ **B2** (PR #56) — TIER 1 monsters removed.
2. ✅ **B3a** (PR #57) — NOTICE/attribution shipped.
3. ✅ **B3b** (this section) — non-SRD content enumerated with a re-runnable scanner.
4. **B3c** — apply the 15 spell renames (mechanical, safe).
5. **B3d** — user decision on restrict-vs-rewrite for the 156; then execute per content type.
6. Verbatim-text pass over descriptions of the KEPT SRD entries (paraphrase where copied).
7. Legal review before any commercial release.
