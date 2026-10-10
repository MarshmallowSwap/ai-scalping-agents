"""Guardrail di sicurezza per l'esecuzione degli ordini.

Regole:
  - Il sistema gira in PAPER mode di default.
  - L'esecuzione LIVE richiede un file sentinella '.live_enabled' creato
    manualmente dall'utente nella root del progetto.
  - Il file sentinella deve contenere esattamente la stringa
    "I_UNDERSTAND_LIVE_TRADING_IS_RISKY" (una riga, senza spazi extra).
  - Ogni tentativo di esecuzione viene loggato con hash del payload.
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

SENTINEL_PATH = Path(".live_enabled")
SENTINEL_CONTENT = "I_UNDERSTAND_LIVE_TRADING_IS_RISKY"


class SafetyError(RuntimeError):
    """Violazione di un guardrail di sicurezza."""


def is_live_armed() -> bool:
    """Ritorna True solo se il file sentinella esiste E ha il contenuto corretto."""
    if not SENTINEL_PATH.exists():
        return False
    try:
        content = SENTINEL_PATH.read_text(encoding="utf-8").strip()
    except Exception as e:
        logger.error("Impossibile leggere il file sentinella: %s", e)
        return False
    return content == SENTINEL_CONTENT


def assert_paper_mode(execution_mode: str) -> None:
    """Solleva SafetyError se execution_mode non e' 'paper' e il live non e' armato."""
    if execution_mode == "paper":
        return
    if execution_mode == "live" and is_live_armed():
        logger.warning(
            "SAFETY: esecuzione LIVE consentita (sentinella armata). mode=%s",
            execution_mode,
        )
        return
    raise SafetyError(
        f"Esecuzione bloccata: mode='{execution_mode}' ma il live NON e' armato. "
        f"Per abilitare il live, crea il file '{SENTINEL_PATH}' con contenuto "
        f"esatto '{SENTINEL_CONTENT}'."
    )


def assert_status_pending(suggestion: dict[str, Any]) -> None:
    """Verifica che la proposta sia in stato 'pending_confirmation'."""
    status = suggestion.get("status")
    if status != "pending_confirmation":
        raise SafetyError(
            f"Proposta non in stato 'pending_confirmation' (trovato: {status!r}). "
            "Rifiuto l'esecuzione per evitare doppie esecuzioni o replay."
        )


def log_execution_attempt(suggestion: dict[str, Any], idempotency_key: str) -> str:
    """Logga il tentativo e ritorna un fingerprint del payload."""
    payload = json.dumps(suggestion, sort_keys=True, ensure_ascii=False, default=str)
    fp = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    logger.info(
        "SAFETY: execute attempt | fp=%s | idem=%s | symbol=%s | side=%s | mode=%s",
        fp, idempotency_key,
        (suggestion.get("order") or {}).get("asset"),
        (suggestion.get("order") or {}).get("side"),
        suggestion.get("executionMode"),
    )
    return fp


def require_paper_trading_status(text: str) -> None:
    """Verifica che il testo di paper_trading_status contenga ENABLED."""
    if "ENABLED" not in text.upper():
        raise SafetyError(
            "Paper trading NON abilitato lato Co-Invest. "
            "Abilitalo con enable_paper_trading() prima di procedere."
        )
