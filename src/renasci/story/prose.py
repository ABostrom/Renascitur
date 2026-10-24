"""Claims out of prose (S12 spec §4, #117): what a text says happened, as claims a run can judge.

A pattern extractor, not a parser. Each sentence is **tagged**: dates (the calendar's forms: "4A 5",
"4A 5 Spring", "4A 5 m3 d4", "the year 5 of the Fourth Age", "the 5th year of the Fourth Age"), places,
houses ("House Kundarak"), events (by noun: "the ward failure at Lux Oescus in 4A 2", "the death of
Jory"), and people (by name). A person's qualifiers are merged into their mention: "Cara of House
Kundarak", "Cara, of House Kundarak,", "Cara (House Kundarak)", "House Kundarak's Cara", "Cole of Lux
Oescus". Then **relation patterns** (`PATTERNS`, data: a world can add verbs) are matched over the tagged
sentence, with its dated clauses lifted out, and each match is a claim.

**Names** resolve against the run. A stated house or town is a hard filter: "Cara of House Sivis" when
House Sivis has no Cara is a claim that she is of it, and false. Past those, a name several people share
is narrowed, in order, by the document's earlier mention of that name, by the people of the sentence's
events, and by who was alive in the sentence's year (soft filters, each kept only if it leaves someone).
A name still shared is **ambiguous**, reported with its candidates, so the prose can be repaired.

**Dates:** a sentence's own date, else the latest one stated earlier in its paragraph (a chronicle's
"**4A 2.**" lead). **`claims` blocks** (a fenced block, info string `claims`, of JSON lines `{"pred",
"args", "date"?}`, ids or names) are read verbatim, for exact checking.

`extract(run, text)` returns the sentences, each with its claims (`{pred, args, date, by}`) and its
unresolved mentions. Judging is `renasci.story.check`.
"""

from __future__ import annotations

import json
import re

from renasci.story.text import noun

CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f§]")
FENCE = re.compile(r"^```[ \t]*(\w*)[^\n]*\n(.*?)^```[ \t]*$", re.M | re.S)
TOKEN = r"§{k}\d+§"
SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(§])")

# the relation patterns: {role:KINDS} is a tagged mention (P person, H house, E event, D date; X: a literal)
PATTERNS: dict[str, list[str]] = {
    "killed": [
        r"{by:PH} (?:killed|slew|murdered|poisoned|struck down|cut down|did away with|put an end to) {victim:P}",
        r"{victim:P} (?:was|had been) (?:killed|slain|murdered|poisoned|struck down|cut down|done away with) by {by:PH}",
        r"{victim:P} died\b(?:[^§.;]|§[LD]\d+§)*?,? (?:killed|slain|murdered|struck down) by {by:PH}",
        r"{victim:P} (?:died|fell) (?:at|by) the hands? of {by:PH}",
        r"{victim:P} fell to {by:PH}",
        r"the (?:killer|murderer|slayer) of {victim:P} was {by:PH}",
        r"{by:PH} was the (?:killer|murderer|slayer) of {victim:P}",
        r"{victim:P} was killed(?:[^§.;]|§[LD]\d+§)*?, by {by:PH}",
    ],
    "caused": [
        r"{by:PH} (?:caused|brought about|was behind|were behind|was responsible for|were responsible for|engineered|arranged) {event:E}",
        r"{event:E} was (?:caused|brought about|engineered|arranged) by {by:PH}",
        r"{event:E} was the (?:doing|work) of {by:PH}",
    ],
    "fault": [
        r"{event:E} was the fault of {party:PHX}",
        r"{party:PH} (?:was|were) to blame for {event:E}",
        r"the fault for {event:E} lay with {party:PHX}",
    ],
    "married": [
        r"{a:P} (?:married|wed) {b:P}",
        r"{a:P} and {b:P} (?:were married|married|wed)",
        r"{a:P} took {b:P} (?:as|to) (?:wife|husband|spouse)",
        r"{a:P},? the (?:wife|husband|spouse) of {b:P}",
        r"{a:P} was (?:married|wed) to {b:P}",
    ],
    "died_in": [
        r"{who:P} (?:died|perished|passed away)\b",
        r"{who:P} (?:was|had been) (?:killed|slain|murdered|struck down|cut down)",
        r"{who:P} fell (?:in a duel|in battle|to)",
    ],
    "ruled": [
        r"{who:P} (?:ruled|led|headed) {house:H} from {date:D}",
        r"{who:P} became (?:the )?head of {house:H}",
        r"{who:P} succeeded {before:P} as (?:the )?head of {house:H}",
        r"{who:P} took (?:up )?the headship of {house:H}",
        r"{who:P} succeeded {before:P}",
    ],
}
NOT_ACTING = {"was", "were", "is", "are", "had", "has", "died", "perished", "fell", "and", "or", "who", "whose",
              "of", "lay", "remained", "never", "did", "would", "could", "might", "in", "at", "by", "to", "with",
              "for", "from", "as", "the", "a", "an", "passed", "lies", "rests", "rested", "slept", "haunted", "s"}
