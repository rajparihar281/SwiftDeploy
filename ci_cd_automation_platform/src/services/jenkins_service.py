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
        if not db_conn:
            return

        raw_builds = self.client.get_build_list(self.job_name)
        active_build_nums = {b['number'] for b in raw_builds}
        
        # Also find all builds in our DB that are currently 'queued' or 'running'
        # to ensure we check their specific status even if they rolled off the top 10 list
        active_local_ids = db_conn.execute("SELECT pipeline_id FROM pipelines WHERE status IN ('queued', 'running', 'blocked')").fetchall()
        for row in active_local_ids:
            pid = row[0]
            if pid.startswith("PL-"):
                try:
                    num = int(pid.split("-")[1])
                    if num not in active_build_nums:
                        # Fetch specific build status if it's missing from the main list
                        build_status = self.client.get_build_status(self.job_name, num)
                        if build_status:
                            build_status['number'] = num
                            raw_builds.append(build_status)
                except:
                    pass

        for build in raw_builds:
            build_num = build.get('number')
            if not build_num: continue
            
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
            
            # Check if we have a record for this pipeline_id
            existing = db_conn.execute("SELECT id, status FROM pipelines WHERE pipeline_id = ?", (pipeline_id,)).fetchone()
            
            # Fetch commit metadata from Jenkins if possible
            commit_info = {}
            try:
                meta_url = f"{self.url}/job/{self.job_name}/{build_num}/api/json?tree=actions[lastBuiltRevision[SHA1],remoteUrls],changeSets[items[commitId,author[fullName],msg]]"
                meta_res = requests.get(meta_url, auth=self.client.auth)
                if meta_res.status_code == 200:
                    meta_data = meta_res.json()
                    for action in meta_data.get("actions", []):
                        if action.get("lastBuiltRevision"):
                            commit_info["id"] = action["lastBuiltRevision"].get("SHA1")
                        if action.get("remoteUrls"):
                            commit_info["repo"] = action["remoteUrls"][0]
                    
                    cs = meta_data.get("changeSets", [])
                    if cs and cs[0].get("items"):
                        last_item = cs[0]["items"][0]
                        commit_info["author"] = last_item.get("author", {}).get("fullName")
                        commit_info["message"] = last_item.get("msg")
                        if not commit_info.get("id"):
                            commit_info["id"] = last_item.get("commitId")
            except Exception as e:
                print(f"[Sync Metadata Error] {e}")

            if existing:
                current_status = existing[1]
                new_status = status
                # Protection: If local DB already says 'running', only update if Jenkins says it's finished
                if current_status == 'running' and status == 'queued':
                    new_status = 'running'

                db_conn.execute("""
                    UPDATE pipelines 
                    SET status = ?, 
                        total_pipeline_duration = ?,
                        updated_at = ?,
                        commit_id = COALESCE(commit_id, ?),
                        commit_author = COALESCE(commit_author, ?),
                        commit_message = COALESCE(commit_message, ?),
                        repository = COALESCE(repository, ?)
                    WHERE pipeline_id = ?
                """, (
                    new_status, 
                    build.get("duration", 0) / 1000.0,
                    datetime.now(timezone.utc).isoformat(),
                    commit_info.get("id"),
                    commit_info.get("author"),
                    commit_info.get("message"),
                    commit_info.get("repo"),
                    pipeline_id
                ))
            else:
                # Create new record with metadata
                db_conn.execute("""
                    INSERT INTO pipelines (pipeline_id, repository, branch, status, commit_id, commit_author, commit_message, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    pipeline_id,
                    commit_info.get("repo") or self.job_name,
                    params.get("BRANCH", "main"),
                    status,
                    commit_info.get("id"),
                    commit_info.get("author"),
                    commit_info.get("message"),
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
