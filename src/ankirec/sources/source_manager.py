"""Handles the sources feature, intended to help you organise anki cards created"""
from __future__ import annotations
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum
from typing import Iterable
import click
import copy

from ..base.json_manager import JsonManager

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
        parts = [self.name, *(a.name for a in self.ancestors)]
        return "/".join(reversed(parts))

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
            return next((c for c in self.children if c.name == name), None)

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
            "name": self.name,
            "children": [c.to_dict() for c in self.children],
        }

    # def contents(self) -> Iterator[TreeItem]:
    #     """Returns everything 1 level into the folder"""
    #     return (child for child in self.children)

    @classmethod
    def from_dict(cls, data: dict) -> Folder:
        folder = cls(name=data["name"])
        for child in data["children"]:
            kind = Folder if child["type"] == "folder" else Source
            folder.add(kind.from_dict(child))
        return folder


@dataclass(kw_only=True, eq=False)
class Source(TreeItem):
    item_type = ItemTypes.SOURCE

    def to_dict(self) -> dict:
        return {
            "type": "source",
            "name": self.name,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Source:
        return cls(name=data["name"])


class Sources(JsonManager):
    """Handles the sources feature, intended to help you organise the Anki cards you create."""

    filename = "sources"
    defaults = {
        "selected": "",
        "file_system": {"type": "folder", "name": "root", "children": []},
    }

    def __init__(self):
        super().__init__()
        self._integrity = True
        self.get()  # load and validate straight away
        pass

    def load(self) -> dict:
        """Load from disk, falling back to the defaults if there is no root folder."""
        data = super().load()
        self._integrity = self._has_root(data.get("file_system"))
        if not self._integrity:
            click.echo("Warning: sources.json has no root folder, using defaults", err=True)
            data = copy.deepcopy(self.defaults)
        return data

    def load_root_folder(self) -> Folder:
        """Loads the root folder from the dict"""
        return Folder.from_dict(self.file_system)

    # --- state -------------------------------------------------------

    @property
    def integrity(self) -> bool:
        """False if the file on disk had no root folder when last loaded."""
        return self._integrity

    @property
    def selected(self) -> str:
        """Name of the currently selected source."""
        return self.get_value("selected")

    @selected.setter
    def selected(self, name: str):
        self.set_value("selected", name)

    @property
    def file_system(self) -> dict:
        """The folder tree, starting at root."""
        return self.get_value("file_system")

    @file_system.setter
    def file_system(self, tree: dict):
        if not self._has_root(tree):
            raise ValueError("File system must start with a root folder")
        self.set_value("file_system", tree)

    # --- actions -----------------------------------------------------

    def add_item(self, name: str, parent_folder: str, item_type: str) -> TreeItem:
        """Adds an item in the given folder."""
        kind = ItemTypes.map_to_item(item_type)
        self._check_name(name)
        root = self.load_root_folder()
        folder = self._resolve_folder(root, parent_folder)
        item = create_item_factory(name, kind, parent=folder)
        self._commit(root)
        return item

    def list_items(self, target_folder: str = "root", recurse: bool = False) -> list[TreeItem]:
        """Returns the items in a folder, or every descendant if recurse is set."""
        root = self.load_root_folder()
        folder = self._resolve_folder(root, target_folder)
        return list(folder.walk()) if recurse else list(folder.children)

    def move_item(self, path: str, new_folder: str) -> TreeItem:
        """Moves an item into another folder."""
        root = self.load_root_folder()
        selected = self._selected_item(root)
        item = self._resolve(root, path)
        if item is root:
            raise ValueError("Cannot move the root folder")
        item.move_to(self._resolve_folder(root, new_folder))
        self._commit(root, selected)
        return item

    def rename_item(self, path: str, new_name: str) -> TreeItem:
        """Renames an item in place."""
        self._check_name(new_name)
        root = self.load_root_folder()
        selected = self._selected_item(root)
        item = self._resolve(root, path)
        if item is root:
            raise ValueError("Cannot rename the root folder")
        item.rename(new_name)
        self._commit(root, selected)
        return item

    def delete_item(self, path: str) -> TreeItem:
        """Deletes an item. Deleting a folder deletes all its children."""
        root = self.load_root_folder()
        selected = self._selected_item(root)
        item = self._resolve(root, path)
        if item is root:
            raise ValueError("Cannot delete the root folder. Use reset instead")
        item.detach()
        self._commit(root, selected)
        return item

    def select(self, path: str) -> Source:
        """Sets the active source."""
        root = self.load_root_folder()
        item = self._resolve(root, path)
        if not isinstance(item, Source):
            raise ValueError(f"{path!r} is a folder, not a source")
        self.selected = self._relative_path(item)
        return item

    # --- tree helpers ------------------------------------------------

    @staticmethod
    def _check_name(name: str) -> None:
        if not name or "/" in name or name == "root":
            raise ValueError(f"Invalid name {name!r}: it cannot be empty, 'root', or contain '/'")

    @staticmethod
    def _relative_path(item: TreeItem) -> str:
        return item.full_path.removeprefix("root/")

    @staticmethod
    def _resolve(root: Folder, path: str) -> TreeItem:
        """Finds an item by path, e.g. "japanese/books". "root" is the root folder."""
        parts = [p for p in path.strip().split("/") if p]
        if parts and parts[0] == "root":
            parts = parts[1:]
        node: TreeItem = root
        for part in parts:
            child = node.get(part) if isinstance(node, Folder) else None
            if child is None:
                raise ValueError(f"{path!r} not found")
            node = child
        return node

    def _resolve_folder(self, root: Folder, path: str) -> Folder:
        item = self._resolve(root, path)
        if not isinstance(item, Folder):
            raise ValueError(f"{path!r} is a source, not a folder")
        return item

    def _selected_item(self, root: Folder) -> Source | None:
        """The selected source as an object in this tree, if it still exists."""
        if not self.selected:
            return None
        try:
            item = self._resolve(root, self.selected)
        except ValueError:
            return None
        return item if isinstance(item, Source) else None

    def _commit(self, root: Folder, selected: Source | None = None) -> None:
        """Writes the tree to sources.json, keeping "selected" in step with it."""
        data = copy.deepcopy(self.get())
        data["file_system"] = root.to_dict()
        if selected is not None:
            still_in_tree = root in selected.ancestors
            data["selected"] = self._relative_path(selected) if still_in_tree else ""
        self.save(data)