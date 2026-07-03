# Top-100 Rescueability Review

Generated: 2026-07-03T06:07:55.136270+00:00

## Purpose

Phase 3.2 separates label/product burden from plausible formulation rescueability. The Phase 3.1 scientific rescue signal score ranks how loudly burden appears; the new rescueability score independently estimates whether current evidence links that burden to a potentially modifiable route, formulation, handling, dosing, exposure, storage, device, or presentation issue.

This is deterministic hypothesis generation, not scientific, clinical, formulation, regulatory, patent, commercial, or investment validation.

## Review queue definitions

- small_molecule_reformulation: non-biologic therapeutics with a plausible general formulation question.
- anti_infective_specialist: products requiring resistance, stewardship, infection, or hospital-use context.
- oncology_specialist: classical cytotoxics and oncology biologics/ADCs or specialist agents.
- biologic_delivery_specialist: complex proteins, enzymes, peptides, or toxins with biologic-specific delivery questions.
- immunology_biologic: immunomodulators whose warnings must not be mistaken for intrinsic cytotoxic identity.
- acute_care_or_anaesthesia: ICU, emergency, anaesthesia, paralytic, intrathecal, or acute-administration products.
- deprioritise_or_false_positive: weak links, contextual cytotoxic language, or duplicate family members without an independent rationale.

## Rescueability tiers

- A_strong_near_term_review: strongest non-conflicted, non-duplicate candidates for immediate manual review.
- B_plausible_literature_review: plausible burden-to-fix link with unresolved evidence.
- C_specialist_only_review: oncology, biologic, NTI, or other specialist feasibility/safety context.
- D_deprioritise: weak, crowded, duplicate, or severely conflicted rationale.
- E_likely_false_positive: active-identity correction suggests the prior loud signal is unrelated to formulation rescue.

## Counts by review queue

- acute_care_or_anaesthesia: 5
- anti_infective_specialist: 13
- biologic_delivery_specialist: 8
- deprioritise_or_false_positive: 13
- immunology_biologic: 15
- oncology_specialist: 39
- small_molecule_reformulation: 7

## Counts by rescueability tier

- B_plausible_literature_review: 12
- C_specialist_only_review: 62
- D_deprioritise: 25
- E_likely_false_positive: 1

## Identity correction counts

- true_cytotoxic_antineoplastic_flag: 21
- oncology_biologic_or_adc_flag: 24
- immunomodulator_warning_flag: 18
- cytotoxic_context_only_flag: 27
- duplicate family clusters: 6

## Top 20 by rescueability score

