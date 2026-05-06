import json
import os
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from openai import OpenAI
import requests

import agent_tools as tools

# -----------------------------
# Setup OpenAI
# -----------------------------

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

MODEL_AI = "gpt-4.1-mini"

# ══════════════════════════════════════════════════════════════════════════════
# OUTILS DÉCLARÉS POUR LE LLM
# ══════════════════════════════════════════════════════════════════════════════
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "fetch_rss",
            "description": "Récupère les titres et liens des N derniers articles d'un flux RSS.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL du flux RSS"},
                    "limit": {
                        "type": "integer",
                        "description": "Nombre d'articles à retourner",
                    },
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "summarize_url",
            "description": "Télécharge une page web et retourne un résumé en 3 phrases.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "URL de l'article à résumer",
                    }
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_html_report",
            "description": "Génère un rapport HTML avec les articles résumés et le sauvegarde sur disque.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "Sujet de la veille"},
                },
                "required": ["topic"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_sources",
            "description": "Retourne toutes les sources RSS mémorisées avec leurs scores de pertinence.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_source",
            "description": "Ajoute une nouvelle source RSS à la mémoire persistante.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Nom lisible de la source",
                    },
                    "url": {"type": "string", "description": "URL du flux RSS"},
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Tags thématiques",
                    },
                    "score": {
                        "type": "integer",
                        "description": "Score initial de pertinence (1-10)",
                    },
                },
                "required": ["name", "url", "tags"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remove_source",
            "description": "Supprime une source RSS jugée non pertinente.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "URL de la source à supprimer",
                    }
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_score",
            "description": "Met à jour le score de pertinence d'une source (1 à 10).",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL de la source"},
                    "nouveau_score": {
                        "type": "integer",
                        "description": "Nouveau score (1-10)",
                    },
                    "raison": {
                        "type": "string",
                        "description": "Raison de la mise à jour",
                    },
                },
                "required": ["url", "nouveau_score"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "store_article",
            "description": "Stocke un article résumé dans le buffer pour inclusion dans le rapport final. À appeler après chaque summarize_url réussi.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Titre de l'article"},
                    "url": {"type": "string", "description": "URL de l'article"},
                    "summary": {"type": "string", "description": "Résumé de l'article"},
                },
                "required": ["title", "url", "summary"],
            },
        },
    },
]


# ══════════════════════════════════════════════════════════════════════════════
# OUTILS Utilisant cleint OpenAI
# ══════════════════════════════════════════════════════════════════════════════
# Résumer un article à partir de son URL
def summarize_url(url: str) -> str:
    try:
        response = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(
            response.text, "html.parser"
        )  # Check if the content is HTML
        # get only 3000 characters of the page
        Content = soup.get_text(separator=" ", strip=True)[:3000]
        if len(Content) < 100:  # page vide ou inaccessible
            return "SKIP"

    except requests.RequestException as e:
        print(f"Error fetching URL {url}: {e}")
        return "SKIP"

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


# ══════════════════════════════════════════════════════════════════════════════
# ROUTEUR D'OUTILS
# ══════════════════════════════════════════════════════════════════════════════
def run_tool(tool_name: str, inputs: dict) -> str:
    """Exécute un outil en fonction de son nom."""
    routes = {
        "summarize_url": summarize_url,
        "fetch_rss": tools.fetch_rss,
        "generate_html_report": tools.generate_html_report,
        "get_sources": lambda **kwargs: tools.get_sources(),
        "add_source": tools.add_source,
        "remove_source": tools.remove_source,
        "update_score": tools.update_score,
        "store_article": tools.store_article,
    }
    fn = routes.get(tool_name)
    if fn:
        return fn(**inputs)
    return f"Outil '{tool_name}' non trouvé."


# ══════════════════════════════════════════════════════════════════════════════
# BOUCLE PRINCIPALE : Think → Act → Observe
# ══════════════════════════════════════════════════════════════════════════════
def run_agent(objectif: str, max_tours: int = 10) -> str:
    print(f"\n🎯 Objectif : {objectif}\n{'─'*60}")

    # Nettoyage automatique avant chaque session
    print("\n🧹 Nettoyage des sources...")
    print(f"    {tools.cleanup_sources()}")

    system_prompt = f"""Tu es un agent de veille qui utilise des outils pour accomplir des tâches. 
Tu as accès à une mémoire persistante de sources RSS avec des scores de pertinence (1-10).
À chaque session : 
    1) consulte tes sources mémorisées,
    2) priorise celles avec le meilleur score,
    3) après avoir lu les articles, mets à jour les scores selon la pertinence,
    4) génère un rapport HTML final.
IMPORTANT : si summarize_url retourne 'SKIP', ignore cet article 
et passe au suivant — ne l'inclus pas dans le rapport.     
Sois autonome dans tes décisions."    
"""
    historique = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": objectif},
    ]

    for tour in range(max_tours):
        print(f"\n--- Tour {tour+1} ---")
        response = client.chat.completions.create(
            model=MODEL_AI, messages=historique, tools=TOOLS, tool_choice="auto"
        )
        msg = response.choices[0].message
        print(f"   Stop reason : {response.choices[0].finish_reason}")
        if response.choices[0].finish_reason == "tool_calls":
            historique.append(msg)
            # executer les outils appelés
            for tool_call in msg.tool_calls:
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments)
                print(f"   ⚡ ACT → {tool_name}({tool_args})")
                tool_result = run_tool(tool_name, tool_args)
                print(f"   👁 OBSERVE → {tool_result[:100]}...")
                # Injecter le résultat dans le contexte
                historique.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": tool_result,  # json.dumps(tool_result, ensure_ascii=False)
                    }
                )
        elif response.choices[0].finish_reason == "stop":
            final = msg.content or "Aucune réponse de l'agent."
            print(f"\n✅ Réponse finale :\n{final}")
            return final

    return "Nombre maximum de tours atteint sans que l'agent ne termine sa mission."


# ══════════════════════════════════════════════════════════════════════════════
# LANCEMENT
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    run_agent(
        """Fais une rechereche  sur les agents d'intelligence artificielle.
Voici les étapes OBLIGATOIRES que tu dois suivre dans l'ordre :
1) Consulte tes sources mémorisées avec get_sources.
2) Sélectionne EXACTEMENT 3 sources avec le meilleur score.
3) Pour chaque source, appelle fetch_rss et récupère EXACTEMENT 3 articles.
Tu dois donc appeler fetch_rss 3 fois, une fois par source. "
4) Pour chaque article récupéré, appelle summarize_url puis store_article immédiatement.
Si le résultat de summarize_url est SKIP, ignore-le mais continue.
Tu dois avoir au minimum 9 résumés au total (3 sources x 3 articles). 
5) Mets à jour les scores des sources avec update_score. 
6) Génère un rapport HTML avec generate_report lorsqu'on a 9 articles stockés. 
"""
    )
