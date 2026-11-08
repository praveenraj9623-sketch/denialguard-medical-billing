"""Leakage, artifact, metric, offline UI, and audit integration checks."""
import json
from pathlib import Path
from unittest.mock import patch

import joblib
import numpy as np
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from ambulance_ml.evaluate import evaluate
from ambulance_ml.inference import load_artifacts, predict
from ambulance_ml.schema import (COMPLETE, DATA_COLUMNS, EXCLUDED_INPUTS, FEATURES, NUMERIC,
                                 SCENARIOS, feature_frame, validate_inputs)
from ambulance_ml.synthetic import SEED, generate_dataset
from ambulance_ml.train import DEFAULT_DIR, check_partitions, select_threshold, train


@pytest.fixture(autouse=True)
def no_local_credentials(monkeypatch, tmp_path):
    monkeypatch.setattr('agents.secrets._ROOT_ENV', tmp_path / '.env')
    monkeypatch.setenv('LLM_PROVIDER', 'groq')
    monkeypatch.delenv('GROQ_API_KEY', raising=False)
    monkeypatch.delenv('ANTHROPIC_API_KEY', raising=False)
    monkeypatch.setattr('streamlit.secrets', {})


@pytest.fixture(scope='module')
def data():
    return pd.read_csv(DEFAULT_DIR / 'dataset.csv')


def test_generation_reproduces_saved_dataset(data):
    pd.testing.assert_frame_equal(generate_dataset(), data, check_exact=False, atol=1e-10)
    assert not generate_dataset(seed=SEED + 2).equals(data)
    assert len(data) == 6000
    assert data.family_id.nunique() == 3000
    assert data.partition.value_counts().to_dict() == {'train': 3600, 'validation': 1200, 'test': 1200}


def test_family_and_exact_duplicate_partition_isolation(data):
    check_partitions(data)
    sets = [set(data.loc[data.partition == part, 'family_id']) for part in ('train', 'validation', 'test')]
    assert not sets[0] & sets[1] and not sets[0] & sets[2] and not sets[1] & sets[2]
    assert data.duplicated(FEATURES).sum() >= 300
    assert data.groupby(FEATURES).partition.nunique().max() == 1
    manifest = json.loads((DEFAULT_DIR / 'split_manifest.json').read_text(encoding='utf-8'))
    assert all(set(manifest[part]) == set(data.loc[data.partition == part, 'family_id']) for part in manifest)


def test_partition_check_detects_split_family(data):
    corrupted = data.copy()
    corrupted.loc[0, 'partition'] = 'test' if data.loc[1, 'partition'] != 'test' else 'train'
    with pytest.raises(ValueError, match='Related family'):
        check_partitions(corrupted)


@pytest.mark.parametrize('field', EXCLUDED_INPUTS)
def test_leakage_fields_cannot_enter_prediction(field):
    with pytest.raises(ValueError, match='exactly'):
        validate_inputs({**COMPLETE, field: 'excluded'})


def test_training_uses_only_feature_allowlist(data):
    frame = feature_frame(data)
    assert list(frame.columns) == FEATURES
    assert not set(EXCLUDED_INPUTS) & set(frame.columns)
    corrupted = data.assign(denial_reason='outcome explanation')
    with pytest.raises(ValueError, match='Dataset columns'):
        feature_frame(corrupted)
    pipeline, _ = load_artifacts()
    assert list(pipeline.feature_names_in_) == FEATURES
    assert pipeline.named_steps['preprocess'].remainder == 'drop'


def test_saved_scaler_was_fitted_only_to_training(data):
    pipeline, _ = load_artifacts()
    scaler = pipeline.named_steps['preprocess'].named_transformers_['numeric']
    expected = data.loc[data.partition == 'train', NUMERIC].mean().to_numpy()
    np.testing.assert_allclose(scaler.mean_, expected, atol=1e-12)
    assert not np.allclose(scaler.mean_, data[NUMERIC].mean().to_numpy())
    assert scaler.n_samples_seen_ == 3600


