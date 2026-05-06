from datetime import datetime
import os
from pathlib import Path

from bs4 import BeautifulSoup
from dotenv import load_dotenv
import feedparser
import json

from crewai import Agent,  Crew, Process, Task
from crewai.tools import BaseTool
from openai import OpenAI
import requests

import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

MODEL_AI = "gpt-4.1-mini"
SOURCES_FILE = Path(__file__).resolve().parent.parent / "sources.json"
MAX_SOURCES  = 10
SCORE_MIN    = 5
SOURCES_DEFAUT = {
    "sources": [
        {
            "name": "Hacker News",
            "url": "https://hnrss.org/frontpage",
            "tags": ["tech", "ia", "dev"],
            "score": 7,
            "articles_vus": 0,
            "derniere_utilisation": None,
        },
        {
            "name": "MIT Tech Review",
            "url": "https://www.technologyreview.com/feed/",
            "tags": ["ia", "science", "tech"],
            "score": 7,
            "articles_vus": 0,
            "derniere_utilisation": None,
        },
        {
            "name": "Hugging Face",
            "url": "https://huggingface.co/blog/feed.xml",
            "tags": ["ia", "llm", "ml"],
            "score": 9,
            "articles_vus": 0,
            "derniere_utilisation": None,
        },
        {
            "name": "TechCrunch",
            "url": "https://techcrunch.com/feed/",
            "tags": ["startup", "tech"],
            "score": 6,
            "articles_vus": 0,
            "derniere_utilisation": None,
        },
        {
            "name": "OpenAI Blog",
            "url": "https://openai.com/news/rss.xml",
            "tags": ["ia", "gpt", "llm"],
            "score": 9,
            "articles_vus": 0,
            "derniere_utilisation": None,
        },
    ]
}

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ==============================================================================
# Agent Crew
# ==============================================================================


