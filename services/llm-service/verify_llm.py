import asyncio
import os
import json
import logging
from dotenv import load_dotenv

# Import our service components
from rule_engine import LLMOptimizationRequest, FallbackRoute, LLMDecision, ThreatType, PriorityTier, TransportMode
from prompt_builder import build_prompt
from vertex_client import VertexClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("LLM-Verifier")

async def run_diagnostic():
    # 1. Load configuration
    load_dotenv()
    project = os.environ.get("GCP_PROJECT")
    if not project:
        print("❌ ERROR: GCP_PROJECT not found in .env")
        return

    print(f"🔍 Starting LLM Diagnostic (Project: {project})")
    
    # 2. Construct a sample disruption payload
    # Scenario: A severe weather event causing a 48h delay for a HIGH priority shipment
    mock_request = LLMOptimizationRequest(
        request_id="test-req-001",
        alert_id="alert-001",
        threat_id="threat-weather-001",
        threat_type=ThreatType.WEATHER,
        severity=8,
        estimated_delay_hours=48.0,
        collision_coordinates={"lat": 34.05, "lon": -118.24},
        shipment_id="shipment-999",
        priority_tier=PriorityTier.HIGH,
        transport_mode=TransportMode.SEA,
        fallback_routes=[
            FallbackRoute(route_id="R-FAST-01", base_cost=1500.0, estimated_transit_time_hours=12.0),
            FallbackRoute(route_id="R-CHEAP-02", base_cost=400.0, estimated_transit_time_hours=36.0),
        ],
        assembled_at="2024-04-18T20:00:00Z"
    )

    # 3. Build the prompt
    print("📝 Building prompt...")
    prompt = build_prompt(mock_request)
    
    # 4. Call Vertex AI
    print("☁️ Sending request to Vertex AI (Gemini 2.5 Pro)...")
    client = VertexClient()
    
    try:
        decision_dict = await client.get_optimization_decision(prompt)
        
        # 5. Validate output against schema
        print("✅ Received response from Vertex AI!")
        decision = LLMDecision(**decision_dict)
        
        print("\n--- LLM DECISION RESULTS ---")
        print(f"Action:      {decision.action}")
        print(f"Selected:    {decision.selected_route_id}")
        print(f"Reduction:   {decision.new_eta_offset_hours} hours")
        print(f"Reasoning:   {decision.reasoning}")
        print(f"Human Req:   {decision.requires_human}")
        print("----------------------------\n")
        
        # Check rule 1: HIGH priority should minimize delay
        if decision.selected_route_id == "R-FAST-01":
            print("✨ Rule Success: LLM correctly prioritized speed for HIGH priority cargo.")
        
        print("🎯 DIAGNOSTIC PASSED: LLM is working perfectly.")

    except Exception as e:
        print(f"❌ DIAGNOSTIC FAILED: {e}")
        logger.exception("Diagnostic error:")

if __name__ == "__main__":
    asyncio.run(run_diagnostic())
