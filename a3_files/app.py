"""
Simple 2d world where the player can interact with the items in the world.
"""

__author__ = "Jinyuan Chen"
__date__ = "2019/05/25"
__version__ = "1.1.0"
__copyright__ = "The University of Queensland, 2019"

import tkinter as tk
import random
from collections import namedtuple

import pymunk

from block import Block, ResourceBlock, BREAK_TABLES, LeafBlock, TrickCandleFlameBlock
from grid import Stack, Grid, SelectableGrid, ItemGridView
from item import Item, SimpleItem, HandItem, BlockItem, MATERIAL_TOOL_TYPES, TOOL_DURABILITIES
from player import Player
from dropped_item import DroppedItem
from crafting import GridCrafter, CraftingWindow
from world import World
from core import positions_in_range
from game import GameView, WorldViewRouter
from mob import Bird, Mob
from physical_thing import BoundaryWall

import cmath

from tkinter import messagebox

BLOCK_SIZE = 2 ** 5
GRID_WIDTH = 2 ** 5
GRID_HEIGHT = 2 ** 4

# Task 3/Post-grad only:
# Class to hold game data that is passed to each thing's step function
# Normally, this class would be defined in a separate file
# so that type hinting could be used on PhysicalThing & its
# subclasses, but since it will likely need to be extended
# for these tasks, we have defined it here
GameData = namedtuple('GameData', ['world', 'player'])

SHEEP_GRAVITY_FACTOR = 100


class Sheep(Mob):
    """A friendly sheep,  move around randomly and do not damage the player"""

    def step(self, time_delta, game_data):
        """Advance this sheep by one time step

        See PhysicalThing.step for parameters & return"""

        if self._steps % 100 == 0:
            health_percentage = self._health / self._max_health
            z = cmath.rect(self._tempo * health_percentage, random.uniform(0, 2 * cmath.pi))

            dx, dy = z.real * 2, z.imag

            x, y = self.get_velocity()
            velocity = x + dx, y + dy - SHEEP_GRAVITY_FACTOR

            self.set_velocity(velocity)

        super().step(time_delta, game_data)

    def can_use(self):
        return False

    def use(self):
        pass

    def get_drops(self):
        """Drops a wool in sheep form 1 times

        See Block.get_drops for parameters & return"""
        self._sheep_wool = WoolBlock
        return self._sheep_wool.get_drops


BEE_GRAVITY_FACTOR = 200


class Bee(Mob):
    """ A bee swarms the player."""
    def step(self, time_delta, game_data):
        """Advance this bee by one time step

        See PhysicalThing.step for parameters & return"""

        if self._steps % 20 == 0:
            health_percentage = self._health / self._max_health
            z = cmath.rect(self._tempo * health_percentage, random.uniform(0, 2 * cmath.pi))

            dx, dy = z.real * 1.5, z.imag

            x, y = self.get_velocity()
            velocity = x + dx, y + dy - BEE_GRAVITY_FACTOR

            self.set_velocity(velocity)

        super().step(time_delta, game_data)

    def use(self):
        pass


class NewWorldViewRouter(WorldViewRouter):
    """
    Magical (sub)class used to facilitate drawing of different physical things on a canvas

    For a large system, separate classes could be used for each thing,
    but for simplicity's sake, we've opted to use a single class with
    multiple similar methods
    """
    _routing_table = [
        (Block, '_draw_block'),
        (TrickCandleFlameBlock, '_draw_mayhem_block'),
        (DroppedItem, '_draw_physical_item'),
        (Player, '_draw_player'),
        (Bird, '_draw_bird'),
        (BoundaryWall, '_draw_undefined'),
        (None.__class__, '_draw_undefined'),
        (Sheep, '_draw_sheep'),
        (Bee, '_draw_bee')
    ]

    def _draw_sheep(self, instance, shape, view):
        """Draw the sheep."""
        return [view.create_rectangle(shape.bb.left, shape.bb.top, shape.bb.right, shape.bb.bottom,
                                     fill='white', tag=('mod', 'sheep'))]

    def _draw_bee(self, instance, shape, view):
        """Draw the bee."""
        return [view.create_rectangle(shape.bb.left, shape.bb.top, shape.bb.right, shape.bb.bottom,
                                     fill='yellow', tag=('mob', 'bee'))]


