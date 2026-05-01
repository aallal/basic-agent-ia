

import json
from pathlib import Path


STATE_PATH = Path("state.json")

def load_state() ->dict:
    """Charge l'état de l'agent depuis un fichier JSON."""
    try:
        with open(STATE_PATH, "r" , encoding="utf-8") as f:
            return  json.load(f)
    except :
        return {"topics": [], "sources": [], "seen_links": []}
    
def save_state(state: dict) -> None:
    """Sauvegarde l'état de l'agent dans un fichier JSON."""
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)    
