"""
Dedicated tests for the Groq -> Gemini fallback wired via
app.ai.llm_provider.llm = groq_llm.with_fallbacks([gemini_llm]).

Quota-friendly design: only ONE test (test_ask_question_falls_back_to_...)
makes a real Gemini call, as an end-to-end sanity check. The other two
mock Gemini's response too — they only need to prove that (a) Groq
failing triggers a call to Gemini and (b) the response gets processed
correctly, not that Gemini's real API is reachable. This keeps repeated
runs from tripping the Gemini free-tier per-minute quota.
"""
import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import AIMessage

from app.ai.llm_provider import groq_llm

pytestmark = pytest.mark.asyncio


async def setup_group_with_expense(client, headers):
    r = await client.post("/groups", json={"name": "Fallback Test Group"}, headers=headers)
    group_id = r.json()["id"]
    await client.post("/expenses", json={
        "group_id": group_id,
        "description": "Lunch",
        "total_amount": 400.0,
        "split_type": "equal"
    }, headers=headers)
    return group_id


def _broken_groq():
    """
    Context manager: makes every ChatGroq instance's ainvoke() raise,
    forcing fallback to Gemini.

    Patched at the CLASS level (ChatGroq), not the instance (groq_llm),
    deliberately — Pydantic overrides __delattr__ on model instances,
    which breaks patch.object()'s cleanup when the instance itself is
    patched. Patching the class sidesteps that.
    """
    return patch.object(
        ChatGroq, "ainvoke", AsyncMock(side_effect=Exception("Simulated Groq outage"))
    )


def _mocked_gemini(content: str):
    """
    Context manager: makes every ChatGoogleGenerativeAI instance's
    ainvoke() return a fixed, fake successful response — no real network
    call to Gemini. Used to verify fallback ROUTING and response
    PARSING (does extract_text() handle it, does the endpoint return
    200) without spending real Gemini quota on every test run.
    """
    return patch.object(
        ChatGoogleGenerativeAI, "ainvoke", AsyncMock(return_value=AIMessage(content=content))
    )


async def test_mock_actually_breaks_groq(client: AsyncClient, auth_headers):
    """Sanity check on the mock itself — confirms patch.object really
    makes groq_llm.ainvoke raise, so a false-positive pass elsewhere
    (mock silently not applied) can't hide a real fallback bug."""
    with _broken_groq():
        with pytest.raises(Exception, match="Simulated Groq outage"):
            await groq_llm.ainvoke("test prompt")


async def test_categorize_falls_back_to_gemini_when_groq_fails(client: AsyncClient, auth_headers):
    """Gemini mocked — verifies routing + response parsing only, no real API call."""
    with _broken_groq(), _mocked_gemini(content="Food"):
        response = await client.post("/ai/categorize", json={
            "description": "Dinner at Barbeque Nation"
        }, headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["category"] == "Food"


async def test_ask_question_falls_back_to_gemini_when_groq_fails(client: AsyncClient, auth_headers):
    """
    The ONE real end-to-end test — Gemini is NOT mocked here, this
    actually calls the live Gemini API. Keep this as the single source
    of truth that the fallback works against the real provider, not
    just against a mock.
    """
    group_id = await setup_group_with_expense(client, auth_headers)

    with _broken_groq():
        response = await client.post("/ai/ask", json={
            "group_id": group_id,
            "question": "How much total has been spent?"
        }, headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert len(data["answer"]) > 0


async def test_agent_falls_back_to_gemini_when_groq_fails(client: AsyncClient, auth_headers):
    """Gemini mocked — verifies routing + response parsing only, no real API call."""
    group_id = await setup_group_with_expense(client, auth_headers)

    with _broken_groq(), _mocked_gemini(content="Mocked agent report."):
        response = await client.post(f"/ai/agent/{group_id}", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["final_report"] == "Mocked agent report."