ACTING = re.compile(r"(?:^|, |; | and | then )§P(\d+)§ ([a-z]+)\b")
EVENT_WORDS = {  # (event nouns beyond `text.noun`: data, a world can add)
    "ward.failure": ["ward failure", "failure of the wards", "fall of the wards", "wards' failure", "failing of the wards"],
    "ward.sabotage": ["sabotage of the wards", "ward sabotage", "sabotage", "cracking of the ward-stones"],
    "ward.contract_lost": ["lost ore contract", "loss of the ore contract", "ore contract"],
    "ward.testimony": ["testimony about the wards", "ward testimony"],
}
UNNAMED = ("people.",)
CLAUSES = re.compile(r", and |; |, but |, while |, then | and then ")
RELTIME = re.compile(r"\b(?:later|earlier|before|afterwards?|ago|since|the (?:next|following|previous) "
                     r"(?:year|season|spring|summer|autumn|winter))\b", re.I)
REPORTED = re.compile(r"\b(?:said|claimed|believed|whispered|rumou?red|thought|insisted|alleged|according to)\b", re.I)  # (events too many to name by noun: a death is "the death of Jory")


def _clean(text: str) -> str:
    text = CONTROL.sub(" ", text).replace("\ufeff", "").replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return text.replace("—", ", ").replace("–", "-")


def _strip_markdown(par: str) -> str:
    par = re.sub(r"(\*\*|__|\*|_|`)", "", par)
    return re.sub(r"^\s*(?:[-+>]|\d+\.)\s+", "", par, flags=re.M)


