"""Various blocks that can exist in cells and their properties."""
from __future__ import annotations
from enum import Enum
from functools import reduce

from directions import Direction


class Wall(Enum):
    """Solid barrier that blocks movement and rays."""
    NORMAL = 1
    BORDER = 2


class Mirror:
    """Solid barrier that blocks movement and reflects rays."""

    def __init__(self, sides: Direction = Direction.NONE):
        self.sides = sides

    def toggle(self, sides: Direction):
        """Toggle sides of a mirror on or off, with off being normal walls."""
        self.sides ^= sides


class Portal:
    """Semi-solid barrier that allows movement and teleportation."""

    def __init__(self):
        self.active: bool = True
        self.links: dict[Direction, tuple[tuple[int, int], Direction] | None] = {
            Direction.UP: None,
            Direction.DOWN: None,
            Direction.LEFT: None,
            Direction.RIGHT: None
        }

    def get_subrect_indices(self) -> list[int]:
        """Get indices of a 3x3 grid that correspond to cardinal directions."""
        linked_directions = [direction for direction, link in self.links.items()
                             if link is not None]
        compound_direction = reduce(lambda a, b: a | b, linked_directions)
        return compound_direction.get_subrect_indices()
