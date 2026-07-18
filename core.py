from dataclasses import dataclass, field
from typing import Callable, Optional

# ---- Einheitliche Ein-/Ausgabe-Datentypen ----
@dataclass
class Falldaten:
    landgericht: str = ""
    amtsgericht: str = ""
    haftart: str = "Freiheitsstrafe"
    geschlecht: str = "männlich"
    alter: int = 30
    alter_tatzeit: int = 0
    dauer_monate: Optional[float] = None
    lebenslang: bool = False
    offener_vollzug: bool = False
    auf_freiem_fuss: bool = False
    sexualdelikt: bool = False          # NEU: zentrale Ladung (z. B. BB -> Brandenburg a. d. Havel)

@dataclass
class Ergebnis:
    anstalt: Optional[str]
    regel: str
    hinweise: list = field(default_factory=list)
    adresse: list = field(default_factory=list)

@dataclass
class Bundesland:
    code: str                      # "MV", "BY", ...
    name: str                      # "Mecklenburg-Vorpommern"
    stand: str                     # Stichtag des Plans
    quelle: str                    # URL/Fundstelle
    ermittle: Callable[[Falldaten], Ergebnis]
    landgerichte: list             # Auswahlliste fürs Frontend
    anstalten: dict                # Name -> Adresszeilen

# ---- Registry ----
_REGISTRY: dict[str, Bundesland] = {}

def registriere(bl: Bundesland):
    _REGISTRY[bl.code] = bl

def alle_laender() -> list[Bundesland]:
    return sorted(_REGISTRY.values(), key=lambda b: b.name)

def hole_land(code: str) -> Bundesland:
    return _REGISTRY[code]
