# 客户端 DNS / 代理自检（钉钉登录排障通用版）
#
# 用途：系统地址"时灵时不灵"、扫码后回调落到 404、或「nslookup 正确但浏览器打不开」时，
#       在**出问题的那台机器**上跑本脚本，一次性看清所有解析/代理通道。
#
# 用法：
#   powershell -NoProfile -ExecutionPolicy Bypass -File client-dns-check.ps1 -Domain <登录域名> -OriginIp <源站内网IP>
#   可选参数：-Port <端口，默认 443 不带端口显示>  -Scheme <https|http，默认 https>  -ProbePath <健康检查路径，默认 healthz>
#   例：./client-dns-check.ps1 -Domain patents.example.com -OriginIp 192.168.3.14 -Port 4322
#
# 判读标准：该域名必须解析到 -OriginIp 指定的源站；任何解析器/缓存给出其它公网 IP 都是隐患。
# （若场景是"裸 IP + HTTP"访问则无 DNS 问题可言，本脚本不适用——问题多半在代理或证书页拦截。）

param(
  [Parameter(Mandatory=$true)][string]$Domain,
  [Parameter(Mandatory=$true)][string]$OriginIp,
  [int]$Port = 0,
  [string]$Scheme = 'https',
  [string]$ProbePath = 'healthz'
)

$domain = $Domain
$origin = $OriginIp
$portPart = if ($Port -and $Port -ne 443) { ":$Port" } else { '' }
$probeUrl = "$Scheme`://$domain$portPart/$ProbePath"

function Show($s) { Write-Output $s }

Show "================ 目标: $probeUrl   期望解析: $origin ================"

Show ""
Show "================ 1. 各网卡当前生效的 DNS ================"
$servers = @()
Get-DnsClientServerAddress -AddressFamily IPv4 |
  Where-Object { $_.ServerAddresses } |
  ForEach-Object {
    "{0,-30} -> {1}" -f $_.InterfaceAlias, ($_.ServerAddresses -join ', ')
    $servers += $_.ServerAddresses
  }
$servers = $servers | Sort-Object -Unique
Show ""
Show ("全部解析器: " + ($servers -join ', '))
Show "（注意：nslookup 只问排在最前的那一台；VPN/虚拟机网卡也可能带自己的 DNS）"

Show ""
Show "================ 2. DHCP 下发 vs 手工设置 ================"
$map = @{}
Get-NetAdapter | ForEach-Object { $map[$_.InterfaceGuid.ToLower()] = $_.Name }
Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Services\Tcpip\Parameters\Interfaces\*' -ErrorAction SilentlyContinue |
  Where-Object { $_.DhcpNameServer -or $_.NameServer } |
  ForEach-Object {
    $n = $map[$_.PSChildName.ToLower()]; if (-not $n) { $n = $_.PSChildName }
    "  {0,-28} DHCP下发=[{1}]  手工设置=[{2}]" -f $n, $_.DhcpNameServer, $_.NameServer
  }
Show "（DHCP 下发列里若含公网 DNS 或非源站 DNS 服务器，续租后会把故障带回来）"

Show ""
Show "================ 3. 逐台解析器实测该域名 + 响应耗时 ================"
Show "（Chromium 内核浏览器会同时问多台解析器、用先返回的那个；'哪台快'决定浏览器走哪边）"
$bad = @()
foreach ($s in $servers) {
  try {
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    $ip = (Resolve-DnsName $domain -Type A -Server $s -DnsOnly -ErrorAction Stop |
           Where-Object { $_.IPAddress }).IPAddress
    $sw.Stop()
    if ($ip -contains $origin) {
      "  {0,-18} -> {1,-16} {2,5} ms   OK" -f $s, ($ip -join ', '), $sw.ElapsedMilliseconds
    } else {
      "  {0,-18} -> {1,-16} {2,5} ms   <== 错！不是源站 $origin" -f $s, ($ip -join ', '), $sw.ElapsedMilliseconds
      $bad += $s
    }
  } catch {
    "  {0,-18} -> 查询失败: {1}" -f $s, $_.Exception.Message
    $bad += $s
  }
}
if (-not $bad) { Show "  全部解析器正确。" } else { Show ("  有问题的解析器: " + ($bad -join ', ') + "  → 必须从本机 DNS 列表里去掉") }

Show ""
Show "================ 4. 代理 / 加速器（最容易被忽略：它会顶替系统 DNS） ================"
$ie = Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings' -ErrorAction SilentlyContinue
"  系统代理开关 ProxyEnable = {0}   服务器 = {1}" -f $ie.ProxyEnable, $ie.ProxyServer
$ov = @((($ie.ProxyOverride | Out-String).Trim() -split ';') | Where-Object { $_ -ne '' })
$bypassed = $ov | Where-Object { $_ -eq $domain -or $_ -like "*$domain*" }
if ($bypassed) { "  绕过列表已含该域名: " + ($bypassed -join ', ') }
else { "  ⚠ 绕过列表【不含】$domain —— 一旦代理开启，该域名的请求会交给代理，由代理自己的 DNS 解析（很可能拿到公网答案）" }

