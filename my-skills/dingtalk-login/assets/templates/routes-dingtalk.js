/**
 * 钉钉登录路由 —— 实现模板（与同目录 dingtalk_login.js 配套）
 *
 * 落位：app.use('/api/auth', require('./routes/dingtalk')) 即可。
 *
 *   GET  /api/auth/dingtalk/status     —— 是否已配置（登录页据此决定是否显示按钮）
 *   GET  /api/auth/dingtalk/start      —— 302 到钉钉授权页（state 防 CSRF）
 *   GET  /api/auth/dingtalk/callback   —— 钉钉回调：换 token → 取用户 → 关联账号 →
 *                                          302 回前端（带一次性 code，不放 JWT 到 URL）
 *   POST /api/auth/dingtalk/exchange   —— 前端用一次性 code 换 { token, user }
 *   POST /api/auth/dingtalk/workbench  —— 钉钉工作台免登（H5 JSAPI 拿 authCode 直接换）
 *   GET  /api/auth/dingtalk/diag       —— 诊断：配置是否就绪 + 到钉钉的出站连通性
 *
 * 登录成功后签发的是本系统 JWT，与密码登录完全一致。
 */
const { Router } = require('express');
const {
  isConfigured, buildAuthUrl, newState, consumeState,
  issueLoginCode, consumeLoginCode, exchangeCode, fetchUserInfo,
  upsertDingtalkUser, signUserToken, landingUrl, defaultRole,
  AUTH_BASE, TOKEN_URL, USERINFO_URL,
} = require('../dingtalk_login');

const router = Router();

// 是否已配置（不泄露任何密钥内容）
router.get('/dingtalk/status', (req, res) => {
  res.json({
    success: true,
    data: {
      configured: isConfigured(),
      redirect_uri: process.env.DINGTALK_REDIRECT_URI || null,
      landing_url: landingUrl(),
      default_role: defaultRole(),
    },
  });
});

// 诊断：配置项是否齐全 + 钉钉域名出站连通性（只做 HEAD/GET 探测，不发送凭据）
router.get('/dingtalk/diag', async (req, res) => {
  const checks = {
    DINGTALK_CLIENT_ID: Boolean(process.env.DINGTALK_CLIENT_ID),
    DINGTALK_CLIENT_SECRET: Boolean(process.env.DINGTALK_CLIENT_SECRET),
    DINGTALK_REDIRECT_URI: process.env.DINGTALK_REDIRECT_URI || null,
    DINGTALK_LANDING_URL: landingUrl(),
    DINGTALK_DEFAULT_ROLE: defaultRole(),
  };
  async function probe(url) {
    const t0 = Date.now();
    try {
      const r = await fetch(url, { method: 'GET', redirect: 'manual' });
      return { ok: true, status: r.status, ms: Date.now() - t0 };
    } catch (e) {
      return { ok: false, error: e.message, ms: Date.now() - t0 };
    }
  }
  const [auth, token, userinfo] = await Promise.all([
    probe(AUTH_BASE + '?response_type=code&client_id=diag&redirect_uri=https%3A%2F%2Fexample.invalid%2Fcb&scope=openid&state=diag'),
    probe(TOKEN_URL),
    probe(USERINFO_URL),
  ]);
  res.json({ success: true, data: { configured: isConfigured(), env: checks, outbound: { auth, token, userinfo } } });
});

// 授权入口：生成 state → 302 到钉钉。可选 return_to（站内相对路径）决定登录后回到哪。
router.get('/dingtalk/start', (req, res) => {
  if (!isConfigured()) {
    return res.status(503).json({ success: false, message: '钉钉登录未配置（缺少 DINGTALK_CLIENT_ID/CLIENT_SECRET/REDIRECT_URI）' });
  }
  const state = newState(req.query.return_to);
  res.redirect(buildAuthUrl(state, process.env.DINGTALK_REDIRECT_URI));
});

// 回调：钉钉 302 用户浏览器到此（authCode 或 code，两种参数名都兼容）
router.get('/dingtalk/callback', async (req, res) => {
  const landing = landingUrl();
  const fail = (reason) => res.redirect(`${landing}${landing.includes('?') ? '&' : '?'}error=${reason}`);
  if (!isConfigured()) return fail('dingtalk_not_configured');

  const authCode = req.query.authCode || req.query.code;
  const state = req.query.state;
  if (!authCode) return fail('dingtalk_no_code');
  const stateRec = consumeState(state); // state 不匹配/过期 → 防 CSRF
  if (!stateRec) return fail('dingtalk_bad_state');

  try {
    const tokenResult = await exchangeCode(authCode);
    const info = await fetchUserInfo(tokenResult.accessToken);
    if (!info.openId) return fail('dingtalk_no_openid');
    const user = upsertDingtalkUser(info);
    const token = signUserToken(user);
    // 一次性 code 落服务端；同时把 return_to 一并带回（前端据此跳回入口页）
    const code = issueLoginCode({ token, user, returnTo: stateRec.returnTo || null });
    return res.redirect(`${landing}${landing.includes('?') ? '&' : '?'}dingtalk_code=${code}`);
  } catch (err) {
    console.error('[dingtalk-login] callback 失败:', err.message);
    return fail('dingtalk_exchange_failed');
  }
});

// 前端用一次性 code 换 token（JWT 不经过 URL，避免进浏览器历史和日志）
router.post('/dingtalk/exchange', (req, res) => {
  const rec = consumeLoginCode(req.body && req.body.code);
  if (!rec) return res.status(400).json({ success: false, message: '登录码无效或已过期，请重新登录' });
  res.json({ success: true, data: { token: rec.token, user: rec.user, return_to: rec.returnTo || null } });
});

// 工作台免登：钉钉 H5 微应用内 JSAPI 拿到 authCode 后 POST 到此
router.post('/dingtalk/workbench', async (req, res) => {
  if (!isConfigured()) return res.status(503).json({ success: false, message: '钉钉登录未配置' });
  const authCode = req.body && req.body.authCode;
  if (!authCode) return res.status(400).json({ success: false, message: 'authCode 必填' });
  try {
    const tokenResult = await exchangeCode(authCode);
    const info = await fetchUserInfo(tokenResult.accessToken);
    if (!info.openId) return res.status(400).json({ success: false, message: '未取得 openId' });
    const user = upsertDingtalkUser(info);
    res.json({ success: true, data: { token: signUserToken(user), user } });
  } catch (err) {
    console.error('[dingtalk-login] workbench 失败:', err.message);
    res.status(500).json({ success: false, message: '钉钉免登失败：' + err.message });
  }
});

module.exports = router;
