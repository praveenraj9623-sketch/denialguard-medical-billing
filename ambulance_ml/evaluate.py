"""Evaluate frozen saved pipelines; no fit, threshold selection, API or network calls."""
import argparse
import json
from pathlib import Path

import joblib
import pandas as pd

from ambulance_ml.inference import load_artifacts
from ambulance_ml.schema import feature_frame
from ambulance_ml.train import DEFAULT_DIR, check_partitions, metrics, sha256


def evaluate(directory=DEFAULT_DIR):
    directory = Path(directory)
    _, metadata = load_artifacts(directory)
    dataset = directory / 'dataset.csv'
    if sha256(dataset) != metadata['dataset_sha256']:
        raise ValueError('Dataset checksum differs from the training snapshot.')
    data = pd.read_csv(dataset)
    check_partitions(data)
    x = feature_frame(data)
    results = {}
    for name, info in metadata['model_files'].items():
        path = directory / info['filename']
        if sha256(path) != info['sha256']:
            raise ValueError('Saved pipeline checksum mismatch.')
        pipeline = joblib.load(path)
        threshold = metadata['evaluation'][name]['validation']['threshold']
        results[name] = {}
        for part in ('validation', 'test'):
            mask = data.partition == part
            results[name][part] = metrics(data.loc[mask, 'simulated_denial'],
                                          pipeline.predict_proba(x.loc[mask])[:, 1], threshold)
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifact-dir', type=Path, default=DEFAULT_DIR)
    args = parser.parse_args()
    print(json.dumps(evaluate(args.artifact_dir), indent=2))


if __name__ == '__main__':
    main()
