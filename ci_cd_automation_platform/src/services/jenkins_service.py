import os
from datetime import datetime
from integrations.jenkins.client import JenkinsClient

class JenkinsService:
    def __init__(self):
        self.url = os.getenv("JENKINS_URL", "http://localhost:8080/")
        self.user = os.getenv("JENKINS_USER", "admin")
        self.token = os.getenv("JENKINS_TOKEN", "114d154f42f2e6dd30a9db042b6fd36c98")
        self.job_name = os.getenv("JENKINS_JOB_NAME", "CI-CD-Intelligence-Test")
        self.client = JenkinsClient(self.url, self.user, self.token)

    def sync_pipelines(self):
        """Fetch latest builds and map them to our internal pipeline schema."""
        raw_builds = self.client.get_build_list(self.job_name)
        pipelines = []
        
        for build in raw_builds[:10]: # Process latest 10 builds
            build_num = build['number']
            wf_data = self.client.get_pipeline_wf_api(self.job_name, build_num)
            
            pipeline = {
                "pipeline_id": f"JNK-{build_num}",
                "repository": self.job_name, # Fallback if repository name isn't in build params
                "status": self._map_status(build),
                "created_at": self._format_ts(build.get("timestamp")),
                "total_pipeline_duration": build.get("duration", 0) / 1000.0, # Jenkins is in ms
                "stages": self._map_stages(wf_data) if wf_data else []
            }
            pipelines.append(pipeline)
            
        return pipelines

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
            return datetime.utcnow().isoformat()
        return datetime.fromtimestamp(ts_ms / 1000.0).isoformat()

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
