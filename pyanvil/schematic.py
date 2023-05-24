from .coordinate import AbsoluteCoordinate


class Schematic:

    def __init__(self, state_map):
        self.state_map = state_map

    def paste(self, world: 'World', corner: AbsoluteCoordinate):
        for loc, state in self.state_map.items():
            shift_loc = (loc.x + corner.x, loc.y + corner.y, loc.z + corner.z)
            world.get_block(shift_loc).set_state(state)
