from pyanvil.components.biome import Biome
from pyanvil.components.component_base import ComponentBase


class BiomeRegion(ComponentBase):
    def __init__(self, biome, dirty: bool = False, parent_chunk_section: 'ChunkSection' = None):
        super().__init__(parent=parent_chunk_section, dirty=dirty)
        self._biome: Biome = biome

    def __str__(self):
        return f'BiomeRegion({self._biome})'

    def set_biome(self, biome):
        self._dirty = True
        if type(biome) is Biome:
            self._biome = biome
        else:
            self._biome = Biome(biome)
        self.mark_as_dirty()

    def get_biome(self):
        return self._biome.clone()
