import json
from abc import ABC
from .mixin import VerboseMixin

class JsonManager(VerboseMixin):
    def __init__(self, verbose):
        super().__init__(verbose)
