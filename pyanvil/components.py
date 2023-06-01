from __future__ import annotations
import io

import math
import logging
import sys
from types import TracebackType
import zlib
from abc import ABC
from enum import IntEnum
from io import FileIO
from pathlib import Path
from time import time
from typing import Generator, Self, BinaryIO, Union

from pyanvil.coordinate import AbsoluteCoordinate, BiomeCoordinate, ChunkCoordinate
from pyanvil.nbt import NBT, BaseTag, ByteArrayTag, ByteTag, CompoundTag, StringTag, LongArrayTag, LongTag, ListTag
from pyanvil.stream import InputStream, OutputStream


class Sizes(IntEnum):
    REGION_WIDTH = 32
    SUBCHUNK_WIDTH = 16,
    BIOME_REGION_WIDTH = 4,
    CHUNK_SECTOR_SIZE = 4096  # 4KiB


class ComponentBase(ABC):

    _parent: ComponentBase | None
    _is_dirty: bool
    _dirty_children: set[ComponentBase]

    def __init__(
        self,
        parent: ComponentBase | None = None,
        dirty: bool = False
    ) -> None:
        '''Handles "dirty" propagation up the component chain.'''
        self._parent = parent
        self._is_dirty = dirty
        self._dirty_children = set()

    @property
    def is_dirty(self) -> bool:
        return self._is_dirty

    @is_dirty.setter
    def is_dirty(self, value: bool) -> None:
        self._is_dirty = value

    def mark_as_dirty(self) -> None:
        self._is_dirty = True
        if self._parent is not None:
            self._parent.mark_child_as_dirty(self)
            self._parent.mark_as_dirty()

    def mark_child_as_dirty(self, child: ComponentBase) -> None:
        self._dirty_children.add(child)

    def set_parent(self, parent: ComponentBase) -> None:
        self._parent = parent


class Block(ComponentBase):

    _parent: ComponentBase | None
    is_dirty: bool
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
        self.is_dirty = True
        if isinstance(state, BlockState):
            self._state = state
        else:
            self._state = BlockState(state, {})
        self.mark_as_dirty()

    def get_state(self) -> BlockState:
        return self._state.clone()


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

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, BlockState):
            return False
        return self.name == other.name and self.props == other.props

    def clone(self) -> BlockState:
        return BlockState(self.name, self.props.copy())


class BiomeRegion(ComponentBase):

    _parent: ComponentBase | None
    is_dirty: bool
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
        self.is_dirty = True
        if isinstance(biome, Biome):
            self._biome = biome
        else:
            self._biome = Biome(biome)
        self.mark_as_dirty()

    def get_biome(self) -> Biome:
        return self._biome.clone()


class Biome:

    name: str

    def __init__(self, name: str) -> None:
        self.name = name

    def __str__(self) -> str:
        return f'Biome({self.name})'

    def __hash__(self) -> int:
        return hash(self.name)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Biome):
            return False
        return self.name == other.name

    def clone(self) -> Biome:
        return Biome(self.name)


