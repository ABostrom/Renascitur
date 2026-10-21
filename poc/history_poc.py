"""Proof of concept for the Renascitur History Engine.

Throwaway code to demonstrate the ideas in notes/specs/2026-10-21-history-engine-design.md:
keyed randomness with causal ids, genomes, families, relationships, drives/wants/needs,
an epistemic layer (truth vs belief, lies, rumour drift, provenance), aggregates with
promotion, a canon pin (guard/steer/force), a ripple, and checkpoint replay.

House and settlement names are PoC placeholders, not canon.

Keyed draws here hash (seed, key) with blake2b; the real engine would use NumPy Philox with the same keying.

Run:  uv run --python 3.12 python poc/history_poc.py
Out:  poc/out/poc_data.json
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import pickle
from dataclasses import dataclass, field
from pathlib import Path

START_YEAR = 2300
END_YEAR = 2420
SEED = 1337

# --------------------------------------------------------------------------- keyed randomness

def u(*parts) -> float:
    """Uniform [0,1) draw keyed by (seed, *parts). Same key, same draw, in any run."""
    h = hashlib.blake2b("|".join(map(str, (SEED,) + parts)).encode(), digest_size=8).digest()
    return int.from_bytes(h, "little") / 2**64


def pick(seq, *parts):
    return seq[int(u(*parts) * len(seq))]


def choose(people, *parts):
    """Rendezvous (min-hash) choice: adding/removing one candidate only matters if it is the winner."""
    return min(people, key=lambda x: (u(*parts, x.id), x.id)) if people else None


MATCHING = "rendezvous"  # or "greedy": the naive version, kept to show the coupling it causes


def cid(*parts) -> str:
    """Causal id: derived from what created the entity, never from a global counter."""
    return hashlib.blake2b("|".join(map(str, parts)).encode(), digest_size=5).hexdigest()


# --------------------------------------------------------------------------- world data

PLACES = {
    "lions_rest": dict(name="Lion's Rest", province="Ashgatar", pop=9000),
    "ashgatar": dict(name="Ashgatar Keep", province="Ashgatar", pop=5200),
    "emberwatch": dict(name="Emberwatch", province="Ember Peaks", pop=3100),
    "saltmere": dict(name="Saltmere", province="Flame Coast", pop=6400),
    "cinderford": dict(name="Cinderford", province="Ashen Plains", pop=4800),
    "frontier_hold": dict(name="Frontier Hold", province="Frontier's Edge", pop=2600),
    "burnt_hollow": dict(name="Burnt Hollow", province="Burnt Reach", pop=1900),
}
# (a, b, days on foot, is_vialux)
ROUTES = [
    ("lions_rest", "ashgatar", 6, True), ("lions_rest", "saltmere", 9, True),
    ("lions_rest", "cinderford", 8, True), ("ashgatar", "emberwatch", 11, False),
    ("cinderford", "frontier_hold", 14, False), ("saltmere", "cinderford", 10, True),
    ("frontier_hold", "burnt_hollow", 12, False), ("emberwatch", "frontier_hold", 16, False),
]

HOUSES = {
    "ashford": dict(name="House Ashford", seat="ashgatar", trade="smiths and caravans"),
    "vane": dict(name="House Vane", seat="lions_rest", trade="contracts and coin"),
    "corvel": dict(name="House Corvel", seat="saltmere", trade="ships"),
    "halden": dict(name="House Halden", seat="cinderford", trade="grain"),
    "merrow": dict(name="House Merrow", seat="emberwatch", trade="mines"),
    "tarsk": dict(name="House Tarsk", seat="frontier_hold", trade="wardens"),
}

# locus, alleles (dominant first), founder frequency of recessive allele, trait name
LOCI = [
    ("might", "M", "m", 0.5), ("wits", "W", "w", 0.5), ("temper", "T", "t", 0.5),
    ("stature", "S", "s", 0.5), ("ember_hair", "e", "E", 0.15),  # E dominant ember hair, rare
    ("luxsight", "N", "x", 0.10),  # rare recessive: x/x sees Lux Lapis glow in the dark
    ("resilience", "R", "r", 0.4), ("charm", "C", "c", 0.5),
]

FIRST = {"F": ["Maren", "Sefa", "Brisa", "Tamsin", "Veya", "Lira", "Anwen", "Corra", "Edda", "Nyssa", "Rhosyn", "Aveline", "Brenna", "Cerys",
               "Dara", "Elowen", "Fenna", "Gwen", "Hesper", "Isolde", "Juna", "Kenna", "Liesl", "Mira", "Nerys", "Orla", "Perrin", "Quilla",
               "Rowan", "Saoirse", "Talia", "Una", "Wren", "Yseult"],
         "M": ["Aric", "Odran", "Tomas", "Cael", "Berin", "Dorran", "Halric", "Jory", "Kestrel", "Lucan", "Mael", "Pell", "Roderic", "Senn",
               "Alder", "Bram", "Corwin", "Davin", "Emrys", "Faolan", "Garrick", "Hollis", "Ivo", "Jarek", "Kellan", "Lorcan", "Merek",
               "Niall", "Osric", "Piran", "Quentin", "Rhys", "Soren", "Tobin", "Ulric", "Varek"]}
COMMON_SUR = ["of the Road", "Tanner", "Cobb", "Wick", "Marsh", "Holt", "Reed", "Fenn"]

CLAIMS = {
    "C0": dict(text="House Vane's agents cracked the ward-stones", truth="true", parent=None, blames="vane"),
    "C1": dict(text="The caravan's ward-keeper misaligned the stones", truth="lie", parent=None, blames="victims"),
    "C2": dict(text="Lux Faber's ward-stones were faulty", truth="false", parent=None, blames="guild"),
    "C3": dict(text="House Vane paid a guild apprentice to crack the stones", truth="half", parent="C0", blames="vane"),
    "C4": dict(text="The Guild and House Vane conspire to ruin Ashford", truth="false", parent="C3", blames="guild+vane"),
    "C5": dict(text="Ashford skimped on ward-stones to save coin", truth="false", parent="C1", blames="victims"),
}
DRIFT = {"C0": "C3", "C3": "C4", "C1": "C5", "C2": "C4"}

# --------------------------------------------------------------------------- state


@dataclass
class Person:
    id: str
    name: str
    house: str | None
    sex: str
    born: int
    place: str
    role: str
    mother: str | None = None
    father: str | None = None
    genome: list = field(default_factory=list)  # [[allele, origin_id], [allele, origin_id]] per locus
    died: int | None = None
    death_cause: str | None = None
    spouse: str | None = None
    children: list = field(default_factory=list)
    rel: dict = field(default_factory=dict)  # other_id -> {kind, strength, since}
    drives: dict = field(default_factory=dict)
    wants: list = field(default_factory=list)
    need: str | None = None
    wound: str | None = None
    beliefs: dict = field(default_factory=dict)  # claim -> {conf, heard_from, t, via_event}
    history: list = field(default_factory=list)  # [year, field, value]
    promoted_from: str | None = None
    gen: int = 0
    dormant: bool = False  # demoted back into the aggregate; record kept, id kept
    marriage_event: str | None = None
    grievance: str | None = None  # event id of a violent death this person blames someone for
    amb: list = field(default_factory=list)  # ambition ids, in formation order
    extra_wants: list = field(default_factory=list)  # (kind, text, target, cause) set by scenarios
    title_event: str | None = None
    cooldown: dict = field(default_factory=dict)  # ambition kind -> year it may form again

    def alive(self, y):
        return self.died is None and not self.dormant and self.born <= y


@dataclass
class World:
    year: int = START_YEAR
    people: dict = field(default_factory=dict)
    events: list = field(default_factory=list)
    agg: dict = field(default_factory=dict)  # place -> {pop, freqs, beliefs, series}
    objects: dict = field(default_factory=dict)
    strain: list = field(default_factory=list)
    pins: dict = field(default_factory=dict)
    ripples: list = field(default_factory=list)
    news_in_transit: list = field(default_factory=list)  # [arrive_year, place, claim, from_event]
    ordinals: dict = field(default_factory=dict)
    ambitions: dict = field(default_factory=dict)
    schemes: dict = field(default_factory=dict)
    hinges: list = field(default_factory=list)

    # ---- helpers
    def living(self, place=None):
        ps = [p for p in self.people.values() if p.alive(self.year) and (place is None or p.place == place)]
        return sorted(ps, key=lambda p: p.id)  # stable order: never iterate dicts/sets for sim logic

    def age(self, p):
        return self.year - p.born

    def emit(self, typ, text, place, participants, causes=(), source="system", month=None, salience=1):
        okey = (typ, self.year, json.dumps(participants, sort_keys=True))
        ordinal = self.ordinals.get(okey, 0)
        self.ordinals[okey] = ordinal + 1
        eid = "E" + cid(*okey, ordinal)
        if month is None:
            month = 1 + int(u("month", eid) * 12)
        self.events.append(dict(id=eid, year=self.year, month=month, type=typ, text=text, place=place,
                                participants=participants, causes=list(causes), source=source, salience=salience))
        return eid

    def log(self, p, fld, val):
        p.history.append([self.year, fld, val])


# --------------------------------------------------------------------------- genome


def founder_genome(pid, place_freqs=None, carrier=None):
    g = []
    for i, (locus, dom, rec, f) in enumerate(LOCI):
        f = place_freqs[i] if place_freqs else f
        pair = []
        for k in range(2):
            a = rec if u("founder_allele", pid, locus, k) < f else dom
            if carrier and locus == carrier:
                a = rec
            pair.append([a, pid])
        g.append(pair)
    return g


def inherit(child_id, mom, dad):
    g = []
    for i, (locus, dom, rec, _) in enumerate(LOCI):
        pair = []
        for k, parent in enumerate((mom, dad)):
            allele = copy.copy(parent.genome[i][0 if u("meiosis", child_id, locus, k) < 0.5 else 1])
            if u("mutation", child_id, locus, k) < 0.002:
                allele = [rec if allele[0] == dom else dom, child_id]
            pair.append(allele)
        g.append(pair)
    return g


def phenotype(genome):
    out = {}
    for i, (locus, dom, rec, _) in enumerate(LOCI):
        a, b = genome[i][0][0], genome[i][1][0]
        if locus == "luxsight":
            out[locus] = a == rec and b == rec
        elif locus == "ember_hair":
            out[locus] = "E" in (a, b)
        else:
            out[locus] = (a == dom) + (b == dom)  # 0..2
    return out


# --------------------------------------------------------------------------- setup


def make_person(w, pid, house, sex, born, place, role, **kw):
    first = pick(FIRST[sex], "first", pid)
    sur = HOUSES[house]["name"].split()[-1] if house else pick(COMMON_SUR, "sur", pid)
    p = Person(id=pid, name=f"{first} {sur}", house=house, sex=sex, born=born, place=place, role=role, **kw)
    p.drives = dict(food=0.8, safety=0.7, belonging=0.5, status=0.6 if house else 0.3)
    w.people[pid] = p
    return p


def seed_world(ripples):
    w = World(ripples=ripples)
    for pl, d in PLACES.items():
        w.agg[pl] = dict(pop=d["pop"], freqs=[l[3] for l in LOCI], beliefs={}, series=[])
    for h, hd in HOUSES.items():
        lord = make_person(w, cid("founder", h, "lord"), h, "M", 2262 + int(u("fb", h) * 8), hd["seat"], "lord")
        lord.genome = founder_genome(lord.id, carrier="luxsight" if h == "merrow" else None)
        lady = make_person(w, cid("founder", h, "lady"), h, "F", 2266 + int(u("fb2", h) * 8), hd["seat"], "lady")
        lady.genome = founder_genome(lady.id, carrier="luxsight" if h == "ashford" else None)
        lord.spouse, lady.spouse = lady.id, lord.id
        for a, b in ((lord, lady), (lady, lord)):
            a.rel[b.id] = dict(kind="spouse", strength=0.8, since=START_YEAR)
        # two to four grown children per founding couple
        for k in range(2 + int(u("nkids", h) * 3)):
            c = make_person(w, cid(lady.id, lord.id, "child", k), h, "F" if u("sex", h, k) < 0.5 else "M",
                            2284 + int(u("kb", h, k) * 12), hd["seat"], "heir" if k == 0 else "scion",
                            mother=lady.id, father=lord.id)
            c.genome = inherit(c.id, lady, lord)
            lady.children.append(c.id)
            lord.children.append(c.id)
            for parent in (lady, lord):
                c.rel[parent.id] = dict(kind="parent", strength=0.7, since=c.born)
                parent.rel[c.id] = dict(kind="child", strength=0.8, since=c.born)
    # pinned smith: Kaela Ashford (existence pin), daughter of the Ashford founders
    lord, lady = w.people[cid("founder", "ashford", "lord")], w.people[cid("founder", "ashford", "lady")]
    kaela = make_person(w, cid("pin", "P1", "kaela"), "ashford", "F", 2289, "ashgatar", "smith",
                        mother=lady.id, father=lord.id)
    kaela.name = "Kaela Ashford"
    kaela.genome = inherit(kaela.id, lady, lord)
    lady.children.append(kaela.id)
    lord.children.append(kaela.id)
    for parent in (lady, lord):
        kaela.rel[parent.id] = dict(kind="parent", strength=0.7, since=2289)
        parent.rel[kaela.id] = dict(kind="child", strength=0.8, since=2289)
    # siblings know each other
    for parent in w.living():
        kids = [w.people[c] for c in parent.children]
        for a in kids:
            for b in kids:
                if a.id != b.id:
                    a.rel.setdefault(b.id, dict(kind="sibling", strength=0.6, since=max(a.born, b.born)))
    # Lux Faber guild master at Lion's Rest
    gm = make_person(w, cid("guild", "master"), None, "M", 2270, "lions_rest", "Lux Faber guildmaster")
    gm.name = "Master Orrin of Lux Faber"
    gm.genome = founder_genome(gm.id)
    w.pins = {
        "P1": dict(id="P1", kind="event", text="Kaela Ashford forges the Emberfang between 2312 and 2318",
                   who=kaela.id, window=[2312, 2318], status="pending", guards=0, steered=0, forced=False),
        "P2": dict(id="P2", kind="existence", text="Ilsa Ashford carries the luxsight allele",
                   who=lady.id, status="held"),
        "P3": dict(id="P3", kind="survive", text="Odile Tarsk lives to keep the Night Vigil of 2350 at Frontier Hold",
                   who=cid("founder", "tarsk", "lady"), until=2350, status="pending", guards=0, steered=0, forced=False),
    }
    lady.name = "Ilsa Ashford"
    w.people[cid("founder", "tarsk", "lady")].name = "Odile Tarsk"
    for p in w.people.values():
        w.emit("birth" if p.born >= START_YEAR else "enters_record", f"{p.name} enters the record", p.place, {"subject": p.id}, source="seed", salience=0)
    return w


# --------------------------------------------------------------------------- ambitions

AMB_WEIGHT = dict(spouse=0.2, vengeance=1.0, seize=1.6, standing=1.0, legend=1.2, bury=1.3, clear=1.6)
SCHEME_KIND = dict(seize="poison the heir", standing="win favour at the Firebrand court", bury="silence the witness", clear="gather proof of sabotage")


def amb_active(w, p, kind):
    for aid in p.amb:
        a = w.ambitions[aid]
        if a["kind"] == kind and a["status"] == "active":
            return a
    return None


def form_ambition(w, p, kind, text, target=None, cause=None):
    a = amb_active(w, p, kind)
    if a:
        return a
    aid = "A" + cid("amb", p.id, kind, target, w.year)
    a = dict(id=aid, owner=p.id, kind=kind, text=text, target=target, formed=w.year, cause=cause, status="active",
             resolved=None, outcome=None, beats=[], scheme=None, age_formed=w.age(p))
    w.ambitions[aid] = a
    p.amb.append(aid)
    w.log(p, "ambition", [aid, text, "formed"])
    return a


def resolve_ambition(w, a, status, event=None):
    if a["status"] != "active":
        return
    a["status"], a["resolved"], a["outcome"] = status, w.year, event
    if event:
        a["beats"].append(event)
    p = w.people[a["owner"]]
    p.extra_wants = [x for x in p.extra_wants if x[0] != a["kind"]]
    if a["kind"] in ("standing", "seize"):
        p.cooldown[a["kind"]] = w.year + (40 if status == "fulfilled" else 12)
    w.log(p, "ambition", [a["id"], a["text"], status])
    sc = w.schemes.get(a["scheme"]) if a["scheme"] else None
    if sc and sc["status"] == "active":
        sc["status"] = "owner_died" if status == "died_unfulfilled" else "ended"
        sc["ended"] = w.year


def potential(w, p):
    ph = phenotype(p.genome)
    return round((ph["might"] + ph["wits"] + ph["charm"]) / 6, 2)


# --------------------------------------------------------------------------- systems


def ripple_active(w, kind, target=None):
    return [r for r in w.ripples if r["kind"] == kind and r["year_from"] <= w.year <= r["year_to"] and (target is None or r.get("target") == target)]


def sys_deaths(w):
    plague_places = [e["place"] for e in w.events if e["type"] == "plague" and e["year"] == w.year]
    for p in w.living():
        a = w.age(p)
        hazard = 0.04 if a < 5 else 0.0015 * math.exp(0.085 * max(0, a - 20))
        if p.place in plague_places:
            hazard += 0.12 * (1.4 - 0.3 * phenotype(p.genome)["resilience"])
        roll, hz = u("death", p.id, w.year), min(hazard, 0.95)
        if roll >= hz:
            continue
        cause = "plague" if p.place in plague_places else ("childhood fever" if a < 5 else "old age" if a > 60 else "illness")
        protect = ripple_active(w, "protect", p.id)
        if protect:
            w.emit("near_miss", f"{p.name} recovers from {cause}, tended by a Saltmere physician", p.place, {"subject": p.id},
                   causes=[f"ripple:{protect[0]['id']}"], source="ripple", salience=2)
            continue
        if any(w.ambitions[x]["status"] == "active" and w.ambitions[x]["kind"] != "spouse" for x in p.amb):
            w.hinges.append(dict(year=w.year, kind="death", person=p.id, margin=round((hz - roll) / hz, 3),
                                 text=f"{p.name} died of {cause} with ambitions unfinished"))
        # pin director: guard pinned participants until their pin is fulfilled
        guarded = [pin for pin in w.pins.values() if pin.get("who") == p.id and pin["status"] == "pending"]
        if guarded:
            pin = guarded[0]
            pin["guards"] += 1
            eid = w.emit("near_miss", f"{p.name} survives {cause} against the odds", p.place, {"subject": p.id},
                         causes=[f"pin:{pin['id']}"], source="pin_director", salience=2)
            w.strain.append(dict(year=w.year, pin=pin["id"], action="guard", detail=f"blocked death by {cause}", event=eid))
            continue
        kill(w, p, cause, [e["id"] for e in w.events if e["type"] == "plague" and e["year"] == w.year and e["place"] == p.place])


def kill(w, p, cause, causes, killer=None):
    p.died, p.death_cause = w.year, cause
    parts = {"subject": p.id}
    if killer:
        parts["killer"] = killer
    eid = w.emit("death", f"{p.name} dies ({cause}) aged {w.age(p)}", p.place, parts, causes=causes, salience=2 if p.role in ("lord", "lady", "heir") or killer or p.amb else 1)
    for aid in list(p.amb):
        resolve_ambition(w, w.ambitions[aid], "died_unfulfilled", eid)
    violent = cause in ("night terrors", "slain in a duel")
    for oid in sorted(p.rel):
        o = w.people[oid]
        if o.alive(w.year) and p.rel[oid]["kind"] in ("spouse", "child", "parent", "sibling") and (violent or p.rel[oid]["kind"] == "spouse"):
            if o.wound != "grief":
                o.wound = "grief"
                w.log(o, "wound", "grief")
            if violent and not o.grievance:
                o.grievance = eid
                w.log(o, "grievance", eid)
    # objects pass to the eldest living child, else lost
    for o in w.objects.values():
        if o["owner"] == p.id:
            heirs = sorted([w.people[c] for c in p.children if w.people[c].alive(w.year)], key=lambda c: (c.born, c.id))
            if heirs:
                o["owner"] = heirs[0].id
                o["bio"].append(w.emit("inherits", f"{heirs[0].name} inherits {o['name']}", p.place, {"heir": heirs[0].id, "object": o["id"]}, causes=[eid], salience=2))
            else:
                o["owner"] = None
                o["bio"].append(w.emit("lost", f"{o['name']} is sealed in the vault at {PLACES[p.place]['name']}, its line ended", p.place, {"object": o["id"]}, causes=[eid], salience=3))
    if p.role == "heir":
        for par in (p.mother, p.father):
            if par in w.people and w.people[par].alive(w.year):
                assign_heir(w, w.people[par])
    # succession of house role
    if p.role in ("lord", "lady") and p.house:
        heirs = sorted([w.people[c] for c in p.children if w.people[c].alive(w.year) and w.people[c].house == p.house], key=lambda c: (c.born, c.id))
        if not heirs:  # no children: the seat passes to the eldest living sibling of the house
            sibs = {c for par in (p.mother, p.father) if par in w.people for c in w.people[par].children}
            heirs = sorted([w.people[c] for c in sibs if c != p.id and w.people[c].alive(w.year) and w.people[c].house == p.house], key=lambda c: (c.born, c.id))
        if heirs and heirs[0].role not in ("lord", "lady"):
            h = heirs[0]
            h.role = "lord" if h.sex == "M" else "lady"
            w.log(h, "role", h.role)
            h.drives["status"] = min(1, h.drives["status"] + 0.3)
            h.title_event = w.emit("succession", f"{h.name} becomes head of {HOUSES[p.house]['name']}", p.place, {"heir": h.id, "predecessor": p.id}, causes=[eid], salience=3)
            assign_heir(w, h)
    return eid


def assign_heir(w, head):
    """The eldest living child of a house head, of that house, is named heir."""
    if not head.house or head.role not in ("lord", "lady"):
        return
    kids = sorted([w.people[c] for c in head.children if w.people[c].alive(w.year) and w.people[c].house == head.house], key=lambda c: (c.born, c.id))
    if kids and not any(k.role == "heir" for k in kids) and kids[0].role == "scion":
        kids[0].role = "heir"
        w.log(kids[0], "role", "heir")


def close_kin(a, b):
    pa, pb = {a.mother, a.father} - {None}, {b.mother, b.father} - {None}
    return a.id == b.id or bool(pa & pb) or b.id in pa or a.id in pb


def wed(w, m, f, place, causes):
    m.spouse, f.spouse = f.id, m.id
    for a, b in ((m, f), (f, m)):
        a.rel[b.id] = dict(kind="spouse", strength=0.7, since=w.year)
        w.log(a, "spouse", b.id)
        sp = amb_active(w, a, "spouse")
        if sp:
            sp["_fulfil"] = True
    # the spouse without a house (or the bride, between houses) moves to the other's seat
    mover, host = (f, m) if (m.house or not f.house) else (m, f)
    if mover.place != host.place:
        mover.place = host.place
        w.log(mover, "place", host.place)
    m.marriage_event = f.marriage_event = w.emit("marriage", f"{m.name} weds {f.name}", place, {"groom": m.id, "bride": f.id},
                                                 causes=causes, salience=2 if m.house and f.house else 1)
    for x in (m, f):
        sp = amb_active(w, x, "spouse")
        if sp and sp.pop("_fulfil", False):
            resolve_ambition(w, sp, "fulfilled", m.marriage_event)


def sys_marriage(w):
    """Court season: notables of all houses meet; matching is greedy in stable id order.
    Greedy matching couples broadly (review C2): one extra candidate can re-pair the pool."""
    alive = w.living()
    men = [p for p in alive if p.sex == "M" and p.spouse is None and 17 <= w.age(p) <= 45]
    women = [p for p in alive if p.sex == "F" and p.spouse is None and 17 <= w.age(p) <= 40]
    if MATCHING == "rendezvous":
        # one proposal round: each man proposes to his min-hash eligible woman; each woman accepts her min-hash suitor
        proposals = {}
        for m in men:
            ok = [f for f in women if not close_kin(m, f) and not (m.house and m.house == f.house)
                  and m.rel.get(f.id, {}).get("kind") != "rival" and u("court", m.id, f.id, w.year) < 0.12]
            f = choose(ok, "propose", m.id, w.year)
            if f:
                proposals.setdefault(f.id, []).append(m)
        for fid in sorted(proposals):
            f = w.people[fid]
            m = choose(proposals[fid], "accept", fid, w.year)
            wed(w, m, f, "lions_rest", [f"drive:belonging:{m.id}"])
        men = []
    for m in men:
        best, bs = None, 0.80
        for f in women:
            if f.spouse or close_kin(m, f) or (m.house and m.house == f.house):
                continue
            score = u("match", m.id, f.id, w.year) + (0.05 if m.place == f.place else 0)
            if m.rel.get(f.id, {}).get("kind") == "rival":
                score -= 0.5
            if score > bs:
                best, bs = f, score
        if best:
            wed(w, m, best, "lions_rest", [f"drive:belonging:{m.id}"])
    # no match at court: a notable over 23 may marry a commoner, promoted out of the local aggregate
    for p in w.living():
        if p.house and p.spouse is None and 23 <= w.age(p) <= 40 and u("commoner_match", p.id, w.year) < 0.3:
            c = promote(w, p.place, f"spouse_of_{p.id}", w.year, "commoner")
            if c.sex == p.sex:
                c.sex = "F" if p.sex == "M" else "M"
                c.name = f"{pick(FIRST[c.sex], 'first', c.id)} {c.name.split(' ', 1)[1]}"
            c.born = p.born + int(u("spouse_age", c.id) * 6) - 2
            m, f = (p, c) if p.sex == "M" else (c, p)
            wed(w, m, f, p.place, [f"drive:belonging:{p.id}", "lod:promotion"])


def sys_births(w):
    for mom in w.living():
        if mom.sex != "F" or not mom.spouse or not (18 <= w.age(mom) <= 42):
            continue
        dad = w.people[mom.spouse]
        if not dad.alive(w.year) or u("conceive", mom.id, dad.id, w.year) > 0.22:
            continue
        k = sum(1 for c in mom.children if w.people[c].father == dad.id)
        kid_id = cid(mom.id, dad.id, "child", k)
        house = dad.house or mom.house
        c = make_person(w, kid_id, house, "F" if u("sex", kid_id) < 0.5 else "M", w.year, mom.place,
                        "scion" if house else "commoner", mother=mom.id, father=dad.id)
        c.genome = inherit(kid_id, mom, dad)
        c.gen = max(mom.gen, dad.gen) + 1
        for parent in (mom, dad):
            parent.children.append(kid_id)
            c.rel[parent.id] = dict(kind="parent", strength=0.7, since=w.year)
            parent.rel[kid_id] = dict(kind="child", strength=0.8, since=w.year)
        marriage = mom.marriage_event
        for parent in (mom, dad):
            assign_heir(w, parent)
        ph = phenotype(c.genome)
        eid = w.emit("birth", f"{c.name} is born to {mom.name} and {dad.name}", mom.place, {"child": kid_id, "mother": mom.id, "father": dad.id},
                     causes=[marriage] if marriage else [], salience=1)
        if ph["luxsight"]:
            origins = sorted({a[1] for a in c.genome[5]})
            names = ", ".join(w.people[o].name for o in origins if o in w.people)
            w.emit("trait_resurfaces", f"{c.name} is born with luxsight; the old blood of {names} shows again", mom.place,
                   {"child": kid_id}, causes=[eid], salience=3)


def sys_demote(w):
    """LOD: minor cadet lines fade back into the aggregate. Records stay (dormant), ids stay, pinned never fade."""
    pinned = {pin.get("who") for pin in w.pins.values()}
    obj_owners = {o["owner"] for o in w.objects.values()}
    for p in w.living():
        if (p.role in ("scion", "commoner") and p.gen >= 2 and w.age(p) >= 25 and not p.beliefs and not p.wound
                and not any(w.ambitions[x]["status"] == "active" and w.ambitions[x]["kind"] != "spouse" for x in p.amb)
                and p.id not in pinned and p.id not in obj_owners and u("demote", p.id, w.year) < 0.25):
            p.dormant = True
            w.log(p, "dormant", True)
            w.agg[p.place]["pop"] += 1
            w.emit("fades", f"{p.name} fades from the chronicles into the common folk of {PLACES[p.place]['name']}",
                   p.place, {"subject": p.id}, source="lod", salience=0)


def sys_social(w):
    """Seasonal: co-located notables form friendships and rivalries."""
    for season in range(4):
        for pl in PLACES:
            ps = [p for p in w.living(pl) if w.age(p) >= 14]
            for i, a in enumerate(ps):
                for b in ps[i + 1:]:
                    r = u("social", a.id, b.id, w.year, season)
                    if r > 0.012:
                        continue
                    ta, tb = phenotype(a.genome)["temper"], phenotype(b.genome)["temper"]
                    kind = "rival" if (ta + tb) <= 1 and r < 0.006 else "friend"
                    if a.rel.get(b.id, {}).get("kind") in ("spouse", "parent", "child", "sibling"):
                        continue
                    for x, y in ((a, b), (b, a)):
                        x.rel[y.id] = dict(kind=kind, strength=0.5, since=w.year)
                    w.emit("befriend" if kind == "friend" else "quarrel",
                           f"{a.name} and {b.name} become {'friends' if kind == 'friend' else 'rivals'}", pl,
                           {"a": a.id, "b": b.id}, salience=0, month=1 + season * 3)


def sys_minds(w):
    """Yearly drives -> wants; wounds -> needs. Logs changes for the 'as of' inspector."""
    for p in w.living():
        if w.age(p) < 12:
            continue
        d = p.drives
        nd = dict(d)
        nd["belonging"] = round(min(1, 0.25 + 0.15 * sum(1 for r in p.rel.values() if r["kind"] in ("spouse", "friend", "child"))), 2)
        nd["safety"] = round(0.4 if p.wound in ("grief", "terror") else 0.75, 2)
        nd["status"] = round(0.9 if p.role in ("lord", "lady") else 0.85 if p.role.startswith("envoy") else
                             0.2 if p.role in ("exile", "disgraced") else 0.6 if p.house else 0.3, 2)
        if nd != d:
            p.drives = nd
            w.log(p, "drives", nd)
        ph = phenotype(p.genome)
        age = w.age(p)
        # fulfilment first: ambitions of rank are met by holding the seat
        for aid in list(p.amb):
            a = w.ambitions[aid]
            if a["status"] == "active" and a["kind"] in ("seize", "standing") and p.role in ("lord", "lady"):
                resolve_ambition(w, a, "fulfilled", p.title_event)
        cand = []  # (kind, text, target, cause)
        if p.spouse is None and 17 <= age <= 45 and nd["belonging"] < 0.6:
            cand.append(("spouse", "find a spouse", None, f"drive:belonging:{p.id}"))
        blame = blamed_house(p)
        if p.grievance and blame:
            cand.append(("vengeance", f"avenge kin against {blame}", blame, p.grievance))
        if (nd["status"] < 0.7 and ph["charm"] >= 1 and ph["wits"] >= 1 and p.house and 18 <= age <= 60
                and u("courtly", p.id) < 0.25 and p.cooldown.get("standing", 0) <= w.year and p.role not in ("lord", "lady", "exile")):
            cand.append(("standing", f"raise {HOUSES[p.house]['name']} high at the Firebrand court", p.house, f"drive:status:{p.id}"))
        if (p.house and p.role == "scion" and 18 <= age <= 50 and ph["temper"] <= 1 and ph["wits"] >= 1
                and u("ambitious", p.id) < 0.45 and p.cooldown.get("seize", 0) <= w.year):
            sibs = {c for par in (p.mother, p.father) if par in w.people for c in w.people[par].children}
            elders = [w.people[c] for c in sorted(sibs) if c != p.id and w.people[c].alive(w.year)
                      and w.people[c].house == p.house and w.people[c].role in ("heir", "lord", "lady")]
            if elders:
                e = min(elders, key=lambda x: (x.born, x.id))
                cand.append(("seize", f"take the seat of {HOUSES[p.house]['name']} from {e.name.split()[0]}", e.id, f"drive:status:{p.id}"))
        if p.role == "smith" and not any(w.ambitions[x]["kind"] == "legend" and w.ambitions[x]["status"] == "fulfilled" for x in p.amb):
            cand.append(("legend", "forge a blade worthy of legend", None, f"drive:status:{p.id}"))
        cand += [tuple(x) for x in p.extra_wants]
        kinds = {c[0] for c in cand}
        for kind, text, target, cause in cand:
            form_ambition(w, p, kind, text, target, cause)
        for aid in list(p.amb):
            a = w.ambitions[aid]
            if a["status"] == "active" and a["kind"] not in kinds and a["kind"] not in ("legend",):
                resolve_ambition(w, a, "abandoned")
        wants = [w.ambitions[x]["text"] for x in p.amb if w.ambitions[x]["status"] == "active"]
        if wants != p.wants:
            p.wants = wants
            w.log(p, "wants", wants)
        need = {"grief": "to let the dead rest", "terror": "to walk in the dark unafraid", "betrayal": "to trust again"}.get(p.wound)
        if need and need != p.need:
            p.need = need
            w.log(p, "need", need)


def blamed_house(p):
    best = max(p.beliefs.items(), key=lambda kv: (kv[1]["conf"], kv[0]), default=None)
    if not best:
        return None
    b = CLAIMS[best[0]]["blames"]
    return {"vane": "House Vane", "guild": "Lux Faber", "guild+vane": "House Vane and Lux Faber", "victims": None}[b]


def believe(w, p, claim, conf, heard_from, via_event):
    old = p.beliefs.get(claim)
    if old and old["conf"] >= conf:
        return False
    rivals = [c for c, b in p.beliefs.items() if CLAIMS[c]["blames"] != CLAIMS[claim]["blames"] and c != claim]
    strongest = max((p.beliefs[c]["conf"] for c in rivals), default=0)
    if strongest >= conf:
        return False  # contradicts a firmer belief: rejected
    for c in sorted(rivals):  # accepted: contradicting accounts weaken
        p.beliefs[c]["conf"] = round(p.beliefs[c]["conf"] * 0.5, 2)
    p.beliefs[claim] = dict(conf=round(conf, 2), heard_from=heard_from, t=w.year, via_event=via_event)
    w.log(p, "belief", [claim, round(conf, 2), heard_from])
    return True


def sys_rumour(w):
    """Seasonal gossip along relationships, with trust, fit-with-prior-beliefs and drift."""
    for season in range(4):
        for p in w.living():
            for claim in sorted(p.beliefs):
                b = p.beliefs[claim]
                if b["conf"] < 0.4:
                    continue
                for oid in sorted(p.rel):
                    o = w.people[oid]
                    if not o.alive(w.year) or o.place != p.place:
                        continue
                    r = p.rel[oid]
                    if u("gossip", p.id, oid, claim, w.year, season) > 0.15 * r["strength"]:
                        continue
                    told = claim
                    if claim in DRIFT and u("drift", p.id, oid, claim, w.year, season) < 0.08:
                        told = DRIFT[claim]  # retelling mutates the claim; lineage kept in CLAIMS[parent]
                    trust = r["strength"] * (1.2 if r["kind"] in ("spouse", "sibling", "parent", "child") else 0.8)
                    fit = 1.0
                    prior = blamed_house(o)
                    if prior and CLAIMS[told]["blames"] != "victims" and prior.split()[-1].lower() in CLAIMS[told]["blames"]:
                        fit = 1.3  # confirmation bias
                    conf = min(0.95, b["conf"] * trust * fit)
                    if conf > 0.25 and believe(w, o, told, conf, p.id, None):
                        if told != claim:
                            w.emit("rumour_drift", f"{p.name} tells {o.name}: \"{CLAIMS[told]['text']}\"", p.place,
                                   {"teller": p.id, "hearer": o.id}, causes=[f"claim:{claim}"], salience=1, month=1 + season * 3)
    # travelling news: arrives after route delay; Vialux carries the guild line
    arrived = [n for n in w.news_in_transit if n[0] <= w.year]
    w.news_in_transit = [n for n in w.news_in_transit if n[0] > w.year]
    for _, place, claim, ev in sorted(arrived):
        bel = w.agg[place]["beliefs"]
        bel[claim] = round(min(1.0, bel.get(claim, 0) + 0.25), 3)


def sys_aggregates(w):
    """Seasonal masses: population, allele frequencies and belief distribution per place."""
    for pl, a in w.agg.items():
        plague = any(e["type"] == "plague" and e["place"] == pl and e["year"] == w.year for e in w.events)
        growth = -0.18 if plague else 0.004 + 0.004 * (u("harvest", pl, w.year) - 0.5)
        a["pop"] = int(a["pop"] * (1 + growth))
        # masses drift toward local notables' beliefs
        notables = w.living(pl)
        for claim in sorted(CLAIMS):
            share = sum(p.beliefs.get(claim, {}).get("conf", 0) for p in notables) / max(1, len(notables))
            cur = a["beliefs"].get(claim, 0.0)
            new = round(0.85 * cur + 0.15 * min(1.0, share * 3), 3)
            if new > 0.001:
                a["beliefs"][claim] = new
        a["series"].append(dict(year=w.year, pop=a["pop"], beliefs=dict(a["beliefs"])))


def promote(w, place, event_key, k, role):
    """Pull a concrete person out of a place's aggregate, consistent with its allele frequencies."""
    pid = cid("promote", place, event_key, k)
    sex = "F" if u("sex", pid) < 0.5 else "M"
    p = make_person(w, pid, None, sex, w.year - 18 - int(u("age", pid) * 25), place, role, promoted_from=place)
    p.genome = founder_genome(pid, w.agg[place]["freqs"])
    w.agg[place]["pop"] -= 1
    w.emit("promoted", f"{p.name}, a {role} of {PLACES[place]['name']}, steps out of the crowd", place, {"subject": pid}, source="lod", salience=0)
    return p


