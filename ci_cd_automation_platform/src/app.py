from flask import Flask, render_template, request, jsonify
import sqlite3
import os
import json
import uuid
import random
from datetime import datetime, timedelta

import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.metrics.collector import MetricsCollector
from services.governance.decision_engine import evaluate_build
from services.reports.report_builder import ReportBuilder
from services.explainer.log_parser import parse_pytest_failure
from integrations.github.webhook import parse_webhook_payload
from integrations.jenkins.client import JenkinsClient
from services.jenkins_service import JenkinsService

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

    # Legacy builds table
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

    # New pipelines table for full CI/CD observability
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS pipelines (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pipeline_id TEXT UNIQUE,
        repository TEXT,
        branch TEXT,
        commit_id TEXT,
        commit_author TEXT,
        commit_message TEXT,
        status TEXT DEFAULT 'queued',

        stage_checkout_start TEXT,
        stage_checkout_end TEXT,
        stage_checkout_status TEXT DEFAULT 'waiting',

        stage_install_start TEXT,
        stage_install_end TEXT,
        stage_install_status TEXT DEFAULT 'waiting',
        stage_install_dep_count INTEGER DEFAULT 0,

        stage_test_start TEXT,
        stage_test_end TEXT,
        stage_test_status TEXT DEFAULT 'waiting',
        test_pass_count INTEGER DEFAULT 0,
        test_fail_count INTEGER DEFAULT 0,
        test_skip_count INTEGER DEFAULT 0,

        stage_metrics_start TEXT,
        stage_metrics_end TEXT,
        stage_metrics_status TEXT DEFAULT 'waiting',

        stage_governance_start TEXT,
        stage_governance_end TEXT,
        stage_governance_status TEXT DEFAULT 'waiting',

        stage_build_start TEXT,
        stage_build_end TEXT,
        stage_build_status TEXT DEFAULT 'waiting',
        image_size TEXT,

        stage_deploy_start TEXT,
        stage_deploy_end TEXT,
        stage_deploy_status TEXT DEFAULT 'waiting',
        container_health TEXT,

        total_pipeline_duration REAL DEFAULT 0,
        governance_decision TEXT,
        governance_explanation TEXT,
        failure_stage TEXT,
        failure_explanation TEXT,
        failure_log_snippet TEXT,

        created_at TEXT,
        updated_at TEXT
    )
    """)

    conn.commit()
    conn.close()


# --------------------------------------------------
# Database Helpers
# --------------------------------------------------

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def row_to_dict(row):
    if row is None:
        return None
    return dict(row)


def rows_to_list(rows):
    return [dict(r) for r in rows]


def calc_duration_seconds(start_str, end_str):
    """Calculate duration between two ISO timestamp strings in seconds."""
    if not start_str or not end_str:
        return 0
    try:
        s = datetime.fromisoformat(start_str)
        e = datetime.fromisoformat(end_str)
        return round((e - s).total_seconds(), 2)
    except Exception:
        return 0


def build_stage_list(pipeline):
    """Build ordered list of stage objects from a pipeline dict."""
    stages_def = [
        ("Code Checkout", "checkout"),
        ("Dependency Install", "install"),
        ("Testing", "test"),
        ("Metrics Collection", "metrics"),
        ("Governance Evaluation", "governance"),
        ("Docker Build", "build"),
        ("Deployment", "deploy"),
    ]
    stages = []
    for label, key in stages_def:
        start = pipeline.get(f"stage_{key}_start")
        end = pipeline.get(f"stage_{key}_end")
        status = pipeline.get(f"stage_{key}_status", "waiting")
        duration = calc_duration_seconds(start, end)

        stage = {
            "name": label,
            "key": key,
            "start": start,
            "end": end,
            "status": status,
            "duration": duration,
        }

        # Extra metrics per stage
        if key == "install":
            stage["dep_count"] = pipeline.get("stage_install_dep_count", 0)
        elif key == "test":
            stage["test_pass"] = pipeline.get("test_pass_count", 0)
            stage["test_fail"] = pipeline.get("test_fail_count", 0)
            stage["test_skip"] = pipeline.get("test_skip_count", 0)
        elif key == "build":
            stage["image_size"] = pipeline.get("image_size", "")
        elif key == "deploy":
            stage["container_health"] = pipeline.get("container_health", "")

        stages.append(stage)
    return stages


# --------------------------------------------------
# Seed Demo Data
# --------------------------------------------------

def seed_demo_data():
    """Populate the database with realistic sample pipeline data for dashboard demonstration."""
    conn = get_db()
    cursor = conn.cursor()

    existing = cursor.execute("SELECT COUNT(*) FROM pipelines").fetchone()[0]
    if existing > 0:
        conn.close()
        return

    repos = ["ci_cd_automation_platform", "frontend-app", "api-gateway", "auth-service"]
    branches = ["main", "develop", "feature/auth", "fix/login-bug", "release/v2.1"]
    authors = ["Raj Parihar", "Alice Chen", "Bob Singh", "Carol Martinez"]
    messages = [
        "feat: add user authentication module",
        "fix: resolve login timeout issue",
        "chore: update dependencies",
        "refactor: clean up API handlers",
        "feat: implement pipeline metrics",
        "fix: patch security vulnerability in auth",
        "docs: update README with deployment steps",
        "feat: add Docker health check",
        "test: add integration tests for CI pipeline",
        "fix: correct environment variable paths",
    ]
    statuses_pool = ["success", "success", "success", "success", "failed", "blocked", "running", "queued"]

    now = datetime.utcnow()

    for i in range(15):
        pipeline_id = f"PL-{uuid.uuid4().hex[:8].upper()}"
        repo = random.choice(repos)
        branch = random.choice(branches)
        author = random.choice(authors)
        message = random.choice(messages)
        status = statuses_pool[i % len(statuses_pool)]
        created = now - timedelta(hours=random.randint(1, 72), minutes=random.randint(0, 59))

        # Generate realistic stage timestamps
        t = created
        stage_data = {}
        stage_keys = ["checkout", "install", "test", "metrics", "governance", "build", "deploy"]
        durations = [3, 25, 40, 2, 5, 60, 15]  # typical seconds per stage

        failed_at = None
        if status == "failed":
            failed_at = random.choice(["test", "build", "deploy"])
        elif status == "blocked":
            failed_at = "governance"

        for idx, key in enumerate(stage_keys):
            d = durations[idx] + random.randint(-2, 10)
            if d < 1:
                d = 1

            if status == "queued":
                stage_data[f"stage_{key}_status"] = "waiting"
                continue

            if status == "running" and idx >= 3:
                if idx == 3:
                    stage_data[f"stage_{key}_start"] = t.isoformat()
                    stage_data[f"stage_{key}_status"] = "running"
                else:
                    stage_data[f"stage_{key}_status"] = "waiting"
                continue

            stage_data[f"stage_{key}_start"] = t.isoformat()
            end = t + timedelta(seconds=d)
            stage_data[f"stage_{key}_end"] = end.isoformat()

            if failed_at == key:
                stage_data[f"stage_{key}_status"] = "failed"
                # Remaining stages stay waiting
                for remaining_key in stage_keys[idx + 1:]:
                    stage_data[f"stage_{remaining_key}_status"] = "waiting"
                break
            else:
                stage_data[f"stage_{key}_status"] = "completed"

            t = end + timedelta(seconds=random.randint(1, 3))

        total_dur = calc_duration_seconds(
            stage_data.get("stage_checkout_start", ""),
            stage_data.get(f"stage_{stage_keys[-1]}_end", stage_data.get(f"stage_{failed_at}_end", "")) if failed_at else stage_data.get("stage_deploy_end", "")
        )

        # Test metrics
        tp = random.randint(20, 50)
        tf = random.randint(0, 3) if status in ("failed", "blocked") else 0
        ts = random.randint(0, 5)

        # Governance
        gov_decision = "ALLOW"
        gov_explanation = ""
        if status == "blocked":
            gov_decision = "BLOCK"
            gov_explanation = f"Deployment blocked because {tf} of {tp + tf} tests failed during the testing stage."
        elif status == "failed" and failed_at == "test":
            gov_decision = "BLOCK"
            gov_explanation = f"Deployment blocked because tests failed with {tf} failures."

        # Failure info
        failure_stage = None
        failure_explanation = ""
        failure_log = ""
        if status == "failed":
            failure_stage = failed_at
            if failed_at == "test":
                failure_explanation = "Testing stage failed because pytest returned exit code 1."
                failure_log = "FAILED tests/test_auth.py::test_login - AssertionError: assert 200 == 401"
            elif failed_at == "build":
                failure_explanation = "Docker build failed due to missing dependency in requirements.txt."
                failure_log = "ERROR: Could not find a version that satisfies the requirement nonexistent-pkg==1.0.0"
            elif failed_at == "deploy":
                failure_explanation = "Deployment failed because container health check did not pass within timeout."
                failure_log = "ERROR: Container ci_cd_app exited with code 1 after 30s health check timeout."

        cursor.execute("""
            INSERT INTO pipelines (
                pipeline_id, repository, branch, commit_id, commit_author, commit_message, status,
                stage_checkout_start, stage_checkout_end, stage_checkout_status,
                stage_install_start, stage_install_end, stage_install_status, stage_install_dep_count,
                stage_test_start, stage_test_end, stage_test_status,
                test_pass_count, test_fail_count, test_skip_count,
                stage_metrics_start, stage_metrics_end, stage_metrics_status,
                stage_governance_start, stage_governance_end, stage_governance_status,
                stage_build_start, stage_build_end, stage_build_status, image_size,
                stage_deploy_start, stage_deploy_end, stage_deploy_status, container_health,
                total_pipeline_duration, governance_decision, governance_explanation,
                failure_stage, failure_explanation, failure_log_snippet,
                created_at, updated_at
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?,
                ?, ?
            )
        """, (
            pipeline_id, repo, branch,
            uuid.uuid4().hex[:12], author, message, status,
            stage_data.get("stage_checkout_start"), stage_data.get("stage_checkout_end"), stage_data.get("stage_checkout_status", "waiting"),
            stage_data.get("stage_install_start"), stage_data.get("stage_install_end"), stage_data.get("stage_install_status", "waiting"), random.randint(5, 20),
            stage_data.get("stage_test_start"), stage_data.get("stage_test_end"), stage_data.get("stage_test_status", "waiting"),
            tp, tf, ts,
            stage_data.get("stage_metrics_start"), stage_data.get("stage_metrics_end"), stage_data.get("stage_metrics_status", "waiting"),
            stage_data.get("stage_governance_start"), stage_data.get("stage_governance_end"), stage_data.get("stage_governance_status", "waiting"),
            stage_data.get("stage_build_start"), stage_data.get("stage_build_end"), stage_data.get("stage_build_status", "waiting"),
            f"{random.randint(80, 350)}MB",
            stage_data.get("stage_deploy_start"), stage_data.get("stage_deploy_end"), stage_data.get("stage_deploy_status", "waiting"),
            "healthy" if status == "success" else ("unhealthy" if status == "failed" and failed_at == "deploy" else ""),
            total_dur, gov_decision, gov_explanation,
            failure_stage, failure_explanation, failure_log,
            created.isoformat(), (created + timedelta(seconds=total_dur)).isoformat() if total_dur else created.isoformat(),
        ))

    conn.commit()
    conn.close()
    print("[Seed] Inserted 15 demo pipeline records.")


# --------------------------------------------------
# Legacy Routes
# --------------------------------------------------

def get_failure_recurrence(signature):
    if not signature:
        return 0
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM builds WHERE failure_signature = ?", (signature,))
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

    simulate_failure = False
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
    report = ReportBuilder.build_report(metrics, decision_data, test_status)
    report["ai_explanation"] = explanation
    ReportBuilder.save_to_database(report)
    return jsonify(report)


@app.route("/api/evaluate", methods=["POST"])
def api_evaluate():
    try:
        data = request.json
        metrics = data.get("metrics")
        test_status = data.get("test_status")
        log_text = data.get("log_text", "")
        failure_signature = None
        recurrence_count = 0
        explanation = None

        decision_data = evaluate_build(metrics, test_status)

        if test_status == "FAILED":
            explanation = parse_pytest_failure(log_text)
            from services.explainer.log_parser import generate_failure_signature
            failure_signature = generate_failure_signature(explanation)
            recurrence_count = get_failure_recurrence(failure_signature)
            explanation["failure_signature"] = failure_signature
            explanation["recurrence_count"] = recurrence_count

        report = ReportBuilder.build_report(metrics, decision_data, test_status)
        report["ai_explanation"] = explanation
        report["failure_signature"] = failure_signature
        ReportBuilder.save_to_database(report)
        return jsonify(report)
    except Exception as e:
        import traceback
        print(f"[api_evaluate ERROR] {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


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

    # Create a new pipeline record
    pipeline_id = f"PL-{uuid.uuid4().hex[:8].upper()}"
    conn = get_db()
    conn.execute("""
        INSERT INTO pipelines (pipeline_id, repository, branch, commit_id, commit_author, commit_message, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, 'queued', ?, ?)
    """, (
        pipeline_id,
        parsed_data.get("repository", ""),
        parsed_data.get("branch", ""),
        parsed_data.get("commit_id", ""),
        parsed_data.get("author", ""),
        parsed_data.get("commit_message", ""),
        datetime.utcnow().isoformat(),
        datetime.utcnow().isoformat(),
    ))
    conn.commit()
    conn.close()

    # Trigger Jenkins Pipeline
    jenkins_url = os.getenv("JENKINS_URL", "http://localhost:8080/")
    jenkins_user = os.getenv("JENKINS_USER", "admin")
    jenkins_token = os.getenv("JENKINS_TOKEN", "114d154f42f2e6dd30a9db042b6fd36c98")
    job_name = os.getenv("JENKINS_JOB_NAME", "CI-CD-Intelligence-Test")
    client = JenkinsClient(jenkins_url, jenkins_user, jenkins_token)
    params = None
    if parsed_data.get("commit_id"):
        params = {
            "COMMIT_ID": parsed_data["commit_id"],
            "BRANCH": parsed_data.get("branch", ""),
            "PIPELINE_ID": pipeline_id
        }
    client.trigger_build(job_name, params=params)

    return jsonify({"message": "Webhook processed, Jenkins build triggered.", "pipeline_id": pipeline_id, "data": parsed_data})


# --------------------------------------------------
# Pipeline Report Endpoint (used by Jenkinsfile)
# --------------------------------------------------

@app.route("/api/pipelines/report", methods=["POST"])
def pipeline_report():
    """Accepts stage metadata from Jenkins to create or update pipeline records."""
    try:
        data = request.json
        pipeline_id = data.get("pipeline_id")
        if not pipeline_id:
            return jsonify({"error": "pipeline_id is required"}), 400

        conn = get_db()

        # Check if pipeline exists
        existing = conn.execute("SELECT id FROM pipelines WHERE pipeline_id = ?", (pipeline_id,)).fetchone()

        if not existing:
            # Create new pipeline
            conn.execute("""
                INSERT INTO pipelines (pipeline_id, repository, branch, commit_id, commit_author, commit_message, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                pipeline_id,
                data.get("repository", ""),
                data.get("branch", ""),
                data.get("commit_id", ""),
                data.get("commit_author", ""),
                data.get("commit_message", ""),
                data.get("status", "running"),
                datetime.utcnow().isoformat(),
                datetime.utcnow().isoformat(),
            ))

        # Build dynamic UPDATE from provided stage data
        update_fields = []
        update_values = []

        field_map = [
            "status", "stage_checkout_start", "stage_checkout_end", "stage_checkout_status",
            "stage_install_start", "stage_install_end", "stage_install_status", "stage_install_dep_count",
            "stage_test_start", "stage_test_end", "stage_test_status",
            "test_pass_count", "test_fail_count", "test_skip_count",
            "stage_metrics_start", "stage_metrics_end", "stage_metrics_status",
            "stage_governance_start", "stage_governance_end", "stage_governance_status",
            "stage_build_start", "stage_build_end", "stage_build_status", "image_size",
            "stage_deploy_start", "stage_deploy_end", "stage_deploy_status", "container_health",
            "total_pipeline_duration", "governance_decision", "governance_explanation",
            "failure_stage", "failure_explanation", "failure_log_snippet",
        ]

        for field in field_map:
            if field in data:
                update_fields.append(f"{field} = ?")
                update_values.append(data[field])

        if update_fields:
            update_fields.append("updated_at = ?")
            update_values.append(datetime.utcnow().isoformat())
            update_values.append(pipeline_id)

            conn.execute(
                f"UPDATE pipelines SET {', '.join(update_fields)} WHERE pipeline_id = ?",
                update_values
            )

        conn.commit()
        conn.close()
        return jsonify({"message": "Pipeline updated", "pipeline_id": pipeline_id})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# --------------------------------------------------
