from abc import ABC, abstractmethod
import struct
from enum import IntEnum
from typing import Any, ClassVar, Self
from pyanvil.stream import InputStream, OutputStream


class TagType(IntEnum):
    END = 0
    BYTE = 1
    SHORT = 2
    INT = 3
    LONG = 4
    FLOAT = 5
    DOUBLE = 6
    BYTE_ARRAY = 7
    STRING = 8
    LIST = 9
    COMPOUND = 10
    INT_ARRAY = 11
    LONG_ARRAY = 12


class BaseTag(ABC):

    class_id: ClassVar[TagType]

    tag_name: str

    @classmethod
    @abstractmethod
    def parse(cls, stream: InputStream, name: str) -> Self:
        pass

    @abstractmethod
    def print(self, indent: str) -> None:
        pass

    @abstractmethod
    def get(self) -> Any:
        pass

    @abstractmethod
    def serialize(self, stream: OutputStream, include_name=True) -> None:
        pass

    @abstractmethod
    def clone(self) -> Self:
        pass


class BaseDataTag(BaseTag):

    class_width: ClassVar[int]
    class_name: ClassVar[str]
    class_parser: ClassVar[str | bytes]
    class_id: ClassVar[TagType]

    tag_name: str
    tag_value: float

    @classmethod
    def parse(cls, stream: InputStream, name: str) -> Self:
        return cls(
            tag_value=struct.unpack(
                cls.class_parser,
                stream.read(cls.class_width)
            )[0],
            tag_name=name
        )

    def __init__(
        self,
        tag_value: float,
        tag_name: str = 'None',
    ) -> None:
        self.tag_name = tag_name
        self.tag_value = tag_value

    def print(self, indent: str = '') -> None:
        print(indent + self.__repr__())

    def get(self) -> float:
        return self.tag_value

    def name(self) -> str:
        return self.tag_name

    def serialize(
        self,
        stream: OutputStream,
        include_name: bool = True,
    ) -> None:
        if include_name:
            stream.write(type(self).class_id.to_bytes(1))
            NBT.write_string(stream, self.tag_name)

        stream.write(struct.pack(type(self).class_parser, self.tag_value))

    def clone(self) -> Self:
        return type(self)(self.tag_value, tag_name=self.tag_name)

    def __repr__(self) -> str:
        return f"{type(self).class_name}Tag '{self.tag_name}' = {str(self.tag_value)}"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, BaseDataTag):
            return False
        return self.tag_name == other.tag_name and self.tag_value == other.tag_value


class ByteTag(BaseDataTag):
    class_width = 1
    class_name = 'Byte'
    class_parser = '>b'
    class_id = TagType.BYTE


class ShortTag(BaseDataTag):
    class_width = 2
    class_name = 'Short'
    class_parser = '>h'
    class_id = TagType.SHORT


class IntTag(BaseDataTag):
    class_width = 4
    class_name = 'Int'
    class_parser = '>i'
    class_id = TagType.INT


class LongTag(BaseDataTag):
    class_width = 8
    class_name = 'Long'
    class_parser = '>q'
    class_id = TagType.LONG


class FloatTag(BaseDataTag):
    class_width = 4
    class_name = 'Float'
    class_parser = '>f'
    class_id = TagType.FLOAT


class DoubleTag(BaseDataTag):
    class_width = 8
    class_name = 'Double'
    class_parser = '>d'
    class_id = TagType.DOUBLE


class StringTag(BaseTag):

    class_id: ClassVar[TagType] = TagType.STRING
    tag_name: str
    tag_value: str

    @classmethod
    def parse(cls, stream: InputStream, name: str) -> Self:
        payload_length = int.from_bytes(stream.read(2))
        payload = stream.read(payload_length).decode('utf-8')
        return cls(payload, tag_name=name)

    def __init__(self, tag_value: str, tag_name: str = 'None') -> None:
        self.tag_name = tag_name
        self.tag_value = tag_value

    def print(self, indent: str = '') -> None:
        print(indent + 'String: ' + self.tag_name + ' = ' + str(self.tag_value))

    def get(self) -> str:
        return self.tag_value

    def name(self) -> str:
        return self.tag_name

    def serialize(
        self,
        stream: OutputStream,
        include_name: bool = True,
    ) -> None:
        if include_name:
            stream.write(type(self).class_id.to_bytes(1))
            NBT.write_string(stream, self.tag_name)

        stream.write(len(self.tag_value).to_bytes(2))
        for c in self.tag_value:
            stream.write(ord(c).to_bytes(1))

    def clone(self) -> Self:
        return type(self)(self.tag_value, tag_name=self.tag_name)

    def __repr__(self) -> str:
        return f"StringTag: {self.tag_name} = '{self.tag_value}'"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, StringTag):
            return False
        return self.tag_name == other.tag_name and self.tag_value == other.tag_value


