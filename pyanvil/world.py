from types import TracebackType
from typing import Self
from pathlib import Path

from pyanvil.components.region import Region
from pyanvil.coordinate import AbsoluteCoordinate, ChunkCoordinate, RegionCoordinate
from pyanvil.canvas import Canvas
from pyanvil.components import Chunk, Block


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
