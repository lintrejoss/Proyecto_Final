import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from starlette.testclient import TestClient
from src.main import app
from src.auth.security import verify_password, hash_password

client = TestClient(app)


def test_health_endpoint():
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "online"
    assert data["timezone"] == "America/Bogota"


def test_argon2_hashing():
    pwd = "MiPasswordSeguro123!"
    h = hash_password(pwd)
    assert h.startswith("$argon2id$")
    assert verify_password(pwd, h) is True
    assert verify_password("Erronea", h) is False


def test_login_exitoso_todos_los_roles():
    cuentas = [
        ("estudiante@universidad.edu.co", "Estudiante123!", "estudiante"),
        ("docente@universidad.edu.co", "Docente123!", "docente"),
        ("responsable@universidad.edu.co", "Responsable123!", "responsable"),
        ("coordinacion@universidad.edu.co", "Coordinacion123!", "coordinacion")
    ]
    for email, pwd, rol in cuentas:
        res = client.post("/api/v1/auth/login", json={"email": email, "password": pwd})
        assert res.status_code == 200, f"Fallo login de {rol}"
        payload = res.json()
        assert "access_token" in payload
        assert payload["user"]["rol"] == rol


def test_login_credenciales_invalidas():
    res = client.post(
        "/api/v1/auth/login",
        json={"email": "estudiante@universidad.edu.co", "password": "PasswordIncorrecto"}
    )
    assert res.status_code == 401
    assert "detail" in res.json()


def test_me_con_token_valido():
    test_client = TestClient(app)
    res_login = test_client.post(
        "/api/v1/auth/login",
        json={"email": "estudiante@universidad.edu.co", "password": "Estudiante123!"}
    )
    token = res_login.json()["access_token"]

    res_me = test_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res_me.status_code == 200
    data = res_me.json()
    assert data["email"] == "estudiante@universidad.edu.co"
    assert data["nombre_completo"] == "Paulina Trejos"
    assert "password" not in data
    assert "password_hash" not in data


def test_me_sin_token_rechazado():
    fresh_client = TestClient(app)
    res = fresh_client.get("/api/v1/auth/me")
    assert res.status_code == 401


def test_vistas_web_login_y_redireccion():
    fresh_client = TestClient(app)
    # Sin sesión -> / redirige a /login (302)
    res_unauth = fresh_client.get("/", follow_redirects=False)
    assert res_unauth.status_code == 302
    assert res_unauth.headers["location"] == "/login"

    # Página de login renderiza 200
    res_login_page = fresh_client.get("/login")
    assert res_login_page.status_code == 200
    assert "Ingreso al Sistema" in res_login_page.text

    # Con sesión iniciada
    auth_client = TestClient(app)
    auth_client.post(
        "/api/v1/auth/login",
        json={"email": "estudiante@universidad.edu.co", "password": "Estudiante123!"}
    )
    res_dash = auth_client.get("/")
    assert res_dash.status_code == 200
    assert "Paulina Trejos" in res_dash.text
    assert "Estudiante" in res_dash.text


if __name__ == "__main__":
    print("Iniciando pruebas unitarias de Etapa 1...")
    test_health_endpoint()
    print("✓ test_health_endpoint OK")
    test_argon2_hashing()
    print("✓ test_argon2_hashing OK")
    test_login_exitoso_todos_los_roles()
    print("✓ test_login_exitoso_todos_los_roles OK")
    test_login_credenciales_invalidas()
    print("✓ test_login_credenciales_invalidas OK")
    test_me_con_token_valido()
    print("✓ test_me_con_token_valido OK")
    test_me_sin_token_rechazado()
    print("✓ test_me_sin_token_rechazado OK")
    test_vistas_web_login_y_redireccion()
    print("✓ test_vistas_web_login_y_redireccion OK")
    print("\n🎉>>> TODOS LOS 7 TESTS DE LA ETAPA 1 PASARON EXITOSAMENTE <<<")

