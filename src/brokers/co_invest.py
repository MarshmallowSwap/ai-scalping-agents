"""
Wrapper Python per il server MCP di Co-Invest (Liquid).
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from contextlib import AsyncExitStack
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logger = logging.getLogger(__name__)

MCP_SERVER_URL = "https://coinvest.liquid.trade/mcp"


class CoInvestError(RuntimeError):
    """Errore sollevato quando un tool MCP restituisce un errore."""


class CoInvestClient:
    """Client async per Co-Invest via MCP."""

    def __init__(self, server_url: str = MCP_SERVER_URL):
        self.server_url = server_url
        self._session: ClientSession | None = None
        self._exit_stack: AsyncExitStack | None = None

    async def __aenter__(self) -> "CoInvestClient":
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.stop()

    async def start(self) -> None:
        if self._session is not None:
            return
        logger.info("Avvio mcp-remote per %s", self.server_url)
        params = StdioServerParameters(
            command="npx.cmd",
            args=["-y", "mcp-remote", self.server_url],
        )
        self._exit_stack = AsyncExitStack()
        read, write = await self._exit_stack.enter_async_context(stdio_client(params))
        session = await self._exit_stack.enter_async_context(ClientSession(read, write))
        await session.initialize()
        self._session = session
        logger.info("Sessione MCP pronta.")

    async def stop(self) -> None:
        if self._exit_stack is not None:
            await self._exit_stack.aclose()
            self._exit_stack = None
            self._session = None

    async def list_tools(self) -> list[dict[str, Any]]:
        assert self._session is not None, "Client non avviato"
        result = await self._session.list_tools()
        return [{"name": t.name, "description": (t.description or "").strip()} for t in result.tools]

    async def call(self, tool_name: str, arguments: dict[str, Any] | None = None) -> Any:
        assert self._session is not None, "Client non avviato"
        args = arguments or {}
        logger.debug("MCP call: %s %s", tool_name, args)
        result = await self._session.call_tool(tool_name, args)
        if getattr(result, "isError", False):
            raise CoInvestError(f"Tool {tool_name} ha restituito errore: {result.content}")
        parts: list[str] = []
        for item in result.content:
            text = getattr(item, "text", None)
            if text:
                parts.append(text)
        raw = "\n".join(parts) if parts else ""
        if not raw:
            return None
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return raw

    # -------- Analisi --------

    async def analyze_market(self, symbol: str) -> Any:
        return await self.call("analyze_market", {"symbol": symbol})

    async def analyze_markets_batch(self, symbols: list[str]) -> Any:
        return await self.call("analyze_markets_batch", {"symbols": symbols})

    async def get_technical_indicators(self, **kwargs: Any) -> Any:
        return await self.call("get_technical_indicators", kwargs)

    async def get_positioning_pulse(self) -> Any:
        return await self.call("get_positioning_pulse", {})

    async def get_news(self, **kwargs: Any) -> Any:
        return await self.call("get_news", kwargs)

    # -------- Portfolio / account --------

    async def get_portfolio(self) -> Any:
        return await self.call("get_portfolio", {})

    async def get_account(self) -> Any:
        return await self.call("get_account", {})

    async def view_open_orders(self) -> Any:
        return await self.call("view_open_orders", {})

    async def get_position_history(self, **kwargs: Any) -> Any:
        return await self.call("get_position_history", kwargs)

    # -------- Paper trading --------

    async def enable_paper_trading(self) -> Any:
        return await self.call("enable_paper_trading", {})

    async def disable_paper_trading(self) -> Any:
        return await self.call("disable_paper_trading", {})

    async def paper_trading_status(self) -> Any:
        return await self.call("paper_trading_status", {})

    async def reset_paper_account(self) -> Any:
        return await self.call("reset_paper_account", {})

    # -------- Proposta / esecuzione --------

    async def suggest_trade(self, **kwargs: Any) -> Any:
        return await self.call("suggest_trade", kwargs)

    async def execute_suggestion(
        self,
        suggestion: dict[str, Any],
        idempotency_key: str | None = None,
    ) -> Any:
        """Esegue un oggetto di proposta restituito da suggest_trade.

        Mappa i campi come richiesto da execute_order: solo i campi esecutivi,
        escluse le proprieta' di sola visualizzazione (sizeBasis, displayName, ecc.).
        """
        order = suggestion.get("order") if isinstance(suggestion, dict) and "order" in suggestion else suggestion
        if not isinstance(order, dict):
            raise CoInvestError(f"Formato suggestion non riconosciuto: {suggestion!r}")

        side = order.get("side")
        side_exec = "buy" if side == "long" else "sell" if side == "short" else side

        args: dict[str, Any] = {
            "executionMode": suggestion.get("executionMode", "paper"),
            "symbol": order.get("asset"),
            "side": side_exec,
            "size": order.get("size"),
            "type": order.get("orderType", "market"),
            "leverage": order.get("leverage"),
            "reasoning": order.get("reasoning", ""),
            "confirmed": True,
            "idempotencyKey": idempotency_key or str(uuid.uuid4()),
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

    async def execute_order(self, **kwargs: Any) -> Any:
        return await self.call("execute_order", kwargs)

    async def close_position(self, **kwargs: Any) -> Any:
        return await self.call("close_position", kwargs)

    async def cancel_order(self, **kwargs: Any) -> Any:
        return await self.call("cancel_order", kwargs)

    async def update_leverage(self, **kwargs: Any) -> Any:
        return await self.call("update_leverage", kwargs)

    # -------- Policy di automazione --------

    async def enable_automated_trading(self, **kwargs: Any) -> Any:
        return await self.call("enable_automated_trading", kwargs)

    async def disable_automated_trading(self) -> Any:
        return await self.call("disable_automated_trading", {})

    async def automated_trading_status(self) -> Any:
        return await self.call("automated_trading_status", {})


async def _smoke_test() -> None:
    logging.basicConfig(level=logging.INFO)
    async with CoInvestClient() as client:
        print("== paper_trading_status ==")
        print(await client.paper_trading_status())


if __name__ == "__main__":
    asyncio.run(_smoke_test())
