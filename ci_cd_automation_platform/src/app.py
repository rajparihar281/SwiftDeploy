from flask import Flask, render_template, request, jsonify
import sqlite3
import os
import json
import uuid
import random
from datetime import datetime, timedelta, timezone
from fpdf import FPDF
from fpdf.enums import XPos, YPos
import io

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


# --------------------------------------------------
# Legacy Routes (Disabled for Production)
# --------------------------------------------------
# @app.route("/simulate-build")
# def simulate_build():
#     ...


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

@app.route("/webhook/github", methods=["POST"], strict_slashes=False)
def github_webhook():
    event_type = request.headers.get("X-GitHub-Event")
    if not event_type:
        print("[Webhook Error] Missing X-GitHub-Event header")
        return jsonify({"message": "Missing X-GitHub-Event header"}), 400

    payload = request.json
    parsed_data = parse_webhook_payload(payload, event_type)
    
    repo = parsed_data.get("repository", "unknown")
    branch = parsed_data.get("branch", "unknown")
    commit = parsed_data.get("commit_id", "none")[:8]
    
    print(f"[Webhook] Received GitHub {event_type} event for {repo} ({branch}) @ {commit}")

    # Create a new pipeline record
    # Since we can't pass the ID to Jenkins anymore, we'll prefix it so we know it was webhook-triggered
    pipeline_id = f"WEBHOOK-{uuid.uuid4().hex[:6].upper()}"
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
        datetime.now(timezone.utc).isoformat(),
        datetime.now(timezone.utc).isoformat(),
    ))
    conn.commit()
    conn.close()

    # Trigger Jenkins Pipeline
    jenkins_url = os.getenv("JENKINS_URL", "http://localhost:8080/")
    jenkins_user = os.getenv("JENKINS_USER", "admin")
    jenkins_token = os.getenv("JENKINS_TOKEN", "114d154f42f2e6dd30a9db042b6fd36c98")
    job_name = os.getenv("JENKINS_JOB_NAME", "CI-CD-Intelligence-Test")

    print(f"[Jenkins] Triggering build for '{job_name}' on {jenkins_url}")
    client = JenkinsClient(jenkins_url, jenkins_user, jenkins_token)
    
    params = {
        "COMMIT_ID": parsed_data.get("commit_id", ""),
        "BRANCH": parsed_data.get("branch", ""),
        "PIPELINE_ID": pipeline_id,
        "REPO_NAME": parsed_data.get("repository", "")
    }
    
    success = client.trigger_build(job_name, params=params)
    if success:
        print(f"[Jenkins] Build triggered successfully for {pipeline_id}")
    else:
        print(f"[Jenkins Error] Failed to trigger build for {pipeline_id}")

    return jsonify({
        "message": "Webhook processed, Jenkins build triggered." if success else "Webhook processed, but Jenkins trigger failed.", 
        "pipeline_id": pipeline_id, 
        "success": success,
        "data": parsed_data
    })


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
        existing = conn.execute("SELECT pipeline_id FROM pipelines WHERE pipeline_id = ?", (pipeline_id,)).fetchone()

        if not existing and data.get("commit_id"):
            # Try to correlate by commit_id targeting the most RECENT 'queued' record for this commit
            print(f"[Correlation] Linking Jenkins {pipeline_id} to webhook record for commit {data.get('commit_id')[:8]}")
            
            conn.execute("""
                UPDATE pipelines SET pipeline_id = ?, status = ? 
                WHERE id = (
                    SELECT id FROM pipelines 
                    WHERE commit_id = ? AND status = 'queued' 
                    ORDER BY created_at DESC LIMIT 1
                )
            """, (pipeline_id, data.get("status", "running"), data.get("commit_id")))
            
            existing = conn.execute("SELECT pipeline_id FROM pipelines WHERE pipeline_id = ?", (pipeline_id,)).fetchone()
            if existing:
                print(f"[Correlation] Successfully linked {pipeline_id} to existing webhook record.")
                
                # Cleanup: Delete any other 'queued' records for this same commit/branch to prevent clutter
                conn.execute("DELETE FROM pipelines WHERE commit_id = ? AND status = 'queued'", (data.get("commit_id"),))
            else:
                print(f"[Correlation] No matching queued record found for commit {data.get('commit_id')[:8]}")

        if not existing:
            # Create new pipeline if still not found
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
                datetime.now(timezone.utc).isoformat(),
                datetime.now(timezone.utc).isoformat(),
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
            update_values.append(datetime.now(timezone.utc).isoformat())
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
    """Syncs with Jenkins and returns active pipelines from DB."""
    conn = get_db()
    
    # Sync latest from Jenkins to DB first
    try:
        service = JenkinsService()
        service.sync_pipelines(db_conn=conn)
    except Exception as e:
        print(f"[Jenkins Sync Error] {e}")

    rows = conn.execute("SELECT * FROM pipelines WHERE status IN ('queued', 'running', 'blocked') ORDER BY created_at DESC").fetchall()
    conn.close()
    
    pipelines = rows_to_list(rows)
    for p in pipelines:
        p["stages"] = build_stage_list(p)
        
    return jsonify(pipelines)


