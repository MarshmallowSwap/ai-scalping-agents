from pathlib import Path

p = Path("src/brokers/co_invest.py")
content = p.read_text(encoding="utf-8")

# 1) Aggiungi import safety
if "from src.tools.safety import" not in content:
    content = content.replace(
        "from mcp import ClientSession, StdioServerParameters",
        "from mcp import ClientSession, StdioServerParameters\nfrom src.tools.safety import (\n    assert_paper_mode,\n    assert_status_pending,\n    log_execution_attempt,\n)"
    )

# 2) Sostituisci execute_suggestion con la versione sicura
old_marker = "    async def execute_suggestion("
new_method = '''    async def execute_suggestion(
        self,
        suggestion: dict[str, Any],
        idempotency_key: str | None = None,
    ) -> Any:
        """Esegue una proposta SOLO dopo i controlli di sicurezza.

        Guardrail:
          - executionMode deve essere 'paper' (o 'live' con sentinella armata)
          - status della proposta deve essere 'pending_confirmation'
          - ogni tentativo viene loggato con fingerprint
        """
        order = suggestion.get("order") if isinstance(suggestion, dict) and "order" in suggestion else suggestion
        if not isinstance(order, dict):
            raise CoInvestError(f"Formato suggestion non riconosciuto: {suggestion!r}")

        # SAFETY: guardrail
        execution_mode = suggestion.get("executionMode", "paper")
        assert_status_pending(suggestion)
        assert_paper_mode(execution_mode)

        side = order.get("side")
        side_exec = "buy" if side == "long" else "sell" if side == "short" else side

        idem = idempotency_key or str(uuid.uuid4())
        log_execution_attempt(suggestion, idem)

        args: dict[str, Any] = {
            "executionMode": execution_mode,
            "symbol": order.get("asset"),
            "side": side_exec,
            "size": order.get("size"),
            "type": order.get("orderType", "market"),
            "leverage": order.get("leverage"),
            "reasoning": order.get("reasoning", ""),
            "confirmed": True,
            "idempotencyKey": idem,
        }
        if order.get("requestedLeverage") is not None:
            args["requestedLeverage"] = order["requestedLeverage"]
        if order.get("takeProfit") is not None:
            args["tp"] = order["takeProfit"]
        if order.get("stopLoss") is not None:
            args["sl"] = order["stopLoss"]
        if order.get("limitPrice") is not None:
            args["price"] = order["limitPrice"]
        if order.get("timeInForce") is not None:
            args["timeInForce"] = order["timeInForce"]
        if order.get("aiAttribution") is not None:
            args["aiAttribution"] = order["aiAttribution"]

        return await self.call("execute_order", args)
'''

i_start = content.find(old_marker)
if i_start == -1:
    print("ERRORE: marker execute_suggestion non trovato")
else:
    # Trova la fine del metodo (prossima def async o def con indentazione 4)
    tail = content[i_start:]
    # cerca il prossimo "\n    async def" dopo la firma
    next_idx = tail.find("\n    async def", 10)
    if next_idx == -1:
        next_idx = tail.find("\n    # --------", 10)
    if next_idx == -1:
        print("ERRORE: fine metodo execute_suggestion non trovata")
    else:
        old_method = tail[:next_idx]
        content = content[:i_start] + new_method + content[i_start + next_idx:]
        p.write_text(content, encoding="utf-8")
        print("FATTO: execute_suggestion sostituita con versione sicura.")
