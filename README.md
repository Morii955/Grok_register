# Grok 注册机（CPA 版）

基于 **Chromium + DrissionPage + turnstilePatch** 的免费 Grok 账号注册机。注册成功拿到 SSO 后，自动铸造 **CPA 认证文件（OIDC）**，可直接导入 CLIProxyAPI 类网关调用免费 Grok Build（`cli-chat-proxy`）。

**核心能力：**

- **注册**：本机 Chrome + turnstilePatch 过 CF；邮箱支持 Cloudflare 临时邮箱 Worker（自建，填 API 地址 + 域名）/ Hotmail 四段凭证（XOAUTH2 IMAP 收码）/ CloudMail / testmail 等
- **SSO 导出**：注册成功自动写账本 `email----password----sso`，可推 grok2api Web 池（可选）
- **CPA 铸造（协议优先）**：有 SSO 时先走**纯 HTTP Device Flow**（约 6–9s/号），失败回退**有头浏览器 consent**（约 45–90s/号），产出 `cpa_auths/xai-<邮箱>.json`
- **运维脚本**：存量号批量补 CPA、SSO 存活扫描、CPA token 全量验证（refresh grant 轮换）
- **一键环境**：`setup.ps1` / `setup.sh`（自动装 uv + Python 3.13 + 依赖、检查 Chrome、生成预填配置）

**产物：**

| 产物 | 用途 | 位置 |
|------|------|------|
| **SSO** | grok.com / grok2api Web 池 | 账本第三段 + 可选推远端池 |
| **CPA（OIDC）xAI** | 免费 Grok Build（`cli-chat-proxy.grok.com`） | `cpa_auths/xai-<邮箱>.json` |

> **关键概念：SSO ≠ OIDC。**  
> 免费 Grok Build **不能**用账本里的 SSO JWT 直接打 API；必须再走 `accounts.x.ai` device-auth 铸 OIDC，写成 CPA 的 `type=xai` 认证文件。本项目的协议路径正是用 SSO cookie **自动完成**这一步（优先纯 HTTP，无需再弹浏览器）。

---

## 快速开始（5 分钟跑起来）

> 只想跑注册机？照下面 4 步走即可。

### 第 0 步：机器准备（对照检查）

