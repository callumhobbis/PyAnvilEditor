from typing import Self


class Biome:

    name: str

    def __init__(self, name: str) -> None:
        self.name = name

    def __str__(self) -> str:
        return f'Biome({self.name})'

    def __hash__(self) -> int:
        return hash(self.name)

    def __eq__(self, other: Self) -> bool:
        return self.name == other.name

    def clone(self) -> Self:
        return Biome(self.name)
