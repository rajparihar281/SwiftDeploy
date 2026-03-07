def parse_webhook_payload(payload, event_type):
    """
    Parse a GitHub webhook payload.
    Supports 'push' and 'pull_request' events.
    """
    data = {}
    if event_type == "push":
        data["repository"] = payload.get("repository", {}).get("name", "")
        data["branch"] = payload.get("ref", "").replace("refs/heads/", "")
        head_commit = payload.get("head_commit", {})
        data["commit_id"] = head_commit.get("id", "")
        data["author"] = head_commit.get("author", {}).get("name", "")
        data["commit_message"] = head_commit.get("message", "")
        
    elif event_type == "pull_request":
        data["repository"] = payload.get("repository", {}).get("name", "")
        pr = payload.get("pull_request", {})
        data["branch"] = pr.get("head", {}).get("ref", "")
        data["commit_id"] = pr.get("head", {}).get("sha", "")
        data["author"] = pr.get("user", {}).get("login", "")
        data["commit_message"] = pr.get("title", "")
        
    return data
