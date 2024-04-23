"""Implementation for a controllable player."""
# pylint: disable=no-member,no-name-in-module,c-extension-no-member

import pygame
from pygame.locals import (K_LEFT, K_RIGHT, K_LSHIFT,
                           K_w, K_a, K_s, K_d)

from cells import TRANSPARENT, CellMap
from blocks import Portal
from directions import MovementCombo


MOVEMENT_ANGLES = {
    MovementCombo.FORWARD: 0,
    MovementCombo.FORWARD_RIGHT: 45,
    MovementCombo.RIGHT: 90,
    MovementCombo.BACKWARD_RIGHT: 135,
    MovementCombo.BACKWARD: 180,
    MovementCombo.BACKWARD_LEFT: 225,
    MovementCombo.LEFT: 270,
    MovementCombo.FORWARD_LEFT: 315
    }

DIRECTION_BINDS = (
    (K_w, MovementCombo.FORWARD),
    (K_a, MovementCombo.LEFT),
    (K_s, MovementCombo.BACKWARD),
    (K_d, MovementCombo.RIGHT)
    )


class Player(pygame.sprite.Sprite):
    """Controllable character whose position and direction is tracked."""
    SPEED_MULTIPLIER = 3
    BODY_COLOR = (255, 255, 255)
    DIRECTION_COLOR = (0, 0, 0)

    def __init__(self, radius: int, position: tuple[int, int]):
        super().__init__()
        self.radius = radius
        self.position = pygame.Vector2(position)
        self.surf = pygame.Surface((self.radius*2, self.radius*2), pygame.SRCALPHA)
        self.rect: pygame.Rect = self.surf.get_rect(center=position, size=self.surf.get_size())
        self.direction = pygame.Vector2(0, -1)

    def update(self, keys, cell_map: CellMap):
        """Handle directional movement and rotation."""
        if keys[K_LEFT]:
            self.direction.rotate_ip(-1)
        elif keys[K_RIGHT]:
            self.direction.rotate_ip(1)

        self.draw()
        self.move(keys, cell_map)

    def draw(self):
        """Draw the player on the map."""
        self.surf.fill(TRANSPARENT)
        pygame.draw.circle(self.surf, self.BODY_COLOR,
                           (self.radius, self.radius), self.radius)
        start_pos = pygame.Vector2(self.radius, self.radius)
        end_pos = start_pos + self.direction*self.radius
        pygame.draw.line(self.surf, self.DIRECTION_COLOR, start_pos, end_pos, width=2)

    def move(self, keys, cell_map: CellMap):
        """Update the player's position and direction on the map."""
        movement_combo = MovementCombo.NONE
        for key_id, direction in DIRECTION_BINDS:
            if keys[key_id]:
                movement_combo |= direction
        movement_combo = movement_combo.resolved()

        if movement_combo.value:
            multiplier = (self.SPEED_MULTIPLIER if keys[K_LSHIFT] else 1)
            movement_angle = MOVEMENT_ANGLES.get(movement_combo, 0)
            new_position = self.position + self.direction.rotate(movement_angle)*multiplier
            new_x, new_y = new_position.x, new_position.y
            current_cell = (int(self.position.x // cell_map.square_size),
                            int(self.position.y // cell_map.square_size))
            new_cell = (int(new_x // cell_map.square_size),
                        int(new_y // cell_map.square_size))

            # check if moving from empty cell to portal cell
            if (isinstance(cell_map.get_cell(*new_cell).type_, Portal)
                and cell_map.get_cell(*current_cell).type_ is False):
                self.position, self.direction = (
                    cell_map.portal_transform(new_position, self.direction))
            else:
                # splitting x and y allows for diagonal "gliding"
                new_x_cell = (int(new_x // cell_map.square_size),
                              int(self.position.y // cell_map.square_size))
                if not cell_map.get_cell(*new_x_cell).type_:
                    self.position.x = new_x
                new_y_cell = (int(self.position.x // cell_map.square_size),
                              int(new_y // cell_map.square_size))
                if not cell_map.get_cell(*new_y_cell).type_:
                    self.position.y = new_y

            self.rect.center = self.position.xy

        # keep in bounds
        self.position.x = pygame.math.clamp(
            self.position.x, self.radius, cell_map.size[0]-self.radius)
        self.position.y = pygame.math.clamp(
            self.position.y, self.radius, cell_map.size[1]-self.radius)