def create_block(*block_id):
    """(Block) Creates a block (this function can be thought of as a block factory)

    Parameters:
        block_id (*tuple): N-length tuple to uniquely identify the block,
        often comprised of strings, but not necessarily (arguments are grouped
        into a single tuple)

    Examples:
        >>> create_block("leaf")
        LeafBlock()
        >>> create_block("stone")
        ResourceBlock('stone')
        >>> create_block("mayhem", 1)
        TrickCandleFlameBlock(1)
    """
    if len(block_id) == 1:
        block_id = block_id[0]
        if block_id == "leaf":
            return LeafBlock()
        elif block_id in BREAK_TABLES:
            return ResourceBlock(block_id, BREAK_TABLES[block_id])
        elif block_id == "crafting_table":
            return CraftingTableBlock(block_id, BREAK_TABLES["wood"])
        elif block_id == "diamond":
            return DiamondBlock(block_id, BREAK_TABLES["stone"])
        elif block_id == "wool":
            return WoolBlock(block_id, BREAK_TABLES["wood"])
        elif block_id == "bed":
            return BedBlock(block_id, BREAK_TABLES["wood"])
        elif block_id == "honey":
            return HoneyBlock("honey", BREAK_TABLES["wood"])
        elif block_id == "furnace":
            return Furnace(block_id, BREAK_TABLES["stone"])
        elif block_id == "hive":
            return HiveBlock(block_id, BREAK_TABLES["wood"])

    elif block_id[0] == 'mayhem':
        return TrickCandleFlameBlock(block_id[1])

    raise KeyError(f"No block defined for {block_id}")


def create_item(*item_id):
    """(Item) Creates an item (this function can be thought of as a item factory)

    Parameters:
        item_id (*tuple): N-length tuple to uniquely identify the item,
        often comprised of strings, but not necessarily (arguments are grouped
        into a single tuple)

    Examples:
        >>> create_item("dirt")
        BlockItem('dirt')
        >>> create_item("hands")
        HandItem('hands')
        >>> create_item("pickaxe", "stone")  # *without* Task 2.1.2 implemented
        Traceback (most recent call last):
        ...
        NotImplementedError: "Tool creation is not yet handled"
        >>> create_item("pickaxe", "stone")  # *with* Task 2.1.2 implemented
        ToolItem('stone_pickaxe')
    """
    if len(item_id) == 2:

        if item_id[0] in MATERIAL_TOOL_TYPES and item_id[1] in TOOL_DURABILITIES:
            if item_id[0] == "pickaxe" and item_id[1] == "stone":
                return ToolItem("stone_pickaxe", "pickaxe", 132)
            elif item_id[0] == "pickaxe" and item_id[1] == "diamond":
                return ToolItem("diamond_pickaxe", "pickaxe", 1562)
            elif item_id[0] == "pickaxe" and item_id[1] == "wood":
                return ToolItem('wood_pickaxe', "pickaxe", 60)
            elif item_id[0] == "axe" and item_id[1] == "wood":
                return ToolItem('wood_axe', "axe", 60)
            elif item_id[0] == "shovel" and item_id[1] == "wood":
                return ToolItem('wood_shovel', "shovel", 60)
            elif item_id[0] == "sword" and item_id[1] == "wood":
                return ToolItem('wood_sword', "sword", 60)
            elif item_id[0] == "axe" and item_id[1] == "stone":
                return ToolItem('stone_axe', "axe", 132)
            elif item_id[0] == "shovel" and item_id[1] == "stone":
                return ToolItem('stone_shovel', "shovel", 132)
            elif item_id[0] == "sword" and item_id[1] == "stone":
                return ToolItem('stone_sword', "sword", 132)
            elif item_id[0] == "bow" and item_id[1] == "arrow":
                return BowArrowItem('bow_arrow', 'arrow', 'inf')

    elif len(item_id) == 1:

        item_type = item_id[0]

        if item_type == "hands":
            return HandItem("hands")

        elif item_type == "bow":
            return SimpleItem("bow")

        elif item_type == "arrow":
            return SimpleItem("arrow")

        elif item_type == "dirt":
            return BlockItem(item_type)

        # Task 1.4 Basic Items: Create wood & stone here
        # ...

        elif item_type == "wood":
            return BlockItem(item_type)

        elif item_type == "stone":
            return BlockItem(item_type)

        elif item_type == "apple":
            return FoodItem(item_type, 2)

        elif item_type == "stick":
            return SimpleItem(item_type)

        elif item_type == "crafting_table":
            return BlockItem(item_type)

        elif item_type == "wool":
            return BlockItem(item_type)

        elif item_type == "bed":
            return BlockItem(item_type)

        elif item_type == "honey":
            return BlockItem(item_type)

        elif item_type == "furnace":
            return BlockItem(item_type)

        elif item_type == "diamond":
            return BlockItem(item_type)

        elif item_type == "swarming_bee":
            return Bee("_draw_bee", 5)

        elif item_type == "hive":
            return BlockItem(item_type)

    raise KeyError(f"No item defined for {item_id}")


