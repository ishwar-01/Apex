# AI Loan Intelligence: Phase 1 + 2 engine and Phase 3 bank-officer application

A bank-facing **loan assessment engine** (salaried, unsecured personal loans, India, INR). It produces **four separate results** that never override one another:

1. **Financial affordability** (outcome A / B / C / I, EMI capacity, alternative loan structures)
2. **Bank-policy eligibility** for one explicitly selected bank/product, within one explicitly selected *policy environment*
3. **Adverse credit-history warning**
4. **Machine-learning credit risk** (Phase 2): a probability of 90+ days past due within 12 months, from a model trained on **synthetic** data

There is no user interface yet (Phase 3 has not been started). Everything runs from Python and the command line.

> **Read this first.** SBI's *current official* lending criteria are **not verified** in this project. The `evidence_backed` environment refuses to give a pass because its SBI source is outdated and has no administrator reconfirmation. The `synthetic_demo` environment uses clearly labelled **demonstration assumptions**. The risk model is trained on **fictional** borrowers and is **not** an SBI default probability.

## Quick start
```bash
pip install -r requirements.txt
python -m pytest -q                                   # 308 tests (192 Phase 1 + 116 Phase 2)

# Rebuild everything from scratch (all steps are deterministic and seeded):
python -m ml.generate                                 # 10,000 synthetic applicants -> data/synthetic/ (+ metadata, SHA-256)
python -m ml.train                                    # trains Logistic Regression + Gradient Boosting -> models/synthetic_generic/
python -m ml.report                                   # plots + docs/MODEL_EVALUATION_REPORT.md (generated from metrics.json)
python -m ml.make_docs                                # dataset documentation, limitations report, data contract

# Run assessments. The bank AND the policy environment are mandatory: there are no defaults.
python run_demo.py sbi --env synthetic_demo           # simulation mode (the demonstration environment)
python run_demo.py sbi --env evidence_backed          # evidence-only: SBI is outdated -> 'policy verification required'
python run_demo.py sbi --env synthetic_demo --outdir out/     # write one report per applicant
python run_demo.py sbi --env synthetic_demo --no-risk         # skip the ML risk section
```
From Python:
```python
from core import policy_env
from core.assess import assess
from ml.predict import load_risk_model
from data import sample_applicants as S
policies = policy_env.load_environment("synthetic_demo")          # explicit; there is no default environment
result = assess(S.strong(), "sbi", policies=policies, risk_model=load_risk_model())
print(result["environment_banner"], result["guidance_with_risk"], result["credit_risk"]["probability_pct"])
```

## Three strictly separated policy environments
| Environment | Source | What it may produce | Banner |
|---|---|---|---|
| `evidence_backed` | `config/bank_policies.json`: documented official criteria only | Real passes/fails only for **current**, administrator-reconfirmed criteria. Stale or unresolved policy gives *"Insufficient information – policy verification required"*; never an automatic failure | none |
| `synthetic_demo` | `config/synthetic_demo_policies.json`: SBI Xpress Credit **demonstration assumptions** (Phase 1 configured values: Rs 1 lakh minimum, Rs 30 lakh maximum, 24x NMI, 60% EMI/NMI, 84 months, maturity by age 60 / retirement / contract end) | Simulated results worded *"Meets SIMULATED demonstration criteria (not an SBI decision)"* | **SIMULATION MODE – SBI POLICY VALUES ARE DEMONSTRATION ASSUMPTIONS AND HAVE NOT BEEN CONFIRMED AS CURRENT SBI UNDERWRITING RULES.** |
| `test_fixture` | in-memory, `tests/` only | nothing outside the test suite: it refuses to load unless `tests/conftest.py` has enabled test mode | test banner |

Safeguards (all tested): no implicit environment; environments cannot be mixed in one assessment; the fixture lives under `tests/` and cannot be imported by shipped code; synthetic assumptions cannot be "reconfirmed" into evidence; the environment is recorded in every assessment and report; affordability numbers are identical in both environments because both carry the same configured values; each file may only contain its own kind of criterion (the loader rejects anything else).