# ==============================================================================
# les outils de l'agent crew
# ==============================================================================
# Charger les sources depuis le fichier sur disque
def _load_sources() -> dict:
    if not os.path.exists(SOURCES_FILE):
        _save_sources(SOURCES_DEFAUT)
        return SOURCES_DEFAUT
    with open(SOURCES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def _save_sources(data: dict):
    with open(SOURCES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)



class GetSourcesTool(BaseTool):
    name: str = "get_sources"
    description: str = (
        "Retourne toutes les sources RSS mémorisées triées par score décroissant. Usage: get_sources() -> str"
    )
    def _run(self) -> str:
        data = _load_sources()
        # trier les sources par score décroissant
        data['sources'].sort(key=lambda x: x["score"], reverse=True)

        top_sources = data['sources'][:MAX_SOURCES]

        return json.dumps(top_sources, ensure_ascii=False , indent=2)  # Return as JSON string

class AddSourceTool(BaseTool):
    name: str = "add_source"
    description: str = (
        "Ajouter une nouvelle source RSS. Usage: add_source(name: str, url: str, tags: list[str], score: int=5) -> str. "
        "Fournis uniquement un objet JSON valide sans texte supplémentaire."
    )
    

    def _run(self, name: str, url: str, tags: list[str], score: int = 5) -> str:
        data = _load_sources()
        #vérifier si la source existe déjà (connue)
        if any(s["url"] == url for s in data["sources"]):
            return f"Erreur : La source '{name}' existe déjà."

        if len(data["sources"]) >= MAX_SOURCES:
            return f"Erreur : Nombre maximum de sources ({MAX_SOURCES}) déjà atteint."
        
        if score < SCORE_MIN:
            return f"Erreur : Le score doit être au moins {SCORE_MIN}."
        
        new_source = {
            "name": name,
            "url": url,
            "tags": tags,
            "score": score,
            "articles_vus": 0,
            "derniere_utilisation": None,
        }
        data["sources"].append(new_source)
        _save_sources(data)
        return f"Source '{name}' ajoutée avec succès !"    
    
class RemoveSourceTool(BaseTool):
    name: str = "remove_source"
    description: str = (
        "Supprimer une source RSS par son URL. Usage: remove_source(url: str) -> str"
    )

    def _run(self, url: str) -> str:
        data = _load_sources()
        sources_initiales = len(data["sources"])
        data["sources"] = [s for s in data["sources"] if s["url"] != url]
        if len(data["sources"]) < sources_initiales:
            _save_sources(data)
            return f"Source avec URL '{url}' supprimée avec succès."
        else:
            return f"Erreur : Aucune source trouvée avec l'URL '{url}'."    
        
class UpdateSourceScoreTool(BaseTool):
    name: str = "update_score"
    description: str = (
        "Met à jour le score d'une source RSS. Usage: update_score(url: str, score: int, raison: str = '') -> str. "
        "Fournis uniquement un objet JSON valide sans texte supplémentaire."
    )
    

    def _run(self, url: str, score: int, raison: str = "") -> str:
        if score is None:
            return "Erreur : score manquant."
        try:
            score = int(score)
        except (TypeError, ValueError):
            return "Erreur : le score doit être un entier valide entre 1 et 10."

        data = _load_sources()
        for source in data["sources"]:
            if source["url"] == url:
                ancien_score = source['score']
                bounded_score = max(1, min(10, score))  # Assurer que le score reste entre 1 et 10
                source["score"] = bounded_score
                source["derniere_utilisation"] = datetime.now().strftime("%Y-%m-%d")
                source["articles_vus"] += 1
                _save_sources(data)
                return f"Score de la source avec URL '{url}' mis à jour de {ancien_score} à {bounded_score}."
        return f"Erreur : Aucune source trouvée avec l'URL '{url}'."

class CleanupSourcesTool(BaseTool):
    name: str = "cleanup_sources"
    description: str = (
        "Supprime les sources RSS dont le score est inférieur au seuil défini à {SCORE_MIN}. Usage: cleanup_sources() -> str"
    )

    def _run(self) -> str:
        data = _load_sources()
        sources_initiales = len(data["sources"])
        data["sources"] = [s for s in data["sources"] if s["score"] >= SCORE_MIN]
        sources_supprimees = sources_initiales - len(data["sources"])
        if sources_supprimees > 0:
            _save_sources(data)
            return f"{sources_supprimees} source(s) supprimée(s) avec un score inférieur à {SCORE_MIN}."
        else:
            return "Aucune source supprimée. Toutes les sources ont un score supérieur ou égal au seuil."

class FetchRssTool(BaseTool):
    name: str = "fetch_rss"
    description: str = (
        "Fetch the content of an RSS feed. Usage: fetch_rss(url: str, limit: int = 5) -> str"
    )

    def _run(self, url: str, limit: int = 5) -> str:
        feed = feedparser.parse(url)
        articles = [{"title": e.title, "url": e.link} for e in feed.entries[:limit]]
        return json.dumps(articles, ensure_ascii=False)  # Return as JSON string


class SummarizeUrlTool(BaseTool):
    name: str = "summarize_article"
    description: str = (
        "Télécharge une page web et retourne un résumé en 3 phrases en français. Paramètre : url (str)."
    )

    def _run(self, url: str) -> str:
        # Placeholder for article summarization logic
        try:
            response = requests.get(
                url, timeout=10, headers={"User-Agent": "Mozilla/5.0"}
            )
            soup = BeautifulSoup(response.text, "html.parser")
            Content = soup.get_text(separator=" ", strip=True)[:3000]
            if len(Content) < 100:  # page vide ou inaccessible
                return "SKIP"
            #client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            msg = client.chat.completions.create(
                model=MODEL_AI,
                messages=[
                    {
                        "role": "user",
                        "content": f"Résume en 3 phrases cet article en français :\n\n{Content}",
                    }
                ],
                max_tokens=300,
            )
            return msg.choices[0].message.content
        except requests.RequestException as e:
            print(f"Error fetching URL {url}: {e}")
            return f"SKIP ({e})"