# Task 1.3: Implement StatusView class here
# ...
class StatusView(tk.Frame):
    """ display information to the player about their status in the game"""

    def __init__(self, master, health, food):
        """Constructor

                Parameters:
                    master (tk.Tk): tkinter root widget
                """
        super().__init__(master)
        self._health_img = tk.PhotoImage(file="health_img.gif")

        self._health_image = tk.Label(self, image=self._health_img)
        self._health_image.pack(side=tk.LEFT)
        self._health_label = tk.Label(self, text="Health: {}".format(health))
        self._health_label.pack(side=tk.LEFT)

        self._food_img = tk.PhotoImage(file="food_img.gif")
        self._food_image = tk.Label(self, image=self._food_img)
        self._food_image.pack(side=tk.LEFT)
        self._food_label = tk.Label(self, text="Food: {}".format(food))
        self._food_label.pack(side=tk.LEFT)

    def set_health(self, health):
        """ A label to display the amount of health the player has remaining,
        with an image of a heart to the left."""

        self._health_label.config(text="Health: {}".format(round(health * 2) / 2))

    def set_food(self, food):
        """ A label to display the amount of food the player has remaining,
        with an image of a mushroom to the left. """
        self._food_label.config(text="Food: {}".format(round(food * 2) / 2))


class FoodItem(Item):
    """
     Given an item identifier and a strength
    """

    def __init__(self, item_id, strength):
        """
        :param item_id: str
        :param strength: float
        """

        super().__init__(id_=item_id)
        self._strength = strength

    def get_strength(self):
        """
         float: Returns the amount of food/health to be recovered by the player by when used
        """

        return float(self._strength)

    def place(self):
        """
        float: Returns an effect that represents an increase in the player's food/health
        """

        return [('effect', ('food', self._strength))]

    def can_attack(self):
        """(bool) Returns False, since BlockItems cannot be used to attack"""
        return False


class ToolItem(Item):
    """
    Given an item identifier, the type of tool it will be and the tool's durability.
    """

    def __init__(self, item_id, tool_type, durability):
        """

        :param item_id: str
        :param tool_type: str
        :param durability: float
        """
        super().__init__(id_=item_id)
        self._tool_type = tool_type
        self._durability = durability
        self._max_durability = durability

    def get_type(self):
        """
         str: Returns the tool's type.
        :return:str
        """
        return self._tool_type

    def get_durability(self):
        """
         float: Returns the tool's remaining durability.
        :return: float
        """
        return self._durability

    def get_max_durability(self):
        """
        float: Returns the tool's max durability.
        :return: float
        """

        return self._max_durability

    def can_attack(self):
        """
         bool: Returns True iff the tool is not depleted.

        :return: bool
        """

        if self._durability > 0:
            return True

    def attack(self, successful):
        """
        Attacks with the tool; if the attack was not successful,
        the tool's durability should be reduced by one.

        :param successful: bool
        :return:bool
        """

        if not successful:
            self._durability -= 1

    def place(self):
        """Places the item into the world in its block form

        Return:
            [tuple<str, tuple<str, ...>>]:
                    A list of EffectIDs resulting from placing this item. Each EffectID is a pair
                    of (effect_type, effect_sub_id) pair, where:
                      - effect_type is the type of the effect ('item', 'block', etc.)
                      - effect_sub_id is the unique identifier for an effect of a particular type
        """
        pass

    def is_stackable(self):
        """(bool) Returns True iff this item is stackable in the inventory/hotbar"""
        return False


class BowArrowItem(Item):
    """Define the bow and arrow tool."""

    _id = "arrow"

    _break_table = {
        "dirt": {
            "arrow": (0.1, False),
        },

        "wood": {
            "arrow": (0.1, True),
        },

        "stone": {
            "arrow": (0.1, False),
        }
    }

    def __init__(self, item_id, tool_type, durability):
        """
         Adding a bow & arrow tool to the game
        :param item_id: str
        :param tool_type: str
        :param durability: float
        """

        super().__init__(id_=item_id)
        self._tool_type = tool_type
        self._durability = durability
        self._max_durability = durability


    def get_type(self):
        """
        str: Returns the tool's type.
       :return:str
       """

        return self._tool_type

    def get_durability(self):
        """
          float: Returns the tool's remaining durability.
         :return: float
         """

        return float("inf")

    def get_max_durability(self):
        """
          float: Returns the tool's max durability.
         :return: float
         """

        return float("inf")

    def can_attack(self):
        """
         bool: Returns True iff the tool is not depleted.

        :return: bool
        """
        pass

    def attack(self, successful):
        """
        Attacks with the tool; if the attack was not successful,
        the tool's durability should be reduced by one.

        :param successful: bool
        :return:bool
        """
        return successful

    def place(self):
        """Places the item into the world in its block form

        Return:
            [tuple<str, tuple<str, ...>>]:
                    A list of EffectIDs resulting from placing this item. Each EffectID is a pair
                    of (effect_type, effect_sub_id) pair, where:
                      - effect_type is the type of the effect ('item', 'block', etc.)
                      - effect_sub_id is the unique identifier for an effect of a particular type
        """
        pass

    def is_stackable(self):
        """(bool) Returns True iff this item is stackable in the inventory/hotbar"""
        return False


