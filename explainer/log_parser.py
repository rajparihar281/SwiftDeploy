import re
from explainer.error_registry import get_suggestion

def generate_failure_signature(parsed_data):
    if not parsed_data:
        return None

    file = parsed_data.get("file")
    line = parsed_data.get("line")
    error_type = parsed_data.get("error_type")

    if file and line and error_type:
        return f"{file}:{line}:{error_type}"

    return None

def parse_pytest_failure(log_text: str):
    result = {
        "failed_test": None,
        "file": None,
        "line": None,
        "error_type": None,
        "suggestion": None
    }

    # Detect failed test name
    test_match = re.search(r"FAILED (.+?)::(.+?) ", log_text)
    if test_match:
        result["file"] = test_match.group(1)
        result["failed_test"] = test_match.group(2)

    # Detect file + line
    line_match = re.search(r"(tests[\\/].+?):(\d+):", log_text)
    if line_match:
        result["file"] = line_match.group(1)
        result["line"] = line_match.group(2)

    # Detect error type
    if "AssertionError" in log_text:
        result["error_type"] = "AssertionError"
    elif "ModuleNotFoundError" in log_text:
        result["error_type"] = "ModuleNotFoundError"
    elif "TypeError" in log_text:
        result["error_type"] = "TypeError"

    # Get intelligent suggestion
    if result["error_type"]:
        result["suggestion"] = get_suggestion(result["error_type"])

    return result