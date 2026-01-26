from flask import Flask, jsonify

app = Flask(__name__)

@app.route("/")
def home():
    return "Omygawd its working"

@app.route("/health")
def health():
    return jsonify(status="OK")

@app.route("/hello")
def hello():
    return jsonify(message="Hello from CI/CD pipeline!")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
