"""
input_dialogue.py — runs as a subprocess.

CRITICAL RESOURCE CLEANUP:
- Unbind all event handlers before destroying widgets
- Explicitly destroy all widgets in reverse order
- Call update_idletasks() to flush pending events
- Exit cleanly with sys.exit() to flush all buffers

CROSS-PLATFORM SUPPORT: Windows, macOS, Linux (X11 & Wayland)

On submit  : emits JSON {"__dialog__": "result", "values": {...}} to stdout, exits 0.
On close   : emits JSON {"__dialog__": "cancelled"} to stdout, exits 1.
DO NOT import this file directly. Use input_api.py instead.
"""
import json
import os
import platform
import subprocess
import sys
import tkinter as tk
from tkinter import messagebox
import gc
import atexit

IS_LINUX   = platform.system() == "Linux"
IS_MAC     = platform.system() == "Darwin"
IS_WINDOWS = platform.system() == "Windows"

# ── Parent/child protocol ─────────────────────────────────────────────────────
def _emit(msg: dict) -> None:
    """Send one control/result message to the parent process."""
    try:
        sys.stdout.write(json.dumps(msg) + "\n")
        sys.stdout.flush()
    except (BrokenPipeError, OSError):
        pass

def _read_reply() -> dict | None:
    """Block until the parent sends one reply line; returns the parsed dict or None."""
    try:
        line = sys.stdin.readline()
        if not line:
            return None
        return json.loads(line)
    except (json.JSONDecodeError, EOFError, OSError):
        return None

# ── Palette ───────────────────────────────────────────────────────────────────
BG           = "#141414"
BG2          = "#1c1c1c"
BG_FOCUS     = "#2a2a2a"
TITLEBAR     = "#0d0d0d"
FG           = "#e8e8e8"
FG_DIM       = "#666666"
FG_LABEL     = "#3a7a7a"
FG_OPTIONAL  = "#555555"
ACCENT       = "#00c8c8"
ACCENT_DIM   = "#007777"
BORDER       = "#2e2e2e"
BORDER_FOCUS = "#00c8c8"
BORDER_ERR   = "#c0392b"
SEL_BG       = "#1a5050"
CLOSE_HOV    = "#e74c3c"
MEDIA_BG      = "#1e2e2e"
MEDIA_BG_HOV  = "#2a4040"
MEDIA_FG      = "#00c8c8"
MEDIA_BORDER  = "#2e4444"

# ── Layout constants ──────────────────────────────────────────────────────────
WIN_W           = 420
TITLEBAR_H      = 28
BODY_PAD_Y      = 16
FIELD_LABEL_H   = 18
FIELD_ENTRY_H   = 54
FIELD_ERROR_H   = 16
FIELD_GAP       = 5
MEDIA_ROW_H     = 40
SUBMIT_H        = 36
BOTTOM_PAD      = 8
TEXT_LINE_H     = 18
TEXT_MIN_LINES  = 1


def _cleanup():
    """Cleanup handler to ensure proper exit."""
    try:
        gc.collect()
        sys.stdout.flush()
        sys.stderr.flush()
    except Exception:
        pass


def _safe_unbind(widget, sequence):
    """Safely unbind an event, ignoring if it doesn't exist."""
    try:
        widget.unbind(sequence)
    except Exception:
        pass


def _safe_destroy(widget):
    """Safely destroy a widget, ignoring errors."""
    try:
        if widget and widget.winfo_exists():
            widget.destroy()
    except Exception:
        pass


