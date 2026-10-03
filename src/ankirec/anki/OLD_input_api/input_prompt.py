"""
input_prompt.py — import THIS in your code.

Usage:
    from input_prompt import ask_input, Field

    values = ask_input(
        fields=[
            Field("Username"),
            Field("Email"),
            Field("Notes", optional=True),
        ],
        title="Create Account",
        image_path="/path/to/reference.png",   # optional — adds "View Image" button
        audio_path="/path/to/sample.mp3",      # optional — adds "Play Audio" button
    )

    if values is None:
        # Window was closed — handle cancellation.
        ...
    else:
        print(values["Username"])   # always a non-empty string
        print(values["Email"])      # always a non-empty string
        print(values["Notes"])      # may be "" if left blank (optional)
"""

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Callable

_DIALOG_SCRIPT = Path(__file__).resolve().parent / "input_dialogue.py"


@dataclass
class Field:
    """Describes a single input field in the dialog."""
    label: str
    optional: bool = False

    def to_dict(self) -> dict:
        return {"label": self.label, "optional": self.optional}


def ask_input(
    fields: list[Field],
    title: str = "Input",
    image_path: Optional[str] = None,
    audio_path: Optional[str] = None,
    retake_callback: Optional[Callable] = None,
) -> Optional[dict[str, str]]:
    """
    Spawn input_dialogue.py as a subprocess with one entry per field.

    Args:
        fields:      Ordered list of Field objects defining the form.
        title:       Window title bar text.
        image_path:  Path to an image file. When provided, a "View Image"
                     button appears that opens the file in the OS default app.
        audio_path:  Path to an audio file. When provided, a "Play Audio"
                     button appears that opens the file in the OS default app.
        retake_callback: Function to call to retake the image

    Returns:
        dict mapping each Field.label to its submitted value (stripped).
        Optional fields that were left blank will have an empty string "".
        Returns None if the window was closed without submitting.

    Raises:
        ValueError:        if fields is empty.
        FileNotFoundError: if input_dialogue.py can't be found.
    """
    if not fields:
        raise ValueError("fields must contain at least one Field.")

    if not _DIALOG_SCRIPT.exists():
        raise FileNotFoundError(
            f"Dialog script not found: {_DIALOG_SCRIPT}\n"
            "Make sure input_dialogue.py is in the same directory as input_prompt.py."
        )

    fields_json = json.dumps([f.to_dict() for f in fields])

    # Popen (not run) so we can stream messages both ways while the window is open.
    # The child asks for a retake over its stdout; we run retake_callback here and
    # send the new path back over its stdin. See input_dialogue.py for the protocol.
    proc = subprocess.Popen(
        [
            sys.executable,
            str(_DIALOG_SCRIPT),
            fields_json,
            title,
            image_path or "",
            audio_path or "",
            "1" if retake_callback is not None else "0",
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )

    result: Optional[dict[str, str]] = None
    try:
        while True:
            line = proc.stdout.readline()
            if not line:
                break  # child exited without a final message

            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                # Not a protocol line — clipboard notices, PowerShell output, etc.
                continue
            if not isinstance(msg, dict) or "__dialog__" not in msg:
                continue

            kind = msg["__dialog__"]
            if kind == "retake":
                new_path = ""
                if retake_callback is not None:
                    try:
                        returned = retake_callback()
                        new_path = str(returned) if returned else ""
                    except Exception:
                        new_path = ""  # a failed retake just keeps the old image
                proc.stdin.write(
                    json.dumps({"__dialog__": "image", "path": new_path}) + "\n"
                )
                proc.stdin.flush()
            elif kind == "result":
                result = msg.get("values")
                break
            elif kind == "cancelled":
                result = None
                break
    finally:
        proc.wait()

    return result


# ── Quick demo ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    def callback():
        print("The callback was called")

    result = ask_input(
        fields=[
            Field("First Name"),
            Field("Last Name"),
            Field("Email"),
            Field("Notes", optional=True),
        ],
        title="Demo Form",
        image_path=r"C:\Users\Evan\Pictures\Screenshots\2026-05-28 18_25_41-Greenshot.png",
        audio_path=r"C:\Users\Evan\Evan\file.opus",
        retake_callback=callback
    )

    if result is None:
        print("FAIL — window was closed.")
    else:
        print("OK — received:")
        for key, value in result.items():
            print(f"  {key!r}: {value!r}")