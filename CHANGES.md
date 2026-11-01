# Deployment packaging (local launcher + Render)

**No change to the interface, engine, policies, models or behaviour.** Added `run_local.bat`/`run_local.sh`, `Dockerfile`, `docker-entrypoint.sh`, `.dockerignore`, `render.yaml`, `DEPLOYMENT.md`, `requirements-dev.txt` (runtime `requirements.txt` no longer lists pytest/playwright), `.gitignore`, `.gitattributes`, `tools/backup_data.py`, `tests/deploy/` (21 tests), updated `.env.example`.
Two small code edits: `app/config.py` (empty env var = unset; opt-in `LOAN_APP_REQUIRE_ENV_PASSWORDS`) and `app/streamlit_app.py` / `app/bootstrap.py` (clear message instead of silently creating accounts with unknown or weak passwords when that flag is on).
Defects found by verifying the deployment (all fixed): (1) the container entrypoint left `HOME=/root` after dropping privileges, which would have crash-looped Streamlit on Render; (2) the first-run account creation would have produced unknown random passwords on a public host; (3) `.env.example` placeholder passwords satisfied the strength rules and so could become public credentials if copied unchanged; (4) an empty `LOAN_APP_DATA_DIR` would have resolved to the project root.

---

# Phase 3: Bank-Officer Application (summary of changes)

**Added only; no Phase 1/2 file was modified** (core/, ml/, config/, models/, data/, all 8 original test files, conftest, run_demo, sample outputs and docs are byte-identical to the Phase 1+2 ZIP). New: `app/` (Streamlit app + services), `tests/app/` (193 tests), `tools/make_sample_documents.py`, `data/sample_documents/` (fictional), `.streamlit/config.toml`, `docs/ARCHITECTURE.md`, `docs/USER_GUIDE.md`, `docs/SECURITY_AND_PRIVACY.md`, `docs/PHASE3_IMPLEMENTATION_AND_TESTING_REPORT.md`, `docs/screenshots/`, updated `requirements.txt`, `packages.txt`, `.env.example`, README.

## Defects found by the new tests/browser runs and fixed (all within Phase 3 code)
1. **Account lockout never engaged and failed logins were not audited**: the error was raised inside a transaction, rolling back the counter and the audit row.
2. Password rule accepted all-uppercase passwords.
3. Salary-history parser split `1,00,000` into three numbers and could merge `1,00,000, 90,000`; ambiguous input is now refused.
4. Stale UI state: document list after upload; newly run assessment not shown; report scenario selection kept across assessments.
5. Demo loading skipped everything for a second officer (PAN duplicate check); admin had a demo button that could only error.
6. PDF omitted the risk model's own disclaimer.
7. Truncated metrics, clipped tables, mixed-type table columns (pyarrow warning).
No engine defect was found, so no engine change was made.

---

# Phase 2 + Synthetic Policy Environments: Summary of Changes

**Result: 308 tests pass** (192 Phase 1 preserved + 32 environment tests + 27 dataset + 26 model + 31 risk-integration). No Phase 1 policy value was changed.

## A. Part 1: strictly separated policy environments
- New `core/policy_env.py`: `evidence_backed`, `synthetic_demo`, `test_fixture`. `assess()` now **requires** an explicit environment (via a tagged `PolicySet` or `environment=`); there is no default and mixing raises an error.
- New `config/synthetic_demo_policies.json`, generated from the evidence config by `tools/make_synthetic_policy.py` (so numbers cannot drift; a test asserts equality): SBI Xpress Credit, every criterion a `synthetic_assumption` with a stated basis and no source. Persistent banner and "SIMULATED ... (not an SBI decision)" wording.
- Policy loader enforces which criterion kinds each environment file may hold; synthetic assumptions can never be reconfirmed into evidence and are never "current".
- **Test fixture isolation**: the synthetic reconfirmation moved from `data/demo_reconfirmation.py` (shipped) to `tests/fixtures.py`; `--demo-reconfirmed` was removed from `run_demo.py`; `test_fixture` loads only after `tests/conftest.py` enables test mode (tested to refuse otherwise; only conftest may enable it).
- Environment recorded in every assessment, disclaimer and rendered report. Affordability is identical across environments (tested on all six samples).
- Evidence-backed behaviour is unchanged: stale or unresolved policy gives "Insufficient information – policy verification required" and never an automatic failure.

## B. Part 2: dataset
10,000 fictional applicants, seed 20261101, 48 columns, 9.33% defaults; derived ratios computed from primitives; 40+ consistency checks; reproducible byte-for-byte (SHA-256 recorded and tested).

