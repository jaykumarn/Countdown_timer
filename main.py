"""
Countdown Timer – tkinter GUI
==============================
Replaces the original terminal-only script with a self-contained window that
anyone can launch without touching a command prompt.

Layout
------
  ┌──────────────────────────────────┐
  │         Countdown Timer          │  ← title label
  │                                  │
  │   HH  :  MM  :  SS               │  ← three spinboxes (hours/mins/secs)
  │                                  │
  │      ┌────────┐  ┌──────┐        │
  │      │ START  │  │ RESET│        │  ← action buttons
  │      └────────┘  └──────┘        │
  │                                  │
  │         00 : 00 : 00             │  ← big live display
  │                                  │
  │    ● ● ● ● ● ● ● ● ● ●          │  ← animated progress dots
  └──────────────────────────────────┘
"""

import time
import threading
import tkinter as tk
from tkinter import font as tkfont, messagebox


# ── colour palette ─────────────────────────────────────────────────────────────
BG = "#1e1e2e"          # window background
SURFACE = "#313244"     # card / spinbox background
ACCENT = "#cba6f7"      # purple highlight (buttons, title)
ACCENT2 = "#a6e3a1"     # green  – "running" state
ACCENT3 = "#f38ba8"     # red    – "finished / urgent" state
TEXT = "#cdd6f4"        # primary text
SUBTEXT = "#6c7086"     # muted text / inactive dots
DOT_ON = ACCENT2
DOT_OFF = SURFACE