# Pipeline API Endpoints
# --------------------------------------------------

@app.route("/api/pipelines/active")
def pipelines_active():
    service = JenkinsService()
    pipelines = service.sync_pipelines()
    active = [p for p in pipelines if p['status'] in ('queued', 'running')]
    return jsonify(active)


@app.route("/api/pipelines/history")
def pipelines_history():
    service = JenkinsService()
    pipelines = service.sync_pipelines()
    history = [p for p in pipelines if p['status'] not in ('queued', 'running')]
    return jsonify(history)


@app.route("/api/pipelines/metrics")
def pipelines_metrics():
    conn = get_db()

    total = conn.execute("SELECT COUNT(*) FROM pipelines").fetchone()[0]
    success = conn.execute("SELECT COUNT(*) FROM pipelines WHERE status = 'success'").fetchone()[0]
    failed = conn.execute("SELECT COUNT(*) FROM pipelines WHERE status = 'failed'").fetchone()[0]
    blocked = conn.execute("SELECT COUNT(*) FROM pipelines WHERE status = 'blocked'").fetchone()[0]
    active = conn.execute("SELECT COUNT(*) FROM pipelines WHERE status IN ('queued', 'running')").fetchone()[0]

    avg_duration = conn.execute("SELECT AVG(total_pipeline_duration) FROM pipelines WHERE total_pipeline_duration > 0").fetchone()[0] or 0

    # Average test duration
    rows = conn.execute("""
        SELECT stage_test_start, stage_test_end FROM pipelines
        WHERE stage_test_start IS NOT NULL AND stage_test_end IS NOT NULL
    """).fetchall()
    test_durations = [calc_duration_seconds(r["stage_test_start"], r["stage_test_end"]) for r in rows]
    avg_test_duration = round(sum(test_durations) / len(test_durations), 2) if test_durations else 0

    # Average build duration
    brows = conn.execute("""
        SELECT stage_build_start, stage_build_end FROM pipelines
        WHERE stage_build_start IS NOT NULL AND stage_build_end IS NOT NULL
    """).fetchall()
    build_durations = [calc_duration_seconds(r["stage_build_start"], r["stage_build_end"]) for r in brows]
    avg_build_duration = round(sum(build_durations) / len(build_durations), 2) if build_durations else 0

    conn.close()

    return jsonify({
        "total_builds": total,
        "successful_builds": success,
        "failed_builds": failed,
        "blocked_deployments": blocked,
        "active_pipelines": active,
        "avg_pipeline_duration": round(avg_duration, 2),
        "avg_test_duration": avg_test_duration,
        "avg_build_duration": avg_build_duration,
    })


@app.route("/api/pipelines/details/<int:pipeline_db_id>")
def pipeline_details(pipeline_db_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM pipelines WHERE id = ?", (pipeline_db_id,)).fetchone()
    conn.close()
    if not row:
        return jsonify({"error": "Pipeline not found"}), 404
    pipeline = row_to_dict(row)
    pipeline["stages"] = build_stage_list(pipeline)
    return jsonify(pipeline)


# --------------------------------------------------
# Legacy History Endpoint
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
    return render_template("index.html")


# --------------------------------------------------
# App Runner
# --------------------------------------------------

if __name__ == "__main__":
    init_db()
    # seed_demo_data() # Disabled for real integration
    app.run(debug=True)