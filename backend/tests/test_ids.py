import re

from app.ids import generate_api_request_id

_REQUEST_ID_PATTERN = re.compile(r"^req_[A-Za-z0-9_-]{10,16}$")


def test_generate_api_request_id_format() -> None:
    request_id = generate_api_request_id()
    assert _REQUEST_ID_PATTERN.match(request_id)
    assert len(request_id) <= 20


def test_generate_api_request_id_is_unique() -> None:
    ids = {generate_api_request_id() for _ in range(100)}
    assert len(ids) == 100
