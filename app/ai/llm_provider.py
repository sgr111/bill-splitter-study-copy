"""
Shared dual-LLM provider with automatic Groq -> Gemini fallback.

Single source of truth for LLM instances used across the AI layer
(langchain_qa.py, langgraph_agent.py) — import `llm` from here instead of
constructing ChatGroq / ChatGoogleGenerativeAI separately in each file.

Any chain built with `prompt | llm` gets fallback for free: if the Groq
call raises, LangChain automatically retries the same input against
gemini_llm — no manual try/except needed at call sites.
"""
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI

from app.config import settings

groq_llm = ChatGroq(
    model="llama-3.1-8b-instant",
    api_key=settings.GROQ_API_KEY,
    temperature=0.3,
)

gemini_llm = ChatGoogleGenerativeAI(
    model="gemini-3.5-flash-lite",
    google_api_key=settings.GEMINI_API_KEY,
    temperature=0.3,
)

# Primary = Groq, automatic fallback = Gemini.
llm = groq_llm.with_fallbacks([gemini_llm])


def extract_text(content) -> str:
    """
    Normalize an LLM response's .content into plain text.

    Groq (and older Gemini models) return .content as a plain string.
    Newer Gemini 3.x models return .content as a list of content blocks
    instead — e.g. [{"type": "text", "text": "...", "extras": {...}}], a
    multi-part/"Interactions"-style format. Since `llm` here can be
    answered by either provider (Groq primary, Gemini on fallback), every
    call site must use this instead of touching response.content
    directly, or it'll break/silently misbehave depending on which
    provider actually served that particular call.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
            elif isinstance(block, str):
                parts.append(block)
        return "".join(parts)
    return str(content)