class Lexicon:
    """What a run's names, places, houses, events and dates look like in prose, compiled once."""

    def __init__(self, run):
        self.run = run
        ppl = {i: e for i, e in run.ents.items() if e["kind"] == "person"}
        self.people = ppl
        self.byname: dict[str, list[str]] = {}
        for i in sorted(ppl):
            if ppl[i]["fields"].get("name"):  # (a world may leave people unnamed)
                self.byname.setdefault(ppl[i]["fields"]["name"], []).append(i)
        self.house_ids = {_clean(run.names(h)): h for h in sorted(run.names.houses) if run.names(h)}
        self.place_ids: dict[str, str] = {}
        for i, n in sorted(run.names.names.items()):
            if i in run.ents and run.ents[i]["kind"] in ("person", "house", "office", "tie", "ambition", "scheme"):
                continue
            if n and n not in self.house_ids and i not in run.names.houses and n not in self.byname:
                self.place_ids.setdefault(_clean(n), i)
        self.re_place = _alternation(self.place_ids)
        self.re_house = re.compile(r"\bHouse (" + "|".join(map(re.escape, sorted(self.house_ids, key=len, reverse=True))) + r")\b") \
            if self.house_ids else None
        self.re_person = _alternation(self.byname)
        cal = run.manifest.get("meta", {}).get("calendar") or {}
        self.ages = {a["abbrev"]: a["index"] for a in cal.get("ages", [])}
        self.months = [n for _, n in cal.get("months", [])]
        self.age_names = {a["name"].lower(): a["index"] for a in cal.get("ages", [])}
        seasons = "|".join(re.escape(s[0]) for s in cal.get("seasons", [])) or "Spring|Summer|Autumn|Winter"
        ab = "|".join(map(re.escape, self.ages)) or r"\d+A"
        nm = "|".join(map(re.escape, (a["name"] for a in cal.get("ages", [])))) or "Age"
        self.re_date = re.compile(
            rf"\b(?P<ab>{ab}) (?P<y>\d+)(?: m(?P<m>\d+) d(?P<d>\d+)| (?:{seasons})\b)?"
            rf"|\b(?:the )?year (?P<y2>\d+) of the (?P<nm>{nm})\b"
            rf"|\b(?:the )?(?P<y3>\d+)(?:st|nd|rd|th) year of the (?P<nm3>{nm})\b", re.I)
        words: dict[str, list[str]] = {}
        types = sorted({e["type"] for e in run.events})
        for t in types:
            if t.startswith(UNNAMED) or t.startswith(("belief.", "engine.", "lod.", "ripple.")):
                continue
            for w in EVENT_WORDS.get(t, []) + [noun({"type": t})[4:]]:
                words.setdefault(w.lower(), [])
                if t not in words[w.lower()]:
                    words[w.lower()].append(t)
        self.event_words = words
        self.re_event = re.compile(r"\b(?:the )?(" + "|".join(map(re.escape, sorted(words, key=len, reverse=True))) + r")\b", re.I) \
            if words else None
        self.by_type: dict[str, list[dict]] = {}
        for e in run.events:
            self.by_type.setdefault(e["type"], []).append(e)
        self.patterns = [(pred, i, _compile(t)) for pred, ts in PATTERNS.items() for i, t in enumerate(ts)]

    def date(self, m: re.Match) -> list:
        if m.group("ab"):
            age, y = self.ages.get(m.group("ab"), self.ages.get(m.group("ab").upper())), int(m.group("y"))
            month, day = int(m.group("m") or 0), int(m.group("d") or 0)
            if 1 <= month <= len(self.months) and 1 <= day <= self.months[month - 1]:
                return [age, y, sum(self.months[:month - 1]) + day - 1]
            return [age, y]
        y = m.group("y2") or m.group("y3")
        return [self.age_names.get((m.group("nm") or m.group("nm3")).lower()), int(y)]

    def parse_date(self, text: str) -> list | None:
        m = self.re_date.search(_clean(text))
        return self.date(m) if m else None


def _alternation(names) -> re.Pattern | None:
    if not names:
        return None
    return re.compile(r"(?<![\w§])(" + "|".join(map(re.escape, sorted(names, key=len, reverse=True))) + r")(?![\w§])")


def _compile(template: str) -> re.Pattern:
    def slot(m):
        name, kinds = m.group(1), m.group(2)
        tok = TOKEN.format(k=f"[{kinds.replace('X', '')}]")
        if "X" in kinds:
            return rf"(?P<{name}>{tok}(?!')|(?:the |a |an )?[a-z][a-z' -]*[a-z])"
        return rf"(?P<{name}>{tok})(?!')"  # (not a possessive: "Jory's killer" is not Jory
    return re.compile(re.sub(r"\{(\w+):([A-Z]+)\}", slot, template), re.I)


