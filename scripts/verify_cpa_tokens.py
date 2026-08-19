#!/usr/bin/env python3
"""Verify CPA xai-*.json files by refreshing their tokens.

For each credential file, POST grant_type=refresh_token to the xAI token
endpoint. On success the file is updated in place (new access_token,
rotated refresh_token, id_token, expires_in, expired/last_refresh) so the
files are guaranteed importable into CLIProxyAPI hot-load.

Usage (from grok_reg project root):
  uv run python -u scripts/verify_cpa_tokens.py --dir ./cpa_auths
  uv run python -u scripts/verify_cpa_tokens.py --dir ./cpa_auths --workers 8
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from cpa_xai.oauth_device import CLIENT_ID, TOKEN_URL, _post_form  # noqa: E402


def _utc_iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def verify_one(path: Path, proxy: str | None) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    refresh = str(data.get("refresh_token") or "").strip()
    if not refresh:
        return {"email": data.get("email") or path.stem, "ok": False, "error": "no refresh_token"}
    try:
        status, body = _post_form(
            TOKEN_URL,
            {
                "grant_type": "refresh_token",
                "client_id": CLIENT_ID,
                "refresh_token": refresh,
            },
            timeout=30.0,
            proxy=proxy,
            retries=2,
            retry_sleep=1.0,
        )
    except BaseException as e:  # noqa: BLE001
        return {"email": data.get("email") or path.stem, "ok": False, "error": f"net: {e}"}
    if status == 200 and isinstance(body, dict) and body.get("access_token"):
        now = time.time()
        expires_in = int(body.get("expires_in") or 21600)
        data["access_token"] = str(body["access_token"]).strip()
        new_refresh = str(body.get("refresh_token") or "").strip()
        if new_refresh:
            data["refresh_token"] = new_refresh
        if body.get("id_token"):
            data["id_token"] = str(body["id_token"]).strip()
        data["expires_in"] = expires_in
        data["token_type"] = str(body.get("token_type") or "Bearer")
        data["expired"] = _utc_iso(now + expires_in)
        data["last_refresh"] = _utc_iso(now)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, path)
        return {"email": data.get("email") or path.stem, "ok": True}
    err = ""
    desc = ""
    if isinstance(body, dict):
        err = str(body.get("error") or "")
        desc = str(body.get("error_description") or "")
    return {
        "email": data.get("email") or path.stem,
        "ok": False,
        "error": f"HTTP {status} {err} {desc}".strip()[:300],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dir", default=str(_ROOT / "cpa_auths"))
    ap.add_argument("--proxy", default="")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--config", default=str(_ROOT / "config.json"))
    args = ap.parse_args()

    if not args.proxy:
        try:
            cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
            args.proxy = (cfg.get("cpa_proxy") or cfg.get("proxy") or "").strip()
        except Exception:
            args.proxy = os.environ.get("https_proxy") or os.environ.get("http_proxy") or ""

    d = Path(args.dir)
    files = sorted(d.glob("xai-*.json"))
    print(f"dir={d} files={len(files)} proxy={args.proxy or '(none)'} workers={args.workers}", flush=True)
    if not files:
        print("no credential files found")
        return 1

    ok_n = fail_n = 0
    t0 = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
        futs = {ex.submit(verify_one, f, args.proxy or None): f for f in files}
        for fut in concurrent.futures.as_completed(futs):
            r = fut.result()
            if r["ok"]:
                ok_n += 1
                print(f"OK   {r['email']}", flush=True)
            else:
                fail_n += 1
                print(f"FAIL {r['email']}  {r.get('error','')}", flush=True)
    dt = time.time() - t0
    print(f"\n=== verify done ok={ok_n} fail={fail_n} files={len(files)} in {dt:.0f}s ===", flush=True)
    return 0 if fail_n == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