class CraftingTableBlock(ResourceBlock):
    """
     Trigger the crafting table screen
    """

    def __init__(self, block_id, break_table):
        """
        Inherits from ResourceBlock
        :param block_id: str
        :param break_table: str
        """
        super().__init__(block_id, break_table)

    def get_drops(self, luck, correct_item_used):
        """Drops a itself in item form 1 times

        See Block.get_drops for parameters & return"""

        if correct_item_used:
            return [('item', (self._id,))] * 1

    def can_use(self):
        """(bool) Returns True"""
        return True

    def use(self):
        """Does the crafting table screen"""
        return ("crafting", "crafting_table")


class DiamondBlock(ResourceBlock):
    """Create a diamond block"""

    def __init__(self, block_id, break_table):
        """
        Create a diamond block'id
        :param block_id: str
        :param break_table: str
        """
        super().__init__(block_id, break_table)

    def get_drops(self, luck, correct_item_used):
        """Drops a itself in item form 1 times

        See Block.get_drops for parameters & return"""

        if correct_item_used:
            return [('item', (self._id,))] * 1

    def can_use(self):
        return False

    def use(self):
        pass


class WoolBlock(ResourceBlock):
    """
    Create a wool block
    """
    def __init__(self, block_id, break_table):
        super().__init__(block_id, break_table)

    def get_drops(self, luck, correct_item_used):
        """Drops a itself in item form 1 times

        See Block.get_drops for parameters & return"""

        if correct_item_used:
            return [('item', (self._id,))] * 1

    def can_use(self):
        return False

    def use(self):
        pass


class BedBlock(ResourceBlock):
    """Create a bed block"""

    def __init__(self, block_id, break_table):
        super().__init__(block_id, break_table)

    def get_drops(self, luck, correct_item_used):
        """Drops a itself in item form 1 times

        See Block.get_drops for parameters & return"""

        if correct_item_used:
            return [('item', (self._id,))] * 1

    def can_use(self):
        return False

    def use(self):
        pass


class HoneyBlock(ResourceBlock):
    """Create a honey block"""
    def __init__(self, block_id, break_table):
        super().__init__(block_id, break_table)

    def get_drops(self, luck, correct_item_used):
        """Drops a itself in item form 5 times

        See Block.get_drops for parameters & return"""

        if correct_item_used:
            return [('item', (self._id,))] * 5

    def can_use(self):
        return False

    def use(self):
        pass


class HiveBlock(ResourceBlock):
    """Create a hive block"""
    def __init__(self, block_id, break_table):
        super().__init__(block_id, break_table)

    def get_drops(self, luck, correct_item_used):
        """Drops a itself in item form 5 times

        See Block.get_drops for parameters & return"""

        if correct_item_used:
            return [('item', ("bee",))] * 5

    def can_use(self):
        return False

    def use(self):
        pass


class Furnace(ResourceBlock):
    """Create a furnace block"""
    def __init__(self, block_id, break_table):
        super().__init__(block_id, break_table)

    def get_drops(self, luck, correct_item_used):
        """Drops a itself in item form 1 times

        See Block.get_drops for parameters & return"""

        if correct_item_used:
            return [('item', (self._id,))] * 1

    def can_use(self):
        return True

    def use(self):
        pass


BLOCK_COLOURS = {
    'diamond': 'blue',
    'dirt': '#552015',
    'stone': 'grey',
    'wood': '#723f1c',
    'leaves': 'green',
    'crafting_table': 'pink',
    'furnace': 'black',
    'wool': 'aliceblue',
    'bed': 'slategrey',
    'honey': 'yellow',
    'hive': 'brown',
    'arrow': 'silver'
}

ITEM_COLOURS = {
    'diamond': 'blue',
    'dirt': '#552015',
    'stone': 'grey',
    'wood': '#723f1c',
    'apple': '#ff0000',
    'leaves': 'green',
    'crafting_table': 'pink',
    'furnace': 'black',
    'cooked_apple': 'red4',
    'wool': 'aliceblue',
    'bed': 'slategrey',
    'honey': 'yellow',
    'hive': 'brown',
    'arrow': 'silver'

}


