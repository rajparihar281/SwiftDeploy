import yaml
import os

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.yaml")

def load_config():
    with open(CONFIG_PATH, "r") as file:
        return yaml.safe_load(file)

def evaluate_policies(waste_score, test_status):
    config = load_config()
    thresholds = config["thresholds"]
    policies = config["policies"]

    violations = []

    if policies["block_on_test_failure"] and test_status != "PASSED":
        violations.append("Test failure detected")

    if policies["block_on_high_waste"] and waste_score > thresholds["waste_score_max"]:
        violations.append("Waste score exceeded threshold")

    decision = "BLOCK" if violations else "ALLOW"

    return decision, violations