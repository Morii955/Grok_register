# grok_reg-protocol_cpa

基于 **Chromium + DrissionPage + turnstilePatch** 的免费 Grok 账号注册机。

本分支在原版注册机基础上新增了两点：

1. **Hotmail / Outlook 邮箱凭证池**  
   支持 `邮箱----密码----ClientID----Token` 四段格式读取与 XOAUTH2 IMAP 收验证码。
2. **协议优先的  导出**  
   注册拿到 SSO 后，优先用 **纯 HTTP Device Flow**（`curl_cffi` + `sso` cookie）铸造 CPA 用的 `xai-*.json`；协议失败再回退原浏览器 consent 逻辑。

一条成功链路会产出两类凭证：

| 产物 | 用途 | 路径 |
|------|------|------|
| **SSO** | grok.com / grok2api Web 池 | 账本第三段 + 可选推远端池 |
| **OIDC（CPA xAI）** | 免费 **Grok 4.5**（Grok Build / cli-chat-proxy） | `cpa_auths/xai-<email>.json` |

> **硬约束：SSO ≠ OIDC。**  
> 免费 Grok 4.5 **不能**用账本里的 sso JWT 直接打 API；必须再走  
> `accounts.x.ai` device-auth 铸 OIDC，写成 CPA 的 `type=xai` 认证文件。  
> 本仓库的协议路径正是用 **SSO cookie 自动完成** 这一步（无需再弹浏览器时优先走协议）。

本仓库**自包含** OIDC/CPA 铸造代码（`cpa_xai/`）：

| 路径 | 说明 |
|------|------|
| `cpa_xai/protocol_mint.py` | **新增**：SSO → 纯 HTTP Device Flow（verify / approve / token） |
| `cpa_xai/mint.py` | 协议优先，失败回退 `mint_with_browser` |
| `cpa_xai/browser_confirm.py` | 原逻辑：有头 Chromium 完成 consent |
| `cpa_export.py` | 注册成功 hook |
| `scripts/backfill_cpa_xai_from_accounts.py` | 存量账号批量补 CPA |
| `scripts/export_cpa_xai_from_grok_auth.py` | 从 `~/.grok/auth.json` 导出 |

---

## 快速开始（5 分钟跑起来）

> 只想跑注册机？照下面 4 步走即可，不用先读后面文档。

### 第 0 步：机器准备（对照检查）

