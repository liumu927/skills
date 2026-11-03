#!/usr/bin/env node
/**
 * 内网消费端参考实现（拉取器）—— 零外部依赖。
 *
 * 契约（与 05-edge-middleware.md §3 / 06-office-lan-pull.md §二 一致）：
 *   拉取 → 本地事务落库（按 external_id 幂等）→ ack；失败 → nack
 * 铁律：先落库再 ack；ack 失败不要紧（租约到期会重投），但本地不能产生副作用重复。
 *
 * 运行：node --env-file=.env pull.mjs
 * 单次：node --env-file=.env pull.mjs --once
 */
import fs from 'node:fs';
import path from 'node:path';

const env = process.env;
const EDGE_BASE = (env.EDGE_BASE || '').replace(/\/$/, '');
const CONSUMER = env.CONSUMER || '';
const TOKEN = env.CONSUMER_TOKEN || '';
const LIMIT = Number(env.PULL_LIMIT || 20);
const LEASE = Number(env.PULL_LEASE || 60);
const INTERVAL = Number(env.PULL_INTERVAL_MS || 30_000);
const LOCAL_DIR = env.LOCAL_DIR || './data';
const ONCE = process.argv.includes('--once');

if (!EDGE_BASE) throw new Error('EDGE_BASE 未配置，如 https://<domain>');
if (!CONSUMER) throw new Error('CONSUMER 未配置');
if (!TOKEN) throw new Error('CONSUMER_TOKEN 未配置');

fs.mkdirSync(LOCAL_DIR, { recursive: true });
const STORE = path.join(LOCAL_DIR, `inbound-${CONSUMER}.ndjson`);

/** 已处理的 external_id（启动时从本地库重建，保证重启后仍幂等） */
const seen = new Set();
const voids = new Set();

function loadLocal() {
  if (!fs.existsSync(STORE)) return;
  for (const line of fs.readFileSync(STORE, 'utf8').split('\n')) {
    if (!line.trim()) continue;
    try {
      const r = JSON.parse(line);
      seen.add(r.external_id);
      if (r.event === 'delete' || r.event === 'revoke') voids.add(r.external_id);
    } catch {
      /* 尾部半行忽略 */
    }
  }
}

/**
 * 本地落库（示例用 NDJSON；换成你们的业务库时，把这里替换成事务 upsert）
 * 返回后表示"已持久化"，此时才允许 ack。
 */
function upsertLocal(item) {
  if (item.event === 'delete' || item.event === 'revoke') {
    // 撤回/删除：标记作废而不是物理删（便于审计）。本地没有这条也算成功。
    voids.add(item.external_id);
    fs.appendFileSync(
      STORE,
      JSON.stringify({
        external_id: item.external_id,
        event: item.event,
        void: true,
        payload: item.payload,
        received_at: new Date().toISOString(),
      }) + '\n',
    );
    return;
  }
  // 幂等：同一 external_id 第二次到达直接跳过（至少一次投递的正常现象）
  if (seen.has(item.external_id) && !voids.has(item.external_id)) return;
  fs.appendFileSync(
    STORE,
    JSON.stringify({
      external_id: item.external_id,
      event: item.event,
      payload: item.payload,
      received_at: new Date().toISOString(),
    }) + '\n',
  );
  seen.add(item.external_id);
  voids.delete(item.external_id);
}

async function pullOnce() {
  const url = `${EDGE_BASE}/api/pull/${encodeURIComponent(CONSUMER)}?limit=${LIMIT}&lease=${LEASE}`;
  const res = await fetch(url, { headers: { Authorization: `Bearer ${TOKEN}` } });
  if (!res.ok) {
    console.error(`[pull] HTTP ${res.status} ${await res.text().catch(() => '')}`);
    return 0;
  }
  const { items = [], has_more } = await res.json();
  if (items.length === 0) return 0;

  const acks = [];
  const nacks = [];
  for (const item of items) {
    try {
      upsertLocal(item);
      acks.push({ id: item.id, lease_token: item.lease_token });
    } catch (e) {
      nacks.push({ id: item.id, lease_token: item.lease_token, error: String(e && e.message) });
    }
  }

  const ackRes = await fetch(`${EDGE_BASE}/api/ack/${encodeURIComponent(CONSUMER)}`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${TOKEN}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ acks, nacks }),
  });
  if (!ackRes.ok) {
    console.error(`[ack] HTTP ${ackRes.status} ${await ackRes.text().catch(() => '')}`);
  } else {
    const r = await ackRes.json();
    console.log(`[pull] got=${items.length} acked=${r.acked} nacked=${r.nacked} has_more=${!!has_more}`);
  }
  return items.length;
}

async function main() {
  loadLocal();
  console.log(`[puller] consumer=${CONSUMER} edge=${EDGE_BASE} local=${STORE} interval=${INTERVAL}ms`);
  if (ONCE) {
    await pullOnce();
    return;
  }
  let backoff = 0;
  for (;;) {
    try {
      let n = await pullOnce();
      backoff = 0;
      // 还有更多就立刻继续拉，拉空才等一个间隔
      while (n >= LIMIT) n = await pullOnce();
    } catch (e) {
      backoff = Math.min(backoff ? backoff * 2 : 5000, 300_000);
      console.error(`[pull] error: ${e && e.message}; retry in ${backoff}ms`);
    }
    await new Promise((r) => setTimeout(r, backoff || INTERVAL));
  }
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
