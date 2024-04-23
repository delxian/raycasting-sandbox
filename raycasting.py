"""Management for all raycasting calculations."""
from dataclasses import dataclass
import math
from functools import lru_cache
import statistics

import numpy as np
import pygame

from player import Player
from cells import split_position, get_enter_side, CellMap
from blocks import Wall, Mirror, Portal
from directions import Direction


ADJACENT_OFFSETS = {
    Direction.UP: (0, -1),
    Direction.RIGHT: (1, 0),
    Direction.DOWN: (0, 1),
    Direction.LEFT: (-1, 0)
    }


@dataclass
class RaySegment:
    """Data for a single segment of a ray."""
    start_pos: pygame.Vector2
    end_pos: pygame.Vector2
    distance: float
    end_type: Wall | Mirror | Portal | bool


class CastingRay:
    """Implementation of a single ray for raycasting."""

    def __init__(self, direction: pygame.Vector2, visible_distance: int,
                 player: Player, cell_map: CellMap):
        self.direction = direction
        self.visible_distance = visible_distance

        self.total_distance: float = 0
        self.segment_distance: float = 0
        self.segments: list[RaySegment] = []
        self.points: list[tuple[float, float]] = []

        self.start_position: pygame.Vector2 = player.position.xy
        self.end_position: pygame.Vector2 = player.position.xy

        self.cell_map = cell_map

    def cast(self):
        """Cast the ray and calculate relevant data."""
        while True:
            self.points.append((self.end_position.x, self.end_position.y))
            cell, cell_pos = split_position(
                self.end_position, self.cell_map.square_size)

            cell_type = self.cell_map.get_cell(int(cell.x), int(cell.y)).type_
            enter_side = get_enter_side(cell_pos, self.direction)

            action = self.handle_type(cell_type, enter_side, cell)
            if action == "break":
                break
            if action == "continue":
                continue

            action = self.take_step(cell_pos)
            if action == "break":
                break

    def take_step(self, cell_pos: pygame.Vector2) -> str:
        """Propagate the ray in its direction, handling two "edge" cases."""
        step_distance = self.step_to_edge(
            (cell_pos.x, cell_pos.y), (self.direction.x, self.direction.y))
        new_position = self.end_position + self.position_step(step_distance)
        new_total_distance = self.total_distance + step_distance
        if (new_total_distance > self.visible_distance
            or not self.cell_map.in_bounds(new_position)):
            if new_total_distance > self.visible_distance:
                # total distance with step exceeds visible distance, shorten to maximum
                adjusted_distance = self.visible_distance-self.total_distance
                cell_type = False
            else:
                # new position is out of bounds, shorten until it is within bounds
                adjusted_distance = step_distance
                while True:
                    adjusted_distance *= 0.99
                    safe_end_position = (
                        self.end_position + self.position_step(adjusted_distance))
                    if self.cell_map.in_bounds(safe_end_position):
                        break
                cell_type = Wall.BORDER
            self.end_position += self.position_step(adjusted_distance)
            self.total_distance += adjusted_distance
            self.segment_distance += adjusted_distance
            self.add_segment_and_point(cell_type)
            return "break"
        self.end_position = new_position
        self.total_distance = new_total_distance
        self.segment_distance += step_distance
        return ''

    def handle_type(self, cell_type: Wall | Mirror | Portal | bool,
                    enter_side: Direction, cell: pygame.Vector2) -> str:
        """Handle various cell types at the ray's end position."""
        match cell_type:
            case Wall.NORMAL:
                self.add_segment_and_point(Wall.NORMAL)
                return "break"

            case Mirror():
                if not bool(cell_type.sides & enter_side):
                    self.add_segment_and_point(Wall.NORMAL)
                    return "break"

                self.add_segment_and_point(cell_type)
                self.start_position, self.segment_distance = self.end_position.xy, 0

                self.mirror_reflect(cell, enter_side)

            case Portal():
                if cell_type.links[enter_side] is None:
                    self.add_segment_and_point(Wall.NORMAL)
                    return "break"

                self.add_segment_and_point(cell_type)
                self.start_position, self.segment_distance = self.end_position.xy, 0

                self.start_position, self.direction = (
                    self.cell_map.portal_transform(self.start_position, self.direction))
                self.start_position += self.direction*0.05  # avoid clipping into portal walls
                self.end_position = self.start_position.xy
                return "continue"

        return ''

    def mirror_reflect(self, cell: pygame.Vector2, enter_side: Direction):
        """Reflect the ray's direction according to local mirror configuration."""
        # adjacent cell at enter direction is occupied
        adjacent = cell + pygame.Vector2(ADJACENT_OFFSETS[enter_side])
        if (self.cell_map.get_cell(int(adjacent.x), int(adjacent.y))).type_:
            # reflect in possible direction (exposed side)
            if enter_side in {Direction.LEFT, Direction.RIGHT}:
                self.direction.y *= -1
            elif enter_side in {Direction.UP, Direction.DOWN}:
                self.direction.x *= -1
        else:
            # reflect in normal direction (expected side)
            if enter_side in {Direction.LEFT, Direction.RIGHT}:
                self.direction.x *= -1
            elif enter_side in {Direction.UP, Direction.DOWN}:
                self.direction.y *= -1

    def add_segment_and_point(self, end_type: Wall | Mirror | Portal | bool):
        """Store current ray values as a segment and a point."""
        self.segments.append(
            RaySegment(self.start_position.xy, self.end_position.xy,
                       self.segment_distance, end_type)
        )
        self.points.append((self.end_position.x, self.end_position.y))

    def position_step(self, distance: float) -> pygame.Vector2:
        """Calculate the actual offset for a step in the current direction."""
        return self.direction*distance*self.cell_map.square_size

    @staticmethod
    @lru_cache(maxsize=500)
    def step_to_edge(position: tuple[float, float], direction: tuple[float, float]) -> float:
        """Starting in a unit square, find the distance to the edge in a given direction."""
        step_x, step_y = math.inf, math.inf

        if direction[0] > 0:
            step_x = (1-position[0]) / direction[0]
        elif direction[0] < 0:
            step_x = position[0] / abs(direction[0]) + 0.001
        if direction[1] > 0:
            step_y = (1-position[1]) / direction[1]
        elif direction[1] < 0:
            step_y = position[1] / abs(direction[1]) + 0.001
        return min(step_x, step_y)


