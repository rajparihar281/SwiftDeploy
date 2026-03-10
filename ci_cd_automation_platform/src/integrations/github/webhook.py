def parse_webhook_payload(payload, event_type):
    """
    Parse a GitHub webhook payload for push and pull_request events.
    Metadata extracted: repo full name, branch, commit info, author.
    """
    data = {}
    if not payload:
        return data

    if event_type == "push":
        repo_data = payload.get("repository", {})
        data["repository"] = repo_data.get("full_name") or repo_data.get("name", "unknown-repo")
        
        # Branch extraction (e.g., refs/heads/main -> main)
        ref = payload.get("ref", "")
        data["branch"] = ref.replace("refs/heads/", "") if ref else "unknown-branch"
        
        head_commit = payload.get("head_commit") or {}
        data["commit_id"] = head_commit.get("id", "none")
        data["author"] = head_commit.get("author", {}).get("name", "unknown-author")
        data["commit_message"] = head_commit.get("message", "No commit message")
        
    elif event_type == "pull_request":
        repo_data = payload.get("repository", {})
        data["repository"] = repo_data.get("full_name") or repo_data.get("name", "unknown-repo")
        
        pr = payload.get("pull_request", {})
        head = pr.get("head", {})
        data["branch"] = head.get("ref", "unknown-branch")
        data["commit_id"] = head.get("sha", "none")
        data["author"] = pr.get("user", {}).get("login", "unknown-author")
        data["commit_message"] = pr.get("title", "No PR title")
        
    return data
