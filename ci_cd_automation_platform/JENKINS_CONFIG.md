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
3. Under **Build Triggers**, ensure **NONE** are checked (we use direct REST API triggers from the backend).
4. Under **Pipeline**, ensure:
   - **Definition**: `Pipeline script from SCM`
   - **SCM**: `Git`
   - **Repository URL**: `https://github.com/<your-username>/ci_cd_intelligence.git`
   - **Branch Specifier**: `*/main` (or `${BRANCH}` if you want to support multi-branch).
   - **Script Path**: `Jenkinsfile`
5. **Parameters**: Add the following String Parameters:
   - `COMMIT_ID`
   - `BRANCH`
   - `PIPELINE_ID`
   - `REPO_NAME`

## 3. GitHub Webhook Configuration
1. Go to your GitHub Repository -> **Settings** -> **Webhooks**.
2. Click **Add webhook**.
3. **Payload URL**: `https://jerold-nonimpressionistic-glynis.ngrok-free.dev/webhook/github`
   > [!IMPORTANT]
   > The backend handles both trailing and non-trailing slashes.
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