class GenerateReportTool(BaseTool):
    name: str = "generate_report"
    description: str = (
        "Génère un rapport HTML à partir d'une liste JSON d'articles. Usage: generate_report(articles_json : str, topic: str) -> str"
    )

    def _run(self, articles_json: str, topic: str = "Agent IA") -> str:
        try:
            articles = json.loads(articles_json)
        except Exception as e:
            return "Erreur : Données JSON invalides."

        if not articles:
            return "Aucun article dans le buffer !"

        date = datetime.now().strftime("%d/%m/%Y à %H:%M")
        cards = ""
        for a in articles:
            cards += f"""
            <div class="card">
                <h2><a href="{a['url']}" target="_blank">{a['title']}</a></h2>
                <p>{a['summary']}</p>
                <a class="btn" href="{a['url']}" target="_blank">Lire l'article →</a>
            </div>"""

            html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <title>Veille — {topic}</title>
    <style>
        body       {{ font-family: sans-serif; max-width: 860px; margin: 40px auto; padding: 0 20px; background: #f5f5f5; color: #222; }}
        header     {{ background: #1a1a2e; color: white; padding: 28px 32px; border-radius: 10px; margin-bottom: 32px; }}
        header h1  {{ margin: 0 0 6px; font-size: 1.6rem; }}
        header p   {{ margin: 0; opacity: .7; font-size: .9rem; }}
        .card      {{ background: white; border-radius: 10px; padding: 24px 28px; margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0,0,0,.07); }}
        .card h2   {{ margin: 0 0 12px; font-size: 1.1rem; }}
        .card h2 a {{ color: #1a1a2e; text-decoration: none; }}
        .card h2 a:hover {{ text-decoration: underline; }}
        .card p    {{ margin: 0 0 16px; line-height: 1.6; color: #444; }}
        .btn       {{ display: inline-block; background: #1a1a2e; color: white; padding: 8px 16px; border-radius: 6px; text-decoration: none; font-size: .85rem; }}
        footer     {{ text-align: center; margin-top: 40px; font-size: .8rem; color: #999; }}
    </style>
</head>
<body>
    <header>
        <h1>🤖 Veille IA — {topic}</h1>
        <p>Rapport généré automatiquement le {date} • {len(articles)} articles</p>
    </header>
    {cards}
    <footer>Généré par mon agent IA 🚀</footer>
</body>
</html>"""

        filename = f"rapport_{topic.replace(' ', '_')}_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.html"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(html)
        return f"Rapport généré et sauvegardé sous le nom '{filename}' ({len(articles)} articles)."


# ==============================================================================
# Les agents crew
# ==============================================================================
#agent gestionnaire de sources
gestionnaire= Agent(
    role="gestionnaire de sources",
    goal=(
        "Gérer la liste en mémoire des sources RSS : ajouter, supprimer, mettre à jour le score et nettoyer les sources faibles."
        "consulter les meilleures sources, et après la collecte mettre à jour "
        "les scores selon la qualité des articles trouvés." 
        ),
    backstory=(
        "Tu es un gestionnaire de sources d'information."
        "Tu maintiens une liste de sources RSS pertinentes (de qualité)."
        "Tu supprime les sources obsolètes, mettre à jour le score des sources en fonction de leur pertinence et nettoyer les sources dont le score est trop bas."
    ), 
    tools=[GetSourcesTool(), AddSourceTool(), RemoveSourceTool(), UpdateSourceScoreTool(), CleanupSourcesTool()],    
    verbose=True,
    max_iter=20
)

collecteur = Agent(
    role="collecteur",
    goal="Collecter les titres et liens des derniers articles sur les agents IA  à partir de flux RSS, puis résumer chaque article et générer un rapport HTML.",
    backstory=("Tu es un expert en agent IA ."
               "Tu maîtrises la collecte d'informations à partir de flux RSS, la synthèse de contenu et la génération de rapports HTML."
               "et retourner uen liste complète et structurée."
    ), 
    tools=[FetchRssTool()],    
    verbose=True,
    max_iter=15
)

analyste = Agent(
    role="analyste IA",
    goal="Résumer chaque article en 3 phrases claires en français et ignorer les articles inaccessibles.",
    backstory=(
        "Tu es un analyste expert en agent IA ."
        "Tu lis le contenu de chaque article et tu génères un résumé clair et concis en français, en 3 phrases maximum."
        "Si un article retourne SKIP, tu l'ignores."
    ), 
    tools=[SummarizeUrlTool()],    
    verbose=True,
    max_iter=30
)

redacteur = Agent(
    role="rédacteur",
    goal="Générer un rapport HTML professionnel avec tous les articles résumés.",
    backstory=(
        "Tu es un rédacteur expert en agent IA ."
        "Tu assembles les articles résumés en un rapport HTML clair et lisible, "
        "en passant la liste complète en JSON à l'outil generate_report."
    ), 
    tools=[GenerateReportTool()],    
    verbose=True,
    max_iter=5
)

# ==============================================================================
# Les TASKS
# ==============================================================================

task_gestion = Task(
    description= (
        "1) Nettoie les sources faibles avec cleanup_sources. "
        "2) Consulte les sources mémorisées avec get_sources. "
        "3) Si aucunne source ou moins de 5 sources disponibles, cherche et ajoute avec add_source "
        "  de nouvelles sources pertinentes sur les agents IA. "
        "4) Sélectionne les 3 sources avec le meilleur score. sous forme JSON :"
        '[{"name": "...", "url": "...", "score": ...}]'        
    ),
    expected_output="Liste JSON des 3 meilleures sources avec name, url et score.",
    agent=gestionnaire
)

task_collecte= Task(
      description=(
        "À partir des sources fournies, appelle fetch_rss pour chaque URL avec limit=3. "
        "Tu dois appeler fetch_rss EXACTEMENT 3 fois."
        "Retourne la liste complète de tous les articles au format JSON : "
        '[{{"title": "...", "url": "..."}}]'
    ),
    expected_output="Une Liste Json de 09 articles avec leur titre et url",
    agent=collecteur,
    context=[task_gestion]
)

task_analyse = Task(
    description=(
        "Pour chaque article de la liste JSON, utilise summarize_article pour obtenir un résumé en 3 phrases. "
        "Retourne une nouvelle liste JSON avec les champs title, url et summary :"
         '[{{"title": "...", "url": "...", "summary": "..."}}]'
    ),
    expected_output="Une Liste Json des articles avec leur titre, url et summary",
    agent=analyste,
    context=[task_collecte]
)

task_scores = Task(
    description=(
        "Pour chaque source utilisée lors de la collecte : "
        "1) Évalue la qualité des articles trouvés (pertinence, fraîcheur). "
        "2) Appelle update_score si t'as  un score entre 1 et 10 , uen url valide et une raison. "
        "Retourne un résumé des scores mis à jour."
        "en cas de problème avec une source, tu peux lui attribuer un score plus bas et expliquer la raison (ex: 'articles peu pertinents', 'source obsolète', etc.)"
    ),
    expected_output="Résumé des scores mis à jour pour chaque source.",
    agent=gestionnaire,
    context=[task_collecte, task_analyse]  # ← reçoit articles + résumés
)

task_rapport = Task(
    description=(
        "Prends la liste JSON des articles avec leurs résumés et utilise generate_report pour créer un rapport HTML professionnel. "
        "- articles_json : la liste JSON complète des articles résumés (stringify) "
        "- topic : 'Intelligence Artificielle' "
        "Retourne le message de confirmation avec le nom du fichier généré."
    ),
    expected_output="Nom du fichier HTML généré.",
    agent=redacteur,
    context=[task_analyse]
)

# ══════════════════════════════════════════════════════════════════════════════
# CREW — l'équipe
# ══════════════════════════════════════════════════════════════════════════════

crew = Crew(
    agents=[gestionnaire, collecteur, analyste, redacteur],
    tasks=[task_gestion, task_collecte, task_analyse, task_scores, task_rapport],
    process=Process.sequential,   # séquentiel : tâche 1 → 2 → 3
    verbose=True
)


# ══════════════════════════════════════════════════════════════════════════════
# LANCEMENT
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("🚀 Démarrage de la veille IA avec CrewAI\n" + "─" * 50)
    result = crew.kickoff()
    print(f"\n✅ Mission accomplie !\n{result}")