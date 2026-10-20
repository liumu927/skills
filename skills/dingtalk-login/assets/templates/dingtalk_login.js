/**
 * 钉钉登录（扫码 / OAuth2 授权码模式）—— 实现模板（已在内网生产环境完整验证）
 *
 * 落位：放到你的项目 server/ 目录下（文件名可自定）。
 * 依赖宿主项目提供三个模块（按需替换为自己的等价实现）：
 *   - ./db               导出 getDb()，返回 better-sqlite3 实例（users 表需含
 *                        dingtalk_open_id/union_id/nick 列，openId 上建唯一索引）
 *   - ./middleware/auth  导出 JWT_SECRET / JWT_EXPIRES_IN（与密码登录共用同一套 JWT 密钥）
 *   - ./password         导出 hashPassword(明文)（自动建号时生成「无人知道明文」的占位）
 *
 * 设计要点：
 *   - 只把「登录这一步」接到钉钉；登录成功后签发本系统自己的 JWT，业务侧零感知。
 *   - 回调地址由 DINGTALK_REDIRECT_URI 注入。钉钉服务器只校验它、不访问它
 *     （是用户浏览器被 302 过去），所以可以指向内网地址，无需把业务系统暴露到公网。
 *   - 服务端需要出站访问 api.dingtalk.com（换 token / 取用户信息）。
 *   - 账号以 dingtalk_open_id 为幂等键关联；首次登录自动建号（默认最低权限），
 *     管理员再提权。绝不按姓名/手机号自动认领已有账号（防「同名即接管」越权）。
 *   - 若与其它系统跨应用关联同一自然人：用 unionId（openId 是应用级的，换应用就变）。
 *
 * state 与一次性登录码都放在进程内存（短 TTL）。登录是低频操作，
 * 进程重启只会让「进行中的登录」失效，不影响已登录用户（JWT 是自包含的）。
 * 多实例部署时 state/一次性码需换成共享存储（如 Redis）。
 */
const crypto = require('crypto');
const jwt = require('jsonwebtoken');
const { JWT_SECRET, JWT_EXPIRES_IN } = require('./middleware/auth');
const { hashPassword } = require('./password');
const getDb = require('./db');

const AUTH_BASE = 'https://login.dingtalk.com/oauth2/auth';
const TOKEN_URL = 'https://api.dingtalk.com/v1.0/oauth2/userAccessToken';
const USERINFO_URL = 'https://api.dingtalk.com/v1.0/contact/users/me';

const STATE_TTL_MS = 10 * 60 * 1000;   // 授权页停留时间上限
const CODE_TTL_MS = 2 * 60 * 1000;     // 一次性登录码有效期（换 token 用）

// 仅本进程内存：state → 过期时间；code → { jwt, user, expireAt }
const pendingStates = new Map();
const loginCodes = new Map();

function sweep() {
  const now = Date.now();
  for (const [k, v] of pendingStates) if (v.expireAt < now) pendingStates.delete(k);
  for (const [k, v] of loginCodes) if (v.expireAt < now) loginCodes.delete(k);
}
setInterval(sweep, 60 * 1000).unref();

// ===== 配置 =====
function clientId() { return process.env.DINGTALK_CLIENT_ID || ''; }
function clientSecret() { return process.env.DINGTALK_CLIENT_SECRET || ''; }

// 是否已配置（未配置时登录页不显示钉钉按钮，接口返回明确提示）
function isConfigured() {
  return Boolean(clientId() && clientSecret() && process.env.DINGTALK_REDIRECT_URI);
}

// 登录成功后前端落点（SPA 读取一次性 code 并换 token）
function landingUrl() {
  return process.env.DINGTALK_LANDING_URL || '/';
}

// 默认角色：钉钉首次登录自动建号时使用（最低权限，管理员再提权）
function defaultRole() {
  const r = process.env.DINGTALK_DEFAULT_ROLE || 'viewer';
  return ['viewer', 'editor', 'admin'].includes(r) ? r : 'viewer';
}

// ===== 授权地址 =====
function buildAuthUrl(state, redirectUri) {
  const params = new URLSearchParams({
    redirect_uri: redirectUri,
    response_type: 'code',
    client_id: clientId(),
    scope: 'openid',
    state,
    prompt: 'consent',
  });
  return `${AUTH_BASE}?${params.toString()}`;
}

function newState(returnTo) {
  const state = crypto.randomBytes(16).toString('hex');
  pendingStates.set(state, { expireAt: Date.now() + STATE_TTL_MS, returnTo: safeReturnPath(returnTo) });
  return state;
}

function consumeState(state) {
  if (!state) return null;
  const rec = pendingStates.get(state);
  pendingStates.delete(state);
  if (!rec || rec.expireAt < Date.now()) return null;
  return rec;
}

