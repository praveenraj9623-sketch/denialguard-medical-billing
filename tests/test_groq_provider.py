"""Mocked Groq contract, failure isolation, config, and real Streamlit flows."""
import importlib
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import httpx
import pytest
from streamlit.testing.v1 import AppTest

from agents import provider
from agents.secrets import clear_session_key, get_secret
from rules.models import ClaimIn, Citation, Finding


@pytest.fixture(autouse=True)
def isolated_config(monkeypatch, tmp_path):
    import agents.secrets as secrets
    monkeypatch.setattr(secrets, '_ROOT_ENV', tmp_path / '.env')
    monkeypatch.setenv('LLM_PROVIDER', 'groq')
    monkeypatch.delenv('GROQ_API_KEY', raising=False)
    monkeypatch.delenv('ANTHROPIC_API_KEY', raising=False)
    # No owner secrets or session state can accidentally trigger a live request.
    monkeypatch.setattr('streamlit.secrets', {})


@pytest.fixture
def claim():
    return ClaimIn('GROQ-TEST', 'Medicare', '', ['99213'], ['Z00.00'], [], '11', {})


@pytest.fixture
def transport(monkeypatch):
    monkeypatch.setenv('GROQ_API_KEY', 'mock-secret-do-not-export')
    client = MagicMock()
    with patch('agents.provider.httpx.Client') as factory:
        factory.return_value.__enter__.return_value = client
        yield client


POLICY = {'document_id': 'LCD_TEST', 'title': 'Test policy', 'section': 'Indications',
          'edition': 'synthetic test', 'effective_date': '2026-01-01',
          'excerpt': 'Coverage requires documentation of a separate problem.'}


def args(kind):
    return dict(issue='Documentation missing', recommendation='Review the record.', severity='MEDIUM',
                confidence=0.81, citation_doc_id='LCD_TEST', citation_section='Indications',
                citation_excerpt=POLICY['excerpt'])


def reply(name, arguments, finish='tool_calls'):
    return {'choices': [{'finish_reason': finish, 'message': {'tool_calls': [
        {'type': 'function', 'function': {'name': name, 'arguments': json.dumps(arguments)}}]}}]}


def respond(client, data, status=200):
    client.post.return_value = httpx.Response(status, json=data,
        request=httpx.Request('POST', 'https://api.groq.com/openai/v1/chat/completions'))


@pytest.mark.parametrize('kind', ['coverage', 'coding'])
def test_no_selected_key_makes_no_request(kind, claim, monkeypatch):
    # Even a key for the other provider must not enable Groq.
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'unused-other-provider')
    mod = importlib.import_module(f'agents.{kind}_validation')
    with patch('agents.provider.httpx.Client') as client, patch('anthropic.Anthropic') as other:
        result = getattr(mod, f'validate_{kind}')(claim)
    assert result == ([], [])
    assert result.status == 'rule_only'
    client.assert_not_called()
    other.assert_not_called()


@pytest.mark.parametrize('kind', ['coverage', 'coding'])
def test_groq_schema_and_cited_finding(kind, claim, transport):
    mod = importlib.import_module(f'agents.{kind}_validation')
    respond(transport, reply(f'report_{kind}_finding', args(kind)))
    with patch.object(mod, '_retrieve_policies', return_value=[POLICY]):
        result = getattr(mod, f'validate_{kind}')(claim)
    assert result.status == 'complete'
    finding = result[0][0]
    assert finding.citation.doc_id == 'LCD_TEST'
    assert finding.citation.excerpt == POLICY['excerpt']
    assert finding.confidence == 0.81
    request = transport.post.call_args
    assert request.args[0] == 'https://api.groq.com/openai/v1/chat/completions'
    body = request.kwargs['json']
    assert body['model'] == 'openai/gpt-oss-20b'
    assert body['tool_choice'] == 'required'
    assert body['parallel_tool_calls'] is False
    function = body['tools'][0]['function']
    assert function['parameters']['properties'] == mod._TOOLS[0]['input_schema']['properties']
    assert function['parameters']['required'] == mod._TOOLS[0]['input_schema']['required']
    assert function['parameters']['additionalProperties'] is False
    assert 'input_schema' not in function


