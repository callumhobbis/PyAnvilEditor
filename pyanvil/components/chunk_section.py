import math

from .component_base import ComponentBase
from . import Block, BlockState, Biome, BiomeRegion, Sizes
from . import ByteArrayTag, ByteTag, CompoundTag, StringTag, LongArrayTag, LongTag, ListTag


class ChunkSection(ComponentBase):
    def __init__(self, raw_section, y_index, blocks: dict[int, Block] = None, biome_regions: dict[int, BiomeRegion] = None, parent_chunk: 'Chunk' = None):
        super().__init__(parent=parent_chunk)

        if blocks is None:
            blocks = dict()
        self.__blocks: dict[int, Block] = blocks

        if biome_regions is None:
            biome_regions = dict()
        self.__biome_regions: dict[int, BiomeRegion] = biome_regions

        self.raw_section = raw_section
        self.y_index = y_index

    def get_block(self, block_pos):
        x = block_pos[0]
        y = block_pos[1]
        z = block_pos[2]

        return self.__blocks[x + z * Sizes.SUBCHUNK_WIDTH + y * Sizes.SUBCHUNK_WIDTH ** 2]

    def set_blocks(self, blocks: dict[int, Block]):
        if blocks is not None:
            self.__blocks = blocks
        else:
            self.__blocks = dict()

    def get_biome(self, biome_pos):
        x = biome_pos[0]
        y = biome_pos[1]
        z = biome_pos[2]

        biome_region_count = Sizes.SUBCHUNK_WIDTH // Sizes.BIOME_REGION_WIDTH
        return self.__biome_regions[x + z * biome_region_count + y * biome_region_count ** 2]

    def set_biome_regions(self, biome_regions: dict[int, Biome]):
        if biome_regions is not None:
            self.__biome_regions = biome_regions
        else:
            self.__biome_regions = dict()


    @staticmethod
    def from_nbt(section_nbt, parent_chunk=None) -> 'ChunkSection':
        states_palette = [
            BlockState(
                state.get('Name').get(),
                state.get('Properties').to_dict() if state.has('Properties') else {}
            ) for state in section_nbt.get('block_states').get('palette').children
        ]
        if len(states_palette) == 1:
            states = [0] * 16**3
        else:
            flatstates = [c.get() for c in section_nbt.get('block_states').get('data').children]
            pack_size = max(4, (len(states_palette) - 1).bit_length())
            states = [
                ChunkSection._read_width_from_loc(flatstates, pack_size, i) for i in range(Sizes.SUBCHUNK_WIDTH ** 3)
            ]

        block_lights = ChunkSection._divide_nibbles(section_nbt.get('BlockLight').get()) if section_nbt.has('BlockLight') else None
        sky_lights = ChunkSection._divide_nibbles(section_nbt.get('SkyLight').get()) if section_nbt.has('SkyLight') else None
        section = ChunkSection(section_nbt, section_nbt.get('Y').get(), parent_chunk=parent_chunk)
        blocks: dict[int, Block] = dict()
        for i, state in enumerate(states):
            state = states_palette[state]
            block_light = block_lights[i] if block_lights else 0
            sky_light = sky_lights[i] if sky_lights else 0
            blocks[i] = Block(state=state, block_light=block_light, sky_light=sky_light, parent_chunk_section=section)
        section.set_blocks(blocks=blocks)

        biomes_palette = [
            Biome(
                biome.get()
            ) for biome in section_nbt.get('biomes').get('palette').children
        ]
        if len(biomes_palette) == 1:
            biomes = [0] * 16**3
        else:
            flatbiomes = [c.get() for c in section_nbt.get('biomes').get('data').children]
            pack_size = (len(biomes_palette) - 1).bit_length()
            biomes = ChunkSection._read_width_from_loc(flatbiomes, pack_size, (Sizes.SUBCHUNK_WIDTH//Sizes.BIOME_REGION_WIDTH)**3)

        biome_regions: dict[int, BiomeRegion] = dict()
        for i, biome in enumerate(biomes):
            biome = biomes_palette[biome]
            biome_regions[i] = BiomeRegion(biome=biome, parent_chunk_section=section)
        section.set_biome_regions(biome_regions=biome_regions)

        return section

    def serialize(self):
        serial_section = self.raw_section
        blocks_dirty = any((b.is_dirty for b in self.__blocks.values()))
        if blocks_dirty:
            self.states_palette = list(set([b._state for b in self.__blocks.values()] + [BlockState('minecraft:air', {})]))
            self.states_palette.sort(key=lambda s: s.name)
            serial_section.add_child(ByteTag(tag_value=self.y_index, tag_name='Y'))
            mat_id_mapping = {self.states_palette[i]: i for i in range(len(self.states_palette))}
            serial_section.add_child(self._serialize_blockstates(mat_id_mapping))

        biomes_dirty = any((b.is_dirty for b in self.__biome_regions.values()))
        if biomes_dirty:
            self.biomes_palette = list(set(b._biome for b in self.__biome_regions.values()))
            self.biomes_palette.sort(key=lambda b: b.name)
            biome_id_mapping = {self.biomes_palette[i]: i for i in range(len(self.biomes_palette))}
            serial_section.add_child(self._serialize_biomes(biome_id_mapping))

        if not serial_section.has('SkyLight'):
            serial_section.add_child(ByteArrayTag(tag_name='SkyLight', children=[ByteTag(-1, tag_name='None') for i in range(2048)]))

        if not serial_section.has('BlockLight'):
            serial_section.add_child(ByteArrayTag(tag_name='BlockLight', children=[ByteTag(-1, tag_name='None') for i in range(2048)]))

        return serial_section

    def _serialize_states_palette(self):
        serial_palette = ListTag(CompoundTag.clazz_id, tag_name='palette')
        for state in self.states_palette:
            palette_item = CompoundTag(tag_name='None', children=[
                StringTag(state.name, tag_name='Name')
            ])
            if len(state.props) != 0:
                serial_props = CompoundTag(tag_name='Properties')
                for name, val in state.props.items():
                    serial_props.add_child(StringTag(str(val), tag_name=name))
                palette_item.add_child(serial_props)
            serial_palette.add_child(palette_item)

        return serial_palette

    def _serialize_blockstates(self, state_mapping):
        serial_blockstates = CompoundTag(tag_name='block_states')
        serial_palette = self._serialize_states_palette()
        serial_blockstates.add_child(serial_palette)

        serial_data = LongArrayTag(tag_name='data')
        width = math.ceil(math.log(len(self.states_palette), 2))
        if width < 4:
            width = 4

        # max amount of states that fit in a long
        states_per_long = 64 // width

        # amount of longs
        arraylength = math.ceil(len(self.__blocks) / states_per_long)

        for long_index in range(arraylength):
            lng = 0
            for state in range(states_per_long):
                # insert blocks in reverse, so first one ends up most to the right
                block_index = long_index * states_per_long + (states_per_long - state - 1)

                if block_index < len(self.__blocks):
                    block = self.__blocks[block_index]
                    lng = (lng << width) + state_mapping[block._state]

            lng = int.from_bytes(lng.to_bytes(8, byteorder='big', signed=False), byteorder='big', signed=True)
            serial_data.add_child(LongTag(lng))

        serial_blockstates.add_child(serial_data)
        return serial_blockstates

    def _serialize_biomes_palette(self):
        serial_palette = ListTag(StringTag.clazz_id, tag_name='palette')
        for biome in self.biomes_palette:
            serial_palette.add_child(StringTag(biome.name, tag_name='Name'))
        return serial_palette

    def _serialize_biomes(self, biome_mapping):
        serial_biomes = CompoundTag(tag_name='biomes')
        serial_palette = self._serialize_biomes_palette()
        serial_biomes.add_child(serial_palette)

        serial_data = LongArrayTag(tag_name='data')
        width = math.ceil(math.log(len(self.biomes_palette), 2))

        # max amount of states that fit in a long
        biomes_per_long = 64 // width

        # amount of longs
        arraylength = math.ceil(len(self.__biome_regions) / biomes_per_long)

        for long_index in range(arraylength):
            lng = 0
            for state in range(biomes_per_long):
                # insert blocks in reverse, so first one ends up most to the right
                biome_index = long_index * biomes_per_long + (biomes_per_long - state - 1)

                if biome_index < len(self.__biome_regions):
                    biome_region = self.__biome_regions[biome_index]
                    lng = (lng << width) + biome_mapping[biome_region._biome]

            lng = int.from_bytes(lng.to_bytes(8, byteorder='big', signed=False), byteorder='big', signed=True)
            serial_data.add_child(LongTag(lng))

        serial_biomes.add_child(serial_data)
        return serial_biomes

    @staticmethod
    def _read_width_from_loc(long_list, width, position):
        # max amount of blockstates that fit in each long
        states_per_long = 64 // width

        # the long in which this blockstate is stored
        long_index = position // states_per_long

        # at which bit in the long this state is located
        position_in_long = (position % states_per_long) * width
        return ChunkSection._read_bits(long_list[long_index], width, position_in_long)

    @staticmethod
    def _read_bits(num, width: int, start: int):
        # create a mask of size 'width' of 1 bits
        mask = (2 ** width) - 1
        # shift it out to where we need for the mask
        mask = mask << start
        # select the bits we need
        comp = num & mask
        # move them back to where they should be
        comp = comp >> start

        return comp

    @staticmethod
    def _divide_nibbles(arry):
        rtn = []
        f2_mask = (2 ** 4) - 1
        f1_mask = f2_mask << 4
        for s in arry:
            rtn.append(s & f1_mask)
            rtn.append(s & f2_mask)

        return rtn
