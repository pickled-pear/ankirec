"""Handles the sources feature, intended to help you organise anki cards created"""
from __future__ import annotations

from pathlib import Path

import click
import copy
import re

from ..base.json_manager import JsonManager
from .source_tree import Folder, Source, TreeItem, ItemTypes, create_item_factory
# from ..base.firebase_sync import FirebaseStore # used for syncing
# from ..fields_input_api.input_api import ask_input


class Sources(JsonManager):
    """Handles the sources feature, intended to help you organise the Anki cards you create."""

    filename = "sources"
    defaults = {
        "selected": "",  # id of the selected source, "" if none
        "file_system": {"type": "folder", "name": "root", "children": []},
    }

    def __init__(self):
        super().__init__()
        self._integrity = True
        self.get()  # load and validate straight away

    def load(self) -> dict:
        """Load from disk, falling back to the defaults if there is no root folder."""
        data = super().load()
        self._integrity = self._has_root(data.get("file_system"))
        if not self._integrity:
            click.echo("Warning: sources.json has no root folder, using defaults", err=True)
            data = copy.deepcopy(self.defaults)
        return data

    def load_root_folder(self) -> Folder:
        """Builds the folder tree from the stored dict."""
        return Folder.from_dict(self.file_system)

    # --- state -------------------------------------------------------

    @property
    def integrity(self) -> bool:
        """False if the file on disk had no root folder when last loaded."""
        return self._integrity

    @property
    def file_system(self) -> dict:
        """The folder tree, starting at root."""
        return self.get_value("file_system")

    @file_system.setter
    def file_system(self, tree: dict):
        if not self._has_root(tree):
            raise ValueError("File system must start with a root folder")
        self.set_value("file_system", tree)

    @property
    def selected_id(self) -> str:
        """Id of the selected source, or "" if nothing is selected."""
        root = self.load_root_folder()
        item = self._find_selected(root)
        return item.id if item is not None else ""

    @property
    def selected(self) -> Source | None:
        """The selected source, or None if nothing is selected."""
        return self._find_selected(self.load_root_folder())

    # --- viewing -----------------------------------------------------

    def get_folder(self, path: str = "root") -> Folder:
        """A folder and everything beneath it, ready to be displayed."""
        root = self.load_root_folder()
        return self._resolve_folder(root, path)

    def list_items(self, target_folder: str = "root", recurse: bool = False) -> list[TreeItem]:
        """Returns the items in a folder, or every descendant if recurse is set."""
        folder = self.get_folder(target_folder)
        return list(folder.walk()) if recurse else list(folder.children)

    def list_sources(self, target_folder: str = "root") -> list[Source]:
        """Every source beneath a folder, in the order the tree is displayed."""
        return list(self.get_folder(target_folder).sources())

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

    def move_item(self, path: str, new_folder: str) -> TreeItem:
        """Moves an item into another folder."""
        root = self.load_root_folder()
        item = self._resolve(root, path)
        if item is root:
            raise ValueError("Cannot move the root folder")
        item.move_to(self._resolve_folder(root, new_folder))
        self._commit(root)
        return item

    def rename_item(self, path: str, new_name: str) -> TreeItem:
        """Renames an item in place."""
        self._check_name(new_name)
        root = self.load_root_folder()
        item = self._resolve(root, path)
        if item is root:
            raise ValueError("Cannot rename the root folder")
        item.rename(new_name)
        self._commit(root)
        return item

    def delete_item(self, path: str) -> TreeItem:
        """Deletes an item. Deleting a folder deletes all its children."""
        root = self.load_root_folder()
        item = self._resolve(root, path)
        if item is root:
            raise ValueError("Cannot delete the root folder. Use reset instead")
        item.detach()
        self._commit(root)
        return item

    def select(self, path: str) -> Source:
        """Sets the active source."""
        root = self.load_root_folder()
        item = self._resolve(root, path)
        if not isinstance(item, Source):
            raise ValueError(f"{path!r} is a folder, not a source")
        self._commit(root, selected=item)
        return item

    def deselect(self) -> None:
        """Clears the active source."""
        data = copy.deepcopy(self.get())
        data["selected"] = ""
        self.save(data)

    # --- tree helpers ------------------------------------------------

    @staticmethod
    def _check_name(name: str) -> None:
        if not name or "/" in name or name == "root":
            raise ValueError(f"Invalid name {name!r}: it cannot be empty, 'root', or contain '/'")

    @staticmethod
    def _resolve(root: Folder, path: str) -> TreeItem:
        """Finds an item by path. "root" is the root folder.

        The path is tried from the root first. If nothing is there, it is treated
        as the tail end of a path and searched for through the whole tree, so
        "algebra" or "maths/algebra" finds "uni/maths/algebra". A path that
        starts with "root" is always taken literally.
        """
        parts = [p for p in path.strip().split("/") if p]
        anchored = bool(parts) and parts[0] == "root"
        if anchored:
            parts = parts[1:]

        node: TreeItem | None = root
        for part in parts:
            node = node.get(part) if isinstance(node, Folder) else None
            if node is None:
                break
        if node is not None:
            return node

        if not anchored:
            matches = [
                item for item in root.walk()
                if item.path.split("/")[-len(parts):] == parts
            ]
            if len(matches) == 1:
                return matches[0]
            if matches:
                options = ", ".join(item.path for item in matches)
                raise ValueError(f"{path!r} matches more than one item: {options}. Use a longer path")
        raise ValueError(f"{path!r} not found")

    def _resolve_folder(self, root: Folder, path: str) -> Folder:
        item = self._resolve(root, path)
        if not isinstance(item, Folder):
            raise ValueError(f"{path!r} is a source, not a folder")
        return item

    def _find_selected(self, root: Folder) -> Source | None:
        """The selected source as an object in this tree, if it still exists."""
        stored = self.get_value("selected")
        if not stored:
            return None
        item = root.find(stored)
        if item is None:
            # Files written before ids existed stored a path here instead.
            try:
                item = self._resolve(root, stored)
            except ValueError:
                return None
        return item if isinstance(item, Source) else None

    def _commit(self, root: Folder, selected: Source | None = None) -> None:
        """Writes the tree to sources.json.

        Pass `selected` to change the selection. Otherwise the current selection
        is kept, and cleared only if the source it points at is no longer in the tree.
        """
        if selected is None:
            selected = self._find_selected(root)
        data = copy.deepcopy(self.get())
        data["file_system"] = root.to_dict()
        data["selected"] = selected.id if selected is not None else ""
        self.save(data)

    # --- class-level helpers -----------------------------------------

    @classmethod
    def get_selected_source_name(cls) -> str:
        """Name of the selected source, or "" if nothing is selected."""
        source = cls().selected
        return source.name if source is not None else ""

    @classmethod
    def get_selected_source_path(cls) -> str:
        """Path of the selected source, e.g. "maths/algebra", or "" if nothing is selected."""
        source = cls().selected
        return source.path if source is not None else ""

    @classmethod
    def get_source_file(cls) -> Path:
        return cls.build_path(cls.filename)

    @staticmethod
    def _has_root(tree) -> bool:
        return isinstance(tree, dict) and tree.get("name") == "root"

    @staticmethod
    def normalise_source_name(source: str) -> str:
        """Runs some normalisation on the source name to standardise it."""
        return re.sub(r"[.,;\s\"'=~@<>\[\]{}()-]+", "_", source).lower().strip("_")