@pytest.mark.parametrize('kind', ['coverage', 'coding'])
def test_no_concern_is_successful_only_after_valid_tool(kind, claim, transport):
    mod = importlib.import_module(f'agents.{kind}_validation')
    respond(transport, reply(f'no_{kind}_concern', {'reason': 'Policy supports the service.'}))
    with patch.object(mod, '_retrieve_policies', return_value=[POLICY]):
        result = getattr(mod, f'validate_{kind}')(claim)
    assert result.status == 'complete' and result[0] == []


@pytest.mark.parametrize('mutation', [
    {'citation_doc_id': 'UNKNOWN'}, {'confidence': '0.8'}, {'confidence': True},
    {'confidence': 1.2}, {'confidence': float('nan')}, {'severity': 'CRITICAL'},
    {'issue': []}, {'citation_excerpt': None}, {'recommendation': ''}, {'unexpected': 'extra'},
])
def test_bad_arguments_fail_without_findings(mutation, claim, transport):
    from agents.coverage_validation import validate_coverage
    arguments = {**args('coverage'), **mutation}
    respond(transport, reply('report_coverage_finding', arguments))
    with patch('agents.coverage_validation._retrieve_policies', return_value=[POLICY]):
        result = validate_coverage(claim)
    assert result[0] == [] and result.status == 'failed'


@pytest.mark.parametrize('data', [
    {}, {'choices': []}, reply('execute_shell', {'command': 'anything'}),
    reply('no_coverage_concern', {}), reply('no_coverage_concern', {'reason': 42}),
    reply('no_coverage_concern', {'reason': 'ok'}, finish='length'),
    {'choices': [{'finish_reason': 'stop', 'message': {'content': 'No issues'}}]},
])
def test_invalid_response_is_failed(data, claim, transport):
    from agents.coverage_validation import validate_coverage
    respond(transport, data)
    with patch('agents.coverage_validation._retrieve_policies', return_value=[POLICY]):
        output = validate_coverage(claim)
    assert output.status == 'failed' and output[0] == []


def test_invalid_json_arguments_and_multiple_tools_fail(claim, transport):
    from agents.coverage_validation import validate_coverage
    data = reply('no_coverage_concern', {'reason': 'ok'})
    for calls in ([{'type': 'function', 'function': {'name': 'no_coverage_concern', 'arguments': '{bad'}}],
                  data['choices'][0]['message']['tool_calls'] * 2):
        data['choices'][0]['message']['tool_calls'] = calls
        respond(transport, data)
        with patch('agents.coverage_validation._retrieve_policies', return_value=[POLICY]):
            assert validate_coverage(claim).status == 'failed'


@pytest.mark.parametrize('status,category', [(401, 'authentication'), (403, 'authentication'),
                                           (429, 'rate_limit'), (500, 'provider_error')])
def test_http_errors_are_safe_failures(status, category, claim, transport, caplog):
    from agents.coverage_validation import validate_coverage
    respond(transport, {'error': 'mock-secret-do-not-export'}, status=status)
    with patch('agents.coverage_validation._retrieve_policies', return_value=[POLICY]):
        result = validate_coverage(claim)
    assert result.status == 'failed' and result.error == category
    assert 'mock-secret-do-not-export' not in caplog.text


def test_timeout_failure(claim, transport):
    from agents.coding_validation import validate_coding
    transport.post.side_effect = httpx.ReadTimeout('mock-secret-do-not-export')
    with patch('agents.coding_validation._retrieve_policies', return_value=[POLICY]):
        result = validate_coding(claim)
    assert result.status == 'failed' and result.error == 'timeout'


def test_invalid_json_body_failure(claim, transport):
    from agents.coverage_validation import validate_coverage
    transport.post.return_value = httpx.Response(200, text='<html>error</html>',
        request=httpx.Request('POST', 'https://api.groq.com'))
    with patch('agents.coverage_validation._retrieve_policies', return_value=[POLICY]):
        assert validate_coverage(claim).status == 'failed'


def test_no_retrieved_documents_is_incomplete(claim, transport):
    from agents.coverage_validation import validate_coverage
    with patch('agents.coverage_validation._retrieve_policies', return_value=[]):
        output = validate_coverage(claim)
    assert output.status == 'incomplete'
    transport.post.assert_not_called()


