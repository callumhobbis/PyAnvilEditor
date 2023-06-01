from __future__ import annotations

from pathlib import Path
from types import TracebackType
from typing import Self

from pyanvil.components import Block, BlockState, Chunk, Region
from pyanvil.coordinate import AbsoluteCoordinate, ChunkCoordinate, RegionCoordinate


class World:

    debug: bool
    world_folder: Path
    regions: dict[RegionCoordinate, Region]

    def __init__(
        self,
        world_folder: str | Path,
        save_location: str | Path | None = None,
        debug: bool = False,
        read: bool = True,
        write: bool = True,
    ):
        self.debug = debug
        self.world_folder = self.__resolve_world_folder(world_folder=world_folder, save_location=save_location)
        self.regions = {}

    def __resolve_world_folder(self, world_folder: str | Path, save_location: str | Path | None) -> Path:
        folder = Path()
        if save_location is not None:
            folder = Path(save_location) / world_folder
        else:
            folder = Path(world_folder)
        if not folder.is_dir():
            raise FileNotFoundError(f'No such folder "{folder}"')
        return folder

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if exc_type is None:
            self.close()

    def flush(self) -> None:
        self.close()
        self.regions: dict[RegionCoordinate, Region] = dict()

    def close(self) -> None:
        for region in self.regions.values():
            if region.is_dirty:
                region.save()

    def get_block(self, coordinate: AbsoluteCoordinate) -> Block:
        self._get_region_file_name(coordinate.to_region_coordinate())
        chunk = self.get_chunk(coordinate.to_chunk_coordinate())
        return chunk.get_block(coordinate)

    def get_region(self, coord: RegionCoordinate) -> Region:
        return self.regions.get(coord, self._load_region(coord))

    def get_chunk(self, coord: ChunkCoordinate) -> Chunk:
        region = self.get_region(coord.to_region_coordinate())
        return region.get_chunk(coord)

    def get_canvas(self) -> Canvas:
        return Canvas(self)

    def _load_region(self, coord: RegionCoordinate) -> Region:
        name = self._get_region_file_name(coord)
        region = Region(self.world_folder / 'region' / name)
        self.regions[coord] = region
        return region

    def _get_region_file_name(self, region: RegionCoordinate) -> str:
        return f'r.{region.x}.{region.z}.mca'


class WorldTask:
    def __init__(self, location, new_state):
        self.location = location
        self.new_state = new_state


class Canvas:

    world: World
    work_queue: list[WorldTask]
    auto_commit: bool
    selection: set[AbsoluteCoordinate]

    def __init__(self, world: World, auto_commit: bool = True) -> None:
        self.world = world
        self.work_queue = []
        self.auto_commit = auto_commit
        self.selection = set()

    def fill(self, state: BlockState) -> None:
        my_state = state.clone()
        for b in list(self.selection):
            self.work_queue.append(WorldTask(b, my_state))

        self.deselect()

        if self.auto_commit:
            self.commit()

    def deselect(self) -> None:
        self.selection.clear()

    def copy(self) -> Schematic:
        min_x = min((loc.x for loc in self.selection))
        min_y = min((loc.y for loc in self.selection))
        min_z = min((loc.z for loc in self.selection))
        print(min_x, min_y, min_z)

        new_schem = Schematic({
            AbsoluteCoordinate(loc.x - min_x, loc.y - min_y, loc.z - min_z): self.world.get_block(loc).get_state() for loc in self.selection
        })
        self.deselect()
        return new_schem

    def commit(self) -> None:
        region_work: dict[Region, list[WorldTask]] = {}
        for task in self.work_queue:
            chunk = self.world.get_chunk(task.location)
            region_coord = chunk.coordinate.to_region_coordinate()
            region = self.world.get_region(region_coord)
            if region not in region_work:
                region_work[region] = []
            region_work[region].append(task)

        for work in region_work.values():
            for task in work:
                self.world.get_block(task.location).set_state(task.new_state)
            self.world.flush()

    def select_rectangle(
        self,
        p1: AbsoluteCoordinate,
        p2: AbsoluteCoordinate
    ) -> Self:
        self._rect(p1, p2, True)
        return self

    def deselect_rectangle(
        self,
        p1: AbsoluteCoordinate,
        p2: AbsoluteCoordinate,
    ) -> Self:
        self._rect(p1, p2, False)
        return self

    def _rect(
        self,
        p1: AbsoluteCoordinate,
        p2: AbsoluteCoordinate,
        select: bool,
    ) -> None:
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


class Schematic:

    state_map: dict[AbsoluteCoordinate, BlockState]

    def __init__(self, state_map: dict[AbsoluteCoordinate, BlockState]) -> None:
        self.state_map = state_map

    def paste(self, world: World, corner: AbsoluteCoordinate) -> None:
        for loc, state in self.state_map.items():
            shift_loc = loc + corner
            world.get_block(shift_loc).set_state(state)
