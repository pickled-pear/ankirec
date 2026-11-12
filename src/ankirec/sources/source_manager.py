# """Handles the sources feature, intended to help you organise anki cards created"""
# from __future__ import annotations

# from pathlib import Path

# import click
# import copy
# import re

# from ..base.json_manager import JsonManager
# from .source_tree import Folder, Source, TreeItem, ItemTypes, create_item_factory
# # from ..base.firebase_sync import FirebaseStore # used for syncing
# # from ..fields_input_api.input_api import ask_input


# class Sources(JsonManager):
#     """Handles the sources feature, intended to help you organise the Anki cards you create."""

#     filename = "sources"
#     defaults = {
#         "selected": "",  # id of the selected source, "" if none
#         "file_system": {"type": "folder", "name": "root", "children": []},
#     }

#     def __init__(self):
#         super().__init__()
#         self._integrity = True
#         self.get()  # load and validate straight away

#     def load(self) -> dict:
#         """Load from disk, falling back to the defaults if there is no root folder."""
#         data = super().load()
#         self._integrity = self._has_root(data.get("file_system"))
#         if not self._integrity:
#             click.echo("Warning: sources.json has no root folder, using defaults", err=True)
#             data = copy.deepcopy(self.defaults)
#         return data

#     def load_root_folder(self) -> Folder:
#         """Builds the folder tree from the stored dict."""
#         return Folder.from_dict(self.file_system)

#     # --- state -------------------------------------------------------

#     @property
#     def integrity(self) -> bool:
#         """False if the file on disk had no root folder when last loaded."""
#         return self._integrity

#     @property
#     def file_system(self) -> dict:
#         """The folder tree, starting at root."""
#         return self.get_value("file_system")

#     @file_system.setter
#     def file_system(self, tree: dict):
#         if not self._has_root(tree):
#             raise ValueError("File system must start with a root folder")
#         self.set_value("file_system", tree)

#     @property
#     def selected_id(self) -> str:
#         """Id of the selected source, or "" if nothing is selected."""
#         root = self.load_root_folder()
#         item = self._find_selected(root)
#         return item.id if item is not None else ""

#     @property
#     def selected(self) -> Source | None:
#         """The selected source, or None if nothing is selected."""
#         return self._find_selected(self.load_root_folder())

#     # --- viewing -----------------------------------------------------

#     def get_folder(self, path: str = "root") -> Folder:
#         """A folder and everything beneath it, ready to be displayed."""
#         root = self.load_root_folder()
#         return self._resolve_folder(root, path)

#     def list_items(self, target_folder: str = "root", recurse: bool = False) -> list[TreeItem]:
#         """Returns the items in a folder, or every descendant if recurse is set."""
#         folder = self.get_folder(target_folder)
#         return list(folder.walk()) if recurse else list(folder.children)

#     def list_sources(self, target_folder: str = "root") -> list[Source]:
#         """Every source beneath a folder, in the order the tree is displayed."""
#         return list(self.get_folder(target_folder).sources())

#     # --- actions -----------------------------------------------------

#     def add_item(self, name: str, parent_folder: str, item_type: str) -> TreeItem:
#         """Adds an item in the given folder."""
#         kind = ItemTypes.map_to_item(item_type)
#         self._check_name(name)
#         root = self.load_root_folder()
#         folder = self._resolve_folder(root, parent_folder)
#         item = create_item_factory(name, kind, parent=folder)
#         self._commit(root)
#         return item

#     def move_item(self, path: str, new_folder: str) -> TreeItem:
#         """Moves an item into another folder."""
#         root = self.load_root_folder()
#         item = self._resolve(root, path)
#         if item is root:
#             raise ValueError("Cannot move the root folder")
#         item.move_to(self._resolve_folder(root, new_folder))
#         self._commit(root)
#         return item

#     def rename_item(self, path: str, new_name: str) -> TreeItem:
#         """Renames an item in place."""
#         self._check_name(new_name)
#         root = self.load_root_folder()
#         item = self._resolve(root, path)
#         if item is root:
#             raise ValueError("Cannot rename the root folder")
#         item.rename(new_name)
#         self._commit(root)
#         return item

#     def delete_item(self, path: str) -> TreeItem:
#         """Deletes an item. Deleting a folder deletes all its children."""
#         root = self.load_root_folder()
#         item = self._resolve(root, path)
#         if item is root:
#             raise ValueError("Cannot delete the root folder. Use reset instead")
#         item.detach()
#         self._commit(root)
#         return item

#     def select(self, path: str) -> Source:
#         """Sets the active source."""
#         root = self.load_root_folder()
#         item = self._resolve(root, path)
#         if not isinstance(item, Source):
#             raise ValueError(f"{path!r} is a folder, not a source")
#         self._commit(root, selected=item)
#         return item

#     def deselect(self) -> None:
#         """Clears the active source."""
#         data = copy.deepcopy(self.get())
#         data["selected"] = ""
#         self.save(data)

#     # --- tree helpers ------------------------------------------------

#     @staticmethod
#     def _check_name(name: str) -> None:
#         if not name or "/" in name or name == "root":
#             raise ValueError(f"Invalid name {name!r}: it cannot be empty, 'root', or contain '/'")

