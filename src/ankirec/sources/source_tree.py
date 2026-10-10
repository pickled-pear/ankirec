"""Contains classes to maintain a tree holding sources"""
from __future__ import annotations
from typing import Iterable
from uuid import uuid4
from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import Enum
from rich.tree import Tree
from rich.markup import escape

def _new_id() -> str:
    return uuid4().hex[:8]


class ItemTypes(Enum):
    SOURCE = "source"
    FOLDER = "folder"

    @classmethod
    def map_to_item(cls, item: str) -> "ItemTypes":
        try:
            return cls(item.strip().lower())
        except ValueError:
            valid = ", ".join(t.value for t in cls)
            raise ValueError(f"Unknown item type {item!r}. Expected one of: {valid}") from None


@dataclass(kw_only=True, eq=False)
class TreeItem:
    name: str
    # Stable identity. Survives renames and moves, so anything that needs to
    # point at an item (e.g. the current selection) should store this, not a path.
    id: str = field(default_factory=_new_id)
    parent: Folder | None = field(default=None, repr=False)

    @property
    def ancestors(self) -> Iterator[Folder]:
        """Parent, grandparent, ... up to the root."""
        node = self.parent
        while node is not None:
            yield node
            node = node.parent

    @property
    def full_path(self) -> str:
        """Path including the root folder, e.g. "root/maths/algebra"."""
        parts = [self.name, *(a.name for a in self.ancestors)]
        return "/".join(reversed(parts))

    @property
    def path(self) -> str:
        """Path as the user types it, without the root, e.g. "maths/algebra"."""
        return self.full_path.removeprefix("root/")

    def detach(self) -> None:
        """Remove this item from its parent."""
        if self.parent is not None:
            self.parent.children.remove(self)
            self.parent = None

    def move_to(self, folder: Folder) -> None:
        folder.add(self)

    def to_dict(self) -> dict:
        raise NotImplementedError

    def rename(self, new_name: str) -> None:
        """Renames this item. Fails if there is a dupe name in the folder"""
        if new_name == self.name:
            return
        if self.parent is not None and self.parent.get(new_name) is not None:
            raise ValueError(f"{new_name!r} already exists in {self.parent.name!r}")
        self.name = new_name


def create_item_factory(
    name: str,
    item_type: ItemTypes,
    parent: Folder | None = None,
    children: Iterable[TreeItem] = (),
) -> TreeItem:
    match item_type:
        case ItemTypes.SOURCE:
            if children:
                raise ValueError("A source cannot have children")
            item = Source(name=name)
        case ItemTypes.FOLDER:
            item = Folder(name=name)
            for child in list(children):
                item.add(child)
        case _:
            raise ValueError(f"Unhandled item type: {item_type!r}")

    if parent is not None:
        parent.add(item)
    return item


@dataclass(kw_only=True, eq=False)
class Folder(TreeItem):
    children: list[TreeItem] = field(default_factory=list)
    item_type = ItemTypes.FOLDER

    def add(self, item: TreeItem) -> None:
        if item is self or item in self.ancestors:
            raise ValueError("Cannot move a folder inside itself")
        if self.get(item.name) is not None:
            raise ValueError(f"{item.name!r} already exists in {self.name!r}")
        item.detach()
        item.parent = self
        self.children.append(item)

    def get(self, name: str) -> TreeItem | None:
        """The direct child with this name, if there is one."""
        return next((c for c in self.children if c.name == name), None)

    def find(self, item_id: str) -> TreeItem | None:
        """The descendant with this id, at any depth, if there is one."""
        if not item_id:
            return None
        return next((item for item in self.walk() if item.id == item_id), None)

    def walk(self) -> Iterator[TreeItem]:
        """Every descendant, depth first."""
        for child in self.children:
            yield child
            if isinstance(child, Folder):
                yield from child.walk()

    def sources(self) -> Iterator[Source]:
        return (item for item in self.walk() if isinstance(item, Source))

    def to_dict(self) -> dict:
        return {
            "type": "folder",
            "id": self.id,
            "name": self.name,
            "children": [c.to_dict() for c in self.children],
        }

    @classmethod
    def from_dict(cls, data: dict) -> Folder:
        # Files written before ids existed get one here; it is persisted on the next save.
        folder = cls(name=data["name"], id=data.get("id") or _new_id())
        for child in data.get("children", []):
            kind = Folder if child["type"] == "folder" else Source
            folder.add(kind.from_dict(child))
        return folder


@dataclass(kw_only=True, eq=False)
class Source(TreeItem):
    item_type = ItemTypes.SOURCE

    def to_dict(self) -> dict:
        return {
            "type": "source",
            "id": self.id,
            "name": self.name,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Source:
        return cls(name=data["name"], id=data.get("id") or _new_id())


def source_tree_rich(folder: Folder, selected_id: str = "", numbered: list | None = None) -> Tree:
    """Builds a rich Tree of a folder.
 
    If `numbered` is a list, each source is given a number in the display and
    appended to the list, so numbered[n - 1] is the source shown as n.
    """
 
    def label(item) -> str:
        if isinstance(item, Folder):
            return f"[bold blue]{escape(item.name)}/[/]"
        text = escape(item.name)
        if numbered is not None:
            numbered.append(item)
            text = f"[dim]{len(numbered)}[/]  {text}"
        if item.id == selected_id:
            text += "  [green]<- selected[/]"
        return text
 
    def fill(branch: Tree, parent: Folder) -> None:
        for child in parent.children:
            node = branch.add(label(child))
            if isinstance(child, Folder):
                fill(node, child)
 
    tree = Tree(f"[bold blue]{escape(folder.name)}/[/]")
    fill(tree, folder)
    return tree
 