def test_failure_preserves_rules_and_logs_failure(claim, transport, monkeypatch):
    from agents.orchestrator import run_review
    logs = []
    monkeypatch.setattr('agents.run_logger._logger.info', logs.append)
    rule = Finding('test_rule', 'HIGH', 'Rule issue', 'Fix it', Citation('rules', 'RULE', '', ''), 1.0)
    respond(transport, {}, status=401)
    with patch('agents.orchestrator.review_claim', return_value=[rule]), \
         patch('agents.coverage_validation._retrieve_policies', return_value=[POLICY]), \
         patch('agents.coding_validation._retrieve_policies', return_value=[POLICY]):
        assessment, _ = run_review(claim)
    assert assessment.findings == [rule]
    assert assessment.review_mode == 'incomplete' and assessment.escalation_required
    records = [json.loads(line) for line in logs]
    assert records[0]['success'] is True
    assert all(r['success'] is False for r in records[1:])
    assert 'mock-secret-do-not-export' not in str(records)


def test_npi_short_circuit_never_calls_groq(claim, transport):
    from agents.orchestrator import run_review
    claim.npi = '123'
    result, _ = run_review(claim)
    assert result.review_mode == 'rule_only'
    assert len(result.checks_run) == 1
    transport.post.assert_not_called()


def test_provider_selection_and_default(monkeypatch):
    monkeypatch.delenv('LLM_PROVIDER')
    assert provider.provider_name() == 'groq'
    assert provider.model_name() == 'openai/gpt-oss-20b'
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'other-key')
    assert not provider.configured()
    monkeypatch.setenv('LLM_PROVIDER', 'anthropic')
    assert provider.configured() and provider.key_name() == 'ANTHROPIC_API_KEY'
    monkeypatch.setenv('LLM_PROVIDER', 'unsupported')
    assert not provider.configured()


def test_config_precedence_and_session_clear(monkeypatch, tmp_path):
    import agents.secrets as secrets
    path = tmp_path / '.env'
    path.write_text('GROQ_API_KEY=dotenv-value\n', encoding='utf-8')
    monkeypatch.setattr(secrets, '_ROOT_ENV', path)
    state = {'GROQ_API_KEY': 'session-value', 'session_api_key_input_GROQ_API_KEY': 'widget-value'}
    fake_st = SimpleNamespace(session_state=state, secrets={'GROQ_API_KEY': 'secrets-value'})
    with patch.dict('sys.modules', {'streamlit': fake_st}):
        monkeypatch.setenv('GROQ_API_KEY', 'env-value')
        assert get_secret('GROQ_API_KEY') == 'session-value'
        clear_session_key(state, 'GROQ_API_KEY')
        assert state == {}
        assert get_secret('GROQ_API_KEY') == 'env-value'
        monkeypatch.delenv('GROQ_API_KEY')
        assert get_secret('GROQ_API_KEY') == 'dotenv-value'
        path.write_text('GROQ_API_KEY=\n', encoding='utf-8')
        assert get_secret('GROQ_API_KEY') == 'secrets-value'


def test_utf8_loaders_preserve_unicode():
    from app.main import load_claims, load_cached_ai_demo_artifacts
    from pathlib import Path
    claims = load_claims()
    assert claims == json.loads(Path('data/synthetic/sample_claims.json').read_text(encoding='utf-8'))
    assert any('·' in c.get('demo_type', '') for c in claims)
    assert any('—' in c.get('description', '') for c in claims)
    assert load_cached_ai_demo_artifacts() == json.loads(
        Path('data/synthetic/cached_ai_demo_artifacts.json').read_text(encoding='utf-8'))
    assert 'â€' not in str(claims)


def test_streamlit_launch_rule_only_and_session_clear(monkeypatch):
    with patch('agents.provider.httpx.Client') as client:
        at = AppTest.from_file('app/main.py', default_timeout=20).run()
        assert not at.exception
        assert any('DenialGuard' in m.value for m in at.markdown)
        at.button(key='sample_review_btn').click().run()
        assert not at.exception
        assert any('Rule-only review' in m.value for m in at.info)
        client.assert_not_called()
        field = 'session_api_key_input_GROQ_API_KEY'
        at.text_input(key=field).set_value('mock-session-key').run()
        at.button(key='enable_session_api_key_btn').click().run()
        assert not at.exception
        assert at.session_state['GROQ_API_KEY'] == 'mock-session-key'
        at.button(key='clear_session_api_key_btn').click().run()
        assert not at.exception
        assert at.text_input(key=field).value == ''
        assert 'GROQ_API_KEY' not in at.session_state.filtered_state
        client.assert_not_called()