| Order | Ingredient | Rescueability | Burden score | Tier | Queue | Primary hypothesis | Notes |
|---:|---|---:|---:|---|---|---|---|
| 1 | DESMOPRESSIN ACETATE | 14 | 22 | B_plausible_literature_review | small_molecule_reformulation | ready_to_use_or_reconstitution_reduction | Distinct rescueability score based on status, administration/handling, route, PK, evidence quality, identity taxonomy, and toxicity conflict. Primary hypothesis: ready_to_use_or_reconstitution_reduction. This rule-based rank does not establish clinical utility, technical feasibility, regulatory eligibility, patent freedom, or commercial viability. |
| 2 | GANCICLOVIR SODIUM | 12 | 23 | B_plausible_literature_review | anti_infective_specialist | anti_infective_formulation_or_delivery | Distinct rescueability score based on status, administration/handling, route, PK, evidence quality, identity taxonomy, and toxicity conflict. Primary hypothesis: anti_infective_formulation_or_delivery. Phase 3.1 oncology language is treated as contextual because active-identity taxonomy does not support a cytotoxic/oncology classification. This rule-based rank does not establish clinical utility, technical feasibility, regulatory eligibility, patent freedom, or commercial viability. |
| 3 | CEFEPIME HYDROCHLORIDE | 12 | 22 | B_plausible_literature_review | anti_infective_specialist | anti_infective_formulation_or_delivery | Distinct rescueability score based on status, administration/handling, route, PK, evidence quality, identity taxonomy, and toxicity conflict. Primary hypothesis: anti_infective_formulation_or_delivery. Phase 3.1 oncology language is treated as contextual because active-identity taxonomy does not support a cytotoxic/oncology classification. This rule-based rank does not establish clinical utility, technical feasibility, regulatory eligibility, patent freedom, or commercial viability. |
| 4 | CEFTIZOXIME SODIUM | 12 | 22 | B_plausible_literature_review | anti_infective_specialist | anti_infective_formulation_or_delivery | Distinct rescueability score based on status, administration/handling, route, PK, evidence quality, identity taxonomy, and toxicity conflict. Primary hypothesis: anti_infective_formulation_or_delivery. Phase 3.1 oncology language is treated as contextual because active-identity taxonomy does not support a cytotoxic/oncology classification. This rule-based rank does not establish clinical utility, technical feasibility, regulatory eligibility, patent freedom, or commercial viability. |
| 5 | FERRIC PYROPHOSPHATE CITRATE | 12 | 22 | B_plausible_literature_review | small_molecule_reformulation | ready_to_use_or_reconstitution_reduction | Distinct rescueability score based on status, administration/handling, route, PK, evidence quality, identity taxonomy, and toxicity conflict. Primary hypothesis: ready_to_use_or_reconstitution_reduction. This rule-based rank does not establish clinical utility, technical feasibility, regulatory eligibility, patent freedom, or commercial viability. |
| 75 | SODIUM SUCCINATE | 12 | 22 | D_deprioritise | deprioritise_or_false_positive | ready_to_use_or_reconstitution_reduction | Distinct rescueability score based on status, administration/handling, route, PK, evidence quality, identity taxonomy, and toxicity conflict. Primary hypothesis: ready_to_use_or_reconstitution_reduction. Phase 3.1 oncology language is treated as contextual because active-identity taxonomy does not support a cytotoxic/oncology classification. This rule-based rank does not establish clinical utility, technical feasibility, regulatory eligibility, patent freedom, or commercial viability. |
| 6 | TIGECYCLINE | 11 | 23 | B_plausible_literature_review | anti_infective_specialist | anti_infective_formulation_or_delivery | Distinct rescueability score based on status, administration/handling, route, PK, evidence quality, identity taxonomy, and toxicity conflict. Primary hypothesis: anti_infective_formulation_or_delivery. Severe conflict blocks A-tier assignment. This rule-based rank does not establish clinical utility, technical feasibility, regulatory eligibility, patent freedom, or commercial viability. |
| 7 | CASPOFUNGIN ACETATE | 11 | 22 | B_plausible_literature_review | anti_infective_specialist | anti_infective_formulation_or_delivery | Distinct rescueability score based on status, administration/handling, route, PK, evidence quality, identity taxonomy, and toxicity conflict. Primary hypothesis: anti_infective_formulation_or_delivery. Phase 3.1 oncology language is treated as contextual because active-identity taxonomy does not support a cytotoxic/oncology classification. This rule-based rank does not establish clinical utility, technical feasibility, regulatory eligibility, patent freedom, or commercial viability. |
| 8 | HISTRELIN ACETATE | 11 | 22 | B_plausible_literature_review | small_molecule_reformulation | ready_to_use_or_reconstitution_reduction | Distinct rescueability score based on status, administration/handling, route, PK, evidence quality, identity taxonomy, and toxicity conflict. Primary hypothesis: ready_to_use_or_reconstitution_reduction. This rule-based rank does not establish clinical utility, technical feasibility, regulatory eligibility, patent freedom, or commercial viability. |
| 13 | AZATHIOPRINE SODIUM | 10 | 23 | C_specialist_only_review | immunology_biologic | ready_to_use_or_reconstitution_reduction | Distinct rescueability score based on status, administration/handling, route, PK, evidence quality, identity taxonomy, and toxicity conflict. Primary hypothesis: ready_to_use_or_reconstitution_reduction. Phase 3.1 oncology language is treated as contextual because active-identity taxonomy does not support a cytotoxic/oncology classification. This rule-based rank does not establish clinical utility, technical feasibility, regulatory eligibility, patent freedom, or commercial viability. |
| 14 | BLEOMYCIN SULFATE | 10 | 23 | C_specialist_only_review | oncology_specialist | specialist_oncology_formulation | Distinct rescueability score based on status, administration/handling, route, PK, evidence quality, identity taxonomy, and toxicity conflict. Primary hypothesis: specialist_oncology_formulation. This rule-based rank does not establish clinical utility, technical feasibility, regulatory eligibility, patent freedom, or commercial viability. |
| 76 | DEFEROXAMINE MESYLATE | 10 | 23 | D_deprioritise | deprioritise_or_false_positive | ready_to_use_or_reconstitution_reduction | Distinct rescueability score based on status, administration/handling, route, PK, evidence quality, identity taxonomy, and toxicity conflict. Primary hypothesis: ready_to_use_or_reconstitution_reduction. Phase 3.1 oncology language is treated as contextual because active-identity taxonomy does not support a cytotoxic/oncology classification. Severe conflict blocks A-tier assignment. This rule-based rank does not establish clinical utility, technical feasibility, regulatory eligibility, patent freedom, or commercial viability. |
| 9 | OLICERIDINE | 10 | 23 | B_plausible_literature_review | acute_care_or_anaesthesia | acute_care_administration_simplification | Distinct rescueability score based on status, administration/handling, route, PK, evidence quality, identity taxonomy, and toxicity conflict. Primary hypothesis: acute_care_administration_simplification. Severe conflict blocks A-tier assignment. This rule-based rank does not establish clinical utility, technical feasibility, regulatory eligibility, patent freedom, or commercial viability. |
| 10 | PRAMLINTIDE ACETATE | 10 | 23 | B_plausible_literature_review | small_molecule_reformulation | storage_or_stability_improvement | Distinct rescueability score based on status, administration/handling, route, PK, evidence quality, identity taxonomy, and toxicity conflict. Primary hypothesis: storage_or_stability_improvement. Severe conflict blocks A-tier assignment. This rule-based rank does not establish clinical utility, technical feasibility, regulatory eligibility, patent freedom, or commercial viability. |
| 11 | IRON SUCROSE | 10 | 22 | B_plausible_literature_review | small_molecule_reformulation | ready_to_use_or_reconstitution_reduction | Distinct rescueability score based on status, administration/handling, route, PK, evidence quality, identity taxonomy, and toxicity conflict. Primary hypothesis: ready_to_use_or_reconstitution_reduction. Severe conflict blocks A-tier assignment. This rule-based rank does not establish clinical utility, technical feasibility, regulatory eligibility, patent freedom, or commercial viability. |
| 77 | FOSCARNET SODIUM | 9 | 23 | D_deprioritise | anti_infective_specialist | anti_infective_formulation_or_delivery | Distinct rescueability score based on status, administration/handling, route, PK, evidence quality, identity taxonomy, and toxicity conflict. Primary hypothesis: anti_infective_formulation_or_delivery. Phase 3.1 oncology language is treated as contextual because active-identity taxonomy does not support a cytotoxic/oncology classification. Severe conflict blocks A-tier assignment. This rule-based rank does not establish clinical utility, technical feasibility, regulatory eligibility, patent freedom, or commercial viability. |
| 78 | MICAFUNGIN SODIUM | 9 | 23 | D_deprioritise | anti_infective_specialist | anti_infective_formulation_or_delivery | Distinct rescueability score based on status, administration/handling, route, PK, evidence quality, identity taxonomy, and toxicity conflict. Primary hypothesis: anti_infective_formulation_or_delivery. Phase 3.1 oncology language is treated as contextual because active-identity taxonomy does not support a cytotoxic/oncology classification. Severe conflict blocks A-tier assignment. This rule-based rank does not establish clinical utility, technical feasibility, regulatory eligibility, patent freedom, or commercial viability. |
| 12 | VECURONIUM BROMIDE | 9 | 23 | B_plausible_literature_review | acute_care_or_anaesthesia | acute_care_administration_simplification | Distinct rescueability score based on status, administration/handling, route, PK, evidence quality, identity taxonomy, and toxicity conflict. Primary hypothesis: acute_care_administration_simplification. This rule-based rank does not establish clinical utility, technical feasibility, regulatory eligibility, patent freedom, or commercial viability. |
| 79 | AMPHOTERICIN B | 9 | 22 | D_deprioritise | anti_infective_specialist | anti_infective_formulation_or_delivery | Distinct rescueability score based on status, administration/handling, route, PK, evidence quality, identity taxonomy, and toxicity conflict. Primary hypothesis: anti_infective_formulation_or_delivery. Phase 3.1 oncology language is treated as contextual because active-identity taxonomy does not support a cytotoxic/oncology classification. Severe conflict blocks A-tier assignment. This rule-based rank does not establish clinical utility, technical feasibility, regulatory eligibility, patent freedom, or commercial viability. |
| 80 | DAPTOMYCIN | 9 | 22 | D_deprioritise | anti_infective_specialist | anti_infective_formulation_or_delivery | Distinct rescueability score based on status, administration/handling, route, PK, evidence quality, identity taxonomy, and toxicity conflict. Primary hypothesis: anti_infective_formulation_or_delivery. Phase 3.1 oncology language is treated as contextual because active-identity taxonomy does not support a cytotoxic/oncology classification. Severe conflict blocks A-tier assignment. This rule-based rank does not establish clinical utility, technical feasibility, regulatory eligibility, patent freedom, or commercial viability. |

