import requests
import json
import time

class JenkinsClient:
    def __init__(self, url, user, token):
        self.url = url
        self.user = user
        self.token = token
        self.auth = (self.user, self.token) if self.user and self.token else None

    def trigger_build(self, job_name, params=None):
        """Trigger a Jenkins build with optional parameters."""
        build_url = f"{self.url}/job/{job_name}/build"
        if params:
            build_url = f"{self.url}/job/{job_name}/buildWithParameters"
            response = requests.post(build_url, auth=self.auth, data=params)
        else:
            response = requests.post(build_url, auth=self.auth)
        
        if response.status_code in [200, 201]:
            print(f"[Jenkins] Triggered build for {job_name} successfully.")
            return True
        else:
            print(f"[Jenkins] Failed to trigger build: {response.text}")
            return False

    def get_build_status(self, job_name, build_number):
        """Get the status of a specific build."""
        status_url = f"{self.url}/job/{job_name}/{build_number}/api/json"
        response = requests.get(status_url, auth=self.auth)
        if response.status_code == 200:
            data = response.json()
            return {
                "building": data.get("building"),
                "result": data.get("result"),
                "timestamp": data.get("timestamp"),
                "duration": data.get("duration")
            }
        return None

    def get_console_logs(self, job_name, build_number):
        """Get the console logs of a specific build."""
        log_url = f"{self.url}/job/{job_name}/{build_number}/consoleText"
        response = requests.get(log_url, auth=self.auth)
        if response.status_code == 200:
            return response.text
        return None

    def get_build_list(self, job_name):
        """Fetch the list of latest builds for a specific job."""
        api_url = f"{self.url}/job/{job_name}/api/json?tree=builds[number,url,result,timestamp,duration,building]"
        response = requests.get(api_url, auth=self.auth)
        if response.status_code == 200:
            return response.json().get("builds", [])
        return []

    def get_pipeline_wf_api(self, job_name, build_number):
        """Fetch detailed pipeline stage information using the Workflow API."""
        # This requires the 'Pipeline: Stage View' plugin
        api_url = f"{self.url}/job/{job_name}/{build_number}/wfapi/describe"
        response = requests.get(api_url, auth=self.auth)
        if response.status_code == 200:
            return response.json()
        return None
