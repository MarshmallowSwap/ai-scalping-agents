"""Dashboard game-style v2 per il sistema AI Scalping Agents."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import json
import re
from datetime import datetime, timezone

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
import ta

from dashboard.runtime import runtime, fetch_candles
from dashboard.theme import CUSTOM_CSS

st.set_page_config(
    page_title="AI SCALPING // COMMAND CENTER",
    page_icon="🎮",
    layout="wide",
    initial_sidebar_state="collapsed",
)
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# ============ HELPERS ============
def parse_portfolio(text: str) -> dict:
    out = {"mode": "-", "equity": 0.0, "available": 0.0, "margin": 0.0, "positions": []}
    if not text:
        return out
    m = re.search(r"Account mode:\s*([^\n]+)", text)
    if m:
        out["mode"] = m.group(1).strip()
    m = re.search(r"\$([\d,]+\.?\d*)\s+equity", text)
    if m:
        out["equity"] = float(m.group(1).replace(",", ""))
    m = re.search(r"\$([\d,]+\.?\d*)\s+available", text)
    if m:
        out["available"] = float(m.group(1).replace(",", ""))
    m = re.search(r"\$([\d,]+\.?\d*)\s+margin used", text)
    if m:
        out["margin"] = float(m.group(1).replace(",", ""))

    pos_pat = re.compile(
        r"-\s+(?P<symbol>\w+)\s+(?P<side>LONG|SHORT)\s+(?P<lev>\d+)x\s+\|"
        r"\s+Size:\s+\$(?P<size>[\d.]+)\s+\|"
        r"\s+Margin:\s+\$(?P<margin>[\d.]+)\s+\|"
        r"\s+Entry:\s+\$(?P<entry>[\d,]+)\s+\|"
        r"\s+PnL:\s+(?P<sign>[+-]?)\$(?P<pnl>[\d.]+)\s+\((?P<pct_sign>[+-]?)(?P<pct>[\d.]+)%\)"
        r"(?:\s+\|\s+TP/SL:\s+\$(?P<tp>[\d,]+)\s*/\s*\$(?P<sl>[\d,]+))?"
    )
    for line in text.splitlines():
        m = pos_pat.search(line)
        if m:
            pnl = float(m.group("pnl"))
            if m.group("sign") == "-":
                pnl = -pnl
            pct = float(m.group("pct"))
            if m.group("pct_sign") == "-":
                pct = -pct
            out["positions"].append({
                "symbol": m.group("symbol"),
                "side": m.group("side"),
                "leverage": int(m.group("lev")),
                "size": float(m.group("size")),
                "margin": float(m.group("margin")),
                "entry": float(m.group("entry").replace(",", "")),
                "pnl_usd": pnl,
                "pnl_pct": pct,
                "tp": float(m.group("tp").replace(",", "")) if m.group("tp") else None,
                "sl": float(m.group("sl").replace(",", "")) if m.group("sl") else None,
            })
    return out


def fetch_portfolio_text() -> str:
    try:
        client = runtime.ensure_client()
        return str(runtime.run_sync(client.get_portfolio(), timeout=15))
    except Exception as e:
        return f"ERRORE: {e}"


def load_journal() -> pd.DataFrame:
    p = Path("data/trades_journal.jsonl")
    if not p.exists():
        return pd.DataFrame()
    rows = []
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    return pd.DataFrame(rows)


def compute_equity_from_journal(df: pd.DataFrame) -> pd.DataFrame:
    """Costruisce equity curve dai trade eseguiti (event=executed)."""
    if df.empty or "event" not in df.columns:
        return pd.DataFrame()
    ex = df[df["event"] == "executed"].copy()
    if ex.empty:
        return pd.DataFrame()
    ex["timestamp"] = pd.to_datetime(ex["timestamp"])
    ex = ex.sort_values("timestamp")
    # Stima PnL dal result se possibile, altrimenti 0
    pnls = []
    for _, r in ex.iterrows():
        result = r.get("result")
        pnl = 0.0
        if isinstance(result, dict):
            order = result.get("order", {})
            try:
                pnl = float(order.get("pnl", 0.0) or 0.0)
            except Exception:
                pnl = 0.0
        pnls.append(pnl)
    ex["pnl_estimate"] = pnls
    ex["cum_pnl"] = ex["pnl_estimate"].cumsum()
    ex["equity"] = 10000.0 + ex["cum_pnl"]
    return ex[["timestamp", "equity", "pnl_estimate"]]


# ============ HEADER ============
portfolio_text = fetch_portfolio_text()
portfolio = parse_portfolio(portfolio_text)

h1, h2, h3, h4 = st.columns([3, 1, 1, 1])
with h1:
    st.markdown(
        '<div class="main-title">⚡ AI SCALPING // COMMAND CENTER</div>'
        '<div class="main-subtitle">Liquid Co-Invest MCP · Multi-Agent Trading System</div>',
        unsafe_allow_html=True,
    )
with h2:
    pnl_total = portfolio["equity"] - 10000.0
    cls = "pos" if pnl_total >= 0 else "neg"
    st.markdown(
        f'<div class="stat-card"><div class="stat-label">Equity</div>'
        f'<div class="stat-value ${cls}">${portfolio["equity"]:,.2f}</div></div>',
        unsafe_allow_html=True,
    )
with h3:
    cls = "pos" if pnl_total >= 0 else "neg"
    st.markdown(
        f'<div class="stat-card"><div class="stat-label">PnL</div>'
        f'<div class="stat-value {cls}">${pnl_total:+,.2f}</div></div>',
        unsafe_allow_html=True,
    )
with h4:
    mode_label = "PAPER" if "paper" in portfolio["mode"].lower() else "LIVE"
    mode_cls = "pos" if mode_label == "PAPER" else "neg"
    sched_status = "RUN" if runtime.scheduler_running else "OFF"
    st.markdown(
        f'<div class="stat-card"><div class="stat-label">Mode</div>'
        f'<div class="stat-value {mode_cls}">{mode_label}</div>'
        f'<div class="stat-label" style="margin-top:6px">Bot: {sched_status}</div></div>',
        unsafe_allow_html=True,
    )

st.markdown("---")

# ============ TABS ============
tabs = st.tabs(["🎯 POSITIONS", "📈 CHART", "🎮 CONTROL", "📊 PERFORMANCE", "📜 LOG"])
tab_pos, tab_chart, tab_ctrl, tab_perf, tab_log = tabs

# ---- POSITIONS ----
with tab_pos:
    left, right = st.columns([2, 1])
    with left:
        st.markdown('<div class="panel"><div class="panel-title">Open Positions</div>', unsafe_allow_html=True)
        if not portfolio["positions"]:
            st.markdown('<div style="color:#8892b0;padding:20px;text-align:center">Nessuna posizione aperta</div>', unsafe_allow_html=True)
        else:
            for p in portfolio["positions"]:
                cls = "pos" if p["pnl_usd"] >= 0 else "neg"
                side_cls = "short" if p["side"] == "SHORT" else ""
                tp_sl = ""
                if p["tp"] and p["sl"]:
                    tp_sl = f' · TP ${p["tp"]:,.0f} / SL ${p["sl"]:,.0f}'
                st.markdown(
                    f'<div class="pos-row {side_cls}">'
                    f'<div><span class="pos-symbol">{p["symbol"]}</span> '
                    f'<span class="pos-detail">{p["side"]} {p["leverage"]}x</span><br>'
                    f'<span class="pos-detail">Size ${p["size"]:.2f} · Entry ${p["entry"]:,.2f}{tp_sl}</span></div>'
                    f'<div style="text-align:right"><span class="pos-pnl {cls}">${p["pnl_usd"]:+.2f}</span><br>'
                    f'<span class="pos-detail {cls}">{p["pnl_pct"]:+.2f}%</span></div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
        st.markdown("</div>", unsafe_allow_html=True)

        # Log live sotto le posizioni
        st.markdown('<div class="panel"><div class="panel-title">Live Feed</div>', unsafe_allow_html=True)
        if not runtime.log:
            st.markdown('<div style="color:#8892b0;padding:10px">Nessun evento.</div>', unsafe_allow_html=True)
        else:
            lines = []
            for ts, msg in list(runtime.log)[:15]:
                lvl = "INFO"
                for tag in ("SIGNAL", "EXEC", "WARN", "ERR", "DEBUG"):
                    if msg.startswith(f"[{tag}]"):
                        lvl = tag
                        break
                msg_clean = msg.replace(f"[{lvl}] ", "")
                lines.append(
                    f'<div class="log-line {lvl}"><span class="ts">{ts}</span> '
                    f'<span class="msg">{msg_clean}</span></div>'
                )
            st.markdown('<div class="log-container">' + "".join(lines) + "</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with right:
        st.markdown('<div class="panel"><div class="panel-title">Account</div>', unsafe_allow_html=True)
        st.markdown(f'**Available:** ${portfolio["available"]:,.2f}')
        st.markdown(f'**Margin used:** ${portfolio["margin"]:,.2f}')
        st.markdown(f'**Mode:** {portfolio["mode"]}')
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div class="panel"><div class="panel-title">Quick Actions</div>', unsafe_allow_html=True)
        if st.button("🔄 Refresh", width="stretch"):
            st.rerun()
        if st.button("🔁 Reset Paper Account", width="stretch"):
            try:
                client = runtime.ensure_client()
                result = runtime.run_sync(client.reset_paper_account())
                st.success(f"Reset: {str(result)[:200]}")
                st.rerun()
            except Exception as e:
                st.error(f"Errore: {e}")

        st.markdown('<div class="panel-title" style="margin-top:14px;color:#ff2e63">⚠ KILL SWITCH</div>', unsafe_allow_html=True)
        if st.button("❌ CHIUDI TUTTE LE POSIZIONI", width="stretch"):
            try:
                client = runtime.ensure_client()
                closed = []
                for p in portfolio["positions"]:
                    runtime.run_sync(client.call("close_position", {"symbol": p["symbol"], "confirmed": True}))
                    closed.append(p["symbol"])
                if closed:
                    st.success(f"Chiuse: {', '.join(closed)}")
                else:
                    st.info("Nessuna posizione da chiudere.")
                st.rerun()
            except Exception as e:
                st.error(f"Errore: {e}")
        st.markdown("</div>", unsafe_allow_html=True)


# ---- CHART ----
with tab_chart:
    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        chart_symbol = st.selectbox("Symbol", ["BTC", "ETH", "SOL", "BNB", "XRP"], key="chart_symbol")
    with c2:
        chart_tf = st.selectbox("Timeframe", ["1m", "5m", "15m", "1h", "4h", "1d"], index=1, key="chart_tf")
    with c3:
        candles_n = st.number_input("Candele", min_value=50, max_value=1000, value=200, step=50, key="chart_n")

    try:
        df = fetch_candles(chart_symbol, timeframe=chart_tf, limit=int(candles_n))
    except Exception as e:
        st.error(f"Errore nel recupero candele: {e}")
        df = None

    if df is not None and not df.empty:
        # indicatori
        df["ema20"] = ta.trend.EMAIndicator(df["close"], window=20).ema_indicator()
        df["ema50"] = ta.trend.EMAIndicator(df["close"], window=50).ema_indicator()
        bb = ta.volatility.BollingerBands(df["close"], window=20, window_dev=2)
        df["bb_up"] = bb.bollinger_hband()
        df["bb_lo"] = bb.bollinger_lband()
        df["bb_mid"] = bb.bollinger_mavg()
        df["rsi"] = ta.momentum.RSIIndicator(df["close"], window=14).rsi()

        fig = make_subplots(
            rows=2, cols=1, shared_xaxes=True,
            row_heights=[0.75, 0.25], vertical_spacing=0.03,
            subplot_titles=(f"{chart_symbol}/USDT · {chart_tf}", "RSI14"),
        )
        fig.add_trace(go.Candlestick(
            x=df.index, open=df["open"], high=df["high"], low=df["low"], close=df["close"],
            increasing_line_color="#00ff88", decreasing_line_color="#ff2e63",
            increasing_fillcolor="#00ff88", decreasing_fillcolor="#ff2e63",
            name="Price",
        ), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df["ema20"], name="EMA20",
                                 line=dict(color="#00ffc8", width=1.2)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df["ema50"], name="EMA50",
                                 line=dict(color="#ffd93d", width=1.2)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df["bb_up"], name="BB up",
                                 line=dict(color="rgba(155,0,255,0.5)", width=1, dash="dot")), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df["bb_lo"], name="BB low",
                                 line=dict(color="rgba(155,0,255,0.5)", width=1, dash="dot"),
                                 fill="tonexty", fillcolor="rgba(155,0,255,0.08)"), row=1, col=1)

        fig.add_trace(go.Scatter(x=df.index, y=df["rsi"], name="RSI",
                                 line=dict(color="#00ffc8")), row=2, col=1)
        fig.add_hline(y=70, line_dash="dot", line_color="#ff2e63", row=2, col=1)
        fig.add_hline(y=30, line_dash="dot", line_color="#00ff88", row=2, col=1)

        fig.update_layout(
            paper_bgcolor="rgba(10,14,26,1)",
            plot_bgcolor="rgba(10,14,26,1)",
            font=dict(color="#e6f1ff", family="monospace"),
            height=650,
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            xaxis_rangeslider_visible=False,
        )
        fig.update_xaxes(gridcolor="rgba(136,146,176,0.1)")
        fig.update_yaxes(gridcolor="rgba(136,146,176,0.1)")
        st.plotly_chart(fig, width="stretch")

        # metriche
        mc = st.columns(4)
        mc[0].metric("Last", f"${df['close'].iloc[-1]:,.2f}")
        mc[1].metric("Change", f"{(df['close'].iloc[-1]/df['close'].iloc[0]-1)*100:+.2f}%")
        mc[2].metric("High", f"${df['high'].max():,.2f}")
        mc[3].metric("Low", f"${df['low'].min():,.2f}")


# ---- CONTROL ----
with tab_ctrl:
    left, right = st.columns([1, 1])
    with left:
        st.markdown('<div class="panel"><div class="panel-title">Scheduler</div>', unsafe_allow_html=True)

        symbols_input = st.text_input("Symbols (CSV)", value="BTC,ETH,SOL", key="cfg_symbols")
        timeframe = st.selectbox("Timeframe", ["1m", "5m", "15m", "1h", "4h", "1d"], index=1, key="cfg_tf")
        interval = st.number_input("Intervallo (s)", min_value=10, max_value=3600, value=60, step=10, key="cfg_interval")
        max_notional = st.number_input("Max notional ($)", min_value=10.0, max_value=1000.0, value=50.0, step=10.0, key="cfg_max_notional")
        execute = st.checkbox("Esegui ordini (paper)", value=False, key="cfg_execute")
        st.markdown("</div>", unsafe_allow_html=True)

        if runtime.scheduler_running:
            if st.button("⏹ FERMA SCHEDULER", width="stretch"):
                runtime.stop_scheduler()
                st.rerun()
        else:
            if st.button("▶ AVVIA SCHEDULER", width="stretch"):
                cfg = {
                    "symbols": [s.strip().upper() for s in symbols_input.split(",") if s.strip()],
                    "timeframe": timeframe,
                    "interval": int(interval),
                    "execute": bool(execute),
                    "max_notional": float(max_notional),
                }
                runtime.start_scheduler(cfg)
                st.rerun()

    with right:
        st.markdown('<div class="panel"><div class="panel-title">Status</div>', unsafe_allow_html=True)
        status = "🟢 ATTIVO" if runtime.scheduler_running else "🔴 FERMO"
        st.markdown(f"**Scheduler:** {status}")
        st.markdown(f"**Cicli eseguiti:** {runtime.cycle_count}")
        st.markdown(f"**Ultimo ciclo:** {runtime.last_cycle_at or '-'}")
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div class="panel"><div class="panel-title">Journal</div>', unsafe_allow_html=True)
        if st.button("🔄 Sync Journal", width="stretch"):
            try:
                from src.tools.journal_sync import sync_with_client
                client = runtime.ensure_client()
                result = runtime.run_sync(sync_with_client(client), timeout=30)
                st.success(f"Parsed: {result['parsed']}  Added: {result['added']}")
                st.rerun()
            except Exception as e:
                st.error(f"Errore sync: {e}")
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div class="panel"><div class="panel-title">Manual Trade</div>', unsafe_allow_html=True)
        ms = st.selectbox("Symbol", ["BTC", "ETH", "SOL"], key="m_sym")
        mside = st.selectbox("Side", ["long", "short"], key="m_side")
        msize = st.number_input("Size ($)", min_value=10.0, max_value=500.0, value=50.0, key="m_size")
        mlev = st.number_input("Leverage", min_value=1, max_value=10, value=3, key="m_lev")
        if st.button("📤 Proponi (suggest)", width="stretch"):
            try:
                client = runtime.ensure_client()
                res = runtime.run_sync(client.suggest_trade(
                    asset=ms, side=mside, leverage=int(mlev),
                    orderType="market", size=float(msize),
                    reasoning="Manuale da dashboard",
                ))
                st.code(str(res)[:1500], language="json")
            except Exception as e:
                st.error(f"Errore: {e}")
        st.markdown("</div>", unsafe_allow_html=True)


# ---- PERFORMANCE ----
with tab_perf:
    journal = load_journal()
    if journal.empty:
        st.info("Journal vuoto. Attiva lo scheduler per generare dati.")
    else:
        c1, c2, c3, c4 = st.columns(4)
        events = journal["event"].value_counts().to_dict()
        c1.metric("Eventi totali", len(journal))
        c2.metric("Segnali", events.get("suggested_dry_run", 0) + events.get("executed", 0))
        c3.metric("Eseguiti", events.get("executed", 0))
        c4.metric("No setup", events.get("no_setup", 0))

        # Distribuzione eventi
        st.markdown("### Distribuzione eventi")
        ev = journal["event"].value_counts()
        st.bar_chart(ev)

        # Equity curve (se ci sono trade eseguiti)
        eq = compute_equity_from_journal(journal)
        if not eq.empty:
            st.markdown("### Equity curve (da journal)")
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=eq["timestamp"], y=eq["equity"],
                mode="lines+markers", name="Equity",
                line=dict(color="#00ffc8", width=2),
                marker=dict(size=6, color="#00ffc8"),
            ))
            fig.update_layout(
                paper_bgcolor="rgba(10,14,26,1)",
                plot_bgcolor="rgba(10,14,26,1)",
                font=dict(color="#e6f1ff", family="monospace"),
                height=350,
                showlegend=False,
            )
            fig.update_xaxes(gridcolor="rgba(136,146,176,0.1)")
            fig.update_yaxes(gridcolor="rgba(136,146,176,0.1)")
            st.plotly_chart(fig, width="stretch")

        # Ultimi trade
        st.markdown("### Ultimi eventi")
        recent = journal.tail(20).iloc[::-1]
        st.dataframe(recent, width="stretch")


# ---- LOG ----
with tab_log:
    st.markdown('<div class="panel"><div class="panel-title">Full System Log</div>', unsafe_allow_html=True)
    if not runtime.log:
        st.markdown('<div style="color:#8892b0;padding:20px">Nessun evento.</div>', unsafe_allow_html=True)
    else:
        lines = []
        for ts, msg in list(runtime.log):
            lvl = "INFO"
            for tag in ("SIGNAL", "EXEC", "WARN", "ERR", "DEBUG"):
                if msg.startswith(f"[{tag}]"):
                    lvl = tag
                    break
            msg_clean = msg.replace(f"[{lvl}] ", "")
            lines.append(
                f'<div class="log-line {lvl}"><span class="ts">{ts}</span> '
                f'<span class="msg">{msg_clean}</span></div>'
            )
        st.markdown('<div class="log-container" style="max-height:600px">' + "".join(lines) + "</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
    if st.button("🗑 Pulisci log"):
        runtime.log.clear()
        st.rerun()


# ============ AUTO-REFRESH ============
# Sempre attivo, ogni 5 secondi
st.markdown(
    """
    <script>
    setTimeout(function() { window.location.reload(); }, 5000);
    </script>
    """,
    unsafe_allow_html=True,
)
