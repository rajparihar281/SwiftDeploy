from flask import Flask, render_template, request, jsonify
import sqlite3
import os
from datetime import datetime

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.metrics.collector import MetricsCollector
from services.governance.decision_engine import evaluate_build
from services.reports.report_builder import ReportBuilder
from services.explainer.log_parser import parse_pytest_failure
from integrations.github.webhook import parse_webhook_payload
from integrations.jenkins.client import JenkinsClient

app = Flask(__name__, 
            template_folder=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dashboard", "templates"),
            static_folder=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dashboard", "static"))

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
        
        from services.explainer.log_parser import generate_failure_signature
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
# GitHub Webhook Endpoint
# --------------------------------------------------

@app.route("/webhook/github", methods=["POST"])
def github_webhook():
    event_type = request.headers.get("X-GitHub-Event")
    if not event_type:
        return jsonify({"message": "Missing X-GitHub-Event header"}), 400

    payload = request.json
    parsed_data = parse_webhook_payload(payload, event_type)
    
    print(f"Received GitHub {event_type} event: {parsed_data}")
    
    # Trigger Jenkins Pipeline
    jenkins_url = os.getenv("JENKINS_URL", "http://localhost:8080/")
    jenkins_user = os.getenv("JENKINS_USER", "admin")
    jenkins_token = os.getenv("JENKINS_TOKEN", "114d154f42f2e6dd30a9db042b6fd36c98")
    job_name = os.getenv("JENKINS_JOB_NAME", "CI-CD-Intelligence-Test")
    
    client = JenkinsClient(jenkins_url, jenkins_user, jenkins_token)
    
    # Passing the commit info as params if requested
    params = None
    if parsed_data.get("commit_id"):
        params = {"COMMIT_ID": parsed_data["commit_id"], "BRANCH": parsed_data.get("branch", "")}
        
    client.trigger_build(job_name, params=params)

    return jsonify({"message": "Webhook processed, Jenkins build triggered.", "data": parsed_data})

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