$proxyProcs = Get-Process -ErrorAction SilentlyContinue |
  Where-Object { $_.ProcessName -match 'clash|mihomo|v2ray|xray|sing-box|verge|neko|trojan|shadow|warp|surge|quantumult|ssr|proxy' }
if ($proxyProcs) {
  "  ⚠ 检测到代理类进程（可能是导致 nslookup 正确、浏览器仍打不开的原因）:"
  $proxyProcs | Select-Object -Unique ProcessName, Id | ForEach-Object { "      {0} (PID {1})" -f $_.ProcessName, $_.Id }
} else { "  未检测到常见代理进程" }

$proxyPorts = @(7890, 7891, 7892, 1080, 1081, 8080, 10808, 20171, 33210)
$listening = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
  Where-Object { $proxyPorts -contains $_.LocalPort -and $_.LocalAddress -in @('127.0.0.1', '0.0.0.0', '::1', '::') }
if ($listening) {
  "  ⚠ 本地代理端口在监听:"
  $listening | Select-Object -Unique LocalAddress, LocalPort | ForEach-Object { "      {0}:{1}" -f $_.LocalAddress, $_.LocalPort }
  $port2 = ($listening | Select-Object -First 1).LocalPort
  Show "  → 立即验证（走代理 vs 直连，目的地一眼可辨）:"
  foreach ($m in @('proxy', 'direct')) {
    if ($m -eq 'proxy') {
      $out = & curl.exe -s -o NUL -w "%{http_code} %{remote_ip}" -x "http://127.0.0.1:$port2" --max-time 12 $probeUrl 2>$null
    } else {
      $out = & curl.exe -s -o NUL -w "%{http_code} %{remote_ip}" --noproxy '*' --max-time 12 $probeUrl 2>$null
    }
    "      {0,-7} -> {1}" -f $m, $out
  }
  Show "      （proxy 与 direct 结果不同 = 问题就在代理分流；在代理里给该域名加 DIRECT 规则）"
} else { "  未发现常见本地代理端口在监听" }

Show ""
Show "================ 5. 系统解析 + DNS 缓存 + 源站连通性 ================"
try {
  $ip = (Resolve-DnsName $domain -Type A -ErrorAction Stop | Where-Object { $_.IPAddress }).IPAddress
  "  Resolve-DnsName 结果: {0}" -f ($ip -join ', ')
  if (-not ($ip -contains $origin)) { Show "  <== 没有解析到源站 $origin，浏览器必然走错" }
} catch { "  Resolve-DnsName 失败: $($_.Exception.Message)" }

$cached = Get-DnsClientCache -ErrorAction SilentlyContinue |
  Where-Object { $_.Entry -eq $domain -and $_.Data } |
  Select-Object -ExpandProperty Data -Unique
if ($cached) {
  "  系统 DNS 缓存里的答案: {0}" -f ($cached -join ', ')
  if (-not ($cached -contains $origin)) {
    Show "  <== 缓存里不是源站答案！nslookup 看不到它（nslookup 不走缓存）——这就是「nslookup 对、浏览器错」的典型形态"
    Show "      处置: ipconfig /flushdns 立即清掉；若反复被写回，见第 3/4 节"
  }
} else { "  系统 DNS 缓存: 无该域名条目（正常）" }

try {
  $r = Invoke-WebRequest $probeUrl -UseBasicParsing -TimeoutSec 8
  "  $ProbePath -> $($r.StatusCode) $($r.Content.Trim().Substring(0, [Math]::Min(80, $r.Content.Trim().Length)))"
} catch {
  Show "  $ProbePath 请求失败: $($_.Exception.Message)  （TLS 证书名不符也会到这一步——确认访问的是登记给钉钉的域名而非裸 IP）"
}

Show ""
Show "================ 6. 其它可能绕过系统 DNS 的通道 ================"
$v6 = Get-DnsClientServerAddress -AddressFamily IPv6 -ErrorAction SilentlyContinue |
  Where-Object { $_.ServerAddresses } |
  ForEach-Object {
    $real = @($_.ServerAddresses | Where-Object { $_ -notlike 'fec0:0:0:ffff:*' })
    if ($real) { "  {0,-30} -> {1}" -f $_.InterfaceAlias, ($real -join ', ') }
  }
if ($v6) { Show "  ⚠ 存在真实 IPv6 DNS（nslookup 默认看不到这些，浏览器却可能用）:"; $v6 } else { "  IPv6 DNS: 无真实解析器（正常）" }

$vpn = Get-NetAdapter -ErrorAction SilentlyContinue |
  Where-Object { $_.Status -eq 'Up' -and $_.InterfaceDescription -match 'TAP|TUN|Wintun|WireGuard|OpenVPN|VPN|Virtual|VMware|Hyper-V|Tailscale|ZeroTier' }
