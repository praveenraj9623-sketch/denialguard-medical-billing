# Coding argument validation follow-up — November 8, 2026

## Confirmed inspection findings

The Groq request sends the coding agent's Anthropic-style `input_schema` as
OpenAI function `parameters`, requests exactly one tool, JSON-decodes
`message.tool_calls[].function.arguments`, validates the allowed name and
arguments, then builds a Finding only after validating the retrieved document ID.

Before this follow-up, the request's string schemas allowed empty strings and
its confidence schema allowed arbitrary numbers. Local validation nevertheless
required nonblank strings and finite confidence numbers between 0 and 1.
These were real request/validator contract differences. They are corrected by
`minLength: 1`, a non-whitespace pattern, explicit confidence bounds, and
`additionalProperties: false` in both agents' source tool schemas. The prompts
now describe the same argument requirements. No missing argument is synthesized,
no string-to-number coercion is performed, and invalid responses still fail.

## Limit of the incident diagnosis

The user's original coding `invalid_arguments` response was not saved by the
previous logger, which recorded only the error category. It cannot be recovered
from that record. An initial live orchestrator request and four further coding
requests completed successfully. Two later coding requests hit rate limits.
None reproduced the original `invalid_arguments` rejection. Consequently there
is no observed original rejected path/type to report, and no claim that a
simulated test case is the original response.

A proposed batch of six paced reproduction requests was rejected by automatic
approval review because of additional paid calls following repeated rate limits.
That batch was not executed. The user subsequently declined any further paid
reproduction requests. No additional live requests were made during the offline
follow-up, and there is no pending reproduction batch. Safe diagnostics remain
available for a recurrence during normal use.

## Safe diagnostics now retained

`ReviewError.validation_errors` and `AgentResult.validation_errors` contain only
schema-owned field paths, expected constraints, and received JSON types or
missing/blank/range flags. Arbitrary model values, unknown property names, raw
response bodies, headers, and credentials are excluded. Diagnostics propagate
to `RiskAssessment.ai_details`, append-only run-log records, and incomplete-result
UI text. Existing audit-decision database behavior is unchanged.

Examples of **mocked** rejection diagnostics:

| Path inside decoded function.arguments | Expected | Rejected example type/status |
| --- | --- | --- |
| `reason` | nonblank string | null / blank string / array |
| `recommendation` | string | missing |
| `confidence` | finite number in [0, 1] | string |
| `citation_excerpt` | nonblank string | null |
| `<additional_property>` | no additional properties | present |

The full diagnostic path starts with `tool_calls[0].function.arguments`.
These examples are regression tests, not observed fields from the original incident.

## Tests (mocked network)

Command:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_groq_provider.py tests/test_coding_validation.py tests/test_coverage_validation.py tests/test_orchestrator.py tests/test_run_logger.py tests/test_secrets.py tests/test_session_api_key.py tests/test_policy_repository.py tests/test_manual_claim_review.py tests/test_cached_ai_demo.py -q
```

Final offline result: **262 passed, 0 failed**. The suite ran through a temporary
runner that blocked external socket connections while permitting loopback for
the local Streamlit health check. Groq/Anthropic responses were mocked; no paid
API requests were made.

The earlier result was 258 passed and 2 failed. Inspection confirmed both failures
were stale wording assertions in
`test_system_prompt_instructs_not_to_duplicate_rule_layer_findings`: the tests
required "Do not restate or duplicate" and "genuinely", while the current prompts
say "Do not restate those — they are handled separately" and explain that a
policy-based concern can be distinct from a code-rule finding. No implementation
change was necessary for those failures.

Both assertions now check the meaningful current guidance in its rule-context
section: avoid restating deterministic findings, allow distinct concerns supported
by policy text, and retain the report/no-concern tool instructions. Two additional
tests (one per agent) check that no rule findings does not imply a clean claim and
that independent policy review still runs. These are offline prompt-contract
checks, not claims about live model reasoning. Existing mocked tests still verify
that actual requests include rule findings and use the expected tool semantics.

Nine added regression cases cover schema/validator agreement, safe missing/type/
blank/additional-field diagnostics, multiple simultaneous rejections, preservation
of rule and successful Coverage findings when Coding fails, failure logging,
and display of the rejected paths. Citation validation, no-key gating, NPI
short-circuiting, and session behavior remain covered by the relevant suite.

## Final live verification (separate from mocked tests)

One final invocation of the real `agents.orchestrator.run_review()` used the
existing local Groq configuration after these changes, without mocks or retries.
Provider/model: Groq `openai/gpt-oss-20b`; claim: CLM-001.

- Coverage: **complete**, one finding citing `LCD_E_M_MEDICAL_NECESSITY_Z00`.
- Coding: **complete**, one finding citing `LCD_E_M_MEDICAL_NECESSITY_Z00`.
- Retrieval: three curated JSON policies per agent (optional ChromaDB unavailable).
- Rule findings: **3**, preserved.
- Overall review mode: **live**, risk **HIGH**. Successful completion does not
  approve the claim; human review and decisions remain required.

`CLAUDE.md` and `GROQ.md` were left untouched. No push or deployment occurred.

## Final status after offline follow-up

- The confirmed request-schema/local-validator mismatch is fixed.
- The exact original rejected field remains unconfirmed; no response or field
  values were invented to fill that gap.
- Both agents completed the previously recorded final live CLM-001 verification.
  That verification was not rerun during the offline follow-up.
- Safe validation diagnostics, citation checks, rule findings, human review, and
  audit behavior remain unchanged by the test-only wording updates.
- No blockers remain for the scoped offline test cleanup. The original incident's
  missing field-level evidence remains a diagnostic limitation, not proof of a
  particular rejected field.
