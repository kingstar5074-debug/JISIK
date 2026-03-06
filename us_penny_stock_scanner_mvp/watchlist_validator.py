from __future__ import annotations

"""
Watchlist Validator.

tickers.txt 기반 watchlist 심볼들을 실제 provider(yahoo 등)로 검증하여
유효/무효 티커를 나누고, 옵션에 따라 watchlist 를 정리(clean)하는 도구입니다.

기능:
- universe/watchlist_universe.py 를 사용해 티커 로드
- scanner.providers.factory.get_market_data_provider 로 provider 생성
- 각 심볼에 대해 fetch_quotes 호출 후 price 존재 여부 확인
- 결과를 콘솔 요약 및 JSON 파일로 저장
- --clean 옵션 시 유효하지 않은 심볼을 tickers.txt 에서 제거 (백업 파일 생성)
"""

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd

from scanner.providers.factory import get_market_data_provider
from universe.watchlist_universe import WatchlistUniverseProvider


PROJECT_ROOT = Path(__file__).resolve().parent
TICKERS_FILE = PROJECT_ROOT / "tickers.txt"
REPORTS_DIR = PROJECT_ROOT / "reports"


def _load_watchlist() -> List[str]:
    provider = WatchlistUniverseProvider(TICKERS_FILE)
    try:
        return provider.load_symbols()
    except FileNotFoundError:
        print(f"watchlist file not found: {TICKERS_FILE}")
        return []


class _ProviderConfig:
    def __init__(self, name: str) -> None:
        self.data_provider = name
        # research_pipeline / main 과 동일 필드 이름만 최소한 제공
        self.polygon_api_key = ""  # polygon 사용 시 .env 로 설정돼 있어야 함
        self.per_symbol_delay_seconds = 0.2


def _build_provider(name: str):
    cfg = _ProviderConfig(name)
    return get_market_data_provider(cfg)


def _validate_symbols(
    symbols: List[str],
    provider_name: str,
    verbose: bool,
) -> Tuple[List[str], List[str]]:
    try:
        provider = _build_provider(provider_name)
    except Exception as e:
        print(f"provider init failed ({provider_name}): {e}")
        return [], symbols[:]  # 전부 invalid 로 간주

    valid: List[str] = []
    invalid: List[str] = []

    for sym in symbols:
        s = sym.strip().upper()
        if not s:
            continue
        ok = False
        try:
            quotes = provider.fetch_quotes([s], market_session="regular")  # type: ignore[arg-type]
            q = quotes.get(s)
            if q is not None and q.current_price is not None:
                ok = True
        except Exception as e:
            if verbose:
                print(f"  provider error for {s}: {e}")
            ok = False

        if ok:
            valid.append(s)
            if verbose:
                print(f"  {s}: VALID")
        else:
            invalid.append(s)
            if verbose:
                print(f"  {s}: INVALID")

    return valid, invalid


def _save_json_report(
    total: int,
    valid: List[str],
    invalid: List[str],
) -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / "watchlist_validation.json"
    payload: Dict[str, object] = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "total": total,
        "valid": len(valid),
        "invalid": len(invalid),
        "invalid_symbols": invalid,
    }
    try:
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"JSON report saved to {path}")
    except Exception as e:
        print(f"Failed to save JSON report: {e}")


def _clean_watchlist(valid_symbols: List[str]) -> None:
    if not TICKERS_FILE.exists():
        print(f"tickers file not found, skip cleaning: {TICKERS_FILE}")
        return

    ts = datetime.now().strftime("%Y%m%d")
    backup_name = f"watchlist_backup_{ts}.txt"
    backup_path = PROJECT_ROOT / backup_name
    try:
        backup_path.write_text(TICKERS_FILE.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"Backup created: {backup_path}")
    except Exception as e:
        print(f"Failed to create backup, aborting clean: {e}")
        return

    try:
        # 한 줄당 하나씩, 빈 줄 없이 깔끔하게 작성
        content = "\n".join(sorted(set(valid_symbols))) + "\n" if valid_symbols else ""
        TICKERS_FILE.write_text(content, encoding="utf-8")
        print(f"Cleaned watchlist written to {TICKERS_FILE}")
    except Exception as e:
        print(f"Failed to write cleaned watchlist: {e}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate watchlist tickers using market data provider.")
    parser.add_argument(
        "--provider",
        type=str,
        default="yahoo",
        help="data provider name (default: yahoo)",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="remove invalid tickers from watchlist (creates backup first)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="save JSON report to reports/watchlist_validation.json",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="print per-symbol validation result",
    )
    args = parser.parse_args()

    symbols = _load_watchlist()
    if not symbols:
        print("Watchlist is empty or file missing.")
        return 0

    print(f"Validating {len(symbols)} symbol(s) with provider={args.provider}...")
    valid, invalid = _validate_symbols(symbols, args.provider, args.verbose)

    print("")
    print(f"VALID: {len(valid)}")
    print(f"INVALID: {len(invalid)}")

    if invalid:
        print("")
        print("Invalid tickers:")
        for s in invalid:
            print(s)

    if args.json:
        _save_json_report(len(symbols), valid, invalid)

    if args.clean and invalid:
        _clean_watchlist(valid)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