## Top candidates per review queue

### acute_care_or_anaesthesia

| Order | Ingredient | Rescueability | Burden score | Tier | Queue | Primary hypothesis | Notes |
|---:|---|---:|---:|---|---|---|---|
| 9 | OLICERIDINE | 10 | 23 | B_plausible_literature_review | acute_care_or_anaesthesia | acute_care_administration_simplification | Distinct rescueability score based on status, administration/handling, route, PK, evidence quality, identity taxonomy, and toxicity conflict. Primary hypothesis: acute_care_administration_simplification. Severe conflict blocks A-tier assignment. This rule-based rank does not establish clinical utility, technical feasibility, regulatory eligibility, patent freedom, or commercial viability. |
| 12 | VECURONIUM BROMIDE | 9 | 23 | B_plausible_literature_review | acute_care_or_anaesthesia | acute_care_administration_simplification | Distinct rescueability score based on status, administration/handling, route, PK, evidence quality, identity taxonomy, and toxicity conflict. Primary hypothesis: acute_care_administration_simplification. This rule-based rank does not establish clinical utility, technical feasibility, regulatory eligibility, patent freedom, or commercial viability. |
| 84 | METHOHEXITAL SODIUM | 8 | 22 | D_deprioritise | acute_care_or_anaesthesia | acute_care_administration_simplification | Distinct rescueability score based on status, administration/handling, route, PK, evidence quality, identity taxonomy, and toxicity conflict. Primary hypothesis: acute_care_administration_simplification. Severe conflict blocks A-tier assignment. This rule-based rank does not establish clinical utility, technical feasibility, regulatory eligibility, patent freedom, or commercial viability. |
| 85 | ZICONOTIDE ACETATE | 8 | 22 | D_deprioritise | acute_care_or_anaesthesia | acute_care_administration_simplification | Distinct rescueability score based on status, administration/handling, route, PK, evidence quality, identity taxonomy, and toxicity conflict. Primary hypothesis: acute_care_administration_simplification. This rule-based rank does not establish clinical utility, technical feasibility, regulatory eligibility, patent freedom, or commercial viability. |
| 89 | UROKINASE | 3 | 24 | D_deprioritise | acute_care_or_anaesthesia | acute_care_administration_simplification | Distinct rescueability score based on status, administration/handling, route, PK, evidence quality, identity taxonomy, and toxicity conflict. Primary hypothesis: acute_care_administration_simplification. Severe conflict blocks A-tier assignment. This rule-based rank does not establish clinical utility, technical feasibility, regulatory eligibility, patent freedom, or commercial viability. |