def test_validation_threshold_is_selected_without_test_labels(data):
    pipeline, metadata = load_artifacts()
    validation = data[data.partition == 'validation']
    probabilities = pipeline.predict_proba(feature_frame(validation))[:, 1]
    selected = select_threshold(validation.simulated_denial, probabilities)
    assert selected == metadata['evaluation']['logistic_regression']['test']['threshold']
    # Independently derive the F1-maximizing grid point without calling train.metrics.
    candidates = []
    y = validation.simulated_denial.to_numpy()
    for threshold in metadata['threshold_selection']['grid']:
        predicted = probabilities >= threshold
        tp = int(((y == 1) & predicted).sum())
        fp = int(((y == 0) & predicted).sum())
        fn = int(((y == 1) & ~predicted).sum())
        candidates.append((2 * tp / (2 * tp + fp + fn), threshold))
    assert selected == max(candidates)[1]


@pytest.mark.parametrize('values', list(SCENARIOS.values()))
def test_saved_model_inference_does_not_fit_or_call_ai(values):
    pipeline, metadata = load_artifacts()
    with patch.object(pipeline, 'fit', side_effect=AssertionError('Inference must not fit')), \
         patch('agents.provider.httpx.Client', side_effect=AssertionError('ML must not call Groq')):
        result = predict(dict(values), bundle=(pipeline, metadata))
    assert 0 <= result['simulated_denial_probability'] <= 1
    assert result['predicted_simulated_denial'] == (result['simulated_denial_probability'] >= result['threshold'])


@pytest.mark.parametrize('changes', [
    {'distance_miles': -1}, {'distance_miles': 251}, {'distance_miles': '12'},
    {'distance_miles': float('nan')}, {'distance_miles': True},
    {'documentation_delay_hours': float('inf')}, {'documentation_delay_hours': 169},
    {'transport_level': 'unknown'}, {'dispatch_type': 'denied'},
    {'pcs_documented': 1}, {'medical_necessity_documented': None},
])
def test_invalid_inputs_are_rejected(changes):
    with pytest.raises(ValueError):
        predict({**COMPLETE, **changes})


def test_missing_feature_rejected():
    values = dict(COMPLETE)
    del values['distance_miles']
    with pytest.raises(ValueError):
        predict(values)


def test_saved_evaluation_matches_frozen_inference_and_manual_confusion_counts():
    metadata = json.loads((DEFAULT_DIR / 'metadata.json').read_text(encoding='utf-8'))
    assert evaluate() == metadata['evaluation']
    predictions = pd.read_csv(DEFAULT_DIR / 'heldout_predictions.csv')
    for name in metadata['evaluation']:
        actual = predictions.simulated_denial.to_numpy()
        predicted = predictions[name + '_prediction'].to_numpy()
        tn = int(((actual == 0) & (predicted == 0)).sum())
        fp = int(((actual == 0) & (predicted == 1)).sum())
        fn = int(((actual == 1) & (predicted == 0)).sum())
        tp = int(((actual == 1) & (predicted == 1)).sum())
        measured = metadata['evaluation'][name]['test']
        assert measured['confusion_matrix'] == [[tn, fp], [fn, tp]]
        assert measured['denial_precision'] == pytest.approx(tp / (tp + fp))
        assert measured['denial_recall'] == pytest.approx(tp / (tp + fn))
        assert measured['denial_f1'] == pytest.approx(2 * tp / (2 * tp + fp + fn))
    # A constant-score dummy's AP must equal positive-class prevalence.
    assert metadata['evaluation']['dummy_prior']['test']['average_precision'] == pytest.approx(actual.mean())


def test_tampered_or_missing_artifact_fails_clearly(tmp_path):
    with pytest.raises(ValueError, match='Model unavailable'):
        load_artifacts(tmp_path)
    metadata = json.loads((DEFAULT_DIR / 'metadata.json').read_text(encoding='utf-8'))
    (tmp_path / 'metadata.json').write_text(json.dumps(metadata), encoding='utf-8')
    (tmp_path / 'logistic_regression.joblib').write_bytes(b'not a trusted model')
    with pytest.raises(ValueError, match='checksum'):
        load_artifacts(tmp_path)