# --------------------------------------------------------------------------- scenario: the ward failure


def scenario_ward_failure(w):
    """Scripted injection (review I10): a Vialux-adjacent ward failure, year 2330."""
    if w.year != 2330:
        return
    ash = sorted([p for p in w.living("ashgatar") if p.house == "ashford" and 18 <= w.age(p) <= 50], key=lambda p: (p.role != "heir", p.born, p.id))
    vane_head = next((p for p in w.living() if p.house == "vane" and p.role in ("lord", "lady")), None)
    if not ash or not vane_head:
        return
    leader = ash[0]
    # true cause chain: Vane's rivalry over the Emberwatch ore contract
    contract = w.emit("contract_lost", f"House Vane loses the Emberwatch ore contract to House Ashford", "lions_rest",
                      {"winner": leader.id, "loser": vane_head.id}, salience=2)
    vane_head.rel[leader.id] = dict(kind="rival", strength=0.8, since=w.year)
    leader.rel[vane_head.id] = dict(kind="rival", strength=0.6, since=w.year)
    sabotage = w.emit("sabotage", f"Agents of {vane_head.name} crack the caravan's ward-stones in secret", "ashgatar",
                      {"ordered_by": vane_head.id}, causes=[contract], salience=3)
    keeper = promote(w, "ashgatar", "ward_failure", 0, "ward-keeper")
    guards = [promote(w, "ashgatar", "ward_failure", k, "caravan guard") for k in (1, 2, 3)]
    failure = w.emit("ward_failure", f"The wards fail on the Emberwatch road at night; night terrors take the caravan of {leader.name}",
                     "ashgatar", {"leader": leader.id, "keeper": keeper.id}, causes=[sabotage], salience=4)
    # leader dies unless a ripple protects them (disguised as an in-world cause)
    saved = ripple_active(w, "protect", leader.id)
    if saved:
        w.emit("rescue", f"A Leonin outrider pulls {leader.name} from the wreck before dawn", "ashgatar", {"saved": leader.id},
               causes=[failure, f"ripple:{saved[0]['id']}"], source="ripple", salience=3)
        leader.wound = "terror"
        leader.grievance = failure
        w.log(leader, "wound", "terror")
        w.log(leader, "grievance", failure)
        survivors = [leader, keeper, guards[0]]
        for g in guards[1:]:
            kill(w, g, "night terrors", [failure])
    else:
        kill(w, leader, "night terrors", [failure])
        kill(w, guards[2], "night terrors", [failure])
        survivors = [keeper, guards[0], guards[1]]
    # perception: survivors saw parts of it
    for s in survivors:
        if u("perceive", s.id) < 0.45:
            believe(w, s, "C0", 0.6, None, failure)
        else:
            believe(w, s, "C2", 0.5, None, failure)
        s.wound = s.wound or "terror"
        w.log(s, "wound", s.wound)
    # the guild master privately suspects sabotage but publicly blames the ward-keeper (a lie with intent)
    gm = w.people[cid("guild", "master")]
    believe(w, gm, "C3", 0.7, None, failure)
    stmt = w.emit("guild_statement", f"{gm.name} declares the ward-keeper misaligned the stones", "lions_rest",
                  {"speaker": gm.id, "accused": keeper.id}, causes=[failure, "intent:protect guild reputation"], salience=3)
    for pl in sorted(PLACES):
        delay = 0 if pl == "lions_rest" else 1  # Vialux carries the official line fast
        w.news_in_transit.append([w.year + delay, pl, "C1", stmt])
    for p in w.living("lions_rest"):
        if p.house in ("vane", "corvel") or p.role.startswith("Lux"):
            believe(w, p, "C1", 0.6, gm.id, stmt)
    # rumours travel the wild roads slowly from Ashgatar
    for a, b, days, vialux in ROUTES:
        if "ashgatar" in (a, b) and not vialux:
            other = b if a == "ashgatar" else a
            w.news_in_transit.append([w.year + 2, other, "C0", failure])
    keeper.wound = "betrayal"
    w.log(keeper, "wound", "betrayal")
    vane_head.extra_wants.append(("bury", "bury the truth of the Emberwatch road", keeper.id, sabotage))
    keeper.extra_wants.append(("clear", "clear my name before the Emperor's magistrate", gm.id, stmt))