def test_incomplete_ui_never_displays_successful_clean_review(monkeypatch):
    from rules.models import RiskAssessment
    from app.main import _render_full_review_results
    assessment = RiskAssessment('CLEAN', [], True, [], review_mode='incomplete', ai_provider='groq',
        ai_details={'coverage_validation': {'status': 'failed', 'error': 'authentication'}})
    with patch('streamlit.success') as success, patch('streamlit.warning') as warning, \
         patch('streamlit.caption'), patch('streamlit.expander'), patch('streamlit.markdown'):
        _render_full_review_results(assessment, 'TEST', '', None)
    success.assert_not_called()
    assert 'incomplete' in warning.call_args_list[0].args[0]


def test_groq_orchestrator_no_key_never_dispatches_agents(claim):
    from agents.orchestrator import run_review
    with patch('agents.orchestrator.validate_coverage') as coverage, \
         patch('agents.orchestrator.validate_coding') as coding, \
         patch('agents.provider.httpx.Client') as client:
        assessment, policies = run_review(claim)
    assert assessment.review_mode == 'rule_only'
    coverage.assert_not_called()
    coding.assert_not_called()
    client.assert_not_called()


def test_complete_groq_review_is_labelled_live(claim, transport):
    from agents.orchestrator import run_review
    def post(url, **kwargs):
        tool = kwargs['json']['tools'][1]['function']['name']
        return httpx.Response(200, json=reply(tool, {'reason': 'Supported by policy.'}),
                              request=httpx.Request('POST', url))
    transport.post.side_effect = post
    with patch('agents.orchestrator.review_claim', return_value=[]), \
         patch('agents.coverage_validation._retrieve_policies', return_value=[POLICY]), \
         patch('agents.coding_validation._retrieve_policies', return_value=[POLICY]):
        assessment, _ = run_review(claim)
    assert assessment.review_mode == 'live'
    assert assessment.ai_provider == 'groq'
    assert all(d['status'] == 'complete' for d in assessment.ai_details.values())
    assert transport.post.call_count == 2


def test_model_excerpt_cannot_be_displayed_as_an_invented_quote(claim, transport):
    from agents.coverage_validation import validate_coverage
    arguments = {**args('coverage'), 'citation_excerpt': 'An invented policy quote.',
                 'citation_section': 'An invented heading'}
    respond(transport, reply('report_coverage_finding', arguments))
    with patch('agents.coverage_validation._retrieve_policies', return_value=[POLICY]):
        output = validate_coverage(claim)
    assert output[0][0].citation.excerpt == POLICY['excerpt']
    assert output[0][0].citation.section == POLICY['section']


def test_missing_confidence_is_failed_instead_of_invented(claim, transport):
    from agents.coverage_validation import validate_coverage
    arguments = args('coverage')
    del arguments['confidence']
    respond(transport, reply('report_coverage_finding', arguments))
    with patch('agents.coverage_validation._retrieve_policies', return_value=[POLICY]):
        output = validate_coverage(claim)
    assert output.status == 'failed' and output[0] == []


