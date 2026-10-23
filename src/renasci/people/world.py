"""The people ruleset for a world described by a scenario (S3): every people system, the scenario's
world params, and its conservation check. Kin and the Fourth Age are both built from this."""

from __future__ import annotations

from renasci.core.systems import Ruleset
from renasci.people.ambitions import Ambitions
from renasci.people.canon import FORCERS
from renasci.people.drives import Drives
from renasci.people.families import Marriage
from renasci.people.genome import Catalogue
from renasci.people.houses import Houses
from renasci.people.life import Births, Illness, Life, world_params
from renasci.people.minds import Minds
from renasci.people.schemes import Schemes
from renasci.people.population import Lod, Population, conservation
from renasci.people.ties import Ties
from renasci.people.travel import Migration
from renasci.people.beliefs import Gossip


def people_ruleset(name: str, scenario: dict, version: int = 1) -> Ruleset:
    params = world_params(scenario["races"], scenario["catalogue"], aggregates=True,
                          **{k: v for k, v in scenario.get("params", {}).items() if k != "aggregates"})
    systems = (Population(), Births(), Life(), Marriage(), Houses(), Lod(), Ties(), Drives(), Ambitions(), Schemes(),
               Minds())
    if scenario.get("geography"):  # journeys need routes (S4 §5)
        systems += (Migration(),)
    if scenario.get("params", {}).get("beliefs"):  # gossip needs minds that hold beliefs (S6 §6)
        systems += (Gossip(),)
    return Ruleset(name, version, systems,
                   params=params, forcers=FORCERS, disguises=(Illness(),),
                   conservation=conservation(Catalogue.from_json(scenario["catalogue"])))