### anti_infective_specialist

| Order | Ingredient | Rescueability | Burden score | Tier | Queue | Primary hypothesis | Notes |
|---:|---|---:|---:|---|---|---|---|
| 2 | GANCICLOVIR SODIUM | 12 | 23 | B_plausible_literature_review | anti_infective_specialist | anti_infective_formulation_or_delivery | Distinct rescueability score based on status, administration/handling, route, PK, evidence quality, identity taxonomy, and toxicity conflict. Primary hypothesis: anti_infective_formulation_or_delivery. Phase 3.1 oncology language is treated as contextual because active-identity taxonomy does not support a cytotoxic/oncology classification. This rule-based rank does not establish clinical utility, technical feasibility, regulatory eligibility, patent freedom, or commercial viability. |
| 3 | CEFEPIME HYDROCHLORIDE | 12 | 22 | B_plausible_literature_review | anti_infective_specialist | anti_infective_formulation_or_delivery | Distinct rescueability score based on status, administration/handling, route, PK, evidence quality, identity taxonomy, and toxicity conflict. Primary hypothesis: anti_infective_formulation_or_delivery. Phase 3.1 oncology language is treated as contextual because active-identity taxonomy does not support a cytotoxic/oncology classification. This rule-based rank does not establish clinical utility, technical feasibility, regulatory eligibility, patent freedom, or commercial viability. |
| 4 | CEFTIZOXIME SODIUM | 12 | 22 | B_plausible_literature_review | anti_infective_specialist | anti_infective_formulation_or_delivery | Distinct rescueability score based on status, administration/handling, route, PK, evidence quality, identity taxonomy, and toxicity conflict. Primary hypothesis: anti_infective_formulation_or_delivery. Phase 3.1 oncology language is treated as contextual because active-identity taxonomy does not support a cytotoxic/oncology classification. This rule-based rank does not establish clinical utility, technical feasibility, regulatory eligibility, patent freedom, or commercial viability. |
| 6 | TIGECYCLINE | 11 | 23 | B_plausible_literature_review | anti_infective_specialist | anti_infective_formulation_or_delivery | Distinct rescueability score based on status, administration/handling, route, PK, evidence quality, identity taxonomy, and toxicity conflict. Primary hypothesis: anti_infective_formulation_or_delivery. Severe conflict blocks A-tier assignment. This rule-based rank does not establish clinical utility, technical feasibility, regulatory eligibility, patent freedom, or commercial viability. |
| 7 | CASPOFUNGIN ACETATE | 11 | 22 | B_plausible_literature_review | anti_infective_specialist | anti_infective_formulation_or_delivery | Distinct rescueability score based on status, administration/handling, route, PK, evidence quality, identity taxonomy, and toxicity conflict. Primary hypothesis: anti_infective_formulation_or_delivery. Phase 3.1 oncology language is treated as contextual because active-identity taxonomy does not support a cytotoxic/oncology classification. This rule-based rank does not establish clinical utility, technical feasibility, regulatory eligibility, patent freedom, or commercial viability. |

