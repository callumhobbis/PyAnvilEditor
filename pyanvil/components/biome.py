class Biome:
    def __init__(self, name: str):
        self.name = name

    def __str__(self):
        return f'Biome({self.name})'

    def __hash__(self) -> int:
        return hash(self.name)

    def __eq__(self, other):
        return self.name == other.name

    def clone(self):
        return Biome(self.name)
