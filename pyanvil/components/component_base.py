from abc import ABC
from typing import Self


class ComponentBase(ABC):

    _parent: Self | None
    _is_dirty: bool
    _dirty_children: set['ComponentBase']

    def __init__(
        self,
        parent: 'ComponentBase' | None = None,
        dirty: bool = False
    ) -> None:
        '''Handles "dirty" propagation up the component chain.'''
        self._parent = parent
        self._is_dirty = dirty
        self._dirty_children = set()

    @property
    def is_dirty(self) -> bool:
        return self._is_dirty

    def mark_as_dirty(self) -> None:
        self._is_dirty = True
        if self._parent is not None:
            self._parent.mark_child_as_dirty(self)
            self._parent.mark_as_dirty()

    def mark_child_as_dirty(self, child: 'ComponentBase') -> None:
        self._dirty_children.add(child)

    def set_parent(self, parent: 'ComponentBase') -> None:
        self._parent = parent