class Doc:
    """One text's extraction: names it has already settled (a later bare "Cara" is the same Cara)."""

    def __init__(self, lex: Lexicon):
        self.lex, self.run = lex, lex.run
        self.memory: dict[str, str] = {}

    # ------------------------------------------------------------ tagging

    def tag(self, s: str) -> tuple[str, dict]:
        lex, m = self.lex, {}
        n = [0]

        def put(kind, value):
            key = f"§{kind}{n[0]}§"
            n[0] += 1
            m[key] = {"kind": kind, **value}
            return key

        s = lex.re_date.sub(lambda x: put("D", {"date": lex.date(x), "text": x.group(0)}), s)
        if lex.re_place:
            s = lex.re_place.sub(lambda x: put("L", {"id": lex.place_ids[x.group(1)], "text": x.group(1)}), s)
        if lex.re_house:
            s = lex.re_house.sub(lambda x: put("H", {"id": lex.house_ids[x.group(1)], "text": x.group(0)}), s)
        s = re.sub(r"\bthe (?:death|murder|killing|slaying) of (?=§|[A-Z])", "the death of ", s, flags=re.I)
        if lex.re_event:
            s = lex.re_event.sub(lambda x: put("E", {"words": x.group(1).lower(), "text": x.group(0)}), s)
        if lex.re_person:
            s = lex.re_person.sub(lambda x: put("P", {"name": x.group(1), "text": x.group(1)}), s)
        # (qualifiers: merged into the mention they qualify)
        def house_of(x):
            p = x.group(1)
            m[p]["house"] = m[x.group(2) or x.group(3) or x.group(4)]["id"]
            return p
        s = re.sub(r"(§P\d+§)(?:, of (§H\d+§)(?:,|(?=[.;!?]|$))| of (§H\d+§)| \((§H\d+§)\))", house_of, s)

        def house_first(x):
            m[x.group(2)]["house"] = m[x.group(1)]["id"]
            return x.group(2)
        s = re.sub(r"(§H\d+§)'s (§P\d+§)", house_first, s)

        def town(x):
            m[x.group(1)]["place"] = m[x.group(2)]["id"]
            return x.group(1)
        s = re.sub(r"(§P\d+§),? of (§L\d+§),?", town, s)

        def death_of(x):
            return put("E", {"death_of": x.group(1), "text": "the death of"})
        s = re.sub(r"the death of (§P\d+§)", death_of, s, flags=re.I)

        def event_where(x):
            e = m[x.group(1)]
            if x.group(2):
                e["place"] = m[x.group(2)]["id"]
            if x.group(3):
                e["date"] = m[x.group(3)]["date"]
            return x.group(1)
        s = re.sub(r"(§E\d+§)(?:,? (?:at|in|near|on the road at|outside) (§L\d+§))?(?:,? (?:in|of|during) (§D\d+§))?", event_where, s)
        return s, m

    # ------------------------------------------------------------ resolving

    def _alive(self, pid: str, date: list) -> bool:
        f = self.lex.people[pid]["fields"]
        born, died = f.get("born"), self.run.died.get(pid)
        return (not born or born[:2] <= date[:2]) and (not died or died[:2] >= date[:2])

    def _lived(self, pid: str, place: str) -> bool:
        return place == self.lex.people[pid]["fields"].get("place") or any(p == place for _, p in self.run.residence(pid))

    def person(self, mention: dict, date: list | None, involved: set[str], places: set[str] = frozenset()) -> dict:
        name = mention["name"]
        cands = list(self.lex.byname.get(name, []))
        stated = bool(mention.get("house") or mention.get("place"))
        if mention.get("house"):
            cands = [c for c in cands if self.run.houses.get(c) == mention["house"]]
            if not cands:
                return {"ids": [], "why": "house"}
        if mention.get("place"):
            cands = [c for c in cands if self._lived(c, mention["place"])]
            if not mention.get("house"):  # ("Cole of Lux Oescus": a commoner; a house's own are named by it)
                cands = [c for c in cands if not self.run.houses.get(c)] or cands
            if not cands:
                return {"ids": [], "why": "place"}
        if len(cands) > 1 and not stated and self.memory.get(name) in cands:
            cands = [self.memory[name]]
        for narrow in ((lambda c: c in involved), (lambda c: any(self._lived(c, p) for p in places)),
                       (lambda c: date is not None and self._alive(c, date))):
            if len(cands) > 1:
                cands = [c for c in cands if narrow(c)] or cands
        if len(cands) == 1:
            self.memory[name] = cands[0]
        return {"ids": cands, "why": None if len(cands) == 1 else "ambiguous"}

    def event(self, mention: dict, people: dict) -> list[str]:
        if "death_of" in mention:
            who = people.get(mention["death_of"], {}).get("ids", [])
            return [d["id"] for p in who[:1] for d in self.run.log.deaths.get(p, [])][:1] if len(who) == 1 else []
        found = []
        for t in self.lex.event_words.get(mention["words"], []):
            for e in self.lex.by_type.get(t, []):
                if mention.get("place") and e.get("place") != mention["place"]:
                    continue
                if mention.get("date") and e["date"][:2] != mention["date"][:2]:
                    continue
                found.append(e["id"])
        return found

    def candidates(self, ids: list[str]) -> list[dict]:
        out = []
        for i in ids[:12]:
            f = self.lex.people[i]["fields"]
            out.append({"id": i, "name": self.run.names.full(i), "house": f.get("house"), "born": f.get("born"),
                        "died": self.run.died.get(i)})
        return out

    # ------------------------------------------------------------ a sentence

    def sentence(self, text: str, context: list | None) -> dict:
        tagged, m = self.tag(text)

        def first_date(s: str):
            found = [m[k]["date"] for k in re.findall(r"§D\d+§", s) if m[k]["date"][0] is not None]
            return found[0] if found else None

        rel: list[str] = []  # ("Brak, who killed Hask in 4A 12, fell ...": the relative clause is its own, dated
                             # only by itself)
        def lift(x):
            rel.append(f"{x.group(1)} {x.group(2)}")
            return x.group(1)
        main = re.sub(r"(§P\d+§), (?:who|whom) ([^,]+),", lift, tagged)
        own = first_date(main)
        relative = own is None and bool(RELTIME.search(main))  # ("Two years later ...": not the paragraph's year)
        date = own if own is not None else (None if relative else context)
        units = [(c, first_date(c) or (None if RELTIME.search(c) and own is None else date))
                 for c in CLAUSES.split(main) if c.strip()]
        units += [(c, first_date(c)) for c in rel]
        events = {k: self.event(v, {}) for k, v in m.items() if v["kind"] == "E" and "death_of" not in v}
        involved = {x for ids in events.values() if len(ids) == 1 for x in _people_of(self.run.by_id[ids[0]])}
        places = {v["id"] for v in m.values() if v["kind"] == "L"}
        people = {k: self.person(v, date, involved, places) for k, v in m.items() if v["kind"] == "P"}
        events |= {k: self.event(v, people) for k, v in m.items() if v["kind"] == "E" and "death_of" in v}
        claims, unresolved, seen = [], [], set()

        def value(tok: str):
            v = m.get(tok)
            if v is None:  # (a literal party: "the guild's stones", without its article)
                return re.sub(r"^(?:the|a|an) ", "", tok.strip(), flags=re.I), None
            if v["kind"] == "P":
                r = people[tok]
                return (r["ids"][0], None) if len(r["ids"]) == 1 else (None, {"mention": v["text"], "kind": "person",
                        "why": r["why"], "candidates": self.candidates(r["ids"] or self.lex.byname.get(v["name"], []))})
            if v["kind"] == "E":
                ids = events[tok]
                return (ids[0], None) if len(ids) == 1 else (None, {"mention": v["text"], "kind": "event",
                        "why": "ambiguous" if ids else "none", "candidates": [{"id": i, "date": self.run.by_id[i]["date"],
                        "place": self.run.by_id[i].get("place")} for i in ids[:12]]})
            if v["kind"] == "H":
                return v["id"], None
            if v["kind"] == "D":
                return v["date"], None
            return v.get("id"), None

        def add(pred, args, by, when):
            key = json.dumps([pred, args, when], sort_keys=True)
            if key not in seen:
                seen.add(key)
                claims.append({"pred": pred, "args": args, "date": when, "by": by})

        for clause, cdate in units:
            if REPORTED.search(clause):  # ("Some said ...": a report of what was believed, not a claim)
                continue
            self._clause(_flat(clause), cdate, people, value, add, unresolved, claims)
        for k, v in m.items():  # (a stated house or town nobody of that name belongs to)
            if v["kind"] == "P" and people[k]["why"] in ("house", "place"):
                where = v.get("house") if people[k]["why"] == "house" else v.get("place")
                add("member" if people[k]["why"] == "house" else "lived_in",
                    {"who": v["name"], "of": where}, "qualifier", None)
        return {"text": text, "date": own, "relative": relative, "claims": claims, "unresolved": unresolved}

    def _clause(self, flat, date, people, value, add, unresolved, claims):
        for pred, i, rx in self.lex.patterns:
            for hit in rx.finditer(flat):
                args, bad = {}, []
                for role, tok in hit.groupdict().items():
                    if tok is None:
                        continue
                    v, problem = value(tok)
                    if problem:
                        bad.append(problem)
                    elif role == "date":
                        continue
                    else:
                        args[role] = v
                when = value(hit.group("date"))[0] if "date" in hit.groupdict() and hit.group("date") else date
                if pred == "died_in" and when is None:
                    continue
                if bad:
                    unresolved += [b for b in bad if b not in unresolved]
                    continue
                if pred == "married":
                    args = dict(zip(("a", "b"), sorted((args["a"], args["b"]))))
                if pred == "ruled" and "house" not in args:
                    args["house"] = self.run.houses.get(args["who"])
                    if args["house"] is None:
                        continue
                add(pred, args, f"{pred}.{i}", when)
        if date is not None:
            for hit in ACTING.finditer(flat):
                tok = f"§P{hit.group(1)}§"
                if hit.group(2) in NOT_ACTING or tok not in people or len(people[tok]["ids"]) != 1:
                    continue
                if any(c["pred"] == "killed" and c["args"].get("victim") == people[tok]["ids"][0] for c in claims):
                    continue
                add("alive_at", {"who": people[tok]["ids"][0]}, "acting", date)


