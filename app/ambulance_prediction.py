"""Isolated Streamlit surface for the saved synthetic ambulance classifier."""
import pandas as pd
import streamlit as st

from ambulance_ml.inference import load_artifacts, predict
from ambulance_ml.schema import FEATURE_SCHEMA, SCENARIOS
from ambulance_ml.train import DEFAULT_DIR


@st.cache_resource
def _load_bundle(model_stamp, metadata_stamp):
    # File stamps invalidate the cache after an explicit offline training run.
    return load_artifacts(DEFAULT_DIR)


def render_ambulance_prediction():
    st.header('Ambulance prediction')
    st.info('Trained on synthetic data — predicted outcomes are simulated, not real payer decisions.')
    st.write('This saved logistic-regression model uses pre-submission claim details and documentation flags. '
             'It works locally without an API key. It is separate from rule risk labels and Groq findings.')
    st.caption('The generic claim-review rules do not provide comprehensive ambulance coverage. '
               'This demonstration does not validate ambulance HCPCS/modifier combinations, covered destinations, '
               'mileage, certification timing, signature exceptions, or payer-specific authorization requirements.')
    scenario = st.selectbox('Synthetic example scenario', list(SCENARIOS), key='ambulance_scenario')
    defaults = SCENARIOS[scenario]
    scenario_index = list(SCENARIOS).index(scenario)
    with st.form('ambulance_inputs'):
        values = {}
        left, right = st.columns(2)
        for index, (name, spec) in enumerate(FEATURE_SCHEMA.items()):
            with (left if index % 2 == 0 else right):
                key = f'ambulance_input_{scenario_index}_{name}'
                if spec['type'] == 'boolean':
                    values[name] = st.checkbox(spec['label'], value=defaults[name], key=key, help=spec['help'])
                elif spec['type'] == 'category':
                    values[name] = st.selectbox(spec['label'], spec['choices'],
                        index=spec['choices'].index(defaults[name]), key=key, help=spec['help'])
                else:
                    values[name] = st.number_input(spec['label'], min_value=spec['minimum'], max_value=spec['maximum'],
                        value=defaults[name], step=0.1, key=key, help=spec['help'])
        submitted = st.form_submit_button('Predict simulated denial', key='ambulance_predict')
    try:
        bundle = _load_bundle((DEFAULT_DIR / 'logistic_regression.joblib').stat().st_mtime_ns,
                              (DEFAULT_DIR / 'metadata.json').stat().st_mtime_ns)
    except (ValueError, OSError, ImportError) as exc:
        st.error('Saved ambulance model unavailable or incompatible. Run the offline training command; review remains available in the other tabs.')
        st.code('.\\.venv\\Scripts\\python.exe -m ambulance_ml.train', language='powershell')
        return
    _, metadata = bundle
    if submitted:
        try:
            result = predict(values, bundle=bundle)
            st.metric('Estimated simulated denial probability', f"{result['simulated_denial_probability']:.1%}")
            label = 'Simulated denial predicted' if result['predicted_simulated_denial'] else 'Simulated non-denial predicted'
            st.write(f"**{label}** at validation-selected threshold {result['threshold']:.2f}.")
            st.caption('This is a fitted-model estimate within an invented simulator. It is not calibrated to real claims '
                       'and does not approve or reject a claim. Human review is required.')
        except ValueError as exc:
            st.error(f'Invalid ambulance inputs: {exc}')
    st.subheader('Held-out synthetic evaluation')
    st.caption(f"Seed {metadata['seed']} · {metadata['dataset_rows']:,} simulated rows · "
               '60% training / 20% validation / 20% test, isolated by scenario family. '
               'Both models were fitted on training only; thresholds maximize validation denial-class F1.')
    records = []
    for model, display in [('dummy_prior', 'Dummy prior baseline'), ('logistic_regression', 'Logistic regression')]:
        metrics = metadata['evaluation'][model]['test']
        records.append({'Model': display, **{key: metrics[key] for key in (
            'threshold', 'denial_precision', 'denial_recall', 'denial_f1', 'average_precision')}})
    st.dataframe(pd.DataFrame(records).set_index('Model').round(4))
    st.caption('Average precision (AP / non-interpolated PR summary) = sum of precision weighted by increases in recall. '
               'It is not trapezoidal PR-AUC. The tuned dummy baseline predicts every test row as denied; '
               'its recall is 1 and its AP equals test denial prevalence.')
    with st.expander('Class counts and confusion matrices'):
        st.table(pd.DataFrame({part: counts['class_counts'] for part, counts in metadata['partitions'].items()}).T)
        for model, display in [('dummy_prior', 'Dummy prior baseline'), ('logistic_regression', 'Logistic regression')]:
            st.write(display)
            st.table(pd.DataFrame(metadata['evaluation'][model]['test']['confusion_matrix'],
                index=['Actual non-denial', 'Actual denial'], columns=['Predicted non-denial', 'Predicted denial']))
    st.subheader('Limitations')
    for limitation in metadata['limitations']:
        st.write('• ' + limitation)