### biologic_delivery_specialist

| Order | Ingredient | Rescueability | Burden score | Tier | Queue | Primary hypothesis | Notes |
|---:|---|---:|---:|---|---|---|---|
| 16 | AVALGLUCOSIDASE ALFA-NGPT | 7 | 22 | C_specialist_only_review | biologic_delivery_specialist | biologic_delivery_improvement | Distinct rescueability score based on status, administration/handling, route, PK, evidence quality, identity taxonomy, and toxicity conflict. Primary hypothesis: biologic_delivery_improvement. This rule-based rank does not establish clinical utility, technical feasibility, regulatory eligibility, patent freedom, or commercial viability. |
| 17 | CIPAGLUCOSIDASE ALFA-ATGA | 6 | 22 | C_specialist_only_review | biologic_delivery_specialist | biologic_delivery_improvement | Distinct rescueability score based on status, administration/handling, route, PK, evidence quality, identity taxonomy, and toxicity conflict. Primary hypothesis: biologic_delivery_improvement. This rule-based rank does not establish clinical utility, technical feasibility, regulatory eligibility, patent freedom, or commercial viability. |
| 18 | VELAGLUCERASE ALFA | 6 | 22 | C_specialist_only_review | biologic_delivery_specialist | biologic_delivery_improvement | Distinct rescueability score based on status, administration/handling, route, PK, evidence quality, identity taxonomy, and toxicity conflict. Primary hypothesis: biologic_delivery_improvement. Severe conflict blocks A-tier assignment. This rule-based rank does not establish clinical utility, technical feasibility, regulatory eligibility, patent freedom, or commercial viability. |
| 21 | COLLAGENASE CLOSTRIDIUM HISTOLYTICUM | 5 | 22 | C_specialist_only_review | biologic_delivery_specialist | biologic_delivery_improvement | Distinct rescueability score based on status, administration/handling, route, PK, evidence quality, identity taxonomy, and toxicity conflict. Primary hypothesis: biologic_delivery_improvement. Severe conflict blocks A-tier assignment. This rule-based rank does not establish clinical utility, technical feasibility, regulatory eligibility, patent freedom, or commercial viability. |
| 24 | TEDUGLUTIDE | 5 | 22 | C_specialist_only_review | biologic_delivery_specialist | biologic_delivery_improvement | Distinct rescueability score based on status, administration/handling, route, PK, evidence quality, identity taxonomy, and toxicity conflict. Primary hypothesis: biologic_delivery_improvement. Severe conflict blocks A-tier assignment. This rule-based rank does not establish clinical utility, technical feasibility, regulatory eligibility, patent freedom, or commercial viability. |

### deprioritise_or_false_positive

