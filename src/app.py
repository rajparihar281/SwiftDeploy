from flask import Flask, jsonify

app = Flask(__name__)

@app.route("/")
def home():
    return "WEBHOOK CI/CD WORKING"

@app.route("/about")
def about():
    return jsonify({
        "project": "SwiftDeploy",
        "description": "CI/CD pipeline using Jenkins, Docker and GitHub",
        "author": "Raj Parihar"
    })
@app.route("/health")
def health():
    return jsonify(status="OK")

@app.route("/hello")
def hello():
    return jsonify(message="Hello gu kha from CI/CD pipeline!")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
