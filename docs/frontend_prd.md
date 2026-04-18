# Phase 5: Logistics Dashboard Frontend (PRD)

## 1. Product Overview
The Analytics & Tracking Dashboard is the real-time visual nervous system of the Logistics supply chain. It connects to the web sockets emitted by our unified infrastructure (Kafka, Redis, and Vertex AI) to visualize global shipments.

**Design Philosophy**: Corporate, Professional, Data-Dense. The dashboard must prioritize clarity, strict grid alignments, accessible contrast ratios, and operational efficiency over purely decorative "vibecoding" elements.

## 2. Core Features & Requirements

### 2.1 Live Global Node Tracking (Map Interface)
*   **Dynamic Nodes**: Ships (Sea), Trucks (Road), and Planes (Air) must be displayed on a dark or high-contrast web map (e.g., using Mapbox GL JS or deck.gl for high-performance rendering).
*   **Coordinate Interpolation**: Nodes must smoothly handle telemetry transitions. Flink coordinates from `shipment-telemetry` should be interpolated logically so ships visibly "move" across the ocean rather than teleporting.
*   **Entity Clustering**: Because the mock generator can spawn hundreds of shipments, the map must cluster closely-packed nodes when zoomed out, breaking them apart upon zooming in.

### 2.2 Threat Visualization & Geofencing
*   **Polygons**: Severe weather cells, pirate threats, and infrastructure chokepoints generated in `threat-signals` must be rendered as colored geopolitical polygons overlaid on the map.
*   **Collision Highlighting**: When the Flink CoProcessFunction fires an anomaly alert, the UI must pulse the respective ship node and draw a warning vector towards the intersecting threat polygon.

### 2.3 LLM Optimization Sidebar
*   **Decision Feed**: A rolling column displaying real-time outputs from the Phase 4 `reroute-decisions` topic. 
*   **Data Structure**: For each card, display the `action` (REROUTE, WAIT, ESCALATE), the `Risk Score` metric, and the detailed Vertex AI `reasoning` block.
*   **Human Intervention**: Priority Tier 2 shipments that are flagged as `requires_human: true` should feature an actionable UI (Accept / Reject alternatives).

## 3. Technology Stack Recommendation

### Frontend Framework
*   **React 18** mapping state cleanly via Context or Redux Toolkit.
*   **Next.js (App Router)** for fast initial loads, or pure **Vite.js** if it is strictly an SPA.

### Geospatial & Rendering
*   **Mapbox GL JS** or **React-Map-GL**: The industry standard for smooth, enterprise-grade vector mapping. 
*   **Deck.gl**: Ideal if node data arrays grow beyond 10,000 parallel shipments.

### Styling & Component Library
*   **Shadcn UI + Tailwind CSS**: Clean, monochromatic UI components that look strictly B2B and professional. Highly accessible structure.
*   **Color Palette**: Navy, White, Charcoal, with strict semantic highlighting (Red for Threat Polygons, Yellow for Escalation, Green for Clear). Avoid neon gradients or "gamer" aesthetics.

## 4. Real-time Architecture Boundary
The frontend will strictly observe. It will not write back directly to Kafka.
*   **The Bridge**: A lightweight Node.js/FastAPI server running `Socket.io` or SSE (Server-Sent Events) will consume the `shipment-telemetry`, `threat-signals`, and `reroute-decisions` Kafka topics, and broadcast them directly to the React frontend.
*   **State Hydration**: Initial load fetches the snapshot of active shipments from the `redis` keyspace, then seamlessly transitions to subscribing to the live WebSocket feed.

## 5. Implementation Milestones
- [ ] **M1: Map Foundation**: Setup React + Mapbox. Draw a static ship and a static polygon using mock coordinates.
- [ ] **M2: WebSocket Webs**: Spin up the backend translation bridge connected to `logistics-redpanda`.
- [ ] **M3: Live Hydration**: Feed live Kafka telemetry to update the React component state, ensuring nodes visually traverse the screen.
- [ ] **M4: The LLM Console**: Bind the Vertex AI payload responses to the right-side analytics column.
