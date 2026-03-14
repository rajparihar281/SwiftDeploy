import pytest # type: ignore
import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from services.reports.intelligence_report import IntelligenceReportGenerator # type: ignore

def test_intelligence_report_structure():
    mock_data = {
        "pipeline_id": "WEBHOOK-12345",
        "repository": "test-repo",
        "branch": "main",
        "commit_id": "abcdef123456",
        "commit_author": "Test Author",
        "status": "success",
        "created_at": "2026-03-14T10:00:00",
        "updated_at": "2026-03-14T10:05:00",
        "total_pipeline_duration": 300.0,
        "waste_score": 45.5,
        "governance_decision": "ALLOW",
        "governance_explanation": "All clear",
        "test_pass_count": 10,
        "test_fail_count": 0,
        "test_skip_count": 1,
        "stage_test_status": "completed",
        "stage_test_start": "2026-03-14T10:01:00",
        "stage_test_end": "2026-03-14T10:02:00",
        "stage_deploy_status": "completed",
        "deployed_port": 6001,
        "deployed_url": "http://localhost:6001"
    }
    
    generator = IntelligenceReportGenerator(mock_data)
    report = generator.generate()
    
    # Verify all sections exist
    sections = [
        "executive_summary", "build_metadata", "stage_execution_analysis",
        "test_intelligence", "governance_report", "docker_deployment",
        "performance_metrics", "intelligence_insights", "visualization_data"
    ]
    for section in sections:
        assert section in report, f"Missing section: {section}"
        
    # Verify specific details
    assert report["executive_summary"]["overall_result"] == "SUCCESS"
    assert report["governance_report"]["waste_score_classification"] == "MEDIUM"
    assert report["test_intelligence"]["total_tests"] == 11
    assert "efficiency" in report["performance_metrics"] or "build_efficiency_indicator" in report["performance_metrics"]

def test_failure_analysis():
    mock_data = {
        "status": "failed",
        "failure_stage": "Testing",
        "failure_explanation": "Unit test failed in Auth module"
    }
    
    generator = IntelligenceReportGenerator(mock_data)
    report = generator.generate()
    
    assert report["failure_analysis"] is not None
    assert report["failure_analysis"]["failure_stage"] == "Testing"
    assert "suggested_fixes" in report["failure_analysis"]

if __name__ == "__main__":
    test_intelligence_report_structure()
    test_failure_analysis()
    print("All tests passed!")
