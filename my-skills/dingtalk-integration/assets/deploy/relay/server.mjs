#!/usr/bin/env node
/**
 * 边界中间件参考实现（形态 B：落盘 + 拉取）—— 零外部依赖。
 *
 * 定位：能直接跑、能压测、能被你们的安全评审，然后按需替换。
 *      生产前请务必：换存储（DB）、加 TLS 前置（nginx）、加审计日志、过代码评审。
 *
 * 与 05-edge-middleware.md §3.3 的接口契约一致：
 *   POST /api/inbound/:consumer/:event   X-API-Token        钉钉侧调用，落盘后立即 200
 *   GET  /api/pull/:consumer             Bearer             内网侧拉取，发放租约
 *   POST /api/ack/:consumer              Bearer             内网侧确认
 *   GET  /healthz                                           存活
 *   GET  /api/admin/stats|dead           Admin 令牌          对账
 *   POST /api/admin/replay/:id           Admin 令牌          重放
 *
 * 存储：追加式 NDJSON 事件日志 + 内存索引，启动重放、定期压缩快照。
 *      审批场景日均量级（数千条）足够；上十万级请换 DB（schema 见 ../sql/）。
 *
 * 运行：node --env-file=.env server.mjs      (Node >= 20.6)
 */
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';

const VERSION = '1.0.0';

// ---------- 配置 ----------
const env = process.env;
const PORT = Number(env.PORT || 4330);
const HOST = env.HOST || '127.0.0.1'; // 只监听本机，前面必须挂 nginx
const DATA_DIR = env.DATA_DIR || '/var/lib/dingtalk-relay';
const MAX_BODY = Number(env.MAX_BODY_BYTES || 256 * 1024);
const LEASE_DEFAULT = Number(env.LEASE_SECONDS || 60);
const MAX_ATTEMPTS = Number(env.MAX_ATTEMPTS || 8);
const RETENTION_DAYS = Number(env.RETENTION_DAYS || 60);
const COMPACT_EVERY = Number(env.COMPACT_EVERY || 5000);

/** "<system>:tok1,assets:tok2" -> Map(consumer -> token) */
function parseTokenMap(raw, name) {
  const m = new Map();
  if (!raw) return m;
  for (const pair of raw.split(',')) {
    const s = pair.trim();
    if (!s) continue;
    const i = s.indexOf(':');
    if (i < 1) throw new Error(`${name} 格式应为 consumer:token，收到 ${s}`);
    m.set(s.slice(0, i).trim(), s.slice(i + 1).trim());
  }
  return m;
}

const EDGE_TOKENS = parseTokenMap(env.EDGE_TOKENS, 'EDGE_TOKENS');
const CONSUMER_TOKENS = parseTokenMap(env.CONSUMER_TOKENS, 'CONSUMER_TOKENS');
const ADMIN_TOKEN = env.ADMIN_TOKEN || '';

if (EDGE_TOKENS.size === 0) throw new Error('EDGE_TOKENS 未配置（consumer:token,...）');
if (CONSUMER_TOKENS.size === 0) throw new Error('CONSUMER_TOKENS 未配置（consumer:token,...）');

// ---------- 状态 ----------
/** id -> record */
const records = new Map();
/** `${consumer}\0${external_id}` -> id */
const byKey = new Map();
let nextId = 1;
let logFd = -1;
let logLines = 0;

fs.mkdirSync(DATA_DIR, { recursive: true });
const LOG_PATH = path.join(DATA_DIR, 'messages.log');
const SNAP_PATH = path.join(DATA_DIR, 'snapshot.json');

function now() {
  return Date.now();
}

function safeEqual(a, b) {
  const x = Buffer.from(String(a || ''));
  const y = Buffer.from(String(b || ''));
  if (x.length !== y.length) return false;
  return crypto.timingSafeEqual(x, y);
}

/** 追加事件（单进程串行写，无需锁） */
function append(event) {
  fs.writeSync(logFd, JSON.stringify(event) + '\n');
  logLines += 1;
}

