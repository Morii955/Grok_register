#!/usr/bin/env python3
"""Re-sweep only the error rows (alive=null) of an alive_sweep.jsonl.

Looks up each errored email's SSO from the ledgers (newest-first, same
dedupe rule as sweep_sso_alive.py), re-checks liveness with one retry,
and rewrites alive_sweep.jsonl in place with the updated rows.

Usage (from project root):
  .venv\Scripts\python.exe -X utf8 -u scripts/resweep_errors.py
"""

from __future__ import annotations

import concurrent.futures
import glob
import json
import time
from collections import Counter
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
import sys  # noqa: E402

if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from cpa_xai import existing_cpa_emails, parse_accounts_file  # noqa: E402
from cpa_xai.protocol_mint import _session, _set_sso_cookie  # noqa: E402
from cpa_xai.proxyutil import resolve_proxy  # noqa: E402


def check_sso(email: str, sso: str, proxy: str | None, timeout: float, retries: int = 2) -> dict:
    last: dict = {}
    for attempt in range(1, retries + 1):
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
            last = {"email": email, "alive": None, "error": str(e)[:200]}
            if attempt < retries:
                time.sleep(1.5)
    return last


def main() -> int:
    out = _ROOT / "alive_sweep.jsonl"
    rows: list[dict] = []
    errors: dict[str, dict] = {}
    for line in out.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        rows.append(row)
        if row.get("alive") is None:
            errors[row["email"].lower()] = row

    print(f"error rows to resweep: {len(errors)}", flush=True)
    if not errors:
        print("nothing to do", flush=True)
        return 0

    # proxy
    try:
        cfg = json.loads((_ROOT / "config.json").read_text(encoding="utf-8"))
        proxy_raw = (cfg.get("cpa_proxy") or cfg.get("proxy") or "").strip()
    except Exception:
        proxy_raw = ""
    proxy = resolve_proxy(proxy_raw) or None
    print(f"proxy={proxy or '(none)'}", flush=True)

    # lookup SSO from ledgers, newest-first (first hit wins) — same rule as sweep
    ledgers = sorted(
        glob.glob(str(_ROOT / "accounts_*.txt")),
        key=lambda p: Path(p).stat().st_mtime,
        reverse=True,
    )
    sso_for: dict[str, str] = {}
    for ledger in ledgers:
        for a in parse_accounts_file(ledger):
            key = a.email.lower()
            if key in errors and key not in sso_for and (a.sso or "").strip():
                sso_for[key] = a.sso.strip()
    missing = [e for e in errors if e not in sso_for]
    if missing:
        print(f"warning: {len(missing)} error emails had no SSO in ledgers", flush=True)

    t0 = time.time()
    results: dict[str, dict] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        futs = {
            ex.submit(check_sso, email, sso, proxy, 20.0): email
            for email, sso in sso_for.items()
        }
        for fut in concurrent.futures.as_completed(futs):
            r = fut.result()
            results[r["email"].lower()] = r
    print(f"reswept {len(results)} in {time.time() - t0:.0f}s", flush=True)

    # merge in place: replace error rows with fresh results (keep date)
    fixed = 0
    for i, row in enumerate(rows):
        if row.get("alive") is None:
            fresh = results.get(row["email"].lower())
            if fresh is not None:
                fresh["date"] = row.get("date")
                rows[i] = fresh
                if fresh["alive"] is not None:
                    fixed += 1
    with open(out, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    c = Counter()
    for row in rows:
        if row.get("alive") is True:
            c["alive"] += 1
        elif row.get("alive") is False:
            c["dead"] += 1
        else:
            c["error"] += 1
    print(f"resolved {fixed} of {len(errors)} error rows", flush=True)
    print(f"FINAL: alive={c['alive']} dead={c['dead']} error={c['error']} of {len(rows)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