class BaseArrayTag(BaseTag):

    class_sub_type: ClassVar[type[BaseDataTag]]
    class_name: ClassVar[str]
    class_id: ClassVar[TagType]

    tag_name: str
    children: list[BaseDataTag]

    @classmethod
    def parse(cls, stream: InputStream, name: str) -> Self:
        payload_length = int.from_bytes(stream.read(4), signed=True)
        tag = cls(tag_name=name)
        for i in range(payload_length):
            tag.add_child(cls.class_sub_type.parse(stream, 'None'))
        return tag

    def __init__(
        self,
        tag_name: str = 'None',
        children: list[BaseDataTag] | None = None,
    ) -> None:
        self.tag_name = tag_name
        self.children = [] if children is None else children[:]

    def add_child(self, tag: BaseDataTag) -> None:
        self.children.append(tag)

    def name(self) -> str:
        return self.tag_name

    def print(self, indent: str = '') -> None:
        str_dat = ', '.join([str(c.get()) for c in self.children])
        print(f'{indent}{type(self).class_name}: {self.tag_name} size {str(len(self.children))} = [{str_dat}]')

    def get(self) -> list[int]:
        return [int(c.get()) for c in self.children]

    def __getitem__(self, index: int) -> BaseDataTag:
        return self.children[index]

    def serialize(
        self,
        stream: OutputStream,
        include_name: bool = True,
    ) -> None:
        if include_name:
            stream.write(type(self).class_id.to_bytes(1))
            NBT.write_string(stream, self.tag_name)

        stream.write(len(self.children).to_bytes(4, signed=True))

        for tag in self.children:
            tag.serialize(stream, include_name=False)

    def clone(self) -> Self:
        return type(self)(tag_name=self.tag_name, children=[c.clone() for c in self.children])

    def __repr__(self) -> str:
        str_dat = ', '.join([str(c.get()) for c in self.children])
        return f'{type(self).class_name}: {self.tag_name} size {str(len(self.children))} = [{str_dat}]'

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, BaseArrayTag):
            return False
        return (
            self.tag_name == other.tag_name
            and len(self.children) == len(other.children)
            and not any([
                not self.children[i] == other.children[i]
                for i in range(len(self.children))
            ])
        )


class ByteArrayTag(BaseArrayTag):
    class_sub_type = ByteTag
    class_name = 'ByteArray'
    class_id = TagType.BYTE_ARRAY


class IntArrayTag(BaseArrayTag):
    class_sub_type = IntTag
    class_name = 'IntArray'
    class_id = TagType.INT_ARRAY


class LongArrayTag(BaseArrayTag):
    class_sub_type = LongTag
    class_name = 'LongArray'
    class_id = TagType.LONG_ARRAY


class ListTag(BaseTag):

    class_id: ClassVar[TagType] = TagType.LIST

    tag_name: str
    sub_type_id: int
    children: list[BaseTag]

    @classmethod
    def parse(cls, stream: InputStream, name: str) -> Self:
        sub_type = int.from_bytes(stream.read(1))
        payload_length = int.from_bytes(stream.read(4), signed=True)
        tag = cls(sub_type, tag_name=name)
        for i in range(payload_length):
            tag.add_child(NBT._parsers[sub_type].parse(stream, 'None'))
        return tag

    def __init__(
        self,
        sub_type_id: int,
        tag_name: str = 'None',
        children: list[BaseTag] | None = None
    ) -> None:
        self.tag_name = tag_name
        self.sub_type_id = sub_type_id
        self.children = [] if children is None else children[:]

    def add_child(self, tag: BaseTag) -> None:
        self.children.append(tag)

    def get(self) -> list:
        return [c.get() for c in self.children]

    def __getitem__(self, index: int) -> BaseTag:
        return self.children[index]

    def name(self) -> str:
        return self.tag_name

    def print(self, indent: str = '') -> None:
        print(indent + 'List: ' + self.tag_name + ' size ' + str(len(self.children)))
        for c in self.children:
            c.print(indent + '  ')

    def serialize(
        self,
        stream: OutputStream,
        include_name: bool = True,
    ) -> None:
        if include_name:
            stream.write(type(self).class_id.to_bytes(1))
            NBT.write_string(stream, self.tag_name)

        stream.write(self.sub_type_id.to_bytes(1))
        stream.write(len(self.children).to_bytes(4, signed=True))

        for tag in self.children:
            tag.serialize(stream, include_name=False)

    def clone(self) -> Self:
        return type(self)(self.sub_type_id, tag_name=self.tag_name, children=[c.clone() for c in self.children])

    def __repr__(self) -> str:
        str_dat = ', '.join([c.__repr__() for c in self.children])
        return f'ListTag: {self.tag_name} size {str(len(self.children))} = [{str_dat}]'

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ListTag):
            return False
        return (
            self.tag_name == other.tag_name
            and len(self.children) == len(other.children)
            and (
                len(self.children) == 0
                or not any([
                    not self.children[i] == other.children[i]
                    for i in range(len(self.children))
                ])
            )
        )


