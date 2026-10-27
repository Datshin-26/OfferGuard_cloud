import csv
import tempfile
import unittest
from pathlib import Path

from server import analyze_offer, read_verifications, save_verification


class OfferAnalysisTests(unittest.TestCase):
    def test_suspicious_offer_gets_expected_score(self):
        record = analyze_offer({
            "company": "Acme Careers",
            "website": "http://acme.example",
            "email": "recruiter@gmail.com",
            "fee": "yes",
            "message": "Limited seats! Pay now; guaranteed job; registration fee.",
        })
        self.assertEqual(record["score"], 90)
        self.assertEqual(record["risk"], "🔴 High Risk")
        self.assertEqual(len(record["reasons"]), 4)

    def test_secure_offer_with_company_email_scores_zero(self):
        record = analyze_offer({
            "company": "Example Co",
            "website": "https://example.com/jobs",
            "email": "recruiter@example.com",
            "fee": "no",
            "message": "Please review the internship responsibilities.",
        })
        self.assertEqual(record["score"], 0)
        self.assertEqual(record["risk"], "🟢 Low Risk")

    def test_invalid_website_is_rejected(self):
        offer = {
            "company": "Example Co",
            "website": "javascript:alert(1)",
            "email": "",
            "fee": "no",
            "message": "Internship details",
        }
        with self.assertRaisesRegex(ValueError, "website URL"):
            analyze_offer(offer)


class CsvPersistenceTests(unittest.TestCase):
    def test_record_is_saved_and_read_back_from_csv(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            csv_path = Path(temporary_directory) / "data" / "checks.csv"
            record = analyze_offer({
                "company": "Example Co",
                "website": "",
                "email": "",
                "fee": "no",
                "message": "Internship details",
            })

            save_verification(record, csv_path)
            history = read_verifications(csv_path)

            self.assertEqual(len(history), 1)
            self.assertEqual(history[0]["company"], "Example Co")
            self.assertEqual(history[0]["score"], record["score"])
            with csv_path.open(encoding="utf-8", newline="") as csv_file:
                rows = list(csv.DictReader(csv_file))
            self.assertEqual(rows[0]["message"], "Internship details")

    def test_formula_like_text_is_stored_as_a_literal_csv_cell(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            csv_path = Path(temporary_directory) / "checks.csv"
            record = analyze_offer({
                "company": "=1+1",
                "website": "",
                "email": "",
                "fee": "no",
                "message": "@SUM(A1:A2)",
            })

            save_verification(record, csv_path)

            with csv_path.open(encoding="utf-8", newline="") as csv_file:
                row = next(csv.DictReader(csv_file))
            self.assertEqual(row["company"], "'=1+1")
            self.assertEqual(row["message"], "'@SUM(A1:A2)")


if __name__ == "__main__":
    unittest.main()
