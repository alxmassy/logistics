"""
Rule Engine — Pydantic v2 models and deterministic risk scoring.

Defines all shared schemas (input/output) and the ExecutionPayload
that merges them with a computed risk score and execution tier.
"""
import uuid
from enum import Enum
from typing import List, Dict

from pydantic import BaseModel

# ── Threshold ────────────────────────────────────────────────────────
TIER_1_MAX_SCORE = 40


# ── Enums ────────────────────────────────────────────────────────────
class ThreatType(str, Enum):
    WEATHER = "WEATHER"
    CONGESTION = "CONGESTION"
    INFRASTRUCTURE = "INFRASTRUCTURE"


class PriorityTier(str, Enum):
    LOW = "LOW"
    STANDARD = "STANDARD"
    HIGH = "HIGH"


class TransportMode(str, Enum):
    SEA = "SEA"
    AIR = "AIR"
    ROAD = "ROAD"


class LLMAction(str, Enum):
    REROUTE = "REROUTE"
    WAIT = "WAIT"
    ESCALATE = "ESCALATE"


# ── Input Schema (from Kafka topic: optimization-requests) ───────────
class FallbackRoute(BaseModel):
    route_id: str
    base_cost: float
    estimated_transit_time_hours: float


class LLMOptimizationRequest(BaseModel):
    request_id: str
    alert_id: str
    threat_id: str
    threat_type: ThreatType
    severity: int
    estimated_delay_hours: float
    collision_coordinates: Dict[str, float]
    shipment_id: str
    priority_tier: PriorityTier
    transport_mode: TransportMode
    fallback_routes: List[FallbackRoute]
    assembled_at: str


# ── LLM Output Schema ───────────────────────────────────────────────
class LLMDecision(BaseModel):
    selected_route_id: str
    action: LLMAction
    reasoning: str
    requires_human: bool
    new_eta_offset_hours: float


# ── Execution Payload (merged context + decision + score) ────────────
class ExecutionPayload(BaseModel):
    request_data: LLMOptimizationRequest
    decision: LLMDecision
    score: int = 0
    tier: int = 1
    idempotency_key: str = ""

    def model_post_init(self, __context) -> None:
        """Generate a unique idempotency key on creation."""
        if not self.idempotency_key:
            self.idempotency_key = str(uuid.uuid4())

    def calculate_risk_score(self) -> None:
        """
        Deterministic risk scoring per the PRD matrix.

        Scoring factors:
        ─────────────────────────────────────────────────
        Cost Delta (selected vs cheapest fallback):
            $0–$100   → +0
            $101–$500 → +5
            >$500     → +50

        Cargo Priority (SLA):
            LOW       → +0
            STANDARD  → +10
            HIGH      → +50

        Mode / Carrier Friction:
            Same mode & carrier          → +0
            Different carrier, same mode → +20
            Different transport mode     → +50

        Tier assignment:
            score <= 40  AND  requires_human == False  → Tier 1 (auto)
            score >  40  OR   requires_human == True   → Tier 2 (human)
        """
        score = 0

        # ── 1. Cargo Priority ────────────────────────────────────────
        priority_scores = {
            PriorityTier.LOW: 0,
            PriorityTier.STANDARD: 10,
            PriorityTier.HIGH: 50,
        }
        score += priority_scores.get(self.request_data.priority_tier, 0)

        # ── 2. Cost Delta ────────────────────────────────────────────
        selected_route = next(
            (r for r in self.request_data.fallback_routes
             if r.route_id == self.decision.selected_route_id),
            None,
        )
        if selected_route and self.request_data.fallback_routes:
            cheapest_cost = min(
                r.base_cost for r in self.request_data.fallback_routes
            )
            cost_delta = selected_route.base_cost - cheapest_cost
            if cost_delta > 500:
                score += 50
            elif cost_delta > 100:
                score += 5

        # ── 3. Mode / Carrier Friction ───────────────────────────────
        # The fallback routes in the PRD schema don't carry a
        # `transport_mode` or `carrier` field, so we infer friction
        # from the LLM's action field:
        #   • REROUTE with a different route → at least a carrier change (+20)
        #   • ESCALATE                       → likely a mode change   (+50)
        #   • WAIT / same route              → no change              (+0)
        if self.decision.action == LLMAction.ESCALATE:
            score += 50
        elif (
            self.decision.action == LLMAction.REROUTE
            and selected_route
            and selected_route.route_id
            != self.request_data.fallback_routes[0].route_id
        ):
            score += 20

        self.score = score

        # ── 4. Tier assignment ───────────────────────────────────────
        if self.score > TIER_1_MAX_SCORE or self.decision.requires_human:
            self.tier = 2
        else:
            self.tier = 1
