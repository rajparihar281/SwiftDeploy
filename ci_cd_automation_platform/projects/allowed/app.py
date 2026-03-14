from flask import Flask, jsonify
import os
import datetime

app = Flask(__name__)

@app.route('/')
def hello_world():
    build_number = os.getenv('BUILD_NUMBER', 'N/A')
    commit_id = os.getenv('GIT_COMMIT', 'N/A')
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    return f"""
    <html>
    <head>
        <title>Project Deployed</title>
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #0f172a; color: white; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }}
            .card {{ background: rgba(30, 41, 59, 0.7); border: 1px solid rgba(255, 255, 255, 0.1); padding: 40px; border-radius: 20px; box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04); backdrop-filter: blur(10px); text-align: center; }}
            h1 {{ color: #00f2ff; margin-bottom: 24px; }}
            .success-msg {{ font-size: 18px; margin-bottom: 32px; color: #94a3b8; }}
            .meta {{ font-family: monospace; color: #00ffa3; text-align: left; background: rgba(0, 0, 0, 0.2); padding: 16px; border-radius: 8px; font-size: 14px; }}
            .footer {{ margin-top: 32px; font-size: 12px; color: #64748b; }}
        </style>
    </head>
    <body>
        <div class="card">
            <h1>Hello World</h1>
            <p class="success-msg">Application deployed successfully via CI/CD pipeline.</p>
            <div class="meta">
                <div>Build Number: {build_number}</div>
                <div>Commit ID: {commit_id}</div>
                <div>Deployment Time: {timestamp}</div>
            </div>
            <p class="footer">SwiftDeploy Premium CI/CD Governance Engine</p>
        </div>
    </body>
    </html>
    """

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
