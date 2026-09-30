# import json
# import urllib
# import socket
# from pathlib import Path
# from dataclasses import dataclass

# from ..base.exceptions import AnkiConnectError
# from ..base.universal import warn
# from ..base.config import Config

# @dataclass
# class AnkiConfig:
#     instant_send: bool
#     auto_clear_folder: bool
#     deckname: str
#     cardmodel: str
#     anki_profile: str
#     ankiconnect_port: int
#     ankiconnect_api_ver: int


# class AnkiActions:
#     API_VERSION = 6
#     port: int

#     def __init__(self):
#         self.ANKI_CONNECT_URL = f"http://localhost:{self.port}"
#         self.cards_json_file = Path("cards.json")

#     def _invoke(self, action, **params):
#         """Sends a """
#         payload = json.dumps({
#             "action": action,
#             "version": self.API_VERSION,
#             "params": params
#         }).encode("utf-8")

            
#         request = urllib.request.Request(self.ANKI_CONNECT_URL, payload)
#         with urllib.request.urlopen(request) as response:
#             result = json.loads(response.read())
    
#         if result.get("error"):
#             raise Exception(f"[red]{result['error']}")
        
#         return result["result"]

#     def send_to_anki(self):
#         """Adds the contents of cards.json to anki itself"""
#         if is_port_open(self.port):
#             cards_json = {}
#             self._invoke("addNotes", notes=cards_json)

#         else:
#             warn("Anki is not running!")

#     def set_port(self, port: int):
#         self.port = port
            

# def is_port_open(port: int, host: str = 'localhost', timeout: float = 1.0) -> bool:
#     """
#     Check if a port is open and listening on the local machine.
    
#     Args:
#         port: The port number to check (0-65535)
#         host: The host to check (default: 'localhost')
#         timeout: Socket timeout in seconds (default: 1.0)
    
#     Returns:
#         True if the port is open, False otherwise
    
#     Example:
#         >>> is_port_open(8080)
#         True
#         >>> is_port_open(9999)
#         False
#     """
#     sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
#     sock.settimeout(timeout)
    
#     try:
#         result = sock.connect_ex((host, port))
#         return result == 0
#     finally:
#         sock.close()


# if __name__ == "__main__":
#     print(is_port_open(8765))