def _flat(clause: str) -> str:
    """A clause with its dates lifted out (they're the claims' dates), commas that close other clauses kept."""
    c = re.sub(r"^\s*(?:in|during|by)\s+§D\d+§,?\s*", "", clause, flags=re.I)
    c = re.sub(r"^\s*§D\d+§\s*[.:,;-]?\s*", "", c)
    c = re.sub(r", (?:in|during|by) §D\d+§,", "", c, flags=re.I)  # ("Gwen, in 4A 5, killed ...")
    c = re.sub(r",? (?:in|during|by|of) §D\d+§", "", c, flags=re.I)
    c = re.sub(r"§D\d+§", "", c)
    return re.sub(r"\s+", " ", c).strip().lstrip(", ")


def _people_of(ev: dict) -> set[str]:
    return {x for ms in (ev.get("roles") or {}).values() for x in ms}


def _block(doc: Doc, body: str) -> list[dict]:
    """A `claims` block: JSON lines {pred, args, date?}; an arg is an id, or a name or event phrase."""
    out = []
    for line in body.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            c = json.loads(line)
        except ValueError:
            out.append({"text": line, "date": None, "claims": [], "unresolved": [{"mention": line, "kind": "block",
                        "why": "not JSON", "candidates": []}]})
            continue
        if not isinstance(c, dict) or not isinstance(c.get("args"), dict) or not isinstance(c.get("pred"), str):
            out.append({"text": line, "date": None, "claims": [], "unresolved": [{"mention": line, "kind": "block",
                        "why": "not a claim", "candidates": []}]})
            continue
        args, bad = {}, []
        date = c.get("date")
        if isinstance(date, str):
            date = doc.lex.parse_date(date)
        elif not (date is None or (isinstance(date, list) and 2 <= len(date) <= 3
                                   and all(isinstance(x, int) and not isinstance(x, bool) for x in date))):
            bad.append({"mention": json.dumps(date), "kind": "block", "why": "a date is \"4A 5\" or [age, year]",
                        "candidates": []})
        for role, v in sorted(c["args"].items()):
            if not isinstance(v, str):
                bad.append({"mention": json.dumps(v), "kind": "block", "why": f"{role} is not an id or a name",
                            "candidates": []})
                continue
            if v in doc.run.ents or v in doc.run.by_id:
                args[role] = v
                continue
            tagged, m = doc.tag(_clean(v))  # (a name or an event phrase)
            toks = [k for k in m if k in tagged]
            kind = m[toks[0]]["kind"] if len(toks) == 1 else None
            res = doc.person(m[toks[0]], None, set()) if kind == "P" else None
            found = doc.event(m[toks[0]], {}) if kind == "E" else []
            if res and len(res["ids"]) == 1:
                args[role] = res["ids"][0]
            elif kind == "E" and len(found) == 1:
                args[role] = found[0]
            elif kind == "H":
                args[role] = m[toks[0]]["id"]
            else:
                args[role] = v
                ids = res["ids"] if res else found
                bad.append({"mention": v, "kind": {"P": "person", "E": "event"}.get(kind, "block"),
                            "why": (res or {}).get("why") or ("ambiguous" if ids else "unknown"),
                            "candidates": doc.candidates(ids or doc.lex.byname.get(m[toks[0]].get("name", ""), []))
                            if kind == "P" else [{"id": i} for i in ids[:12]]})
        if c["pred"] == "married" and {"a", "b"} <= set(args):
            args = {**args, **dict(zip(("a", "b"), sorted((args["a"], args["b"]))))}
        out.append({"text": line, "date": date, "claims": [] if bad else [{"pred": c["pred"], "args": args, "date": date, "by": "block"}],
                    "unresolved": bad})
    return out


