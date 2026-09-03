"""Guards against the periodic risk-recompute job running more than once
per machine.

APScheduler's BackgroundScheduler runs in-process. That's invisible with
one `uvicorn` process (dev, or `--workers 1`), but the instant this app
runs with more than one worker process — the normal way to scale a FastAPI
app in production (`gunicorn -w 4 ...`) — every worker starts its own
scheduler, and the "every 5 minutes" job actually fires N times in
parallel: N x the real Planetary Computer/Open-Meteo calls, and N processes
racing to write to the same SQLite file.

This is a single-machine stopgap, not a substitute for the real production
fix (move the scheduler to one dedicated worker process/cron job, outside
the web-serving processes — see docs/DEPLOYMENT.md). It uses a plain
`flock` on a lock file: the first process to start wins and keeps running
the schedule; every other process on the same machine detects the lock is
held and simply skips starting its own scheduler (the API itself, and the
manual `/cycle/run` trigger, work identically in every process regardless).

POSIX-only (`fcntl`). On a platform without it, fails open with a logged
warning — acceptable for this prototype's actual deployment targets, not
appropriate to rely on for a real multi-worker production rollout.
"""

import logging
import os

logger = logging.getLogger("neonepal.scheduler_lock")

_LOCK_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".scheduler.lock")
_lock_file = None  # kept open for the process lifetime; closing releases the flock


def acquire() -> bool:
    global _lock_file
    try:
        import fcntl
    except ImportError:
        logger.warning(
            "fcntl unavailable on this platform — cannot coordinate the scheduler "
            "across worker processes. Fine for a single-worker prototype; do not "
            "run multiple workers in production without a real fix (see docs/DEPLOYMENT.md)."
        )
        return True

    fh = open(_LOCK_PATH, "w")
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        fh.close()
        return False

    _lock_file = fh  # keep the fd open so the lock is held for the process lifetime
    return True
