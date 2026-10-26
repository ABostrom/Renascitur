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

**Canon** (S2 §7, `canon=`): people the vault places at the start, cast with their canon ids (`v:`).
A house whose head is canon is built around them: the canon head takes the synthesised head's place (and
the headship), with the family's ages fitted to theirs, and a canon father takes the founder's. Other canon
people are added to their house (or as commoners at their home), with their canon parents; canon parents
who died before the start are cast as dead records, so lineages hold. Placed canon count as residents
before the masses are cast, so conservation holds as it does for synthesised notables.
"""

from __future__ import annotations

from renasci import geo, polities
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
    def __init__(self, engine, scenario: dict, seed: int, canon=None):
        self.e, self.sc = engine, scenario
        self.canon = canon or {"people": {}, "heads": {}}
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

    def rename(self, old: str, new: str) -> None:
        """Give a synthesised person a canon id, everywhere they are named."""
        self.people[new] = self.people.pop(old)
        for person in self.people.values():
            for k in ("mother", "father", "spouse"):
                if person[k] == old:
                    person[k] = new
            person["children"] = [new if c == old else c for c in person["children"]]
        if old in self.dead:
            self.dead.discard(old)
            self.dead.add(new)

    def canon_age(self, cid: str) -> int | None:
        born = self.canon["people"].get(cid, {}).get("born")
        return age_years(self.cal, born, self.today) if born else None

    def apply_canon(self, pid: str, cid: str) -> None:
        """A synthesised person becomes the canon one: their id, and what the vault says of them."""
        self.rename(pid, cid)
        c, person = self.canon["people"][cid], self.people[cid]
        for k in ("name", "sex", "born", "race"):
            if c.get(k):
                person[k] = c[k]
        if c.get("status") == "dead":
            self.dead.add(cid)
        else:
            self.dead.discard(cid)

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
        canon_head = self.canon["heads"].get(house)
        head_sex = "m"
        father_age = father_dead_for = None
        if canon_head:
            if self.canon_age(canon_head) is not None:
                head_age = self.canon_age(canon_head)
            head_sex = self.canon["people"][canon_head].get("sex") or "m"
            father = self.canon["people"].get(self.canon["people"][canon_head].get("father") or "", {})
            if father.get("born"):
                father_age = age_years(self.cal, father["born"], self.today)
                if self.canon_age(canon_head) is None:  # a drawn head: young enough to be the father's child
                    head_age = max(1, min(head_age, father_age - race.marriage[0]))
            if father.get("died"):
                father_dead_for = age_years(self.cal, father["died"], self.today)
        founder_id = founder_person("m", head_age + race.marriage[0] + int(rng.integers(0, 11)), True)
        self.dead.add(founder_id)
        ages = [head_age]  # the head is the eldest son; his brothers and sisters are younger
        for _ in range(int(rng.integers(0, 4))):
            nxt = ages[-1] - gap - int(rng.integers(0, 4))
            if nxt < 1:
                break
            ages.append(nxt)
        if father_dead_for is not None:  # nobody is the canon father's child who was born after he died
            ages = [ages[0]] + [a for a in ages[1:] if a >= father_dead_for]
        siblings = [child_of(None, founder_id, a, True, sex=head_sex if i == 0 else None) for i, a in enumerate(ages)]
        head = siblings[0]
        if canon_head:
            self.apply_canon(head, canon_head)
            siblings[0] = head = canon_head
            father = self.canon["people"][canon_head].get("father")
            if father and father in self.canon["people"] and father not in self.people:
                self.apply_canon(founder_id, father)  # the canon father is the founder
                founder_id = father
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

    def canon_rest(self, settlements: dict, houses: dict) -> None:
        """Canon people not already cast as a head or a head's father: added where the vault puts them.
        Parents first (by the order of their births), so a child's canon parents exist when it is cast."""
        canon = self.canon["people"]
        order: list[str] = []

        def visit(cid, seen=()):
            if cid in order or cid in seen or cid not in canon:
                return
            for k in ("father", "mother"):
                visit(canon[cid].get(k), (*seen, cid))
            order.append(cid)

        for cid in sorted(canon):
            visit(cid)
        for cid in order:
            if cid in self.people:
                continue
            c = canon[cid]
            home = c.get("home") if c.get("home") in settlements else (
                houses[c["house"]]["seat"] if c.get("house") in houses else self.sc["settlements"][0]["id"])
            spec = settlements[home]
            race = self.races[c.get("race") or spec["race"]]
            rng = self.stream("canon", cid)
            sex = c.get("sex") or ("m" if rng.random() < race.male else "f")
            born = c.get("born")
            kids = sorted(k["born"] for k in canon.values() if cid in (k.get("father"), k.get("mother")) and k.get("born"))
            if born is None and kids:  # a parent: old enough at their first child's birth
                lo = race.fertile[0] if sex == "f" else race.marriage[0]
                hi = race.fertile[1] if sex == "f" else race.marriage[0] + 25
                at = lo + int(rng.integers(0, max(1, min(hi, lo + 15) - lo + 1)))
                born = [kids[0][0], kids[0][1] - at, int(rng.integers(0, self.cal.days_per_year))]
            elif born is None:
                age = self.age_from_life_table(race, sex, rng, lo=race.marriage[0])
                born = _born(self.today, age, int(rng.integers(0, self.cal.days_per_year)))
            father = c.get("father") if c.get("father") in self.people else None
            mother = c.get("mother") if c.get("mother") in self.people else None
            group = spec["genome_group"]
            if father or mother:
                known = [self.people[x]["genome"] for x in (mother, father) if x]
                mg, fg = (known[0], known[1]) if len(known) == 2 else (None, known[0])
                unknown = None if mg else ({lo.id: self.cat.groups[group][lo.id] for lo in self.cat.loci}, f"f:{group}")
                genome, _ = inherit(self.cat, mg, fg, self.genome_streams(cid), f"f:{group}", unknown=unknown)
            else:
                genome = founder(self.cat, group, self.genome_streams(cid), f"f:{group}")
            self.people[cid] = _person(c.get("name") or cid, sex, born, race.id, home, genome, self.cat,
                                       house=c.get("house") if c.get("house") in houses else None,
                                       mother=mother, father=father)
            for parent in (mother, father):
                if parent:
                    self.people[parent]["children"].append(cid)
            if c.get("status") == "dead":
                self.dead.add(cid)

    def link_canon(self) -> None:
        """Canon parents, linked whatever order people were cast in (a head built as a synthesised
        founder's son, a child cast before its parent)."""
        for cid, c in sorted(self.canon["people"].items()):
            if cid not in self.people:
                continue
            person = self.people[cid]
            for k in ("father", "mother"):
                parent = c.get(k)
                if not parent or parent not in self.people or person[k] == parent:
                    continue
                old = person[k]
                if old in self.people:
                    self.people[old]["children"] = [x for x in self.people[old]["children"] if x != cid]
                person[k] = parent
                self.people[parent]["children"].append(cid)

    def geography(self) -> None:
        """The scenario's places, regions and routes (S4 §2-3), once its settlements agree with them."""
        g = self.sc.get("geography")
        if g is None:
            return
        if not isinstance(g, dict):
            raise ValueError("the scenario's geography must be loaded first (renasci.geo.attach)")
        bad = [f for f in geo.check(g) if f["severity"] == "error"] or geo.check_scenario(self.sc, g)
        if bad:
            raise ValueError("geography: " + "; ".join(f"{f['kind']}: {f['message']}" for f in bad))
        geo.cast(self.e, g, polities.control_of(self.sc))

    # ------------------------------------------------------------ cast it all

    def build(self) -> None:
        bad = polities.check(self.sc)
        if bad:
            raise ValueError("polities: " + "; ".join(f"{f['kind']}: {f['message']}" for f in bad))
        control = polities.control_of(self.sc)
        settlements = {s["id"]: s for s in self.sc["settlements"]}
        for spec in self.sc["settlements"]:
            self.commoners(spec)
        heads = {}
        for spec in self.sc["houses"]:
            heads[spec["id"]] = self.house(spec, settlements[spec["seat"]])[0]
        self.canon_rest(settlements, {h["id"]: h for h in self.sc["houses"]})
        self.link_canon()
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
                "danger": spec.get("danger", 0.0), **({"control": control.get(s)} if control else {})})
        cast_masses(self.e, {s: (spec["race"], spec["genome_group"], spec.get("masses", 0), len(residents[s]))
                             for s, spec in settlements.items()}, self.cat, self.races)
        if (self.sc.get("params") or {}).get("crafts"):  # (S9: the masses' job columns, #123)
            from renasci.people import work

            work.cast(self.e, sorted(settlements), {s: spec.get("masses", 0) for s, spec in settlements.items()},
                      self.sc["params"]["crafts"])
            from renasci.people import crafts

            crafts.cast(self.e, sorted(settlements), self.sc["params"]["crafts"])
        self.geography()
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
        polities.cast(self.e, self.sc, self.today)


def synthesise(engine, scenario: dict, seed: int, canon: dict | None = None) -> None:
    """Cast a scenario's starting world into `engine` (before pins are applied), with canon placed in it:
    `canon = {"people": {id: {name, sex, born, race, house, home, father, mother, status}}, "heads": {house: id}}`
    (`renasci.people.casting.canon_from` builds it from the vault)."""
    _Builder(engine, scenario, seed, canon).build()
