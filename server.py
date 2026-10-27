import csv
import json
import re
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit


APP_DIR = Path(__file__).resolve().parent
CSV_FILE = APP_DIR / "data" / "verifications.csv"
MAX_REQUEST_BYTES = 16_384
CSV_FIELDS = [
    "date",
    "company",
    "website",
    "email",
    "fee",
    "message",
    "score",
    "risk",
    "reasons",
]
FREE_EMAIL_DOMAINS = {"gmail.com", "yahoo.com", "outlook.com", "hotmail.com"}
SUSPICIOUS_PHRASES = (
    "pay now",
    "limited seats",
    "urgent payment",
    "guaranteed job",
    "registration fee",
    "send money",
    "today last date",
)
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
CSV_FORMULA_PREFIXES = ("=", "+", "-", "@")


def _csv_safe(value):
    text = str(value)
    if text.lstrip().startswith(CSV_FORMULA_PREFIXES):
        return "'" + text
    return text


def analyze_offer(offer):
    if not isinstance(offer, dict):
        raise ValueError("The request body must be a JSON object.")

    company = offer.get("company")
    website = offer.get("website", "")
    email = offer.get("email", "")
    message = offer.get("message")
    fee = offer.get("fee")

    if not isinstance(company, str) or not company.strip():
        raise ValueError("Enter a company name.")
    if len(company) > 200:
        raise ValueError("Company name must be 200 characters or fewer.")
    if not isinstance(message, str) or not message.strip():
        raise ValueError("Enter the internship offer message.")
    if len(message) > 5000:
        raise ValueError("Offer message must be 5,000 characters or fewer.")
    if not isinstance(website, str) or len(website) > 320:
        raise ValueError("Website must be 320 characters or fewer.")
    if not isinstance(email, str) or len(email) > 320:
        raise ValueError("Email must be 320 characters or fewer.")
    if fee not in ("yes", "no"):
        raise ValueError("Choose whether the offer requests a registration fee.")

    company = company.strip()
    website = website.strip()
    email = email.strip()
    message = message.strip()

    score = 0
    reasons = []

    if fee == "yes":
        score += 35
        reasons.append("⚠️ Registration fee requested.")

    if not website:
        score += 15
        reasons.append("⚠️ Company website not provided.")
    else:
        try:
            parsed_url = urlsplit(website)
        except ValueError as error:
            raise ValueError("Enter a valid company website URL.") from error
        if parsed_url.scheme not in ("http", "https") or not parsed_url.netloc:
            raise ValueError("Enter a valid company website URL using HTTP or HTTPS.")
        if parsed_url.scheme != "https":
            score += 10
            reasons.append("⚠️ Website does not use HTTPS.")

    if not email:
        score += 10
        reasons.append("⚠️ Recruiter email not provided.")
    elif not EMAIL_PATTERN.fullmatch(email):
        raise ValueError("Enter a valid recruiter email address.")
    elif email.rsplit("@", 1)[1].lower() in FREE_EMAIL_DOMAINS:
        score += 15
        reasons.append("⚠️ Recruiter uses a free email service.")

    detected_phrases = [
        phrase for phrase in SUSPICIOUS_PHRASES if phrase in message.lower()
    ]
    if detected_phrases:
        score += min(len(detected_phrases) * 10, 30)
        reasons.append("⚠️ Suspicious phrases: " + ", ".join(detected_phrases))

    score = min(score, 100)
    if score >= 60:
        risk = "🔴 High Risk"
    elif score >= 30:
        risk = "🟠 Medium Risk"
    else:
        risk = "🟢 Low Risk"

    return {
        "date": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "company": company,
        "website": website,
        "email": email,
        "fee": fee,
        "message": message,
        "score": score,
        "risk": risk,
        "reasons": reasons,
    }


def save_verification(record, csv_path=CSV_FILE):
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not csv_path.exists() or csv_path.stat().st_size == 0
    with csv_path.open("a", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=CSV_FIELDS)
        if write_header:
            writer.writeheader()
        writer.writerow({
            field: _csv_safe(
                "; ".join(record[field])
                if field == "reasons"
                else record[field]
            )
            for field in CSV_FIELDS
        })


def read_verifications(csv_path=CSV_FILE):
    if not csv_path.exists():
        return []
    with csv_path.open("r", encoding="utf-8", newline="") as csv_file:
        return [
            {
                "date": row["date"],
                "company": row["company"],
                "score": int(row["score"]),
                "risk": row["risk"],
            }
            for row in csv.DictReader(csv_file)
        ][::-1]


class OfferGuardHandler(BaseHTTPRequestHandler):
    def _send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, filename, content_type):
        body = (APP_DIR / filename).read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/api/verifications":
            try:
                self._send_json(200, read_verifications())
            except (OSError, ValueError, KeyError) as error:
                self.log_error("Could not read verification CSV: %s", error)
                self._send_json(500, {"error": "Could not read saved verification history."})
            return

        static_files = {
            "/": ("index.html", "text/html; charset=utf-8"),
            "/index.html": ("index.html", "text/html; charset=utf-8"),
            "/style.css": ("style.css", "text/css; charset=utf-8"),
            "/script.js": ("script.js", "text/javascript; charset=utf-8"),
        }
        if path not in static_files:
            self._send_json(404, {"error": "Not found."})
            return
        filename, content_type = static_files[path]
        try:
            self._send_file(filename, content_type)
        except OSError as error:
            self.log_error("Could not serve %s: %s", filename, error)
            self._send_json(500, {"error": "Could not serve the application file."})

    def do_POST(self):
        if urlsplit(self.path).path != "/api/verifications":
            self._send_json(404, {"error": "Not found."})
            return
        if self.headers.get_content_type() != "application/json":
            self._send_json(415, {"error": "Send the offer as JSON."})
            return

        try:
            content_length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            self._send_json(400, {"error": "Invalid request length."})
            return
        if content_length < 0 or content_length > MAX_REQUEST_BYTES:
            self._send_json(413, {"error": "Request is too large."})
            return

        try:
            offer = json.loads(self.rfile.read(content_length))
            record = analyze_offer(offer)
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as error:
            self._send_json(400, {"error": str(error)})
            return

        try:
            save_verification(record)
        except OSError as error:
            self.log_error("Could not save verification CSV: %s", error)
            self._send_json(500, {"error": "Could not save the offer check to CSV."})
            return

        self._send_json(201, {
            "date": record["date"],
            "score": record["score"],
            "risk": record["risk"],
            "reasons": record["reasons"],
        })

    def log_message(self, format_string, *args):
        print("%s - %s" % (self.address_string(), format_string % args))


def main():
    server = ThreadingHTTPServer(("127.0.0.1", 8000), OfferGuardHandler)
    print("OfferGuard is running at http://127.0.0.1:8000")
    print("Verification CSV: %s" % CSV_FILE)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping OfferGuard.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
