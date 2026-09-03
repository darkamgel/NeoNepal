from unittest.mock import Mock

import pytest
from fastapi import HTTPException

from app.rate_limit import RateLimiter


def _request_from(ip: str):
    req = Mock()
    req.client.host = ip
    return req


def test_allows_up_to_max_calls():
    limiter = RateLimiter(max_calls=3, window_seconds=60)
    req = _request_from("1.2.3.4")
    for _ in range(3):
        limiter(req)  # should not raise


def test_blocks_the_call_after_max():
    limiter = RateLimiter(max_calls=2, window_seconds=60)
    req = _request_from("1.2.3.4")
    limiter(req)
    limiter(req)
    with pytest.raises(HTTPException) as exc_info:
        limiter(req)
    assert exc_info.value.status_code == 429


def test_tracks_clients_independently():
    limiter = RateLimiter(max_calls=1, window_seconds=60)
    limiter(_request_from("1.1.1.1"))
    limiter(_request_from("2.2.2.2"))  # different IP, should not raise


def test_old_calls_outside_window_are_forgotten(monkeypatch):
    limiter = RateLimiter(max_calls=1, window_seconds=10)
    req = _request_from("1.2.3.4")

    current_time = [1000.0]
    monkeypatch.setattr("app.rate_limit.time.monotonic", lambda: current_time[0])

    limiter(req)
    with pytest.raises(HTTPException):
        limiter(req)

    current_time[0] += 11  # past the window
    limiter(req)  # should not raise now
