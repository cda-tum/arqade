"""Overquqed: two chefs cook real co-op rounds, driven by the game's own kitchen AI.

The menus are walked with the pads like two players would: A on the title,
P2 joins, then a kitchen from the level select. In a round the game's own
kitchen bot (overquqed.bot.Bot, the one its attract demo uses) plans the
orders and returns one ChefInput per chef, and this bot presses exactly that
on the two pads: the stick to walk, A to pick up and put down, B tapped or
held on the stations. The game sees two people playing.

On top of that, a chef with nothing to do walks over to a fridge, ready for
the next order, as people do (not in the Cosmic Cafe, where a chef waiting
there would block the other one's second fetch for the Waffle Iron).

The capture visits two kitchens, quitting the first one through the pause
menu (Start, up, A: a few frames on screen).
"""

from overquqed.bot import Bot as KitchenBot
from overquqed.levels import LEVELS
from overquqed.stations import TAP_GATES
from overquqed.world import IDLE

# (level-select index, seconds of kitchen time to cook there before leaving)
KITCHENS = ((3, 42.0), (1, None))  # Cosmic Cafe, then the Superconducting Snack Bar

SECONDS = 85.0
SKIP = 0.6  # the Cosmic Cafe round starts at 0.6 s
HIGHLIGHTS = [
    21.2,  # Cosmic Cafe: both chefs on the two-chef Waffle Iron, ENTANGLED!
    37.2,  # Cosmic Cafe: a Bell tray carried to the pass and served
    29.9,  # Cosmic Cafe: cosmic-ray warning, then the hit
    55.0,  # Snack Bar: |-> carried over and served, receipt slides in
    5.0,   # Cosmic Cafe: Hadamard Blender, |-> served
    51.0,  # Snack Bar: Pauli-X Flipper, bowl on to the Blender
    77.3,  # Snack Bar: |+> served
    13.2,  # Cosmic Cafe: blending |+> for the Waffle Iron
]

DT = 1 / 60
MENU_GAP = 6  # frames between two menu presses


class Bot:
    def __init__(self, pads, rng):
        self.pads, self.rng = pads, rng
        self.visit = 0
        self.world = None
        self.kitchen = None
        self.wait = 0

    def update(self, t):
        scene = self.pads.loop["self"].scene
        name = type(scene).__name__
        if name == "RoundScene" and not scene.paused:
            self.cook(scene)
            return
        # Menus: one press (a single frame is enough) every MENU_GAP frames.
        self.pads.release_all()
        if self.wait > 0:
            self.wait -= 1
            return
        self.wait = MENU_GAP
        if name == "TitleScene":
            self.pads.hold(0, "a")
        elif name == "JoinScene":
            self.pads.hold(0 if 1 in scene.joined else 1, "a")
        elif name == "LevelSelectScene":
            want = KITCHENS[min(self.visit, len(KITCHENS) - 1)][0]
            down = (want - scene.index) % len(LEVELS)
            if down == 0:
                if scene.t > 0.2:
                    self.pads.hold(0, "a")
            else:
                self.pads.stick(0, 0.0, 1.0 if down <= len(LEVELS) // 2 else -1.0)
        elif name == "RoundScene":  # paused: QUIT TO MENU is the last item
            if scene.pause_index != 2:
                self.pads.stick(0, 0.0, -1.0)
            else:
                self.pads.hold(0, "a")

    def cook(self, scene):
        world = scene.world
        if world is not self.world:
            self.world, self.kitchen = world, KitchenBot(world)
        leave_after = KITCHENS[min(self.visit, len(KITCHENS) - 1)][1]
        if leave_after is not None and world.t >= leave_after:
            self.pads.release_all()
            self.pads.hold(0, "start")
            self.visit += 1
            self.wait = MENU_GAP
            return
        inputs = self.kitchen.update(DT)
        if not self.kitchen.jobs and not world.level.two_chef_press:
            self.stand_by(world, inputs)
        for player, (chef, inp) in enumerate(zip(world.chefs, inputs)):
            self.pads.stick(player, float(inp.move[0]), float(inp.move[1]))
            # A: the game wants a fresh press each time, so a pick asked for
            # while A is still down from the last one lets go first.
            if inp.pick and not self.pads.held(player, "a"):
                self.pads.hold(player, "a")
            else:
                self.pads.release(player, "a")
            # B: held for the Blender, the Sink and the Waffle Iron; a tap
            # station needs a fresh press, like A.
            station = world.station_at(chef.target)
            tap = station is not None and station.kind in TAP_GATES
            if inp.use_pressed and tap and self.pads.held(player, "b"):
                self.pads.release(player, "b")
            elif inp.use or inp.use_pressed:
                self.pads.hold(player, "b")
            else:
                self.pads.release(player, "b")

    def stand_by(self, world, inputs):
        """No order to cook: empty-handed chefs walk to their nearest fridge."""
        for idx, chef in enumerate(world.chefs):
            if chef.held is None and inputs[idx] == IDLE:
                fridge = self.kitchen._nearest("fridge", idx)
                move = fridge and self.kitchen._goto(idx, fridge, DT)
                if move is not None:
                    inputs[idx] = move
