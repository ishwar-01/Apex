"""Writes a full plain-text assessment for each sample applicant. The bank/product MUST be chosen explicitly.
Usage: python run_demo.py <bank> --env <evidence_backed|synthetic_demo> [--outdir DIR] [--no-risk]
Both the bank/product AND the policy environment are REQUIRED; there are no defaults. 'test_fixture' is not available here."""
import sys
from pathlib import Path
from core.assess import assess
from core.policy import load_policies
from data import sample_applicants as S


def render(name, p, a) -> str:
    L = []; w = L.append
    ss, r, ind, el = a["scenarios"], a["recommendations"], a["indicators"], a["eligibility_selected"]
    o = ss.scenarios[0]
    w("=" * 100)
    w(f"{p.application_id} ({name}) | PAN {a['pan_masked']} | SELECTED: {a['selected_bank']} - {a['selected_product']} [{a['selected_role']}]")
    w("=" * 100)
    if a.get("environment_banner"):
        w("!" * 100); w(a["environment_banner"]); w("!" * 100)
    w(f"POLICY ENVIRONMENT: {a['policy_environment']} - {a['environment_description']}")
    w(f"Data completeness {a['completeness']['percent_complete']}% | verified {a['completeness']['percent_verified']}% | missing: {', '.join(a['completeness']['missing']) or 'none'}")
    w(f"Request: INR {o.amount:,.0f} over {o.tenure} months at {o.rate_pct}%  (rate basis: {ss.rate_source})")
    w(f"Net income INR {p.income.net_monthly or 0:,.0f} | existing EMIs INR {ratios_ex(p):,.0f} | proposed EMI INR {o.emi:,.0f}\n")
    w("RESULT 1 - FINANCIAL AFFORDABILITY (not eligibility, not approval)")
    w(f"  Outcome {a['affordability_outcome']}: {r.headline}")
    w(f"  {ss.message}")
    if ss.limits["max_foir_pct"]: w(f"  Capacity bound by: {ss.capacity['binding']} (published FOIR limit {ss.limits['max_foir_pct']}%{' - source OUTDATED; used only as a conservative structuring limit' if el.policy_stale else ''})")
    else: w(f"  Capacity bound by: {ss.capacity['binding']} (no confirmed FOIR limit for this product)")
    w(f"  Capacity INR {ss.capacity['recommended']:,.0f}/month | post-loan FOIR {ind['foir_proposed'].value if ind['foir_proposed'].value is None else round(ind['foir_proposed'].value,1)}% | disposable after EMI INR {ind['net_disposable_post'].value:,.0f}")
    for c in r.constraints: w(f"  constraint: {c}")
    w("")
    w(f"RESULT 2 - ELIGIBILITY FOR {a['selected_bank'].upper()} ({a['selected_product']})")
    w(f"  STATUS: {el.display_status}")
    w("  REASONS (kept separate):")
    labels = {"applicant_information_missing": "APPLICANT INFORMATION MISSING", "policy_outdated": "POLICY INFORMATION OUTDATED",
              "policy_unresolved": "POLICY INFORMATION UNRESOLVED", "policy_undisclosed": "POLICY INFORMATION UNDISCLOSED"}
    for rs in el.reasons:
        w(f"    [{labels[rs['type']]}]{'' if rs['blocks_status'] else ' (does not block status)'} {', '.join(rs['items'])}")
    if not el.reasons: w("    none")
    if el.foir:
        f = el.foir
        w("  EMI/NMI (FOIR) CHECK:")
        w(f"    Formula : {f['formula']}")
        w(f"    Working : {f['calculation']}  |  threshold {f['threshold']}% -> {'WITHIN' if f['within_threshold'] else 'ABOVE' if f['within_threshold'] is False else 'cannot be assessed'}")
        w(f"    Basis   : {f['threshold_source']}")
        if not f["is_official_definition"]: w(f"    NOTE    : {f['note']}")
    if el.maturity:
        m = el.maturity
        w("  MATURITY CHECK (retirement / end of contract / age 60 - earliest applies):")
        lim = f"limit {m['limit_date']} ({m['binding']})" if m["limit_date"] else "limit cannot be determined yet"
        w(f"    {m['employment_type']} | loan start assumed {m['start_date_assumed']} | maturity {m['maturity_date']} | {lim} -> {m['result'].upper().replace('_', ' ')}")
        w(f"    {m['reason']}  Retirement / contract-end information is {'UNVERIFIED (manually entered)' if m['unverified'] else 'marked verified'}.")
    for rq in a["conditional_requirements"]:
        w(f"  CONDITIONAL REQUIRED FIELD: {rq['field']}" + (f" (alternative: {rq['alternative']})" if rq['alternative'] else "") + f" - {'provided' if rq['satisfied'] else 'MISSING'}; show when {rq['show_when']}")
    pv = el.policy_verification
    w(f"  POLICY VERIFICATION STATUS: {pv['status'].upper()}  (earliest next review {pv['earliest_next_review']}; freshness limit {next(iter(pv['criteria'].values()))['limit_days']} days)")
    for k, v in pv["criteria"].items():
        if v["applies"]:
            w(f"    {k:<28} {v['status']:<19} source updated {v['source_last_updated']} | last verified {v['last_verified']} | admin reconfirmed {v['reconfirmed_on'] or 'never'} | next review {v['next_review_date']}")
    for k, v in pv["criteria"].items():
        for pr in v["reconfirmation_problems"]: w(f"    REJECTED reconfirmation for {k}: {pr}")
    for title, items in [("PASSED (confirmed)", el.passed), ("FAILED (confirmed)", el.failed), ("MISSING APPLICANT DATA", el.missing_data),
                         ("UNRESOLVED POLICY", el.unresolved), ("ADVISORY ONLY (third-party / preference)", el.advisory)]:
        if items:
            w(f"  {title}:")
            for c in items: w(f"    - {c.label}: {c.explanation[:230]}")
    if el.stale:
        w("  OUTDATED POLICY (informational against the outdated value; neither pass nor fail):")
        for c in el.stale: w(f"    - {c.label}: would {str(c.stale_outcome).upper()} against outdated value. ({c.freshness['age_days']} days old)")
    if el.undisclosed: w("  NOT PUBLICLY DISCLOSED: " + ", ".join(c.label for c in el.undisclosed))
    for x in el.remarks: w(f"  note: {x}")
    w("")
    ad = a["adverse_credit"]
    w(f"RESULT 3 - ADVERSE CREDIT HISTORY WARNING: level = {ad['level'].upper()}")
    w(f"  {ad['message']}")
    for i in ad["items"]: w(f"    - {i}")
    w("")
    cr = a.get("credit_risk")
    w("RESULT 4 - MACHINE-LEARNING CREDIT RISK (separate from results 1-3; never overrides them)")
    if cr is None:
        w("  Not run (no risk model supplied).")
    else:
        w(f"  {cr['banner']}")
        m = cr["model"]; ev = m["evaluation_summary"]
        if cr["status"] != "available":
            w(f"  STATUS: NOT AVAILABLE. {cr['reason']}")
        else:
            rb = cr["risk_band"]
            w(f"  Estimated probability of 90+ DPD within 12 months: {cr['probability_pct']}  ({cr['relative_to_base_rate']:.1f}x the {cr['base_rate_in_training']*100:.1f}% synthetic training average)")
            w(f"  Demonstration risk band: {rb['label']} ({rb['min']*100:.0f}%-{rb['max']*100:.0f}%)  |  review level: {cr['review_level']}")
            w(f"  Action: {rb['action']}")
        w(f"  Model: {m['name']} ({m['model_id']}), trained on {m['training_dataset_size']:,} SYNTHETIC records ({m['n_train']:,} train); data source: {m['data_source']}")
        w(f"  Evaluation (held-out synthetic test set only): AUC {ev['test_roc_auc']:.3f}, Brier {ev['test_brier']:.4f}, ECE {ev['test_ece']:.4f}, calibration method {ev['calibration_method']}")
        w(f"  Calibration scope: {m.get('calibration_scope', cr.get('calibration_scope'))}")
        if cr["status"] == "available":
            w("  Factors associated with HIGHER estimated risk: " + ("; ".join(f"{x['description']} ({x['contribution_log_odds']:+.2f})" for x in cr["top_risk_increasing_factors"][:4]) or "none material"))
            w("  Factors associated with LOWER estimated risk : " + ("; ".join(f"{x['description']} ({x['contribution_log_odds']:+.2f})" for x in cr["top_risk_decreasing_factors"][:4]) or "none material"))
            w(f"  Explanation ({cr['explanation_method']}): {cr['explanation']}")
            w(f"  Reliability: {cr['reliability']}. {cr['imputation_note']}")
            if cr["imputed_features"]: w("  Imputed (training median, not zero): " + ", ".join(cr["imputed_features"]))
            if cr["structurally_absent_features"]: w("  Structurally absent (new-to-credit / no history; not a data error): " + ", ".join(cr["structurally_absent_features"]))
            w(f"  Other model for transparency: {cr['other_model_probability']['model']} = {cr['other_model_probability']['probability']*100:.1f}%")
        if cr["missing_inputs"]: w("  Missing inputs: " + "; ".join(f"{k} ({v})" for k, v in cr["missing_inputs"].items()))
        w("  Unverified inputs: " + "; ".join(cr["unverified_inputs"]))
        for n in cr["notes"]: w(f"  Note: {n}")
        w(f"  {cr['disclaimer']}")
    w("")
    w(f"OVERALL GUIDANCE: {a['guidance']}")
    if cr is not None: w(f"WITH MODEL RISK NOTE: {a.get('guidance_with_risk', a['guidance'])}")
    w("")
    w("SCENARIOS (selected bank only)")
    if ad["level"] != "none": w(f"  NOTE: scenario labels describe affordability and published-criteria checks only. The {ad['level'].upper()} adverse-credit warning above still applies to every scenario.")
    for s in ss.scenarios:
        w(f"  {s.id} {s.label:<42} INR {s.amount:>9,.0f} {s.tenure:>3}m {s.rate_pct:>5.2f}%  EMI {s.emi:>8,.0f}  interest {s.total_interest:>9,.0f}  FOIR {s.foir_post or 0:>5.1f}%  left {s.disposable_after:>9,.0f}")
        w(f"       status: {s.status_label} | bank: {s.bank_eligible_text}")
        for x in s.assumptions[:2]: w(f"       assumption: {x[:200]}")
    w(f"  Best feasible: {('%s - INR %s over %sm' % (ss.best_feasible.label, format(ss.best_feasible.amount, ',.0f'), ss.best_feasible.tenure)) if ss.best_feasible else 'none selected'}")
    w("")
    w("RECOMMENDATIONS")
    for x in r.recommendations: w(f"  - {x.title}: {x.text[:260]}")
    w("")
    w("COMPARISON (each bank evaluated independently with its own rate assumption; never mixed)")
    for pid, e in a["eligibility"].items():
        tag = " <- selected" if pid == a["selected_policy"] else ""
        w(f"  {pid:<6} {e.status:<36} pass {len(e.passed)} / fail {len(e.failed)} / missing {len(e.missing_data)} / unresolved {len(e.unresolved)} / undisclosed {len(e.undisclosed)}  rate {e.rate_used_pct}%{tag}")
    w("")
    w("DATA ISSUES: " + ("; ".join(f"[{i.severity}] {i.message}" for i in a["issues"]) or "none"))
    w("\n" + a["disclaimer"])
    return "\n".join(L)


