"""CSS custom per la dashboard in stile gaming/cyberpunk."""

CUSTOM_CSS = """
<style>
/* ===== BASE ===== */
.stApp {
    background: radial-gradient(circle at 20% 0%, #0f1630 0%, #0a0e1a 55%, #05070d 100%);
    font-family: 'JetBrains Mono', 'Fira Code', Consolas, monospace;
    color: #e6f1ff;
}

/* ===== HEADER ===== */
.main-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 16px 24px;
    background: linear-gradient(90deg, rgba(0,255,200,0.08) 0%, rgba(155,0,255,0.08) 100%);
    border: 1px solid rgba(0,255,200,0.25);
    border-radius: 12px;
    margin-bottom: 16px;
    box-shadow: 0 0 24px rgba(0,255,200,0.15);
}
.main-title {
    font-size: 22px;
    font-weight: 700;
    letter-spacing: 2px;
    color: #00ffc8;
    text-shadow: 0 0 12px rgba(0,255,200,0.6);
}
.main-subtitle {
    font-size: 11px;
    color: #8892b0;
    letter-spacing: 3px;
    text-transform: uppercase;
}

/* ===== STAT CARDS ===== */
.stat-card {
    background: linear-gradient(135deg, rgba(19,24,38,0.9) 0%, rgba(10,14,26,0.9) 100%);
    border: 1px solid rgba(0,255,200,0.15);
    border-radius: 10px;
    padding: 14px 18px;
    text-align: center;
    transition: all 0.2s;
}
.stat-card:hover {
    border-color: rgba(0,255,200,0.5);
    box-shadow: 0 0 20px rgba(0,255,200,0.2);
}
.stat-label {
    font-size: 10px;
    color: #8892b0;
    letter-spacing: 2px;
    text-transform: uppercase;
    margin-bottom: 4px;
}
.stat-value {
    font-size: 22px;
    font-weight: 700;
    color: #00ffc8;
    text-shadow: 0 0 10px rgba(0,255,200,0.5);
}
.stat-value.pos { color: #00ff88; text-shadow: 0 0 10px rgba(0,255,136,0.5); }
.stat-value.neg { color: #ff2e63; text-shadow: 0 0 10px rgba(255,46,99,0.5); }

/* ===== PANELS ===== */
.panel {
    background: rgba(19,24,38,0.6);
    border: 1px solid rgba(0,255,200,0.15);
    border-radius: 12px;
    padding: 16px;
    margin-bottom: 12px;
}
.panel-title {
    font-size: 11px;
    color: #00ffc8;
    letter-spacing: 3px;
    text-transform: uppercase;
    margin-bottom: 10px;
    border-bottom: 1px solid rgba(0,255,200,0.2);
    padding-bottom: 6px;
}

/* ===== POSITION ROW ===== */
.pos-row {
    display: flex;
    justify-content: space-between;
    padding: 10px 12px;
    background: rgba(0,255,200,0.05);
    border-left: 3px solid #00ffc8;
    border-radius: 6px;
    margin-bottom: 8px;
    font-size: 13px;
}
.pos-row.short { border-left-color: #ff2e63; background: rgba(255,46,99,0.05); }
.pos-symbol { font-weight: 700; color: #e6f1ff; }
.pos-detail { color: #8892b0; font-size: 11px; }
.pos-pnl.pos { color: #00ff88; font-weight: 700; }
.pos-pnl.neg { color: #ff2e63; font-weight: 700; }

/* ===== LOG ===== */
.log-container {
    background: #05070d;
    border: 1px solid rgba(0,255,200,0.15);
    border-radius: 8px;
    padding: 10px;
    font-size: 11px;
    max-height: 320px;
    overflow-y: auto;
    font-family: 'JetBrains Mono', monospace;
}
.log-line { padding: 2px 0; }
.log-line .ts { color: #4a5568; }
.log-line.INFO .msg { color: #8892b0; }
.log-line.SIGNAL .msg { color: #ffd93d; }
.log-line.EXEC .msg { color: #00ff88; font-weight: 700; }
.log-line.WARN .msg { color: #ffaa33; }
.log-line.ERR .msg { color: #ff2e63; font-weight: 700; }
.log-line.DEBUG .msg { color: #4a5568; }

/* ===== BUTTONS ===== */
.stButton > button {
    border-radius: 8px !important;
    border: 1px solid rgba(0,255,200,0.3) !important;
    background: rgba(0,255,200,0.08) !important;
    color: #00ffc8 !important;
    font-weight: 700 !important;
    letter-spacing: 2px !important;
    transition: all 0.2s !important;
}
.stButton > button:hover {
    background: rgba(0,255,200,0.2) !important;
    box-shadow: 0 0 20px rgba(0,255,200,0.4) !important;
    border-color: #00ffc8 !important;
}

/* ===== TABS ===== */
.stTabs [data-baseweb="tab-list"] {
    gap: 6px;
    background: transparent;
}
.stTabs [data-baseweb="tab"] {
    background: rgba(19,24,38,0.6);
    border-radius: 8px 8px 0 0;
    color: #8892b0;
    letter-spacing: 2px;
    font-size: 11px;
    text-transform: uppercase;
}
.stTabs [aria-selected="true"] {
    color: #00ffc8 !important;
    background: rgba(0,255,200,0.1) !important;
    border-bottom: 2px solid #00ffc8 !important;
}

/* ===== INPUTS ===== */
.stTextInput input, .stNumberInput input, .stSelectbox div {
    background: rgba(5,7,13,0.8) !important;
    border: 1px solid rgba(0,255,200,0.2) !important;
    color: #e6f1ff !important;
    font-family: 'JetBrains Mono', monospace !important;
    border-radius: 6px !important;
}

/* ===== METRIC ===== */
[data-testid="stMetricValue"] {
    color: #00ffc8 !important;
    font-family: 'JetBrains Mono', monospace !important;
    text-shadow: 0 0 10px rgba(0,255,200,0.4);
}
[data-testid="stMetricLabel"] {
    color: #8892b0 !important;
    letter-spacing: 2px;
    font-size: 10px !important;
    text-transform: uppercase;
}
</style>
"""