## Phase 2 in brief
- **Dataset**: 10,000 fictional applicants, programmatically generated (`ml/synthetic_data.py`, seed 20261101); 933 defaults (9.33%) vs 9,067. Derived ratios are computed, not drawn; the target `default_90dpd_12m` comes from a stochastic latent process with unobserved noise (best achievable AUC from the observable features is 0.831). See `docs/DATASET_DOCUMENTATION.md`.
- **Models**: Logistic Regression (baseline) and Gradient Boosting, in scikit-learn Pipelines (preprocessing fitted on training rows only); stratified 60/20/20 split; hyper-parameters chosen on validation log-loss; calibration chosen on validation; the test set is used for no choice.
- **Held-out test results (synthetic data only)**: ROC-AUC LR 0.822 vs GB 0.832; Brier LR 0.0649 vs GB 0.0646; the paired-bootstrap AUC difference interval (-0.005 to +0.026) includes zero, so the models are statistically tied. Deployed model: **logistic_regression** (chosen on validation by a rule fixed in advance). See `docs/MODEL_EVALUATION_REPORT.md`.
- **Applicant-level risk** (`ml/predict.py`): probability, demonstration band (`config/risk_bands.json`), main factors (exact linear contributions for LR, SHAP for GB), explanation, missing/unverified inputs. Missing critical inputs withhold the prediction; other gaps are imputed with the training median (never zero) and reported; new-to-credit is a thin file, not bad credit.
- **A high band means human review, never automatic rejection; a low band never overrides unaffordability or a failed criterion.**

## Documentation
| File | Content |
|---|---|
| `docs/MODEL_EVALUATION_REPORT.md` | metrics, confusion matrices, calibration, model comparison, disclosure of one model revision |
| `docs/MODEL_LIMITATIONS.md` | what the model is and is not |
| `docs/DATASET_DOCUMENTATION.md` | generation process, assumptions, column dictionary |
| `docs/REAL_DATA_INTEGRATION.md` | data, anonymisation, agreements and architecture for replacing synthetic data with authorised bank data |
| `docs/POLICY_VERIFICATION_REPORT.md` | per-criterion sources, passages and freshness for the evidence-backed policies |
| `CHANGES.md` | every change, bugs found, decisions and limitations |
| `models/synthetic_generic/plots/` | ROC, precision-recall, calibration, confusion matrices, feature importance, LR coefficients |

## Layout
`core/` Phase 1 engine (EMI, ratios, validation, policy, eligibility, scenarios, recommendations, maturity, credit flags, `policy_env.py`, `assess.py`) | `ml/` Phase 2 (generator, features, training, calibration, prediction, bank calibration hook, reports) | `config/` policies, synthetic policy, settings, risk bands, data contract | `data/` sample applicants and the synthetic CSV | `models/` saved models and artefacts | `sample_assessments/` full outputs | `tests/` 308 tests.

## Limitations
Synthetic data and assumed base rate; not representative of SBI or Indian default rates; the model has no bank-specific knowledge; no fairness analysis; one population and one seed; admin controls are file-based and not tamper-proof; HDFC and ICICI are experimental and evidence-backed only; saved `.joblib` models need scikit-learn 1.8.x. Full lists in `docs/MODEL_LIMITATIONS.md` and `CHANGES.md`. Phase 3 (interface) has not been started.


## Phase 3: the bank-officer application (Streamlit)
Decision support for bank officers: registration, document upload with local OCR/text extraction, assessments in an explicitly chosen policy environment, scenario simulator, PDF reports, SQLite persistence, audit trail, officer/administrator roles. **It never approves or rejects a loan.**

```bash
pip install -r requirements.txt          # plus the Tesseract binary for OCR: see packages.txt (optional)
python -m app.bootstrap                  # creates the DB and the first users; prints generated passwords ONCE (or reads LOAN_APP_*_PASSWORD)
streamlit run app/streamlit_app.py       # open the printed local URL
python -m pytest -q                      # 308 original + Phase 3 tests
```
Database: `data/app/loan_app.db` (uploads in `data/app/uploads`, reports in `data/app/reports`; override with `LOAN_APP_*` variables, see `.env.example`). No credentials are shipped.
Sample documents for trying extraction: `data/sample_documents/` (fictional; regenerate with `python tools/make_sample_documents.py`).
Docs: `docs/ARCHITECTURE.md`, `docs/USER_GUIDE.md`, `docs/SECURITY_AND_PRIVACY.md` (prototype limits), `docs/PHASE3_IMPLEMENTATION_AND_TESTING_REPORT.md`, screenshots in `docs/screenshots/`.


## Run locally or publish online
Windows: double-click **`run_local.bat`** (macOS/Linux: `./run_local.sh`) and open http://localhost:8501. Manual: `pip install -r requirements.txt`, `python -m app.bootstrap`, `streamlit run app/streamlit_app.py`.
Cloud (Render, persistent disk, public HTTPS URL): see **`DEPLOYMENT.md`** (`render.yaml`, `Dockerfile`, `.env.example`). Tests: `pip install -r requirements-dev.txt && python -m pytest -q`.
