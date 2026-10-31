"""One extension that touches every kind of content (notes/extending.md walks through it; a test runs it).

Put `extensions = ["ext_pilgrims"]` under `[run]` in a recipe and run from this folder. It adds pilgrims: a vow,
a bell that tolls yearly, a mark for the devout, a drive, a harsher verdict and a looser line of succession.
"""

from renasci.analysis.graph import Link
from renasci.core.events import EventType
from renasci.core.pools import Reaction, Wording
from renasci.core.systems import System
from renasci.marks import Mark
from renasci.people.actions import Action
from renasci.people.ambitions import Ambition, Formation
from renasci.people.courts import Verdict
from renasci.people.drives import Drive
from renasci.people.houses import SuccessionRule
from renasci.people.planner import Goal
from renasci.story.cards import Person

VOWED = EventType("pilgrim.vowed", 1, roles={"who": (1, 1)}, payload={})
BLESSED = EventType("pilgrim.blessed", 1, roles={"who": (1, 1)}, payload={})
TOLLED = EventType("pilgrim.tolled", 1, roles={"place": (1, 1)}, payload={})


class TakeVow(Action):
    """Something a person can do in a scheme: the planner finds it by what it `achieves`."""

    name, achieves, duration_days = "TakeVow", "vowed", 30

    def possible(self, ctx, actor, target, scheme):
        return True

    def odds(self, ctx, actor, target, scheme):
        return 1.0

    def succeed(self, ctx, actor, target, scheme, event):
        ctx.emit("pilgrim.vowed", {"who": (actor,)}, purpose="vow", actor=actor)


class Pilgrimage(Ambition):
    """Something a person can want. `subgoals` are planner tags; the planner works out the actions."""

    name, cooldown_years, stakes = "Pilgrimage", 50, 2.0
    titles = {"*": "The pilgrimage of {owner}"}

    def eligible(self, ctx, person):
        return Formation(ctx.get(person, "place"), ("drive", "status"))

    def urge(self, ctx, person):
        return 1.0

    def subgoals(self, ctx, amb):
        return [frozenset({"vowed"})]

    def text(self, ctx, owner, target):
        return "make a pilgrimage"


class Bell(System):
    """A whole new mechanic: it joins every age's rules. For a stock another system reads, see `core/stocks.py`."""

    name, cadence = "pilgrim.bell", "yearly"
    reads = frozenset({"ids:settlement"})
    event_types = (TOLLED,)

    def run(self, ctx):
        place = ctx.ids("settlement")[0]
        ctx.emit("pilgrim.tolled", {"place": (place,)}, purpose="toll", actor=place)


class Faith(Drive):
    """A need people feel, kept in `drives` and read by ambitions."""

    name = "faith"

    def level(self, ctx, person, settlement):
        return 0.5


class Penance(Verdict):
    """A thing a court can decide."""

    name = "penance"
    writes = frozenset({"favour"})

    def weight(self, ctx, case):
        return 0.5

    def carry_out(self, ctx, case, causes):
        ctx.set(case.accused, "favour", 0.0)


class Tanistry(SuccessionRule):
    """A house names this as its `rule` in the scenario."""

    name, male_first = "tanistry", False


class Pilgrim(Person):
    """A kind of card for `renasci gen`. This one only renames `Person`: override `fits` and `card` to change it."""

    name = "pilgrim"


def bless(ctx, event):
    who = event.roles["who"][0]
    ctx.emit("pilgrim.blessed", {"who": (who,)}, purpose="bless", actor=who)


def extend(pools):
    pools.actions.add(TakeVow)
    pools.ambitions.add(Pilgrimage)
    pools.event_types.add(VOWED)
    pools.event_types.add(BLESSED)
    pools.systems.add(Bell)
    pools.drives.add(Faith)
    pools.verdicts.add(Penance)
    pools.succession.add(Tanistry)
    pools.generators.add(Pilgrim)
    pools.goals.add(Goal("devout", lambda ctx, owner, ref, scheme: bool(ctx.get(owner, "acquired"))))
    # (`needs` is a count on the subject: nothing here raises `faith_shown`, so a system of yours would have to)
    pools.marks.add(Mark("devout", "devout", ("person",), {"faith_shown": 3}, {"charm": 0.1}))
    pools.reactions.add(Reaction("pilgrim.blessing", "pilgrim.vowed", bless, emits=("pilgrim.blessed",)))
    pools.links.add(Link("pilgrim.vowed", "pilgrim.blessed", "a vow is blessed"))
    pools.wording.add(Wording("pilgrim.vowed", lambda ev, n: f"{n.full(ev['roles']['who'][0])} took a pilgrim's vow"))
