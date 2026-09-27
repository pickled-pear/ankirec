from rich import print
class VerboseMixin:
    verbose: bool

    def __init__(self, verbose):
        self.verbose = verbose

    def echo(self, *args):
        if self.verbose:
            print(*args)