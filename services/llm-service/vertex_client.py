"""
Vertex AI Client — async wrapper around Gemini 1.5 Pro.

Uses the google-cloud-aiplatform SDK with strict JSON output enforcement
via response_mime_type="application/json".
"""
import os
import json
import logging

import google.generativeai as genai

logger = logging.getLogger(__name__)


def _init_vertex() -> None:
    """Initialize the Gemini SDK with API Key from env."""
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        logger.warning(
            "GEMINI_API_KEY env var is not set. "
            "Gemini AI calls will fail until it is configured."
        )
    genai.configure(api_key=api_key)


class VertexClient:
    """Async client for Gemini 1.5 Pro structured decision-making."""

    def __init__(self) -> None:
        self._initialized = False
        self.model: genai.GenerativeModel | None = None

    def _ensure_initialized(self) -> None:
        """Lazy-init so import-time doesn't crash if SDK isn't ready."""
        if self._initialized:
            return
        try:
            _init_vertex()
            self.model = genai.GenerativeModel("gemini-1.5-pro")
            self._initialized = True
            logger.info("Gemini AI model loaded successfully.")
        except Exception as e:
            logger.error("Failed to initialize Gemini AI: %s", e, exc_info=True)
            self.model = None
            self._initialized = True  # don't retry on every call

    async def get_optimization_decision(self, prompt: str) -> dict:
        """
        Send the optimization prompt to Gemini and return a parsed dict.

        Returns a dict that maps to the LLMDecision schema.
        Falls back to a stub response if the model couldn't be loaded
        (e.g. missing credentials during local dev).
        """
        self._ensure_initialized()

        if not self.model:
            logger.warning(
                "Gemini AI model not available — returning stub decision."
            )
            return {
                "selected_route_id": "R-002",
                "action": "REROUTE",
                "reasoning": (
                    "Stub decision: Gemini AI model was not loaded. "
                    "Configure GEMINI_API_KEY environment variable."
                ),
                "requires_human": False,
                "new_eta_offset_hours": 28.5,
            }

        generation_config = genai.GenerationConfig(
            response_mime_type="application/json",
            temperature=0.0,
        )

        try:
            response = await self.model.generate_content_async(
                prompt,
                generation_config=generation_config,
            )
            raw = response.text
            logger.info("Gemini AI raw response: %s", raw[:500])
            return json.loads(raw)
        except json.JSONDecodeError as e:
            logger.error(
                "Gemini returned non-JSON response: %s — raw: %s",
                e, response.text[:500],
            )
            raise
        except Exception as e:
            logger.error("Error calling Gemini AI: %s", e, exc_info=True)
            raise