def sys_feuds(w):
    """Wants become actions: vengeance traced to beliefs."""
    for p in w.living():
        want = next((x for x in p.wants if x.startswith("avenge")), None)
        if not want or w.age(p) < 16:
            continue
        if u("feud", p.id, w.year) > 0.12:
            continue
        target_house = "vane" if "Vane" in want else None
        targets = [t for t in w.living() if target_house and t.house == target_house and w.age(t) >= 16
                   and t.id != p.id and t.house != p.house]
        if not targets:
            continue
        t = choose(targets, "target", p.id, w.year) if MATCHING == "rendezvous" else pick(targets, "target", p.id, w.year)
        claim = max(p.beliefs.items(), key=lambda kv: (kv[1]["conf"], kv[0]))[0]
        sword = next((o for o in w.objects.values() if o["owner"] == p.id), None)
        causes = [f"belief:{p.id}:{claim}", f"want:{p.id}:{want}"]
        weapon = f" with {sword['name']}" if sword else ""
        droll, dthr = u("duel", p.id, t.id, w.year), 0.45 + 0.15 * phenotype(p.genome)["might"] + (0.15 if sword else 0)
        win = droll < dthr
        duel = w.emit("duel", f"{p.name} challenges {t.name}{weapon}, believing \"{CLAIMS[claim]['text']}\"", t.place,
                      {"challenger": p.id, "target": t.id}, causes=causes, salience=3)
        if sword:
            sword["bio"].append(duel)
        amb = amb_active(w, p, "vengeance")
        if amb:
            amb["beats"].append(duel)
        if abs(droll - dthr) < 0.06:
            w.hinges.append(dict(year=w.year, kind="duel", person=p.id, margin=round(droll - dthr, 3), event=duel,
                                 text=f"{p.name}'s duel with {t.name} turned on a hair"))
        if win and amb:
            resolve_ambition(w, amb, "fulfilled", duel)
        loser = t if win else p
        spare = ripple_active(w, "protect", loser.id)
        if spare:
            w.emit("spared", f"{loser.name} is struck down but lives, carried from the field by a Leonin outrider", t.place,
                   {"subject": loser.id}, causes=[duel, f"ripple:{spare[0]['id']}"], source="ripple", salience=2)
            continue
        kill(w, loser, "slain in a duel", [duel], killer=(p if win else t).id)
        if win and sword:
            sword["deeds"] += 1
        survivor = p if win else t
        if win:
            p.wants = [x for x in p.wants if x != want]
            p.wound, p.grievance = None, None
            w.log(p, "wound", None)
            w.log(p, "grievance", None)
            w.log(p, "wants", list(p.wants))
        else:
            for oid in sorted(p.rel):
                o = w.people[oid]
                if o.alive(w.year) and p.rel[oid]["kind"] in ("spouse", "child", "sibling"):
                    believe(w, o, claim, 0.8, p.id, duel)