| Order | Ingredient | Rescueability | Burden score | Tier | Queue | Primary hypothesis | Notes |
|---:|---|---:|---:|---|---|---|---|
| 75 | SODIUM SUCCINATE | 12 | 22 | D_deprioritise | deprioritise_or_false_positive | ready_to_use_or_reconstitution_reduction | Distinct rescueability score based on status, administration/handling, route, PK, evidence quality, identity taxonomy, and toxicity conflict. Primary hypothesis: ready_to_use_or_reconstitution_reduction. Phase 3.1 oncology language is treated as contextual because active-identity taxonomy does not support a cytotoxic/oncology classification. This rule-based rank does not establish clinical utility, technical feasibility, regulatory eligibility, patent freedom, or commercial viability. |
| 76 | DEFEROXAMINE MESYLATE | 10 | 23 | D_deprioritise | deprioritise_or_false_positive | ready_to_use_or_reconstitution_reduction | Distinct rescueability score based on status, administration/handling, route, PK, evidence quality, identity taxonomy, and toxicity conflict. Primary hypothesis: ready_to_use_or_reconstitution_reduction. Phase 3.1 oncology language is treated as contextual because active-identity taxonomy does not support a cytotoxic/oncology classification. Severe conflict blocks A-tier assignment. This rule-based rank does not establish clinical utility, technical feasibility, regulatory eligibility, patent freedom, or commercial viability. |
| 90 | TELAVANCIN HYDROCHLORIDE | 0 | 24 | D_deprioritise | deprioritise_or_false_positive | anti_infective_formulation_or_delivery | Distinct rescueability score based on status, administration/handling, route, PK, evidence quality, identity taxonomy, and toxicity conflict. Primary hypothesis: anti_infective_formulation_or_delivery. Family duplicate of TELAVANCIN; independent rationale: none identified. Severe conflict blocks A-tier assignment. This rule-based rank does not establish clinical utility, technical feasibility, regulatory eligibility, patent freedom, or commercial viability. |
| 91 | ECULIZUMAB-AEEB | 0 | 23 | D_deprioritise | deprioritise_or_false_positive | biologic_delivery_improvement | Distinct rescueability score based on status, administration/handling, route, PK, evidence quality, identity taxonomy, and toxicity conflict. Primary hypothesis: biologic_delivery_improvement. Family duplicate of ECULIZUMAB; independent rationale: none identified. Severe conflict blocks A-tier assignment. This rule-based rank does not establish clinical utility, technical feasibility, regulatory eligibility, patent freedom, or commercial viability. |
| 92 | INFLIXIMAB-DYYB | 0 | 23 | D_deprioritise | deprioritise_or_false_positive | biologic_delivery_improvement | Distinct rescueability score based on status, administration/handling, route, PK, evidence quality, identity taxonomy, and toxicity conflict. Primary hypothesis: biologic_delivery_improvement. Phase 3.1 oncology language is treated as contextual because active-identity taxonomy does not support a cytotoxic/oncology classification. Family duplicate of INFLIXIMAB-AXXQ; independent rationale: none identified. Severe conflict blocks A-tier assignment. This rule-based rank does not establish clinical utility, technical feasibility, regulatory eligibility, patent freedom, or commercial viability. |

### immunology_biologic

| Order | Ingredient | Rescueability | Burden score | Tier | Queue | Primary hypothesis | Notes |
|---:|---|---:|---:|---|---|---|---|
| 13 | AZATHIOPRINE SODIUM | 10 | 23 | C_specialist_only_review | immunology_biologic | ready_to_use_or_reconstitution_reduction | Distinct rescueability score based on status, administration/handling, route, PK, evidence quality, identity taxonomy, and toxicity conflict. Primary hypothesis: ready_to_use_or_reconstitution_reduction. Phase 3.1 oncology language is treated as contextual because active-identity taxonomy does not support a cytotoxic/oncology classification. This rule-based rank does not establish clinical utility, technical feasibility, regulatory eligibility, patent freedom, or commercial viability. |
| 22 | DONANEMAB-AZBT | 5 | 22 | C_specialist_only_review | immunology_biologic | biologic_delivery_improvement | Distinct rescueability score based on status, administration/handling, route, PK, evidence quality, identity taxonomy, and toxicity conflict. Primary hypothesis: biologic_delivery_improvement. Severe conflict blocks A-tier assignment. This rule-based rank does not establish clinical utility, technical feasibility, regulatory eligibility, patent freedom, or commercial viability. |
| 25 | GLATIRAMER ACETATE | 4 | 23 | C_specialist_only_review | immunology_biologic | ready_to_use_or_reconstitution_reduction | Distinct rescueability score based on status, administration/handling, route, PK, evidence quality, identity taxonomy, and toxicity conflict. Primary hypothesis: ready_to_use_or_reconstitution_reduction. Severe conflict blocks A-tier assignment. This rule-based rank does not establish clinical utility, technical feasibility, regulatory eligibility, patent freedom, or commercial viability. |
| 29 | LECANEMAB-IRMB | 4 | 22 | C_specialist_only_review | immunology_biologic | biologic_delivery_improvement | Distinct rescueability score based on status, administration/handling, route, PK, evidence quality, identity taxonomy, and toxicity conflict. Primary hypothesis: biologic_delivery_improvement. Severe conflict blocks A-tier assignment. This rule-based rank does not establish clinical utility, technical feasibility, regulatory eligibility, patent freedom, or commercial viability. |
| 32 | BELATACEPT | 3 | 23 | C_specialist_only_review | immunology_biologic | biologic_delivery_improvement | Distinct rescueability score based on status, administration/handling, route, PK, evidence quality, identity taxonomy, and toxicity conflict. Primary hypothesis: biologic_delivery_improvement. Phase 3.1 oncology language is treated as contextual because active-identity taxonomy does not support a cytotoxic/oncology classification. Severe conflict blocks A-tier assignment. This rule-based rank does not establish clinical utility, technical feasibility, regulatory eligibility, patent freedom, or commercial viability. |

### oncology_specialist

