# Synthetic claim-review examples

These inherited fictional examples support claim review and its golden-set evaluation. They contain no intended real patient records and are not a record of actual payer decisions.

This review dataset is **not** the 6,000-row ambulance classification experiment. The classifier's generated data, partitions, saved pipelines and measured results are under [artifacts/ambulance](../../artifacts/ambulance), with methodology in the [model card](../../docs/ambulance-model-card.md).

Use the actual fixture files and evaluation loader as the schema source; do not infer that every file is a CSV header or that identifiers represent verified providers. Review finding precision/recall, classifier F1 and upstream historical benchmarks are different evaluations.

For app setup and accurately labelled current results, see the [project README](../../README.md). Add only fictional examples, keep expected findings explicit, and do not tune against the published held-out classifier outcomes.
