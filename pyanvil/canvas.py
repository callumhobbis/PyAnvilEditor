import math
from pyanvil.schematic import Schematic
from pyanvil.coordinate import AbsoluteCoordinate


class WorldTask:
    def __init__(self, location, new_state):
        self.location = location
        self.new_state = new_state


class Canvas:

    def __init__(self, world: 'World', auto_commit: bool = True):
        self.world: 'World' = world
        self.work_queue: list[WorldTask] = []
        self.auto_commit: bool = auto_commit
        self.selection = set()

    def fill(self, state):
        my_state = state.clone()
        for b in list(self.selection):
            self.work_queue.append(WorldTask(b, my_state))

        self.deselect()

        if self.auto_commit:
            self.commit()

    def deselect(self):
        self.selection.clear()

    def copy(self):
        min_x = min((loc.x for loc in self.selection))
        min_y = min((loc.y for loc in self.selection))
        min_z = min((loc.z for loc in self.selection))
        print(min_x, min_y, min_z)
        new_schem = Schematic({
            AbsoluteCoordinate(loc.x - min_x, loc.y - min_y, loc.z - min_z): self.world.get_block(loc).get_state() for loc in self.selection
        })
        self.deselect()
        return new_schem

    def commit(self):
        region_work = {}
        for task in self.work_queue:
            chunk_cords = self.world._get_chunk(task.location)
            region_cords = self.world._get_region_file(chunk_cords)
            if region_cords not in region_work:
                region_work[region_cords] = []
            region_work[region_cords].append(task)

        for chunk, work in region_work.items():
            for task in work:
                self.world.get_block(task.location).set_state(task.new_state)
            self.world.flush()

    def select_rectangle(self, p1: AbsoluteCoordinate, p2: AbsoluteCoordinate):
        self._rect(p1, p2, True)
        return self

    def deselect_rectangle(self, p1: AbsoluteCoordinate, p2: AbsoluteCoordinate):
        self._rect(p1, p2, False)
        return self

    def _rect(self, p1: AbsoluteCoordinate, p2: AbsoluteCoordinate, select: bool):
        for x in range(p1.x, p2.x + 1):
            for y in range(p1.y, p2.y + 1):
                for z in range(p1.z, p2.z + 1):
                    loc = AbsoluteCoordinate(x, y, z)
                    if select:
                        self.selection.add(loc)
                    else:
                        self.selection.remove(loc)

    # def select_oval(self, p1, p2):
    #     self._oval(center, radius, True)
    #     return self

    # def deselect_oval(self, p1, p2):
    #     self._oval(center, radius, False)
    #     return self

    # def _oval(self, p1, p2, select):
    #     ss = radius+1
    #     for x in range(-ss, ss):
    #         for z in range(-ss, ss):
    #             loc = (center[0] + x, center[1], center[2] + z)
    #             if Canvas._dist(loc, center) <= (radius + 0.5):
    #                 if select:
    #                     self.selection.add(loc)
    #                 else:
    #                     self.selection.remove(loc)

    def _dist(loc1: AbsoluteCoordinate, loc2: AbsoluteCoordinate):
        dx = abs(loc1.x - loc2.x) ** 2
        dy = abs(loc1.y - loc2.y) ** 2
        dz = abs(loc1.z - loc2.z) ** 2

        return math.sqrt(dx + dy + dz)