| Order | Ingredient | Rescueability | Burden score | Tier | Queue | Primary hypothesis | Notes |
|---:|---|---:|---:|---|---|---|---|
| 14 | BLEOMYCIN SULFATE | 10 | 23 | C_specialist_only_review | oncology_specialist | specialist_oncology_formulation | Distinct rescueability score based on status, administration/handling, route, PK, evidence quality, identity taxonomy, and toxicity conflict. Primary hypothesis: specialist_oncology_formulation. This rule-based rank does not establish clinical utility, technical feasibility, regulatory eligibility, patent freedom, or commercial viability. |
| 15 | IXABEPILONE | 9 | 22 | C_specialist_only_review | oncology_specialist | specialist_oncology_formulation | Distinct rescueability score based on status, administration/handling, route, PK, evidence quality, identity taxonomy, and toxicity conflict. Primary hypothesis: specialist_oncology_formulation. This rule-based rank does not establish clinical utility, technical feasibility, regulatory eligibility, patent freedom, or commercial viability. |
| 19 | CYTARABINE | 5 | 23 | C_specialist_only_review | oncology_specialist | specialist_oncology_formulation | Distinct rescueability score based on status, administration/handling, route, PK, evidence quality, identity taxonomy, and toxicity conflict. Primary hypothesis: specialist_oncology_formulation. Severe conflict blocks A-tier assignment. This rule-based rank does not establish clinical utility, technical feasibility, regulatory eligibility, patent freedom, or commercial viability. |
| 20 | BORTEZOMIB | 5 | 22 | C_specialist_only_review | oncology_specialist | specialist_oncology_formulation | Distinct rescueability score based on status, administration/handling, route, PK, evidence quality, identity taxonomy, and toxicity conflict. Primary hypothesis: specialist_oncology_formulation. Severe conflict blocks A-tier assignment. This rule-based rank does not establish clinical utility, technical feasibility, regulatory eligibility, patent freedom, or commercial viability. |
| 23 | MELPHALAN HYDROCHLORIDE | 5 | 22 | C_specialist_only_review | oncology_specialist | specialist_oncology_formulation | Distinct rescueability score based on status, administration/handling, route, PK, evidence quality, identity taxonomy, and toxicity conflict. Primary hypothesis: specialist_oncology_formulation. This rule-based rank does not establish clinical utility, technical feasibility, regulatory eligibility, patent freedom, or commercial viability. |

### small_molecule_reformulation

| Order | Ingredient | Rescueability | Burden score | Tier | Queue | Primary hypothesis | Notes |
|---:|---|---:|---:|---|---|---|---|
| 1 | DESMOPRESSIN ACETATE | 14 | 22 | B_plausible_literature_review | small_molecule_reformulation | ready_to_use_or_reconstitution_reduction | Distinct rescueability score based on status, administration/handling, route, PK, evidence quality, identity taxonomy, and toxicity conflict. Primary hypothesis: ready_to_use_or_reconstitution_reduction. This rule-based rank does not establish clinical utility, technical feasibility, regulatory eligibility, patent freedom, or commercial viability. |
| 5 | FERRIC PYROPHOSPHATE CITRATE | 12 | 22 | B_plausible_literature_review | small_molecule_reformulation | ready_to_use_or_reconstitution_reduction | Distinct rescueability score based on status, administration/handling, route, PK, evidence quality, identity taxonomy, and toxicity conflict. Primary hypothesis: ready_to_use_or_reconstitution_reduction. This rule-based rank does not establish clinical utility, technical feasibility, regulatory eligibility, patent freedom, or commercial viability. |
| 8 | HISTRELIN ACETATE | 11 | 22 | B_plausible_literature_review | small_molecule_reformulation | ready_to_use_or_reconstitution_reduction | Distinct rescueability score based on status, administration/handling, route, PK, evidence quality, identity taxonomy, and toxicity conflict. Primary hypothesis: ready_to_use_or_reconstitution_reduction. This rule-based rank does not establish clinical utility, technical feasibility, regulatory eligibility, patent freedom, or commercial viability. |
| 10 | PRAMLINTIDE ACETATE | 10 | 23 | B_plausible_literature_review | small_molecule_reformulation | storage_or_stability_improvement | Distinct rescueability score based on status, administration/handling, route, PK, evidence quality, identity taxonomy, and toxicity conflict. Primary hypothesis: storage_or_stability_improvement. Severe conflict blocks A-tier assignment. This rule-based rank does not establish clinical utility, technical feasibility, regulatory eligibility, patent freedom, or commercial viability. |
| 11 | IRON SUCROSE | 10 | 22 | B_plausible_literature_review | small_molecule_reformulation | ready_to_use_or_reconstitution_reduction | Distinct rescueability score based on status, administration/handling, route, PK, evidence quality, identity taxonomy, and toxicity conflict. Primary hypothesis: ready_to_use_or_reconstitution_reduction. Severe conflict blocks A-tier assignment. This rule-based rank does not establish clinical utility, technical feasibility, regulatory eligibility, patent freedom, or commercial viability. |

