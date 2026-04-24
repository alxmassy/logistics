/**
 * Logistics Bridge Server
 * 
 * Consumes from Kafka topics (shipment-telemetry, threat-signals, reroute-decisions)
 * and broadcasts events to the React dashboard via Socket.io.
 * Also handles Redis hydration and proxies LLM service endpoints.
 */
import 'dotenv/config';
import { createServer } from 'http';
import { Server } from 'socket.io';
import { Kafka } from 'kafkajs';
import Redis from 'ioredis';

const PORT = parseInt(process.env.PORT || '3001', 10);
const KAFKA_BROKERS = (process.env.KAFKA_BOOTSTRAP_SERVERS || 'localhost:19092').split(',');
const REDIS_URL = process.env.REDIS_URL || 'redis://localhost:6379/0';
const LLM_SERVICE_URL = process.env.LLM_SERVICE_URL || 'http://localhost:8000';

// ── HTTP Server + Socket.io ─────────────────────────────────────────
const httpServer = createServer(async (req, res) => {
  // Simple REST proxy for LLM service approve/reject
  const approveMatch = req.url?.match(/^\/api\/execute\/approve\/(.+)$/);
  const rejectMatch = req.url?.match(/^\/api\/execute\/reject\/(.+)$/);

  if (req.method === 'POST' && (approveMatch || rejectMatch)) {
    const shipmentId = approveMatch?.[1] || rejectMatch?.[1];
    const action = approveMatch ? 'approve' : 'reject';
    try {
      const upstream = await fetch(`${LLM_SERVICE_URL}/execute/${action}/${shipmentId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });
      const data = await upstream.json();
      res.writeHead(upstream.status, { 
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
      });
      res.end(JSON.stringify(data));
    } catch (err) {
      res.writeHead(502, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: 'Bridge proxy error', detail: err.message }));
    }
    return;
  }

  // Health check — extended with system metrics
  if (req.url === '/health') {
    let pendingApprovals = 0;
    let llmReachable = false;
    let flinkRunning = false;

    try {
      const keys = await redis.keys('pending_approval:*');
      pendingApprovals = keys.length;
    } catch {}

    try {
      const llmRes = await fetch(`${LLM_SERVICE_URL}/health`, { signal: AbortSignal.timeout(2000) });
      llmReachable = llmRes.ok;
    } catch {}

    try {
      // Check if Flink container is running via Docker
      const { execSync } = await import('child_process');
      const result = execSync('docker inspect --format="{{.State.Running}}" logistics-flink-collision 2>/dev/null', { encoding: 'utf8' }).trim();
      flinkRunning = result === 'true';
    } catch {}

    res.writeHead(200, {
      'Content-Type': 'application/json',
      'Access-Control-Allow-Origin': '*',
    });
    res.end(JSON.stringify({
      status: 'ok',
      kafka_connected: kafkaConnected,
      redis_connected: redisConnected,
      llm_service_reachable: llmReachable,
      flink_running: flinkRunning,
      pending_approvals: pendingApprovals,
      ws_clients: io.engine?.clientsCount ?? 0,
      cached_decisions: recentDecisions.length,
      active_telemetry: latestTelemetry.size,
      active_threats: activeThreats.size,
    }));
    return;
  }

  // CORS preflight
  if (req.method === 'OPTIONS') {
    res.writeHead(204, {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type',
    });
    res.end();
    return;
  }

  res.writeHead(404);
  res.end('Not Found');
});

const io = new Server(httpServer, {
  cors: {
    origin: '*',
    methods: ['GET', 'POST'],
  },
  pingInterval: 10000,
  pingTimeout: 5000,
});

let kafkaConnected = false;
let redisConnected = false;

// ── Redis Client ────────────────────────────────────────────────────
const redis = new Redis(REDIS_URL, {
  retryStrategy: (times) => Math.min(times * 500, 5000),
  maxRetriesPerRequest: 3,
  lazyConnect: true,
});

redis.on('connect', () => {
  redisConnected = true;
  console.log('✓ Redis connected');
});

redis.on('error', (err) => {
  redisConnected = false;
  console.error('✗ Redis error:', err.message);
});

// ── Kafka Setup ─────────────────────────────────────────────────────
const kafka = new Kafka({
  clientId: 'logistics-bridge',
  brokers: KAFKA_BROKERS,
  retry: {
    initialRetryTime: 1000,
    retries: 10,
  },
});

const consumer = kafka.consumer({ groupId: 'bridge-dashboard-group' });

const TOPICS = {
  TELEMETRY: 'shipment-telemetry',
  THREATS: 'threat-signals',
  DECISIONS: 'reroute-decisions',
};

// In-memory state for hydration of new clients
const latestTelemetry = new Map();   // shipment_id → latest telemetry
const activeThreats = new Map();     // threat_id → threat data
const recentDecisions = [];          // last 50 decisions
const MAX_DECISIONS = 50;
const DECISION_TTL_MS = 10 * 60 * 1000; // 10 minutes — matches Redis pending_approval TTL

async function startKafkaConsumer() {
  try {
    await consumer.connect();
    kafkaConnected = true;
    console.log('✓ Kafka connected');

    await consumer.subscribe({ topics: Object.values(TOPICS), fromBeginning: false });

    await consumer.run({
      eachMessage: async ({ topic, message }) => {
        try {
          const value = JSON.parse(message.value.toString());

          switch (topic) {
            case TOPICS.TELEMETRY:
              latestTelemetry.set(value.shipment_id, value);
              io.emit('telemetry:update', value);
              break;

            case TOPICS.THREATS:
              activeThreats.set(value.threat_id, value);
              io.emit('threat:update', value);
              // Auto-evict threats older than 10 minutes
              setTimeout(() => {
                activeThreats.delete(value.threat_id);
                io.emit('threat:remove', { threat_id: value.threat_id });
              }, 600_000);
              break;

            case TOPICS.DECISIONS:
              value._receivedAt = Date.now();
              recentDecisions.unshift(value);
              if (recentDecisions.length > MAX_DECISIONS) recentDecisions.pop();
              io.emit('decision:new', value);
              break;
          }
        } catch (err) {
          console.error(`Error processing message from ${topic}:`, err.message);
        }
      },
    });
  } catch (err) {
    console.error('✗ Kafka connection failed:', err.message);
    kafkaConnected = false;
    // Retry after 5 seconds
    setTimeout(startKafkaConsumer, 5000);
  }
}

// ── Purge stale decisions older than TTL ────────────────────────────
function purgeStaleDecisions() {
  const now = Date.now();
  // Remove decisions older than DECISION_TTL_MS (walk backwards for safe splice)
  for (let i = recentDecisions.length - 1; i >= 0; i--) {
    if (now - (recentDecisions[i]._receivedAt || 0) > DECISION_TTL_MS) {
      recentDecisions.splice(i, 1);
    }
  }
}

// Periodically clean stale decisions (every 60 seconds)
setInterval(purgeStaleDecisions, 60_000);

// ── Socket.io Connection Handler ────────────────────────────────────
io.on('connection', async (socket) => {
  console.log(`Client connected: ${socket.id}`);

  // Purge stale entries before hydrating
  purgeStaleDecisions();

  // For Tier 2 decisions, verify the pending_approval key still exists in Redis
  // so we don't hydrate expired/un-actionable items
  const liveDecisions = [];
  for (const d of recentDecisions) {
    const isTier2 = d.tier === 2 && d.decision?.requires_human;
    if (isTier2) {
      try {
        const exists = await redis.exists(`pending_approval:${d.request_data?.shipment_id}`);
        if (exists) {
          liveDecisions.push(d);
        }
      } catch {
        // If Redis is down, include it anyway so the UI isn't empty
        liveDecisions.push(d);
      }
    } else {
      liveDecisions.push(d);
    }
  }

  // Send hydration data to the newly connected client
  socket.emit('hydration', {
    telemetry: Object.fromEntries(latestTelemetry),
    threats: Object.fromEntries(activeThreats),
    decisions: liveDecisions,
  });

  socket.on('disconnect', (reason) => {
    console.log(`Client disconnected: ${socket.id} (${reason})`);
  });
});

// ── Redis Hydration (load existing state from Redis) ────────────────
async function hydrateFromRedis() {
  try {
    await redis.connect();
    // Scan for shipment context keys
    let cursor = '0';
    do {
      const [nextCursor, keys] = await redis.scan(cursor, 'MATCH', 'shipment_context:*', 'COUNT', 100);
      cursor = nextCursor;
      for (const key of keys) {
        try {
          const data = await redis.hgetall(key);
          if (data && Object.keys(data).length > 0) {
            const shipmentId = key.replace('shipment_context:', '');
            // Store routes for context but don't emit — telemetry will arrive via Kafka
            console.log(`  Hydrated context for shipment: ${shipmentId}`);
          }
        } catch (e) {
          // Skip malformed keys
        }
      }
    } while (cursor !== '0');
    console.log('✓ Redis hydration complete');
  } catch (err) {
    console.error('✗ Redis hydration failed:', err.message);
  }
}

// ── Start Everything ────────────────────────────────────────────────
async function main() {
  console.log('╔══════════════════════════════════════════╗');
  console.log('║   Logistics Bridge Server                ║');
  console.log('╚══════════════════════════════════════════╝');
  console.log(`  Kafka brokers: ${KAFKA_BROKERS.join(', ')}`);
  console.log(`  Redis: ${REDIS_URL}`);
  console.log(`  LLM Service: ${LLM_SERVICE_URL}`);
  console.log(`  Port: ${PORT}`);
  console.log('');

  await hydrateFromRedis();
  await startKafkaConsumer();

  httpServer.listen(PORT, () => {
    console.log(`\n✓ Bridge server listening on http://localhost:${PORT}`);
  });
}

// Graceful shutdown
for (const signal of ['SIGINT', 'SIGTERM']) {
  process.on(signal, async () => {
    console.log(`\n${signal} received — shutting down...`);
    await consumer.disconnect().catch(() => {});
    redis.disconnect();
    httpServer.close();
    process.exit(0);
  });
}

main().catch(console.error);
