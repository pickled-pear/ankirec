from rich import print

class AnkiConnectError(Exception):
    """Raised for issues with ankiconnect"""
    def __init__(self, message):
        self.message = message
        super().__init__(message)