class Raycaster:
    """Handler for casting multiple rays for level rendering."""

    def __init__(self, player: Player, cell_map: CellMap, fov: float, ray_count: int):
        self.player, self.cell_map = player, cell_map
        self.fov, self.ray_count = fov, ray_count
        self.ray_data: dict[float, tuple[tuple[float, list[RaySegment]],
                                         list[tuple[float, float]]]] = {}

    def distribute_angles(self, center: float) -> list[float]:
        """Get a spread of angles around an angle for raycasting."""
        interval = self.fov / (self.ray_count-1) if self.ray_count > 1 else 1
        angles = np.array(range(self.ray_count))*interval
        median = statistics.median(angles)
        return [angle % 360 for angle in (angles + (center-median))]

    def cast_rays(self, angle_center: float, visible_distance: int):
        """Cast rays in a spread around a provided center angle."""
        angles = self.distribute_angles(angle_center)
        directions = [pygame.Vector2(1, 0).rotate(angle) for angle in angles]
        self.ray_data.clear()
        for angle, direction in zip(angles, directions):
            self.ray_data[angle] = self.cast_ray(direction, visible_distance)

    def cast_ray(self, direction: pygame.Vector2,
                 visible_distance: int) -> tuple[tuple[float, list[RaySegment]],
                                                 list[tuple[float, float]]]:
        """Calculate visible parts of a level map via raycasting."""
        ray = CastingRay(direction, visible_distance, self.player, self.cell_map)
        ray.cast()
        return ((ray.total_distance, ray.segments), ray.points)
