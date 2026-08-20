# Grok 注册机 - Windows 一键环境准备
# 用法：在项目根目录打开 PowerShell，运行：
#   powershell -ExecutionPolicy Bypass -File setup.ps1
# 脚本做四件事：装/查 uv → uv sync（自动拉 Python 3.13，不用自己装 Python）→ 查 Chrome → 生成 config.json

$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot

Write-Host ''
Write-Host '=== [1/4] 检查 uv（Python 包管理器）===' -ForegroundColor Cyan
function Find-Uv {
    $cmd = Get-Command uv -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    foreach ($p in @("$env:USERPROFILE\.local\bin\uv.exe", "$env:LOCALAPPDATA\Microsoft\WinGet\Links\uv.exe", "$env:USERPROFILE\AppData\Roaming\uv\uv.exe")) {
        if (Test-Path $p) { return $p }
    }
    return $null
}
$uvExe = Find-Uv
if (-not $uvExe) {
    Write-Host '未找到 uv，尝试用 winget 安装...'
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if ($winget) {
        winget install --id astral-sh.uv -e --accept-source-agreements --accept-package-agreements
        $uvExe = Find-Uv
    }
    if (-not $uvExe) {
        Write-Host ''
        Write-Host 'winget 装不上，请手动装 uv（任选其一），然后重新运行本脚本：' -ForegroundColor Yellow
        Write-Host '  方式1: powershell -c "irm https://astral.sh/uv/install.ps1 | iex"'
        Write-Host '  方式2: pip install uv'
        Write-Host '  文档:   https://docs.astral.sh/uv/getting-started/installation/'
        exit 1
    }
}
Write-Host ("uv OK: " + $uvExe)

Write-Host ''
Write-Host '=== [2/4] 检查 Chrome（注册页需要本机 Chrome 或 Edge）===' -ForegroundColor Cyan
$browser = $null
foreach ($p in @(
    "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
    "$env:LocalAppData\Google\Chrome\Application\chrome.exe",
    "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
    "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe"
)) {
    if ($p -and (Test-Path $p)) { $browser = $p; break }
}
if ($browser) {
    Write-Host ("浏览器 OK: " + $browser)
} else {
    Write-Host '未找到 Chrome/Edge。注册页面靠它打开，请先安装 Chrome：https://www.google.com/chrome/' -ForegroundColor Yellow
    Write-Host '（装完重跑本脚本；只跑协议 mint 不注册的话可以没有浏览器）'
}

Write-Host ''
Write-Host '=== [3/4] 安装依赖（uv sync，按 uv.lock 精确版本，自动下载 Python 3.13）===' -ForegroundColor Cyan
& $uvExe sync
if ($LASTEXITCODE -ne 0) { Write-Host 'uv sync 失败，检查网络（可能需要代理）后重试。' -ForegroundColor Red; exit 1 }
Write-Host '依赖安装完成。' -ForegroundColor Green

Write-Host ''
Write-Host '=== [4/4] 准备 config.json ===' -ForegroundColor Cyan
if (Test-Path 'config.json') {
    Write-Host 'config.json 已存在，保留不动（用 GUI 或手动编辑修改）。'
} else {
    Copy-Item 'config.cloudflare.json' 'config.json'
    Write-Host '已从预设 config.cloudflare.json 生成 config.json。' -ForegroundColor Green
}

Write-Host ''
Write-Host '============================================================' -ForegroundColor Green
Write-Host '  环境准备完成！接下来补配置 + 跑命令：'
Write-Host ''
Write-Host '  1.【必改】打开 config.json，把 proxy 端口改成本机的代理端口，例如：'
Write-Host '       "proxy": "http://127.0.0.1:7890"'
Write-Host '  2.【邮箱】cloudflare 模式：填你自己的临时邮箱 Worker 地址与域名'
Write-Host '       （cloudflare_api_base + defaultDomains）；或用 hotmail/cloudmail 等其他 provider。'
Write-Host '     （cpa_proxy 留空即可 = 跟 proxy 一样；CPA 参数已预填。）'
Write-Host ''
Write-Host '  3. 冒烟测试（先注册 1 个，看到 "mint protocol SUCCESS" 即链路正常）：'
Write-Host '       uv run python -u register_cli.py --extra 1 --threads 1'
Write-Host ''
Write-Host '  4. 批量跑（示例 200 个、4 并发）：'
Write-Host '       uv run python -u register_cli.py --extra 200 --threads 4'
Write-Host ''
Write-Host '  产出位置：'
Write-Host '       accounts_cli.txt            账本 email----password----sso'
Write-Host '       cpa_auths\xai-<邮箱>.json    CPA 认证文件（导入 CLIProxyAPI 用）'
Write-Host ''
Write-Host '  可选 GUI：uv run python grok_register_ttk.py'
Write-Host '============================================================' -ForegroundColor Green