def load_simple_world(world):
    """Loads blocks into a world

    Parameters:
        world (World): The game world to load with blocks
    """
    block_weights = [
        (100, 'dirt'),
        (30, 'stone'),
    ]

    cells = {}

    ground = []

    width, height = world.get_grid_size()

    for x in range(width):
        for y in range(height):
            if x < 22:
                if y <= 8:
                    continue
            else:
                if x + y < 30:
                    continue

            ground.append((x, y))

    weights, blocks = zip(*block_weights)
    kinds = random.choices(blocks, weights=weights, k=len(ground))

    for cell, block_id in zip(ground, kinds):
        cells[cell] = create_block(block_id)

    trunks = [(3, 8), (3, 7), (3, 6), (3, 5)]

    for trunk in trunks:
        cells[trunk] = create_block('wood')

    leaves = [(4, 3), (3, 3), (2, 3), (4, 2), (3, 2), (2, 2), (4, 4), (3, 4), (2, 4)]

    for leaf in leaves:
        cells[leaf] = create_block('leaf')

    for cell, block in cells.items():
        # cell -> box
        i, j = cell

        world.add_block_to_grid(block, i, j)

    world.add_block_to_grid(create_block("mayhem", 0), 14, 8)

    world.add_mob(Bird("friendly_bird", (12, 12)), 400, 100)
    world.add_mob(Sheep("sheep", (60, 30)), 400, 100)
    world.add_mob(Bee("bee", (5, 5)), 400, 100)


