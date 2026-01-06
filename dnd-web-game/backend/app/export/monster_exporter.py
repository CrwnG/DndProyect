"""
Monster Exporter for Foundry VTT.

Converts our monster JSON format to Foundry VTT dnd5e system Actor format.
"""

from typing import Dict, List, Any, Optional
from pathlib import Path
import json

from .utils import (
    generate_foundry_id,
    convert_to_html,
    parse_damage_dice,
    parse_attack_bonus,
    parse_save_dc,
    parse_reach_or_range,
    parse_cr,
    get_xp_for_cr,
    SIZE_MAP,
    TOKEN_SIZE_SCALE,
    DAMAGE_TYPE_MAP,
)


class MonsterExporter:
    """Converts our monster JSON to Foundry VTT dnd5e Actor format."""

    def __init__(self):
        """Initialize the exporter."""
        self._data_path = self._get_data_path()

    def _get_data_path(self) -> Path:
        """Get the path to the monster data directory."""
        current_dir = Path(__file__).parent
        return current_dir.parent / "data" / "rules" / "2024" / "monsters"

    def load_all_monsters(self) -> List[Dict]:
        """Load all monsters from JSON files."""
        monsters = []

        if not self._data_path.exists():
            print(f"Monster data path not found: {self._data_path}")
            return monsters

        for filepath in self._data_path.glob("*.json"):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Each file has a "monsters" array
                    if "monsters" in data:
                        for monster in data["monsters"]:
                            monster["_source_file"] = filepath.stem
                            monsters.append(monster)
            except (json.JSONDecodeError, FileNotFoundError) as e:
                print(f"Error loading {filepath}: {e}")

        return monsters

    def export(self, our_monster: Dict) -> Dict:
        """
        Convert a single monster to Foundry VTT Actor format.

        Args:
            our_monster: Our monster data dictionary

        Returns:
            Foundry VTT Actor document
        """
        monster_id = our_monster.get("id", "unknown")

        return {
            "_id": generate_foundry_id(monster_id, "monster_"),
            "name": our_monster.get("name", "Unknown Monster"),
            "type": "npc",
            "img": "icons/svg/mystery-man.svg",  # Default placeholder
            "system": {
                "abilities": self._convert_abilities(our_monster),
                "attributes": self._convert_attributes(our_monster),
                "details": self._convert_details(our_monster),
                "traits": self._convert_traits(our_monster),
                "skills": self._convert_skills(our_monster),
                "bonuses": self._get_default_bonuses(),
                "resources": self._get_default_resources(),
            },
            "items": self._convert_to_items(our_monster),
            "effects": [],
            "prototypeToken": self._create_token(our_monster),
            "flags": {
                "dnd-web-game": {
                    "sourceId": monster_id,
                    "exportVersion": "1.0.0"
                }
            }
        }

    def _convert_abilities(self, monster: Dict) -> Dict:
        """Convert ability scores to Foundry format."""
        scores = monster.get("ability_scores", {})

        def make_ability(value: int) -> Dict:
            mod = (value - 10) // 2
            return {
                "value": value,
                "mod": mod,
                "save": mod,  # Base save (no proficiency)
                "proficient": 0,
            }

        return {
            "str": make_ability(scores.get("STR", 10)),
            "dex": make_ability(scores.get("DEX", 10)),
            "con": make_ability(scores.get("CON", 10)),
            "int": make_ability(scores.get("INT", 10)),
            "wis": make_ability(scores.get("WIS", 10)),
            "cha": make_ability(scores.get("CHA", 10)),
        }

    def _convert_attributes(self, monster: Dict) -> Dict:
        """Convert AC, HP, movement, etc. to Foundry format."""
        speed = monster.get("speed", {})

        # Handle speed as int or dict
        if isinstance(speed, int):
            speed = {"walk": speed}

        # Parse hit dice
        hit_dice = monster.get("hit_dice", "1d8")
        hit_points = monster.get("hit_points", 1)

        return {
            "ac": {
                "flat": monster.get("armor_class", 10),
                "calc": "flat",
                "formula": "",
            },
            "hp": {
                "value": hit_points,
                "max": hit_points,
                "temp": 0,
                "tempmax": 0,
                "formula": hit_dice,
            },
            "init": {
                "ability": "dex",
                "bonus": 0,
            },
            "movement": {
                "burrow": speed.get("burrow", 0),
                "climb": speed.get("climb", 0),
                "fly": speed.get("fly", 0),
                "swim": speed.get("swim", 0),
                "walk": speed.get("walk", 30),
                "units": "ft",
                "hover": speed.get("hover", False),
            },
            "senses": self._convert_senses(monster),
            "spellcasting": "",
            "exhaustion": 0,
            "concentration": {
                "ability": "con",
                "limit": 1,
            },
        }

    def _convert_senses(self, monster: Dict) -> Dict:
        """Convert senses to Foundry format."""
        senses = monster.get("senses", {})

        # Parse special senses from description if provided as string
        result = {
            "darkvision": 0,
            "blindsight": 0,
            "tremorsense": 0,
            "truesight": 0,
            "units": "ft",
            "special": "",
        }

        if isinstance(senses, dict):
            result["darkvision"] = senses.get("darkvision", 0)
            result["blindsight"] = senses.get("blindsight", 0)
            result["tremorsense"] = senses.get("tremorsense", 0)
            result["truesight"] = senses.get("truesight", 0)

        return result

    def _convert_details(self, monster: Dict) -> Dict:
        """Convert CR, type, alignment, etc. to Foundry format."""
        cr = parse_cr(monster.get("challenge_rating", 0))
        xp = monster.get("xp", get_xp_for_cr(cr))

        # Parse creature type
        creature_type = monster.get("type", "monstrosity")
        subtype = ""
        if "(" in creature_type:
            parts = creature_type.split("(")
            creature_type = parts[0].strip()
            subtype = parts[1].rstrip(")").strip()

        return {
            "biography": {
                "value": convert_to_html(monster.get("description", ""), convert_dice=False),
                "public": "",
            },
            "alignment": monster.get("alignment", ""),
            "race": "",
            "type": {
                "value": creature_type.lower().split()[0],  # Get first word
                "subtype": subtype,
                "swarm": "",
                "custom": "",
            },
            "environment": "",
            "cr": cr,
            "spellLevel": 0,
            "xp": {
                "value": xp,
            },
            "source": monster.get("_source_file", "D&D Web Game"),
            "ideal": "",
            "bond": "",
            "flaw": "",
        }

    def _convert_traits(self, monster: Dict) -> Dict:
        """Convert size, languages, resistances, immunities to Foundry format."""
        size = monster.get("size", "Medium")
        size_key = SIZE_MAP.get(size.lower(), "med")

        # Process damage immunities, resistances, vulnerabilities
        di = monster.get("damage_immunities", [])
        dr = monster.get("damage_resistances", [])
        dv = monster.get("damage_vulnerabilities", [])
        ci = monster.get("condition_immunities", [])

        # Normalize to lowercase
        if isinstance(di, list):
            di = [d.lower() for d in di]
        if isinstance(dr, list):
            dr = [d.lower() for d in dr]
        if isinstance(dv, list):
            dv = [d.lower() for d in dv]
        if isinstance(ci, list):
            ci = [c.lower() for c in ci]

        return {
            "size": size_key,
            "di": {
                "value": di if isinstance(di, list) else [],
                "custom": "",
            },
            "dr": {
                "value": dr if isinstance(dr, list) else [],
                "custom": "",
            },
            "dv": {
                "value": dv if isinstance(dv, list) else [],
                "custom": "",
            },
            "ci": {
                "value": ci if isinstance(ci, list) else [],
                "custom": "",
            },
            "languages": {
                "value": monster.get("languages", []),
                "custom": "",
            },
        }

    def _convert_skills(self, monster: Dict) -> Dict:
        """Convert skills to Foundry format."""
        skills = monster.get("skills", {})
        result = {}

        # Map our skill names to Foundry skill keys
        skill_map = {
            "acrobatics": "acr",
            "animal handling": "ani",
            "arcana": "arc",
            "athletics": "ath",
            "deception": "dec",
            "history": "his",
            "insight": "ins",
            "intimidation": "itm",
            "investigation": "inv",
            "medicine": "med",
            "nature": "nat",
            "perception": "prc",
            "performance": "prf",
            "persuasion": "per",
            "religion": "rel",
            "sleight of hand": "slt",
            "stealth": "ste",
            "survival": "sur",
        }

        for skill_name, bonus in skills.items():
            foundry_key = skill_map.get(skill_name.lower())
            if foundry_key and isinstance(bonus, (int, float)):
                result[foundry_key] = {
                    "value": 1,  # Proficient
                    "ability": "dex",  # Default, could be inferred
                    "bonuses": {
                        "check": "",
                        "passive": "",
                    },
                    "total": int(bonus),
                }

        return result

    def _get_default_bonuses(self) -> Dict:
        """Get default bonus structure for Foundry."""
        return {
            "mwak": {"attack": "", "damage": ""},
            "rwak": {"attack": "", "damage": ""},
            "msak": {"attack": "", "damage": ""},
            "rsak": {"attack": "", "damage": ""},
            "abilities": {"check": "", "save": "", "skill": ""},
            "spell": {"dc": ""},
        }

    def _get_default_resources(self) -> Dict:
        """Get default resources structure."""
        return {
            "legact": {"value": 0, "max": 0},
            "legres": {"value": 0, "max": 0},
            "lair": {"value": False, "initiative": 20},
        }

    def _convert_to_items(self, monster: Dict) -> List[Dict]:
        """Convert actions and traits to Foundry Item documents."""
        items = []

        # Convert traits to feature items
        for trait in monster.get("traits", []):
            items.append(self._trait_to_item(trait, monster.get("id", "unknown")))

        # Convert actions to weapon/attack items
        for action in monster.get("actions", []):
            items.append(self._action_to_item(action, monster.get("id", "unknown")))

        # Convert legendary actions if present
        for legendary in monster.get("legendary_actions", []):
            items.append(self._legendary_to_item(legendary, monster.get("id", "unknown")))

        # Convert reactions if present
        for reaction in monster.get("reactions", []):
            items.append(self._reaction_to_item(reaction, monster.get("id", "unknown")))

        return items

    def _trait_to_item(self, trait: Dict, parent_id: str) -> Dict:
        """Convert a monster trait to Foundry feature Item."""
        trait_name = trait.get("name", "Trait")
        description = trait.get("description", trait.get("desc", ""))

        return {
            "_id": generate_foundry_id(f"{parent_id}_trait_{trait_name}"),
            "name": trait_name,
            "type": "feat",
            "img": "icons/svg/book.svg",
            "system": {
                "description": {
                    "value": convert_to_html(description),
                },
                "source": "",
                "activation": {
                    "type": "",
                    "cost": None,
                    "condition": "",
                },
                "duration": {
                    "value": None,
                    "units": "",
                },
                "cover": None,
                "target": {
                    "value": None,
                    "width": None,
                    "units": "",
                    "type": "",
                },
                "range": {
                    "value": None,
                    "long": None,
                    "units": "",
                },
                "uses": {
                    "value": None,
                    "max": "",
                    "per": None,
                    "recovery": "",
                },
                "consume": {
                    "type": "",
                    "target": None,
                    "amount": None,
                },
                "ability": None,
                "actionType": "",
                "attackBonus": "",
                "chatFlavor": "",
                "critical": {
                    "threshold": None,
                    "damage": "",
                },
                "damage": {
                    "parts": [],
                    "versatile": "",
                },
                "formula": "",
                "save": {
                    "ability": "",
                    "dc": None,
                    "scaling": "spell",
                },
                "type": {
                    "value": "monster",
                    "subtype": "",
                },
                "requirements": "",
                "recharge": {
                    "value": None,
                    "charged": True,
                },
            },
            "effects": [],
            "flags": {},
        }

    def _action_to_item(self, action: Dict, parent_id: str) -> Dict:
        """Convert a monster action to Foundry weapon/attack Item."""
        action_name = action.get("name", "Attack")
        description = action.get("description", action.get("desc", ""))

        # Determine action type and parse attack data
        is_melee = "melee" in description.lower()
        is_ranged = "ranged" in description.lower()
        is_weapon = "weapon attack" in description.lower()
        is_spell = "spell attack" in description.lower()

        # Parse attack bonus
        attack_bonus = parse_attack_bonus(description)

        # Parse damage
        damage_parts = []
        damages = parse_damage_dice(description)
        for dice, damage_type in damages:
            foundry_type = DAMAGE_TYPE_MAP.get(damage_type.lower(), damage_type.lower())
            damage_parts.append([dice, foundry_type])

        # Parse reach/range
        reach, long_range = parse_reach_or_range(description)

        # Parse save DC if present
        save_dc, save_ability = parse_save_dc(description)

        # Determine item type and action type
        if is_weapon or is_spell:
            item_type = "weapon"
            if is_melee:
                action_type = "msak" if is_spell else "mwak"
            else:
                action_type = "rsak" if is_spell else "rwak"
        else:
            item_type = "feat"
            action_type = "save" if save_dc else ""

        return {
            "_id": generate_foundry_id(f"{parent_id}_action_{action_name}"),
            "name": action_name,
            "type": item_type,
            "img": "icons/svg/sword.svg" if is_melee else "icons/svg/target.svg",
            "system": {
                "description": {
                    "value": convert_to_html(description),
                },
                "source": "",
                "quantity": 1,
                "weight": 0,
                "price": {"value": 0, "denomination": "gp"},
                "attunement": 0,
                "equipped": True,
                "rarity": "",
                "identified": True,
                "activation": {
                    "type": "action",
                    "cost": 1,
                    "condition": "",
                },
                "duration": {
                    "value": None,
                    "units": "",
                },
                "cover": None,
                "target": {
                    "value": 1,
                    "width": None,
                    "units": "",
                    "type": "creature",
                },
                "range": {
                    "value": reach or 5,
                    "long": long_range,
                    "units": "ft",
                },
                "uses": {
                    "value": None,
                    "max": "",
                    "per": None,
                    "recovery": "",
                },
                "consume": {
                    "type": "",
                    "target": None,
                    "amount": None,
                },
                "ability": "str" if is_melee else "dex",
                "actionType": action_type,
                "attackBonus": str(attack_bonus) if attack_bonus else "",
                "chatFlavor": "",
                "critical": {
                    "threshold": None,
                    "damage": "",
                },
                "damage": {
                    "parts": damage_parts,
                    "versatile": "",
                },
                "formula": "",
                "save": {
                    "ability": save_ability or "",
                    "dc": save_dc,
                    "scaling": "flat" if save_dc else "spell",
                },
                "armor": {"value": 0},
                "hp": {"value": 0, "max": 0, "dt": None, "conditions": ""},
                "weaponType": "natural",
                "baseItem": "",
                "properties": {},
                "proficient": True,
            },
            "effects": [],
            "flags": {},
        }

    def _legendary_to_item(self, legendary: Dict, parent_id: str) -> Dict:
        """Convert a legendary action to Foundry Item."""
        name = legendary.get("name", "Legendary Action")
        description = legendary.get("description", legendary.get("desc", ""))
        cost = legendary.get("cost", 1)

        return {
            "_id": generate_foundry_id(f"{parent_id}_legendary_{name}"),
            "name": f"{name} (Costs {cost} Actions)" if cost > 1 else name,
            "type": "feat",
            "img": "icons/svg/lightning.svg",
            "system": {
                "description": {
                    "value": convert_to_html(description),
                },
                "activation": {
                    "type": "legendary",
                    "cost": cost,
                    "condition": "",
                },
                "type": {
                    "value": "monster",
                    "subtype": "legendary",
                },
            },
            "effects": [],
            "flags": {},
        }

    def _reaction_to_item(self, reaction: Dict, parent_id: str) -> Dict:
        """Convert a reaction to Foundry Item."""
        name = reaction.get("name", "Reaction")
        description = reaction.get("description", reaction.get("desc", ""))

        return {
            "_id": generate_foundry_id(f"{parent_id}_reaction_{name}"),
            "name": name,
            "type": "feat",
            "img": "icons/svg/hazard.svg",
            "system": {
                "description": {
                    "value": convert_to_html(description),
                },
                "activation": {
                    "type": "reaction",
                    "cost": 1,
                    "condition": "",
                },
                "type": {
                    "value": "monster",
                    "subtype": "",
                },
            },
            "effects": [],
            "flags": {},
        }

    def _create_token(self, monster: Dict) -> Dict:
        """Create prototype token settings for the monster."""
        size = monster.get("size", "Medium")
        size_key = SIZE_MAP.get(size.lower(), "med")
        scale = TOKEN_SIZE_SCALE.get(size_key, 1)

        return {
            "name": monster.get("name", "Unknown"),
            "displayName": 20,  # OWNER_HOVER
            "actorLink": False,
            "appendNumber": True,
            "prependAdjective": False,
            "width": scale,
            "height": scale,
            "texture": {
                "src": "icons/svg/mystery-man.svg",
                "scaleX": 1,
                "scaleY": 1,
                "offsetX": 0,
                "offsetY": 0,
                "rotation": 0,
            },
            "hexagonalShape": 0,
            "lockRotation": False,
            "rotation": 0,
            "alpha": 1,
            "disposition": -1,  # HOSTILE
            "displayBars": 20,  # OWNER_HOVER
            "bar1": {"attribute": "attributes.hp"},
            "bar2": {"attribute": ""},
            "light": {
                "alpha": 0.5,
                "angle": 360,
                "bright": 0,
                "color": None,
                "coloration": 1,
                "dim": 0,
                "attenuation": 0.5,
                "luminosity": 0.5,
                "saturation": 0,
                "contrast": 0,
                "shadows": 0,
                "animation": {"type": None, "speed": 5, "intensity": 5, "reverse": False},
                "darkness": {"min": 0, "max": 1},
            },
            "sight": {
                "enabled": True,
                "range": 0,
                "angle": 360,
                "visionMode": "basic",
                "color": None,
                "attenuation": 0.1,
                "brightness": 0,
                "saturation": 0,
                "contrast": 0,
            },
            "detectionModes": [],
            "flags": {},
            "randomImg": False,
        }

    def export_all(self) -> List[Dict]:
        """
        Export all monsters to Foundry format.

        Returns:
            List of Foundry Actor documents
        """
        monsters = self.load_all_monsters()
        return [self.export(monster) for monster in monsters]