| 项 | 要求 |
|----|------|
| 系统 | Windows 10/11 或带图形桌面的 macOS / Linux |
| Chrome | 本机装 Chrome（注册页靠它打开；[下载](https://www.google.com/chrome/)） |
| 代理 | xAI 官网一般需要代理：需要一个本机能用的代理（Clash/V2Ray 等）并记下端口 |
| Python | **不用自己装**，下面脚本会通过 uv 自动拉 Python 3.13 |

### 第 1 步：一键装依赖

```bash
# Windows：在项目根目录打开 PowerShell
powershell -ExecutionPolicy Bypass -File setup.ps1

# macOS / Linux
bash setup.sh
```

脚本依次做：安装/检查 uv → `uv sync`（自动下载 Python 3.13）→ 检查 Chrome → 从预设生成 `config.json` → 打印后续步骤。

不想用脚本就手动跑这三条：

```bash
# ① 装 uv（已有则跳过）
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"   # Windows
curl -LsSf https://astral.sh/uv/install.sh | sh              # macOS / Linux

# ② 装依赖
uv sync

# ③ 生成配置
cp config.cloudflare.json config.json
```

### 第 2 步：改代理端口（唯一必改项）

打开 `config.json`，把 `proxy` 改成你本机的代理端口：

```json
"proxy": "http://127.0.0.1:7890"
```

邮箱服务（临时邮箱 Worker）和 CPA mint 参数预设里都已填好，其余字段不用动；mint 想走另一个代理就填 `cpa_proxy`（留空 = 跟 `proxy` 相同）。

### 第 3 步：冒烟测试

```bash
uv run python -u register_cli.py --extra 1 --threads 1
```

日志里看到 `protocol token ok` / `mint protocol SUCCESS` 就说明整条链路正常（全程约 30–60s）。

### 第 4 步：批量跑

```bash
uv run python -u register_cli.py --extra 200 --threads 4
```

**产出在哪：**

| 文件 | 说明 |
|------|------|
| `accounts_cli.txt` | 账本 `email----password----sso` |
| `cpa_auths/xai-<邮箱>.json` | CPA 认证文件（导入 CLIProxyAPI 用） |

**可选 GUI：** `uv run python grok_register_ttk.py`，可视化配置代理/邮箱并点开始（GUI 会把配置自动存回 `config.json`）。

---

## 本版主要改动

### 1. Hotmail / Outlook：`邮箱----密码----ClientID----Token`

设置：

```json
{
  "email_provider": "hotmail",
  "hotmail_accounts_file": "mail_credentials.txt",
  "hotmail_max_aliases_per_account": 5
}
```

凭证文件（可从模板复制）：

```bash
cp mail_credentials.example.txt mail_credentials.txt
```

**每行格式（四段，`----` 分隔）：**

```text
邮箱----密码----ClientID----Token
```

| 段 | 含义 |
|----|------|
| 邮箱 | Hotmail / Outlook 主邮箱 |
| 密码 | 邮箱登录密码（注册机侧保留；IMAP 走 OAuth） |
| ClientID | 微软应用（Azure AD 应用）Client ID |
| Token | Microsoft OAuth2 **refresh_token**（XOAUTH2 IMAP 用） |

示例：

```text
your@hotmail.com----mailPassword----xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx----0.AXcA...refresh_token...
```

运行时行为摘要：

- 默认先用原邮箱，后续用随机 plus alias（如 `name+k8s2p9qa@domain`）
- 经 `outlook.office365.com`（可回退 `imap-mail.outlook.com`）XOAUTH2 IMAP 拉验证码
- refresh_token 若轮换会**自动回写** `mail_credentials.txt`
- 成功 / 失败 / 占用中的 alias 会参与去重与 `hotmail_max_aliases_per_account` 计数

相关配置见 `config.example.json` 中 `hotmail_*` 注释键。

### 2. 协议 OIDC → CPA（失败回退浏览器）

```
注册成功拿到 sso cookie
        ↓
【优先】protocol_mint：curl_cffi + sso
   device/code → verify → approve → token 轮询
        ↓ 成功
  cpa_auths/xai-<email>.json   mint_method=protocol
        ↓ 失败
【回退】browser_confirm：有头 Chromium + turnstilePatch
   同一套 device-auth，页面点「允许」
        ↓
  cpa_auths/xai-<email>.json   mint_method=browser
```

实测协议路径约数秒级即可完成（含 probe）；浏览器路径约 40–60s/号。

关键配置：

| 字段 | 默认 | 含义 |
|------|------|------|
| `cpa_prefer_protocol` | `true` | 有 SSO 时先走纯 HTTP 协议 mint |
| `cpa_protocol_only` | `false` | `true`=协议失败也不回退浏览器（调试用） |
| `cpa_protocol_poll_timeout_sec` | `90` | 协议路径 token 轮询超时 |
| `cpa_export_enabled` | `true` | 注册成功后是否 mint OIDC |
| `cpa_auth_dir` | `./cpa_auths` | 主导出目录 |
| `cpa_base_url` | `https://cli-chat-proxy.grok.com/v1` | 免费 Build **必须**此上游 |
| `cpa_headless` | `false` | 回退浏览器时建议有头 |
| `cpa_force_standalone` | `true` | 回退时独立 Chromium，不复用注册 tab |
| `cpa_mint_cookie_inject` | `true` | 回退时注入注册 cookie，尽量跳过二次登录 |

日志里可看到：

```text
[cpa] mint try protocol (SSO HTTP device flow)
[cpa] protocol token ok ...
[cpa] mint protocol SUCCESS
[cpa] mint_method=protocol
```

协议失败时类似：

```text
[cpa] mint protocol failed: ...
[cpa] mint fallback → browser
[cpa] mint_method=browser
```

---

## 整链示意

```
[邮箱 Hotmail/Outlook 或 CloudMail 等]
       ↓  注册 accounts.x.ai
 accounts_*.txt / accounts_cli.txt    email----password----sso
       ↓
 grok2api 池 (可选)                   SSO → Web 非免费档模型
       ↓
 OIDC mint（协议优先 → 浏览器回退）
       ↓
 cpa_auths/xai-email.json             【注册机主导出】
       ↓ (cpa_copy_to_hotload=true 时)
 CPA auth-dir 热加载                  【可选】
       ↓
 CLIProxyAPI :8317                    model=grok-4.6（当前免费档）
```

---

## 环境

| 依赖 | 说明 |
|------|------|
| Windows 10/11 或 macOS/Linux + 桌面 | 协议 mint **不需要**浏览器；注册页与回退浏览器需要本机 GUI + Chrome |
| `uv` + Python 3.13 | 本目录 `pyproject.toml` / `uv.lock`；**一键装**：`setup.ps1`（Windows）/ `setup.sh`（macOS/Linux）；可选 `mise` |
| Chrome | 仅注册 + 协议失败回退时需要 |
| 代理 | xAI / accounts.x.ai 通常需要，如 `http://127.0.0.1:7890`；**填在 `config.json` 的 `proxy`** |
| 可选 | 本机 grok2api `:8000`、CLIProxyAPI(CPA) `:8317` |

```bash
cd /path/to/grok_reg-protocol_cpa
# 一键（推荐，见「快速开始」）：
powershell -ExecutionPolicy Bypass -File setup.ps1    # Windows
bash setup.sh                                         # macOS / Linux
# 或手动：
uv sync
uv run python -c "from DrissionPage import Chromium; from curl_cffi import requests; print('OK')"
```

或用 mise：

```bash
mise install
mise run deps
```

---

## 配置

1. 复制模板并编辑（模板内 `"//…"` 键是注释，加载时忽略）：

```bash
cp config.example.json config.json
# 编辑：email_provider、proxy、hotmail_*、cpa_*
```

2. **字段详解见 `config.example.json` 内注释键**。

### 代理优先级

| 字段 | 作用 |
|------|------|
| `proxy` | **注册** Chromium + 邮箱等 HTTP |
| `cpa_proxy` | **OIDC mint**（协议 HTTP + 回退浏览器 + probe） |

```
cpa_proxy  >  proxy  >  环境变量 https_proxy/http_proxy
```

配置优先于 shell 里的 `https_proxy`，避免「config 写了 7890 却被环境变量盖掉」。

### 与 CPA 相关的关键项（摘要）

| 字段 | 含义 | 建议 |
|------|------|------|
| `cpa_export_enabled` | 注册成功后是否 mint OIDC | `true` |
| `cpa_prefer_protocol` | SSO 协议优先 | `true` |
| `cpa_protocol_only` | 仅协议、不回退浏览器 | 调试时 `true`，日常 `false` |
| `cpa_auth_dir` | **主导出目录** | `./cpa_auths` |
| `cpa_copy_to_hotload` | 是否复制到 CPA 热加载目录 | 可选，默认 `false` |
| `cpa_hotload_dir` | CPA `auth-dir` | 仅 copy 时需要 |
| `cpa_base_url` | 上游 API 根 | **必须** `https://cli-chat-proxy.grok.com/v1` |
| `cpa_headless` | 回退浏览器是否无头 | **`false`** |
| `cpa_force_standalone` | 回退时独立浏览器 | **`true`** |
| `cpa_proxy` | mint 专用代理 | 如 `http://127.0.0.1:7890` |
| `cpa_mint_required` | mint 失败是否整号失败 | 通常 `false` |

CLI 与 GUI 都会在注册成功后读这些配置。GUI 下 CPA 导出会串行，避免多窗口抢焦点。

### 落盘约定

| 路径 | 是否必须 | 说明 |
|------|----------|------|
| `mail_credentials.txt` | hotmail 模式必须 | `邮箱----密码----ClientID----Token` |
| `accounts_cli.txt` / `accounts_*.txt` | 是 | 主账本 `email----password----sso` |
| `cpa_auths/xai-*.json` | 是（开 export 时） | CPA 格式 OIDC 归档 |
| CPA `…/auths/xai-*.json` | 可选 | 热加载；由 `cpa_copy_to_hotload` 控制 |

---

## 命令：批量注册 + 认证

前置：

```bash
cd /path/to/grok_reg-protocol_cpa
# 代理建议写在 config.json 的 proxy / cpa_proxy
# 回退浏览器时需要桌面会话
export DISPLAY=${DISPLAY:-:0}
```

### A. 新注册 N 个号（含 SSO + OIDC 导出）

```bash
# 再注册 1 个（推荐）
uv run python -u register_cli.py --extra 1 --threads 1

# 再注册 5 个
uv run python -u register_cli.py --extra 5 --threads 2

# GUI
uv run python grok_register_ttk.py
# 或 mise run gui / mise run register
```

成功时：

1. 追加账本 `email----password----sso`
2. 可选：推 grok2api
3. 若 `cpa_export_enabled`：协议 mint（失败则浏览器）→ `cpa_auths/xai-<email>.json`
4. 若 `cpa_copy_to_hotload`：再拷到 `cpa_hotload_dir`

### B. 存量号补 CPA（只 mint，不重新注册）

账本需含 SSO（第三段）。协议优先，有 SSO 时通常**无需**弹浏览器：

```bash
uv run python -u scripts/backfill_cpa_xai_from_accounts.py \
  --accounts accounts_cli.txt \
  --limit 1 --probe --timeout 300

# 全量缺失号
uv run python -u scripts/backfill_cpa_xai_from_accounts.py \
  --limit 0 --probe --timeout 300 --sleep 3
```

| 参数 | 含义 |
|------|------|
| `--limit N` | 本次最多 N 个缺失号；`0`=全部 |
| `--email x@y` | 只处理指定邮箱 |
| `--out-dir` | 主导出目录 |
| `--cpa-dir` | 成功后复制到 CPA 热加载目录 |
| `--probe` | 检查是否列出最新 `grok-4.x` 免费模型（当前 `grok-4.6`） |
| `--headless` | 回退浏览器时无头（不推荐） |

### C. 从 `~/.grok/auth.json` 导出 CPA 文件

```bash
uv run python scripts/export_cpa_xai_from_grok_auth.py --out-dir ./cpa_auths
```

### D. 手动导入 CPA 热加载

```bash
cp -a ./cpa_auths/xai-USER@domain.json "$CPA_AUTH_DIR"/
chmod 600 "$CPA_AUTH_DIR"/xai-USER@domain.json
```

### E. 调用验证（免费 Grok 4.6）

```bash
KEY="<你的 CPA API KEY>"

curl -sS http://127.0.0.1:8317/v1/models -H "Authorization: Bearer $KEY" | head

curl -sS http://127.0.0.1:8317/v1/chat/completions \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "grok-4.6",
    "messages": [{"role":"user","content":"Reply with exactly OK"}],
    "stream": false
  }'
```

---

## CLI 参数速查（`register_cli.py`）

| 参数 | 含义 |
|------|------|
| `--extra N` | **再新注册 N 个**（推荐） |
| `--count N` | 账号**总数目标**（含已有）；已达标则退出 |
| `--threads N` | 并发 1–10 |
| `--accounts-file` | 账本路径 |

---

## 故障排查

| 现象 | 原因 / 处理 |
|------|-------------|
| 协议 `sso invalid` | SSO 过期或无效；会回退浏览器；检查账本第三段 |
| 协议 verify/approve 失败 | 会话态变化 / 风控；看日志后自动回退浏览器 |
| 一直 `authorization_pending` | 浏览器路径未完成 consent；需到「设备已授权」且 token 200 |
| Cloudflare / Turnstile | 回退浏览器时关 headless、开 turnstilePatch、检查代理 |
| Hotmail 收不到码 | 检查四段凭证、ClientID/Token、IMAP 主机与 alias 计数 |
| 有 token 但无 grok-4.x 免费模型 | `cpa_base_url` 是否为 `cli-chat-proxy` |
| 注册成功但无 `cpa_auths` | `cpa_export_enabled`？看 `cpa_auth_failed.txt` |

调试原则：以 **token 端点返回 `access_token` + refresh_token** 为准；probe 看 `/v1/models` 是否含最新 `grok-4.x` 免费模型（当前 `grok-4.6`）。

---

## 目录结构

```
grok_reg-protocol_cpa/
  register_cli.py              # CLI 批量注册
  grok_register_ttk.py         # 浏览器注册核心 + Hotmail 等
  cpa_export.py                # 成功 hook
  cpa_xai/
    protocol_mint.py           # SSO 纯 HTTP Device Flow（协议优先）
    mint.py                    # 协议 → 浏览器回退编排
    browser_confirm.py         # 原浏览器 consent
    oauth_device.py / schema.py / writer.py / probe.py ...
  scripts/
    backfill_cpa_xai_from_accounts.py
    export_cpa_xai_from_grok_auth.py
  config.example.json
  config.cloudflare.json       # 临时邮箱 Worker 预设（setup 脚本用它生成 config.json）
  setup.ps1 / setup.sh         # 一键环境准备（Windows / macOS / Linux）
  config.json                  # 本地实配（勿外泄）
  mail_credentials.example.txt # 邮箱----密码----ClientID----Token 模板
  mail_credentials.txt         # 本地邮箱池（勿提交）
  accounts_cli.txt             # 主账本
  cpa_auths/                   # xai-<email>.json（分享包勿带）
  turnstilePatch/
  pyproject.toml / uv.lock / mise.toml
```

---

> 快速开始（clone → 5 分钟跑起来）见文档顶部「快速开始」章节：`setup.ps1` / `setup.sh` 一键装好依赖并生成 `config.json`，改一下 `proxy` 端口即可跑 `uv run python -u register_cli.py --extra 1`。
>
> 用 Hotmail 邮箱的话额外两步：
>
> ```bash
> cp mail_credentials.example.txt mail_credentials.txt   # 填 邮箱----密码----ClientID----Token
> # 并把 config.json 的 email_provider 改为 "hotmail"
> ```
---

## 安全

- `config.json`、`mail_credentials.txt`、账本、`cpa_auths/*.json` 含密码与 refresh_token，**权限 600 / 勿提交 git / 勿塞进分享包**
- 免费 Build 有额度与风控；批量 mint 请控速（`--sleep`）

---

## 相关

- CLIProxyAPI / CPA：自备；将 `cpa_auths/xai-*.json` 拷到 CPA auth-dir 即可
- 免费 Grok 4.5 只走 Build OIDC + `cli-chat-proxy`，不是网页 SSO
