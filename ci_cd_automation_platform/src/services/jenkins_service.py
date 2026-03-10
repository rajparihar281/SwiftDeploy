import os
from datetime import datetime, timezone
from integrations.jenkins.client import JenkinsClient

class JenkinsService:
    def __init__(self):
        self.url = os.getenv("JENKINS_URL", "http://localhost:8080/")
        self.user = os.getenv("JENKINS_USER", "admin")
        self.token = os.getenv("JENKINS_TOKEN", "114d154f42f2e6dd30a9db042b6fd36c98")
        self.job_name = os.getenv("JENKINS_JOB_NAME", "CI-CD-Intelligence-Test")
        self.client = JenkinsClient(self.url, self.user, self.token)

    def sync_pipelines(self, db_conn=None):
        """Fetch latest builds from Jenkins and sync them into our local database."""
        raw_builds = self.client.get_build_list(self.job_name)
        
        for build in raw_builds[:10]:
            build_num = build['number']
            
            # Get full build details to extract parameters
            status_url = f"{self.url}/job/{self.job_name}/{build_num}/api/json"
            import requests
            res = requests.get(status_url, auth=self.client.auth)
            full_build = res.json() if res.status_code == 200 else {}
            
            # Extract PIPELINE_ID from parameters if present
            params = {}
            for action in full_build.get("actions", []):
                if action.get("_class") == "hudson.model.ParametersAction":
                    for p in action.get("parameters", []):
                        params[p.get("name")] = p.get("value")
            
            pipeline_id = params.get("PIPELINE_ID") or f"PL-{build_num}"
            status = self._map_status(build)
            
            if db_conn:
                # Check if we have a record for this pipeline_id
                existing = db_conn.execute("SELECT id FROM pipelines WHERE pipeline_id = ?", (pipeline_id,)).fetchone()
                
                if existing:
                    # Update status and duration if it's still running or just finished
                    db_conn.execute("""
                        UPDATE pipelines 
                        SET status = ?, 
                            total_pipeline_duration = ?,
                            updated_at = ?
                        WHERE pipeline_id = ?
                    """, (
                        status, 
                        build.get("duration", 0) / 1000.0,
                        datetime.now(timezone.utc).isoformat(),
                        pipeline_id
                    ))
                else:
                    # Create new record for untracked (e.g. manual) build
                    db_conn.execute("""
                        INSERT INTO pipelines (pipeline_id, repository, branch, status, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        pipeline_id,
                        self.job_name,
                        params.get("BRANCH", "main"),
                        status,
                        self._format_ts(build.get("timestamp")),
                        datetime.now(timezone.utc).isoformat()
                    ))
                db_conn.commit()

    def _map_status(self, build):
        if build.get("building"):
            return "running"
        result = build.get("result")
        if result == "SUCCESS":
            return "success"
        if result == "FAILURE":
            return "failed"
        if result == "ABORTED":
            return "blocked"
        return "queued"

    def _format_ts(self, ts_ms):
        if not ts_ms:
            return datetime.now(timezone.utc).isoformat()
        return datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc).isoformat()

    def _map_stages(self, wf_data):
        stages = []
        for stage in wf_data.get("stages", []):
            stages.append({
                "name": stage.get("name"),
                "status": self._map_wf_status(stage.get("status")),
                "duration": stage.get("durationMillis", 0) / 1000.0,
                "start": self._format_ts(stage.get("startTimeMillis")),
                "end": self._format_ts(stage.get("startTimeMillis") + stage.get("durationMillis")) if stage.get("durationMillis") else None
            })
        return stages

    def _map_wf_status(self, status):
        mapping = {
            "SUCCESS": "completed",
            "FAILED": "failed",
            "IN_PROGRESS": "running",
            "PAUSED_PENDING_INPUT": "blocked"
        }
        return mapping.get(status, "waiting")
