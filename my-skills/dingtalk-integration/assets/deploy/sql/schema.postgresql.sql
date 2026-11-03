-- 形态 B 中间件的 DB 存储（PostgreSQL）
-- 参考实现 relay/server.mjs 用的是 NDJSON 事件日志；日均上万条或多实例时请改这张表。
--
-- 用法：psql -U postgres -d dingtalk_relay -f schema.postgresql.sql

CREATE TABLE IF NOT EXISTS inbound_message (
    id            BIGSERIAL PRIMARY KEY,
    external_id   TEXT        NOT NULL,               -- 幂等键（审批实例 ID）
    consumer      TEXT        NOT NULL,               -- 目标系统标识，如 <system>-prod
    event         TEXT        NOT NULL,               -- upsert | delete | revoke
    payload       JSONB       NOT NULL,               -- 原始请求体，便于重放/追溯
    payload_enc   BYTEA,                              -- 结论 2b 字段级加密时用（密文）
    payload_kid   TEXT,                               -- 加密密钥版本
    status        TEXT        NOT NULL DEFAULT 'pending',
                                                     -- pending | leased | delivered | dead
    attempts      INTEGER     NOT NULL DEFAULT 0,
    lease_until   TIMESTAMPTZ,
    lease_token   TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    delivered_at  TIMESTAMPTZ,
    last_error    TEXT,
    CONSTRAINT inbound_message_status_chk
        CHECK (status IN ('pending', 'leased', 'delivered', 'dead')),
    CONSTRAINT inbound_message_event_chk
        CHECK (event IN ('upsert', 'delete', 'revoke'))
);

-- 幂等：同一 consumer 下 external_id 唯一。重推靠这个冲突返回 duplicate。
CREATE UNIQUE INDEX IF NOT EXISTS ux_inbound_consumer_extid
    ON inbound_message (consumer, external_id);

-- 拉取主查询：按 consumer + 可投递状态，取最老的 N 条
CREATE INDEX IF NOT EXISTS ix_inbound_pullable
    ON inbound_message (consumer, status, created_at)
    WHERE status IN ('pending', 'leased');

-- 死信巡检
CREATE INDEX IF NOT EXISTS ix_inbound_dead
    ON inbound_message (consumer, created_at)
    WHERE status = 'dead';

-- 保留期清理（配合 RETENTION_DAYS；建议配 pg_cron 或 systemd timer 跑）
-- DELETE FROM inbound_message
--  WHERE status = 'delivered' AND delivered_at < now() - interval '60 days';

-- 对账视图：各 consumer 各状态计数 + 最老待投递
CREATE OR REPLACE VIEW v_inbound_stats AS
SELECT consumer,
       count(*) FILTER (WHERE status = 'pending')   AS pending,
       count(*) FILTER (WHERE status = 'leased')    AS leased,
       count(*) FILTER (WHERE status = 'delivered') AS delivered,
       count(*) FILTER (WHERE status = 'dead')      AS dead,
       min(created_at) FILTER (WHERE status = 'pending') AS oldest_pending_at
  FROM inbound_message
 GROUP BY consumer;

-- 拉取的原子领取（多 worker 并发安全）：
--   WITH picked AS (
--     SELECT id FROM inbound_message
--      WHERE consumer = $1
--        AND (status = 'pending' OR (status = 'leased' AND lease_until < now()))
--      ORDER BY created_at
--      LIMIT $2
--      FOR UPDATE SKIP LOCKED
--   )
--   UPDATE inbound_message m
--      SET status='leased', lease_until=now()+($3||' seconds')::interval,
--          lease_token=md5(random()::text)
--    FROM picked WHERE m.id = picked.id
--   RETURNING m.*;
