from src import app

def test_home():
    client = app.app.test_client()
    response = client.get("/")
    assert response.status_code == 200
    assert b"CI/CD MVP App is running!" in response.data

def test_health():
    client = app.app.test_client()
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json["status"] == "OK"

def test_hello():
    client = app.app.test_client()
    response = client.get("/hello")
    assert response.status_code == 200
    assert "Hello" in response.json["message"]
