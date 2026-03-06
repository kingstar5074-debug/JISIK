from __future__ import annotations

"""
Simple Streamlit dashboard shell for US Penny Stock Scanner MVP.

- ???? import ???? ?
- ??? ??? ?? ?? ??? ?? ???? ?
- ?? ??:
  - Final Strategy
  - Market Regime
  - Strategy Ranking
  - Outcome Performance
  - Theme Heatmap
  - Pipeline Status
"""

import json
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent
REPORTS = PROJECT_ROOT / "reports"


def _load_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _load_csv(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    try:
        return pd.read_csv(path, encoding="utf-8")
    except Exception:
        return None


def _latest_heatmap() -> Path | None:
    directory = REPORTS / "heatmaps"
    if not directory.exists() or not directory.is_dir():
        return None
    pngs = sorted(directory.glob("*.png"), key=lambda p: p.stat().st_mtime, reverse=True)
    return pngs[0] if pngs else None


def main() -> None:
    st.set_page_config(page_title="US Penny Stock Research Dashboard", layout="wide")

    st.title("US Penny Stock Research Dashboard")

    # Final strategy panel
    st.header("Final Strategy")
    fs = _load_json(REPORTS / "final_strategy" / "final_strategy.json")
    if fs:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Final Strategy", fs.get("final_strategy", "?"))
        c2.metric("Market Regime", fs.get("market_regime", "?"))
        c3.metric("Fusion Confidence", fs.get("fusion_confidence", "?"))
        c4.metric("Selector Recommendation", fs.get("selector_recommendation", "?"))
        if fs.get("reason"):
            st.info(fs["reason"])
    else:
        st.info("No data available yet.")

    st.divider()

    # Market regime panel
    st.header("Market Regime")
    mr = _load_json(REPORTS / "market_regime" / "market_regime.json")
    if mr:
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Regime", mr.get("regime", "?"))
        c2.metric("Average Return", mr.get("average_return", "?"))
        c3.metric("Median Return", mr.get("median_return", "?"))
        c4.metric("Volatility", mr.get("volatility", "?"))
        c5.metric("Positive Rate", mr.get("positive_rate", "?"))
    else:
        st.info("No data available yet.")

    st.divider()

    # Strategy ranking panel
    st.header("Strategy Ranking")
    sr = _load_json(REPORTS / "strategy_recommendation" / "recommended_strategy.json")
    if sr and isinstance(sr.get("ranking"), list) and sr["ranking"]:
        df_rank = pd.DataFrame(
            [{"Strategy": r.get("strategy", ""), "Score": r.get("score", "")} for r in sr["ranking"]]
        )
        st.dataframe(df_rank, use_container_width=True, hide_index=True)
    else:
        st.info("No data available yet.")

    st.divider()

    # Outcome performance panel
    st.header("Outcome Performance")
    ocsv = _load_csv(REPORTS / "outcome_analysis" / "outcome_summary_strategy.csv")
    if ocsv is not None and not ocsv.empty:
        st.dataframe(ocsv, use_container_width=True, hide_index=True)
    else:
        st.info("No data available yet.")

    st.divider()

    # Theme heatmap panel
    st.header("Theme Heatmap")
    hp = _latest_heatmap()
    if hp:
        st.image(str(hp), use_container_width=True)
    else:
        st.info("No data available yet.")

    st.divider()

    # Pipeline status panel (??? ?? ?? ??? ??)
    st.header("Pipeline Status")
    fs_ok = (REPORTS / "final_strategy" / "final_strategy.json").exists()
    mr_ok = (REPORTS / "market_regime" / "market_regime.json").exists()
    sr_ok = (REPORTS / "strategy_recommendation" / "recommended_strategy.json").exists()
    oc_ok = (REPORTS / "outcome_analysis" / "outcome_summary_strategy.csv").exists()
    tr_ok = (REPORTS / "trade_outcomes" / "trade_results.csv").exists()

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.success("Final Strategy") if fs_ok else c1.warning("Final Strategy missing")
    c2.success("Market Regime") if mr_ok else c2.warning("Market Regime missing")
    c3.success("Strategy Rec") if sr_ok else c3.warning("Strategy Rec missing")
    c4.success("Outcome CSV") if oc_ok else c4.warning("Outcome CSV missing")
    c5.success("Trade Results") if tr_ok else c5.warning("Trade Results missing")


if __name__ == "__main__":
    main()