def sys_schemes(w):
    """Ambitions of rank, secrecy and justice become multi-year schemes with accomplices, progress and exposure risk."""
    for p in w.living():
        for aid in list(p.amb):
            a = w.ambitions[aid]
            if a["status"] != "active" or a["kind"] not in SCHEME_KIND or not p.alive(w.year):
                continue
            tgt = w.people.get(a["target"])
            if a["scheme"] is None:
                if u("plot", aid, w.year) > 0.45:
                    continue
                pool = [w.people[o] for o in sorted(p.rel) if p.rel[o]["kind"] in ("friend", "sibling", "spouse")
                        and w.people[o].alive(w.year) and o != a["target"]]
                acc = choose(pool, "accomplice", aid)
                sid = "S" + cid("scheme", aid)
                parts = {"schemer": p.id}
                if acc:
                    parts["accomplice"] = acc.id
                if tgt:
                    parts["target"] = tgt.id
                ev = w.emit("scheme_begins", f"{p.name} begins to {SCHEME_KIND[a['kind']]}" + (f", with {acc.name}" if acc else ""),
                            p.place, parts, causes=[a["cause"]] if a["cause"] else [], salience=2)
                w.schemes[sid] = dict(id=sid, ambition=aid, owner=p.id, kind=SCHEME_KIND[a["kind"]], target=a["target"],
                                      accomplices=[acc.id] if acc else [], started=w.year, progress=0.0, status="active",
                                      beats=[ev], ended=None, secret=a["kind"] != "clear", progress_log=[[w.year, 0.0]])
                a["scheme"] = sid
                a["beats"].append(ev)
                continue
            sc = w.schemes[a["scheme"]]
            if sc["status"] != "active":
                continue
            if a["kind"] in ("seize", "bury") and tgt and not tgt.alive(w.year):
                sc["status"], sc["ended"] = "moot", w.year
                if a["kind"] == "bury":
                    resolve_ambition(w, a, "fulfilled", None)
                continue
            ph = phenotype(p.genome)
            favour = ripple_active(w, "favour", p.id)
            gain = (0.10 + 0.07 * ph["wits"] + 0.05 * len(sc["accomplices"])) * (0.5 + u("progress", sc["id"], w.year)) + (0.2 if favour else 0)
            sc["progress"] = round(min(1.0, sc["progress"] + gain), 3)
            sc["progress_log"].append([w.year, sc["progress"]])
            if sc["secret"]:
                pexp = (0.05 + 0.04 * (2 - ph["wits"])) * (0.4 if favour else 1)
                roll = u("expose", sc["id"], w.year)
                if abs(roll - pexp) < 0.04:
                    w.hinges.append(dict(year=w.year, kind="exposure", person=p.id, scheme=sc["id"], margin=round(roll - pexp, 3),
                                         text=f"{p.name}'s plot to {sc['kind']} {'was exposed' if roll < pexp else 'nearly came to light'}"))
                if roll < pexp:
                    expose(w, p, a, sc)
                    continue
            if sc["progress"] >= 1.0:
                succeed(w, p, a, sc)


