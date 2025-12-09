from tkinter import ttk
import tkinter as tk


class Tooltip:
    def __init__(self, widget, text, *, wraplength=280, delay=400):
        self.widget = widget
        self.text = text
        self.wraplength = wraplength
        self.delay = delay
        self._after_id = None
        self._tip_window = None

        widget.bind("<Enter>", self._schedule)
        widget.bind("<Leave>", self._hide)
        widget.bind("<ButtonPress>", self._hide)

    def _schedule(self, _event=None):
        self._cancel_schedule()
        self._after_id = self.widget.after(self.delay, self._show)

    def _cancel_schedule(self):
        if self._after_id:
            self.widget.after_cancel(self._after_id)
            self._after_id = None

    def _show(self, _event=None):
        if self._tip_window:
            return

        x = self.widget.winfo_rootx() + 10
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 2
        self._tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")

        label = ttk.Label(tw, text=self.text, justify="left", wraplength=self.wraplength,
                         relief="solid", borderwidth=1, padding=(6, 4))
        label.pack(ipadx=1)

    def _hide(self, _event=None):
        self._cancel_schedule()
        if self._tip_window:
            self._tip_window.destroy()
            self._tip_window = None


def attach_tooltip(widget, text, **kwargs):
    return Tooltip(widget, text, **kwargs)