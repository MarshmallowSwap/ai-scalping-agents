import asyncio
import json
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    server_params = StdioServerParameters(
        command="npx.cmd",
        args=["-y", "mcp-remote", "https://coinvest.liquid.trade/mcp"],
    )

    print("Avvio mcp-remote e connessione al server Co-Invest...")

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print("Connesso al server MCP.\n")

            tools = await session.list_tools()
            print(f"Tool disponibili: {len(tools.tools)}\n")

            # Salva il catalogo completo su file JSON
            catalogue = []
            for tool in tools.tools:
                catalogue.append({
                    "name": tool.name,
                    "description": (tool.description or "").strip(),
                    "input_schema": tool.inputSchema if hasattr(tool, "inputSchema") else None,
                })

            with open("tools_catalogue.json", "w", encoding="utf-8") as f:
                json.dump(catalogue, f, indent=2, ensure_ascii=False)

            print("Catalogo salvato in tools_catalogue.json")

            # Stampa solo i nomi dei tool + primi 120 caratteri di descrizione
            for tool in tools.tools:
                desc = (tool.description or "").strip().replace("\n", " ")
                print(f"- {tool.name}: {desc[:120]}")


if __name__ == "__main__":
    asyncio.run(main())