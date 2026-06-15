"""Mini GUI dialogs for screen-sharing pairing — tkinter-based."""

import threading
import tkinter as tk

BG = "#1e1e2e"
FG = "#cdd6f4"
DIM = "#6c7086"
ACCENT = "#89b4fa"
SURFACE = "#313244"
BORDER = "#45475a"
GREEN = "#a6e3a1"
RED = "#f38ba8"


def _center(win, w, h):
    win.update_idletasks()
    x = (win.winfo_screenwidth() - w) // 2
    y = (win.winfo_screenheight() - h) // 2
    win.geometry(f"{w}x{h}+{x}+{y}")


class HostCodeWindow:
    """Displays the pairing code while waiting for a viewer to connect."""

    def __init__(self, code: str):
        self._code = code
        self._cancelled = False
        self._root: tk.Tk | None = None
        self._ready = threading.Event()

    def run(self):
        root = tk.Tk()
        self._root = root
        root.title("RemoteDesktop — Screen Share")
        root.configure(bg=BG)
        root.resizable(False, False)
        _center(root, 380, 270)
        root.attributes("-topmost", True)
        root.protocol("WM_DELETE_WINDOW", self._cancel)

        tk.Label(root, text="Screen Sharing", font=("Segoe UI", 16, "bold"),
                 fg=FG, bg=BG).pack(pady=(24, 2))

        tk.Label(root, text="Share this code with the viewer:",
                 font=("Segoe UI", 10), fg=DIM, bg=BG).pack(pady=(0, 14))

        code_frame = tk.Frame(root, bg=SURFACE, highlightbackground=BORDER,
                              highlightthickness=1)
        code_frame.pack(ipadx=28, ipady=10)
        spaced = "   ".join(self._code)
        tk.Label(code_frame, text=spaced, font=("Consolas", 30, "bold"),
                 fg=ACCENT, bg=SURFACE).pack()

        self._status_label = tk.Label(root, text="⏳  Waiting for viewer…",
                                      font=("Segoe UI", 10), fg=DIM, bg=BG)
        self._status_label.pack(pady=(16, 0))

        tk.Button(root, text="Cancel", command=self._cancel,
                  font=("Segoe UI", 9), width=12, bg=SURFACE, fg=FG,
                  activebackground=BORDER, relief="flat",
                  cursor="hand2").pack(pady=(14, 0))

        self._ready.set()
        root.mainloop()

    def _cancel(self):
        self._cancelled = True
        if self._root:
            self._root.destroy()

    def close(self):
        if self._root:
            try:
                self._root.after(0, self._root.destroy)
            except Exception:
                pass

    def set_connected(self):
        if self._root and self._status_label:
            try:
                self._root.after(0, lambda: self._status_label.config(
                    text="✅  Viewer connected!", fg=GREEN))
            except Exception:
                pass

    def wait_ready(self):
        self._ready.wait()

    @property
    def cancelled(self) -> bool:
        return self._cancelled


class ViewerCodeWindow:
    """Prompts the user to enter a pairing code."""

    def __init__(self):
        self._code: str | None = None

    def run(self) -> str | None:
        root = tk.Tk()
        root.title("RemoteDesktop — Connect")
        root.configure(bg=BG)
        root.resizable(False, False)
        _center(root, 380, 240)
        root.attributes("-topmost", True)
        root.protocol("WM_DELETE_WINDOW", root.destroy)

        tk.Label(root, text="Connect to Host", font=("Segoe UI", 16, "bold"),
                 fg=FG, bg=BG).pack(pady=(24, 2))

        tk.Label(root, text="Enter the 6-digit pairing code:",
                 font=("Segoe UI", 10), fg=DIM, bg=BG).pack(pady=(0, 12))

        entry = tk.Entry(root, font=("Consolas", 24, "bold"), width=8,
                         justify="center", bg=SURFACE, fg=ACCENT,
                         insertbackground=ACCENT, relief="flat",
                         highlightbackground=BORDER, highlightthickness=1)
        entry.pack(ipady=4)
        entry.focus_set()

        error_label = tk.Label(root, text="", font=("Segoe UI", 9),
                               fg=RED, bg=BG)
        error_label.pack(pady=(2, 0))

        def on_connect():
            code = entry.get().strip()
            if len(code) >= 4 and code.isdigit():
                self._code = code
                root.destroy()
            else:
                error_label.config(text="Enter a valid numeric code")
                entry.focus_set()

        btn_frame = tk.Frame(root, bg=BG)
        btn_frame.pack(pady=(8, 0))

        tk.Button(btn_frame, text="Connect", command=on_connect,
                  font=("Segoe UI", 10, "bold"), width=12,
                  bg=ACCENT, fg=BG, activebackground="#b4d0fb",
                  relief="flat", cursor="hand2").pack(side="left", padx=4)

        tk.Button(btn_frame, text="Cancel", command=root.destroy,
                  font=("Segoe UI", 10), width=12, bg=SURFACE, fg=FG,
                  activebackground=BORDER, relief="flat",
                  cursor="hand2").pack(side="left", padx=4)

        entry.bind("<Return>", lambda _: on_connect())

        root.mainloop()
        return self._code


def show_host_code(code: str) -> HostCodeWindow:
    """Launch the host code window in a daemon thread. Returns the window handle."""
    win = HostCodeWindow(code)
    t = threading.Thread(target=win.run, daemon=True)
    t.start()
    win.wait_ready()
    return win


def ask_pairing_code() -> str | None:
    """Show the viewer code dialog (blocking). Returns code or None if cancelled."""
    win = ViewerCodeWindow()
    return win.run()