def succeed(w, p, a, sc):
    sc["status"], sc["ended"] = "success", w.year
    tgt = w.people.get(a["target"])
    parts = {"schemer": p.id, **({"accomplice": sc["accomplices"][0]} if sc["accomplices"] else {}), **({"target": tgt.id} if tgt else {})}
    if a["kind"] == "seize" and tgt:
        secret = w.emit("poisoning", f"{p.name} poisons {tgt.name}; the court will call it a wasting illness", tgt.place, parts,
                        causes=[sc["beats"][0], f"want:{p.id}:{a['text']}"], source="scheme", salience=4)
        sc["beats"].append(secret)
        a["beats"].append(secret)
        kill(w, tgt, "a wasting illness", [secret])
    elif a["kind"] == "bury" and tgt:
        secret = w.emit("murder", f"Agents of {p.name} drown {tgt.name} in the Ashgatar cistern; it is called an accident", tgt.place, parts,
                        causes=[sc["beats"][0], f"want:{p.id}:{a['text']}"], source="scheme", salience=4)
        sc["beats"].append(secret)
        kill(w, tgt, "drowned in the Ashgatar cistern", [secret])
        resolve_ambition(w, a, "fulfilled", secret)
    elif a["kind"] == "standing":
        p.role = "envoy to the Firebrand court"
        w.log(p, "role", p.role)
        ev = w.emit("court_favour", f"{p.name} wins the Emperor's favour and is named envoy to the Firebrand court", "lions_rest", parts,
                    causes=[sc["beats"][0]], source="scheme", salience=3)
        sc["beats"].append(ev)
        resolve_ambition(w, a, "fulfilled", ev)
    elif a["kind"] == "clear":
        sab = next((e for e in w.events if e["type"] == "sabotage"), None)
        culprit = sab["participants"]["ordered_by"] if sab else None
        parts = {"witness": p.id, **({"accused": culprit} if culprit else {})}
        ev = w.emit("testimony", f"{p.name} lays proof of the sabotage before the Emperor's magistrate", "lions_rest", parts,
                    causes=[sc["beats"][0]] + ([sab["id"]] if sab else []), source="scheme", salience=4)
        sc["beats"].append(ev)
        for q in w.living("lions_rest") + w.living("ashgatar"):
            believe(w, q, "C0", 0.75, p.id, ev)
        for pl in sorted(PLACES):
            w.news_in_transit.append([w.year + 1, pl, "C0", ev])
        if culprit and culprit in w.people and w.people[culprit].alive(w.year):
            c = w.people[culprit]
            c.role = "disgraced"
            w.log(c, "role", "disgraced")
        resolve_ambition(w, a, "fulfilled", ev)