class ChunkSection(ComponentBase):

    _parent: Chunk | None
    is_dirty: bool
    _dirty_children: set[ComponentBase]

    __blocks: dict[int, Block]
    __biome_regions: dict[int, BiomeRegion]
    raw_section: CompoundTag
    y_index: int
    states_palette: list[BlockState]
    biomes_palette: list[Biome]

    def __init__(
        self,
        raw_section: CompoundTag,
        y_index: int,
        blocks: dict[int, Block] | None = None,
        biome_regions: dict[int, BiomeRegion] | None = None,
        parent_chunk: Chunk | None = None
    ) -> None:
        super().__init__(parent=parent_chunk)

        blocks = {} if blocks is None else blocks
        self.__blocks = blocks

        biome_regions = {} if biome_regions is None else biome_regions
        self.__biome_regions = biome_regions

        self.raw_section = raw_section
        self.y_index = y_index

    def get_block(self, block_pos: AbsoluteCoordinate):
        x = block_pos.x
        y = block_pos.y
        z = block_pos.z

        return self.__blocks[x + z * Sizes.SUBCHUNK_WIDTH + y * Sizes.SUBCHUNK_WIDTH ** 2]

    def set_blocks(self, blocks: dict[int, Block] | None):
        self.__blocks = {} if blocks is None else blocks

    def get_biome(self, biome_pos: BiomeCoordinate):
        x = biome_pos.x
        y = biome_pos.y
        z = biome_pos.z

        biome_region_count = Sizes.SUBCHUNK_WIDTH // Sizes.BIOME_REGION_WIDTH
        return self.__biome_regions[x + z * biome_region_count + y * biome_region_count ** 2]

    def set_biome_regions(self, biome_regions: dict[int, BiomeRegion] | None):
        self.__biome_regions = {} if biome_regions is None else biome_regions

    @staticmethod
    def from_nbt(
        section_nbt: CompoundTag,
        parent_chunk: Chunk | None = None,
    ) -> ChunkSection:
        states_palette = [
            BlockState(
                state['Name'].get(),
                state['Properties'].to_dict() if 'Properties' in state else {}
            ) for state in section_nbt['block_states']['palette']
        ]
        if len(states_palette) == 1:
            state_indexes = [0] * 16**3
        else:
            flatstates = [c.get() for c in section_nbt['block_states']['data']]
            pack_size = max(4, (len(states_palette) - 1).bit_length())
            state_indexes = [
                ChunkSection._read_width_from_loc(flatstates, pack_size, i) for i in range(Sizes.SUBCHUNK_WIDTH ** 3)
            ]

        block_lights = ChunkSection._divide_nibbles(section_nbt['BlockLight'].get()) if 'BlockLight' in section_nbt else None
        sky_lights = ChunkSection._divide_nibbles(section_nbt['SkyLight'].get()) if 'SkyLight' in section_nbt else None
        section = ChunkSection(section_nbt, section_nbt['Y'].get(), parent_chunk=parent_chunk)
        blocks: dict[int, Block] = dict()
        for i, state_index in enumerate(state_indexes):
            state = states_palette[state_index]
            block_light = block_lights[i] if block_lights else 0
            sky_light = sky_lights[i] if sky_lights else 0
            blocks[i] = Block(state=state, block_light=block_light, sky_light=sky_light, parent_chunk_section=section)
        section.set_blocks(blocks=blocks)

        biomes_palette = [
            Biome(
                biome.get()
            ) for biome in section_nbt['biomes']['palette']
        ]
        if len(biomes_palette) == 1:
            biome_indexes = [0] * 16**3
        else:
            flatbiomes = [c.get() for c in section_nbt['biomes']['data']]
            pack_size = (len(biomes_palette) - 1).bit_length()
            biome_indexes = ChunkSection._read_width_from_loc(flatbiomes, pack_size, (Sizes.SUBCHUNK_WIDTH//Sizes.BIOME_REGION_WIDTH)**3)

        biome_regions: dict[int, BiomeRegion] = dict()
        for i, biome_index in enumerate(biome_indexes):
            biome = biomes_palette[biome_index]
            biome_regions[i] = BiomeRegion(biome=biome, parent_chunk_section=section)
        section.set_biome_regions(biome_regions=biome_regions)

        return section

    def serialize(self) -> CompoundTag:
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

    def _serialize_states_palette(self) -> ListTag:
        serial_palette = ListTag(CompoundTag.class_id, tag_name='palette')
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

    def _serialize_blockstates(
        self,
        state_mapping: dict[BlockState, int],
    ) -> CompoundTag:
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

            lng = int.from_bytes(lng.to_bytes(8), signed=True)
            serial_data.add_child(LongTag(lng))

        serial_blockstates.add_child(serial_data)
        return serial_blockstates

    def _serialize_biomes_palette(self) -> ListTag:
        serial_palette = ListTag(StringTag.class_id, tag_name='palette')
        for biome in self.biomes_palette:
            serial_palette.add_child(StringTag(biome.name, tag_name='Name'))
        return serial_palette

    def _serialize_biomes(
        self,
        biome_mapping: dict[Biome, int],
    ) -> CompoundTag:
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

            lng = int.from_bytes(lng.to_bytes(8), signed=True)
            serial_data.add_child(LongTag(lng))

        serial_biomes.add_child(serial_data)
        return serial_biomes

    @staticmethod
    def _read_width_from_loc(
        longs: list[int],
        width: int,
        position: int,
    ) -> int:
        # max amount of blockstates that fit in each long
        states_per_long = 64 // width

        # the long in which this blockstate is stored
        long_index = position // states_per_long

        # at which bit in the long this state is located
        long_pos = (position % states_per_long) * width
        return ChunkSection._read_bits(longs[long_index], width, long_pos)

    @staticmethod
    def _read_bits(num: int, width: int, start: int) -> int:
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
    def _divide_nibbles(arry: list[int]) -> list[int]:
        rtn = []
        f2_mask = (2 ** 4) - 1
        f1_mask = f2_mask << 4
        for s in arry:
            rtn.append(s & f1_mask)
            rtn.append(s & f2_mask)

        return rtn


class Chunk(ComponentBase):

    _parent: Region | None
    is_dirty: bool
    _dirty_children: set[ComponentBase]

    coordinate: ChunkCoordinate
    sections: dict[int, ChunkSection]
    raw_nbt: CompoundTag
    orig_size: int
    __index: int

    def __init__(
        self,
        coord: ChunkCoordinate,
        sections: dict[int, ChunkSection],
        raw_nbt: CompoundTag,
        orig_size: int,
        parent_region: Region | None = None,
    ) -> None:
        super().__init__(parent=parent_region)
        self.coordinate = coord
        self.sections = sections
        self.raw_nbt = raw_nbt
        self.orig_size = orig_size
        self.__index = Chunk.to_region_chunk_index(coord)
        for section in self.sections.values():
            section.set_parent(self)

    def set_parent_region(self, region: Region) -> None:
        self._parent = region

    @staticmethod
    def from_file(
        file: BinaryIO,
        offset: int,
        sections: int,
        parent_region: Region | None = None,
    ) -> Chunk:
        file.seek(offset)
        datalen = int.from_bytes(file.read(4))
        file.read(1)  # Compression scheme
        decompressed = zlib.decompress(file.read(datalen - 1))
        data: CompoundTag = NBT.parse_nbt(InputStream(decompressed))
        x = data['xPos'].get()
        z = data['zPos'].get()
        return Chunk(ChunkCoordinate(x, z), Chunk.__unpack_sections(data), data, datalen, parent_region=parent_region)

    def package_and_compress(self) -> bytes:
        """Serialize and compress chunk to raw data"""
        stream = OutputStream()
        # Serialize and compress chunk
        chunkNBT = self.pack()
        chunkNBT.serialize(stream)
        return zlib.compress(stream.get_data())

    @property
    def index(self) -> int:
        return self.__index

    @staticmethod
    def to_region_chunk_index(coord: ChunkCoordinate) -> int:
        return (coord.x % Sizes.REGION_WIDTH) + (coord.z % Sizes.REGION_WIDTH) * Sizes.REGION_WIDTH

    def get_block(self, block_pos: AbsoluteCoordinate) -> Block:
        return self.get_section(block_pos.y).get_block(
            AbsoluteCoordinate(
                block_pos.x % Sizes.SUBCHUNK_WIDTH,
                block_pos.y % Sizes.SUBCHUNK_WIDTH,
                block_pos.z % Sizes.SUBCHUNK_WIDTH,
            )
        )

    def get_section(self, y: int) -> ChunkSection:
        key = int(y / Sizes.SUBCHUNK_WIDTH)
        if key not in self.sections:
            self.sections[key] = ChunkSection(
                CompoundTag(),
                key,
                blocks={i: Block(dirty=True) for i in range(Sizes.REGION_WIDTH**3)},
                biome_regions={i: BiomeRegion(dirty=True) for i in range((Sizes.REGION_WIDTH//Sizes.BIOME_REGION_WIDTH)**3)},
                parent_chunk=self
            )
        return self.sections[key]

    def find_like(self, string) -> list[tuple[tuple[int, int, int], Block]]:
        results = []
        for sec in self.sections:
            section = self.sections[sec]
            for x1 in range(Sizes.SUBCHUNK_WIDTH):
                for y1 in range(Sizes.SUBCHUNK_WIDTH):
                    for z1 in range(Sizes.SUBCHUNK_WIDTH):
                        if string in section.get_block(AbsoluteCoordinate(x1, y1, z1))._state.name:
                            results.append(
                                (
                                    (
                                        x1 + self.coordinate.x * Sizes.SUBCHUNK_WIDTH,
                                        y1 + sec * Sizes.SUBCHUNK_WIDTH,
                                        z1 + self.coordinate.z * Sizes.SUBCHUNK_WIDTH,
                                    ),
                                    section.get_block(AbsoluteCoordinate(x1, y1, z1)),
                                )
                            )
        return results

    # Blockstates are packed based on the number of values in the pallet.
    # This selects the pack size, then splits out the ids
    @staticmethod
    def __unpack_sections(raw_nbt: BaseTag) -> dict[int, ChunkSection]:
        sections = {}
        for section in raw_nbt['sections']:
            sections[section['Y'].get()] = ChunkSection.from_nbt(section)
        return sections

    def pack(self) -> CompoundTag:
        new_sections = ListTag(
            CompoundTag.class_id,
            tag_name='sections',
            children=[sec.serialize() for sec in self.sections.values()]
        )
        new_nbt = self.raw_nbt.clone()
        new_nbt.add_child(new_sections)

        return new_nbt

    def __str__(self) -> str:
        return f'Chunk({str(self.coordinate.x)},{str(self.coordinate.z)})'


class Region(ComponentBase):

    _parent: None
    is_dirty: bool
    _dirty_children: set[ComponentBase]

    file_path: str | Path
    file: io.BufferedRandom | None
    chunks: dict[int, Chunk]
    __chunk_locations: list[list[int]] | None
    __timestamps: list[int] | None
    __chunk_location_data: bytes
    __timestamps_data: bytes
    __raw_chunk_data: dict[int, bytes]

    def __init__(self, region_file: str | Path):
        super().__init__(parent=None)
        self.file_path = region_file
        self.file = None
        self.chunks: dict[int, Chunk] = {}

        # locations and timestamps are parallel lists.
        # Indexes in one can be accessed in the other as well.
        self.__chunk_locations = None
        self.__timestamps = None

        # Uninterpreted chunks mapped to their index
        self.__raw_chunk_data = {}

        self.__load_from_file()

    def __enter__(self) -> Region:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self.is_dirty:
            self.save()
        if self.file:
            self.file.close()

    def __load_from_file(self) -> None:
        self.__ensure_file_open()
        # 8KiB header. 4KiB chunk location table, 4KiB timestamp table
        self.__chunk_location_data = self.file.read(4 * 1024)
        self.__timestamps_data = self.file.read(4 * 1024)
        self.__read_chunks_to_memory()

    def __ensure_file_open(self) -> None:
        if not self.file:
            self.file = open(self.file_path, mode='r+b')

    def __read_chunks_to_memory(self) -> None:
        for offset, size in self.chunk_locations:
            self.file.seek(offset)
            self.__raw_chunk_data[offset] = self.file.read(size)

    def save(self) -> None:
        self.__ensure_file_open()
        self.file.seek((4 + 4) * 1024)  # Skip to the end of the region header
        # Sort chunks by offset
        #self.chunks.sort(key=lambda chunk: self.__chunk_locations[chunk.index][0])

        rest_of_the_data = self.__read_region_after_header()

        for index, chunk in self.chunks.items():
            self.timestamps[index] = int(time())

            chunk_data: bytes = chunk.package_and_compress()

            datalen = len(chunk_data)
            block_data_len = math.ceil((datalen + 5) / 4096.0) * 4096

            # Constuct new data block
            data: bytes = (datalen + 1).to_bytes(4)  # Total length of chunk data
            data += (2).to_bytes(1)
            data += chunk_data
            data += (0).to_bytes(block_data_len - (datalen + 5))

            loc = self.__chunk_locations[index]
            original_sector_length = loc[1]
            data_len_diff = block_data_len - original_sector_length
            if data_len_diff != 0 and self.debug:
                print(f'Danger: Diff is {data_len_diff}, shifting required!')

            self.__chunk_locations[index][1] = block_data_len

            if loc[0] == 0 or loc[1] == 0:
                print('Chunk not generated', chunk)
                sys.exit(0)

            # Adjust sectors after this one that need their locations recalculated
            for i, other_loc in enumerate(self.__chunk_locations):
                if other_loc[0] > loc[0]:
                    self.__chunk_locations[i][0] = other_loc[0] + data_len_diff

            header_length = 2 * 4096
            rest_of_the_data[(loc[0] - header_length):(loc[0] + original_sector_length - header_length)] = data
            logging.debug(f'Saving {chunk} with', {'loc': loc, 'new_len': datalen, 'old_len': chunk.orig_size, 'sector_len': block_data_len})

        # rewrite entire file with new chunks and locations recorded
        self.file.seek(0)
        self.__write_header(self.file)

        self.file.write(rest_of_the_data)

        required_padding = (math.ceil(self.file.tell() / 4096.0) * 4096) - self.file.tell()

        self.file.write((0).to_bytes(required_padding))

        self.is_dirty = False

    def __write_header(self, file: BinaryIO) -> None:
        for c_loc in self.__chunk_locations:
            file.write(int(c_loc[0] / 4096).to_bytes(3))
            file.write(int(c_loc[1] / 4096).to_bytes(1))

        for ts in self.timestamps:
            file.write(ts.to_bytes(4))

    def get_chunk(self, coord: ChunkCoordinate) -> Chunk:
        chunk_index = Chunk.to_region_chunk_index(coord)
        print(f'Loading {coord.x}x {coord.z}z from {self.file_path}')
        if not chunk_index in self.chunks:
            self.__ensure_file_open()
            offset, sections = self.chunk_locations[chunk_index]
            chunk = Chunk.from_file(file=self.file, offset=offset, sections=sections, parent_region=self)
            self.chunks[chunk_index] = chunk
            return chunk
        else:
            return self.chunks[chunk_index]

    def __read_region_after_header(self) -> bytearray:
        self.__ensure_file_open()
        self.file.seek((4 + 4) * 1024)
        return bytearray(self.file.read())

    @property
    def chunk_locations(self) -> list[list[int]]:
        if self.__chunk_locations is None:
            # Interpret header chunk
            self.__chunk_locations = [
                # Nested list containing 2 elements, one taking 3 bytes, one with 1 byte
                [
                    int.from_bytes(offset) * Sizes.CHUNK_SECTOR_SIZE,
                    size * Sizes.CHUNK_SECTOR_SIZE
                ]
                for (*offset, size) in Region.iterate_in_groups(
                    self.__chunk_location_data, group_size=4, start=0, end=4 * 1024
                )
            ]
        return self.__chunk_locations

    @property
    def timestamps(self) -> list[int]:
        if self.__timestamps is None:
            # Interpret header chunk
            self.__timestamps = [
                int.from_bytes(t)
                for t in Region.iterate_in_groups(
                    self.__timestamps_data, group_size=4, start=4 * 1024, end=8 * 1024
                )
            ]
        return self.__timestamps

    @staticmethod
    def iterate_in_groups(
        container: bytes,
        group_size: int,
        start: int,
        end: int,
    ) -> Generator[bytes, None, None]:
        return (
            container[i: (i + group_size)]
            for i in range(start, end, group_size)
        )
