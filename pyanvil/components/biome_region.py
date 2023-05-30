from pyanvil.components.biome import Biome
from pyanvil.components.chunk_section import ChunkSection
from pyanvil.components.component_base import ComponentBase


class BiomeRegion(ComponentBase):

    _parent: ComponentBase | None
    _is_dirty: bool
    _dirty_children: set[ComponentBase]

    _biome: Biome

    def __init__(
        self,
        biome: Biome,
        dirty: bool = False,
        parent_chunk_section: ChunkSection | None = None
    ) -> None:
        super().__init__(parent=parent_chunk_section, dirty=dirty)
        self._biome: Biome = biome

    def __str__(self) -> str:
        return f'BiomeRegion({self._biome})'

    def set_biome(self, biome: Biome | str) -> None:
        self._is_dirty = True
        if isinstance(biome, Biome):
            self._biome = biome
        else:
            self._biome = Biome(biome)
        self.mark_as_dirty()

    def get_biome(self) -> Biome:
        return self._biome.clone()