class Ninedraft:
    """High-level app class for Ninedraft, a 2d sandbox game"""

    def __init__(self, master):
        """Constructor

        Parameters:
            master (tk.Tk): tkinter root widget
        """

        self._master = master
        self._world = World((GRID_WIDTH, GRID_HEIGHT), BLOCK_SIZE)
        master.title('Ninedraft')
        load_simple_world(self._world)

        self._player = Player()
        self._world.add_player(self._player, 250, 150)

        self._world.add_collision_handler("player", "item", on_begin=self._handle_player_collide_item)

        self._hot_bar = SelectableGrid(rows=1, columns=10)
        self._hot_bar.select((0, 0))

        starting_hotbar = [
            Stack(create_item("dirt"), 20),
            Stack(create_item("apple"), 20),
            Stack(create_item("pickaxe", "stone"), 1),
            Stack(create_item("diamond"), 20),
            Stack(create_item("wool"), 20),
            Stack(create_item("furnace"), 1),
            Stack(create_item("honey"), 1),
            Stack(create_item("hive"), 1),
            Stack(create_item("bow"), 1),
            Stack(create_item("arrow"), 20)

        ]

        for i, item in enumerate(starting_hotbar):
            self._hot_bar[0, i] = item

        self._hands = create_item('hands')

        starting_inventory = [
            ((1, 5), Stack(Item('dirt'), 10)),
            ((0, 2), Stack(Item('wood'), 10)),
        ]
        self._inventory = Grid(rows=3, columns=10)
        for position, stack in starting_inventory:
            self._inventory[position] = stack

        self._crafting_window = None
        self._master.bind("e",
                          lambda e: self.run_effect(('crafting', 'basic')))

        self._view = GameView(master, self._world.get_pixel_size(), NewWorldViewRouter(BLOCK_COLOURS, ITEM_COLOURS))
        self._view.pack()

        # Task 1.2 Mouse Controls: Bind mouse events here
        # ...
        self._view.bind("<Motion>", self._mouse_move)
        self._view.bind("<Leave>", self._mouse_leave)
        self._master.bind("<Button-1>", self._left_click)
        self._view.bind("<Button-3>", self._right_click)



        # Task 1.3: Create instance of StatusView here
        # ...
        self._statusview = StatusView(master, self._player.get_health(), self._player.get_food())
        self._statusview.pack(side=tk.TOP)


        self._hot_bar_view = ItemGridView(master, self._hot_bar.get_size())
        self._hot_bar_view.pack(side=tk.TOP, fill=tk.X)

        # Task 1.5 Keyboard Controls: Bind to space bar for jumping here
        # ...
        self._master.bind("<space>", lambda e: self._jump())
        self._master.bind("a", lambda e: self._move(-1, 0))
        self._master.bind("<Left>", lambda e: self._move(-1, 0))
        self._master.bind("d", lambda e: self._move(1, 0))
        self._master.bind("<Right>", lambda e: self._move(1, 0))
        self._master.bind("s", lambda e: self._move(0, 1))
        self._master.bind("<Down>", lambda e: self._move(0, 1))

        # Task 1.5 Keyboard Controls: Bind numbers to hotbar activation here
        # ...
        self._master.bind("1", lambda e: self._hot_bar.select((0, 0)))
        self._master.bind("2", lambda e: self._hot_bar.select((0, 1)))
        self._master.bind("3", lambda e: self._hot_bar.select((0, 2)))
        self._master.bind("4", lambda e: self._hot_bar.select((0, 3)))
        self._master.bind("5", lambda e: self._hot_bar.select((0, 4)))
        self._master.bind("6", lambda e: self._hot_bar.select((0, 5)))
        self._master.bind("7", lambda e: self._hot_bar.select((0, 6)))
        self._master.bind("8", lambda e: self._hot_bar.select((0, 7)))
        self._master.bind("9", lambda e: self._hot_bar.select((0, 8)))
        self._master.bind("0", lambda e: self._hot_bar.select((0, 9)))

        # Task 1.6 File Menu & Dialogs: Add file menu here
        # ...
        menu_bar = tk.Menu(self._master)
        master.config(menu=menu_bar)
        file_menu = tk.Menu(menu_bar, tearoff=0)
        menu_bar.add_cascade(label='File', menu=file_menu)
        file_menu.add_command(label='New Game', command=self.restart)
        file_menu.add_command(label='Exit', command=self.exit)
        master.protocol("WM_DELETE_WINDOW", self.exit)


        self._target_in_range = False
        self._target_position = 0, 0

        self.redraw()

        self.step()

    def restart(self):
        """Restarts the game"""

        answer = messagebox.askyesno(title='New Game?', message='Are you sure you would like to start a new game?')
        if answer:
            for thing in self._world.get_all_things():
                self._world.remove_thing(thing)
            load_simple_world(self._world)
            self._player = Player()
            self._world.add_player(self._player, 250, 150)
            self._hot_bar.select((0, 0))

            starting_hotbar = [
                Stack(create_item("dirt"), 20),
                Stack(create_item("apple"), 20),
                Stack(create_item("pickaxe", "stone"), 1),
                Stack(create_item("diamond"), 20),
                Stack(create_item("wool"), 20),
                Stack(create_item("furnace"), 1),
                Stack(create_item("honey"), 1),
                Stack(create_item("hive"), 1),
                Stack(create_item("bow"), 1),
                Stack(create_item("arrow"), 20)
            ]
            for position, cell in self._hot_bar.items():
                self._hot_bar[position] = None

            for i, item in enumerate(starting_hotbar):
                self._hot_bar[0, i] = item

            for position, cell in self._inventory.items():
                self._inventory[position] = None
            starting_inventory = [
                ((1, 5), Stack(Item('dirt'), 10)),
                ((0, 2), Stack(Item('wood'), 10)),
            ]

            for position, stack in starting_inventory:
                self._inventory[position] = stack

    def exit(self):
        """Exits the application"""

        answer = messagebox.askyesno(title='Exit', message='Are you sure you want to quit Ninedraft?')
        if answer:
            self._master.destroy()

    def redraw(self):
        self._view.delete(tk.ALL)

        # physical things
        self._view.draw_physical(self._world.get_all_things())

        # target
        target_x, target_y = self._target_position
        target = self._world.get_block(target_x, target_y)
        cursor_position = self._world.grid_to_xy_centre(*self._world.xy_to_grid(target_x, target_y))

        # Task 1.2 Mouse Controls: Show/hide target here
        # ...
        self._view.show_target(self._player.get_position(), self._target_position)
        if not self._target_in_range:
            self._view.hide_target()


        # Task 1.3 StatusView: Update StatusView values here
        # ...
        self._statusview.set_health(self._player.get_health())

        self._statusview.set_food(self._player.get_food())

        # hot bar
        self._hot_bar_view.render(self._hot_bar.items(), self._hot_bar.get_selected())

    def step(self):
        data = GameData(self._world, self._player)
        self._world.step(data)
        self.redraw()

        # Task 1.6 File Menu & Dialogs: Handle the player's death if necessary
        # ...
        if self._player.is_dead():
            self.restart()

        self._master.after(15, self.step)

    def _move(self, dx, dy):
        self.check_target()
        velocity = self._player.get_velocity()
        self._player.set_velocity((velocity.x + dx * 80, velocity.y + dy * 80))

    def _jump(self):
        self.check_target()
        velocity = self._player.get_velocity()
        # Task 1.2: Update the player's velocity here
        # ...
        self._player.set_velocity((velocity.x / 1.5, velocity.y - 150))


    def mine_block(self, block, x, y):
        luck = random.random()

        active_item, effective_item = self.get_holding()

        was_item_suitable, was_attack_successful = block.mine(effective_item, active_item, luck)

        effective_item.attack(was_attack_successful)
        # if the block has been mined


        if block.is_mined():
            # Task 1.2 Mouse Controls: Reduce the player's food/health appropriately
            # ...
            if self._player.get_food() > 0:
                self._player.change_food(-0.5)
            else:
                self._player.change_health(-2.5)

            # Task 1.2 Mouse Controls: Remove the block from the world & get its drops
            # ...
            self._world.remove_item(block)
            if luck < 1:
                drops = block.get_drops(luck, was_item_suitable)
            # Have a look at the World class for removing
            # Have a look at the Block class for getting the drops

            if not drops:
                return

            x0, y0 = block.get_position()

            for i, (drop_category, drop_types) in enumerate(drops):
                print(f'Dropped {drop_category}, {drop_types}')

                if drop_category == "item":
                    physical = DroppedItem(create_item(*drop_types))

                    # this is so bleh
                    x = x0 - BLOCK_SIZE // 2 + 5 + (i % 3) * 11 + random.randint(0, 2)
                    y = y0 - BLOCK_SIZE // 2 + 5 + ((i // 3) % 3) * 11 + random.randint(0, 2)

                    self._world.add_item(physical, x, y)
                elif drop_category == "block":
                    self._world.add_block(create_block(*drop_types), x, y)
                else:
                    raise KeyError(f"Unknown drop category {drop_category}")

    def get_holding(self):
        active_stack = self._hot_bar.get_selected_value()
        active_item = active_stack.get_item() if active_stack else self._hands

        effective_item = active_item if active_item.can_attack() else self._hands

        return active_item, effective_item

    def check_target(self):
        # select target block, if possible
        active_item, effective_item = self.get_holding()

        pixel_range = active_item.get_attack_range() * self._world.get_cell_expanse()

        self._target_in_range = positions_in_range(self._player.get_position(),
                                                   self._target_position,
                                                   pixel_range)

    def _mouse_move(self, event):
        self._target_position = event.x, event.y
        self.check_target()

    def _mouse_leave(self, event):
        self._target_in_range = False

    def _left_click(self, event):
        # Invariant: (event.x, event.y) == self._target_position
        #  => Due to mouse move setting target position to cursor
        x, y = self._target_position

        if self._target_in_range:
            block = self._world.get_block(x, y)
            if block:
                self.mine_block(block, x, y)
            elif "Sheep('sheep')":
                block = WoolBlock("wool", "wood")
                block.get_drops(1, True)


    def _trigger_crafting(self, craft_type):
        print(f"Crafting with {craft_type}")
        CRAFTING_RECIPES_2x2 = [
            (
                (
                    (None, 'wood'),
                    (None, 'wood')
                ),
                Stack(create_item('stick'), 4)
            ),
            (
                (
                    ('wood', 'wood'),
                    ('wood', 'wood')
                ),
                Stack(create_item('crafting_table'), 1)
            ),
            (
                (
                    ('dirt', 'dirt'),
                    ('dirt', 'dirt')
                ),
                Stack(create_item('wood'), 1)
            ),
            (
                (
                    ('stone', 'stone'),
                    ('stone', 'stone')
                ),
                Stack(create_item('diamond'), 1)
            ),
            (
                (
                    ('apple', 'apple'),
                    ('apple', 'apple')
                ),
                Stack(create_item('honey'), 1)
            ),
        ]

        CRAFTING_RECIPES_3x3 = {
            (
                (
                    (None, None, None),
                    (None, 'wood', None),
                    (None, 'wood', None)
                ),
                Stack(create_item('stick'), 16)
            ),
            (
                (
                    ('wood', 'wood', 'wood'),
                    (None, 'stick', None),
                    (None, 'stick', None)
                ),
                Stack(create_item('pickaxe', 'wood'), 1)
            ),
            (
                (
                    ('stone', 'stone', 'stone'),
                    (None, 'stick', None),
                    (None, 'stick', None)
                ),
                Stack(create_item('pickaxe', 'stone'), 1)
            ),
            (
                (
                    ('diamond', 'diamond', 'diamond'),
                    (None, 'stick', None),
                    (None, 'stick', None)
                ),
                Stack(create_item('pickaxe', 'diamond'), 1)
            ),
            (
                (
                    ('wood', 'wood', None),
                    ('wood', 'stick', None),
                    (None, 'stick', None)
                ),
                Stack(create_item('axe', 'wood'), 1)
            ),
            (
                (
                    ('stone', 'stone', None),
                    ('wood', 'stick', None),
                    (None, 'stick', None)
                ),
                Stack(create_item('axe', 'stone'), 1)
            ),
            (
                (
                    (None, 'wood', None),
                    (None, 'stick', None),
                    (None, 'stick', None)
                ),
                Stack(create_item('shovel', 'wood'), 1)
            ),
            (
                (
                    (None, 'stone', None),
                    (None, 'stick', None),
                    (None, 'stick', None)
                ),
                Stack(create_item('shovel', 'stone'), 1)
            ),
            (
                (
                    (None, 'wood', None),
                    (None, 'wood', None),
                    (None, 'stick', None)
                ),
                Stack(create_item('sword', 'wood'), 1)
            ),
            (
                (
                    (None, 'stone', None),
                    (None, 'stone', None),
                    (None, 'stick', None)
                ),
                Stack(create_item('sword', 'stone'), 1)
            ),
            (
                (
                    (None, None, None),
                    ('wool', 'wool', 'wool'),
                    ('wood', 'wood', 'wood')
                ),
                Stack(create_item('bed'), 1)
            ),
            (
                (
                    ('stone', 'stone', 'stone'),
                    ('stone', None, 'stone'),
                    ('stone', 'stone', 'stone')
                ),
                Stack(create_item('furnace'), 1)
            )
        }

        if craft_type == "basic":
            crafter = GridCrafter(CRAFTING_RECIPES_2x2, 2, 2)
        else:
            crafter = GridCrafter(CRAFTING_RECIPES_3x3, 3, 3)

        self._crafting_window = CraftingWindow(self._master, craft_type, hot_bar=self._hot_bar,
                                               inventory=self._inventory, crafter=crafter)

    def run_effect(self, effect):
        if len(effect) == 2:
            if effect[0] == "crafting":
                craft_type = effect[1]

                if craft_type == "basic":
                    print("Can't craft much on a 2x2 grid :/")

                elif craft_type == "crafting_table":
                    print("Let's get our kraft® on! King of the brands")

                self._trigger_crafting(craft_type)
                return

            elif effect[0] in ("food", "health"):
                stat, strength = effect


                if self._player.get_food() < self._player._max_food :
                    stat = "food"
                else:
                    stat = "health"

                print(f"Gaining {strength} {stat}!")
                getattr(self._player, f"change_{stat}")(strength)
                return

        raise KeyError(f"No effect defined for {effect}")

    def _right_click(self, event):
        print("Right click")

        x, y = self._target_position
        target = self._world.get_thing(x, y)

        if target:
            # use this thing
            print(f'using {target}')
            effect = target.use()
            print(f'used {target} and got {effect}')

            if effect:
                self.run_effect(effect)

        else:
            # place active item
            selected = self._hot_bar.get_selected()

            if not selected:
                return

            stack = self._hot_bar[selected]
            if not stack:
                return
            drops = stack.get_item().place()

            stack.subtract(1)
            if stack.get_quantity() == 0:
                # remove from hotbar
                self._hot_bar[selected] = None

            if not drops:
                return

            # handling multiple drops would be somewhat finicky, so prevent it
            if len(drops) > 1:
                raise NotImplementedError("Cannot handle dropping more than 1 thing")

            drop_category, drop_types = drops[0]

            x, y = event.x, event.y

            if drop_category == "block":
                existing_block = self._world.get_block(x, y)

                if not existing_block:
                    self._world.add_block(create_block(drop_types[0]), x, y)
                else:
                    raise NotImplementedError(
                        "Automatically placing a block nearby if the target cell is full is not yet implemented")

            elif drop_category == "effect":
                self.run_effect(drop_types)

            else:
                raise KeyError(f"Unknown drop category {drop_category}")

    def _activate_item(self, index):
        print(f"Activating {index}")

        self._hot_bar.toggle_selection((0, index))

    def _handle_player_collide_item(self, player: Player, dropped_item: DroppedItem, data,
                                    arbiter: pymunk.Arbiter):
        """Callback to handle collision between the player and a (dropped) item. If the player has sufficient space in
        their to pick up the item, the item will be removed from the game world.

        Parameters:
            player (Player): The player that was involved in the collision
            dropped_item (DroppedItem): The (dropped) item that the player collided with
            data (dict): data that was added with this collision handler (see data parameter in
                         World.add_collision_handler)
            arbiter (pymunk.Arbiter): Data about a collision
                                      (see http://www.pymunk.org/en/latest/pymunk.html#pymunk.Arbiter)
                                      NOTE: you probably won't need this
        Return:
             bool: False (always ignore this type of collision)
                   (more generally, collision callbacks return True iff the collision should be considered valid; i.e.
                   returning False makes the world ignore the collision)
        """

        item = dropped_item.get_item()

        if self._hot_bar.add_item(item):
            print(f"Added 1 {item!r} to the hotbar")
        elif self._inventory.add_item(item):
            print(f"Added 1 {item!r} to the inventory")
        else:
            print(f"Found 1 {item!r}, but both hotbar & inventory are full")
            return True

        self._world.remove_item(dropped_item)
        return False

# Task 1.1 App class: Add a main function to instantiate the GUI here


if __name__ == "__main__":
    root = tk.Tk()
    app = Ninedraft(root)
    root.mainloop()




