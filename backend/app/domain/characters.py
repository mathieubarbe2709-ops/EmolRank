"""Personnages Smash Ultimate : normalisation des noms start.gg vers les icônes fournies."""
from __future__ import annotations

import re
import unicodedata

# clé d'icône (nom du fichier PNG sans extension) -> nom affiché
CHARACTERS: dict[str, str] = {
    "banjo_and_kazooie": "Banjo & Kazooie", "bayonetta": "Bayonetta", "bowser": "Bowser",
    "bowser_jr": "Bowser Jr.", "byleth": "Byleth", "captain_falcon": "Captain Falcon",
    "chrom": "Chrom", "cloud": "Cloud", "corrin": "Corrin", "daisy": "Daisy",
    "dark_pit": "Dark Pit", "dark_samus": "Dark Samus", "diddy_kong": "Diddy Kong",
    "donkey_kong": "Donkey Kong", "dq_hero": "Héros", "dr_mario": "Dr. Mario",
    "duck_hunt": "Duck Hunt", "falco": "Falco", "fox": "Fox", "ganondorf": "Ganondorf",
    "gaogaen": "Incineroar", "greninja": "Greninja", "homura": "Pyra / Mythra",
    "ice_climbers": "Ice Climbers", "ike": "Ike", "inkling": "Inkling", "isabelle": "Isabelle",
    "jigglypuff": "Rondoudou", "joker": "Joker", "kazuya": "Kazuya", "ken": "Ken",
    "king_dedede": "King Dedede", "king_k_rool": "King K. Rool", "kirby": "Kirby",
    "link": "Link", "little_mac": "Little Mac", "lucario": "Lucario", "lucas": "Lucas",
    "lucina": "Lucina", "luigi": "Luigi", "mario": "Mario", "marth": "Marth",
    "mega_man": "Mega Man", "meta_knight": "Meta Knight", "mewtwo": "Mewtwo",
    "mii_fighter": "Mii", "minmin": "Min Min", "mr_game_and_watch": "Mr. Game & Watch",
    "ness": "Ness", "olimar": "Olimar", "pac_man": "Pac-Man", "packun_flower": "Plante Piranha",
    "palutena": "Palutena", "peach": "Peach", "pichu": "Pichu", "pikachu": "Pikachu",
    "pit": "Pit", "pokemon_trainer": "Dresseur de Pokémon", "richter": "Richter",
    "ridley": "Ridley", "rob": "R.O.B.", "robin": "Daraen", "rosalina_and_luma": "Harmonie & Luma",
    "roy": "Roy", "ryu": "Ryu", "samus": "Samus", "sephiroth": "Sephiroth", "sheik": "Sheik",
    "shulk": "Shulk", "simon": "Simon", "snake": "Snake", "sonic": "Sonic", "sora": "Sora",
    "steve": "Steve", "terry": "Terry", "toon_link": "Link Cartoon", "villager": "Villageois",
    "wario": "Wario", "wii_fit_trainer": "Entraîneuse Wii Fit", "wolf": "Wolf", "yoshi": "Yoshi",
    "young_link": "Link Jeune", "zelda": "Zelda", "zero_suit_samus": "Samus Zéro",
}

# Noms alternatifs (déjà normalisés) rencontrés sur start.gg -> clé d'icône
ALIASES: dict[str, str] = {
    "hero": "dq_hero", "dragon_quest_hero": "dq_hero", "pyra_mythra": "homura", "pyra": "homura",
    "mythra": "homura", "pyra_and_mythra": "homura", "r_o_b": "rob", "rob": "rob",
    "mii_brawler": "mii_fighter", "mii_swordfighter": "mii_fighter", "mii_gunner": "mii_fighter",
    "mii": "mii_fighter", "incineroar": "gaogaen", "piranha_plant": "packun_flower",
    "terry_bogard": "terry", "min_min": "minmin", "pokemon_trainer": "pokemon_trainer",
    "squirtle": "pokemon_trainer", "ivysaur": "pokemon_trainer", "charizard": "pokemon_trainer",
    "rosalina_luma": "rosalina_and_luma", "rosalina": "rosalina_and_luma",
    "banjo_kazooie": "banjo_and_kazooie", "game_and_watch": "mr_game_and_watch",
    "mr_game_watch": "mr_game_and_watch", "pikmin_and_olimar": "olimar", "pikmin_olimar": "olimar",
    "captain_falcon": "captain_falcon", "bowser_junior": "bowser_jr", "king_k_rool": "king_k_rool",
    "mega_man": "mega_man", "megaman": "mega_man", "pacman": "pac_man", "dr_mario": "dr_mario",
    "doctor_mario": "dr_mario", "wii_fit": "wii_fit_trainer", "ice_climber": "ice_climbers",
    "robin": "robin", "daraen": "robin", "lucina": "lucina", "metaknight": "meta_knight",
}


def _normalize(name: str) -> str:
    text = unicodedata.normalize("NFKD", name)
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return text


def character_key(name: str | None) -> str | None:
    """Clé stable pour un nom de personnage (None si le nom est vide).

    Un nom inconnu conserve sa forme normalisée : il sera compté mais sans icône.
    """
    if not name or not name.strip():
        return None
    norm = _normalize(name)
    if norm in CHARACTERS:
        return norm
    return ALIASES.get(norm, norm)


def character_label(key: str, raw_name: str | None = None) -> str:
    if key in CHARACTERS:
        return CHARACTERS[key]
    return raw_name or key.replace("_", " ").title()


def has_icon(key: str) -> bool:
    return key in CHARACTERS