def extract(run, text: str, lexicon: Lexicon | None = None) -> list[dict]:
    """The text's sentences, in order, each with its claims and unresolved mentions."""
    doc = Doc(lexicon or Lexicon(run))
    text = _clean(text).replace("\r\n", "\n").replace("\r", "\n")
    if text.startswith("---\n"):
        end = text.find("\n---", 4)
        text = text[end + 4:] if end >= 0 else text
    out: list[dict] = []
    pos = 0
    for f in FENCE.finditer(text):
        out += _prose(doc, text[pos:f.start()])
        if f.group(1).lower() == "claims":
            out += _block(doc, f.group(2))
        pos = f.end()
    out += _prose(doc, text[pos:])
    for i, s in enumerate(out):
        s["n"] = i + 1
    return out


LIST_ITEM = re.compile(r"^(?:[-+*>]|\d+\.)\s+")


def _units(text: str):
    """Paragraphs, and each list item and table row on its own (a bullet's date is not the next one's)."""
    for par in re.split(r"\n\s*\n", text):
        buf: list[str] = []
        for line in par.splitlines():
            s = line.strip()
            if not s or s.startswith("#") or (s.startswith("|") and re.fullmatch(r"[|:\s-]+", s)):
                continue
            if LIST_ITEM.match(s) or s.startswith("|"):
                if buf:
                    yield " ".join(buf)
                    buf = []
                s = LIST_ITEM.sub("", s)
                yield "; ".join(c.strip() for c in s.strip("|").split("|") if c.strip()) if s.startswith("|") else s
            else:
                buf.append(s)
        if buf:
            yield " ".join(buf)


def _prose(doc: Doc, text: str) -> list[dict]:
    out = []
    for par in _units(text):
        par = _strip_markdown(par).strip()
        context = None
        for s in SENTENCE.split(par):
            s = s.strip()
            if not s:
                continue
            got = doc.sentence(s, context)
            if got["date"] is not None:
                context = got["date"]
            elif got["relative"]:
                context = None  # ("Two years later": what follows is no longer that year)
            if got["claims"] or got["unresolved"] or re.search(r"[a-z]", s):
                out.append(got)
    return out
