# AI Scalping Agents

Sistema multi-agente per scalping su crypto futures (Pionex / Liquid) con apprendimento trade-by-trade.

## Stack

- Python 3.11
- PyTorch (CPU) + Stable-Baselines3 + Gymnasium (RL)
- pandas, numpy, ta (analisi dati)
- ccxt, websockets (connessione exchange)
- Co-Invest (MCP) per dati ed esecuzione assistita

## Struttura

- `src/agents/` — agenti (analyst, decision, risk, execution, orchestrator)
- `src/backtest/` — motore event-driven e metriche
- `src/brokers/` — wrapper per Pionex e Co-Invest
- `src/data/` — feed dati (WebSocket, REST)
- `src/models/` — wrapper RL
- `src/utils/` — utility
- `configs/` — file YAML di configurazione
- `data/` — dati grezzi e processati
- `tests/` — test

## Modalita

1. `backtest` — simulazione storica
2. `paper` — decisioni reali, esecuzione confermata manualmente (Co-Invest)
3. `live` — esecuzione automatica (solo dopo validazione)

## Setup

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt