"""
LangChain <-> llm-observability bridge, adapted for Bill Splitter.

Same core problem as Activity Tracker's version: llm_observability's
track_llm_call() is a function wrapper that times a callable you hand it,
but LangChain's callback hooks fire AFTER the real model call already
happened — so there's no "not yet run" callable to hand it. This bridges
the two by timing the call ourselves and reusing track_llm_call() purely
for its persistence logic (see the on_llm_end/on_llm_error methods).

TWO THINGS ARE DIFFERENT FROM ACTIVITY TRACKER'S VERSION, BOTH BECAUSE
BILL SPLITTER HAS A Groq->Gemini FALLBACK (llm_provider.py's
`llm = groq_llm.with_fallbacks([gemini_llm])`), WHICH ACTIVITY TRACKER
DOESN'T:

1. `provider` is NOT hardcoded. A single logical call can be served by
   EITHER Groq or Gemini depending on whether Groq failed. When
   with_fallbacks() retries against Gemini, LangChain fires this
   callback's hooks AGAIN for the fallback attempt — so a Groq failure
   followed by a successful Gemini response naturally produces TWO log
   entries: one failed (provider=groq), one succeeded (provider=gemini).
   That's not a bug — it's the fallback event, correctly captured.
   Provider is detected per-call from LangChain's `serialized` payload
   (which model class is actually being invoked right now), not assumed.

2. Response text is extracted via llm_provider.extract_text(), not
   response.content directly — Gemini 3.x returns content as a list of
   blocks, not a plain string, and this callback must handle whichever
   provider actually answered a given call.
"""
import logging
import time
from typing import Any, Dict, Optional
from uuid import UUID

from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.outputs import LLMResult

from llm_observability import track_llm_call
from app.ai.llm_provider import extract_text

logger = logging.getLogger("bill_splitter.observability")


def _detect_provider(serialized: Optional[dict]) -> str:
    """
    Identify which underlying provider LangChain is actually invoking for
    THIS callback firing, from the serialized class-path info LangChain
    passes into on_chat_model_start/on_llm_start. Falls back to
    "unknown" rather than guessing, so a log row never silently claims
    the wrong provider.
    """
    if not serialized:
        return "unknown"
    id_path = serialized.get("id", [])
    id_str = ".".join(str(p) for p in id_path).lower()
    if "groq" in id_str:
        return "groq"
    if "google_genai" in id_str or "generativeai" in id_str:
        return "gemini"
    return "unknown"


class ObservabilityCallback(AsyncCallbackHandler):
    def __init__(
        self,
        *,
        project: str = "bill-splitter",
        feature: str,
        prompt_name: Optional[str] = None,
        prompt_version: Optional[str] = None,
        db_session=None,  # SQLAlchemy AsyncSession, or None for console/JSON fallback
    ):
        self.project = project
        self.feature = feature
        self.prompt_name = prompt_name
        self.prompt_version = prompt_version
        self.db_session = db_session
        self._start_times: Dict[UUID, float] = {}
        self._prompt_text: Dict[UUID, str] = {}
        self._provider: Dict[UUID, str] = {}

    # ── start hooks: record accurate timing + which provider is being tried ──
    async def on_chat_model_start(self, serialized, messages, *, run_id, **kwargs) -> None:
        self._start_times[run_id] = time.monotonic()
        self._provider[run_id] = _detect_provider(serialized)
        try:
            flat = [m.content for turn in messages for m in turn]
            self._prompt_text[run_id] = "\n".join(
                extract_text(c) for c in flat
            )[:4000]
        except Exception:
            pass  # best-effort only — never let logging setup break the call

    async def on_llm_start(self, serialized, prompts, *, run_id, **kwargs) -> None:
        self._start_times.setdefault(run_id, time.monotonic())
        self._provider.setdefault(run_id, _detect_provider(serialized))
        if prompts:
            self._prompt_text.setdefault(run_id, str(prompts[0])[:4000])

    # ── end hooks: reuse track_llm_call's persistence path ──
    async def on_llm_end(self, response: LLMResult, *, run_id, **kwargs) -> None:
        start = self._start_times.pop(run_id, None)
        elapsed_ms = int((time.monotonic() - start) * 1000) if start is not None else None
        prompt_text = self._prompt_text.pop(run_id, None)
        provider = self._provider.pop(run_id, "unknown")

        text = ""
        if response.generations and response.generations[0]:
            raw = response.generations[0][0].text
            text = extract_text(raw) if raw is not None else ""

        model_name = None
        if response.llm_output:
            model_name = response.llm_output.get("model_name") or response.llm_output.get("model")

        input_tokens = output_tokens = None
        if response.llm_output and "token_usage" in (response.llm_output or {}):
            usage = response.llm_output["token_usage"] or {}
            input_tokens = usage.get("prompt_tokens") or usage.get("prompt_token_count") or usage.get("input_tokens")
            output_tokens = usage.get("completion_tokens") or usage.get("candidates_token_count") or usage.get("output_tokens")

        async def _already_resolved(prompt: Optional[str] = None) -> str:
            return text

        await self._log(
            _already_resolved,
            prompt_text=prompt_text,
            model=model_name,
            latency_ms=elapsed_ms,
            provider=provider,
        )

    async def on_llm_error(self, error: BaseException, *, run_id, **kwargs) -> None:
        start = self._start_times.pop(run_id, None)
        elapsed_ms = int((time.monotonic() - start) * 1000) if start is not None else None
        prompt_text = self._prompt_text.pop(run_id, None)
        provider = self._provider.pop(run_id, "unknown")

        async def _reraise(prompt: Optional[str] = None):
            raise error

        try:
            await self._log(
                _reraise, prompt_text=prompt_text, latency_ms=elapsed_ms, provider=provider
            )
        except Exception:
            # track_llm_call re-raises fn's own exception after logging it —
            # expected here since fn=_reraise. When this is the Groq leg of
            # a fallback, LangChain's with_fallbacks() catches this and
            # retries against Gemini on its own — swallowing the re-raise
            # here just stops it bubbling a second time out of a callback
            # (LangChain callbacks shouldn't throw).
            pass

    async def _log(
        self,
        fn,
        *,
        prompt_text: Optional[str] = None,
        model: Optional[str] = None,
        latency_ms: Optional[int] = None,
        provider: str = "unknown",
    ) -> None:
        call_kwargs: Dict[str, Any] = {}
        common = dict(
            project=self.project,
            feature=self.feature,
            provider=provider,
            model=model,
            prompt_name=self.prompt_name,
            prompt_version=self.prompt_version,
            db_session=self.db_session,
        )
        if prompt_text is not None:
            call_kwargs["prompt"] = prompt_text

        try:
            await track_llm_call(
                fn=fn,
                kwargs=call_kwargs,
                latency_ms_override=latency_ms,
                **common,
            )
        except TypeError:
            # Installed llm_observability predates the latency_ms_override
            # patch — still log, just with track_llm_call's own (~0ms,
            # inaccurate) internal timing rather than dropping the entry.
            logger.warning(
                "llm_observability.track_llm_call doesn't accept "
                "latency_ms_override yet — apply the patched logger.py "
                "for accurate latency on LangChain-sourced calls."
            )
            await track_llm_call(fn=fn, kwargs=call_kwargs, **common)
