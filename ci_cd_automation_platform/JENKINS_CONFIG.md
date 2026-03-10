# Jenkins Configuration Guide for Auto-Trigger

To enable automatic builds when code is pushed to GitHub, follow these configuration steps.

## 1. Jenkins Plugins
Ensure the following plugins are installed in Jenkins:
- **Git Plugin**: Base plugin for Git integration.
- **GitHub Integration Plugin**: Required for handling GitHub webhooks.
- **Pipeline: Stage View Plugin**: Required for the dashboard to show stage-level progress.

## 2. Jenkins Job Configuration
1. Open your Jenkins job (e.g., `CI-CD-Intelligence-Test`).
2. Go to **Configure**.
3. Under **Build Triggers**, check:
   - `[x] GitHub hook trigger for GITScm polling`
4. Under **Pipeline**, ensure:
   - **Definition**: `Pipeline script from SCM`
   - **SCM**: `Git`
   - **Repository URL**: Your GitHub repo URL.
   - **Script Path**: `Jenkinsfile` (verify if it is in the root or `deployment/Jenkinsfile`).

## 3. GitHub Webhook Configuration
1. Go to your GitHub Repository -> **Settings** -> **Webhooks**.
2. Click **Add webhook**.
3. **Payload URL**: `http://<YOUR_JENKINS_SERVER>/github-webhook/`
   > [!IMPORTANT]
   > The trailing slash `/` is required.
4. **Content type**: `application/json`
5. **Which events would you like to trigger this webhook?**: `Just the push event.`
6. Click **Add webhook**.

## 4. Verification
- Push a commit to your repository.
- Check GitHub Webhook delivery (Settings -> Webhooks -> Click on your webhook -> Recent Deliveries). It should show a grey checkmark or green tick (HTTP 200).
- Jenkins should automatically start a new build.
- The Dashboard should now show this build in the "Active Pipelines" section.

## Backend Environment Variables
Ensure your backend has the following environment variables set (or updated in `app.py`/`jenkins_service.py`):
- `JENKINS_URL`: e.g., `http://localhost:8080/`
- `JENKINS_USER`: Your Jenkins username.
- `JENKINS_TOKEN`: Your Jenkins API Token (obtain from User -> Settings -> API Token).
- `JENKINS_JOB_NAME`: The name of your Jenkins job.