## C. Parts 3-4: models and risk prediction
Logistic Regression and Gradient Boosting pipelines, validation-based tuning/calibration/selection, bootstrap intervals, plots, evaluation report; applicant-level risk output with bands, explanations (LR exact, GB SHAP), missing-data and new-to-credit handling, integration into `assess(..., risk_model=...)`; bank-specific calibration hook; data contract and real-data guide.

## D. Bugs and weaknesses found along the way (all fixed or disclosed)
1. **Generator**: a "previous default" flag could be set with under 90 days past due (89 rows), caught by the new consistency checker.
2. **My noise-ceiling measurement was wrong at first**: I measured AUC against the *realised* latent probability (which includes noise a model can't see), so more noise looked like a *higher* ceiling. Fixed by integrating the unobserved noise out (Bayes probability given observable features). The first draft's true ceiling was ~0.94 (unrealistically clean); noise settings were then chosen from the generator's own ceiling (~0.83), never from model scores.
3. **CSV precision**: 10 significant digits broke strict derived-value checks after a round-trip; now 12 digits with tolerances tied to file precision.
4. **Redundant feature `dscr_post`**: an exact function of three other inputs; it had a counter-intuitive positive coefficient. Removed and the pipeline retrained. **Disclosure:** I had already seen the first run's test metrics (LR 0.8258 / GB 0.8260 AUC, kept in `models/synthetic_generic/revision_history/`), so this revision was not blind to the test set, although it was driven by training coefficients and algebra and the selection rule was untouched.
5. **Feature-name grouping bug**: `credit_score_available` was attributed to `credit_score` (prefix match). Fixed (exact, then longest prefix); it affected importance tables and local explanations.
6. **Explanations**: a flag and the median-imputed value it governs appeared as separate (offsetting) "drivers" (e.g. "no credit card"). They are now grouped; imputed inputs are never listed as drivers; a materiality floor hides near-zero contributions.
7. **Imputation reporting**: not every imputed feature was listed (e.g. credit profile not entered). Now every feature that passes through the imputer is listed, split into structurally absent vs genuinely missing.
8. `variable_income_share` was drawn separately from the rounded rupee amount; it is now computed from it.
9. Three vacuous test assertions (`... or True`) from my own drafts were found and replaced with real ones; scanned for others.

## E. Findings you should know
- **The two models are statistically tied.** Gradient boosting's point estimate is slightly higher but the interval includes zero; the deployed choice (logistic regression) follows a validation rule fixed in advance. I did not switch after seeing test numbers.
- **Individual disagreement:** for a verified-default applicant (DEMO-004) LR says ~16% and GB ~25%. The output flags disagreements above 5 points as uncertain.
- **Calibration:** validation chose *no* recalibration for either model; probabilities track outcomes closely **on synthetic data only**, which says nothing about real borrowers.
- **Accuracy is uninformative** here (about 0.92 vs 0.91 for "predict nobody defaults"); selection used log-loss.
- Probabilities and bands are demonstration values; no fairness analysis was done.

## F. Not done
Phase 3 interface, PDF report generation (reports are text outputs), any real data or external integration, fairness analysis, model-risk governance.

---

# Phase 1 FINAL Policy Refinements: Summary of Changes

Three decisions implemented on top of the corrected Phase 1 engine (architecture unchanged; all 133 earlier tests preserved).
**Result: 192 tests pass** (133 earlier tests, one rewritten, plus 59 new).

## A. Decision 1 - SBI EMI/NMI (FOIR) convention
| Requirement | Implementation |
|---|---|
| Keep 60% as the SBI screening threshold | `max_foir_pct = 60` unchanged, still `confirmed / mandatory`, passage `'EMI/NMI Ratio upto 60%'` |
| Post-loan FOIR = (existing + proposed EMI) / net income x 100 | `eligibility._foir_value`; also used by `ratios.emi_capacity` so structuring and eligibility agree |
| Explicit policy note: prototype interpretation, not an official formula | New criterion fields `calculation_convention` and `interpretation` (`is_official_definition: false`); note says "not an officially defined SBI formula; not independently verified as an SBI underwriting rule". The validator rejects a FOIR criterion that does not declare this. |
| Configurable convention | `existing_plus_proposed` (default) or `proposed_only`, per criterion in the policy file (default also in `settings.json`); unknown values are rejected |
| Never described as verified | Remarks, report and output wording say "PROTOTYPE INTERPRETATION" everywhere; a test asserts no "verified" claim in guidance |
| Show percentage and formula in the dashboard | `assess()["foir_display"]` = formula, working (`FOIR = (0 + 15,653) / 120,000 x 100 = 13.04%`), threshold, within/above, official-vs-interpretation notes; `run_demo.py` prints it |
| Tests | below 60%, exactly 60% (passes, tolerance 1e-9), above 60%, existing EMIs with no proposed loan, missing / zero net income (missing data, never a fail), convention switch, validator, display, other banks have no FOIR |

## B. Decision 2 - Stale policy handling
- **Rule:** a confirmed criterion is current only if its effective date is within `policy_freshness_days` (365, configurable) of the evaluation date. Effective date = latest of a *valid administrator reconfirmation*, the source page's last-updated date, or (undated sources) our read date.
- **Bank-level result:** `"Insufficient information – policy verification required"`. It can never be "Meets published criteria" while any decisive criterion is stale.
- **Stale is not a fail:** a stale criterion yields `policy_stale` with "would PASS / would FAIL against the outdated value (informational only)". Only current criteria can produce a pass or a fail.
- **Separate reasons** (`BankResult.reasons`): `applicant_information_missing`, `policy_outdated`, `policy_unresolved`, `policy_undisclosed` (the last does not block a status). Shown separately in the output and in `guidance`.
- **Metadata per criterion:** source last updated, last verified, administrator reconfirmation date, verification status (`current` / `stale` / `reconfirmed_current` / `not_applicable`), next review date.
- **Reconfirmation needs evidence, not a date:** `reconfirmed_on`, `reconfirmed_by` (must be an authorised administrator), `evidence_type`, `evidence_reference`, `evidence_summary` (>= 20 chars), and `confirmed_value` equal to the current criterion value. Rejected records are listed in the remarks with the reason. Changing `last_verified` or any date alone does nothing. Reconfirmation expires after 365 days. Unresolved / third-party / undisclosed criteria cannot be reconfirmed. Changing a value discards its reconfirmation.
- **Admin function:** `reconfirm_criterion()` validates, writes, and appends to `config/policy_audit_log.jsonl`.
- **Stale limits still constrain structuring:** an outdated limit never loosens a limit used to build alternative loans.
- **No reconfirmation is recorded in the shipped config.** My own reading of the pages is not an administrator reconfirmation.

## C. Decision 3 - Retirement / contract end
- **New employment fields:** `employment_type` (Permanent / Contractual), `expected_retirement_date`, `expected_contract_end_date`, `retirement_age` (only if the exact date is unavailable), `employment_verification_status` (verified / unverified). Date of birth already existed.
- **Calculation (`core/maturity.py`):** maturity date = evaluation date + tenure (disbursal date unknown); limit = earliest of age 60, retirement date (Permanent; exact date takes precedence over age) or contract end (Contractual). Age at maturity is reported. Maturity exactly on the limit **passes**.
- **Missing information is never a rejection:** Permanent with no retirement date/age, Contractual with no contract end date, an unrecognised employment type, or a date already in the past all give *applicant information missing* (insufficient information). Only the relevant date is required, never both.
- **Unverified information is labelled:** the criterion explanation and a remark state "UNVERIFIED, manually entered".
- **Conditional required field:** `validation.conditional_requirements(profile, policy)` returns exactly which field the registration form must show (Permanent -> retirement date or age; Contractual -> contract end date), and `completeness()` counts it for SBI only. **There is still no UI** (Phase 3); this is the machine-readable rule it will render.
- **Validation:** warns on a retirement date for a contractual employee, past dates, dates before birth, both dates entered, odd retirement ages.

## D. Tests
- All 133 earlier tests preserved. **One rewritten:** `test_sbi_needs_retirement_age_and_flags_stale_page` asserted that a stale SBI page only produced a warning (the behaviour you asked me to change). It is now `test_sbi_needs_retirement_age_and_does_not_auto_reject`; staleness is covered by the new file.
- **`tests/conftest.py` (important):** the earlier tests exercise SBI's confirmed rules, but the shipped SBI config is now outdated, so those tests would otherwise all report "insufficient". `conftest.py` wraps the default `load_policies()` to add an in-memory, clearly synthetic administrator reconfirmation for SBI. New stale/production tests call `load_policies(reconfirmations={})`, i.e. the shipped config unchanged. Nothing synthetic is written to the config file.
- 59 new tests (counted): FOIR 10; maturity / retirement / contract-end 16; stale-policy, reconfirmation, conflicting sources, four-reason reporting, preserved SBI values, no cross-product mixing, experimental status and sample outcomes 33 (several are parametrised).

## E. Sample outcomes changed by these refinements
Eligibility status for SBI changed; **affordability outcomes (A, C, B, A, I, A) and adverse-credit levels are identical to before for all six applicants.**

| Applicant | Previous SBI status | New status (shipped config) | If SBI were administrator-reconfirmed (demo only) |
|---|---|---|---|
| DEMO-001 strong | Meets published criteria | Insufficient information – policy verification required | Meets published criteria |
| DEMO-002 high_debt | Does not meet published criteria | Insufficient information – policy verification required | Does not meet published criteria |
| DEMO-003 low_income | Does not meet published criteria | Insufficient information – policy verification required | Does not meet published criteria |
| DEMO-004 poor_history | Meets published criteria | Insufficient information – policy verification required | Meets published criteria |
| DEMO-005 missing_info | Insufficient information | Insufficient information – policy verification required | Insufficient information |
| DEMO-006 new_to_credit | Insufficient information | Insufficient information – policy verification required | Insufficient information |

- **Why every shipped result is now "policy verification required":** SBI's official page was last updated 2025-02-28 (611 days before today) and has not been reconfirmed by an administrator. Nothing can pass or fail until one records evidence.
- **Sample data changes needed for Decision 3:** DEMO-004 is a contractual employee, so it now has an (unverified) contract end date five years out; DEMO-001 is marked employment-verified; the other Permanent samples keep retirement age 60. Without this DEMO-004 would be "insufficient", which was not the point of that sample.
- Outputs: `sample_assessments/primary_sbi/` (shipped config), `primary_sbi_DEMO_if_reconfirmed/` (**synthetic** reconfirmation, demonstration only), plus experimental HDFC and ICICI runs.

## F. Bugs found while doing this (fixed)
1. My eligibility rewrite dropped the branch that routes "may qualify via an unpublished list" employers into *unresolved* (they fell into *missing data*).
2. Maturity tests initially used a reconfirmation dated after the pinned evaluation date (correctly rejected as "in the future"); the tests, not the engine, were wrong.
3. Cosmetic: the maturity line printed "limit None (None)" when the date was unknown.

## G. Decisions and limits to be aware of
- **Evaluation date** for freshness is the profile's `as_of` (default: today). The check is date-sensitive by design: an unrefreshed policy goes stale on schedule.
- **Undated sources** (HDFC legacy page, ICICI page) are counted from our read date, so they are "current" until 2027-11-01. This is a weaker guarantee than a dated source; those criteria are mostly unresolved anyway.
- **File-based admin controls are not tamper-proof.** Phase 3 must enforce authenticated administrators and an immutable audit log.
- HDFC and ICICI remain experimental; SBI's other schemes are still deliberately not mixed in. SBI values (Rs 30 lakh, 24x NMI, 60%, 84 months) are unchanged and asserted by a test.
- No Phase 2 / machine-learning work has been started.

---

# Earlier change log (previous round)

## Phase 1 Correction & Freeze: Summary of Every Change

## A. Product-level corrections (your sections 1-5)

| # | Requirement | What changed | Where |
|---|---|---|---|
| 1 | Bank-specific architecture | `assess(profile, selected_policy)` now **requires** an explicit bank/product. No default argument; `None`, `""` and unknown ids raise `ValueError`. `build_scenarios` also requires it. SBI Xpress Credit (salaried, SBI salary account) is the single modelled SBI product and is flagged `primary_proof_of_concept`; HDFC and ICICI are `experimental_comparison`. | `core/assess.py`, `core/scenarios.py`, `core/policy.py::get_policy` |
| 1 | One bank used consistently | FOIR limit, amount limits (incl. SBI 24x NMI), min/max tenure, rate assumption, scenarios and recommendation context all come from the selected policy only. | `core/scenarios.py::resolve_limits/resolve_rate` |
| 1 | No cross-bank mixing | Previously every bank was evaluated using the *selected* bank's EMI. Now each bank in the comparison uses **its own** rate assumption; a bank's comparison result is identical whichever bank is selected (tested). Scenario eligibility refers to the selected bank only. | `core/assess.py` |
| 2 | Policy re-verification | Official pages were read in full where the fetch tool allowed (SBI product + rate page, HDFC legacy AMP page, ICICI eligibility page). Every criterion now records bank/product/segment, value+unit, URL, supporting passage, verification date, nature (mandatory/indicative/preference/unavailable), applies-at (application/maturity). | `config/bank_policies.json` (schema v2), `docs/POLICY_VERIFICATION_REPORT.md` |
| 2 | Conflicts are unresolved, not voted | HDFC max age (60 vs 55), HDFC income/experience (legacy page only), ICICI min age (18/20/23), ICICI max age (58/65), ICICI tenure are `unresolved` with the candidate list; value is `null`. | config + `core/eligibility.py` |
| 2 | No definitive pass from unresolved / third-party criteria | Unresolved criteria can never yield "Meets published criteria"; third-party-only and "preferred" criteria are advisory and never decide status. Validator rejects confirmed entries without URL and passage, and unavailable/unresolved entries that carry values. | `core/policy.py::validate_policy_dict` |
| 2 | Assumptions separate from policy | New `rate_assumption` block per bank (SBI: stale 2024 range, labelled prototype assumption); tenure caps outside confirmed policy are reported as `prototype_assumption`. | config, `core/scenarios.py` |
| 3 | Affordability vs eligibility vs credit history | `assess()` returns three separate results plus one `guidance` string. Outcomes A/B/C/I are affordability only. New `eligibility_selected` and `adverse_credit` (none/moderate/serious). The old "proceed to formal verification" wording was removed from the affordability outcome. | `core/assess.py`, new `core/credit_flags.py`, `core/recommendations.py` |
| 3 | Adverse history cannot yield an unqualified proceed | Verified or unverified default, settlement or 90+ DPD -> `serious` -> guidance begins "ADDITIONAL UNDERWRITING REVIEW REQUIRED". | `core/credit_flags.py`, `_guidance()` |
| 4 | Missing information downstream | Scenarios get status `Indicative – verification required`; `best_feasible=None`, `feasible=None`; message starts "INDICATIVE ONLY". No scenario shows "Affordable"/"OK". | `core/scenarios.py` |
| 5 | Scenario integrity | Alternatives must respect the selected bank's confirmed amount/tenure/FOIR/maturity-age limits; `best_feasible` requires affordable + structure-compliant + sufficient data; third-party tenures are never treated as limits; every rate is labelled an assumption (lower-rate scenarios "illustrative"); scenarios cannot claim bank eligibility unless status is "Meets". | `core/scenarios.py` |

## B. Bugs found while doing this (all fixed, all covered by tests)
1. `recommendations.py` still read `ss.max_tenure` after the scenario refactor (AttributeError on 30+ paths).
2. A "same amount" alternative could exceed SBI's 24x NMI cap (e.g. INR 8 lakh offered where the cap was INR 7.2 lakh).
3. The base rate in a scenario had no assumption label when the manager supplied it.
4. HDFC's inclusion list was treated as an exclusion list (an educational-institution employee was a hard "fail").
5. My own regex edit deleted a `@pytest.mark.parametrize` decorator; restored.

## C. Tests
- **All 74 original test functions are preserved by name.** Six were rewritten because the behaviour they asserted was intentionally changed:
  `test_policy_file_valid_and_honest`, `test_policy_validator_rejects_fabrication` (schema v2), `test_mixed_bank_outcomes` (HDFC can no longer "Meet"; SBI vs ICICI used instead),
  `test_maturity_age_basis` (ICICI max age is now unresolved; tested on SBI), `test_outcome_a_strong` (the "formal verification" wording was removed), `test_adverse_history_cannot_hide_behind_affordability` (adverse credit is now a separate output).
- **59 new tests** in `tests/test_phase1_corrections.py` cover: explicit selection, bank switching, bank-specific outcomes, conflicting criteria, missing-info scenario status, verified default + 120 DPD, unsupported tenure assumptions, scenario labelling, and affordability/eligibility separation.
- Result: **133 passed**.

## D. Decisions you may want to overrule
- **SBI's "EMI/NMI up to 60%"** is treated as (existing + proposed EMI) / net income; SBI does not define it. SBI's "monthly income" is treated as net.
- **SBI's source page is >12 months old** (28-02-2025). A pass is still "confirmed" but carries a staleness remark. Say if you want staleness to downgrade it to "Insufficient information".
- **SBI requires the retirement/end-of-contract age** (loan must close before it). If it is not entered, SBI eligibility is "Insufficient information".
- **Employer category** is a coarse mapping; "educational institution of national repute" and "selected corporates" cannot be verified from published information, so they are unresolved for SBI.

## E. Not done / still limited
- HDFC's current product page and both ICICI/HDFC rate pages were not readable here; HDFC and ICICI remain low-to-medium confidence and can never reach "Meets published criteria" until their unresolved criteria are confirmed by an administrator.
- No live SBI rate: the 12.65% default is a labelled placeholder anchored to a 2024 range.
- Phase 2 (ML) has not been started, as instructed.
