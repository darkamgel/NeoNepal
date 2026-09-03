import pytest

from app import scheduler_lock


@pytest.fixture(autouse=True)
def _reset_lock_state(tmp_path, monkeypatch):
    # Point at a throwaway file per test and reset the held-fd global so
    # tests don't leak locks into each other or the real project lock file.
    monkeypatch.setattr(scheduler_lock, "_LOCK_PATH", str(tmp_path / "test.lock"))
    monkeypatch.setattr(scheduler_lock, "_lock_file", None)
    yield
    if scheduler_lock._lock_file:
        scheduler_lock._lock_file.close()


def test_first_acquire_succeeds():
    assert scheduler_lock.acquire() is True


def test_second_acquire_on_same_lock_fails_while_first_still_held():
    assert scheduler_lock.acquire() is True
    # A second attempt (simulating a second worker process) must not also
    # succeed while the first caller's file descriptor is still open.
    assert scheduler_lock.acquire() is False
