from flask import Flask, render_template, request, jsonify
import sqlite3
import os
from datetime import datetime

from metrics.collector import MetricsCollector
from core.decision_engine import evaluate_build
from reports.report_builder import ReportBuilder
from explainer.log_parser import parse_pytest_failure

app = Flask(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "builds.db")


# --------------------------------------------------
# Database Initialization
# --------------------------------------------------

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS builds (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        build_id TEXT,
        waste_score REAL,
        decision TEXT,
        timestamp TEXT,
        failure_signature TEXT
    )
""")

    conn.commit()
    conn.close()


# --------------------------------------------------
# Simulation Route (Manual Testing)
# --------------------------------------------------
def get_failure_recurrence(signature):
    if not signature:
        return 0

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT COUNT(*) FROM builds
        WHERE failure_signature = ?
    """, (signature,))

    count = cursor.fetchone()[0]
    conn.close()

    return count
@app.route("/simulate-build")
def simulate_build():
    collector = MetricsCollector()

    collector.start_timer()
    import time
    time.sleep(2)
    collector.stop_timer()

    metrics = collector.collect_metrics()

    simulate_failure = False  # Toggle for testing

    if simulate_failure:
        test_status = "FAILED"
        fake_log = """
        ============================= test session starts =============================
        FAILED tests/test_basic.py::test_example
        E       assert 1 == 2
        tests/test_basic.py:2: AssertionError
        """
        explanation = parse_pytest_failure(fake_log)
    else:
        test_status = "PASSED"
        explanation = None

    decision_data = evaluate_build(metrics, test_status)

    report = ReportBuilder.build_report(
        metrics,
        decision_data,
        test_status
    )

    report["ai_explanation"] = explanation

    ReportBuilder.save_to_database(report)

    return report


# --------------------------------------------------
# API Endpoint (Used by Jenkins)
# --------------------------------------------------

@app.route("/api/evaluate", methods=["POST"])
def api_evaluate():
    data = request.json

    metrics = data.get("metrics")
    test_status = data.get("test_status")
    log_text = data.get("log_text", "")
    failure_signature = None
    recurrence_count = 0
    explanation = None
    decision_data = evaluate_build(metrics, test_status)
    
    # 🔥 Phase 7 Intelligence Integration
    explanation = None
    if test_status == "FAILED":
        explanation = parse_pytest_failure(log_text)
        
        from explainer.log_parser import generate_failure_signature
        failure_signature = generate_failure_signature(explanation)
        recurrence_count = get_failure_recurrence(failure_signature)
        explanation["failure_signature"] = failure_signature
        explanation["recurrence_count"] = recurrence_count

    report = ReportBuilder.build_report(
        metrics,
        decision_data,
        test_status
    )

    report["ai_explanation"] = explanation
    report["failure_signature"] = failure_signature

    ReportBuilder.save_to_database(report)

    return jsonify(report)


# --------------------------------------------------
# History Endpoint
# --------------------------------------------------

@app.route("/history")
def history():
    builds = ReportBuilder.fetch_all_builds()
    return {"builds": builds}


# --------------------------------------------------
# Dashboard UI
# --------------------------------------------------

@app.route("/")
def home():
    latest = ReportBuilder.fetch_latest_build()
    history = ReportBuilder.fetch_all_builds()

    chart_labels = [build[1] for build in history]
    chart_data = [build[2] for build in history]

    return render_template(
        "index.html",
        latest=latest,
        history=history,
        chart_labels=chart_labels,
        chart_data=chart_data
    )


# --------------------------------------------------
# App Runner
# --------------------------------------------------

if __name__ == "__main__":
    init_db()
    app.run(debug=True)