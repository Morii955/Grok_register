#!/usr/bin/env bash
# Grok 注册机 - macOS / Linux 一键环境准备
# 用法：在项目根目录运行： bash setup.sh
# 脚本做四件事：装/查 uv → uv sync（自动拉 Python 3.13，不用自己装 Python）→ 查 Chrome → 生成 config.json
set -euo pipefail
cd "$(dirname "$0")"

echo ''
echo '=== [1/4] 检查 uv（Python 包管理器）==='
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
if ! command -v uv >/dev/null 2>&1; then
    echo "未找到 uv，自动安装..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
    if ! command -v uv >/dev/null 2>&1; then
        echo 'uv 安装失败，请手动安装后重跑本脚本：'
        echo '  curl -LsSf https://astral.sh/uv/install.sh | sh'
        echo '  或: brew install uv'
        exit 1
    fi
fi
echo "uv OK: $(command -v uv)"

echo ''
echo '=== [2/4] 检查 Chrome（注册页需要本机 Chrome / Chromium）==='
browser=""
if [[ "$OSTYPE" == "darwin"* ]]; then
    if [[ -d "/Applications/Google Chrome.app" ]]; then browser="/Applications/Google Chrome.app"; fi
    if [[ -z "$browser" && -d "$HOME/Applications/Google Chrome.app" ]]; then browser="$HOME/Applications/Google Chrome.app"; fi
else
    for c in google-chrome google-chrome-stable chromium chromium-browser; do
        if command -v "$c" >/dev/null 2>&1; then browser="$c"; break; fi
    done
fi
if [[ -n "$browser" ]]; then
    echo "浏览器 OK: $browser"
else
    echo '警告: 未找到 Chrome/Chromium。注册页面靠它打开，请先安装：'
    echo '  macOS:   brew install --cask google-chrome'
    echo '  Linux:   sudo apt install google-chrome-stable（或你的发行版包）'
    echo '（只跑协议 mint 不注册的话可以没有浏览器）'
fi

echo ''
echo '=== [3/4] 安装依赖（uv sync，按 uv.lock 精确版本，自动下载 Python 3.13）==='
uv sync
echo '依赖安装完成。'

echo ''
echo '=== [4/4] 准备 config.json ==='
if [[ -f config.json ]]; then
    echo 'config.json 已存在，保留不动（用 GUI 或手动编辑修改）。'
else
    cp config.cloudflare.json config.json
    echo '已从预设 config.cloudflare.json 生成 config.json。'
fi

echo ''
echo '============================================================'
echo '  环境准备完成！接下来补配置 + 跑命令：'
echo ''
echo '  1.【必改】打开 config.json，把 proxy 端口改成本机的代理端口，例如：'
echo '       "proxy": "http://127.0.0.1:7890"'
echo '  2.【邮箱】cloudflare 模式：填你自己的临时邮箱 Worker 地址与域名'
echo '       （cloudflare_api_base + defaultDomains）；或用 hotmail/cloudmail 等其他 provider。'
echo '     （cpa_proxy 留空即可 = 跟 proxy 一样；CPA 参数已预填。）'
echo ''
echo '  3. 冒烟测试（先注册 1 个，看到 "mint protocol SUCCESS" 即链路正常）：'
echo '       uv run python -u register_cli.py --extra 1 --threads 1'
echo ''
echo '  4. 批量跑（示例 200 个、4 并发）：'
echo '       uv run python -u register_cli.py --extra 200 --threads 4'
echo ''
echo '  产出位置：'
echo '       accounts_cli.txt             账本 email----password----sso'
echo '       cpa_auths/xai-<邮箱>.json    CPA 认证文件（导入 CLIProxyAPI 用）'
echo ''
echo '  可选 GUI：uv run python grok_register_ttk.py（需要桌面会话）'
echo '============================================================'
