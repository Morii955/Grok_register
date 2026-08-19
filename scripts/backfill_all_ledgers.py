#!/usr/bin/env python3
"""Backfill CPA xai-*.json from ALL ledger files, newest ledger first.

Walks every accounts_*.txt in the project root in descending mtime order,
skips emails that already have a CPA file in the out-dir, and mints the
rest (protocol-first, browser fallback) until --target files exist.

Usage (from grok_reg project root):
  uv run python -u scripts/backfill_all_ledgers.py --target 202 --probe
"""

from __future__ import annotations

import argparse
import concurrent.futures
import glob
import json
import os
import sys
import threading
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from cpa_xai import existing_cpa_emails, mint_and_export, parse_accounts_file  # noqa: E402


def count_cpa(out_dir: Path) -> int:
    return len(list(out_dir.glob("xai-*.json")))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--target", type=int, default=200, help="Stop when out-dir has this many xai-*.json")
    ap.add_argument("--out-dir", default=str(_ROOT / "cpa_auths"))
    ap.add_argument("--timeout", type=float, default=180.0)
    ap.add_argument("--sleep", type=float, default=1.0)
    ap.add_argument("--probe", action="store_true", default=True)
    ap.add_argument("--no-probe", action="store_false", dest="probe")
    ap.add_argument("--proxy", default="")
    ap.add_argument("--config", default=str(_ROOT / "config.json"))
    ap.add_argument(
        "--fail-log",
        default=str(_ROOT / "cpa_auths" / "backfill_all_failed.jsonl"),
    )
    ap.add_argument(
        "--alive-file",
        default="",
        help="JSONL of {email, alive}; when set, only mint emails with alive=true",
    )
    ap.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Concurrent mints; each worker thread has its own browser (threading.local)",
    )
    args = ap.parse_args()

    if not args.proxy:
        try:
            cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
            args.proxy = (cfg.get("cpa_proxy") or cfg.get("proxy") or "").strip()
        except Exception:
            args.proxy = os.environ.get("https_proxy") or os.environ.get("http_proxy") or ""
    print(f"proxy={args.proxy or '(none)'} target={args.target} out={args.out_dir}", flush=True)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    alive_set: set[str] | None = None
    if args.alive_file:
        alive_set = set()
        for line in Path(args.alive_file).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            if row.get("alive") is True:
                alive_set.add(str(row.get("email", "")).lower())
        print(f"alive filter: {len(alive_set)} emails from {args.alive_file}", flush=True)

    ledgers = sorted(
        glob.glob(str(_ROOT / "accounts_*.txt")),
        key=lambda p: Path(p).stat().st_mtime,
        reverse=True,
    )
    print(f"ledgers={len(ledgers)} (newest first)", flush=True)

    have = {e.lower() for e in existing_cpa_emails(out_dir)}
    have_lock = threading.Lock()
    ok_n = fail_n = 0
    t0 = time.time()

    def mint_one(acc) -> dict:
        nonlocal ok_n, fail_n

        def log(msg: str, _email=acc.email) -> None:
            line = f"[{time.strftime('%H:%M:%S')}] [{_email}] {msg}"
            try:
                print(line, flush=True)
            except UnicodeEncodeError:
                # Windows GBK console: never let a log line kill the mint
                enc = sys.stdout.encoding or "utf-8"
                print(line.encode(enc, "replace").decode(enc, "replace"), flush=True)

        r = mint_and_export(
            email=acc.email,
            password=acc.password,
            auth_dir=args.out_dir,
            page=None,
            proxy=args.proxy or None,
            headless=False,
            probe=args.probe,
            probe_chat=False,
            browser_timeout_sec=args.timeout,
            force_standalone=True,
            sso=acc.sso or None,
            prefer_protocol=True,
            log=log,
        )
        with have_lock:
            if r.get("ok") and r.get("path"):
                ok_n += 1
                have.add(acc.email.lower())
            else:
                fail_n += 1
                if args.fail_log:
                    Path(args.fail_log).parent.mkdir(parents=True, exist_ok=True)
                    with open(args.fail_log, "a", encoding="utf-8") as f:
                        f.write(json.dumps(r, ensure_ascii=False) + "\n")
        return r
    for ledger in ledgers:
        n_have = count_cpa(out_dir)
        if n_have >= args.target:
            print(f"\n[target reached] {n_have} >= {args.target} — stop before {ledger}", flush=True)
            break
        accounts = parse_accounts_file(ledger)
        todo = [a for a in accounts if a.email.lower() not in have]
        if alive_set is not None:
            before = len(todo)
            todo = [a for a in todo if a.email.lower() in alive_set]
            if before != len(todo):
                print(f"    alive filter dropped {before - len(todo)} non-alive accounts", flush=True)
        if not todo:
            print(f"\n--- {Path(ledger).name}: total={len(accounts)} todo=0 (have={n_have}) ---", flush=True)
            continue
        print(
            f"\n--- {Path(ledger).name}: total={len(accounts)} todo={len(todo)} (have={n_have}) workers={args.workers} ---",
            flush=True,
        )
        with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
            futs: dict = {}
            for i, acc in enumerate(todo, 1):
                if count_cpa(out_dir) >= args.target:
                    print(f"[target reached] {count_cpa(out_dir)} >= {args.target} — stop submitting", flush=True)
                    break
                futs[ex.submit(mint_one, acc)] = acc
                if args.sleep and i < len(todo):
                    time.sleep(args.sleep)
            for fut in concurrent.futures.as_completed(futs):
                fut.result()

    n_final = count_cpa(out_dir)
    dt = time.time() - t0
    print(
        f"\n=== all-ledgers done ok={ok_n} fail={fail_n} in {dt/60:.1f} min — cpa files now {n_final} (target {args.target}) ===",
        flush=True,
    )
    return 0 if n_final >= args.target else 1


if __name__ == "__main__":
    raise SystemExit(main())
