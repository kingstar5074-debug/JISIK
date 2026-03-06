from __future__ import annotations

"""
Research Dashboard.

파이프라인 결과(최종 전략, regime, 성능, heatmap 등)를 한 화면에 보여주는
Streamlit 기반 대시보드입니다.

실행: streamlit run dashboard.py
"""

import json
import time
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

# Project root (parent of this file)
PROJECT_ROOT = Path(__file__).resolve().parent
REPORTS = PROJECT_ROOT / "reports"


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists() or not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _load_csv(path: Path) -> pd.DataFrame | None:
    if not path.exists() or not path.is_file():
        return None
    try:
        return pd.read_csv(path, encoding="utf-8")
    except Exception:
        return None


def _latest_heatmap_path() -> Path | None:
    heatmap_dir = REPORTS / "heatmaps"
    if not heatmap_dir.exists() or not heatmap_dir.is_dir():
        return None
    pngs = sorted(heatmap_dir.glob("*.png"), key=lambda p: p.stat().st_mtime, reverse=True)
    return pngs[0] if pngs else None


def _outcome_summary_strategy_csv() -> Path:
    return REPORTS / "outcome_analysis" / "outcome_summary_strategy.csv"


def main() -> None:
    st.set_page_config(page_title="US Penny Stock Research Dashboard", layout="wide")

    # --- Header ---
    st.title("US Penny Stock Research Dashboard")
    st.caption(f"Current time: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}")

    # --- Final Strategy Panel ---
    st.header("Final Strategy")
    final_path = REPORTS / "final_strategy" / "final_strategy.json"
    final_data = _load_json(final_path)
    if final_data:
        with st.container():
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Final Strategy", final_data.get("final_strategy", "—"))
            with col2:
                st.metric("Market Regime", final_data.get("market_regime", "—"))
            with col3:
                conf = final_data.get("fusion_confidence")
                st.metric("Fusion Confidence", f"{conf:.2f}" if isinstance(conf, (int, float)) else "—")
            with col4:
                st.metric("Selector Recommendation", final_data.get("selector_recommendation", "—"))
            reason = final_data.get("reason")
            if reason:
                st.info(reason)
    else:
        st.warning("No data available yet.")

    st.divider()

    # --- Market Regime Panel ---
    st.header("Market Regime")
    regime_path = REPORTS / "market_regime" / "market_regime.json"
    regime_data = _load_json(regime_path)
    if regime_data:
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Regime", regime_data.get("regime", "—"))
        c2.metric("Average Return", regime_data.get("average_return", "—"))
        c3.metric("Median Return", regime_data.get("median_return", "—"))
        c4.metric("Volatility", regime_data.get("volatility", "—"))
        c5.metric("Positive Rate", regime_data.get("positive_rate", "—"))
    else:
        st.warning("No data available yet.")

    st.divider()

    # --- Strategy Ranking Panel ---
    st.header("Strategy Ranking")
    rec_path = REPORTS / "strategy_recommendation" / "recommended_strategy.json"
    rec_data = _load_json(rec_path)
    if rec_data:
        ranking = rec_data.get("ranking")
        if isinstance(ranking, list) and ranking:
            df = pd.DataFrame([{"Strategy": r.get("strategy", ""), "Score": r.get("score", "")} for r in ranking])
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.warning("No ranking data.")
    else:
        st.warning("No data available yet.")

    st.divider()

    # --- Outcome Performance Panel ---
    st.header("Outcome Performance")
    csv_path = _outcome_summary_strategy_csv()
    df_outcome = _load_csv(csv_path)
    if df_outcome is not None and not df_outcome.empty:
        st.dataframe(df_outcome, use_container_width=True, hide_index=True)
        if "group" in df_outcome.columns and "average_return" in df_outcome.columns:
            try:
                import matplotlib.pyplot as plt
                fig, ax = plt.subplots()
                ax.bar(df_outcome["group"].astype(str), pd.to_numeric(df_outcome["average_return"], errors="coerce").fillna(0))
                ax.set_xlabel("Strategy")
                ax.set_ylabel("Average Return")
                ax.set_title("Outcome Performance by Strategy (average_return)")
                st.pyplot(fig)
                plt.close(fig)
            except Exception:
                pass
    else:
        st.warning("No data available yet.")

    st.divider()

    # --- Heatmap Panel ---
    st.header("Theme Heatmap")
    heatmap_path = _latest_heatmap_path()
    if heatmap_path:
        try:
            st.image(str(heatmap_path), use_container_width=True)
        except Exception:
            st.warning("Could not load heatmap image.")
    else:
        st.warning("No data available yet.")

    st.divider()

    # --- Pipeline Status Panel ---
    st.header("Pipeline Status")
    scan_ok = (REPORTS / "trade_outcomes" / "scan_snapshots.csv").exists()
    analysis_ok = (REPORTS / "outcome_analysis").exists() and any(
        (REPORTS / "outcome_analysis").glob("outcome_summary_*.json")
    )
    selector_ok = (REPORTS / "strategy_recommendation" / "recommended_strategy.json").exists()
    regime_ok = (REPORTS / "market_regime" / "market_regime.json").exists()

    s1, s2, s3, s4 = st.columns(4)
    s1.success("Scanner (snapshot)") if scan_ok else s1.warning("Scanner (snapshot)")
    s2.success("Outcome analysis") if analysis_ok else s2.warning("Outcome analysis")
    s3.success("Strategy recommendation") if selector_ok else s3.warning("Strategy recommendation")
    s4.success("Regime detection") if regime_ok else s4.warning("Regime detection")

    # --- Auto-refresh ---
    st.divider()
    refresh_placeholder = st.empty()
    refresh_placeholder.caption("Auto-refresh in 60 seconds...")
    time.sleep(60)
    try:
        st.rerun()
    except Exception:
        try:
            st.experimental_rerun()
        except Exception:
            pass


if __name__ == "__main__":
    main()
