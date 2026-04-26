"""
Gemini Client — async wrapper around Google Gemini API.

Replaces the previous Vertex AI client. Uses the google-generativeai SDK
with a standalone API key (no GCP project required).

Uses structured JSON output enforcement via response_mime_type.
"""
import os
import json
import logging

import google.generativeai as genai

logger = logging.getLogger(__name__)


class GeminiClient:
    """Async client for Gemini structured decision-making."""

    def __init__(self) -> None:
        self._initialized = False
        self.model = None

    def _ensure_initialized(self) -> None:
        """Lazy-init so import-time doesn't crash if API key isn't set."""
        if self._initialized:
            return

        api_key = os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            logger.warning(
                "GEMINI_API_KEY env var is not set. "
                "LLM calls will return stub decisions until it is configured."
            )
            self._initialized = True
            return

        try:
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel("gemini-2.0-flash")
            self._initialized = True
            logger.info("Gemini model loaded successfully.")
        except Exception as e:
            logger.error("Failed to initialize Gemini: %s", e, exc_info=True)
            self.model = None
            self._initialized = True  # don't retry on every call

    async def get_optimization_decision(self, prompt: str) -> dict:
        """
        Send the optimization prompt to Gemini and return a parsed dict.

        Returns a dict that maps to the LLMDecision schema.
        Falls back to a stub response if the API key isn't configured.
        """
        self._ensure_initialized()

        if not self.model:
            logger.warning(
                "Gemini model not available — returning stub decision."
            )
            return {
                "selected_route_id": "R-002",
                "action": "REROUTE",
                "reasoning": (
                    "Stub decision: Gemini model was not loaded. "
                    "Set the GEMINI_API_KEY environment variable."
                ),
                "requires_human": False,
                "new_eta_offset_hours": 28.5,
            }

        generation_config = genai.types.GenerationConfig(
            response_mime_type="application/json",
            temperature=0.0,
        )

        try:
            response = await self.model.generate_content_async(
                prompt,
                generation_config=generation_config,
            )
            raw = response.text
            logger.info("Gemini raw response: %s", raw[:500])
            return json.loads(raw)
        except json.JSONDecodeError as e:
            logger.error(
                "Gemini returned non-JSON response: %s — raw: %s",
                e, response.text[:500],
            )
            raise
        except Exception as e:
            logger.error("Error calling Gemini: %s", e, exc_info=True)
            raise
