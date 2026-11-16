# Hungarian gold-set protocol (per owner decision D1: languages are managed separately, never mixed)

**Status:** protocol and tooling ready; **data-blocked** — a Hungarian gold set requires TEV-approved
Hungarian posts and annotation, which this repository must not invent. No Hungarian production claim is
valid before this gate passes.

## Why separate

All current validation (accepted reference, gate, adapter training) is German. Languages never mix in
evaluation or training: intake carries a language tag, a run selects one language's lanes and gold standard
only (SSOT `policy.supported_languages`), and no artifact blends languages.

## Procedure (mirrors the accepted German protocol)

1. **Source.** TEV-approved Hungarian export (the same closed channel as production intake). Posts only;
   no personal data. The approved workbook is the source of truth for texts.
2. **Sample.** Stratified sample from the workbook categories, fixed seed, e.g. 50 per category. Use the
   deterministic sampler: `script/build_gold_sample.py --source <hu-workbook> --out /tmp/hu-gold --seed <seed>`.
   (The sampler's label aliases map workbook labels; extend `ALIAS` for the Hungarian workbook's labels if
   they differ from the German one.)
3. **Double annotation.** Two independent annotators label every sampled row with the TEV seven-category
   scheme (`Anti-Israel`, `Anti-Judaism`, `Holocaust Denial`, `Classical Antisemitism`,
   `Structural Antisemitism`, `Conspiracy Theories`, `Not Antisemitic`), plus an optional secondary category.
   Denial/relativization is `Holocaust Denial` and takes priority.
4. **Adjudication.** Disagreements are resolved by a third reader with a recorded decision and reason.
5. **Acceptance.** Compute inter-annotator kappa and record it. The German reference set the bar at
   kappa 0.827; the Hungarian set must be accepted by the TEV professional owner with the same recorded
   standard. Rows that cannot be adjudicated are excluded with provenance.
6. **Artifact.** `docs/evaluation/goldset_hu_<date>.jsonl` with `sample_id`, `text_sha256`, `label`,
   `secondary_label`, `workbook_label`, `provenance` — post text is **never committed**; it is regenerated
   from the workbook and seed by `script/build_gold_sample.py`.
7. **Gate.** `script/build_training_set.py --reference <hu-goldset> --pipeline-prompt ...` then
   `script/evaluate_adapter.py` and `script/measure_calibration.py` on the Hungarian held-out split — the
   same scripts as German, run against the Hungarian set only.

## Done / pending

| Step | State |
|---|---|
| Deterministic sampler | done (language-agnostic; label alias map may need Hungarian entries) |
| Training-set builder, evaluator, calibration, bakeoff | done, language-parameterized (`--language` in bakeoff) |
| Hungarian sample data | **blocked: requires TEV-approved Hungarian posts** |
| Hungarian double annotation + kappa | **blocked on data** |
| Hungarian acceptance gate | **blocked on annotation** |