def copy_image_to_clipboard(path: str) -> None:
    """Copy an image file to the clipboard (Windows/Linux)."""
    abs_path = os.path.abspath(path)

    if not os.path.isfile(abs_path):
        raise FileNotFoundError(f"File not found: {abs_path}")

    ext = os.path.splitext(abs_path)[1].lower()
    mime_types = {
        ".png":  "image/png",
        ".jpg":  "image/jpeg",
        ".jpeg": "image/jpeg",
        ".bmp":  "image/bmp",
        ".gif":  "image/gif",
        ".tiff": "image/tiff",
        ".webp": "image/webp",
    }
    mime = mime_types.get(ext, "image/png")

    if IS_WINDOWS:
        import base64
        try:
            script = (
                "Add-Type -AssemblyName System.Windows.Forms; "
                "Add-Type -AssemblyName System.Drawing; "
                "$path = $env:CLIP_IMAGE_PATH; "
                "[System.Windows.Forms.Clipboard]::SetImage("
                "[System.Drawing.Image]::FromFile($path))"
            )
            encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
            env = {**os.environ, "CLIP_IMAGE_PATH": abs_path}
            subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
                check=True,
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
            )
        except Exception:
            # Silently fail on Windows clipboard — non-critical
            pass
    elif IS_LINUX:
        try:
            if os.environ.get("WAYLAND_DISPLAY"):
                # Wayland clipboard
                if subprocess.run(["which", "wl-copy"], capture_output=True, timeout=2).returncode == 0:
                    with open(abs_path, "rb") as f:
                        subprocess.run(["wl-copy", "--type", mime], stdin=f, check=True,
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
            else:
                # X11 clipboard
                if subprocess.run(["which", "xclip"], capture_output=True, timeout=2).returncode == 0:
                    with open(abs_path, "rb") as f:
                        subprocess.run(
                            ["xclip", "-selection", "clipboard", "-t", mime, "-i"],
                            stdin=f, check=True,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5
                        )
        except Exception:
            # Silently fail on Linux clipboard — non-critical
            pass


def copy_text_to_clipboard(text: str) -> None:
    """Copy a string to the clipboard (Windows/Linux)."""
    try:
        if IS_WINDOWS:
            subprocess.run(["clip"], input=text.encode("utf-16-le"), check=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
        elif IS_LINUX:
            if os.environ.get("WAYLAND_DISPLAY"):
                if subprocess.run(["which", "wl-copy"], capture_output=True, timeout=2).returncode == 0:
                    subprocess.run(["wl-copy"], input=text.encode("utf-8"), check=True,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
            else:
                if subprocess.run(["which", "xclip"], capture_output=True, timeout=2).returncode == 0:
                    subprocess.run(
                        ["xclip", "-selection", "clipboard"],
                        input=text.encode("utf-8"),
                        check=True,
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5,
                    )
    except Exception:
        # Silently fail — non-critical
        pass


def _calc_height(n_fields: int, has_media: bool) -> int:
    per_field = FIELD_LABEL_H + FIELD_ENTRY_H + FIELD_ERROR_H + FIELD_GAP
    media_h   = (MEDIA_ROW_H + 8) if has_media else 0
    body_h    = (BODY_PAD_Y + n_fields * per_field + BOTTOM_PAD + media_h + SUBMIT_H + BODY_PAD_Y)
    return TITLEBAR_H + body_h


def _open_file(path: str) -> None:
    """Open a file using the OS default application, non-blocking."""
    try:
        if IS_WINDOWS:
            os.startfile(path)
        elif IS_MAC:
            subprocess.Popen(["open", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            # Linux: xdg-open works on both X11 and Wayland
            subprocess.Popen(["xdg-open", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


def _make_media_btn(parent, text: str) -> tk.Label:
    """Create a styled media-open button."""
    btn = tk.Label(
        parent,
        text=text,
        bg=MEDIA_BG,
        fg=MEDIA_FG,
        font=("Consolas", 9, "bold"),
        padx=12,
        pady=6,
        cursor="hand2",
        relief="flat",
    )
    return btn


def _run(fields: list[dict], title: str,
         image_path: str | None, audio_path: str | None,
         has_retake: bool = False) -> None:
    """
    fields:     list of {"label": str, "optional": bool}
    image_path: path to open when "View Image" is clicked, or None
    audio_path: path to open when "Play Audio" is clicked, or None
    has_retake: whether retake is enabled
    """
    atexit.register(_cleanup)
    
    result: list[dict | None] = [None]
    closed_by_user = [False]  # Track if user closed window
    
    root = tk.Tk()
    root.withdraw()
    
    top = tk.Toplevel(root)
    top.title(title)
    top.configure(bg=BG)
    top.resizable(False, True)

    has_media = bool(image_path or audio_path)
    w = WIN_W
    h = _calc_height(len(fields), has_media)
    sw, sh = top.winfo_screenwidth(), top.winfo_screenheight()
    top.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")

    # ── Titlebar ──────────────────────────────────────────────────────────────
    titlebar = tk.Frame(top, bg=TITLEBAR, height=TITLEBAR_H)
    titlebar.pack(fill="x", side="top")
    titlebar.pack_propagate(False)
    
    title_lbl = tk.Label(titlebar, text=title, bg=TITLEBAR, fg=FG_DIM,
                         font=("Consolas", 9), anchor="w", padx=8)
    title_lbl.pack(side="left", fill="y")
    
    close_btn = tk.Label(titlebar, text="✕", bg=TITLEBAR, fg=FG_DIM,
                         font=("Consolas", 10), padx=10, cursor="hand2")
    close_btn.pack(side="right", fill="y")

    def _close(e=None):
        """User closed the window."""
        result[0] = None
        closed_by_user[0] = True
        top.quit()

    close_btn.bind("<Enter>",    lambda e, b=close_btn: b.config(bg=CLOSE_HOV, fg=FG))
    close_btn.bind("<Leave>",    lambda e, b=close_btn: b.config(bg=TITLEBAR,  fg=FG_DIM))
    close_btn.bind("<Button-1>", _close)
    top.protocol("WM_DELETE_WINDOW", _close)

    # ── Drag ──────────────────────────────────────────────────────────────────
    _drag: dict = {}

    def _drag_start(e):
        _drag["x"], _drag["y"] = e.x_root, e.y_root

    def _drag_move(e):
        dx = e.x_root - _drag["x"]
        dy = e.y_root - _drag["y"]
        top.geometry(f"+{top.winfo_x() + dx}+{top.winfo_y() + dy}")
        _drag["x"], _drag["y"] = e.x_root, e.y_root

    for widget in (titlebar, title_lbl):
        widget.bind("<ButtonPress-1>", _drag_start)
        widget.bind("<B1-Motion>",     _drag_move)

    # ── Body ──────────────────────────────────────────────────────────────────
    body = tk.Frame(top, bg=BG, padx=20, pady=BODY_PAD_Y)
    body.pack(fill="both", expand=True)

    text_widgets: list[tk.Text]   = []
    error_lbls: list[tk.Label]    = []
    entry_wraps: list[tk.Frame]   = []

    def _select_all(text_widget):
        def _handler(e=None):
            text_widget.tag_add("sel", "1.0", "end")
            text_widget.mark_set("insert", "end")
            return "break"
        return _handler

    def _make_auto_resize(text_widget, wrap_frame, win):
        """Return a callback that grows the Text widget and window when lines wrap."""
        _resize_pending = [False]  # Use list to allow modification in nested function

        def _do_resize():
            """Perform the actual resize operation."""
            _resize_pending[0] = False
            try:
                display_lines = int(text_widget.count("1.0", "end", "displaylines")[0])
                new_lines = max(TEXT_MIN_LINES, display_lines)
                if text_widget.cget("height") != new_lines:
                    text_widget.config(height=new_lines)
                    win.after(1, lambda: win.geometry(
                        f"{WIN_W}x{win.winfo_reqheight()}+"
                        f"{win.winfo_x()}+{win.winfo_y()}"
                    ))
            except Exception:
                pass

        def _resize(e=None):
            """Debounced resize callback — only schedules one resize per 100 ms."""
            if not _resize_pending[0]:
                _resize_pending[0] = True
                win.after(100, _do_resize)  # Debounce: wait 100 ms before resizing

        return _resize

    def _focus_text(text_widget):
        """Focus the given Text widget and move the insert cursor to the end."""
        def _handler(e=None):
            try:
                (text_widget.focus_force if IS_LINUX else text_widget.focus_set)()
                text_widget.mark_set("insert", "end")
            except Exception:
                pass
        return _handler

    for i, field in enumerate(fields):
        label_text = field["label"]
        optional   = field.get("optional", False)

        lbl_frame = tk.Frame(body, bg=BG)
        lbl_frame.pack(fill="x", pady=(0 if i == 0 else FIELD_GAP, 2))
        
        main_lbl = tk.Label(lbl_frame, text=label_text, bg=BG, fg=FG_LABEL,
                            font=("Consolas", 9, "bold"), anchor="w", cursor="hand2")
        main_lbl.pack(side="left")
        
        if optional:
            opt_lbl = tk.Label(lbl_frame, text=" (optional)", bg=BG, fg=FG_OPTIONAL,
                               font=("Consolas", 8), anchor="w", cursor="hand2")
            opt_lbl.pack(side="left")

        wrap = tk.Frame(body, bg=BORDER, padx=1, pady=1)
        wrap.pack(fill="x", pady=(0, 2))
        entry_wraps.append(wrap)

        text = tk.Text(
            wrap,
            bg=BG2,
            fg=FG,
            insertbackground=ACCENT,
            relief="flat",
            font=("Consolas", 11),
            selectbackground=SEL_BG,
            selectforeground=FG,
            bd=6,
            height=TEXT_MIN_LINES,
            wrap="char",
            undo=True,
        )
        text.pack(fill="x")
        text_widgets.append(text)

        main_lbl.bind("<Button-1>", _focus_text(text))
        if optional:
            opt_lbl.bind("<Button-1>", _focus_text(text))

        def _tab_next(e, idx=i):
            _focus_text(text_widgets[(idx + 1) % len(fields)])()
            return "break"
        
        def _tab_prev(e, idx=i):
            _focus_text(text_widgets[(idx - 1) % len(fields)])()
            return "break"
        
        text.bind("<Tab>",       _tab_next)
        text.bind("<Shift-Tab>", _tab_prev)

        text.bind("<FocusIn>",
                  lambda e, w=wrap, t=text: (w.config(bg=BORDER_FOCUS), t.config(bg=BG_FOCUS)))
        text.bind("<FocusOut>",
                  lambda e, w=wrap, t=text: (w.config(bg=BORDER), t.config(bg=BG2)))

        text.bind("<Control-a>", _select_all(text))
        text.bind("<Return>",         lambda e: None)
        text.bind("<Control-Return>", lambda e: (_submit(), "break")[1])

        _resizer = _make_auto_resize(text, wrap, top)
        text.bind("<KeyRelease>", _resizer)
        text.bind("<<Paste>>",    lambda e, r=_resizer: top.after(10, r))

        err = tk.Label(body, text="", bg=BG, fg=BORDER_ERR,
                       font=("Consolas", 8), anchor="w")
        err.pack(fill="x")
        error_lbls.append(err)

    current_image = {"path": image_path}

    def _open_image(_event=None):
        path = current_image["path"]
        if path:
            _open_file(path)
            # copy_image_to_clipboard(path)

            if not has_retake:
                return

            if messagebox.askokcancel("Retake", "Retake the image?"):
                _emit({"__dialog__": "retake"})
                reply = _read_reply()
                if reply and reply.get("path"):
                    current_image["path"] = reply["path"]
                    if current_image["path"]:
                        _open_file(current_image["path"])
                        # copy_image_to_clipboard(current_image["path"])

    # ── Media buttons (image / audio) ─────────────────────────────────────────
    if has_media:
        media_row = tk.Frame(body, bg=BG)
        media_row.pack(fill="x", pady=(BOTTOM_PAD, 0))
        if image_path:
            img_btn = _make_media_btn(media_row, "⬡  View Image")
            img_btn.pack(side="left", padx=(0, 6))
            img_btn.bind("<Button-1>", _open_image)
        if audio_path:
            aud_btn = _make_media_btn(media_row, "▶  Play Audio")
            aud_btn.pack(side="left")
            aud_str = f"[sound:{os.path.basename(audio_path)}]"
            aud_btn.bind("<Button-1>", lambda e, p=audio_path, s=aud_str: (_open_file(p), copy_text_to_clipboard(s)))

    # ── Submit ────────────────────────────────────────────────────────────────
    def _submit(e=None):
        for wrap, err in zip(entry_wraps, error_lbls):
            wrap.config(bg=BORDER)
            err.config(text="")
        values: dict[str, str] = {}
        first_bad: tk.Text | None = None
        valid = True
        for field, text, wrap, err in zip(fields, text_widgets, entry_wraps, error_lbls):
            value    = text.get("1.0", "end").strip()
            optional = field.get("optional", False)
            if not value and not optional:
                wrap.config(bg=BORDER_ERR)
                err.config(text=f"⚠  '{field['label']}' cannot be empty.")
                if first_bad is None:
                    first_bad = text
                valid = False
            else:
                values[field["label"]] = value
        if not valid:
            try:
                (first_bad.focus_force if IS_LINUX else first_bad.focus_set)()
            except Exception:
                pass
            return
        result[0] = values
        closed_by_user[0] = False  # User submitted, not closing
        top.quit()

    submit_row = tk.Frame(body, bg=BG)
    submit_row.pack(fill="x", pady=(8 if has_media else BOTTOM_PAD, 0))
    btn = tk.Label(submit_row, text="SUBMIT", bg=ACCENT_DIM, fg=ACCENT,
                   font=("Consolas", 9, "bold"), padx=14, pady=5,
                   cursor="hand2", relief="flat")
    btn.pack(side="right")
    btn.bind("<Enter>",    lambda e, b=btn: b.config(bg=ACCENT,     fg=BG))
    btn.bind("<Leave>",    lambda e, b=btn: b.config(bg=ACCENT_DIM, fg=ACCENT))
    btn.bind("<Button-1>", _submit)

    if IS_LINUX:
        def _force_focus():
            try:
                top.focus_force()
                if text_widgets:
                    text_widgets[0].focus_force()
            except Exception:
                pass
        top.after(100, _force_focus)
    else:
        def _force_focus():
            try:
                top.lift()
                top.focus_force()
                if text_widgets:
                    text_widgets[0].focus_force()
            except Exception:
                pass
        top.after(100, _force_focus)

    try:
        root.mainloop()
    except Exception:
        pass

    # ── CRITICAL CLEANUP ──────────────────────────────────────────────────────
    # Unbind all events to break circular references
    for text in text_widgets:
        for seq in ("<Tab>", "<Shift-Tab>", "<FocusIn>", "<FocusOut>", "<Control-a>",
                    "<Return>", "<Control-Return>", "<KeyRelease>", "<<Paste>>"):
            _safe_unbind(text, seq)

    for widget in (close_btn, title_lbl, titlebar):
        for seq in ("<Enter>", "<Leave>", "<Button-1>", "<ButtonPress-1>", "<B1-Motion>"):
            _safe_unbind(widget, seq)

    # Destroy widgets explicitly
    _safe_destroy(body)
    _safe_destroy(titlebar)
    _safe_destroy(top)
    _safe_destroy(root)

    # Clear lists
    text_widgets.clear()
    error_lbls.clear()
    entry_wraps.clear()

    # Update to process destroy events
    try:
        root.update_idletasks()
    except Exception:
        pass

    # Emit result
    if result[0] is not None:
        _emit({"__dialog__": "result", "values": result[0]})
        sys.exit(0)
    elif closed_by_user[0]:
        _emit({"__dialog__": "cancelled_by_user"})
        sys.exit(1)
    else:
        _emit({"__dialog__": "cancelled"})
        sys.exit(0)

    # Clean up
    gc.collect()
    sys.stdout.flush()
    sys.stderr.flush()


if __name__ == "__main__":
    import json as _json
    _fields     = _json.loads(sys.argv[1])
    _title      = sys.argv[2]
    _image_path = sys.argv[3] if len(sys.argv) > 3 and sys.argv[3] else None
    _audio_path = sys.argv[4] if len(sys.argv) > 4 and sys.argv[4] else None
    _has_retake = len(sys.argv) > 5 and sys.argv[5] == "1"
    _run(_fields, _title, _image_path, _audio_path, _has_retake)