def expose(w, p, a, sc):
    sc["status"], sc["ended"] = "exposed", w.year
    tgt = w.people.get(a["target"])
    parts = {"schemer": p.id, **({"target": tgt.id} if tgt else {})}
    ev = w.emit("plot_exposed", f"{p.name}'s plot to {sc['kind']} is exposed", p.place, parts, causes=[sc["beats"][0]], salience=4)
    sc["beats"].append(ev)
    resolve_ambition(w, a, "thwarted", ev)
    if tgt and tgt.alive(w.year):
        tgt.rel[p.id] = dict(kind="enemy", strength=0.9, since=w.year)
        p.rel[tgt.id] = dict(kind="enemy", strength=0.9, since=w.year)
    if a["kind"] == "seize":
        spare = ripple_active(w, "protect", p.id)
        if spare:
            p.role = "exile"
            p.place = "burnt_hollow"
            w.log(p, "role", "exile")
            w.emit("pardon", f"{p.name} is pardoned at the scaffold and exiled to Burnt Hollow", "lions_rest", {"subject": p.id},
                   causes=[ev, f"ripple:{spare[0]['id']}"], source="ripple", salience=3)
        else:
            kill(w, p, "executed for treason", [ev])
    elif a["kind"] == "bury":
        p.role = "exile"
        p.place = "frontier_hold"
        w.log(p, "role", "exile")
        for q in w.living("lions_rest"):
            believe(w, q, "C0", 0.65, None, ev)
    else:
        p.drives["status"] = 0.2
        w.log(p, "drives", dict(p.drives))


def sys_pin_director(w):
    p3 = w.pins["P3"]
    if p3["status"] == "pending" and w.year == p3["until"]:
        o = w.people[p3["who"]]
        w.emit("night_vigil", f"{o.name}, aged {w.age(o)}, keeps the Night Vigil at Frontier Hold", "frontier_hold",
               {"keeper": o.id}, causes=["pin:P3"], salience=3)
        p3["status"] = "fulfilled"
        p3["fulfilled_year"] = w.year
    pin = w.pins["P1"]
    if pin["status"] != "pending":
        return
    lo, hi = pin["window"]
    if w.year < lo:
        return
    kaela = w.people[pin["who"]]
    base = 0.15
    steer = 0.0
    if w.year >= lo + 2:  # steer only once natural odds look thin (review I3)
        steer = 0.12 * (w.year - lo - 1)
        pin["steered"] += 1
        w.strain.append(dict(year=w.year, pin="P1", action="steer", detail=f"forge odds raised by {steer:.2f}", event=None))
    roll = u("forge", kaela.id, w.year)
    forced = w.year == hi and roll >= base + steer
    if roll < base + steer or forced:
        lord = next((p for p in w.living() if p.house == "ashford" and p.role in ("lord", "lady")), kaela)
        commission = w.emit("commission", f"{lord.name} commissions a blade of Lux-tempered steel from {kaela.name}", "ashgatar",
                            {"patron": lord.id, "smith": kaela.id}, causes=[f"want:{kaela.id}:forge a blade worthy of legend"], salience=2)
        causes = [commission, f"pin:P1"]
        forge = w.emit("forging", f"{kaela.name} forges the Emberfang", "ashgatar", {"smith": kaela.id},
                       causes=causes, source="pin_director" if forced else "system", salience=4)
        w.objects["emberfang"] = dict(id="emberfang", name="the Emberfang", maker=kaela.id, owner=lord.id, deeds=0, bio=[commission, forge])
        pin["status"] = "fulfilled"
        pin["fulfilled_year"] = w.year
        if forced:
            pin["forced"] = True
            w.strain.append(dict(year=w.year, pin="P1", action="force", detail="forged at window deadline", event=forge))
        leg = amb_active(w, kaela, "legend")
        if leg:
            resolve_ambition(w, leg, "fulfilled", forge)


