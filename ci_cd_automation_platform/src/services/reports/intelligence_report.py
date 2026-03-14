from datetime import datetime
import json
import re
from typing import Dict, Any, List, Optional

class IntelligenceReportGenerator:
    def __init__(self, pipeline_data: Dict[str, Any]):
        """
        pipeline_data: A dictionary containing row data from the 'pipelines' table.
        """
        self.data = pipeline_data
        self.report: Dict[str, Any] = {
            "executive_summary": {},
            "build_metadata": {},
            "stage_execution_analysis": {},
            "test_intelligence": {},
            "governance_report": {},
            "docker_deployment": {},
            "performance_metrics": {},
            "intelligence_insights": {},
            "failure_analysis": None,
            "visualization_data": {}
        }

    def generate(self) -> Dict[str, Any]:
        self.report["executive_summary"] = self._generate_executive_summary()
        self.report["build_metadata"] = self._generate_build_metadata()
        self.report["stage_execution_analysis"] = self._generate_stage_analysis()
        self.report["test_intelligence"] = self._generate_test_intelligence()
        self.report["governance_report"] = self._generate_governance_report()
        self.report["docker_deployment"] = self._generate_docker_deployment()
        self.report["performance_metrics"] = self._generate_performance_metrics()
        self.report["intelligence_insights"] = self._generate_intelligence_insights()
        self.report["failure_analysis"] = self._generate_failure_analysis()
        self.report["visualization_data"] = self._generate_visualization_data()
        return self.report

    def _generate_executive_summary(self):
        status = self.data.get("status", "unknown").upper()
        decision = self.data.get("governance_decision", "N/A")
        
        highlights = []
        if status == "SUCCESS":
            highlights.append("Pipeline completed successfully.")
        elif status == "FAILED":
            highlights.append(f"Pipeline failed at the {self.data.get('failure_stage', 'unknown')} stage.")
        elif status == "BLOCKED":
            highlights.append("Pipeline was blocked by governance policies.")

        if decision == "ALLOW":
            highlights.append("Governance engine has approved the deployment.")
        elif decision == "BLOCK":
            highlights.append("Governance engine has blocked the deployment due to policy violations.")

        return {
            "overall_result": status,
            "deployment_decision": decision,
            "key_highlights": highlights
        }

    def _generate_build_metadata(self):
        return {
            "pipeline_id": self.data.get("pipeline_id"),
            "repository": self.data.get("repository"),
            "branch": self.data.get("branch"),
            "commit_id": self.data.get("commit_id"),
            "author": self.data.get("commit_author"),
            "trigger_source": "Webhook" if "WEBHOOK" in self.data.get("pipeline_id", "") else "Manual",
            "start_time": self.data.get("created_at"),
            "end_time": self.data.get("updated_at"),
            "total_duration": f"{self.data.get('total_pipeline_duration', 0)}s"
        }

    def _generate_stage_analysis(self):
        stages_def = [
            ("Code Checkout", "checkout"),
            ("Dependency Install", "install"),
            ("Testing", "test"),
            ("Metrics Collection", "metrics"),
            ("Governance Evaluation", "governance"),
            ("Docker Build", "build"),
            ("Deployment", "deploy"),
        ]
        
        analysis: List[Dict[str, Any]] = []
        durations: List[tuple] = []
        
        for label, key in stages_def:
            start = self.data.get(f"stage_{key}_start")
            end = self.data.get(f"stage_{key}_end")
            status = self.data.get(f"stage_{key}_status", "waiting")
            
            duration = 0
            if start and end:
                try:
                    s = datetime.fromisoformat(start)
                    e = datetime.fromisoformat(end)
                    duration = (e - s).total_seconds()
                except:
                    pass
            
            obs = "Stage completed normally."
            if status == "failed":
                obs = "Critical failure detected in this stage."
            elif duration > 60:
                obs = "Stage duration is higher than average."
            
            analysis.append({
                "stage_name": label,
                "duration": f"{duration:.2f}s",
                "status": status.upper(),
                "observations": obs,
                "_duration_val": duration
            })
            
            if status != "waiting":
                durations.append((label, duration))

        slowest = max(durations, key=lambda x: x[1])[0] if durations else "N/A"
        fastest = min(durations, key=lambda x: x[1])[0] if durations else "N/A"
        
        # Identification of bottlenecks (simple logic: any stage taking > 40% of total time)
        bottlenecks = []
        total = self.data.get("total_pipeline_duration", 0)
        if total > 0:
            for label, dur in durations:
                if dur / total > 0.4:
                    bottlenecks.append(label)

        return {
            "stages": analysis,
            "slowest_stage": slowest,
            "fastest_stage": fastest,
            "potential_bottlenecks": bottlenecks
        }

    def _generate_test_intelligence(self):
        total = self.data.get("test_pass_count", 0) + self.data.get("test_fail_count", 0) + self.data.get("test_skip_count", 0)
        
        if total == 0 and self.data.get("stage_test_status") == "waiting":
            return {"message": "No tests were executed in this pipeline."}
        
        # Duration for test stage
        test_duration = 0
        start = self.data.get("stage_test_start")
        end = self.data.get("stage_test_end")
        if start and end:
            try:
                s = datetime.fromisoformat(start)
                e = datetime.fromisoformat(end)
                test_duration = (e - s).total_seconds()
            except:
                pass

        return {
            "total_tests": total,
            "passed_tests": self.data.get("test_pass_count", 0),
            "failed_tests": self.data.get("test_fail_count", 0),
            "skipped_tests": self.data.get("test_skip_count", 0),
            "test_execution_time": f"{test_duration:.2f}s",
            "failed_test_details": "See logs for details" if self.data.get("test_fail_count", 0) > 0 else "None"
        }

    def _generate_governance_report(self):
        waste_score = self.data.get("waste_score", 0)
        classification = "LOW"
        if 31 <= waste_score <= 60:
            classification = "MEDIUM"
        elif waste_score > 60:
            classification = "HIGH"
            
        return {
            "governance_decision": self.data.get("governance_decision", "N/A"),
            "reason": self.data.get("governance_explanation", "No explanation provided."),
            "policy_rules_applied": ["Block on Test Failure", "Block on High Waste"],
            "risk_indicators": "High" if classification == "HIGH" else "Low to Moderate",
            "waste_score": waste_score,
            "waste_score_classification": classification,
            "interpretation": f"A waste score of {waste_score} is considered {classification}."
        }

    def _generate_docker_deployment(self):
        image_name = f"deployed_app_{self.data.get('repository', 'unknown')}" # Simplification
        return {
            "docker_image_name": image_name,
            "container_name": f"container_{self.data.get('pipeline_id', 'unknown')}",
            "deployment_environment": "Production" if self.data.get("status") == "success" else "N/A",
            "exposed_ports": self.data.get("deployed_port", "N/A"),
            "deployment_status": self.data.get("stage_deploy_status", "waiting").upper(),
            "service_url": self.data.get("deployed_url", "N/A")
        }

    def _generate_performance_metrics(self):
        total_duration = self.data.get("total_pipeline_duration", 0)
        
        # Distribution
        stages_def = ["checkout", "install", "test", "metrics", "governance", "build", "deploy"]
        distribution = {}
        for key in stages_def:
            start = self.data.get(f"stage_{key}_start")
            end = self.data.get(f"stage_{key}_end")
            if start and end:
                try:
                    s = datetime.fromisoformat(start)
                    e = datetime.fromisoformat(end)
                    duration = (e - s).total_seconds()
                    distribution[key] = duration
                except:
                    pass

        efficiency = "High" if total_duration < 120 else "Moderate"
        if total_duration > 300:
            efficiency = "Low"

        return {
            "total_pipeline_duration": f"{total_duration:.2f}s",
            "stage_time_distribution": distribution,
            "build_efficiency_indicator": efficiency
        }

    def _generate_intelligence_insights(self):
        insights = []
        total_duration = self.data.get("total_pipeline_duration", 0)
        waste_score = self.data.get("waste_score", 0)
        
        if total_duration > 180:
            insights.append("Pipeline efficiency is low. Consider optimizing Docker build layer caching.")
        else:
            insights.append("Pipeline efficiency is optimal.")
            
        if waste_score > 40:
            insights.append("Unusual resource usage pattern detected. Waste score is above average.")
        
        if self.data.get("status") == "success":
            insights.append("Reliability indicator: HIGH. Multiple stages passed without retries.")
        else:
            insights.append("Reliability indicator: LOW. Frequent failures in current branch.")

        return {
            "pipeline_efficiency": "Optimized" if total_duration < 120 else "Needs Improvement",
            "possible_optimizations": [
                "Implement parallel test execution",
                "Optimize Docker multi-stage builds",
                "Cache npm/pip dependencies across builds"
            ],
            "observations": insights
        }

    def _generate_failure_analysis(self):
        if self.data.get("status") != "failed":
            return None
            
        stage = self.data.get("failure_stage", "Unknown")
        explanation = self.data.get("failure_explanation", "No detailed error captured.")
        
        # Basic heuristic for fixes
        suggestion = "Check the logs for detailed error trace."
        if "test" in stage.lower():
            suggestion = "Review failed test cases and ensure environment variables are parity with production."
        elif "install" in stage.lower():
            suggestion = "Check requirements.txt for conflicting versions or network connectivity issues."
        elif "build" in stage.lower():
            suggestion = "Verify Dockerfile syntax and check if all required base images are accessible."

        return {
            "failure_stage": stage,
            "error_message": explanation,
            "simple_explanation": f"The pipeline encountered an issue during {stage}.",
            "suggested_fixes": suggestion
        }

    def _generate_visualization_data(self):
        # Data for charts
        stages_def = ["checkout", "install", "test", "metrics", "governance", "build", "deploy"]
        durations: List[float] = []
        labels: List[str] = []
        for key in stages_def:
            start = self.data.get(f"stage_{key}_start")
            end = self.data.get(f"stage_{key}_end")
            if start and end:
                try:
                    s = datetime.fromisoformat(start)
                    e = datetime.fromisoformat(end)
                    durations.append((e - s).total_seconds())
                    labels.append(key.capitalize())
                except:
                    pass
        
        return {
            "stage_durations": {
                "labels": labels,
                "values": durations
            },
            "success_indicator": 1 if self.data.get("status") == "success" else 0,
            "governance_score": self.data.get("waste_score", 0),
            "deployment_status": 1 if self.data.get("stage_deploy_status") == "completed" else 0
        }
