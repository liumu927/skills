/**
 * 钉钉登录前端助手 —— 实现模板（原生 JS，无依赖；已在内网生产环境完整验证）
 *
 * 用法：
 *   1) 登录页放一个容器：<div class="dingtalk-login-slot"></div>
 *      （脚本自动探测 /status，未配置则整块隐藏，不显示空按钮）
 *   2) 引入本脚本：<script src="/js/dingtalk-login.js"></script>
 *   3) 登录跳转回来时（URL 带 ?dingtalk_code=xxx），脚本自动用一次性 code 换 token，
 *      写入 localStorage（键：token / currentUser，与密码登录共用），并跳回 return_to。
 *
 * 可调整：顶部 var API = '/api/auth' 改成你自己的路由前缀。
 * 可选覆盖：window.DINGTALK_AFTER_LOGIN 指定登录成功后的默认落点（默认当前路径）。
 */
(function () {
  'use strict';

  var API = '/api/auth';

  function qs(name) {
    var m = new RegExp('[?&]' + name + '=([^&#]*)').exec(location.search || '');
    return m ? decodeURIComponent(m[1].replace(/\+/g, ' ')) : null;
  }

  function saveSession(data) {
    if (!data || !data.token) return;
    localStorage.setItem('token', data.token);
    if (data.user) localStorage.setItem('currentUser', JSON.stringify(data.user));
  }

  // 一键登录：带上当前路径作为登录后返回点（站内相对路径）
  function startDingtalkLogin(returnTo) {
    var to = returnTo || (location.pathname + location.hash);
    location.href = API + '/dingtalk/start?return_to=' + encodeURIComponent(to);
  }
  window.startDingtalkLogin = startDingtalkLogin;

  // 处理回跳：URL 带 dingtalk_code 时换取 token
  async function handleCallbackIfAny() {
    var code = qs('dingtalk_code');
    var err = qs('error');
    if (!code) {
      if (err) showError(err);
      return false;
    }
    try {
      var r = await fetch(API + '/dingtalk/exchange', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code: code })
      });
      var d = await r.json();
      if (!d.success) { showError(d.message || 'dingtalk_exchange_failed'); return false; }
      saveSession(d.data);
      // 清掉 URL 里的参数，避免刷新重复消费
      var clean = location.pathname + (location.hash || '');
      history.replaceState(null, '', clean);
      var to = d.data.return_to || window.DINGTALK_AFTER_LOGIN || clean;
      location.replace(to);
      return true;
    } catch (e) {
      showError('dingtalk_exchange_failed');
      return false;
    }
  }

  var ERROR_TEXT = {
    dingtalk_not_configured: '钉钉登录未配置，请联系管理员',
    dingtalk_no_code: '未获取到钉钉授权码，请重试',
    dingtalk_bad_state: '登录会话已过期（state 校验失败），请重试',
    dingtalk_no_openid: '未获取到钉钉用户标识，请重试',
    dingtalk_exchange_failed: '钉钉登录失败，请重试或改用账号密码登录'
  };

  function showError(code) {
    var box = document.getElementById('dingtalk-error');
    var msg = ERROR_TEXT[code] || ('钉钉登录失败：' + code);
    if (box) { box.textContent = msg; box.style.display = 'block'; }
    else if (window.toast) { try { window.toast(msg, 'error'); } catch (e) { /* ignore */ } }
  }

  // 渲染按钮到所有 .dingtalk-login-slot（探测已配置才显示）
  async function renderButtons() {
    var slots = document.querySelectorAll('.dingtalk-login-slot');
    if (!slots.length) return;
    var configured = false;
    try {
      var r = await fetch(API + '/dingtalk/status');
      var d = await r.json();
      configured = !!(d && d.success && d.data && d.data.configured);
    } catch (e) { configured = false; }

    slots.forEach(function (slot) {
      if (!configured) { slot.style.display = 'none'; return; }
      slot.style.display = '';
      if (slot.dataset.rendered) return;
      slot.dataset.rendered = '1';
      slot.innerHTML =
        '<div class="login-or">或</div>' +
        '<button type="button" class="login-scan">钉钉扫码登录</button>' +
        '<p class="login-scan-hint">平台托管于西三环办公网，仅办公网内可访问</p>' +
        '<div id="dingtalk-error" style="display:none;color:var(--danger,#e53e3e);font-size:12px;margin-top:8px;text-align:center"></div>';
      var btn = slot.querySelector('.login-scan');
      if (btn) btn.addEventListener('click', function () { startDingtalkLogin(); });
    });
  }

  // 子平台 SPA（hash 路由）会在渲染后动态插入 slot：用 MutationObserver 兜住
  function boot() {
    var redirected = false;
    handleCallbackIfAny().then(function (did) {
      redirected = did;
      if (!did) renderButtons();
    });
    var mo = new MutationObserver(function () { if (!redirected) renderButtons(); });
    mo.observe(document.documentElement, { childList: true, subtree: true });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
