"""
Claim review orchestrator — Phase 7 "Unified Review" + v1.3 Coding Validation Agent.

Deterministic Python controller, not a free-running LLM loop:
  1. Run the rule layer synchronously (rules.rule_engine.review_claim()). A HIGH
     NPI finding short-circuits there already — NCCI/MUE/code validity never run.
  2. If the rule layer did not short-circuit, call the Coverage Validation Agent
     (agents.coverage_validation.validate_coverage()), then the Coding Validation
     Agent (agents.coding_validation.validate_coding()) sequentially — no parallel
     execution. If the rule layer short-circuited, neither agent is called: an
     invalid provider identity makes an LLM call pointless and costs an
     unnecessary API call. rule_findings is passed to both agents (TD-24 Phase 3)
     so their prompts can avoid restating or piling on top of a deterministic
     finding the rule engine already raised.
  3. Pass rule findings + coverage findings + coding findings to
     agents.denial_prevention.synthesize() for deterministic scoring — no LLM
     call happens in this module or in denial_prevention.

checks_run reflects only checks that actually executed this run — a short-
circuited claim's checks_run has one entry (NPI), not all seven.

Scope note: Documentation Review remains deferred (see docs/Roadmap.md,
docs/Technical_Debt_Register.md TD-04, docs/Architecture_Decisions.md ADR-016).
It is a future capability under evaluation, not an MVP requirement; this module
does not call it, does not list it in checks_run, and does not fabricate a
placeholder finding for it. A claim with no attached note is simply reviewed on
code, coverage, and coding alone.
"""

from __future__ import annotations

from agents import denial_prevention
from agents.coding_validation import validate_coding
from agents.coverage_validation import validate_coverage
from agents.run_logger import timed_run
from agents.provider import configured, provider_name
from rules.models import ClaimIn, Finding, RiskAssessment
from rules.rule_engine import CHECKS_RUN, review_claim

_COVERAGE_CHECK_LABEL = "Coverage validation — LLM medical necessity review (RAG-grounded, JSON fallback)"
_CODING_CHECK_LABEL = "Coding validation — LLM coding defensibility review"


def _ai_enabled() -> bool:
    """A configured key enables attempts; it does not verify connectivity."""
    return configured()


def run_review(claim: ClaimIn) -> tuple[RiskAssessment, dict[str, list[dict]]]:
    """
    Run the full claim review: rule layer, then coverage + coding agents if
    applicable, then synthesis.

    Returns (assessment, retrieved_policies). retrieved_policies maps
    "coverage_validation" / "coding_validation" to the up-to-3 policy dicts
    that agent retrieved for this claim (empty list if that agent didn't run
    or found nothing) — so the UI can show "Supporting Policies Reviewed"
    (TD-22) without a second retrieval call. RiskAssessment's own shape is
    unchanged; this is a sibling return, not a new field on it, so the
    audit/DB layer (which only ever sees RiskAssessment.findings) is untouched.
    """
    with timed_run(claim_id=claim.claim_id, agent="rule_layer") as result:
        rule_findings = review_claim(claim)
        result["finding_count"] = len(rule_findings)

    retrieved_policies: dict[str, list[dict]] = {"coverage_validation": [], "coding_validation": []}

    ai_details = {}
    if _rule_layer_short_circuited(rule_findings) or not _ai_enabled():
        checks_run = [CHECKS_RUN[0]] if _rule_layer_short_circuited(rule_findings) else list(CHECKS_RUN)
        coverage_findings: list[Finding] = []
        coding_findings: list[Finding] = []
    else:
        checks_run = list(CHECKS_RUN)
        for name, validate, label in (
            ("coverage_validation", validate_coverage, _COVERAGE_CHECK_LABEL),
            ("coding_validation", validate_coding, _CODING_CHECK_LABEL),
        ):
            with timed_run(claim_id=claim.claim_id, agent=name) as result:
                output = None
                try:
                    output = validate(claim, rule_findings)
                    findings, policies = output
                    status = getattr(output, "status", "complete")
                    error = getattr(output, "error", "")
                except Exception:
                    findings, policies, status, error = [], [], "failed", "unexpected_error"
                ai_details[name] = {"status": status, "error": error}
                errors = getattr(output, "validation_errors", [])
                if errors:
                    ai_details[name]["validation_errors"] = errors
                retrieved_policies[name] = policies
                result.update(finding_count=len(findings), success=status == "complete", error=error,
                              validation_errors=errors)
                checks_run.append(f"{provider_name().title()}: {label} — {status}")
                if name == "coverage_validation":
                    coverage_findings = findings
                else:
                    coding_findings = findings

    assessment = denial_prevention.synthesize(rule_findings, coverage_findings, coding_findings, checks_run)
    assessment.ai_provider = provider_name()
    assessment.ai_details = ai_details
    assessment.review_mode = (
        "rule_only" if not assessment.ai_details else
        "live" if all(d["status"] == "complete" for d in assessment.ai_details.values()) else
        "incomplete"
    )
    if assessment.review_mode == "incomplete":
        assessment.escalation_required = True
    return assessment, retrieved_policies


def _rule_layer_short_circuited(rule_findings: list[Finding]) -> bool:
    """
    True iff review_claim() returned early on an invalid-NPI HIGH finding.

    review_claim() guarantees a HIGH npi_invalid finding only ever appears in
    the short-circuit return path — in the normal path, NPI findings included
    are MEDIUM (NPPES not found) or absent. Same detection rule already used
    in app/main.py:_render_checks_summary().
    """
    return any(f.rule == "npi_invalid" and f.severity == "HIGH" for f in rule_findings)
