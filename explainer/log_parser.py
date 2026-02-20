from .error_registry import ERROR_PATTERNS


class LogExplainer:

    @staticmethod
    def analyze_log(log_text):
        for pattern, details in ERROR_PATTERNS.items():
            if pattern.lower() in log_text.lower():
                return {
                    "error_detected": pattern,
                    "explanation": details["explanation"],
                    "suggestion": details["suggestion"]
                }

        return None