import pytest
from fastapi import APIRouter, Depends, FastAPI
from fastapi.testclient import TestClient

from app.core.errors import BadRequestError
from app.core.pagination import Page, PageParams, SortField, page_params, parse_sort, sorting

router = APIRouter(prefix="/_p")
ALLOWED = ["name", "created_at"]


@router.get("/items")
async def _items(
    params: PageParams = Depends(page_params),
    sort: list[SortField] = Depends(sorting(ALLOWED, "-created_at")),
) -> dict[str, object]:
    page = Page[int].create(list(range(params.page_size)), total=45, params=params)
    return {"page": page.model_dump(), "sort": [s.model_dump() for s in sort]}


@pytest.fixture(autouse=True)
def _routes(app: FastAPI) -> None:
    app.include_router(router)


def test_page_math() -> None:
    params = PageParams(page=3, page_size=20)
    assert params.offset == 40
    page = Page[str].create(["a"], total=45, params=params)
    assert (page.pages, page.total, page.page) == (3, 45, 3)
    assert Page[str].create([], total=0, params=PageParams()).pages == 0


def test_defaults_and_bounds(client: TestClient) -> None:
    body = client.get("/_p/items").json()
    assert body["page"]["page"] == 1
    assert body["page"]["page_size"] == 20
    assert body["sort"] == [{"field": "created_at", "descending": True}]
    assert client.get("/_p/items?page_size=101").status_code == 422
    assert client.get("/_p/items?page=0").status_code == 422


def test_sort_parsing(client: TestClient) -> None:
    body = client.get("/_p/items?sort=name,-created_at").json()
    assert body["sort"] == [
        {"field": "name", "descending": False},
        {"field": "created_at", "descending": True},
    ]


def test_sort_rejects_fields_not_on_the_allow_list(client: TestClient) -> None:
    response = client.get("/_p/items?sort=password_hash")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_sort"
    assert parse_sort("name,,", ALLOWED, "-created_at") == [SortField(field="name")]
    with pytest.raises(BadRequestError):
        parse_sort("id; DROP TABLE users", ALLOWED, "name")
