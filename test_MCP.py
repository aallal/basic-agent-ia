from crewai_tools import MCPServerAdapter
from mcp import StdioServerParameters
import os, shutil
from dotenv import load_dotenv
# Charger les variables d'environnement depuis le fichier .env
load_dotenv()

npx_path = shutil.which("npx.cmd") or shutil.which("npx")
if not npx_path:
    raise FileNotFoundError("npx introuvable dans le PATH")


# ── 1. SQLite ──────────────────────────────────────────────
print("\n=== TEST SQLite MCP ===")
sqlite_params  = StdioServerParameters(
    command=npx_path,
    args=["-y", "mcp-server-sqlite-npx", os.path.abspath("veille.db")],
    env=os.environ.copy(),
)
#print("\nConnexion au serveur MCP SQLite...")
with MCPServerAdapter(sqlite_params) as sqlite_tools:
    print("Outils MCP SQLite disponibles :")
    for tool in sqlite_tools:
        print(f"  - {tool.name} : {tool.description[:60]}")

# ── 2. GitHub ──────────────────────────────────────────────
print("\n=== TEST GitHub MCP ===")
github_params   = StdioServerParameters(
    command=npx_path,
    args=["-y","@modelcontextprotocol/server-github"] ,
    env={**os.environ, "GITHUB_PERSONAL_ACCESS_TOKEN": os.getenv("GITHUB_TOKEN", "")}
    
)
#print("\nConnexion au serveur MCP Github ...")
with MCPServerAdapter(github_params) as tools:
    print("Outils MCP GitHub disponibles :")
    for tool in tools:
        print(f"  - {tool.name} : {tool.description[:60]}")


# ── 3. Tavily ──────────────────────────────────────────────
print("\n=== TEST Tavily MCP ===")
tavily_params   = StdioServerParameters(
    command=npx_path,
    args=["-y", "tavily-mcp@0.1.4"],
    env={**os.environ, "TAVILY_API_KEY": os.getenv("TAVILY_API_KEY", "")}
    
)
#print("\nConnexion au serveur MCP Tavily ...")
with MCPServerAdapter(tavily_params) as tools:
    print("Outils MCP Tavily disponibles :")
    for tool in tools:
        print(f"  - {tool.name} : {tool.description[:60]}")
    

print("\n Tous les serveurs MCP sont opérationnels !")