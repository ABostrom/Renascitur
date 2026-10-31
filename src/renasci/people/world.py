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
    if scenario.get("params", {}).get("crafts"):  # jobs, skills and wealth (S9 §2, #123)
        from renasci.people.work import Work

        systems += (Work(),)
        if scenario["params"]["crafts"].get("materials"):  # materials, stock and masterworks (S9 §3, #124)
            from renasci.people.crafts import Crafts

            systems += (Crafts(),)
    if scenario.get("geography"):  # journeys need routes (S4 §5)
        systems += (Migration(),)
        if scenario["geography"].get("changes"):  # the map by year (S4 §8, #81)
            from renasci import geo

            params = {**params, "map_changes": scenario["geography"]["changes"]}
            systems += (geo.map_history()(),)
    if scenario.get("params", {}).get("beliefs"):  # gossip needs minds that hold beliefs (S6 §6)
        systems += (Gossip(),)
    if scenario.get("polities"):  # relations between polities drift (S8 §4)
        from renasci.relations import Diplomacy
        from renasci.stats import Stats
        from renasci.war import War

        systems += (Diplomacy(), War(), Stats())
        if scenario.get("params", {}).get("campaigns"):  # wars fought a season at a time (S8 §8, #122)
            from renasci.campaigns import Campaigns

            systems += (Campaigns(),)
    disguises = (Illness(),)
    if scenario.get("geography"):  # a structural ripple changes the map (#114)
        from renasci import geo

        disguises += (geo.upheaval()(),)
    if scenario.get("params", {}).get("beliefs") or scenario.get("params", {}).get("crafts"):  # a planted rumour
        # needs a town's talk (#114); a planted thing, a world of things (S9 #126)
        from renasci.people.beliefs import plant_for

        disguises += (plant_for(bool(scenario["params"].get("beliefs")), bool(scenario["params"].get("crafts"))),)
    return Ruleset(name, version, systems,
                   params=params, forcers=FORCERS, disguises=disguises,
                   conservation=conservation(Catalogue.from_json(scenario["catalogue"])))