#     @staticmethod
#     def _resolve(root: Folder, path: str) -> TreeItem:
#         """Finds an item by path. "root" is the root folder.

#         The path is tried from the root first. If nothing is there, it is treated
#         as the tail end of a path and searched for through the whole tree, so
#         "algebra" or "maths/algebra" finds "uni/maths/algebra". A path that
#         starts with "root" is always taken literally.
#         """
#         parts = [p for p in path.strip().split("/") if p]
#         anchored = bool(parts) and parts[0] == "root"
#         if anchored:
#             parts = parts[1:]

#         node: TreeItem | None = root
#         for part in parts:
#             node = node.get(part) if isinstance(node, Folder) else None
#             if node is None:
#                 break
#         if node is not None:
#             return node

#         if not anchored:
#             matches = [
#                 item for item in root.walk()
#                 if item.path.split("/")[-len(parts):] == parts
#             ]
#             if len(matches) == 1:
#                 return matches[0]
#             if matches:
#                 options = ", ".join(item.path for item in matches)
#                 raise ValueError(f"{path!r} matches more than one item: {options}. Use a longer path")
#         raise ValueError(f"{path!r} not found")

#     def _resolve_folder(self, root: Folder, path: str) -> Folder:
#         item = self._resolve(root, path)
#         if not isinstance(item, Folder):
#             raise ValueError(f"{path!r} is a source, not a folder")
#         return item

#     def _find_selected(self, root: Folder) -> Source | None:
#         """The selected source as an object in this tree, if it still exists."""
#         stored = self.get_value("selected")
#         if not stored:
#             return None
#         item = root.find(stored)
#         if item is None:
#             # Files written before ids existed stored a path here instead.
#             try:
#                 item = self._resolve(root, stored)
#             except ValueError:
#                 return None
#         return item if isinstance(item, Source) else None

#     def _commit(self, root: Folder, selected: Source | None = None) -> None:
#         """Writes the tree to sources.json.

#         Pass `selected` to change the selection. Otherwise the current selection
#         is kept, and cleared only if the source it points at is no longer in the tree.
#         """
#         if selected is None:
#             selected = self._find_selected(root)
#         data = copy.deepcopy(self.get())
#         data["file_system"] = root.to_dict()
#         data["selected"] = selected.id if selected is not None else ""
#         self.save(data)

#     # --- class-level helpers -----------------------------------------

#     @classmethod
#     def get_selected_source_name(cls) -> str:
#         """Name of the selected source, or "" if nothing is selected."""
#         source = cls().selected
#         return source.name if source is not None else ""

#     @classmethod
#     def get_selected_source_path(cls) -> str:
#         """Path of the selected source, e.g. "maths/algebra", or "" if nothing is selected."""
#         source = cls().selected
#         return source.path if source is not None else ""

#     @classmethod
#     def get_source_file(cls) -> Path:
#         return cls.build_path(cls.filename)

#     @staticmethod
#     def _has_root(tree) -> bool:
#         return isinstance(tree, dict) and tree.get("name") == "root"

#     @staticmethod
#     def normalise_source_name(source: str) -> str:
#         """Runs some normalisation on the source name to standardise it."""
#         return re.sub(r"[.,;\s\"'=~@<>\[\]{}()-]+", "_", source).lower().strip("_")
"""Handles the sources feature, intended to help you organise anki cards created"""
from __future__ import annotations

from pathlib import Path

import click
import copy
import difflib
import re

from ..base.json_manager import JsonManager
from .source_tree import (
    Folder, Source, TreeItem, ItemTypes, create_item_factory, archive_of, is_archive_name,
    ARCHIVE_WORDS, ARCHIVE_NAMES,
)
# from ..base.firebase_sync import FirebaseStore # used for syncing
# from ..fields_input_api.input_api import ask_input


class SourceNotFoundError(ValueError):
    """No item matches the given path."""


class AmbiguousPathError(ValueError):
    """More than one item matches the given path."""


class ArchivedSourceError(ValueError):
    """The source sits inside an archive folder, so it is not selectable by default."""


