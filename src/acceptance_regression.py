from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from openpyxl import Workbook

spec = importlib.util.spec_from_file_location('acceptance_german', Path(__file__).resolve().parents[1] / 'script/acceptance_german.py')
acceptance = importlib.util.module_from_spec(spec)
spec.loader.exec_module(acceptance)


class AcceptanceScoringRegressionTests(unittest.TestCase):
    def test_apl_four_field_intake_maps_by_header_alias(self):
        """The APL structure (ID, text, keywords, link) imports as a good format - adapt, never refuse."""
        import tempfile
        from openpyxl import Workbook

        from src.excel_io import read_input_rows
        from src.ssot_loader import load_ssot

        ssot = load_ssot(Path(__file__).resolve().parents[1] / "ssot" / "ssot.json")
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "apl.xlsx"
            wb = Workbook()
            ws = wb.active
            ws.append(["ID", "A poszt szovege", "Oda tartozo kulcsszavak", "A poszt linkje"])
            ws.append(["apl-1", "A globalistak iranyitjak a valsagokat.", "globalistak, hatterhatalom",
                       "https://platform.example/apl-1"])
            wb.save(path)
            rows = read_input_rows(path, ssot)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].item_number, "apl-1")
            self.assertEqual(rows[0].post_text, "A globalistak iranyitjak a valsagokat.")
            self.assertEqual(rows[0].keywords, "globalistak, hatterhatalom")
            self.assertEqual(rows[0].source_link, "https://platform.example/apl-1")

    def test_failed_negative_placeholder_is_not_a_correct_prediction(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / 'manifest.json'
            manifest.write_text(json.dumps({'rows': [
                {'row_index': 2, 'source_row': 10, 'expected_category': 'Not Antisemitic'},
                {'row_index': 3, 'source_row': 11, 'expected_category': 'Anti-Israel'},
                {'row_index': 4, 'source_row': 12, 'expected_category': 'Not Antisemitic'},
            ]}))
            workbook = Workbook()
            workbook.active.append(['Assigned Category', 'Flags'])
            workbook.active.append(['Not Antisemitic', 'ANALYSIS_FAILED;REVIEW_REQUIRED'])
            workbook.active.append(['Anti-Israel', 'REVIEW_REQUIRED'])
            output = root / 'output.xlsx'
            workbook.save(output)
            workbook.close()
            report = acceptance.score(manifest, output)
            self.assertEqual(report['matches_reference'], 1)
            self.assertEqual(report['failed_analysis_rows'], 1)
            self.assertEqual(report['missing_output_rows'], 1)
            self.assertEqual(report['reference_agreement_percent'], 33.33)
            self.assertEqual(report['confusion_matrix']['Not Antisemitic'], {'FAILED_ANALYSIS': 1, 'MISSING_OUTPUT': 1})


if __name__ == '__main__':
    unittest.main()