| 项 | 要求 |
|----|------|
| 系统 | Windows 10/11 或带图形桌面的 macOS / Linux |
| Chrome | 本机装 Chrome（注册页靠它打开；[下载](https://www.google.com/chrome/)） |
| 代理 | xAI 官网一般需要代理：需要本机能用的代理（Clash/V2Ray 等）并记下端口 |
| Python | **不用自己装**，脚本会通过 uv 自动拉 Python 3.13 |

### 第 1 步：一键装依赖

```bash
# Windows：在项目根目录打开 PowerShell
powershell -ExecutionPolicy Bypass -File setup.ps1

# macOS / Linux
bash setup.sh
```

脚本依次做：安装/检查 uv → `uv sync`（自动下载 Python 3.13）→ 检查 Chrome → 从预设生成 `config.json` → 打印后续步骤。

不想用脚本就手动跑：

```bash
# ① 装 uv（已有则跳过）
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"   # Windows
curl -LsSf https://astral.sh/uv/install.sh | sh              # macOS / Linux

# ② 装依赖
uv sync

# ③ 生成配置
cp config.cloudflare.json config.json
```

### 第 2 步：填代理端口 + 邮箱服务

打开 `config.json`，把 `proxy` 改成你本机的代理端口：

```json
"proxy": "http://127.0.0.1:7890"
```

邮箱服务二选一：

- **cloudflare（临时邮箱 Worker）**：填你自己的 Worker 地址与域名 —— `cloudflare_api_base`（Worker 的 API 根 URL）+ `defaultDomains`（Worker 绑定的邮箱域名）；接口约定见下文「邮箱：Cloudflare 临时邮箱 Worker（自建）」
- **其他 provider（没有 Worker 时推荐）**：`"email_provider": "hotmail"` + `mail_credentials.txt` 四段凭证，或 `cloudmail` 等，字段见 `config.example.json`

CPA 参数预设里已填好，其余字段不用动；CPA 铸造想走另一个代理就填 `cpa_proxy`（留空 = 跟 `proxy` 相同）。

### 第 3 步：冒烟测试

```bash
uv run python -u register_cli.py --extra 1 --threads 1
```

日志里看到 `protocol token ok` / `mint protocol SUCCESS` 即整条链路正常（全程约 30–60s）。

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

## 使用

### A. 新注册 N 个号（含 SSO + CPA 导出）

```bash
uv run python -u register_cli.py --extra 1 --threads 1    # 再注册 1 个（推荐先跑这个）
uv run python -u register_cli.py --extra 5 --threads 2    # 再注册 5 个
```

成功时：① 追加账本 → ② 可选推 grok2api → ③ 协议 mint（失败回退浏览器）写 `cpa_auths/xai-<邮箱>.json` → ④ 可选复制到 CPA 热加载目录（`cpa_copy_to_hotload=true`）。

### B. 存量号补 CPA（只 mint，不重新注册）

账本需含 SSO（第三段）。协议优先，有 SSO 时通常**无需**弹浏览器：

```bash
uv run python -u scripts/backfill_cpa_xai_from_accounts.py \
  --accounts accounts_cli.txt --limit 1 --probe --timeout 300

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
| `--probe` | 检查是否列出最新 `grok-4.x` 免费模型 |
| `--headless` | 回退浏览器时无头（不推荐） |

多账本全量补跑 / SSO 存活扫描：

```bash
uv run python -u scripts/backfill_all_ledgers.py --target 0 --workers 5   # 按目标数补跑全部账本
uv run python -u scripts/sweep_sso_alive.py --workers 8                   # 扫描账本里哪些 SSO 还活着
uv run python -u scripts/resweep_errors.py                                # 重试扫描中 error 的行
```

### C. CPA token 全量验证（refresh grant）

```bash
uv run python -u scripts/verify_cpa_tokens.py --dir cpa_auths --workers 10 --proxy http://127.0.0.1:7890
```

对每个文件发 `grant_type=refresh_token` 换 token：200 即有效，并**原地轮换重写** token（验证后旧 token 作废，重新分发要再拷一遍）。

### D. 从 `~/.grok/auth.json` 导出 CPA

```bash
uv run python scripts/export_cpa_xai_from_grok_auth.py --out-dir ./cpa_auths
```

### E. 导入 CPA 热加载 + 调用验证（免费 Grok）

```bash
# 导入（示例 Linux；Windows 直接拷文件进 auth-dir 即可）
cp -a ./cpa_auths/xai-USER@domain.json "$CPA_AUTH_DIR"/
chmod 600 "$CPA_AUTH_DIR"/xai-USER@domain.json

# 验证（CPA 网关 :8317）
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

### CLI 参数速查（`register_cli.py`）

| 参数 | 含义 |
|------|------|
| `--extra N` | **再新注册 N 个**（推荐） |
| `--count N` | 账号**总数目标**（含已有）；已达标则退出 |
| `--threads N` | 并发 1–10 |
| `--mint-workers N` | CPA 协议 mint 并发 |
| `--accounts-file` | 账本路径 |

### 邮箱：Hotmail 四段凭证（可选）

`config.json` 设 `"email_provider": "hotmail"`，凭证文件 `mail_credentials.txt`（可从 `mail_credentials.example.txt` 复制）：

```text
邮箱----密码----ClientID----Token
```

| 段 | 含义 |
|----|------|
| 邮箱 | Hotmail / Outlook 主邮箱 |
| 密码 | 邮箱登录密码（注册机侧保留；IMAP 走 OAuth） |
| ClientID | 微软应用（Azure AD 应用）Client ID |
| Token | Microsoft OAuth2 **refresh_token**（XOAUTH2 IMAP 用） |

运行时行为：默认先用原邮箱，后续用随机 plus alias（如 `name+k8s2p9qa@domain`）；经 `outlook.office365.com`（可回退 `imap-mail.outlook.com`）XOAUTH2 IMAP 拉验证码；refresh_token 轮换会**自动回写**文件；成功/失败/占用中的 alias 参与去重与 `hotmail_max_aliases_per_account` 计数。

### 邮箱：Cloudflare 临时邮箱 Worker（自建）

`"email_provider": "cloudflare"` 时，注册机按 `cloudflare_api_base` + `cloudflare_path_*` 调你的 Worker。本仓库代码已适配 cloudflare_temp_email v1.8.x 约定：

| 用途 | 方法 + 路径 | 说明 |
|------|-------------|------|
| 建地址 | `POST /api/new_address` | body `{"domain":"your-mail-domain.com"}` → `{address, jwt, ...}` |
| 收信 | `GET /api/mails` | 头 `Authorization: Bearer <建地址返回的 jwt>` |
| 域名 / 令牌（备用） | `GET /api/domains`、`GET /api/token` | 旧版接口，代码按 `cloudflare_path_*` 可配 |

四个路径可用 `cloudflare_path_domains / cloudflare_path_accounts / cloudflare_path_token / cloudflare_path_messages` 覆盖（预设默认 `/api/domains, /api/new_address, /api/token, /api/mails`），鉴权方式见 `cloudflare_auth_mode`（预设 `none`，即 Worker 无 key）。没有自己的 Worker 就改用 `hotmail` / `cloudmail` 等 provider。

---

## 配置

### 文件

| 文件 | 说明 |
|------|------|
| `config.json` | 本地实配（setup 脚本从预设生成；**含本机信息，勿提交/勿分享**） |
| `config.cloudflare.json` | 临时邮箱 Worker 预设（填你自己的 Worker 地址与域名） |
| `config.example.json` | 全字段模板，每个字段带 `"// 注释"` 键详解（加载时自动忽略） |

### 代理优先级

| 字段 | 作用 |
|------|------|
| `proxy` | **注册** Chromium + 邮箱等 HTTP |
| `cpa_proxy` | **CPA 铸造**（协议 HTTP + 回退浏览器 + probe） |

```
cpa_proxy  >  proxy  >  环境变量 https_proxy/http_proxy
```

### 关键字段

| 字段 | 默认 | 含义 |
|------|------|------|
| `email_provider` | — | `cloudflare`（临时邮箱 Worker，预设默认）/ `hotmail` / `cloudmail` / `duckmail` / `yyds` |
| `defaultDomains` | — | 注册用邮箱域名（逗号分隔） |
| `cpa_export_enabled` | `true` | 注册成功后是否 mint CPA |
| `cpa_prefer_protocol` | `true` | 有 SSO 时先走纯 HTTP Device Flow |
| `cpa_protocol_only` | `false` | `true`=协议失败也不回退浏览器（调试用） |
| `cpa_mint_required` | `false` | `false`=mint 失败不丢号（留账本，可事后 backfill） |
| `cpa_auth_dir` | `./cpa_auths` | 主导出目录 |
| `cpa_copy_to_hotload` | `false` | 成功后复制到 CPA 热加载目录 |
| `cpa_hotload_dir` | — | CPA 的 `auth-dir`（copy 时需要） |
| `cpa_base_url` | `https://cli-chat-proxy.grok.com/v1` | 免费 Build 上游，**不要改** |
| `cpa_headless` | `false` | 回退浏览器时是否无头（**建议 false**） |
| `cpa_force_standalone` | `true` | 回退时独立 Chromium，不复用注册 tab |
| `cpa_mint_cookie_inject` | `true` | 回退时注入注册 cookie，尽量跳过二次登录 |
| `cpa_mint_workers` | `-1` | 协议 mint 并发（-1=跟随注册线程） |
| `grok2api_auto_add_local` | `false` | 注册成功自动推本机 grok2api `:8000` |

完整字段（含各超时参数）见 `config.example.json` 内注释。

### 落盘约定

| 路径 | 是否必须 | 说明 |
|------|----------|------|
| `accounts_cli.txt` / `accounts_*.txt` | 是 | 主账本 `email----password----sso` |
| `cpa_auths/xai-*.json` | 开 export 时 | CPA 格式 OIDC 归档 |
| `mail_credentials.txt` | hotmail 模式必须 | `邮箱----密码----ClientID----Token` |
| `emails_used.txt` / `emails_error.txt` | 自动 | 邮箱去重 / 错误记录 |

---

## 链路原理

```
[邮箱：Cloudflare Worker / Hotmail / CloudMail …]
        ↓  注册 accounts.x.ai（本机 Chrome + turnstilePatch）
 accounts_cli.txt                          email----password----sso
        ↓  可选：推 grok2api Web 池（SSO）
 CPA 铸造（cpa_prefer_protocol=true）
   ├─ 协议：curl_cffi + sso cookie → device/code → verify → approve → token 轮询（6-9s/号）
   └─ 回退：有头 Chromium + turnstilePatch，同一套 device-auth 页面点「允许」（45-90s/号）
        ↓
 cpa_auths/xai-<邮箱>.json                 【注册机主导出，mint_method 字段标明走了哪条路径】
        ↓  (cpa_copy_to_hotload=true 时)
 CPA auth-dir 热加载（可选）
        ↓
 CLIProxyAPI :8317                          model=grok-4.6（当前免费档）
```

协议成功日志：

```text
[cpa] mint try protocol (SSO HTTP device flow)
[cpa] protocol token ok ...
[cpa] mint protocol SUCCESS
[cpa] mint_method=protocol
```

协议失败时自动回退：

```text
[cpa] mint protocol failed: ...
[cpa] mint fallback → browser
[cpa] mint_method=browser
```

---

## 故障排查

| 现象 | 原因 / 处理 |
|------|-------------|
| 协议 `sso invalid` | SSO 过期或无效；自动回退浏览器；检查账本第三段 |
| 协议 verify/approve 失败 | 会话态变化 / 风控；看日志后自动回退浏览器 |
| 一直 `authorization_pending` | 浏览器路径未完成 consent；需到「设备已授权」且 token 200 |
| Cloudflare / Turnstile 拦截 | 回退浏览器时关 headless、开 turnstilePatch、检查代理 |
| Hotmail 收不到码 | 检查四段凭证、ClientID/Token、IMAP 主机与 alias 计数 |
| 有 token 但无 grok-4.x 免费模型 | `cpa_base_url` 是否为 `cli-chat-proxy` |
| 注册成功但无 `cpa_auths` | `cpa_export_enabled`？看日志与 `cpa_auth_failed.txt` |
| 代理 TLS 抖动（`UNEXPECTED_EOF` / `curl 35`） | 并发下偶发，重试/回退可吸收；降低 `--threads` 或换代理节点 |
| SSO 扫到「活」但 mint 报 `User is blocked` | xAI 侧封号，cookie 还在但账号被拦，解锁前不可恢复 |

调试原则：以 **token 端点返回 `access_token` + `refresh_token`** 为准；probe 看 `/v1/models` 是否含最新 `grok-4.x` 免费模型（当前 `grok-4.6`）。

---

## 目录结构

```
grok_reg-protocol_cpa/
  register_cli.py              # CLI 批量注册（主入口）
  grok_register_ttk.py         # 浏览器注册核心 + 邮箱/Hotmail 等 + GUI
  cpa_export.py                # 注册成功 hook（CPA 铸造入口）
  cpa_xai/
    protocol_mint.py           # SSO 纯 HTTP Device Flow（协议优先）
    mint.py                    # 协议 → 浏览器回退编排
    browser_confirm.py         # 浏览器 consent 路径
    oauth_device.py / schema.py / writer.py / probe.py ...
  scripts/
    backfill_cpa_xai_from_accounts.py   # 存量号补 CPA
    backfill_all_ledgers.py             # 多账本全量补跑（--target/--alive-file）
    sweep_sso_alive.py                  # SSO 存活扫描
    resweep_errors.py                   # 扫描错误重扫
    verify_cpa_tokens.py                # CPA token 全量验证（轮换）
    export_cpa_xai_from_grok_auth.py    # 从 ~/.grok/auth.json 导出
  config.example.json          # 全字段模板（带注释）
  config.cloudflare.json       # 临时邮箱 Worker 预设（setup 脚本用它生成 config.json）
  setup.ps1 / setup.sh         # 一键环境准备（Windows / macOS / Linux）
  turnstilePatch/              # CF Turnstile 浏览器扩展补丁
  mail_credentials.example.txt # Hotmail 四段凭证模板
  pyproject.toml / uv.lock / mise.toml
  # 运行时产物（.gitignore 已排除）：
  # config.json · accounts_*.txt · cpa_auths/ · emails_*.txt · screenshots/
```

---

## 安全

- `config.json`、`mail_credentials.txt`、账本、`cpa_auths/*.json` 含密码与 refresh_token，**权限 600 / 勿提交 git / 勿塞进分享包**（`.gitignore` 已排除，分发前自查）
- 免费 Build 有额度与风控；批量 mint 请控速（`--sleep` / 降低 `--threads`）
- `verify_cpa_tokens.py` 会轮换 token：验证后旧文件里的 token 作废，重新分发以 `cpa_auths/` 最新内容为准