## Likely false positives

| Ingredient | Prior signal | Corrected reason |
|---|---|---|
| SODIUM SUCCINATE | oncology_cytotoxic / cytotoxic | prior oncology/cytotoxic label classification appears contextual rather than active-identity based |
| DEFEROXAMINE MESYLATE | oncology_cytotoxic / cytotoxic | prior oncology/cytotoxic label classification appears contextual rather than active-identity based |
| TELAVANCIN HYDROCHLORIDE | organ_toxicity / renal failure | non-representative family duplicate without distinct formulation rationale |
| ECULIZUMAB-AEEB | organ_toxicity / renal failure | non-representative family duplicate without distinct formulation rationale |
| INFLIXIMAB-DYYB | oncology_cytotoxic / neutropenia | non-representative family duplicate without distinct formulation rationale |
| TRASTUZUMAB-DKST | oncology_cytotoxic / cytotoxic | non-representative family duplicate without distinct formulation rationale |
| TRASTUZUMAB-QYYP | oncology_cytotoxic / cytotoxic | non-representative family duplicate without distinct formulation rationale |
| TRASTUZUMAB-STRF | oncology_cytotoxic / cytotoxic | non-representative family duplicate without distinct formulation rationale |
| RITUXIMAB-ABBS | oncology_cytotoxic / cytotoxic | non-representative family duplicate without distinct formulation rationale |
| RITUXIMAB-ARRX | oncology_cytotoxic / cytotoxic | non-representative family duplicate without distinct formulation rationale |
| RITUXIMAB-PVVR | oncology_cytotoxic / cytotoxic | non-representative family duplicate without distinct formulation rationale |
| TOCILIZUMAB-AAZG | oncology_cytotoxic / chemotherapy | non-representative family duplicate without distinct formulation rationale |
| ZIPRASIDONE MESYLATE | oncology_cytotoxic / neutropenia | prior oncology/cytotoxic label classification appears contextual rather than active-identity based |

## Duplicate family clusters and representatives

| Family | Members | Representative | Selection reason |
|---|---|---|---|
| ECULIZUMAB | ECULIZUMAB; ECULIZUMAB-AEEB | ECULIZUMAB | unsuffixed/reference core ingredient preferred |
| INFLIXIMAB | INFLIXIMAB-AXXQ; INFLIXIMAB-DYYB | INFLIXIMAB-AXXQ | highest rescueability score; ties resolved by formulation burden, administration burden, scientific signal score, then ingredient name |
| RITUXIMAB | RITUXIMAB-ABBS; RITUXIMAB-ARRX; RITUXIMAB-PVVR; RITUXIMAB | RITUXIMAB | unsuffixed/reference core ingredient preferred |
| TELAVANCIN | TELAVANCIN HYDROCHLORIDE; TELAVANCIN | TELAVANCIN | unsuffixed/reference core ingredient preferred |
| TOCILIZUMAB | TOCILIZUMAB; TOCILIZUMAB-AAZG | TOCILIZUMAB | unsuffixed/reference core ingredient preferred |
| TRASTUZUMAB | TRASTUZUMAB; TRASTUZUMAB-DKST; TRASTUZUMAB-QYYP; TRASTUZUMAB-STRF; PERTUZUMAB, TRASTUZUMAB, AND HYALURONIDASE-ZZXF; TRASTUZUMAB AND HYALURONIDASE-OYSK | TRASTUZUMAB | unsuffixed/reference core ingredient preferred |

## Limitations

- Taxonomy is a transparent curated screening list, not a complete pharmacologic ontology.
- Scores encode review heuristics and deliberately avoid probability or feasibility claims.
- Current product records cannot establish whether an apparent gap has already been solved by a marketed alternative.
- DailyMed matches and keyword burdens may be presentation-specific or context-only.
- Discontinuation cause, shortage, clinical relevance, PK/PD causality, comparator landscape, formulation feasibility, patent/FTO, and regulatory pathway remain unvalidated.

## Recommended next manual review workflow

1. Review A-tier representatives for a concrete burden-to-formulation-fix link and current comparator landscape.
2. Review B-tier representatives with targeted literature, label, PK/PD, discontinuation, and formulation-feasibility questions.
3. Route C-tier representatives to the queue-specific subject-matter expert before general prioritisation.
4. Review independent duplicate rationales; otherwise use the selected family representative.
5. Confirm E-tier identity/context corrections manually before rejecting any candidate.
