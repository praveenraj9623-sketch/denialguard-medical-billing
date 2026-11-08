"""CPU training with family-isolated partitions and validation-only thresholds."""
import argparse
import hashlib
import importlib.metadata
import json
import platform
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, confusion_matrix, precision_recall_fscore_support
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from ambulance_ml.schema import (BOOLEAN, CATEGORICAL, EXCLUDED_INPUTS, FEATURES,
                                 FEATURE_SCHEMA, NUMERIC, SCHEMA_VERSION, feature_frame)
from ambulance_ml.synthetic import (DEFAULT_FAMILIES, GENERATOR_VERSION, LABEL_MECHANISM,
                                    SEED, generate_dataset, save_dataset)

DEFAULT_DIR = Path(__file__).resolve().parent.parent / 'artifacts' / 'ambulance'
THRESHOLDS = np.round(np.arange(.05, .951, .01), 2)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check_partitions(data):
    feature_frame(data)
    if set(data.partition) != {'train', 'validation', 'test'}:
        raise ValueError('Expected training, validation and test partitions.')
    if data.groupby('family_id').partition.nunique().max() != 1:
        raise ValueError('Related family variants cross partitions.')
    if data.groupby(FEATURES, dropna=False).partition.nunique().max() != 1:
        raise ValueError('Duplicate input profiles cross partitions.')
    for part in ('train', 'validation', 'test'):
        if set(data.loc[data.partition == part, 'simulated_denial']) != {0, 1}:
            raise ValueError('Each partition must contain both outcome classes.')


def build_pipeline(estimator):
    preprocessing = ColumnTransformer([
        ('numeric', StandardScaler(), NUMERIC),
        ('category', OneHotEncoder(handle_unknown='ignore', sparse_output=False), CATEGORICAL),
        ('documentation', 'passthrough', BOOLEAN),
    ], remainder='drop')
    return Pipeline([('preprocess', preprocessing), ('classifier', estimator)])


def metrics(labels, probabilities, threshold):
    predictions = (np.asarray(probabilities) >= threshold).astype(int)
    precision, recall, f1, _ = precision_recall_fscore_support(
        labels, predictions, average='binary', pos_label=1, zero_division=0)
    return {'threshold': float(threshold), 'denial_precision': float(precision),
            'denial_recall': float(recall), 'denial_f1': float(f1),
            'average_precision': float(average_precision_score(labels, probabilities)),
            'confusion_matrix': confusion_matrix(labels, predictions, labels=[0, 1]).tolist(),
            'class_counts': {'not_denied': int(np.sum(np.asarray(labels) == 0)),
                             'denied': int(np.sum(np.asarray(labels) == 1))}}


