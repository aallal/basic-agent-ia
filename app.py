
import json
import os
from unittest import result
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from openai import OpenAI
import requests
import tools 


# -----------------------------
# Setup OpenAI
# -----------------------------
load_dotenv()
client =  OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

MODEL_AI="gpt-4.1-mini"

def summarize_url(url: str) -> dict:
    response = requests.get(url, timeout=10 , headers={"User-Agent": "Mozilla/5.0"})        
    soup = BeautifulSoup(response.text, 'html.parser')  # Check if the content is HTML
    # get only 3000 characters of the page
    Content = soup.get_text(separator=" ", strip=True)[:3000]  

    msg = client.chat.completions.create( 
            model = MODEL_AI ,
            messages = [{"role": "user", "content": f"Résume en 3 phrases cet article:\n\n{Content}"}],
            max_tokens=300
        )
    return msg.choices[0].message.content


# -----------------------------------------------------------------
#  Définition des tools (JSON Schema)
# ----------------------------------------------------------------
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "fetch_rss",
            "description": "Récupère les titres et liens des N derniers articles d'un flux RSS.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url":   {"type": "string",  "description": "URL du flux RSS"},
                    "limit": {"type": "integer", "description": "Nombre d'articles à retourner"}
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "summarize_url",
            "description": "Télécharge une page web et retourne un résumé en 3 phrases.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL de l'article à résumer"}
                },
                "required": ["url"]
            }
        }
    }
]

TOOLS2 =[
    {
        "type": "function",
        "function": {
            "name": "fetch_url",
            "description": "Télécharge une page web et renvoie titre + texte brut.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "URL à télécharger"
                    },
                    "timeout_s": {
                        "type": "integer",
                        "description": "Délai d'attente en secondes (optionnel, par défaut 20 secondes)",
                        "default": 20
                    }
                },
                "required": ["url"],
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_time_unix",
            "description": "Obtient l'heure actuelle au format timestamp Unix.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False
            }
        }
    },
      {
        "type": "function",
        "function": {
            "name": "get_UTC_time",
            "description": "Obtient l'heure actuelle au format UTC.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False
            }
        }
    } ,
    {
        "type": "function",
        "function": {
            "name": "list_sources",
            "description": "Liste les sources actuellement suivies par l'agent.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "add_source",
            "description": "Ajoute une source à suivre pour l'agent.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "URL de la source à ajouter"
                    },
                    "kind": {
                        "type": "string",
                        "description": "Type de la source (ex: 'web', 'rss', etc.)",
                        "default": "web"
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Liste de tags pour catégoriser la source (optionnel)"
                    }
                },
                "required": ["url", "kind"],
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {   
            "name": "remove_source",
            "description": "Supprime une source de la liste de suivi de l'agent.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "URL de la source à supprimer"
                    }
                },
                "required": ["url"],
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "save_results",
            "description": "Sauvegarde les résultats de l'agent dans un fichier texte.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Chemin du fichier où sauvegarder les résultats"
                    },
                    "test": {
                        "type": "string",
                        "description": "Contenu à sauvegarder dans le fichier"
                    }
                },
                "required": ["path", "test"],
                "additionalProperties": False
            }
        }
    }



]
#fonction pour sauvegrader sur le fichier resultats.txt les résultats de l'agent
def save_results(path : str, test:str):   
    with open(path, "a", encoding="utf-8") as f:
        f.write(test + "\n")  
    return {"saved_to": path, "length": len(test)}


# -------------------------------------------------
# Router: exécuter l’outil demandé
# -------------------------------------------------
def run_tool(tool_name, tool_args:dict):
    if tool_name == "fetch_url":
        return tools.fetch_url(**tool_args)
    if tool_name == "get_time_unix":
        return tools.get_time_unix()
    if tool_name == "get_UTC_time":
        return tools.get_UTC_time()
    if tool_name == "save_results":
        return save_results(**tool_args)
    if tool_name == "list_sources":
        return tools.list_sources()
    if tool_name == "add_source":        
        return tools.add_source(**tool_args) 
    if tool_name == "remove_source":
        return tools.remove_source(**tool_args)
    if tool_name == "fetch_rss":
        return tools.fetch_rss(**tool_args)
    if tool_name == "summarize_url":
        return summarize_url(**tool_args)    
    else:
        raise ValueError(f"Tool {tool_name} inconnu")
    
# ── LA BOUCLE PRINCIPALE : Think → Act → Observe ─────────────────────────────
def run_agent2(objectif: str, max_tours: int = 10) -> str:
    print(f"\n🎯 Objectif : {objectif}\n{'─'*60}")    
    system_prompt = f"""Tu es un agent de veille qui utilise des outils pour accomplir des tâches. 
"""
    historique = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content":objectif}
        ]
    
    for tour in range(max_tours):
        print(f"\n--- Tour {tour+1} ---")
        response = client.chat.completions.create(
            model=MODEL_AI,
            messages=historique,
            tools=TOOLS,
            tool_choice="auto")
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
                    {"role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(tool_result, ensure_ascii=False)
                })
        elif response.choices[0].finish_reason == "stop":
            final = msg.content or "Aucune réponse de l'agent."
            print(f"\n✅ Réponse finale :\n{final}")
            return final
    
    return "Nombre maximum de tours atteint sans que l'agent ne termine sa mission."
