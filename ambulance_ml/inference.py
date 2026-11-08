"""Local saved-model inference; never trains or calls an external service."""
import json
from pathlib import Path

import joblib
import pandas as pd
import sklearn

from ambulance_ml.schema import FEATURES, FEATURE_SCHEMA, SCHEMA_VERSION, validate_inputs
from ambulance_ml.train import DEFAULT_DIR, sha256


def load_artifacts(directory=DEFAULT_DIR):
    directory = Path(directory)
    try:
        metadata = json.loads((directory / 'metadata.json').read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise ValueError('Model unavailable. Run python -m ambulance_ml.train locally first.') from exc
    if (metadata.get('schema_version') != SCHEMA_VERSION or metadata.get('feature_names') != FEATURES
            or metadata.get('feature_schema') != FEATURE_SCHEMA):
        raise ValueError('Model feature schema differs from this app. Regenerate the local artifacts.')
    if metadata['versions']['scikit-learn'] != sklearn.__version__:
        raise ValueError('Installed scikit-learn differs from the saved model. Install pinned requirements or retrain.')
    filename = directory / 'logistic_regression.joblib'
    if not filename.exists() or sha256(filename) != metadata['model_files']['logistic_regression']['sha256']:
        raise ValueError('Saved model is missing or its checksum does not match metadata. Retrain locally.')
    # Load only trusted repository-generated files, never an uploaded/downloaded pickle.
    pipeline = joblib.load(filename)
    if list(pipeline.feature_names_in_) != FEATURES:
        raise ValueError('Saved pipeline input schema mismatch.')
    return pipeline, metadata


def predict(values, bundle=None):
    values = validate_inputs(values)
    pipeline, metadata = load_artifacts() if bundle is None else bundle
    probability = float(pipeline.predict_proba(pd.DataFrame([values], columns=FEATURES))[0, 1])
    threshold = metadata['evaluation']['logistic_regression']['validation']['threshold']
    return {'simulated_denial_probability': probability, 'threshold': threshold,
            'predicted_simulated_denial': probability >= threshold}
