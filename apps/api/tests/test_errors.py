import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel, EmailStr

from app.core.errors import ConflictError, NotFoundError, PermissionDeniedError

router = APIRouter(prefix="/_t")


class Body(BaseModel):
    email: EmailStr
    password: str


@router.get("/not-found")
async def _not_found() -> None:
    raise NotFoundError("Invoice not found.")


@router.get("/forbidden")
async def _forbidden() -> None:
    raise PermissionDeniedError("You cannot do that.")


@router.get("/conflict")
async def _conflict() -> None:
    raise ConflictError("Already exists.", code="duplicate_name")


@router.get("/crash")
async def _crash() -> None:
    raise RuntimeError("secret internal detail")


@router.post("/body")
async def _body(body: Body) -> None:
    return None


@pytest.fixture(autouse=True)
def _routes(app: FastAPI) -> None:
    app.include_router(router)


def test_app_errors_use_standard_shape(client: TestClient) -> None:
    response = client.get("/_t/not-found")
    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "not_found"
    assert error["message"] == "Invoice not found."
    assert error["request_id"] == response.headers["X-Request-ID"]


@pytest.mark.parametrize(
    ("path", "status", "code"),
    [("/_t/forbidden", 403, "forbidden"), ("/_t/conflict", 409, "duplicate_name")],
)
def test_other_app_errors(client: TestClient, path: str, status: int, code: str) -> None:
    response = client.get(path)
    assert response.status_code == status
    assert response.json()["error"]["code"] == code


def test_unknown_route_and_wrong_method(client: TestClient) -> None:
    assert client.get("/nope").json()["error"]["code"] == "not_found"
    response = client.post("/_t/not-found")
    assert response.status_code == 405
    assert response.json()["error"]["code"] == "method_not_allowed"


def test_validation_error_lists_fields_and_never_echoes_input(client: TestClient) -> None:
    response = client.post("/_t/body", json={"email": "not-an-email", "password": "hunter2-secret"})
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert {d["field"] for d in error["details"]} == {"body.email"}
    assert "hunter2-secret" not in response.text


def test_unhandled_exception_is_a_clean_500(client: TestClient) -> None:
    response = client.get("/_t/crash")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"
    assert "secret internal detail" not in response.text
    assert response.json()["error"]["request_id"]
    assert response.headers["X-Request-ID"]