class CountdownTimer(tk.Tk):
    """Main application window."""

    # ── init ───────────────────────────────────────────────────────────────────
    def __init__(self):
        super().__init__()

        self.title("Countdown Timer")
        self.configure(bg=BG)
        self.resizable(False, False)

        # centre on screen
        self.update_idletasks()
        w, h = 420, 480
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

        # ── state ──────────────────────────────────────────────────────────────
        self._total_seconds = 0       # original duration (for progress dots)
        self._remaining = 0           # seconds left
        self._running = False
        self._thread: threading.Thread | None = None
        self._dot_phase = 0           # cycles the dot animation

        # ── fonts ──────────────────────────────────────────────────────────────
        self._f_title = tkfont.Font(family="Segoe UI", size=18, weight="bold")
        self._f_spin_label = tkfont.Font(family="Segoe UI", size=9)
        self._f_spin = tkfont.Font(family="Segoe UI", size=22, weight="bold")
        self._f_display = tkfont.Font(family="Courier New", size=42, weight="bold")
        self._f_btn = tkfont.Font(family="Segoe UI", size=11, weight="bold")
        self._f_msg = tkfont.Font(family="Segoe UI", size=11)

        self._build_ui()
        self._reset_display()

    # ── UI construction ────────────────────────────────────────────────────────
    def _build_ui(self):
        pad = {"padx": 20, "pady": 6}

        # title
        tk.Label(
            self, text="⏱  Countdown Timer",
            font=self._f_title, bg=BG, fg=ACCENT,
        ).pack(pady=(24, 4))

        # ── spinbox row ────────────────────────────────────────────────────────
        spin_frame = tk.Frame(self, bg=BG)
        spin_frame.pack(**pad)

        self._var_h = tk.StringVar(value="00")
        self._var_m = tk.StringVar(value="00")
        self._var_s = tk.StringVar(value="00")

        for label, var, row_col in [
            ("HH", self._var_h, 0),
            ("MM", self._var_m, 2),
            ("SS", self._var_s, 4),
        ]:
            tk.Label(
                spin_frame, text=label,
                font=self._f_spin_label, bg=BG, fg=SUBTEXT,
            ).grid(row=0, column=row_col, padx=4)
            sb = tk.Spinbox(
                spin_frame,
                from_=0, to=(23 if label == "HH" else 59),
                textvariable=var, width=3,
                font=self._f_spin,
                bg=SURFACE, fg=TEXT,
                buttonbackground=SURFACE,
                relief="flat",
                highlightthickness=0,
                insertbackground=TEXT,
                format="%02.0f",
                wrap=True,
            )
            sb.grid(row=1, column=row_col, padx=4)

        # colons between spinboxes
        for col in (1, 3):
            tk.Label(
                spin_frame, text=":",
                font=self._f_spin, bg=BG, fg=TEXT,
            ).grid(row=1, column=col)

        # ── buttons ────────────────────────────────────────────────────────────
        btn_frame = tk.Frame(self, bg=BG)
        btn_frame.pack(**pad)

        self._btn_start = self._make_button(
            btn_frame, "▶  Start", ACCENT, self._on_start_pause
        )
        self._btn_start.grid(row=0, column=0, padx=10)

        self._btn_reset = self._make_button(
            btn_frame, "↺  Reset", SUBTEXT, self._on_reset
        )
        self._btn_reset.grid(row=0, column=1, padx=10)

        # ── big time display ───────────────────────────────────────────────────
        self._lbl_display = tk.Label(
            self, text="00 : 00 : 00",
            font=self._f_display, bg=BG, fg=TEXT,
        )
        self._lbl_display.pack(pady=(16, 4))

        # ── status message ─────────────────────────────────────────────────────
        self._lbl_status = tk.Label(
            self, text="Set a time and press Start",
            font=self._f_msg, bg=BG, fg=SUBTEXT,
        )
        self._lbl_status.pack()

        # ── progress dots ──────────────────────────────────────────────────────
        dot_frame = tk.Frame(self, bg=BG)
        dot_frame.pack(pady=(18, 0))
        self._dots: list[tk.Label] = []
        for _ in range(10):
            d = tk.Label(dot_frame, text="●", font=("Segoe UI", 14),
                         bg=BG, fg=DOT_OFF)
            d.pack(side="left", padx=3)
            self._dots.append(d)

    # ── helpers ────────────────────────────────────────────────────────────────
    def _make_button(self, parent, text, color, command):
        return tk.Button(
            parent, text=text, font=self._f_btn,
            bg=color, fg=BG,
            activebackground=TEXT, activeforeground=BG,
            relief="flat", padx=18, pady=8,
            cursor="hand2",
            command=command,
        )

    @staticmethod
    def _parse_time(h_str, m_str, s_str) -> int:
        """Return total seconds from three string spinbox values."""
        try:
            h = max(0, min(int(h_str or 0), 23))
            m = max(0, min(int(m_str or 0), 59))
            s = max(0, min(int(s_str or 0), 59))
        except ValueError:
            return 0
        return h * 3600 + m * 60 + s

    @staticmethod
    def _fmt(total: int) -> str:
        """Format seconds into HH : MM : SS."""
        h, rem = divmod(total, 3600)
        m, s = divmod(rem, 60)
        return f"{h:02d} : {m:02d} : {s:02d}"

    # ── display / UI update helpers (always called from main thread) ───────────
    def _reset_display(self):
        self._lbl_display.config(text="00 : 00 : 00", fg=TEXT)
        self._lbl_status.config(text="Set a time and press Start", fg=SUBTEXT)
        self._btn_start.config(text="▶  Start", bg=ACCENT)
        self._update_dots(0, 0)

    def _update_dots(self, remaining: int, total: int):
        """Light up dots proportional to remaining / total time."""
        if total == 0:
            lit = 0
        else:
            lit = round((remaining / total) * len(self._dots))
        for i, dot in enumerate(self._dots):
            dot.config(fg=DOT_ON if i < lit else DOT_OFF)

    # ── event handlers ─────────────────────────────────────────────────────────
    def _on_start_pause(self):
        if self._running:
            # pause
            self._running = False
            self._btn_start.config(text="▶  Resume", bg=ACCENT)
            self._lbl_status.config(text="Paused", fg=ACCENT)
        else:
            if self._remaining == 0:
                # fresh start – read spinboxes
                total = self._parse_time(
                    self._var_h.get(), self._var_m.get(), self._var_s.get()
                )
                if total == 0:
                    messagebox.showwarning(
                        "No time set",
                        "Please enter hours, minutes, or seconds greater than zero."
                    )
                    return
                self._total_seconds = total
                self._remaining = total

            # start / resume
            self._running = True
            self._btn_start.config(text="⏸  Pause", bg=ACCENT2)
            self._lbl_status.config(text="Running…", fg=ACCENT2)
            self._lbl_display.config(fg=TEXT)
            self._thread = threading.Thread(target=self._tick, daemon=True)
            self._thread.start()

    def _on_reset(self):
        self._running = False
        self._remaining = 0
        self._total_seconds = 0
        self._var_h.set("00")
        self._var_m.set("00")
        self._var_s.set("00")
        self._reset_display()

    # ── countdown logic (runs in background thread) ────────────────────────────
    def _tick(self):
        while self._running and self._remaining > 0:
            # schedule a UI refresh on the main thread
            self.after(0, self._refresh_ui, self._remaining)
            time.sleep(1)
            if self._running:          # might have been paused mid-sleep
                self._remaining -= 1

        if self._running:              # finished naturally (not paused/reset)
            self._running = False
            self.after(0, self._on_finished)

    def _refresh_ui(self, remaining: int):
        """Called on the main thread to update display labels and dots."""
        self._lbl_display.config(text=self._fmt(remaining))
        self._update_dots(remaining, self._total_seconds)

        # turn display red in the last 10 seconds
        if remaining <= 10:
            self._lbl_display.config(fg=ACCENT3)
            self._lbl_status.config(text=f"Hurry! {remaining}s left", fg=ACCENT3)

    def _on_finished(self):
        self._lbl_display.config(text="00 : 00 : 00", fg=ACCENT2)
        self._lbl_status.config(text="✓  Timer completed!", fg=ACCENT2)
        self._btn_start.config(text="▶  Start", bg=ACCENT)
        self._update_dots(0, 0)
        messagebox.showinfo("Done", "⏱ Your countdown has finished!")


# ── entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = CountdownTimer()
    app.mainloop()
