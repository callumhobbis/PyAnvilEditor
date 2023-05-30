from pyanvil.components.blockstate import BlockState
from pyanvil.components.chunk_section import ChunkSection
from pyanvil.components.component_base import ComponentBase


class Block(ComponentBase):

    _parent: ComponentBase | None
    _is_dirty: bool
    _dirty_children: set[ComponentBase]

    _state: BlockState
    block_light: int
    sky_light: int

    def __init__(
        self,
        state: BlockState | None = None,
        block_light: int = 0,
        sky_light: int = 0,
        dirty: bool = False,
        parent_chunk_section: ChunkSection | None = None
    ) -> None:
        super().__init__(parent=parent_chunk_section, dirty=dirty)
        self._state = BlockState() if state is None else state
        self.block_light: int = block_light
        self.sky_light: int = sky_light

    def __str__(self) -> str:
        return f'Block({str(self._state)}, {self.block_light}, {self.sky_light})'

    def set_state(self, state: BlockState | str) -> None:
        self._is_dirty = True
        if isinstance(state, BlockState):
            self._state = state
        else:
            self._state = BlockState(state, {})
        self.mark_as_dirty()

    def get_state(self) -> BlockState:
        return self._state.clone()