def ratios_ex(p):
    from core import ratios
    return ratios.existing_emi(p)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Print/write the six sample assessments. Bank and policy environment are mandatory.")
    ap.add_argument("bank", choices=sorted(load_policies(reconfirmations={})))
    ap.add_argument("--env", required=True, choices=["evidence_backed", "synthetic_demo"], help="policy environment (no default)")
    ap.add_argument("--outdir", default=None, help="write one text file per applicant instead of printing")
    ap.add_argument("--no-risk", action="store_true", help="skip the machine-learning risk result")
    args = ap.parse_args()
    from core import policy_env
    pols = policy_env.load_environment(args.env)
    if args.bank not in pols:
        sys.exit(f"'{args.bank}' is not available in the {args.env} environment. Available: {sorted(pols)}")
    out = Path(args.outdir) if args.outdir else None
    if out: out.mkdir(parents=True, exist_ok=True)
    risk = None
    if not args.no_risk:
        from ml.predict import load_risk_model
        risk = load_risk_model()
        if risk is None: print("NOTE: no trained risk model found (run: python -m ml.generate && python -m ml.train)", file=sys.stderr)
    for name, make in S.ALL.items():
        p = make(); res = assess(p, args.bank, policies=pols, risk_model=risk); text = render(name, p, res)
        if out: (out / f"{p.application_id}_{name}_{args.bank}_{args.env}.txt").write_text(text, encoding="utf-8")
        else: print(text)