class Sources(JsonManager):
    """Handles the sources feature, intended to help you organise the Anki cards you create."""

    filename = "sources"

    # Kept here so existing code using Sources.ARCHIVE_WORDS still works.
    # The lists themselves live in source_tree.py, edit them there.
    ARCHIVE_WORDS = ARCHIVE_WORDS
    ARCHIVE_NAMES = ARCHIVE_NAMES

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

    def list_sources(self, target_folder: str = "root", include_archived: bool = True) -> list[Source]:
        """Every source beneath a folder, in the order the tree is displayed.

        Set include_archived=False to leave out sources inside archive folders,
        i.e. only list the ones select() will accept by default.
        """
        root = self.load_root_folder()
        sources = self._resolve_folder(root, target_folder).sources()
        archived = {} if include_archived else self._archived_ids(root)
        return [s for s in sources if s.id not in archived]

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

    def select(self, path: str, include_archived: bool = False) -> Source:
        """Sets the active source.

        `path` is resolved like everywhere else ("algebra", "maths/algebra" or
        "root/uni/maths/algebra"), with a few extras to make picking a source easier:

        - Sources inside an archive folder (see ARCHIVE_WORDS / ARCHIVE_NAMES in source_tree.py) cannot
          be selected unless include_archived=True. When a short path matches both
          an archived and a live source, the live one is picked instead of erroring.
        - If nothing matches exactly, a case-insensitive match is tried, then the
          error suggests the closest source paths.
        - Selecting a folder selects the only source in it, if there is exactly one;
          otherwise the error lists the sources to choose from.
        """
        root = self.load_root_folder()
        # id -> name of the archive folder it sits in. Empty when archives are allowed,
        # so everything below treats every source as selectable.
        archived = {} if include_archived else self._archived_ids(root)

        try:
            item = self._resolve(root, path, prefer=lambda i: i.id not in archived)
        except SourceNotFoundError:
            item = self._resolve_loosely(root, path, archived)

        if isinstance(item, Folder):
            item = self._only_source_in(item, archived)

        if item.id in archived:
            archive = archived[item.id]
            raise ArchivedSourceError(
                f"{item.path!r} is inside the archive folder {archive!r} and can't be "
                f"selected by default. Move it out of the archive, or select it with "
                f"include_archived=True"
            )

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
    def _resolve(root: Folder, path: str, prefer=None) -> TreeItem:
        """Finds an item by path. "root" is the root folder.

        The path is tried from the root first. If nothing is there, it is treated
        as the tail end of a path and searched for through the whole tree, so
        "algebra" or "maths/algebra" finds "uni/maths/algebra". A path that
        starts with "root" is always taken literally.

        `prefer` is an optional predicate used to break ties: if a tail search
        finds several items but exactly one satisfies it, that one is returned.
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
            if matches and prefer is not None:
                preferred = [item for item in matches if prefer(item)]
                if len(preferred) == 1:
                    return preferred[0]
            if matches:
                options = ", ".join(item.path for item in matches)
                raise AmbiguousPathError(f"{path!r} matches more than one item: {options}. Use a longer path")
        raise SourceNotFoundError(f"{path!r} not found")

    def _resolve_folder(self, root: Folder, path: str) -> Folder:
        item = self._resolve(root, path)
        if not isinstance(item, Folder):
            raise ValueError(f"{path!r} is a source, not a folder")
        return item

    # --- selection helpers -------------------------------------------

    @staticmethod
    def is_archive_name(name: str) -> bool:
        """True if a folder with this name counts as an archive (see source_tree.py)."""
        return is_archive_name(name)

    @staticmethod
    def _archived_ids(root: Folder) -> dict[str, str]:
        """Maps the id of every item inside an archive folder to that folder's name."""
        found = {}
        for item in root.walk():
            archive = archive_of(item)
            if archive is not None:
                found[item.id] = archive.name
        return found

    def is_archived(self, item: TreeItem) -> bool:
        """True if the item sits inside an archive folder."""
        return item.id in self._archived_ids(self.load_root_folder())

    def _resolve_loosely(self, root: Folder, path: str, archived: dict[str, str]) -> Source:
        """Fallback for select() when the exact path matched nothing.

        Tries a case-insensitive tail match among selectable sources, and failing
        that raises SourceNotFoundError with "did you mean" suggestions.
        """
        candidates = [s for s in root.sources() if s.id not in archived]
        wanted = [p.lower() for p in path.strip().split("/") if p and p != "root"]
        if wanted:
            matches = [
                s for s in candidates
                if [p.lower() for p in s.path.split("/")[-len(wanted):]] == wanted
            ]
            if len(matches) == 1:
                return matches[0]
            if matches:
                options = ", ".join(s.path for s in matches)
                raise AmbiguousPathError(f"{path!r} matches more than one source: {options}. Use a longer path")

        by_path = {s.path.lower(): s.path for s in candidates}
        by_name = {s.name.lower(): s.path for s in candidates}
        query = path.strip().lower()
        close = difflib.get_close_matches(query, list(by_path), n=3, cutoff=0.6)
        close += [by_name[n] for n in difflib.get_close_matches(query, list(by_name), n=3, cutoff=0.6)]
        suggestions = list(dict.fromkeys(by_path.get(c, c) for c in close))[:3]

        message = f"No source found matching {path!r}"
        if suggestions:
            message += ". Did you mean: " + ", ".join(suggestions) + "?"
        elif archived:
            message += " outside the archive folders"
        raise SourceNotFoundError(message)

    def _only_source_in(self, folder: Folder, archived: dict[str, str]) -> Source:
        """The single selectable source in a folder, or an error listing the options."""
        label = folder.path or "root"
        options = [s for s in folder.sources() if s.id not in archived]
        if len(options) == 1:
            return options[0]
        if not options:
            raise ValueError(f"{label!r} is a folder with no selectable sources in it")
        shown = ", ".join(s.path for s in options[:10])
        more = f" (and {len(options) - 10} more)" if len(options) > 10 else ""
        raise ValueError(f"{label!r} is a folder, not a source. Pick one of: {shown}{more}")

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