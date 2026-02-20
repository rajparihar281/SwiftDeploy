ERROR_PATTERNS = {
    "ModuleNotFoundError": {
        "explanation": "A required Python module is missing.",
        "suggestion": "Add the missing module to requirements.txt and reinstall dependencies."
    },
    "ImportError": {
        "explanation": "There is a problem importing a Python module.",
        "suggestion": "Check module paths and ensure all dependencies are installed."
    },
    "Address already in use": {
        "explanation": "The application port is already occupied.",
        "suggestion": "Stop the process using the port or change the port configuration."
    },
    "docker build failed": {
        "explanation": "Docker image build failed during the pipeline.",
        "suggestion": "Inspect the Dockerfile and ensure all dependencies and paths are correct."
    },
    "pytest failed": {
        "explanation": "One or more unit tests failed.",
        "suggestion": "Review test output and fix failing test cases."
    }
}