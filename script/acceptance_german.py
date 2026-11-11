#!/usr/bin/env python3
"""Prepare a reproducible labelled German sample, then score an actual run output."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from openpyxl import Workbook, load_workbook
from src.classifier import normalize_label
from src.failure_policy import ANALYSIS_FAILURE_FLAGS
from src.models import CANONICAL_CATEGORIES


def prepare(source: Path, destination: Path, per_category: int, seed: int) -> Path:
    destination.mkdir(parents=True, exist_ok=False, mode=0o700)
    rng = random.Random(seed)
    selected = {category: [] for category in sorted(CANONICAL_CATEGORIES)}
    eligible = Counter()
    skipped = Counter()
    seen = set()
    workbook = load_workbook(source, read_only=True, data_only=True)
    try:
        for source_row, row in enumerate(workbook.worksheets[0].iter_rows(min_row=2, values_only=True), 2):
            item, text, label = [str(v or '').strip() for v in row[:3]]
            if not any((item, text, label)):
                continue
            category = normalize_label(label)
            if not text or category not in CANONICAL_CATEGORIES:
                skipped['empty_text_or_unlabelled'] += 1
                continue
            digest = hashlib.sha256(text.encode()).hexdigest()
            if digest in seen:
                skipped['duplicate_text'] += 1
                continue
            seen.add(digest)
            eligible[category] += 1
            entry = {'source_row': source_row, 'item_number': item, 'post_text': text, 'source_label': label, 'expected_category': category, 'post_text_sha256': digest}
            bucket = selected[category]
            if len(bucket) < per_category:
                bucket.append(entry)
            else:
                index = rng.randrange(eligible[category])
                if index < per_category:
                    bucket[index] = entry
    finally:
        workbook.close()
    if any(len(bucket) < per_category for bucket in selected.values()):
        raise RuntimeError('Insufficient labelled rows for a balanced sample')
    entries = [entry for bucket in selected.values() for entry in bucket]
    rng.shuffle(entries)
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(['Item number', 'Post text', 'Category'])
    expected = []
    for index, entry in enumerate(entries, 2):
        # Hide reference labels from inference; preserve provenance separately.
        sheet.append([entry['item_number'], entry['post_text'], ''])
        expected.append({key: value for key, value in entry.items() if key != 'post_text'} | {'row_index': index})
    output = destination / f'german-acceptance-balanced-{len(entries)}.xlsx'
    workbook.save(output)
    workbook.close()
    payload = {'source': str(source.resolve()), 'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(), 'sample_sha256': hashlib.sha256(output.read_bytes()).hexdigest(), 'seed': seed, 'per_category': per_category, 'sample_rows': len(entries), 'eligible_unique_source_rows': dict(eligible), 'excluded_source_rows': dict(skipped), 'reference': 'Existing workbook labels normalized to the closed taxonomy; not an independently adjudicated gold set.', 'rows': expected}
    (destination / 'sample_manifest.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    return output


def score(manifest_path: Path, output: Path) -> dict:
    manifest = json.loads(manifest_path.read_text())
    workbook = load_workbook(output, read_only=True, data_only=True)
    iterator = workbook.worksheets[0].iter_rows(values_only=True)
    header = next(iterator)
    actual = {index: dict(zip(header, row)) for index, row in enumerate(iterator, 2)}
    workbook.close()
    matrix = {c: Counter() for c in sorted(CANONICAL_CATEGORIES)}
    details = []
    correct = 0
    failed = 0
    missing = 0
    for reference in manifest['rows']:
        row = actual.get(reference['row_index'], {})
        flags = set(str(row.get('Flags') or '').split(';'))
        prediction = str(row.get('Assigned Category') or '')
        outcome = 'FAILED_ANALYSIS' if flags & ANALYSIS_FAILURE_FLAGS else prediction
        if not prediction:
            outcome = 'MISSING_OUTPUT'
            missing += 1
        failed += outcome == 'FAILED_ANALYSIS'
        matches = outcome == reference['expected_category']
        correct += matches
        matrix[reference['expected_category']][outcome] += 1
        details.append({'row_index': reference['row_index'], 'source_row': reference['source_row'], 'expected': reference['expected_category'], 'predicted': prediction, 'outcome': outcome, 'matches_reference': matches, 'flags': sorted(flag for flag in flags if flag)})
    total = len(manifest['rows'])
    per_category = {}
    for category in sorted(CANONICAL_CATEGORIES):
        true_positive = matrix[category].get(category, 0)
        support = sum(matrix[category].values())
        predicted_count = sum(counts.get(category, 0) for counts in matrix.values())
        denominator = support + predicted_count
        per_category[category] = {'support': support, 'correct': true_positive, 'precision': round(true_positive / predicted_count, 4) if predicted_count else None, 'recall': round(true_positive / support, 4) if support else None, 'f1': round(2 * true_positive / denominator, 4) if denominator else 0}
    return {'sample_rows': total, 'matches_reference': correct, 'reference_agreement_percent': round(100 * correct / total, 2), 'failed_analysis_rows': failed, 'missing_output_rows': missing, 'per_category': per_category, 'macro_f1': round(sum(m['f1'] for m in per_category.values()) / len(per_category), 4), 'confusion_matrix': {k: dict(v) for k, v in matrix.items()}, 'rows': details, 'limitations': ['Small balanced sample; results do not estimate natural prevalence.', 'Existing source labels require designated reviewer adjudication.', 'A failure placeholder is never scored as a correct negative.']}


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest='command', required=True)
    prep = commands.add_parser('prepare')
    prep.add_argument('--source', type=Path, default=ROOT / 'samples/sample_germany.xlsx')
    prep.add_argument('--destination', type=Path, required=True)
    prep.add_argument('--per-category', type=int, default=5)
    prep.add_argument('--seed', type=int, default=20261108)
    scoring = commands.add_parser('score')
    scoring.add_argument('--manifest', type=Path, required=True)
    scoring.add_argument('--output', type=Path, required=True)
    scoring.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'prepare':
        path = prepare(args.source, args.destination, args.per_category, args.seed)
        print(json.dumps({'workbook': str(path), 'sample_rows': args.per_category * 6, 'seed': args.seed}))
    else:
        report = score(args.manifest, args.output)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2))
        print(json.dumps({k: v for k, v in report.items() if k not in {'rows', 'confusion_matrix'}}))


if __name__ == '__main__':
    main()
