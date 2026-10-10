from pathlib import Path

p = Path("dashboard/app.py")
content = p.read_text(encoding="utf-8")

journal_block = """        st.markdown('<div class="panel"><div class="panel-title">Journal</div>', unsafe_allow_html=True)
        if st.button("\U0001F504 Sync Journal", use_container_width=True):
            try:
                from src.tools.journal_sync import sync_with_client
                client = runtime.ensure_client()
                result = runtime.run_sync(sync_with_client(client), timeout=30)
                st.success(f"Parsed: {result['parsed']}  Added: {result['added']}")
                st.rerun()
            except Exception as e:
                st.error(f"Errore sync: {e}")
        st.markdown("</div>", unsafe_allow_html=True)

"""

marker = """        st.markdown('<div class="panel"><div class="panel-title">Manual Trade</div>', unsafe_allow_html=True)"""

if "Sync Journal" in content:
    print("OK: il pannello Journal esiste gia', nessuna modifica necessaria.")
elif marker not in content:
    print("ERRORE: marker 'Manual Trade' non trovato. Il file potrebbe essere vecchio.")
else:
    content = content.replace(marker, journal_block + marker, 1)
    p.write_text(content, encoding="utf-8")
    print("FATTO: pannello Journal inserito sopra Manual Trade.")
