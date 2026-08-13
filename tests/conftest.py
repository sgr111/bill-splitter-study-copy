import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.main import app
from app.dependencies import get_db
from app.config import settings

TEST_DATABASE_URL = settings.DATABASE_URL


@pytest_asyncio.fixture(scope="function")
async def db_engine():
    """
    One engine PER TEST FUNCTION — not a global singleton, not one
    engine per DB request either.

    pytest-asyncio gives each test function its own event loop by
    default (function scope). An engine built once at import time (the
    original attempted fix) ends up bound to whichever test's loop
    happened to be running when its pool first opened a connection —
    every later test then tries to reuse pooled connections that
    belong to an already-closed loop, causing "attached to a different
    loop" / "Event loop is closed" errors.

    Building the engine inside a function-scoped fixture keeps it tied
    to the CURRENT test's own loop, and disposing it in teardown stops
    any connection from leaking into the next test's loop. Multiple DB
    calls made WITHIN one test (e.g. register -> login -> create group
    -> add expense) still share this same engine's connection pool, so
    the original per-REQUEST connection overhead (a fresh TCP+SSL+auth
    handshake to Neon on every single API call) is still avoided — we
    just don't try to share the pool ACROSS tests/loops anymore.
    """
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"ssl": "require"},
        pool_pre_ping=True,
    )
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def client(db_engine):
    session_factory = async_sessionmaker(
        bind=db_engine, class_=AsyncSession, expire_on_commit=False
    )

    async def override_get_db():
        async with session_factory() as session:
            try:
                yield session
            finally:
                await session.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest_asyncio.fixture(scope="function")
async def registered_user(client):
    import uuid
    unique_email = f"testuser_{uuid.uuid4().hex[:8]}@example.com"
    payload = {
        "name": "Test User",
        "email": unique_email,
        "password": "testpass123"
    }
    await client.post("/auth/register", json=payload)
    return payload


@pytest_asyncio.fixture(scope="function")
async def auth_headers(client, registered_user):
    response = await client.post("/auth/login", json={
        "email": registered_user["email"],
        "password": registered_user["password"]
    })
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}