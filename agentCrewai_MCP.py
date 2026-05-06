# veille_mcp.py — Agent de veille IA avec 3 serveurs MCP
import json
import os
import asyncio
from datetime import datetime
import shutil
from crewai import Agent, Task, Crew, Process
from crewai.tools import BaseTool
from crewai_tools import MCPServerAdapter
from mcp import StdioServerParameters

# ══════════════════════════════════════════════════════════════════════════════
# CONFIG MCP SERVERS
# ══════════════════════════════════════════════════════════════════════════════
npx_path = shutil.which("npx.cmd") or shutil.which("npx")
if not npx_path:
    raise FileNotFoundError("npx introuvable dans le PATH")


# TAVILY MCP PARAMS 
TAVILY_PARAMS    = StdioServerParameters(
    command=npx_path,
    args=["-y", "tavily-mcp@0.1.4"],
    env={**os.environ, "TAVILY_API_KEY": os.getenv("TAVILY_API_KEY", "")}
    
)

# SQLite MCP
SQLITE_PARAMS   = StdioServerParameters(
    command=npx_path,
    args=["-y", "mcp-server-sqlite-npx", os.path.abspath("veille.db")],
    env=os.environ.copy(),
)

# GitHub MCP
GITHUB_PARAMS   = StdioServerParameters(
    command=npx_path,
    args=["-y","@modelcontextprotocol/server-github"] ,
    env={**os.environ, "GITHUB_PERSONAL_ACCESS_TOKEN": os.getenv("GITHUB_TOKEN", "")}
    
)

GITHUB_REPO  = os.getenv("GITHUB_REPO",  "tonpseudo/ton-repo")
articles_buffer = []

# ══════════════════════════════════════════════════════════════════════════════
# OUTILS METIER (sans mémoire JSON — remplacée par SQLite MCP)
# ══════════════════════════════════════════════════════════════════════════════

class FetchRssTool(BaseTool):
    name: str        = "fetch_rss"
    description: str = "Recupere les derniers articles d'un flux RSS. Parametres : url, limit (defaut 3)."

    def _run(self, **kwargs) -> str:
        import feedparser
        url   = kwargs.get("url", "")
        limit = int(kwargs.get("limit", 3))
        feed  = feedparser.parse(url)
        return json.dumps(
            [{"title": e.title, "url": e.link} for e in feed.entries[:limit]],
            ensure_ascii=False
        )


class SummarizeUrlTool(BaseTool):
    name: str        = "summarize_url"
    description: str = "Telecharge et resume un article en 3 phrases en francais. Parametre : url."

    def _run(self, **kwargs) -> str:
        import requests
        from bs4 import BeautifulSoup
        from openai import OpenAI
        url = kwargs.get("url", "")
        try:
            resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            soup = BeautifulSoup(resp.text, "html.parser")
            text = soup.get_text(separator=" ", strip=True)[:3000]
            if len(text) < 100:
                return "SKIP"
            client = OpenAI()
            msg = client.chat.completions.create(
                model="gpt-4o", max_tokens=200,
                messages=[{"role": "user", "content": f"Resume en 3 phrases en francais :\n\n{text}"}]
            )
            return msg.choices[0].message.content
        except Exception as e:
            return f"SKIP ({e})"


class StoreArticleTool(BaseTool):
    name: str        = "store_article"
    description: str = "Stocke un article dans le buffer. Parametres : title, url, summary."

    def _run(self, **kwargs) -> str:
        title   = kwargs.get("title", "")
        url     = kwargs.get("url", "")
        summary = kwargs.get("summary", "")
        if "SKIP" in summary:
            return f"Article ignore : {title}"
        articles_buffer.append({"title": title, "url": url, "summary": summary})
        return f"Stocke ({len(articles_buffer)}) : {title[:60]}"


class GenerateReportTool(BaseTool):
    name: str        = "generate_report"
    description: str = "Genere le rapport HTML final depuis le buffer. Parametre : topic."

    def _run(self, **kwargs) -> str:
        topic    = kwargs.get("topic", "Intelligence Artificielle")
        articles = articles_buffer
        if not articles:
            return "Aucun article dans le buffer"

        date  = datetime.now().strftime("%d/%m/%Y a %H:%M")
        cards = ""
        for a in articles:
            cards += f"""
            <div class="card">
                <h2><a href="{a['url']}" target="_blank">{a['title']}</a></h2>
                <p>{a['summary']}</p>
                <a class="btn" href="{a['url']}" target="_blank">Lire</a>
            </div>"""

        html = f"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="UTF-8">
