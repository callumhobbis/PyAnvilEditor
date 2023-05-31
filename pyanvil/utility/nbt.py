from abc import ABC, abstractmethod
import struct
from enum import IntEnum
from typing import Any, Self
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


class BaseNBTTag(ABC):
    @abstractmethod
    def serialize(self, stream: OutputStream, include_name=True):
        pass


class NBT:

    _parsers: dict[int, type[BaseNBTTag]] = {}

    @staticmethod
    def write_string(stream: OutputStream, string: str) -> None:
        stream.write(len(string).to_bytes(2, byteorder='big', signed=False))
        for c in string:
            stream.write(ord(c).to_bytes(1, byteorder='big', signed=False))

    @staticmethod
    def register_parser(id: int, clazz: type[BaseNBTTag]) -> None:
        NBT._parsers[id] = clazz

    @staticmethod
    def create_simple_nbt_class(
        tag_id: TagType,
        class_tag_name: str,
        tag_width: int,
        tag_parser: str | bytes
    ) -> type[BaseNBTTag]:

        class DataNBTTag(BaseNBTTag):

            clazz_width: int = tag_width
            clazz_name: str = class_tag_name
            clazz_parser: str | bytes = tag_parser
            clazz_id: TagType = tag_id

            tag_name: str
            tag_value: float

            @classmethod
            def parse(cls, stream: InputStream, name: str) -> Self:
                return cls(
                    tag_value=struct.unpack(
                        cls.clazz_parser,
                        stream.read(cls.clazz_width)
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
                    stream.write(type(self).clazz_id.to_bytes(1, byteorder='big', signed=False))
                    NBT.write_string(stream, self.tag_name)

                stream.write(struct.pack(type(self).clazz_parser, self.tag_value))

            def clone(self) -> Self:
                return type(self)(self.tag_value, tag_name=self.tag_name)

            def __repr__(self) -> str:
                return f"{type(self).clazz_name}Tag '{self.tag_name}' = {str(self.tag_value)}"

            def __eq__(self, other: Self) -> bool:
                return self.tag_name == other.tag_name and self.tag_value == other.tag_value

        NBT.register_parser(tag_id, DataNBTTag)

        return DataNBTTag

    @staticmethod
    def create_string_nbt_class(tag_id: TagType) -> type[BaseNBTTag]:
        class DataNBTTag(BaseNBTTag):

            clazz_id: TagType = tag_id
            tag_name: str
            tag_value: str

            @classmethod
            def parse(cls, stream: InputStream, name: str) -> Self:
                payload_length = int.from_bytes(stream.read(2), byteorder='big', signed=False)
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
                    stream.write(type(self).clazz_id.to_bytes(1, byteorder='big', signed=False))
                    NBT.write_string(stream, self.tag_name)

                stream.write(len(self.tag_value).to_bytes(2, byteorder='big', signed=False))
                for c in self.tag_value:
                    stream.write(ord(c).to_bytes(1, byteorder='big', signed=False))

            def clone(self) -> Self:
                return type(self)(self.tag_value, tag_name=self.tag_name)

            def __repr__(self) -> str:
                return f"StringTag: {self.tag_name} = '{self.tag_value}'"

            def __eq__(self, other: Self) -> bool:
                return self.tag_name == other.tag_name and self.tag_value == other.tag_value

        NBT.register_parser(tag_id, DataNBTTag)

        return DataNBTTag

    @staticmethod
    def create_array_nbt_class(
        tag_id: TagType,
        class_tag_name: str,
        sub_type: type[BaseNBTTag],
    ) -> type[BaseNBTTag]:
        class ArrayNBTTag(BaseNBTTag):

            clazz_sub_type: type[BaseNBTTag] = sub_type
            clazz_name: str = class_tag_name
            clazz_id: TagType = tag_id

            tag_name: str
            children: list[BaseNBTTag]

            @classmethod
            def parse(cls, stream: InputStream, name: str) -> Self:
                payload_length = int.from_bytes(stream.read(4), byteorder='big', signed=True)
                tag = cls(tag_name=name)
                for i in range(payload_length):
                    tag.add_child(cls.clazz_sub_type.parse(stream, 'None'))
                return tag

            def __init__(
                self,
                tag_name: str = 'None',
                children: list[BaseNBTTag] | None = None,
            ) -> None:
                self.tag_name = tag_name
                self.children = [] if children is None else children[:]

            def add_child(self, tag: BaseNBTTag) -> None:
                self.children.append(tag)

            def name(self) -> str:
                return self.tag_name

            def print(self, indent: str = '') -> None:
                str_dat = ', '.join([str(c.get()) for c in self.children])
                print(f'{indent}{type(self).clazz_name}: {self.tag_name} size {str(len(self.children))} = [{str_dat}]')

            def get(self) -> list[int]:
                return [int(c.get()) for c in self.children]

            def serialize(
                self,
                stream: OutputStream,
                include_name: bool = True,
            ) -> None:
                if include_name:
                    stream.write(type(self).clazz_id.to_bytes(1, byteorder='big', signed=False))
                    NBT.write_string(stream, self.tag_name)

                stream.write(len(self.children).to_bytes(4, byteorder='big', signed=True))

                for tag in self.children:
                    tag.serialize(stream, include_name=False)

            def clone(self) -> Self:
                return type(self)(tag_name=self.tag_name, children=[c.clone() for c in self.children])

            def __repr__(self) -> str:
                str_dat = ', '.join([str(c.get()) for c in self.children])
                return f'{type(self).clazz_name}: {self.tag_name} size {str(len(self.children))} = [{str_dat}]'

            def __eq__(self, other: Self) -> bool:
                return (
                    self.tag_name == other.tag_name
                    and len(self.children) == len(other.children)
                    and not any([
                        not self.children[i] == other.children[i]
                        for i in range(len(self.children))
                    ])
                )

        NBT.register_parser(tag_id, ArrayNBTTag)

        return ArrayNBTTag

    @staticmethod
    def create_list_nbt_class(tag_id: TagType) -> type[BaseNBTTag]:
        class ListNBTTag(BaseNBTTag):

            clazz_id: TagType = tag_id

            tag_name: str
            sub_type_id: int
            children: list[BaseNBTTag]

            @classmethod
            def parse(cls, stream: InputStream, name: str) -> Self:
                sub_type = int.from_bytes(stream.read(1), byteorder='big', signed=False)
                payload_length = int.from_bytes(stream.read(4), byteorder='big', signed=True)
                tag = cls(sub_type, tag_name=name)
                for i in range(payload_length):
                    tag.add_child(NBT._parsers[sub_type].parse(stream, 'None'))
                return tag

            def __init__(
                self,
                sub_type_id: int,
                tag_name: str = 'None',
                children: list[BaseNBTTag] | None = None
            ) -> None:
                self.tag_name = tag_name
                self.sub_type_id = sub_type_id
                self.children = [] if children is None else children[:]

            def add_child(self, tag: BaseNBTTag) -> None:
                self.children.append(tag)

            def get(self) -> list:
                return [c.get() for c in self.children]

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
                    stream.write(type(self).clazz_id.to_bytes(1, byteorder='big', signed=False))
                    NBT.write_string(stream, self.tag_name)

                stream.write(self.sub_type_id.to_bytes(1, byteorder='big', signed=False))
                stream.write(len(self.children).to_bytes(4, byteorder='big', signed=True))

                for tag in self.children:
                    tag.serialize(stream, include_name=False)

            def clone(self) -> Self:
                return type(self)(self.sub_type_id, tag_name=self.tag_name, children=[c.clone() for c in self.children])

            def __repr__(self) -> str:
                str_dat = ', '.join([c.__repr__() for c in self.children])
                return f'ListTag: {self.tag_name} size {str(len(self.children))} = [{str_dat}]'

            def __eq__(self, other: Self) -> bool:
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

        NBT.register_parser(tag_id, ListNBTTag)

        return ListNBTTag

    @staticmethod
    def create_compund_nbt_class(tag_id: TagType) -> type[BaseNBTTag]:
        class CompundNBTTag(BaseNBTTag):

            clazz_id: TagType = tag_id

            tag_name: str
            children: dict[str, BaseNBTTag]

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
                children: list[BaseNBTTag] | None = None
            ) -> None:
                children = [] if children is None else children
                self.tag_name = tag_name
                self.children = {c.tag_name: c for c in children[:]}

            def add_child(self, tag: BaseNBTTag) -> None:
                self.children[tag.tag_name] = tag

            def get(self, name: str) -> BaseNBTTag:
                return self.children[name]

            # def get(self):
            #     return { n: v.get() for n, v in self.children }

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
                    stream.write(type(self).clazz_id.to_bytes(1, byteorder='big', signed=False))
                    NBT.write_string(stream, self.tag_name)

                for tag_name in self.children:
                    self.children[tag_name].serialize(stream, include_name=True)

                stream.write((0).to_bytes(1, byteorder='big', signed=False))

            def clone(self) -> Self:
                return type(self)(tag_name=self.tag_name, children=[v.clone() for k, v in self.children.items()])

            def __repr__(self) -> str:
                str_dat = ', '.join([c.__repr__() for name, c in self.children.items()])
                return f'CompundTag: {self.tag_name} size {str(len(self.children))} = {{{str_dat}}}]'

            def __eq__(self, other: Self) -> bool:
                passed = True
                for name, v in self.children.items():
                    if name not in other.children:
                        passed = False
                    elif other.children[name] != v:
                        passed = False
                return (
                    self.tag_name == other.tag_name
                    and len(self.children) == len(other.children)
                    and passed
                )

        NBT.register_parser(tag_id, CompundNBTTag)

        return CompundNBTTag

    @staticmethod
    def parse_nbt(stream: InputStream) -> BaseNBTTag:
        tag_type = int.from_bytes(stream.read(1), byteorder='big', signed=False)
        tag_name_length = int.from_bytes(stream.read(2), byteorder='big', signed=False)
        tag_name = stream.read(tag_name_length).decode('utf-8')

        return NBT._parsers[tag_type].parse(stream, tag_name)
