ERROR_SUGGESTIONS = {
    "AssertionError": "Check expected vs actual values in your test assertion.",
    "ModuleNotFoundError": "Make sure required packages are installed and virtual environment is activated.",
    "TypeError": "Check function arguments and data types being passed."
}


def get_suggestion(error_type: str):
    return ERROR_SUGGESTIONS.get(
        error_type,
        "Review the error message and stack trace for root cause."
    )