function apply(event) {
  const r = records.get(event.id);
  switch (event.t) {
    case 'in': {
      const key = `${event.consumer}\u0000${event.external_id}`;
      if (byKey.has(key)) return; // 幂等：重复入库事件不覆盖
      records.set(event.id, {
        id: event.id,
        external_id: event.external_id,
        consumer: event.consumer,
        event: event.event,
        payload: event.payload,
        status: 'pending',
        attempts: 0,
        lease_until: 0,
        lease_token: null,
        created_at: event.created_at,
        delivered_at: null,
        last_error: null,
      });
      byKey.set(key, event.id);
      if (event.id >= nextId) nextId = event.id + 1;
      break;
    }
    case 'lease':
      if (r && r.status === 'pending') {
        r.status = 'leased';
        r.lease_until = event.until;
        r.lease_token = event.token;
      }
      break;
    case 'ack':
      if (r) {
        r.status = 'delivered';
        r.delivered_at = event.at;
        r.lease_token = null;
        r.lease_until = 0;
      }
      break;
    case 'nack':
      if (r) {
        r.attempts = event.attempts;
        r.last_error = event.error || null;
        r.lease_token = null;
        r.lease_until = 0;
        r.status = event.attempts >= MAX_ATTEMPTS ? 'dead' : 'pending';
      }
      break;
    case 'replay':
      if (r) {
        r.status = 'pending';
        r.attempts = 0;
        r.lease_token = null;
        r.lease_until = 0;
      }
      break;
    default:
      break;
  }
}

function loadState() {
  // 1) 快照（压缩过的基线）
  if (fs.existsSync(SNAP_PATH)) {
    const snap = JSON.parse(fs.readFileSync(SNAP_PATH, 'utf8'));
    for (const r of snap.records) {
      records.set(r.id, r);
      byKey.set(`${r.consumer}\u0000${r.external_id}`, r.id);
      if (r.id >= nextId) nextId = r.id + 1;
    }
  }
  // 2) 事件日志重放（覆盖快照之后的变更）
  if (fs.existsSync(LOG_PATH)) {
    const lines = fs.readFileSync(LOG_PATH, 'utf8').split('\n').filter(Boolean);
    for (const line of lines) {
      try {
        apply(JSON.parse(line));
      } catch {
        // 尾部半行（断电）忽略
      }
    }
    logLines = lines.length;
  }
  logFd = fs.openSync(LOG_PATH, 'a');
}

/** 压缩：写快照 + 清空日志 */
function compact() {
  const snap = { version: VERSION, at: now(), records: [...records.values()] };
  const tmp = SNAP_PATH + '.tmp';
  fs.writeFileSync(tmp, JSON.stringify(snap));
  fs.renameSync(tmp, SNAP_PATH);
  fs.ftruncateSync(logFd, 0);
  logLines = 0;
}

/** 回收已投递且超过保留期的记录（只从内存与快照里清，日志靠压缩收敛） */
function sweep() {
  const cutoff = now() - RETENTION_DAYS * 86400_000;
  let removed = 0;
  for (const [id, r] of records) {
    if (r.status === 'delivered' && r.delivered_at && r.delivered_at < cutoff) {
      records.delete(id);
      byKey.delete(`${r.consumer}\u0000${r.external_id}`);
      removed += 1;
    }
  }
  if (removed > 0) compact();
  return removed;
}

// ---------- HTTP 工具 ----------
function send(res, code, body, extraHeaders = {}) {
  const buf = Buffer.from(JSON.stringify(body));
  res.writeHead(code, {
    'Content-Type': 'application/json; charset=utf-8',
    'Content-Length': buf.length,
    'Cache-Control': 'no-store',
    ...extraHeaders,
  });
  res.end(buf);
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    let size = 0;
    const chunks = [];
    req.on('data', (c) => {
      size += c.length;
      if (size > MAX_BODY) {
        reject(Object.assign(new Error('payload too large'), { code: 413 }));
        req.destroy();
        return;
      }
      chunks.push(c);
    });
    req.on('end', () => resolve(Buffer.concat(chunks).toString('utf8')));
    req.on('error', reject);
  });
}

function bearer(req) {
  const h = req.headers['authorization'] || '';
  return h.startsWith('Bearer ') ? h.slice(7).trim() : '';
}