<title>Veille {topic}</title>
<style>
  body {{ font-family:sans-serif; max-width:860px; margin:40px auto; background:#f5f5f5; }}
  header {{ background:#1a1a2e; color:white; padding:28px 32px; border-radius:10px; margin-bottom:32px; }}
  .card {{ background:white; border-radius:10px; padding:24px; margin-bottom:20px; box-shadow:0 2px 8px rgba(0,0,0,.07); }}
  .card h2 a {{ color:#1a1a2e; text-decoration:none; }}
  .card p {{ color:#444; line-height:1.6; }}
  .btn {{ background:#1a1a2e; color:white; padding:8px 16px; border-radius:6px; text-decoration:none; }}
</style></head><body>
<header>
  <h1>Veille IA - {topic}</h1>
  <p>Genere le {date} - {len(articles)} articles</p>
</header>
{cards}
</body></html>"""

        filename = f"rapport_{datetime.now().strftime('%Y%m%d_%H%M')}.html"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(html)
        return f"Rapport genere : {filename} ({len(articles)} articles)"


# ══════════════════════════════════════════════════════════════════════════════
# MAIN — CrewAI + 3 serveurs MCP
# ══════════════════════════════════════════════════════════════════════════════

def main():
    articles_buffer.clear()
    date_du_jour = datetime.now().strftime("%d/%m/%Y")

    with MCPServerAdapter(TAVILY_PARAMS)  as tavily_tools, \
         MCPServerAdapter(SQLITE_PARAMS) as sqlite_tools, \
         MCPServerAdapter(GITHUB_PARAMS) as github_tools:

        print(f"Tavily  tools : {[t.name for t in tavily_tools]}")
        print(f"SQLite tools : {[t.name for t in sqlite_tools]}")
        print(f"GitHub tools : {[t.name for t in github_tools]}")

        # ── AGENTS ────────────────────────────────────────────────────────────

        chercheur = Agent(
            role="Chercheur de sources",
            goal=(
                "Utiliser Brave Search pour trouver les meilleures sources RSS "
                "sur l'intelligence artificielle, puis verifier dans SQLite "
                "si elles sont deja connues et bien scorees."
            ),
            backstory=(
                "Tu es expert en recherche d'information. "
                "Tu utilises Brave Search pour trouver des sources fiables sur l'IA, "
                "et tu consultes la base SQLite pour eviter les doublons "
                "et prioriser les sources avec les meilleurs scores."
            ),
            tools=[*brave_tools, *sqlite_tools],
            verbose=True,
            max_iter=15
        )

        collecteur = Agent(
            role="Collecteur de veille",
            goal="Recuperer 3 articles par source RSS selectionnee.",
            backstory="Expert en veille technologique et collecte RSS.",
            tools=[FetchRssTool()],
            verbose=True,
            max_iter=15
        )

        analyste = Agent(
            role="Analyste IA",
            goal="Resumer chaque article et le stocker dans le buffer et dans SQLite.",
            backstory=(
                "Expert en IA et synthese d'information. "
                "Tu resumes les articles et tu les sauvegardes "
                "dans la base SQLite pour un historique permanent."
            ),
            tools=[SummarizeUrlTool(), StoreArticleTool(), *sqlite_tools],
            verbose=True,
            max_iter=30
        )

        rapporteur = Agent(
            role="Rapporteur et Archiviste GitHub",
            goal=(
                "Generer le rapport HTML et creer une issue GitHub "
                "avec le resume de la veille du jour."
            ),
            backstory=(
                "Expert en communication et documentation. "
                "Tu generes le rapport HTML de la veille "
                "et tu crees une issue GitHub pour garder une trace "
                "de chaque session de veille."
            ),
            tools=[GenerateReportTool(), *github_tools],
            verbose=True,
            max_iter=10
        )

        # ── TASKS ─────────────────────────────────────────────────────────────

        tache_recherche = Task(
            description=(
                "1) Utilise Brave Search pour chercher "
                "   'meilleurs flux RSS intelligence artificielle 2025'. "
                "2) Selectionne 3 URLs de flux RSS pertinentes. "
                "3) Verifie dans SQLite si la table 'sources' existe, "
                "   sinon cree-la avec : "
                "   CREATE TABLE IF NOT EXISTS sources "
                "   (id INTEGER PRIMARY KEY, name TEXT, url TEXT UNIQUE, "
                "   score INTEGER DEFAULT 5, articles_vus INTEGER DEFAULT 0). "
                "4) Insere les nouvelles sources trouvees (ignore les doublons). "
                "5) Retourne les 3 sources avec le meilleur score en JSON."
            ),
            expected_output="Liste JSON de 3 sources avec name, url, score.",
            agent=chercheur
        )

        tache_collecte = Task(
            description=(
                "Pour chaque source recue, appelle fetch_rss avec limit=3. "
                "Appelle fetch_rss exactement 3 fois. "
                "Retourne tous les articles en JSON."
            ),
            expected_output="Liste JSON de 9 articles avec title et url.",
            agent=collecteur,
            context=[tache_recherche]
        )

        tache_analyse = Task(
            description=(
                "Pour chaque article : "
                "1) Appelle summarize_url. "
                "2) Si SKIP, ignore et continue. "
                "3) Appelle store_article pour le buffer. "
                "4) Insere dans SQLite : "
                "   CREATE TABLE IF NOT EXISTS articles "
                "   (id INTEGER PRIMARY KEY, title TEXT, url TEXT UNIQUE, "
                "   summary TEXT, date TEXT). "
                "   INSERT OR IGNORE INTO articles (title, url, summary, date) "
                f"  VALUES (title, url, summary, '{date_du_jour}'). "
                "Retourne le nombre d'articles stockes."
            ),
            expected_output="Nombre d'articles stockes avec succes.",
            agent=analyste,
            context=[tache_collecte]
        )

        tache_rapport = Task(
            description=(
                "1) Appelle generate_report avec topic='Intelligence Artificielle'. "
                f"2) Cree une issue GitHub dans le repo {GITHUB_REPO} avec : "
                f"   - Titre : 'Veille IA du {date_du_jour}' "
                "   - Body : liste des articles avec titre et URL "
                "   - Label : 'veille-ia' "
                "Retourne la confirmation de creation de l'issue."
            ),
            expected_output="Confirmation du rapport genere et de l'issue GitHub creee.",
            agent=rapporteur,
            context=[tache_analyse]
        )

        # ── CREW ──────────────────────────────────────────────────────────────

        crew = Crew(
            agents=[chercheur, collecteur, analyste, rapporteur],
            tasks=[tache_recherche, tache_collecte, tache_analyse, tache_rapport],
            process=Process.sequential,
            verbose=True
        )

        print("\nDemarrage de la veille IA avec CrewAI + MCP\n" + "-"*60)
        result = crew.kickoff()
        print(f"\nMission accomplie !\n{result}")


if __name__ == "__main__":
    main()