class CompoundTag(BaseTag):

    class_id: ClassVar[TagType] = TagType.COMPOUND

    tag_name: str
    children: dict[str, BaseTag]

    @classmethod
    def parse(cls, stream: InputStream, name: str) -> Self:
        tag = cls(tag_name=name)
        while stream.peek() != 0:  # end tag
            tag.add_child(NBT.parse_nbt(stream))
        stream.read(1)  # get rid of the end tag
        return tag

    def __init__(
        self,
        tag_name: str = 'None',
        children: list[BaseTag] | None = None
    ) -> None:
        children = [] if children is None else children
        self.tag_name = tag_name
        self.children = {c.tag_name: c for c in children[:]}

    def add_child(self, tag: BaseTag) -> None:
        self.children[tag.tag_name] = tag

    def get(self) -> dict[str, Any]:
        return {n: v.get() for n, v in self.children.items()}

    def __getitem__(self, name: str) -> BaseTag:
        return self.children[name]

    def __contains__(self, name: str) -> bool:
        return name in self.children

    def name(self) -> str:
        return self.tag_name

    def has(self, name: str) -> bool:
        return name in self.children

    def to_dict(self) -> dict[str, Any]:
        nd = {}
        for p in self.children:
            nd[p] = self.children[p].get()
        return nd

    def print(self, indent: str = '') -> None:
        print(indent + 'Compound: ' + self.tag_name + ' size ' + str(len(self.children)))
        for c in self.children:
            self.children[c].print(indent + '  ')

    def serialize(self, stream: OutputStream, include_name: bool = True) -> None:
        if include_name:
            stream.write(type(self).class_id.to_bytes(1))
            NBT.write_string(stream, self.tag_name)

        for tag_name in self.children:
            self.children[tag_name].serialize(stream, include_name=True)

        stream.write((0).to_bytes(1))

    def clone(self) -> Self:
        return type(self)(tag_name=self.tag_name, children=[v.clone() for k, v in self.children.items()])

    def __repr__(self) -> str:
        str_dat = ', '.join([c.__repr__() for name, c in self.children.items()])
        return f'CompoundTag: {self.tag_name} size {str(len(self.children))} = {{{str_dat}}}]'

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, CompoundTag):
            return False
        for name, v in self.children.items():
            if name not in other.children:
                return False
            if other.children[name] != v:
                return False
        return (
            self.tag_name == other.tag_name
            and len(self.children) == len(other.children)
        )


class NBT:

    _parsers: dict[int, type[BaseTag]] = {}

    @staticmethod
    def write_string(stream: OutputStream, string: str) -> None:
        stream.write(len(string).to_bytes(2))
        for c in string:
            stream.write(ord(c).to_bytes(1))

    @staticmethod
    def register_parser(id: int, class_: type[BaseTag]) -> None:
        NBT._parsers[id] = class_

    @staticmethod
    def parse_nbt(stream: InputStream) -> BaseTag:
        tag_type = int.from_bytes(stream.read(1))
        tag_name_length = int.from_bytes(stream.read(2))
        tag_name = stream.read(tag_name_length).decode('utf-8')

        return NBT._parsers[tag_type].parse(stream, tag_name)


tag_classes: list[type[BaseTag]] = [
    ByteTag, ShortTag, IntTag, LongTag, FloatTag, DoubleTag, StringTag,
    ByteArrayTag, IntArrayTag, LongArrayTag, ListTag, CompoundTag
]
for tag_class in tag_classes:
    NBT.register_parser(tag_class.class_id, tag_class)