// 只接受站内相对路径（防开放重定向）：必须以 / 开头，且不是 // 或 /\（协议相对）
function safeReturnPath(p) {
  const s = String(p || '').trim();
  if (!s || !s.startsWith('/') || s.startsWith('//') || s.startsWith('/\\')) return null;
  return s;
}

// ===== 一次性登录码（避免把 JWT 放进 URL）=====
function issueLoginCode(payload) {
  const code = crypto.randomBytes(24).toString('hex');
  loginCodes.set(code, { ...payload, expireAt: Date.now() + CODE_TTL_MS });
  return code;
}

function consumeLoginCode(code) {
  if (!code) return null;
  const rec = loginCodes.get(code);
  loginCodes.delete(code); // 一次性：取出即失效
  if (!rec || rec.expireAt < Date.now()) return null;
  return rec;
}

// ===== 钉钉接口调用 =====
async function exchangeCode(authCode) {
  const res = await fetch(TOKEN_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      clientId: clientId(),
      clientSecret: clientSecret(),
      code: authCode,
      grantType: 'authorization_code',
    }),
  });
  const text = await res.text();
  if (!res.ok) throw new Error(`换 token 失败(${res.status}): ${text}`);
  const data = JSON.parse(text);
  if (!data.accessToken) throw new Error(`换 token 响应缺少 accessToken: ${text}`);
  return data;
}

async function fetchUserInfo(accessToken) {
  const res = await fetch(USERINFO_URL, {
    headers: { 'x-acs-dingtalk-access-token': accessToken },
  });
  const text = await res.text();
  if (!res.ok) throw new Error(`取用户信息失败(${res.status}): ${text}`);
  const data = JSON.parse(text);
  return {
    openId: data.openId,
    unionId: data.unionId || null,
    nick: data.nick || '',
    avatarUrl: data.avatarUrl || '',
    mobile: data.mobile || '',
  };
}

// ===== 账号关联 =====
// openId 幂等：命中则更新昵称并返回；未命中则新建（默认最低权限）。
// 不按姓名/手机号自动贴靠既有账号，避免「同名即接管」的越权风险。
function upsertDingtalkUser(info) {
  const db = getDb();
  const existing = db.prepare('SELECT * FROM users WHERE dingtalk_open_id = ?').get(info.openId);
  if (existing) {
    // 每次登录刷新钉钉昵称；display_name 只在为空时补，避免覆盖管理员人工设置的姓名
    // （论文侧「我的成果」按姓名匹配，人工校对过的姓名不该被钉钉昵称冲掉）
    const nextDisplay = existing.display_name || info.nick || null;
    db.prepare('UPDATE users SET dingtalk_nick = ?, dingtalk_union_id = COALESCE(?, dingtalk_union_id), display_name = ? WHERE id = ?')
      .run(info.nick || existing.dingtalk_nick || null, info.unionId, nextDisplay, existing.id);
    return db.prepare('SELECT id, username, display_name, role, password_changed FROM users WHERE id = ?').get(existing.id);
  }

  // 生成唯一用户名：dt_ + openId 前 10 位（openId 全局唯一，碰撞概率极低，仍做兜底）
  let base = 'dt_' + String(info.openId).replace(/[^a-zA-Z0-9]/g, '').slice(0, 10);
  if (!base || base === 'dt_') base = 'dt_' + crypto.randomBytes(4).toString('hex');
  let username = base;
  let n = 1;
  while (db.prepare('SELECT 1 FROM users WHERE username = ?').get(username)) {
    username = `${base}_${n++}`;
  }

  const displayName = info.nick || `钉钉用户_${username.slice(3)}`;
  // 钉钉登录不走密码：随机明文再哈希，得到「无人知道明文」的不可登录占位
  const placeholder = hashPassword(crypto.randomBytes(32).toString('hex'));
  const info2 = db.prepare(`
    INSERT INTO users (username, password_hash, role, password_changed, display_name,
                       dingtalk_open_id, dingtalk_union_id, dingtalk_nick, auth_provider)
    VALUES (?,?,?,?,?,?,?,?, 'dingtalk')
  `).run(username, placeholder, defaultRole(), 1, displayName, info.openId, info.unionId, info.nick || null);

  return db.prepare('SELECT id, username, display_name, role, password_changed FROM users WHERE id = ?').get(info2.lastInsertRowid);
}

// 签发本系统 JWT（与密码登录同一套密钥/载荷，业务侧零感知）
function signUserToken(user) {
  return jwt.sign(
    { id: user.id, username: user.username, display_name: user.display_name || null, role: user.role },
    JWT_SECRET,
    { expiresIn: JWT_EXPIRES_IN }
  );
}

module.exports = {
  isConfigured,
  buildAuthUrl,
  newState,
  consumeState,
  issueLoginCode,
  consumeLoginCode,
  exchangeCode,
  fetchUserInfo,
  upsertDingtalkUser,
  signUserToken,
  landingUrl,
  defaultRole,
  AUTH_BASE,
  TOKEN_URL,
  USERINFO_URL,
};
