from flask import Flask, render_template
import sqlite3
import os
from metrics.collector import MetricsCollector
from core.decision_engine import evaluate_build
from datetime import datetime
from reports.report_builder import ReportBuilder
from explainer.log_parser import LogExplainer   
app = Flask(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "builds.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS builds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            build_id TEXT,
            waste_score REAL,
            decision TEXT,
            timestamp TEXT
        )
    """)
    conn.commit()
    conn.close()


@app.route("/simulate-build")
def simulate_build():
    collector = MetricsCollector()

    collector.start_timer()
    import time
    time.sleep(2)
    collector.stop_timer()

    metrics = collector.collect_metrics()

    # Simulate failure scenario toggle
    simulate_failure = False  # Change to True to test failure

    if simulate_failure:
        test_status = "FAILED"
        fake_log = "ModuleNotFoundError: No module named 'flask'"
        explanation = LogExplainer.analyze_log(fake_log)
    else:
        test_status = "PASSED"
        explanation = None

    decision_data = evaluate_build(metrics, test_status)

    report = ReportBuilder.build_report(
        metrics,
        decision_data,
        test_status
    )

    # Attach explanation to report
    report["ai_explanation"] = explanation

    ReportBuilder.save_to_database(report)

    return report

@app.route("/history")
def history():
    builds = ReportBuilder.fetch_all_builds()
    return {
        "builds": builds
    }

@app.route("/api/evaluate", methods=["POST"])
def api_evaluate():
    from flask import request, jsonify

    data = request.json

    metrics = data.get("metrics")
    test_status = data.get("test_status")
    log_text = data.get("log_text", "")

    decision_data = evaluate_build(metrics, test_status)
    explanation = LogExplainer.analyze_log(log_text)

    report = ReportBuilder.build_report(
        metrics,
        decision_data,
        test_status
    )

    report["ai_explanation"] = explanation

    ReportBuilder.save_to_database(report)

    return jsonify(report)

@app.route("/")
def home():
    latest = ReportBuilder.fetch_latest_build()
    history = ReportBuilder.fetch_all_builds()

    # Prepare clean data for chart
    chart_labels = [build[1] for build in history]
    chart_data = [build[2] for build in history]

    return render_template(
        "index.html",
        latest=latest,
        history=history,
        chart_labels=chart_labels,
        chart_data=chart_data
    )

if __name__ == "__main__":
    init_db()
    app.run(debug=True)