def sys_catastrophe(w):
    if w.year == 2352:
        w.emit("plague", "The grey cough sweeps through Saltmere", "saltmere", {}, causes=["structural:harbour trade"], salience=3)
    if w.year == 2371:
        w.emit("plague", "Pox in the Ashgatar barracks", "ashgatar", {}, salience=3)


SYSTEMS = [sys_catastrophe, sys_deaths, sys_marriage, sys_births, sys_demote, scenario_ward_failure, sys_pin_director, sys_social, sys_minds, sys_schemes, sys_rumour, sys_feuds, sys_aggregates]


def step(w):
    for s in SYSTEMS:
        s(w)
    if w.year % 20 == 0:
        print(f"  {w.year}: {len(w.living())} notables alive, {len(w.events)} events", flush=True)
    w.year += 1


def run(ripples, until=END_YEAR, world=None, checkpoint_at=None):
    w = world or seed_world(ripples)
    snap = None
    while w.year < until:
        if checkpoint_at and w.year == checkpoint_at:
            snap = pickle.dumps(w)
        step(w)
    return w, snap


def state_hash(w):
    payload = json.dumps(dict(events=w.events, people={k: v.__dict__ for k, v in sorted(w.people.items())}), sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


# --------------------------------------------------------------------------- export


def export(w):
    people = {}
    for p in w.people.values():
        ph = phenotype(p.genome)
        people[p.id] = dict(id=p.id, name=p.name, house=p.house, sex=p.sex, born=p.born, died=p.died, death_cause=p.death_cause,
                            place=p.place, role=p.role, mother=p.mother, father=p.father, spouse=p.spouse, children=p.children,
                            genome=p.genome, phenotype=ph, rel=p.rel, drives=p.drives, wants=p.wants, need=p.need, wound=p.wound,
                            beliefs=p.beliefs, history=p.history, promoted_from=p.promoted_from, gen=p.gen, dormant=p.dormant)
    events = [e for e in w.events if e["salience"] > 0 or e["type"] in ("promoted", "fades")]
    schemes = {k: dict(v) for k, v in w.schemes.items()}
    return dict(people=people, events=events, event_count=len(w.events), agg=w.agg, objects=w.objects, strain=w.strain, pins=w.pins,
                ripples=w.ripples, ambitions=w.ambitions, schemes=schemes, hinges=w.hinges, threads=story_threads(w), latches=latch_points(w))


# --------------------------------------------------------------------------- story finding


def story_threads(w):
    """Group ambitions that share events, causes or targets into threads, then title and score them."""
    ev = {e["id"]: e for e in w.events}
    ambs = [a for a in w.ambitions.values() if a["kind"] != "spouse"]
    parent = {a["id"]: a["id"] for a in ambs}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    by_event, owner_of = {}, {}
    for a in ambs:
        keys = set(a["beats"]) | ({a["outcome"]} if a["outcome"] else set())
        c = a["cause"]
        if c in ev:
            keys.add(c)
            keys.update(x for x in ev[c]["causes"] if x in ev)
        for k in sorted(keys):
            by_event.setdefault(k, []).append(a["id"])
        owner_of.setdefault(a["owner"], []).append(a["id"])
    for ids in by_event.values():
        for x in ids[1:]:
            parent[find(x)] = find(ids[0])
    for a in ambs:  # plotters racing each other: a scheme's target and the target's own ambitions
        for b in owner_of.get(a["target"], []):
            parent[find(b)] = find(a["id"])
    groups = {}
    for a in ambs:
        groups.setdefault(find(a["id"]), []).append(a)
    out = []
    for members in groups.values():
        has_scheme = any(m["scheme"] for m in members)
        if len(members) < 2 and not has_scheme and members[0]["kind"] != "legend":
            continue
        members.sort(key=lambda m: (m["formed"], m["id"]))
        people = []
        for m in members:
            for x in (m["owner"], m["target"]):
                if x in w.people and x not in people:
                    people.append(x)
        st = {}
        for m in members:
            st[m["status"]] = st.get(m["status"], 0) + 1
        start = min(m["formed"] for m in members)
        end = max((m["resolved"] or END_YEAR) for m in members)
        beat_ids = set()
        for m in members:
            beat_ids.update(m["beats"])
            if m["cause"] in ev:
                beat_ids.add(m["cause"])
        beats = sorted((ev[b] for b in beat_ids if b in ev and ev[b]["salience"] >= 2), key=lambda e: (e["year"], e["month"], e["id"]))
        kinds = {}
        for m in members:
            kinds[m["kind"]] = kinds.get(m["kind"], 0) + AMB_WEIGHT[m["kind"]]
        lead = max(members, key=lambda m: (AMB_WEIGHT[m["kind"]], -m["formed"], m["id"]))
        lp = w.people[lead["owner"]]
        houses = []
        for x in people:
            h = w.people[x].house
            if h and HOUSES[h]["name"].split()[-1] not in houses:
                houses.append(HOUSES[h]["name"].split()[-1])
        if "bury" in kinds or "clear" in kinds:
            title = "The Emberwatch Road Affair"
        elif max(kinds, key=kinds.get) == "vengeance":
            title = f"The {'–'.join(houses[:2]) or 'Ashford'} Blood Feud"
        elif lead["kind"] == "seize":
            title = f"{lp.name}'s Bid for the Seat of {HOUSES[lp.house]['name']}"
        elif lead["kind"] == "standing":
            title = f"{lp.name}'s {'Rise' if lead['status'] == 'fulfilled' else 'Climb'} at Court"
        elif lead["kind"] == "legend":
            title = "The Forging of the Emberfang"
        else:
            title = f"The Ambitions of {lp.name}"
        died = st.get("died_unfulfilled", 0)
        score = round(sum(AMB_WEIGHT[m["kind"]] for m in members) + 1.5 * died + st.get("fulfilled", 0) + 0.7 * st.get("thwarted", 0)
                      + 0.15 * len(people) + (end - start) / 25 + 0.3 * len(beats), 2)
        out.append(dict(id="T" + cid("thread", members[0]["id"]), title=title, start=start, end=end, members=[m["id"] for m in members],
                        people=people[:40], n_people=len(people), status=st, beats=[b["id"] for b in beats][:40], n_beats=len(beats),
                        score=score, open=st.get("active", 0) > 0, lead=lead["id"]))
    out.sort(key=lambda t: (-t["score"], t["id"]))
    seen = {}
    for t in out:  # disambiguate repeated titles
        n = seen.get(t["title"], 0)
        seen[t["title"]] = n + 1
        if n:
            t["title"] += f" ({['', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII'][min(n, 7)]})"
    return out[:60]


def latch_points(w):
    """People who died with an ambition unfulfilled, ranked by how much story a nudge might unlock."""
    best = {}
    for a in w.ambitions.values():
        if a["status"] != "died_unfulfilled" or a["kind"] == "spouse":
            continue
        p = w.people[a["owner"]]
        age = p.died - p.born
        sc = w.schemes.get(a["scheme"]) if a["scheme"] else None
        hinge = next((h for h in w.hinges if h["person"] == p.id and h["kind"] == "death" and h["year"] == p.died), None)
        pot = potential(w, p)
        if a["kind"] == "standing" and not (sc and sc["progress"] >= 0.3):
            continue
        score = round(AMB_WEIGHT[a["kind"]] + pot + max(0, 50 - age) / 25 - (1.0 if age > 60 else 0) + 1.5 * (sc["progress"] if sc else 0)
                      + (0.6 if hinge and hinge["margin"] < 0.3 else 0), 2)
        how = "a ripple can stop a natural death" if p.death_cause in ("illness", "plague", "childhood fever", "old age") else               "a ripple can spare them in the fight" if p.death_cause == "slain in a duel" else               "a ripple can pardon them at the scaffold" if p.death_cause == "executed for treason" else "only a structural ripple could change this"
        lp = dict(person=p.id, ambition=a["id"], kind=a["kind"], text=a["text"], year=p.died, age=age, cause=p.death_cause,
                  potential=pot, progress=sc["progress"] if sc else None, scheme=sc["id"] if sc else None,
                  margin=hinge["margin"] if hinge else None, score=score, how=how,
                  suggestion=f"Protect {p.name} from {p.death_cause} in {p.died}" + (" and favour their scheme" if sc else ""))
        if p.id not in best or best[p.id]["score"] < score:
            best[p.id] = lp
    return sorted(best.values(), key=lambda x: (-x["score"], x["person"]))[:30]


def whatif_summary(base, wi, pid, ripples):
    p0, p1 = base.people[pid], wi.people.get(pid)
    if not p1:
        return None
    ambs = [wi.ambitions[x] for x in p1.amb if wi.ambitions[x]["kind"] != "spouse"]
    after = [e for e in wi.events if pid in e["participants"].values() and e["salience"] >= 2 and e["year"] >= p0.died]
    great = [a for a in ambs if a["status"] == "fulfilled" and (a["resolved"] or 0) >= p0.died]
    if great:
        verdict = "rises to greatness: " + "; ".join(dict.fromkeys(a["text"] for a in great))
    elif p1.died and p1.died > p0.died:
        verdict = f"lives {p1.died - p0.died} more years, but the ambition still slips away"
    elif not p1.died:
        verdict = "survives to 2420 with the ambition still unresolved"
    else:
        verdict = "dies anyway"
    ids0 = {e["id"] for e in base.events}
    ids1 = {e["id"] for e in wi.events}
    return dict(person=pid, ripples=ripples, base_death=p0.died, base_cause=p0.death_cause, died=p1.died, cause=p1.death_cause,
                role=p1.role, verdict=verdict,
                ambitions=[dict(text=a["text"], status=a["status"], formed=a["formed"], resolved=a["resolved"]) for a in ambs],
                beats=[dict(year=e["year"], text=e["text"], type=e["type"]) for e in sorted(after, key=lambda e: (e["year"], e["month"], e["id"]))][:16],
                divergent_events=len(ids0 ^ ids1), descendants=len(p1.children) - len(p0.children))


def diff(a, b):
    ids = sorted(set(a.people) | set(b.people))
    changed, only_a, only_b, by_house = [], [], [], {}
    for i in ids:
        pa, pb = a.people.get(i), b.people.get(i)
        if not pa:
            only_b.append(i)
            continue
        if not pb:
            only_a.append(i)
            continue
        sa = (pa.died, pa.spouse, tuple(sorted(pa.beliefs)), pa.wound, tuple(pa.children))
        sb = (pb.died, pb.spouse, tuple(sorted(pb.beliefs)), pb.wound, tuple(pb.children))
        key = pa.house or f"commoners of {PLACES[pa.place]['name']}"
        h = by_house.setdefault(key, dict(same=0, changed=0))
        if sa != sb:
            changed.append(i)
            h["changed"] += 1
        else:
            h["same"] += 1
    return dict(changed=changed, only_baseline=only_a, only_ripple=only_b, by_group=by_house,
                total_shared=len(ids) - len(only_a) - len(only_b))


def divergence(a, b, ripple_target, ripple_year):
    """Event-level divergence per decade, plus taint tracking: which differences have no causal path from the ripple."""
    ids_a = {e["id"] for e in a.events}
    ids_b = {e["id"] for e in b.events}
    waves = []
    for y in range(ripple_year, END_YEAR + 1, 10):
        row = dict(year=y)
        for pl in sorted(PLACES):
            ea = [e for e in a.events if e["place"] == pl and e["year"] <= y and e["year"] >= ripple_year]
            eb = [e for e in b.events if e["place"] == pl and e["year"] <= y and e["year"] >= ripple_year]
            union = {e["id"] for e in ea} | {e["id"] for e in eb}
            same = sum(1 for e in ea if e["id"] in ids_b)
            row[pl] = round(1 - same / len(union), 3) if union else 0.0
        waves.append(row)
    # taint: the ripple's target, then anyone sharing an event with a tainted person, or hearing gossip from one
    def taint(w):
        t = {ripple_target: ripple_year}
        by_year = {}
        for e in w.events:
            by_year.setdefault(e["year"], []).append(e)
        for y in range(ripple_year, END_YEAR):
            changed = True
            while changed:
                changed = False
                for e in by_year.get(y, []):
                    ps = [v for v in e["participants"].values() if v in w.people]
                    if any(p in t for p in ps):
                        for p in ps:
                            if p not in t:
                                t[p] = y
                                changed = True
                for p in sorted(w.people.values(), key=lambda x: x.id):
                    if p.id in t:
                        continue
                    for h in p.history:
                        if h[0] == y and h[1] in ("belief", "spouse") and (h[2][2] if h[1] == "belief" else h[2]) in t:
                            t[p.id] = y
                            changed = True
                            break
        return t
    ta, tb = taint(a), taint(b)
    tainted = set(ta) | set(tb)
    only = [e for e in b.events if e["id"] not in ids_a and e["year"] >= ripple_year] + \
           [e for e in a.events if e["id"] not in ids_b and e["year"] >= ripple_year]
    people_in = lambda e: [v for v in e["participants"].values() if v in a.people or v in b.people]
    unexplained = [e for e in only if people_in(e) and not any(v in tainted for v in people_in(e))]
    kinds = {}
    for e in unexplained:
        kinds[e["type"]] = kinds.get(e["type"], 0) + 1
    first = sorted(unexplained, key=lambda e: (e["year"], e["id"]))[:5]
    return dict(waves=waves, divergent_events=len(only), unexplained=len(unexplained), unexplained_kinds=kinds,
                first_unexplained=[f"{e['year']} {e['type']}: {e['text']}" for e in first], tainted=len(tainted))


def job(ripples, checkpoint_at=None):
    return run(ripples, checkpoint_at=checkpoint_at)


def resume_job(snap):
    return run([], world=pickle.loads(snap))[0]


def main():
    from concurrent.futures import ProcessPoolExecutor
    outdir = Path(__file__).parent / "out"
    outdir.mkdir(exist_ok=True)
    path = outdir / "poc_data.json"
    greedy_cache = None
    if path.exists():  # greedy-matching comparison carried over from the earlier PoC run
        try:
            greedy_cache = json.loads(path.read_text())["meta"]["checks"].get("greedy_divergence")
        except Exception:
            greedy_cache = None
    with ProcessPoolExecutor(max_workers=4) as ex:
        f_base, f_base2 = ex.submit(job, [], 2360), ex.submit(job, [])
        base, snap = f_base.result()
        leader = next(e["participants"]["leader"] for e in base.events if e["type"] == "ward_failure")
        ripple = dict(id="R1", kind="protect", target=leader, year_from=2330, year_to=2330,
                      text="Protect the Ashford caravan leader at the ward failure (disguised as a Leonin outrider's rescue)")
        f_rip, f_res = ex.submit(job, [ripple]), ex.submit(resume_job, snap)
        latches = latch_points(base)
        picks = [lp for lp in latches if lp["person"] != leader][:4]
        wi_jobs = []
        for i, lp in enumerate(picks):
            pr = base.people[lp["person"]]
            amb = base.ambitions[lp["ambition"]]
            rips = [dict(id=f"W{i + 1}", kind="protect", target=pr.id, year_from=pr.died, year_to=pr.died + 30,
                         text=f"Protect {pr.name} from death for 30 years from {pr.died}"),
                    dict(id=f"W{i + 1}f", kind="favour", target=pr.id, year_from=amb["formed"], year_to=pr.died + 30,
                         text=f"Favour {pr.name}'s schemes")]
            wi_jobs.append((lp, rips, ex.submit(job, rips)))
        base2, _ = f_base2.result()
        rip, _ = f_rip.result()
        resumed = f_res.result()
        whatifs = []
        for lp, rips, f in wi_jobs:
            wi, _ = f.result()
            summ = whatif_summary(base, wi, lp["person"], rips)
            if summ:
                summ["latch"] = lp
                whatifs.append(summ)
    d = diff(base, rip)
    div = divergence(base, rip, leader, 2330)
    checks = dict(determinism=state_hash(base) == state_hash(base2), checkpoint_replay=state_hash(base) == state_hash(resumed),
                  hash=state_hash(base)[:16], divergence=div, greedy_divergence=greedy_cache)
    out = dict(meta=dict(start=START_YEAR, end=END_YEAR, seed=SEED, places=PLACES, routes=ROUTES, houses=HOUSES,
                         loci=[[l[0], l[1], l[2]] for l in LOCI], claims=CLAIMS, checks=checks, diff=d, amb_weight=AMB_WEIGHT),
               runs=dict(baseline=export(base), ripple=export(rip)), whatifs=whatifs)
    path.write_text(json.dumps(out, default=str))
    print(f"people: {len(base.people)}, events: {len(base.events)}, ambitions: {len(base.ambitions)}, schemes: {len(base.schemes)}")
    print(f"checks: determinism={checks['determinism']} replay={checks['checkpoint_replay']} unexplained={div['unexplained']}/{div['divergent_events']}")
    st = {}
    for a in base.ambitions.values():
        st[(a["kind"], a["status"])] = st.get((a["kind"], a["status"]), 0) + 1
    print("ambitions:", dict(sorted(st.items())))
    sst = {}
    for sc in base.schemes.values():
        sst[(sc["kind"], sc["status"])] = sst.get((sc["kind"], sc["status"]), 0) + 1
    print("schemes:", dict(sorted(sst.items())))
    for t in out["runs"]["baseline"]["threads"][:8]:
        print(f"  THREAD {t['score']:6.1f} {t['title']} {t['start']}-{t['end']} people={t['n_people']} {t['status']}")
    for lp in latches[:6]:
        print(f"  LATCH {lp['score']:.2f} {base.people[lp['person']].name}: {lp['text']} | died {lp['year']} ({lp['cause']}) age {lp['age']}")
    for wsum in whatifs:
        print(f"  WHAT-IF {base.people[wsum['person']].name}: {wsum['verdict']} (diverge {wsum['divergent_events']})")
    print(f"wrote {path} ({path.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
