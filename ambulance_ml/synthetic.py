"""Fixed-seed simulator. Coefficients are invented, NOT validated billing rules."""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from ambulance_ml.schema import BOOLEAN, DATA_COLUMNS

SEED = 20261109
DEFAULT_FAMILIES = 3000
GENERATOR_VERSION = 'ambulance-simulator-v1'
# Only this simulator uses these weights; no probability/latent value is a model input.
LABEL_MECHANISM = {
    'intercept': -3.6,
    'missing_document_weights': {
        'loaded_miles_recorded': 0.8, 'medical_necessity_documented': 1.6,
        'mobility_limitation_documented': 0.7, 'crew_assessment_documented': 0.7,
        'patient_signature_recorded': 0.55, 'origin_destination_recorded': 0.8,
    },
    'scheduled_missing_pcs': 1.0, 'scheduled_missing_authorization': 0.85,
    'advanced_transport': 0.35, 'distance_per_100_miles': 0.35,
    'documentation_delay_per_48_hours': 0.4, 'unobserved_family_noise_sd': 0.65,
    'outcome': 'Bernoulli(sigmoid(logit)); shared uniform draw within each family',
}


def generate_dataset(seed=SEED, families=DEFAULT_FAMILIES):
    if type(seed) is not int or seed < 0:
        raise ValueError('Seed must be a nonnegative integer.')
    if type(families) is not int or families < 100 or families % 5:
        raise ValueError('Use at least 100 families, divisible by five for exact 60/20/20 splits.')
    rng = np.random.default_rng(seed)
    order = np.random.default_rng(seed + 1).permutation(families)
    partition = {int(group): ('train' if i < families * .6 else
                             'validation' if i < families * .8 else 'test')
                 for i, group in enumerate(order)}
    rows = []
    for group in range(families):
        quality = rng.beta(5, 2)
        base = {name: bool(rng.random() < quality) for name in BOOLEAN}
        base.update(transport_level=str(rng.choice(['basic', 'advanced'], p=[.65, .35])),
                    dispatch_type=str(rng.choice(['emergency', 'scheduled'], p=[.4, .6])),
                    distance_miles=round(float(rng.uniform(.1, 180)), 6),
                    documentation_delay_hours=round(float(rng.uniform(0, 120)), 6))
        hidden_effect = rng.normal(0, LABEL_MECHANISM['unobserved_family_noise_sd'])
        outcome_draw = rng.random()
        variant = dict(base)
        # Every tenth family is an exact duplicate pair; others are related edits.
        if group % 10:
            edited = str(rng.choice(BOOLEAN))
            variant[edited] = not variant[edited]
        for index, values in enumerate((base, variant)):
            logit = LABEL_MECHANISM['intercept'] + hidden_effect
            logit += sum(weight * (not values[name]) for name, weight in
                         LABEL_MECHANISM['missing_document_weights'].items())
            if values['dispatch_type'] == 'scheduled':
                logit += LABEL_MECHANISM['scheduled_missing_pcs'] * (not values['pcs_documented'])
                logit += LABEL_MECHANISM['scheduled_missing_authorization'] * (not values['authorization_documented'])
            logit += LABEL_MECHANISM['advanced_transport'] * (values['transport_level'] == 'advanced')
            logit += LABEL_MECHANISM['distance_per_100_miles'] * values['distance_miles'] / 100
            logit += LABEL_MECHANISM['documentation_delay_per_48_hours'] * values['documentation_delay_hours'] / 48
            label = int(outcome_draw < 1 / (1 + np.exp(-logit)))
            rows.append({'family_id': f'SIM-{group:05d}', 'variant_id': index,
                         'partition': partition[group], **values, 'simulated_denial': label})
    return pd.DataFrame(rows, columns=DATA_COLUMNS)


def save_dataset(data, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data.to_csv(path, index=False, encoding='utf-8', lineterminator='\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed', type=int, default=SEED)
    parser.add_argument('--families', type=int, default=DEFAULT_FAMILIES)
    parser.add_argument('--output', type=Path, default=Path('artifacts/ambulance/dataset.csv'))
    args = parser.parse_args()
    data = generate_dataset(args.seed, args.families)
    save_dataset(data, args.output)
    print(f'Saved {len(data)} simulated claims. Partitions: {data.partition.value_counts().to_dict()}')


if __name__ == '__main__':
    main()
