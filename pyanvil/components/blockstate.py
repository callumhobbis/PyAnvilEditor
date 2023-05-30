from typing import Self


class BlockState:

    name: str
    props: dict
    id: int | None

    def __init__(
        self,
        name: str = 'minecraft:air',
        props: dict | None = None,
    ) -> None:
        self.name = name
        self.props = {} if props is None else props
        self.id: int | None = None

    def __str__(self) -> str:
        return f'BlockState({self.name}, {str(self.props)})'

    def __hash__(self) -> int:
        return hash(self.name)

    def __eq__(self, other: Self) -> bool:
        return self.name == other.name and self.props == other.props

    def clone(self) -> Self:
        return BlockState(self.name, self.props.copy())
