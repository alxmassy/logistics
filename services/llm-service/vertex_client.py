"""
Vertex AI Client — async wrapper around Gemini 1.5 Pro.

Uses the google-cloud-aiplatform SDK with strict JSON output enforcement
via response_mime_type="application/json".
"""
import os
import json
import logging

import vertexai
from vertexai.generative_models import GenerativeModel, GenerationConfig

logger = logging.getLogger(__name__)


def _init_vertex() -> None:
    """Initialize the Vertex AI SDK with project/location from env."""
    project = os.environ.get("GCP_PROJECT", "")
    location = os.environ.get("GCP_LOCATION", "us-central1")
    if not project:
        logger.warning(
            "GCP_PROJECT env var is not set. "
            "Vertex AI calls will fail until it is configured."
        )
    vertexai.init(project=project, location=location)


class VertexClient:
    """Async client for Gemini 1.5 Pro structured decision-making."""

    def __init__(self) -> None:
        self._initialized = False
        self.model: GenerativeModel | None = None

    def _ensure_initialized(self) -> None:
        """Lazy-init so import-time doesn't crash if SDK isn't ready."""
        if self._initialized:
            return
        try:
            _init_vertex()
            self.model = GenerativeModel("gemini-2.5-pro")
            self._initialized = True
            logger.info("Vertex AI model loaded successfully.")
        except Exception as e:
            logger.error("Failed to initialize Vertex AI: %s", e, exc_info=True)
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
                "Vertex AI model not available — returning stub decision."
            )
            return {
                "selected_route_id": "R-002",
                "action": "REROUTE",
                "reasoning": (
                    "Stub decision: Vertex AI model was not loaded. "
                    "Configure GCP_PROJECT and authenticate via "
                    "'gcloud auth application-default login'."
                ),
                "requires_human": False,
                "new_eta_offset_hours": 28.5,
            }

        generation_config = GenerationConfig(
            response_mime_type="application/json",
            temperature=0.0,
        )

        try:
            response = await self.model.generate_content_async(
                prompt,
                generation_config=generation_config,
            )
            raw = response.text
            logger.info("Vertex AI raw response: %s", raw[:500])
            return json.loads(raw)
        except json.JSONDecodeError as e:
            logger.error(
                "Gemini returned non-JSON response: %s — raw: %s",
                e, response.text[:500],
            )
            raise
        except Exception as e:
            logger.error("Error calling Vertex AI: %s", e, exc_info=True)
            raise
