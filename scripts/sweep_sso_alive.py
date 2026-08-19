#!/usr/bin/env python3
"""Sweep all ledger accounts for SSO cookie liveness (no browser, no mint).

For every ledger account that does not yet have a CPA file, performs the
same first-step check as protocol mint: GET https://accounts.x.ai/ with the
sso cookie (curl_cffi, Chrome impersonation). If the final URL is not a
sign-in/sign-up page the SSO session is still alive server-side and the
account can be fast-minted via protocol (no browser needed).

Usage (from grok_reg project root):
  uv run python -X utf8 -u scripts/sweep_sso_alive.py
  uv run python -X utf8 -u scripts/sweep_sso_alive.py --workers 12 --out alive_sweep.jsonl
"""

from __future__ import annotations

import argparse
import concurrent.futures
import glob
import json
import os
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from cpa_xai import existing_cpa_emails, parse_accounts_file  # noqa: E402
from cpa_xai.protocol_mint import _session, _set_sso_cookie  # noqa: E402
from cpa_xai.proxyutil import resolve_proxy  # noqa: E402


def check_sso(email: str, sso: str, proxy: str | None, timeout: float) -> dict:
    try:
        session = _session(proxy, lambda _m: None)
        _set_sso_cookie(session, sso)
        r = session.get(
            "https://accounts.x.ai/",
            impersonate="chrome",
            timeout=timeout,
            allow_redirects=True,
        )
        final = str(getattr(r, "url", "") or "")
        if "sign-in" in final or "sign-up" in final:
            return {"email": email, "alive": False, "url": final[:120]}
        return {"email": email, "alive": True, "url": final[:120]}
    except BaseException as e:  # noqa: BLE001
        return {"email": email, "alive": None, "error": str(e)[:200]}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--timeout", type=float, default=20.0)
    ap.add_argument("--proxy", default="")
    ap.add_argument("--config", default=str(_ROOT / "config.json"))
    ap.add_argument("--out", default=str(_ROOT / "alive_sweep.jsonl"))
    ap.add_argument("--limit", type=int, default=0, help="0 = all")
    args = ap.parse_args()

    if not args.proxy:
        try:
            cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
            args.proxy = (cfg.get("cpa_proxy") or cfg.get("proxy") or "").strip()
        except Exception:
            args.proxy = os.environ.get("https_proxy") or os.environ.get("http_proxy") or ""
    proxy = resolve_proxy(args.proxy) or None

    out_dir = _ROOT / "cpa_auths"
    have = {e.lower() for e in existing_cpa_emails(out_dir)}

    ledgers = sorted(
        glob.glob(str(_ROOT / "accounts_*.txt")),
        key=lambda p: Path(p).stat().st_mtime,
        reverse=True,  # newest first: first (newest) copy of a dup email wins
    )
    todo: dict[str, tuple[str, str]] = {}  # email -> (sso, ledger_date)
    for ledger in ledgers:
        date = Path(ledger).stem.replace("accounts_", "")[:8]
        for a in parse_accounts_file(ledger):
            key = a.email.lower()
            if key in have or key in todo:
                continue
            if not (a.sso or "").strip():
                continue
            todo[key] = (a.sso.strip(), date)
    if args.limit:
        todo = dict(list(todo.items())[: args.limit])

    print(
        f"proxy={args.proxy or '(none)'} candidates={len(todo)} (have CPA={len(have)}) workers={args.workers}",
        flush=True,
    )

    by_date: dict[str, Counter] = defaultdict(Counter)
    t0 = time.time()
    done = 0
    with open(args.out, "w", encoding="utf-8") as fout:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
            futs = {
                ex.submit(check_sso, email, sso, proxy, args.timeout): (email, date)
                for email, (sso, date) in todo.items()
            }
            for fut in concurrent.futures.as_completed(futs):
                r = fut.result()
                email, date = futs[fut]
                r["date"] = date
                fout.write(json.dumps(r, ensure_ascii=False) + "\n")
                if r["alive"] is True:
                    by_date[date]["alive"] += 1
                elif r["alive"] is False:
                    by_date[date]["dead"] += 1
                else:
                    by_date[date]["error"] += 1
                done += 1
                if done % 100 == 0 or done == len(todo):
                    el = time.time() - t0
                    print(f"  progress {done}/{len(todo)} ({el:.0f}s)", flush=True)

    print(f"\n=== SSO sweep by ledger date ({time.time() - t0:.0f}s total) ===", flush=True)
    tot_a = tot_d = tot_e = 0
    for date in sorted(by_date):
        c = by_date[date]
        n = sum(c.values())
        tot_a += c["alive"]
        tot_d += c["dead"]
        tot_e += c["error"]
        pct = 100.0 * c["alive"] / n if n else 0.0
        print(f"  {date}: alive={c['alive']:<4} dead={c['dead']:<4} error={c['error']:<3} ({pct:.1f}% alive of {n})", flush=True)
    print(f"  TOTAL: alive={tot_a} dead={tot_d} error={tot_e} of {len(todo)}", flush=True)
    print(f"details -> {args.out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
