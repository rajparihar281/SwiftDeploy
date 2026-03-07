import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

from app import app
import json

client = app.test_client()

payload = {
    "repository": {"name": "ci_cd_intelligence"},
    "ref": "refs/heads/main",
    "head_commit": {
        "id": "1234567890abcdef",
        "author": {"name": "Test User"},
        "message": "Test commit"
    }
}

response = client.post(
    "/webhook/github",
    data=json.dumps(payload),
    headers={"Content-Type": "application/json", "X-GitHub-Event": "push"}
)

print(f"Status Code: {response.status_code}")
print(f"Response: {response.data.decode('utf-8')}")
