from .waste_calculator import calculate_waste_score
from .policies import evaluate_policies

def evaluate_build(metrics, test_status):
    cpu = metrics["cpu"]
    memory = metrics["memory"]
    build_time = metrics["build_time"]

    waste_score = calculate_waste_score(cpu, memory, build_time)

    decision, violations = evaluate_policies(
        waste_score=waste_score,
        test_status=test_status
    )

    return {
        "waste_score": waste_score,
        "decision": decision,
        "violations": violations
    }