if ($vpn) {
  Show "  ⚠ 存在已启用的虚拟/VPN 网卡（可能带来第二套 DNS）:"
  $vpn | ForEach-Object {
    $d = (Get-DnsClientServerAddress -InterfaceIndex $_.ifIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue).ServerAddresses
    "      {0} [{1}]  DNS={2}" -f $_.Name, $_.InterfaceDescription, ($(if ($d) { $d -join ', ' } else { '—' }))
  }
} else { "  已启用的虚拟/VPN 网卡: 无" }

$hostsHit = Get-Content "$env:SystemRoot\System32\drivers\etc\hosts" -ErrorAction SilentlyContinue |
  Where-Object { $_ -match [regex]::Escape($domain) -and $_ -notmatch '^\s*#' }
if ($hostsHit) { "  hosts 已有记录: " + ($hostsHit -join ' | ') } else { "  hosts: 无该域名记录" }

Show ""
Show "================ 7. 浏览器扩展扫描 + 无痕对照 ================"
$extRoots = @(
  @{ Name = 'Edge';   Path = "$env:LOCALAPPDATA\Microsoft\Edge\User Data\Default\Extensions" },
  @{ Name = 'Chrome'; Path = "$env:LOCALAPPDATA\Google\Chrome\User Data\Default\Extensions" }
)
$riskyFound = $false
foreach ($root in $extRoots) {
  if (-not (Test-Path $root.Path)) { continue }
  Show ("  [$($root.Name)]")
  Get-ChildItem $root.Path -Directory -ErrorAction SilentlyContinue | ForEach-Object {
    $idDir = $_.FullName
    Get-ChildItem $idDir -Directory -ErrorAction SilentlyContinue | ForEach-Object {
      $mf = Join-Path $_.FullName 'manifest.json'
      if (-not (Test-Path $mf)) { return }
      try {
        $m = Get-Content $mf -Raw -Encoding UTF8 | ConvertFrom-Json
        $perms = @() + $m.permissions + $m.optional_permissions + $m.host_permissions
        $risky = @($perms | Where-Object { $_ -match 'proxy|webRequest|declarativeNetRequest' })
        $name = $m.name
        if ($name -like '__MSG_*') {
          $loc = Join-Path $_.FullName '_locales'
          foreach ($locName in @('zh_CN','en','en_US')) {
            $lm = Join-Path $loc "$locName\messages.json"
            if (Test-Path $lm) {
              $lj = Get-Content $lm -Raw -Encoding UTF8 | ConvertFrom-Json
              foreach ($key in @('name','extName','appName')) {
                if ($lj.$key) { $name = $lj.$key.message; break }
              }
              break
            }
          }
        }
        if ($risky) {
          $riskyFound = $true
          $extId = Split-Path $idDir -Leaf
          "    ⚠ {0}  (ID {1})  敏感权限: {2}" -f $name, $extId, ($risky -join ', ')
        } else {
          "      {0}" -f $name
        }
      } catch { }
    }
  }
}
if ($riskyFound) {
  Show "  ↑ 带 proxy / webRequest / declarativeNetRequest 的扩展能改写或接管请求，是「无痕正常、普通不正常」的头号嫌疑。"
} else {
  Show "  （未发现带 proxy/webRequest/declarativeNetRequest 的扩展）"
}

Show @"

  【决定性对照实验：无痕 vs 普通窗口】
    1) 普通窗口打开 $probeUrl   结果: ____________
    2) 全新普通窗口同一地址     结果: ____________
    3) 无痕/InPrivate 同一地址  结果: ____________

    判读：
      · 无痕正常、普通不正常，且第 1-6 节全绿 → 扩展或普通窗口自己的缓存/连接池。
        处置：禁用扩展；清浏览器 DNS 缓存（edge://net-internals/#dns → Clear host cache）后 Ctrl+Shift+R。
      · 三种都不正常 → 系统层问题，按第 1-6 节结论处置。
      · 只有无痕不正常 → 与网络无关（无痕缺 Cookie/登录态）。
"@

Show ""
Show "================ 8. 浏览器侧（需人工确认） ================"
foreach ($k in @('Google\Chrome','Microsoft\Edge')) {
  $p = "HKLM:\SOFTWARE\Policies\$k"
  if (Test-Path $p) {
    $v = Get-ItemProperty $p -ErrorAction SilentlyContinue
    "  {0} 策略: DnsOverHttpsMode=[{1}] Templates=[{2}]" -f $k, $v.DnsOverHttpsMode, $v.DnsOverHttpsTemplates
  } else {
    "  {0}: 无强制策略（用户仍可能在设置里手动开「使用安全 DNS/DoH」）" -f $k
  }
}
Show @"
  请在出问题的浏览器里：
    a) 地址栏打开 $probeUrl —— 返回正常业务响应 = 已走对；404/打不开 = 仍走错
    b) F12 → Network → 点那条请求 → 看 Remote Address（是 $origin 还是别的 IP）
    c) 关掉「使用安全 DNS/DoH」，清浏览器 DNS 缓存后强刷

  【最快止住：hosts 兜底】
    反复出问题又查不清时，用管理员权限在 hosts 里把 $domain 钉死到 $origin
    （优先级高于 DNS/DoH/缓存；对「请求被交给代理解析」无效，那条靠代理绕过列表）。
"@
