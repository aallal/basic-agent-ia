from datetime import datetime, timezone, timedelta
from http import client
import feedparser
import json
from urllib.parse import urlparse
from bs4 import BeautifulSoup
import requests
import time

from store import load_state, save_state

MODEL_AI="gpt-4.1-mini"

#ajouter une fonction get_time_unix pour l'outil get_time_unix

def get_time_unix():
    """Get the current time in Unix timestamp format."""
    return int(time.time())

def get_UTC_time():
    """Get the current time in UTC datetime ."""
    ts = int(time.time())
    utc_dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    return utc_dt.isoformat()

def fetch_rss(url: str, limit : int = 5 ) -> str:
    """Fetch the content of an RSS feed."""
    feed = feedparser.parse(url)
    articles = feed.entries[:limit]  # Limit the number of entries
    result = [{"title": e.title, "link": e.link} for e in articles]
    return  json.dumps(result, ensure_ascii=False)  # Return as JSON string


def fetch_url(url: str, timeout: int = 20) -> dict:
    """Fetch the content of a URL."""
    try:
        response = requests.get(url, timeout=timeout , headers={"User-Agent": "Mozilla/5.0"}   )
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')  # Check if the content is HTML
        # get titile of the page
        title = soup.title.string if soup.title else 'No title found'
        # get only 3000 characters of the page
        Content = soup.get_text(separator=" ", strip=True)[:3000]  
        return {"url": url, "title": title, "text": Content}
    except requests.RequestException as e:
        return {"url": url, "title": None, "text": None, "error": str(e)}
        

def _norm_url(url: str) -> str:
    url = url.strip()
    return url.rstrip("/")

def  list_sources() -> dict:
    state = load_state()
    sources = state.get("sources", [])
    return {"sources": sources , "count": len(sources)}

#add source to the state
def add_source(url: str, kind :str ="web", tags: list[str] | None = None) -> dict:
    tags = tags or []
    state = load_state()
    sources = state.get("sources", [])
    url = _norm_url(url)

    #vérifier si url existe déjà dans les sources
    if any(s.get("url") == url for s in sources):
        return {"added": False , "reason": "Source_already_exists", "url": url}

    #ajout 
    domain = urlparse(url).netloc
    sources.append(
        {"url": url, 
         "kind": kind, 
         "tags": tags,
         "domain": domain}
        )

    save_state(state)
    return {"added": True, "url": url, "kind": kind, "tags": tags, "count": len(sources)}

#fonction pour deleter une source de la liste des sources
def remove_source(url: str) -> dict:
    state = load_state()
    sources = state.get("sources", [])
    size_before = len(sources)
    url = _norm_url(url)
    #supprimer la source
    sources = [s for s in sources if s["url"] != url]
    size_after = len(sources)

    state["sources"] = sources
    save_state(state)
    return {"removed": size_before != size_after, "url": url, "count": size_after}

    