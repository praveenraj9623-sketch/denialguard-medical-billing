"""Strict pre-submission input allowlist shared by generation, training and UI."""
import math
from numbers import Real

import pandas as pd

SCHEMA_VERSION = 1
FEATURE_SCHEMA = {
    'transport_level': {'type': 'category', 'choices': ['basic', 'advanced'],
                        'label': 'Transport level', 'help': 'Synthetic basic or advanced service category; no HCPCS validation.'},
    'dispatch_type': {'type': 'category', 'choices': ['emergency', 'scheduled'],
                      'label': 'Dispatch type', 'help': 'Whether dispatch was emergency or scheduled.'},
    'distance_miles': {'type': 'number', 'minimum': 0.1, 'maximum': 250.0,
                       'label': 'Loaded distance (miles)', 'help': 'Distance travelled with the patient, before claim submission.'},
    'documentation_delay_hours': {'type': 'number', 'minimum': 0.0, 'maximum': 168.0,
                                  'label': 'Documentation delay (hours)', 'help': 'Hours from transport to completion of the current record; an invented simulator input.'},
    'loaded_miles_recorded': {'type': 'boolean', 'label': 'Loaded mileage recorded', 'help': 'The record includes loaded mileage.'},
    'medical_necessity_documented': {'type': 'boolean', 'label': 'Medical necessity documented', 'help': 'The author marked the need for ambulance transport as documented; this app does not assess the text.'},
    'mobility_limitation_documented': {'type': 'boolean', 'label': 'Mobility limitation documented', 'help': 'The author marked a mobility limitation as documented; not an eligibility determination.'},
    'crew_assessment_documented': {'type': 'boolean', 'label': 'Crew assessment documented', 'help': 'A crew assessment is available before submission.'},
    'patient_signature_recorded': {'type': 'boolean', 'label': 'Signature recorded', 'help': 'A signature is recorded; exception eligibility is not checked.'},
    'origin_destination_recorded': {'type': 'boolean', 'label': 'Origin and destination recorded', 'help': 'Transport endpoints are documented; covered destinations are not validated.'},
    'pcs_documented': {'type': 'boolean', 'label': 'Certification statement documented', 'help': 'A physician certification statement is present; actual requirements and timing are not checked.'},
    'authorization_documented': {'type': 'boolean', 'label': 'Authorization documentation present', 'help': 'Authorization paperwork is on file before submission; payer-specific applicability is not checked.'},
}
FEATURES = list(FEATURE_SCHEMA)
NUMERIC = [k for k, v in FEATURE_SCHEMA.items() if v['type'] == 'number']
CATEGORICAL = [k for k, v in FEATURE_SCHEMA.items() if v['type'] == 'category']
BOOLEAN = [k for k, v in FEATURE_SCHEMA.items() if v['type'] == 'boolean']
# These columns exist only for grouping, provenance, splitting and the training target.
DATA_COLUMNS = ['family_id', 'variant_id', 'partition', *FEATURES, 'simulated_denial']
EXCLUDED_INPUTS = ['claim_id', 'family_id', 'variant_id', 'partition', 'simulated_denial',
                   'denial_reason', 'adjudication_status', 'payment_amount', 'payment_outcome',
                   'risk_score', 'ai_findings']


def validate_inputs(values):
    if not isinstance(values, dict):
        raise ValueError('Inputs must be a feature dictionary.')
    if set(values) != set(FEATURES):
        raise ValueError('Provide exactly the documented pre-submission features; identifiers and outcome fields are not allowed.')
    validated = {}
    for name, spec in FEATURE_SCHEMA.items():
        value = values[name]
        if spec['type'] == 'boolean':
            if type(value) is not bool:
                raise ValueError(f'{name}: expected a true/false value.')
        elif spec['type'] == 'category':
            if not isinstance(value, str) or value not in spec['choices']:
                raise ValueError(f'{name}: choose one of the documented categories.')
        else:
            if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value):
                raise ValueError(f'{name}: expected a finite number.')
            if not spec['minimum'] <= value <= spec['maximum']:
                raise ValueError(f'{name}: expected {spec["minimum"]} to {spec["maximum"]}.')
            value = float(value)
        validated[name] = value
    return validated


def feature_frame(data):
    """Fail closed on unexpected training columns, then select the explicit allowlist."""
    if set(data.columns) != set(DATA_COLUMNS):
        raise ValueError('Dataset columns differ from the synthetic dataset contract.')
    # Validate rather than coerce strings, outcomes, missingness or categories silently.
    rows = [validate_inputs(row) for row in data[FEATURES].to_dict('records')]
    return pd.DataFrame(rows, columns=FEATURES)


COMPLETE = {**{name: True for name in BOOLEAN}, 'transport_level': 'basic',
            'dispatch_type': 'scheduled', 'distance_miles': 12.0, 'documentation_delay_hours': 2.0}
SCENARIOS = {
    'Scheduled transport with complete documentation': COMPLETE,
    'Scheduled transport with documentation gaps': {**COMPLETE,
        'medical_necessity_documented': False, 'mobility_limitation_documented': False,
        'pcs_documented': False, 'authorization_documented': False, 'documentation_delay_hours': 60.0},
    'Emergency advanced transport': {**COMPLETE, 'transport_level': 'advanced',
        'dispatch_type': 'emergency', 'distance_miles': 8.0, 'pcs_documented': False,
        'authorization_documented': False},
}