def test_real_streamlit_server_launches():
    import socket
    import subprocess
    import sys
    import time
    from urllib.request import urlopen
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    process = subprocess.Popen([sys.executable, '-m', 'streamlit', 'run', 'app/main.py',
        '--server.headless=true', '--server.address=127.0.0.1', f'--server.port={port}',
        '--browser.gatherUsageStats=false'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            assert process.poll() is None, 'Streamlit server exited before becoming healthy'
            try:
                with urlopen(f'http://127.0.0.1:{port}/_stcore/health', timeout=1) as response:
                    assert response.read() == b'ok'
                    break
            except OSError:
                time.sleep(0.2)
        else:
            pytest.fail('Streamlit server did not become healthy')
    finally:
        process.terminate()
        process.wait(timeout=10)


@pytest.mark.parametrize('kind', ['coding', 'coverage'])
def test_tool_contract_declares_all_locally_enforced_constraints(kind):
    """Regression for the inspected request-schema/local-validator mismatch."""
    mod = importlib.import_module(f'agents.{kind}_validation')
    for tool in provider.groq_tools(mod._TOOLS):
        schema = tool['function']['parameters']
        assert schema['additionalProperties'] is False
        assert set(schema['required']) == set(schema['properties'])
        for field, prop in schema['properties'].items():
            if prop['type'] == 'string':
                assert prop['minLength'] == 1
                assert prop['pattern'] == r'\S'
            if field == 'confidence':
                assert prop['type'] == 'number'
                assert prop['minimum'] == 0 and prop['maximum'] == 1


@pytest.mark.parametrize('arguments,expected_errors', [
    ({'reason': ''}, [('reason', 'nonblank string', 'blank string')]),
    ({'reason': None}, [('reason', 'nonblank string', 'null')]),
    ({}, [('reason', 'string', 'missing')]),
    ({'reason': ['private-value']}, [('reason', 'nonblank string', 'array')]),
    ({'reason': 'valid', 'do-not-echo-this-key': 'private-value'},
     [('<additional_property>', 'no additional properties', 'present')]),
])
def test_coding_rejection_reports_only_safe_field_paths(arguments, expected_errors, claim, transport):
    from agents.coding_validation import validate_coding
    respond(transport, reply('no_coding_concern', arguments))
    with patch('agents.coding_validation._retrieve_policies', return_value=[POLICY]):
        output = validate_coding(claim)
    assert output.status == 'failed' and output.error == 'invalid_arguments'
    assert output[0] == []
    assert output.validation_errors == [
        {'path': f'tool_calls[0].function.arguments.{field}', 'expected': expected, 'actual': actual}
        for field, expected, actual in expected_errors]
    assert 'private-value' not in json.dumps(output.validation_errors)
    assert 'do-not-echo-this-key' not in json.dumps(output.validation_errors)


def test_multiple_coding_field_rejections_are_all_reported(claim, transport):
    from agents.coding_validation import validate_coding
    arguments = {**args('coding'), 'confidence': 'private-value', 'citation_excerpt': None}
    del arguments['recommendation']
    respond(transport, reply('report_coding_finding', arguments))
    with patch('agents.coding_validation._retrieve_policies', return_value=[POLICY]):
        output = validate_coding(claim)
    paths = {p['path']: p['expected'] for p in output.validation_errors}
    assert paths == {
        'tool_calls[0].function.arguments.recommendation': 'string',
        'tool_calls[0].function.arguments.confidence': 'finite number in [0, 1]',
        'tool_calls[0].function.arguments.citation_excerpt': 'nonblank string',
    }
    assert output.status == 'failed' and output[0] == []
    assert 'private-value' not in json.dumps(output.validation_errors)


def test_coding_diagnostics_survive_orchestration_logs_and_ui(claim, transport, monkeypatch):
    from agents.orchestrator import run_review
    from app.main import _render_full_review_results
    lines = []
    monkeypatch.setattr('agents.run_logger._logger.info', lines.append)
    calls = [reply('report_coverage_finding', args('coverage')),
             reply('no_coding_concern', {'reason': None})]
    def post(url, **kwargs):
        return httpx.Response(200, json=calls.pop(0), request=httpx.Request('POST', url))
    transport.post.side_effect = post
    rule = Finding('test_rule', 'HIGH', 'Rule issue', 'Fix it', Citation('rules', 'RULE', '', ''), 1.0)
    with patch('agents.orchestrator.review_claim', return_value=[rule]), \
         patch('agents.coverage_validation._retrieve_policies', return_value=[POLICY]), \
         patch('agents.coding_validation._retrieve_policies', return_value=[POLICY]):
        assessment, _ = run_review(claim)
    assert assessment.review_mode == 'incomplete' and assessment.escalation_required
    assert assessment.findings[0] == rule
    assert any(f.rule == 'coverage_validation' for f in assessment.findings)
    detail = assessment.ai_details['coding_validation']
    assert detail['status'] == 'failed'
    problem = detail['validation_errors'][0]
    assert problem['path'] == 'tool_calls[0].function.arguments.reason'
    record = json.loads(lines[-1])
    assert record['success'] is False
    assert record['validation_errors'] == detail['validation_errors']
    assert 'mock-secret-do-not-export' not in ''.join(lines)
    with patch('streamlit.success') as success, patch('streamlit.warning'), \
         patch('streamlit.caption'), patch('streamlit.expander'), patch('streamlit.markdown'), \
         patch('streamlit.text') as text, patch('app.main._finding_card'), patch('streamlit.subheader'):
        _render_full_review_results(assessment, 'GROQ-TEST', '', None)
    success.assert_not_called()
    assert text.call_args.args[0] == 'tool_calls[0].function.arguments.reason: expected nonblank string; received null'
