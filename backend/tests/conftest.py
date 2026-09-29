import os

import pytest

# Point the app at the test database before any settings are cached.
_test_url = os.environ.get("TEST_DATABASE_URL")
if _test_url:
    os.environ["DATABASE_URL"] = _test_url


@pytest.fixture(scope="session", autouse=True)
def _migrate_database():
    if not _test_url:
        yield
        return
    import asyncio

    from app.startup import run_migrations

    asyncio.run(run_migrations())
    yield


@pytest.fixture(autouse=True)
async def _flush_notifications():
    yield
    from app.services.notifications.dispatcher import flush_notifications

    await flush_notifications()


@pytest.fixture(autouse=True)
def _disable_rate_limiter():
    from app.security.rate_limit import limiter

    previous = limiter.enabled
    limiter.enabled = False
    limiter.reset()
    yield
    limiter.enabled = previous
    limiter.reset()