def test_training_is_reproducible_in_separate_output_directories(tmp_path):
    first = train(tmp_path / 'first', seed=17, families=100)
    second = train(tmp_path / 'second', seed=17, families=100)
    assert first == second
    assert (tmp_path / 'first/dataset.csv').read_bytes() == (tmp_path / 'second/dataset.csv').read_bytes()


def test_app_ambulance_prediction_and_editing_without_ai_requests():
    with patch('agents.provider.httpx.Client') as client, \
         patch('ambulance_ml.train.train', side_effect=AssertionError('UI must not train')):
        at = AppTest.from_file('app/main.py', default_timeout=30).run()
        assert not at.exception
        assert any('Ambulance prediction' in tab.label for tab in at.tabs)
        assert any('Trained on synthetic data' in item.value for item in at.info)
        at.button(key='ambulance_predict').click().run()
        assert not at.exception
        assert any(m.label == 'Estimated simulated denial probability' for m in at.metric)
        first = next(m.value for m in at.metric if m.label == 'Estimated simulated denial probability')
        at.selectbox(key='ambulance_scenario').select('Scheduled transport with documentation gaps').run()
        at.number_input(key='ambulance_input_1_distance_miles').set_value(25.0)
        at.button(key='ambulance_predict').click().run()
        assert not at.exception
        second = next(m.value for m in at.metric if m.label == 'Estimated simulated denial probability')
        assert first != second
        client.assert_not_called()


def test_ml_prediction_does_not_write_human_audit_decisions(tmp_path):
    from db.audit_repository import AuditRepository
    from tests.test_audit import _make_decision
    repo = AuditRepository(tmp_path / 'ambulance_audit.db')
    repo.save_decision(_make_decision(finding_id='before-ml'))
    before = repo.get_decisions()
    predict(dict(COMPLETE))
    assert repo.get_decisions() == before
    repo.save_decision(_make_decision(finding_id='after-ml', user_decision='overridden', override_reason='Reviewed record'))
    assert len(repo.get_decisions()) == 2
    assert 'after-ml' in repo.export_decisions_csv()


def test_existing_accept_save_and_audit_export_flow_still_works(tmp_path):
    import streamlit as st
    from db.audit_repository import AuditRepository
    repo = AuditRepository(tmp_path / 'ui_audit.db')
    st.cache_resource.clear()
    with patch('db.audit_repository.AuditRepository', return_value=repo), \
         patch('agents.provider.httpx.Client') as client:
        at = AppTest.from_file('app/main.py', default_timeout=30).run()
        at.text_input(key='reviewer_name').set_value('Offline ML reviewer').run()
        at.button(key='sample_review_btn').click().run()
        assert not at.exception
        accept = next(button for button in at.button if str(button.key).startswith('accept_'))
        finding_id = accept.key[len('accept_'):]
        at.button(key=accept.key).click().run()
        at.button(key='save_' + finding_id).click().run()
        assert not at.exception
        rows = repo.get_decisions(claim_id='CLM-001')
        assert len(rows) == 1 and rows[0]['user_decision'] == 'accepted'
        assert rows[0]['reviewer_name'] == 'Offline ML reviewer'
        assert finding_id in repo.export_decisions_csv()
        at.button(key='ambulance_predict').click().run()
        assert not at.exception
        assert len(repo.get_decisions()) == 1
        client.assert_not_called()
    st.cache_resource.clear()


def test_missing_model_is_actionable_and_does_not_break_generic_review():
    with patch('app.ambulance_prediction._load_bundle', side_effect=ValueError('Missing model')):
        at = AppTest.from_file('app/main.py', default_timeout=30).run()
        assert not at.exception
        assert any('Saved ambulance model unavailable' in error.value for error in at.error)
        assert any(button.key == 'sample_review_btn' for button in at.button)