# -------------------------------------------------
#  Boucle tool-calling (max N tours)
# -------------------------------------------------
def run_agent(user_input:str, max_turns:int = 5) -> str:
    system_prompt = f"""Tu es un agent de veille qui utilise des outils pour accomplir des tâches. 
Ta mission : Mainteneir entre 5 et 15 sources de qualité.
Règles :
- Utilise les outils disponibles pour accomplir ta mission.
- Commence par appeler  list_sources pour voir les sources actuelles.
- Si tu as besoin d'ajouter une source (moins de 5 sources ), ajoute des sources peretinentes
- Si tu as besoin de supprimer une source (plus de 15 sources), supprime les moins pertientes.
- Evite les doublons et les sources de mauvaise qualité.
- A la fin résume les actions avec sources ajoutées, supprimées et la liste finale des sources.
"""
    historique = [
        {"role": "system", "content": system_prompt.strip()},
        {"role": "user", "content":user_input.strip()}
        ]
    
    for tour in range(max_turns):
        print(f"\n--- Tour {tour+1} ---")
        response = client.chat.completions.create(
            model=MODEL_AI,
            messages=historique,
            tools=TOOLS,
            tool_choice="auto")
        msg = response.choices[0].message
        historique.append(msg)
        # si pas de tool_calls, c'est que l'agent a fini
        if not msg.tool_calls:
            print("Agent a terminé sa mission.")
            return msg.content or "Aucune réponse de l'agent."
        # executer les outils appelés
        for tool_call in msg.tool_calls:
            tool_name = tool_call.function.name
            tool_args = json.loads(tool_call.function.arguments)
            tool_result = run_tool(tool_name, tool_args)
            historique.append(
                {"role": "tool",
                 "tool_call_id": tool_call.id,
                 "content": json.dumps(tool_result, ensure_ascii=False)
                 })
    return "Nombre maximum de tours atteint sans que l'agent ne termine sa mission."
#---------------------------------------------------------------------------------------

# ── LANCEMENT ─────────────────────────────────────────────────────────────────
def main2():
    run_agent2(
        "Récupère les 3 derniers articles du flux https://hnrss.org/frontpage "
        "et donne-moi un résumé de chacun en français."
    )

# main fonction pour executer l'agent  -----------------------------------------------
def main():
    print("Lancement de l'agent de veille...")
    print("Tape uen demande ou quit pour arrêter l'agent.\n")

    while True:
        user_input = input("Votre demande > ").strip()
        if user_input.lower() in ["quit", "exit"]:
            print("Arrêt de l'agent. Au revoir !")
            break
        resultat = run_agent(user_input)
        print("\nRésultat de l'agent >\n")
        print(resultat)
        print("\n" + "="*80 + "\n")
#---------------------------------------------------------------------------------------
#     
def main_old():
    # prompt pour l'agent
    prompt2 = "Va lire cette page et résume en 5 points : https://developers.openai.com/api/docs/guides/function-calling"
    prompt = "Va lire l'heure actuelle au format UTC"
    prompt3 ="Lis ces deux pages : https://developers.openai.com/api/docs/guides/migrate-to-responses et https://developers.openai.com/api/docs/guides/function-calling, puis compare-les en 3 à 6 lignes : thème, public cible, points clés, limites. "
    
    system_prompt = "Tu es un agent de veille qui utilise des outils pour accomplir des tâches. Utilise les outils disponibles pour répondre à la demande de l'utilisateur."    
    # appeler l'agent openIA avec le prompt et les outils
    my_messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt3}
        ]
    
    
    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=my_messages,
        tools=TOOLS,
        tool_choice="auto",
    )
    msg = response.choices[0].message
    my_messages.append(msg)

    print("Agent response:", msg.content)    
    
    # si l'agent a choisi un outil, exécuter l'outil et afficher le résultat
    if msg.tool_calls:
        for tool_call in msg.tool_calls:
            tool_name = tool_call.function.name
            stool_args = tool_call.function.arguments
            tool_args=  json.loads(stool_args)
            print(f"Agent a choisi d'exécuter l'outil {tool_name} avec les arguments {tool_args}")
            tool_result = run_tool(tool_name, tool_args)

           # print(f"Résultat de l'outil {tool_name}:", tool_result)
            my_messages.append({"role": "tool","tool_call_id": tool_call.id,
                                 "content": json.dumps(tool_result, ensure_ascii=False)})
            
        #deuxième appel de l'agent après l'exécution de l'outil
        response2 = client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=my_messages,
                tools=TOOLS)   
            # tester s'il y a réponse de l'agent après l'exécution de l'outil   

        print("Agent response après exécution de l'outil:", response2.choices[0].message.content)
        save_results("resultats.txt", response2.choices[0].message.content)
    else:
        print("L'agent n'a pas choisi d'exécuter d'outil.")
        print(msg.content)
if __name__ == "__main__":
    main2()  
