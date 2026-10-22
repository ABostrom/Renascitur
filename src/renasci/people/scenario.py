"""Scenario synthesis (S3 spec §9): a starting world from a scenario (JSON), a seed and canon.

```json
{"params": {"house_from": "father", ...},          // world params (people.life.world_params)
 "races": [...], "catalogue": {...},
 "regions": {"t:Hollow": ["t:Hollow-1", ...]},
 "settlements": [{"id": "t:Hollow-1", "region": "t:Hollow", "race": "k:folk", "genome_group": "lowland",
                  "masses": 200, "commoners": 20, "capacity": 440, "notable_target": 20, "danger": 0.0}],
 "houses": [{"id": "t:House-Hollow", "name": "Hollow", "seat": "t:Hollow-1", "rank": 3,
             "rule": "male_preference_primogeniture"}]}
```

Everything is drawn from one keyed stream per purpose (`genome.keyed(seed)`), so the same seed and
scenario always give the same world. Synthesis runs before pins are applied (a pin may name a
synthesised `s:` person); S2's casting (#63) will place canon *into* the synthesised families.

1. **Masses:** each settlement's age structure is its race's life table (`population.cast_masses`).
2. **Commoners:** `commoners` notables per settlement with ages drawn from the same life table and
   founder genomes; neighbours of opposite sex and marriageable age are married.
3. **Houses:** a family at the seat. A founder (dead, a father no younger than the marriage age)
   whose children are the head (30-55, the eldest son) and 0-3 younger siblings; the head and adult
   brothers marry and have up to 4 children (inheriting from both parents), born while the mother was
   fertile, spaced by her race's birth spacing (her `last_birth` is her youngest); sisters stay in the
   house unmarried. Wives join their husband's house. A seat's notable target and capacity grow by the
   house living there. The head holds the headship; the yearly heir pass names the heir.

Synthesised ids start `s:` (cast, not born): `s:<house>:<n>`, `s:<settlement>:<n>`.
"""

from __future__ import annotations

from renasci.core.calendar import Date
from renasci.people.genome import Catalogue, founder, inherit, keyed, phenotype
from renasci.people.population import cast_masses
from renasci.people.races import BAND_YEARS, Race, age_years


def _born(today: Date, age: int, day: int) -> list[int]:
    """A birth date that makes someone exactly `age` on `today`."""
    return [today.age, today.year - age - (1 if day > today.day else 0), day]


def _person(name, sex, born, race, place, genome, catalogue, house=None, mother=None, father=None):
    return {"name": name, "sex": sex, "born": born, "race": race, "place": place, "house": house,
            "mother": mother, "father": father, "children": [], "spouse": None, "genome": genome,
            "traits": phenotype(catalogue, genome, {}), "drives": {}, "ties": [], "last_birth": None, "offices": []}


