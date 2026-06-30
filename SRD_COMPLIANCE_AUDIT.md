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

## Beyond monsters (not yet enumerated — follow-up)
- **Spells (432 loaded):** far more than the SRD spell list. Verify each is SRD and that descriptive
  text is paraphrased, not verbatim. (Spell *mechanics* are fine.)
- **Subclasses (~48 across 12 classes) & backgrounds (16):** likely exceed SRD inclusion. Restrict to
  SRD entries or rewrite. Drop any PI subclass names.
- **Species (10):** verify against SRD species list.

## Recommended remediation order (batches B2, B3)
1. **B2** — Delete/rename TIER 1 (and confirmed TIER 2) monsters; keep stat-block mechanics.
2. **B3** — Audit spells/subclasses/backgrounds for non-SRD entries + verbatim text; add the
   attribution line and a `LICENSE`/`NOTICE` file:
   > *"This work includes material from the System Reference Document 5.2.1 by Wizards of the Coast
   > LLC, available under CC-BY-4.0."*
3. Legal review before any commercial release.
