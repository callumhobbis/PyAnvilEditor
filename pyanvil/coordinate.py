from __future__ import annotations

from abc import ABC, abstractmethod
import math


class Coordinate(ABC):
    def __init__(self, x: int = 0, z: int = 0):
        super().__init__()
        self.x: int = x
        self.z: int = z

    def __hash__(self) -> int:
        return hash((self.x, self.z))

    @abstractmethod
    def __eq__(self, other) -> bool:
        pass

    @abstractmethod
    def to_absolute_coordinate(self) -> 'AbsoluteCoordinate':
        pass

    @abstractmethod
    def to_biome_coordinate(self) -> 'BiomeCoordinate':
        pass

    @abstractmethod
    def to_chunk_coordinate(self) -> 'ChunkCoordinate':
        pass

    @abstractmethod
    def to_region_coordinate(self) -> 'RegionCoordinate':
        pass


class AbsoluteCoordinate(Coordinate):
    def __init__(self, x: int = 0, y: int = 0, z: int = 0):
        super().__init__(x=x, z=z)
        self.y: int = y

    def __hash__(self) -> int:
        return hash((self.x, self.y, self.z))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, AbsoluteCoordinate):
            return False
        return self.x == other.x and self.y == other.y and self.z == other.z

    def __repr__(self) -> str:
        return f'AbsoluteCoordinate({self.x}, {self.y}, {self.z})'

    def __add__(self, other: AbsoluteCoordinate) -> AbsoluteCoordinate:
        return AbsoluteCoordinate(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other: AbsoluteCoordinate) -> AbsoluteCoordinate:
        return AbsoluteCoordinate(self.x - other.x, self.y - other.y, self.z - other.z)

    def dist(self, other: AbsoluteCoordinate) -> float:
        delta = self - other
        return math.sqrt(delta.x + delta.y + delta.z)

    def to_absolute_coordinate(self) -> 'AbsoluteCoordinate':
        return self

    def to_biome_coordinate(self) -> 'BiomeCoordinate':
        return BiomeCoordinate(self.x // 4, self.y // 4, self.z // 4)

    def to_chunk_coordinate(self) -> 'ChunkCoordinate':
        return ChunkCoordinate(self.x // 16, self.z // 16)

    def to_region_coordinate(self) -> 'RegionCoordinate':
        return RegionCoordinate(self.x // (16 * 32), self.z // (16 * 32))


class BiomeCoordinate(Coordinate):
    def __init__(self, x: int = 0, y: int = 0, z: int = 0):
        super().__init__(x=x, z=z)
        self.y: int = y

    def __hash__(self) -> int:
        return hash((self.x, self.y, self.z))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, BiomeCoordinate):
            return False
        return self.x == other.x and self.y == other.y and self.z == other.z

    def __repr__(self) -> str:
        return f'BiomeCoordinate({self.x}, {self.y}, {self.z})'

    def to_absolute_coordinate(self) -> 'AbsoluteCoordinate':
        return AbsoluteCoordinate(x=self.x * 4, y=self.y * 4, z=self.z * 4)

    def to_biome_coordinate(self) -> 'BiomeCoordinate':
        return self

    def to_chunk_coordinate(self) -> 'ChunkCoordinate':
        return ChunkCoordinate(self.x // 4, self.z // 4)

    def to_region_coordinate(self) -> 'RegionCoordinate':
        return RegionCoordinate(self.x // (4 * 32), self.z // (4 * 32))


class ChunkCoordinate(Coordinate):
    def __init__(self, x: int = 0, z: int = 0):
        super().__init__(x=x, z=z)

    def __hash__(self) -> int:
        return hash((self.x, self.z))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ChunkCoordinate):
            return False
        return self.x == other.x and self.z == other.z

    def __repr__(self) -> str:
        return f'ChunkCoordinate({self.x}, {self.z})'

    def to_absolute_coordinate(self) -> 'AbsoluteCoordinate':
        return AbsoluteCoordinate(x=self.x * 16, y=0, z=self.z * 16)

    def to_biome_coordinate(self) -> BiomeCoordinate:
        return BiomeCoordinate(x=self.x // 4, y=0, z=self.z // 4)

    def to_chunk_coordinate(self) -> 'ChunkCoordinate':
        return self

    def to_region_coordinate(self) -> 'RegionCoordinate':
        return RegionCoordinate(self.x // 32, self.z // 32)


class RelativeChunkCoordinate(ChunkCoordinate):
    def __init__(self, x: int = 0, z: int = 0):
        super().__init__(x=x, z=z)

    def __hash__(self) -> int:
        return hash((self.x, self.z))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, RelativeChunkCoordinate):
            return False
        return self.x == other.x and self.z == other.z

    def __repr__(self) -> str:
        return f'RelativeChunkCoordinate({self.x}, {self.z})'


class RegionCoordinate(Coordinate):
    def __init__(self, x: int = 0, z: int = 0):
        super().__init__(x=x, z=z)

    def __hash__(self) -> int:
        return hash((self.x, self.z))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, RegionCoordinate):
            return False
        return self.x == other.x and self.z == other.z

    def __repr__(self) -> str:
        return f'RegionCoordinate({self.x}, {self.z})'

    def to_absolute_coordinate(self) -> 'AbsoluteCoordinate':
        return AbsoluteCoordinate(x=self.x * 16 * 32, y=0, z=self.z * 16 * 32)

    def to_biome_coordinate(self) -> 'BiomeCoordinate':
        return BiomeCoordinate(x=self.x * 4 * 32, y=0, z=self.z * 4 * 32)

    def to_chunk_coordinate(self) -> 'ChunkCoordinate':
        return ChunkCoordinate(self.x * 32, self.z * 32)

    def to_region_coordinate(self) -> 'RegionCoordinate':
        return self
