"""In-memory per-IP rate limiting for endpoints that trigger real external
API calls (Planetary Computer, Overpass, Open-Meteo). Without this, a
scripted client — or just an eager user — hammering `/cycle/run` or
`/glaciers/{id}/analyze` risks getting this app's IP rate-limited or
banned from those free, keyless services, which would break the app for
every user, not just the caller.

Deliberately simple (a dict in process memory) rather than pulling in
Redis or a library — appropriate for this prototype's single-process
scale. Two real limits this implies, both documented rather than hidden:

- **Per-process, not shared.** If this app ever runs with more than one
  worker process, each process enforces its own limit independently — the
  effective limit is (this number) × (worker count). See
  docs/DEPLOYMENT.md. The same file-lock pattern used for the scheduler
  (scheduler_lock.py) doesn't help here since rate limiting needs to
  coordinate live counts, not just pick one leader.
- **Per-IP, not global.** A well-distributed abusive client (many IPs)
  isn't stopped by this. Real deployment should add a global budget cap
  alongside the per-IP one.
"""

import time

from fastapi import HTTPException, Request


class RateLimiter:
    """FastAPI dependency: allows `max_calls` within a rolling `window_seconds`
    per client IP. Raises 429 with a Retry-After-style message once exceeded.
    """

    def __init__(self, max_calls: int, window_seconds: int):
        self.max_calls = max_calls
        self.window_seconds = window_seconds
        self._calls: dict[str, list[float]] = {}

    def __call__(self, request: Request) -> None:
        client_key = request.client.host if request.client else "unknown"
        now = time.monotonic()
        cutoff = now - self.window_seconds

        timestamps = [t for t in self._calls.get(client_key, []) if t > cutoff]

        if len(timestamps) >= self.max_calls:
            retry_after = round(self.window_seconds - (now - timestamps[0]))
            raise HTTPException(
                status_code=429,
                detail=(
                    f"Rate limit exceeded: max {self.max_calls} requests per "
                    f"{self.window_seconds}s. Try again in ~{max(retry_after, 1)}s."
                ),
            )

        timestamps.append(now)
        self._calls[client_key] = timestamps
