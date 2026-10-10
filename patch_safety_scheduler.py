from pathlib import Path

p = Path("src/tools/scheduler.py")
content = p.read_text(encoding="utf-8")

# 1) Import safety
if "from src.tools.safety import" not in content:
    content = content.replace(
        "from src.brokers.co_invest import CoInvestClient",
        "from src.brokers.co_invest import CoInvestClient\nfrom src.tools.safety import require_paper_trading_status"
    )

# 2) Controllo paper all'avvio dello scheduler (dopo l'apertura del client)
marker = "        while not stop.is_set():"
check_block = '''        # SAFETY: verifica paper trading abilitato
        try:
            paper_text = str(await client.paper_trading_status())
            require_paper_trading_status(paper_text)
            logger.info("SAFETY: paper mode confermato lato Co-Invest.")
        except Exception as e:
            logger.error("SAFETY: impossibile confermare paper mode: %s", e)
            raise SystemExit(2)

        while not stop.is_set():'''

if marker in content and "SAFETY: paper mode confermato" not in content:
    content = content.replace(marker, check_block, 1)
    p.write_text(content, encoding="utf-8")
    print("FATTO: scheduler con check safety all'avvio.")
elif "SAFETY: paper mode confermato" in content:
    print("OK: check gia' presente.")
else:
    print("ERRORE: marker while non trovato.")
