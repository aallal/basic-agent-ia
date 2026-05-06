from datetime import date, datetime
import json
from pathlib import Path
import feedparser


SOURCES_FILE = Path("sources.json")
MAX_SOURCES = 10        # nombre max de sources mémorisées
SCORE_MIN   = 4         # score en dessous duquel une source est supprimée
# Sources par défaut au premier lancement
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

# Liste globale qui accumule les articles au fil des tours
articles_buffer = []

def store_article(title: str, url: str, summary: str) -> str:
    """Stocke un article résumé dans le buffer pour le rapport final."""
    if summary == "SKIP":
        return f"⏭ Article ignoré : {title}"
    articles_buffer.append({"title": title, "url": url, "summary": summary})
    return f"✅ Article stocké ({len(articles_buffer)} au total) : {title[:60]}"

# Charger les sources depuis le fichier sur disque
def _load_sources() -> dict:
    """Charge les sources depuis le fichier JSON, ou crée un fichier avec les sources par défaut si le fichier n'existe pas."""
    if not SOURCES_FILE.exists():
        _save_sources(SOURCES_DEFAUT)
        return SOURCES_DEFAUT
    else:
        with open(SOURCES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)


# Sauvegarder les sources dans le fichier sur disque
def _save_sources(data: dict):
    """Sauvegarde les sources dans le fichier JSON."""
    with open(SOURCES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


def get_sources() -> str:
    """Retourne la liste des sources au format JSON."""
    data = _load_sources()
    # trier les sources par score décroissant
    data["sources"].sort(key=lambda x: x["score"], reverse=True)
    return json.dumps(data, ensure_ascii=False, indent=4)


# ajouter une source
def add_source(nom: str, url: str, tags: list[str], score: int = 5) -> None:
    """Ajoute une nouvelle source à la liste des sources."""
    sources = _load_sources()
    if any(source["url"] == url for source in sources["sources"]):
        return f"La source '{nom}' existe déjà."

    # Limiter le nombre de sources mémorisées
    if len(sources["sources"]) >= MAX_SOURCES:
        # Supprimer les sources avec le score le plus bas
        sources["sources"].sort(key=lambda x: x["score"])
        while len(sources["sources"]) >= MAX_SOURCES:
            source_supprimee = sources["sources"].pop(0)
            print(f"Source supprimée pour faire de la place : {source_supprimee['name']} (score {source_supprimee['score']})")
    
    nouvelle_source = {
        "name": nom,
        "url": url,
        "tags": tags,
        "score": score,
        "articles_vus": 0,
        "derniere_utilisation": None,
    }
    sources["sources"].append(nouvelle_source)
    _save_sources(sources)
    return f"La source '{nom}' a été ajoutée avec succès avec le score {score}."

# fonction pour netoyaer les sources avec un score trop bas
def cleanup_sources(score_min: int = SCORE_MIN) -> str:
    """Supprime les sources dont le score est inférieur au seuil défini."""
    sources = _load_sources()
    sources_initiales = len(sources["sources"])
    sources["sources"] = [s for s in sources["sources"] if s["score"] >= score_min]
    sources_supprimees = sources_initiales - len(sources["sources"])
    if sources_supprimees > 0:
        _save_sources(sources)
        return f"{sources_supprimees} source(s) supprimée(s) avec un score inférieur à {score_min}."
    else:
        return "Aucune source supprimée. Toutes les sources ont un score supérieur ou égal au seuil."
# Supprimer une source
def remove_source(url: str) -> str:
    """Supprime une source de la liste des sources."""
    sources = _load_sources()
    if not any(source["url"] == url for source in sources["sources"]):
        return f"Aucune source trouvée avec l'URL '{url}'."

    sources["sources"] = [
        source for source in sources["sources"] if source["url"] != url
    ]
    _save_sources(sources)
    return f"La source avec l'URL '{url}' a été supprimée avec succès."


# Msie à jour d'un score d'une source
def update_score(url: str, nouveau_score: int, raison: str = "") -> str:
    """Met à jour le score d'une source."""
    sources = _load_sources()
    for source in sources["sources"]:
        if source["url"] == url:
            ancien_score = source["score"]
            source["score"] = nouveau_score
            source["derniere_utilisation"] = datetime.now().isoformat()
            source["articles_vus"] += 1
            _save_sources(sources)
            return f"Le score de la source '{source['name']}' a été mis à jour de {ancien_score} à {nouveau_score}. Raison : {raison}"
    return f"Aucune source trouvée avec l'URL '{url}'."


def fetch_rss(url: str, limit: int = 5) -> str:
    """Fetch the content of an RSS feed."""
    feed = feedparser.parse(url)
    articles = feed.entries[:limit]  # Limit the number of entries
    result = [{"title": e.title, "url": e.link} for e in articles]
    return json.dumps(result, ensure_ascii=False)  # Return as JSON string


# générer un rapport en html à partir d'une liste d'articles
def generate_html_report( topic: str) -> str:
    """Génère un rapport HTML à partir d'une liste d'articles."""
    # Utilise le buffer global au lieu des arguments du LLM
    articles = articles_buffer
    
    if not articles:
        return "⚠️ Aucun article dans le buffer !"
    
    
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