@app.route("/api/pipelines/history")
def pipelines_history():
    """Returns historical pipelines from the local database."""
    conn = get_db()
    
    # Filter by search/status/repo if present in query params
    search = request.args.get("search")
    status = request.args.get("status")
    repo = request.args.get("repo")
    
    query = "SELECT * FROM pipelines WHERE status NOT IN ('queued', 'running', 'blocked')"
    params = []
    
    if search:
        query += " AND (pipeline_id LIKE ? OR commit_message LIKE ? OR commit_author LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
    if status:
        query += " AND status = ?"
        params.append(status)
    if repo:
        query += " AND repository = ?"
        params.append(repo)
        
    query += " ORDER BY created_at DESC LIMIT 50"
    
    rows = conn.execute(query, params).fetchall()
    conn.close()
    
    pipelines = rows_to_list(rows)
    for p in pipelines:
        p["stages"] = build_stage_list(p)
        
    return jsonify(pipelines)


@app.route("/api/pipelines/metrics")
def pipelines_metrics():
    conn = get_db()

    # Basic Counts
    total = conn.execute("SELECT COUNT(*) FROM pipelines").fetchone()[0]
    success = conn.execute("SELECT COUNT(*) FROM pipelines WHERE status = 'success'").fetchone()[0]
    failed = conn.execute("SELECT COUNT(*) FROM pipelines WHERE status = 'failed'").fetchone()[0]
    blocked = conn.execute("SELECT COUNT(*) FROM pipelines WHERE status = 'blocked'").fetchone()[0]
    active = conn.execute("SELECT COUNT(*) FROM pipelines WHERE status IN ('queued', 'running')").fetchone()[0]

    # Global Durations
    avg_duration = conn.execute("SELECT AVG(total_pipeline_duration) FROM pipelines WHERE total_pipeline_duration > 0").fetchone()[0] or 0
    
    # Status Distribution details
    counts_by_status = conn.execute("SELECT status, COUNT(*) as count FROM pipelines GROUP BY status").fetchall()
    status_distribution = {row['status']: row['count'] for row in counts_by_status}

    # Time-series Trend (Last 30 builds)
    trend_rows = conn.execute("""
        SELECT pipeline_id, total_pipeline_duration, test_pass_count, test_fail_count, status, created_at 
        FROM pipelines 
        WHERE status NOT IN ('queued', 'running')
        ORDER BY created_at DESC LIMIT 30
    """).fetchall()
    
    history_trend = []
    for r in reversed(trend_rows):
        history_trend.append({
            "id": r['pipeline_id'][:8],
            "duration": r['total_pipeline_duration'] or 0,
            "tests_pass": r['test_pass_count'] or 0,
            "tests_fail": r['test_fail_count'] or 0,
            "status": r['status']
        })

    # Stage Averages
    stage_keys = ["checkout", "install", "test", "metrics", "governance", "build", "deploy"]
    stage_averages = {}
    for key in stage_keys:
        rows = conn.execute(f"""
            SELECT stage_{key}_start, stage_{key}_end FROM pipelines
            WHERE stage_{key}_start IS NOT NULL AND stage_{key}_end IS NOT NULL
        """).fetchall()
        durs = [calc_duration_seconds(r[f"stage_{key}_start"], r[f"stage_{key}_end"]) for r in rows]
        stage_averages[key] = round(sum(durs) / len(durs), 2) if durs else 0

    # Build Frequency (Last 7 days)
    frequency_rows = conn.execute("""
        SELECT date(created_at) as day, COUNT(*) as count 
        FROM pipelines 
        WHERE created_at >= date('now', '-7 days')
        GROUP BY day ORDER BY day ASC
    """).fetchall()
    build_frequency = {row['day']: row['count'] for row in frequency_rows}

    # Top Contributors
    top_authors = conn.execute("SELECT commit_author, COUNT(*) as count FROM pipelines GROUP BY commit_author ORDER BY count DESC LIMIT 5").fetchall()
    top_repos = conn.execute("SELECT repository, COUNT(*) as count FROM pipelines GROUP BY repository ORDER BY count DESC LIMIT 5").fetchall()
    
    # Reliability Metrics
    deploy_total = conn.execute("SELECT COUNT(*) FROM pipelines WHERE stage_deploy_status != 'waiting'").fetchone()[0]
    deploy_success = conn.execute("SELECT COUNT(*) FROM pipelines WHERE stage_deploy_status = 'completed'").fetchone()[0]
    
    # Health Score Calculation (Simplified logic)
    # 50% success rate, 30% test pass rate, 20% duration stability
    success_rate = (success / total * 100) if total > 0 else 0
    deploy_rate = (deploy_success / deploy_total * 100) if deploy_total > 0 else 0
    health_score = round((success_rate * 0.6) + (deploy_rate * 0.4)) if total > 0 else 0

    conn.close()

    return jsonify({
        "total_builds": total,
        "successful_builds": success,
        "failed_builds": failed,
        "blocked_deployments": blocked,
        "active_pipelines": active,
        "avg_pipeline_duration": round(avg_duration, 2),
        "avg_test_duration": stage_averages.get("test", 0),
        "avg_build_duration": stage_averages.get("build", 0),
        
        # New analytics
        "status_distribution": status_distribution,
        "history_trend": history_trend,
        "stage_averages": stage_averages,
        "build_frequency": build_frequency,
        "top_authors": [{"name": r['commit_author'], "count": r['count']} for r in top_authors],
        "top_repositories": [{"name": r['repository'], "count": r['count']} for r in top_repos],
        "deployment_stats": {
            "total": deploy_total,
            "success": deploy_success,
            "failed": deploy_total - deploy_success,
            "rate": round(deploy_rate, 1)
        },
        "health_score": health_score,
        "test_stats": {
            "total_executed": sum(r['tests_pass'] + r['tests_fail'] for r in history_trend),
            "avg_pass_rate": round(sum(r['tests_pass'] for r in history_trend) / sum(r['tests_pass'] + r['tests_fail'] if (r['tests_pass'] + r['tests_fail']) > 0 else 1 for r in history_trend) * 100, 1) if history_trend else 0
        }
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


@app.route("/build/<int:pipeline_db_id>")
def build_details_page(pipeline_db_id):
    """Render the detailed full-page view for a specific build."""
    conn = get_db()
    row = conn.execute("SELECT * FROM pipelines WHERE id = ?", (pipeline_db_id,)).fetchone()
    conn.close()
    if not row:
        return "Build not found", 404
    
    pipeline = row_to_dict(row)
    pipeline["stages"] = build_stage_list(pipeline)
    return render_template("build_details.html", pipeline=pipeline)


@app.route("/api/admin/clean-db", methods=["POST"])
def admin_clean_db():
    """Wipes all pipeline and build records for a clean slate."""
    try:
        conn = get_db()
        conn.execute("DELETE FROM pipelines")
        conn.execute("DELETE FROM builds")
        conn.commit()
        conn.close()
        return jsonify({"message": "Database cleaned successfully. All history purged."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/pipelines/report/pdf/<int:pipeline_db_id>")
def download_pdf_report(pipeline_db_id):
    """Generates and serves a PDF report for a specific pipeline execution."""
    conn = get_db()
    row = conn.execute("SELECT * FROM pipelines WHERE id = ?", (pipeline_db_id,)).fetchone()
    conn.close()
    
    if not row:
        return "Pipeline not found", 404
    
    p = row_to_dict(row)
    stages = build_stage_list(p)
    
    # Generate PDF
    pdf = FPDF()
    pdf.add_page()
    
    # Header
    pdf.set_font("Helvetica", 'B', 16)
    pdf.cell(0, 10, "SwiftDeploy - CI/CD Pipeline Report", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
    pdf.set_font("Helvetica", '', 10)
    pdf.cell(0, 10, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
    pdf.ln(10)
    
    # Summary Table
    pdf.set_font("Helvetica", 'B', 12)
    pdf.cell(0, 10, "1. Build Metadata", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", '', 10)
    
    data_summary = [
        ["Pipeline ID", p["pipeline_id"]],
        ["Repository", p["repository"] or "N/A"],
        ["Branch", p["branch"] or "N/A"],
        ["Commit", (p["commit_id"] or "N/A")[:12]],
        ["Author", p["commit_author"] or "N/A"],
        ["Status", (p["status"] or "waiting").upper()],
        ["Duration", f"{p['total_pipeline_duration'] or 0}s"]
    ]
    
    for row_data in data_summary:
        pdf.cell(50, 8, row_data[0], border=1)
        pdf.cell(0, 8, str(row_data[1]), border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    
    pdf.ln(10)
    
    # Stage Timeline
    pdf.set_font("Helvetica", 'B', 12)
    pdf.cell(0, 10, "2. Stage Timeline", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", 'B', 10)
    pdf.cell(60, 8, "Stage", border=1)
    pdf.cell(40, 8, "Duration (s)", border=1)
    pdf.cell(0, 8, "Status", border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    
    pdf.set_font("Helvetica", '', 10)
    for s in stages:
        pdf.cell(60, 8, s["name"], border=1)
        pdf.cell(40, 8, f"{s['duration']}s", border=1)
        pdf.cell(0, 8, (s["status"] or "waiting").upper(), border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        
    pdf.ln(10)
    
    # Governance & Failures
    if p["governance_decision"] or p["failure_stage"]:
        pdf.set_font("Helvetica", 'B', 12)
        pdf.cell(0, 10, "3. Analysis & Governance", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("Helvetica", '', 10)
        
        if p["governance_decision"]:
            pdf.multi_cell(0, 8, f"Governance Decision: {p['governance_decision']}", border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.multi_cell(0, 8, f"Explanation: {p['governance_explanation'] or 'N/A'}", border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.ln(5)
            
        if p["failure_stage"]:
            pdf.set_text_color(200, 0, 0)
            pdf.multi_cell(0, 8, f"FAILURE at {p['failure_stage']} stage", border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_text_color(0, 0, 0)
            pdf.multi_cell(0, 8, f"Reason: {p['failure_explanation'] or 'N/A'}", border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    
    # Send Binary
    buffer = io.BytesIO()
    pdf_output = pdf.output()
    if isinstance(pdf_output, str): # Compatibility with different fpdf versions
        buffer.write(pdf_output.encode('latin-1'))
    else:
        buffer.write(pdf_output)
    
    buffer.seek(0)
    from flask import send_file
    return send_file(
        buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f"report_{p['pipeline_id']}.pdf"
    )


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
    app.run(debug=True)