// ---------- 路由 ----------
const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://${req.headers.host || 'localhost'}`);
  const p = url.pathname;

  try {
    if (req.method === 'GET' && p === '/healthz') {
      return send(res, 200, { ok: true, version: VERSION, uptime: process.uptime(), records: records.size });
    }

    // ---- 入库（钉钉侧）----
    const inMatch = p.match(/^\/api\/inbound\/([^/]+)\/([^/]+)$/);
    if (req.method === 'POST' && inMatch) {
      const consumer = decodeURIComponent(inMatch[1]);
      const event = decodeURIComponent(inMatch[2]);
      if (!['upsert', 'delete', 'revoke'].includes(event)) {
        return send(res, 400, { ok: false, error: 'unsupported event' });
      }
      const expect = EDGE_TOKENS.get(consumer);
      if (!expect) return send(res, 401, { ok: false, error: 'unknown consumer' });
      if (!safeEqual(req.headers['x-api-token'], expect)) {
        return send(res, 401, { ok: false, error: 'bad edge token' });
      }
      const ctype = String(req.headers['content-type'] || '');
      if (!ctype.includes('application/json')) {
        return send(res, 415, { ok: false, error: 'content-type must be application/json' });
      }
      const raw = await readBody(req);
      let body;
      try {
        body = JSON.parse(raw);
      } catch {
        return send(res, 400, { ok: false, error: 'invalid json' });
      }
      if (!body || typeof body !== 'object' || Array.isArray(body)) {
        return send(res, 400, { ok: false, error: 'body must be an object' });
      }
      const externalId = body.external_id;
      if (!externalId || typeof externalId !== 'string') {
        return send(res, 400, { ok: false, error: 'external_id (string) is required' });
      }
      const key = `${consumer}\u0000${externalId}`;
      const existing = byKey.get(key);
      if (existing) {
        return send(res, 200, { ok: true, receipt_id: existing, duplicate: true });
      }
      const id = nextId++;
      const ev = {
        t: 'in',
        id,
        external_id: externalId,
        consumer,
        event,
        payload: body,
        created_at: now(),
      };
      append(ev);
      apply(ev);
      if (logLines >= COMPACT_EVERY) compact();
      return send(res, 200, { ok: true, receipt_id: id, duplicate: false });
    }

    // ---- 拉取（内网侧）----
    const pullMatch = p.match(/^\/api\/pull\/([^/]+)$/);
    if (req.method === 'GET' && pullMatch) {
      const consumer = decodeURIComponent(pullMatch[1]);
      const expect = CONSUMER_TOKENS.get(consumer);
      if (!expect) return send(res, 401, { ok: false, error: 'unknown consumer' });
      if (!safeEqual(bearer(req), expect)) return send(res, 401, { ok: false, error: 'bad consumer token' });

      const limit = Math.min(Number(url.searchParams.get('limit') || 20), 100);
      const lease = Math.min(Number(url.searchParams.get('lease') || LEASE_DEFAULT), 600);
      const onlyEvent = url.searchParams.get('event');
      const t = now();
      const out = [];

      for (const r of records.values()) {
        if (out.length >= limit) break;
        if (r.consumer !== consumer) continue;
        if (onlyEvent && r.event !== onlyEvent) continue;
        const available =
          r.status === 'pending' || (r.status === 'leased' && r.lease_until < t);
        if (!available) continue;
        const token = crypto.randomBytes(12).toString('hex');
        const until = t + lease * 1000;
        const ev = { t: 'lease', id: r.id, until, token };
        append(ev);
        apply(ev);
        out.push({
          id: r.id,
          external_id: r.external_id,
          event: r.event,
          payload: r.payload,
          created_at: r.created_at,
          lease_token: token,
          lease_until: until,
        });
      }
      return send(res, 200, { items: out, has_more: out.length >= limit });
    }

    // ---- 确认 ----
    const ackMatch = p.match(/^\/api\/ack\/([^/]+)$/);
    if (req.method === 'POST' && ackMatch) {
      const consumer = decodeURIComponent(ackMatch[1]);
      const expect = CONSUMER_TOKENS.get(consumer);
      if (!expect) return send(res, 401, { ok: false, error: 'unknown consumer' });
      if (!safeEqual(bearer(req), expect)) return send(res, 401, { ok: false, error: 'bad consumer token' });

      const raw = await readBody(req);
      let body;
      try {
        body = JSON.parse(raw || '{}');
      } catch {
        return send(res, 400, { ok: false, error: 'invalid json' });
      }
      const acks = Array.isArray(body.acks) ? body.acks : [];
      const nacks = Array.isArray(body.nacks) ? body.nacks : [];
      let acked = 0;
      let nacked = 0;

      for (const a of acks) {
        const r = records.get(Number(a.id));
        if (!r || r.consumer !== consumer) continue;
        if (!safeEqual(a.lease_token, r.lease_token)) continue; // 租约过期/被重投，忽略
        const ev = { t: 'ack', id: r.id, at: now() };
        append(ev);
        apply(ev);
        acked += 1;
      }
      for (const n of nacks) {
        const r = records.get(Number(n.id));
        if (!r || r.consumer !== consumer) continue;
        if (!safeEqual(n.lease_token, r.lease_token)) continue;
        const attempts = (r.attempts || 0) + 1;
        const ev = { t: 'nack', id: r.id, attempts, error: String(n.error || '').slice(0, 500) };
        append(ev);
        apply(ev);
        if (attempts >= MAX_ATTEMPTS) {
          append({ t: 'dead', id: r.id });
        }
        nacked += 1;
      }
      return send(res, 200, { ok: true, acked, nacked });
    }

    // ---- 运维接口 ----
    if (p.startsWith('/api/admin/')) {
      if (!ADMIN_TOKEN) return send(res, 404, { ok: false, error: 'admin disabled' });
      if (!safeEqual(bearer(req), ADMIN_TOKEN)) return send(res, 401, { ok: false, error: 'bad admin token' });

      if (req.method === 'GET' && p === '/api/admin/stats') {
        const per = {};
        for (const r of records.values()) {
          per[r.consumer] ||= { pending: 0, leased: 0, delivered: 0, dead: 0, oldest_pending_at: null };
          per[r.consumer][r.status] = (per[r.consumer][r.status] || 0) + 1;
          if (r.status === 'pending') {
            const cur = per[r.consumer].oldest_pending_at;
            if (!cur || r.created_at < cur) per[r.consumer].oldest_pending_at = r.created_at;
          }
        }
        return send(res, 200, { ok: true, now: now(), per, total: records.size, log_lines: logLines });
      }
      if (req.method === 'GET' && p === '/api/admin/dead') {
        const dead = [...records.values()].filter((r) => r.status === 'dead');
        return send(res, 200, { ok: true, count: dead.length, items: dead.slice(0, 200) });
      }
      const replayMatch = p.match(/^\/api\/admin\/replay\/(\d+)$/);
      if (req.method === 'POST' && replayMatch) {
        const id = Number(replayMatch[1]);
        if (!records.has(id)) return send(res, 404, { ok: false, error: 'not found' });
        append({ t: 'replay', id });
        apply({ t: 'replay', id });
        return send(res, 200, { ok: true, id, status: records.get(id).status });
      }
      if (req.method === 'POST' && p === '/api/admin/compact') {
        compact();
        const removed = sweep();
        return send(res, 200, { ok: true, compacted: true, swept: removed });
      }
      return send(res, 404, { ok: false, error: 'not found' });
    }

    return send(res, 404, { ok: false, error: 'not found' });
  } catch (err) {
    if (err && err.code === 413) return send(res, 413, { ok: false, error: 'payload too large' });
    console.error('[error]', err);
    return send(res, 500, { ok: false, error: 'internal error' });
  }
});

loadState();
server.listen(PORT, HOST, () => {
  console.log(`[dingtalk-relay] ${VERSION} listening on http://${HOST}:${PORT} data=${DATA_DIR} records=${records.size}`);
});

// 每小时回收过期已投递记录
setInterval(() => {
  try {
    const n = sweep();
    if (n) console.log(`[sweep] removed ${n}`);
  } catch (e) {
    console.error('[sweep]', e);
  }
}, 3600_000).unref();

for (const sig of ['SIGINT', 'SIGTERM']) {
  process.on(sig, () => {
    console.log(`[${sig}] flushing & exit`);
    try {
      compact();
    } catch (e) {
      console.error('[compact-on-exit]', e);
    }
    process.exit(0);
  });
}