class _Builder:
    def __init__(self, engine, scenario: dict, seed: int):
        self.e, self.sc = engine, scenario
        self.cal, self.today = engine.calendar, engine.start
        self.races = {r["id"]: Race.from_json(r) for r in scenario["races"]}
        self.cat = Catalogue.from_json(scenario["catalogue"])
        self.streams = keyed(seed)
        self.people: dict[str, dict] = {}  # everyone, settled before anything is cast
        self.dead: set[str] = set()

    def stream(self, *parts):
        return self.streams("synth:" + ":".join(parts))

    def genome_streams(self, pid: str):
        return lambda name: self.streams(f"genome:{pid}:{name}")

    def age_from_life_table(self, race: Race, sex: str, rng, lo: int = 0, hi: int = 99) -> int:
        alive, weights = 1.0, []
        for b in range(20):
            weights.append(alive)
            alive *= (1.0 - race.mortality[sex][b]) ** BAND_YEARS
        ok = [b for b in range(20) if b * BAND_YEARS + BAND_YEARS - 1 >= lo and b * BAND_YEARS <= hi]
        b = ok[rng.choice_index([weights[x] for x in ok])]
        return min(max(b * BAND_YEARS + int(rng.integers(0, BAND_YEARS)), lo), hi)

    def name(self, race: Race, sex: str, rng) -> str:
        pool = race.names[sex]
        return pool[rng.choice_index([1.0] * len(pool))]

    def marry(self, a: str, b: str) -> None:
        self.people[a]["spouse"], self.people[b]["spouse"] = b, a

    # ------------------------------------------------------------ commoners

    def commoners(self, spec: dict) -> None:
        s, race = spec["id"], self.races[spec["race"]]
        rng = self.stream("commoners", s)
        made = []
        for i in range(spec.get("commoners", 0)):
            pid = f"s:{s[2:]}:{i:03d}"
            sex = "m" if i % 2 == 0 else "f"
            age = self.age_from_life_table(race, sex, rng)
            day = int(rng.integers(0, self.cal.days_per_year))
            genome = founder(self.cat, spec["genome_group"], self.genome_streams(pid), f"f:{spec['genome_group']}")
            self.people[pid] = _person(self.name(race, sex, rng), sex, _born(self.today, age, day), race.id, s,
                                       genome, self.cat)
            made.append((pid, age))
        for (a, age_a), (b, age_b) in zip(made[0::2], made[1::2]):  # neighbours of age marry
            if min(age_a, age_b) >= race.marriage[0] and abs(age_a - age_b) <= 15:
                self.marry(a, b)

    # ------------------------------------------------------------ houses

    def house(self, spec: dict, seat: dict) -> tuple[str, list[str]]:
        house, s, race = spec["id"], seat["id"], self.races[seat["race"]]
        group = seat["genome_group"]
        rng = self.stream("house", house)
        n = [0]

        def new_id() -> str:
            n[0] += 1
            return f"s:{house[2:]}:{n[0]:03d}"

        def founder_person(sex: str, age: int, member: bool) -> str:
            pid = new_id()
            day = int(rng.integers(0, self.cal.days_per_year))
            genome = founder(self.cat, group, self.genome_streams(pid), f"f:{group}")
            self.people[pid] = _person(self.name(race, sex, rng), sex, _born(self.today, age, day), race.id, s,
                                       genome, self.cat, house=house if member else None)
            return pid

        def child_of(mother: str | None, father: str, age: int, member: bool, sex: str | None = None) -> str:
            pid = new_id()
            drawn = "m" if rng.random() < race.male else "f"
            sex = sex or drawn
            day = int(rng.integers(0, self.cal.days_per_year))
            mg = self.people[mother]["genome"] if mother else None
            fg = self.people[father]["genome"]
            unknown = None if mg else ({lo.id: self.cat.groups[group][lo.id] for lo in self.cat.loci}, f"f:{group}")
            genome, _ = inherit(self.cat, mg, fg, self.genome_streams(pid), f"f:{group}", unknown=unknown)  # stock
            self.people[pid] = _person(self.name(race, sex, rng), sex, _born(self.today, age, day), race.id, s,
                                       genome, self.cat, house=house if member else None, mother=mother, father=father)
            for parent in (mother, father):
                if parent:
                    self.people[parent]["children"].append(pid)
            return pid

        # Whole years between a mother's births: her spacing, plus a year so birth days can't close the gap.
        gap = -(-race.spacing_days // self.cal.days_per_year) + 1
        head_age = 30 + int(rng.integers(0, 26))
        founder_id = founder_person("m", head_age + race.marriage[0] + int(rng.integers(0, 11)), True)
        self.dead.add(founder_id)
        ages = [head_age]  # the head is the eldest son; his brothers and sisters are younger
        for _ in range(int(rng.integers(0, 4))):
            nxt = ages[-1] - gap - int(rng.integers(0, 4))
            if nxt < 1:
                break
            ages.append(nxt)
        siblings = [child_of(None, founder_id, a, True, sex="m" if i == 0 else None) for i, a in enumerate(ages)]
        head = siblings[0]
        for p, age in zip(siblings, ages):
            if self.people[p]["sex"] != "m" or age < race.marriage[0]:
                continue  # sisters and the young stay unmarried in the house
            wife_age = max(race.marriage[0], min(age - 10 + int(rng.integers(0, 16)), race.fertile[1] + 15))
            wife = founder_person("f", wife_age, True)
            self.marry(p, wife)
            # Children eldest first: she was fertile at each birth, he was of age, and births are spaced.
            child_age = min(wife_age - race.fertile[0], age - race.marriage[0])
            child_age = int(rng.integers(0, child_age + 1)) if child_age >= 0 else -1
            for _ in range(int(rng.integers(0, 5))):
                if child_age < 0:
                    break
                if wife_age - child_age <= race.fertile[1]:
                    child_of(wife, p, child_age, True)
                child_age -= gap + int(rng.integers(0, 3))
            kids = self.people[wife]["children"]
            if kids:
                self.people[wife]["last_birth"] = self.people[kids[-1]]["born"]
        return head, siblings

    # ------------------------------------------------------------ cast it all

    def build(self) -> None:
        settlements = {s["id"]: s for s in self.sc["settlements"]}
        for spec in self.sc["settlements"]:
            self.commoners(spec)
        heads = {}
        for spec in self.sc["houses"]:
            heads[spec["id"]] = self.house(spec, settlements[spec["seat"]])[0]
        residents = {s: [] for s in settlements}
        for pid, person in self.people.items():
            if pid not in self.dead:
                residents[person["place"]].append(pid)
        for spec in self.sc["settlements"]:
            s = spec["id"]
            extra = len(residents[s]) - spec.get("commoners", 0)  # a seat's house lives there too
            target, capacity = spec.get("notable_target"), spec.get("capacity")
            self.e.cast("settlement", s, {
                "region": spec["region"], "race": spec["race"], "genome_group": spec["genome_group"],
                "residents": sorted(residents[s]),
                "capacity": None if capacity is None else capacity + max(0, extra),
                "notable_target": None if target is None else target + max(0, extra),
                "danger": spec.get("danger", 0.0)})
        cast_masses(self.e, {s: (spec["race"], spec["genome_group"], spec.get("masses", 0), len(residents[s]))
                             for s, spec in settlements.items()}, self.cat, self.races)
        for pid in sorted(self.people):
            person = self.people[pid]
            if pid in heads.values():
                house = person["house"]
                person["offices"] = [f"{house}-head"]
            self.e.cast("person", pid, person, status="dead" if pid in self.dead else "active")
        for spec in self.sc["houses"]:
            house = spec["id"]
            self.e.cast("house", house, {"name": spec["name"], "seat": spec["seat"], "rank": spec.get("rank", 0),
                                         "founded": self.today.to_json(), "headship": f"{house}-head", "extinct": None})
            self.e.cast("office", f"{house}-head", {"name": f"Head of {spec['name']}", "holder": heads[house],
                                                    "heir": None, "rule": spec.get("rule", "male_preference_primogeniture"),
                                                    "house": house})


def synthesise(engine, scenario: dict, seed: int) -> None:
    """Cast a scenario's starting world into `engine` (before it runs, after canon is placed)."""
    _Builder(engine, scenario, seed).build()