def select_threshold(validation_labels, validation_probabilities):
    # Fixed grid; highest threshold wins exact F1 ties. No test information used.
    return float(max(reversed(THRESHOLDS), key=lambda t:
        metrics(validation_labels, validation_probabilities, t)['denial_f1']))


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def train(output_dir=DEFAULT_DIR, seed=SEED, families=DEFAULT_FAMILIES):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    data = generate_dataset(seed=seed, families=families)
    check_partitions(data)
    dataset_file = output_dir / 'dataset.csv'
    save_dataset(data, dataset_file)
    x = feature_frame(data)
    masks = {part: data.partition == part for part in ('train', 'validation', 'test')}
    y = data.simulated_denial
    estimators = {'dummy_prior': DummyClassifier(strategy='prior'),
                  'logistic_regression': LogisticRegression(C=1.0, max_iter=1000,
                                                           solver='lbfgs', random_state=seed)}
    results, files = {}, {}
    heldout = data.loc[masks['test'], ['family_id', 'variant_id', 'simulated_denial']].copy()
    for name, estimator in estimators.items():
        pipeline = build_pipeline(estimator)
        pipeline.fit(x.loc[masks['train']], y.loc[masks['train']])
        val_probs = pipeline.predict_proba(x.loc[masks['validation']])[:, 1]
        threshold = select_threshold(y.loc[masks['validation']], val_probs)
        # Frozen training pipeline + validation-selected threshold. No refitting.
        test_probs = pipeline.predict_proba(x.loc[masks['test']])[:, 1]
        results[name] = {'validation': metrics(y.loc[masks['validation']], val_probs, threshold),
                         'test': metrics(y.loc[masks['test']], test_probs, threshold)}
        filename = name + '.joblib'
        joblib.dump(pipeline, output_dir / filename, compress=3)
        files[name] = {'filename': filename, 'sha256': sha256(output_dir / filename)}
        heldout[name + '_probability'] = test_probs
        heldout[name + '_prediction'] = (test_probs >= threshold).astype(int)
    heldout.to_csv(output_dir / 'heldout_predictions.csv', index=False, encoding='utf-8', lineterminator='\n')
    partitions = {}
    for part, mask in masks.items():
        labels = y.loc[mask]
        partitions[part] = {'rows': int(mask.sum()), 'families': int(data.loc[mask, 'family_id'].nunique()),
                            'class_counts': {'not_denied': int((labels == 0).sum()), 'denied': int((labels == 1).sum())}}
    metadata = {
        'schema_version': SCHEMA_VERSION, 'generator_version': GENERATOR_VERSION,
        'trained_on': 'synthetic data only; simulated outcomes, not payer decisions',
        'seed': seed, 'dataset_rows': len(data), 'families': families,
        'dataset_sha256': sha256(dataset_file), 'feature_names': FEATURES,
        'feature_schema': FEATURE_SCHEMA, 'excluded_inputs': EXCLUDED_INPUTS,
        'label_mechanism': LABEL_MECHANISM, 'partitions': partitions,
        'partition_method': 'seed+1 shuffled families; 60/20/20; variants stay together',
        'threshold_selection': {'partition': 'validation', 'objective': 'maximum denial-class F1',
                                'tie_break': 'highest threshold', 'grid': THRESHOLDS.tolist()},
        'preprocessing_fit_partition': 'train only',
        'model_parameters': {'dummy_prior': {'strategy': 'prior'},
                             'logistic_regression': {'C': 1.0, 'solver': 'lbfgs', 'max_iter': 1000, 'random_state': seed}},
        'versions': {'python': platform.python_version(), **{name: importlib.metadata.version(name)
                     for name in ('scikit-learn', 'numpy', 'pandas', 'scipy', 'joblib', 'threadpoolctl')}},
        'positive_class': '1 = simulated denial',
        'average_precision_definition': 'AP = sum((R_n - R_(n-1)) * P_n); non-interpolated sklearn average_precision_score, not trapezoidal PR area',
        'confusion_matrix_order': 'rows=actual [not denied, denied]; columns=predicted [not denied, denied]; [[TN, FP], [FN, TP]]',
        'model_files': files, 'evaluation': results,
        'limitations': [
            'Learns invented simulator assumptions; no real payer decisions or validated billing rules.',
            'Same-simulator held-out evaluation is not real-world denial accuracy or probability calibration.',
            'Documentation flags are self-reported; clinical text and policy requirements are not validated.',
            'No payer-specific coverage, HCPCS/modifier, destination eligibility, mileage audit or signature-exception checks.',
            'Threshold maximizes simulated validation F1; no clinical/billing cost justification.',
        ],
    }
    write_json(output_dir / 'metadata.json', metadata)
    write_json(output_dir / 'split_manifest.json', {
        part: sorted(data.loc[mask, 'family_id'].unique().tolist()) for part, mask in masks.items()})
    write_json(output_dir / 'evaluation.json', results)
    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed', type=int, default=SEED)
    parser.add_argument('--families', type=int, default=DEFAULT_FAMILIES)
    parser.add_argument('--output-dir', type=Path, default=DEFAULT_DIR)
    args = parser.parse_args()
    metadata = train(args.output_dir, args.seed, args.families)
    print(json.dumps({'partitions': metadata['partitions'], 'evaluation': metadata['evaluation']}, indent=2))


if __name__ == '__main__':
    main()
