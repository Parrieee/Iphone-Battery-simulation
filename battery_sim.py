"""Battery Sim: the tkinter GUI for the iPhone battery simulator.

The calculations live in battery_model.py; this file only draws and handles input.

Run it with:  python3 battery_sim.py

The left side draws the phone; the right side holds the live readout, the
loads that drain the battery, and a chart of charge over simulated time.
Colours, type and spacing follow the Battery Sim design system.
"""

import tkinter as tk
import tkinter.font as tkfont

from battery_model import Battery, LOW_POWER_LEVEL, format_duration, state_for

# ---------------------------------------------------------------------------
# Design tokens (from the Battery Sim design system's tokens.json)
# ---------------------------------------------------------------------------
SURFACE = "#f6f7f5"          # page background
SURFACE_RAISED = "#ffffff"   # cards and panels
LINE = "#d9dde1"             # hairline borders
INK = "#16191d"              # primary text
INK_MUTED = "#5b636d"        # secondary text
DEVICE = "#22262b"           # the phone body
DEVICE_EDGE = "#3a4047"      # side buttons and the frame's rim (a lighter device shade)
CHARGE = "#1a7a43"           # healthy charge, primary actions
CHARGE_TINT = "#dcefe3"      # empty segments, area under the curve
CHARGE_LOW = "#f2b705"       # Low Power (20% and below); ink text on it
CHARGE_CRITICAL = "#c4321f"  # critical (10% and below); white text on it
WHITE = "#ffffff"

SPACE_1, SPACE_2, SPACE_4, SPACE_6 = 4, 8, 16, 24
RADIUS_SM, RADIUS_MD = 6, 12

TICK_MS = 100  # the simulation advances ten times a second


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def rgb_to_hex(rgb):
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(round(c)))) for c in rgb)


def blend(a, b, t):
    """Mix colour a towards colour b by t (0..1)."""
    ra, rb = hex_to_rgb(a), hex_to_rgb(b)
    return rgb_to_hex([ra[i] + (rb[i] - ra[i]) * t for i in range(3)])


def luminance(h):
    def channel(c):
        c = c / 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (channel(c) for c in hex_to_rgb(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def rounded_rect(canvas, x1, y1, x2, y2, r, **kw):
    """Draw a rounded rectangle as a smoothed polygon."""
    r = min(r, (x2 - x1) / 2, (y2 - y1) / 2)
    pts = [x1 + r, y1, x1 + r, y1, x2 - r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
           x2, y1 + r, x2, y2 - r, x2, y2 - r, x2, y2, x2 - r, y2, x2 - r, y2,
           x1 + r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y2 - r, x1, y1 + r,
           x1, y1 + r, x1, y1]
    return canvas.create_polygon(pts, smooth=True, splinesteps=16, **kw)


def pick_font(root, candidates, fallback):
    available = set(tkfont.families(root))
    for name in candidates:
        if name in available:
            return name
    return fallback


# ---------------------------------------------------------------------------
# Widgets styled from the design system
# ---------------------------------------------------------------------------
class FlatButton(tk.Label):
    """A button that looks the same on every platform (tk.Button ignores colours on macOS)."""

    VARIANTS = {
        "primary": (CHARGE, WHITE),
        "secondary": (SURFACE_RAISED, INK),
        "danger": (CHARGE_CRITICAL, WHITE),
    }

    def __init__(self, master, text, command, variant="primary", font=None):
        bg, fg = self.VARIANTS[variant]
        super().__init__(master, text=text, bg=bg, fg=fg, font=font, padx=SPACE_4, pady=SPACE_2,
                         cursor="hand2", takefocus=1, highlightthickness=2,
                         highlightbackground=master["bg"], highlightcolor=INK,
                         bd=1 if variant == "secondary" else 0, relief="solid")
        if variant == "secondary":
            self.configure(bd=0, highlightbackground=LINE, highlightthickness=1)
        self._bg = bg
        self.command = command
        self.bind("<Button-1>", lambda e: self.command())
        self.bind("<Return>", lambda e: self.command())
        self.bind("<space>", lambda e: (self.command(), "break")[1])
        self.bind("<Enter>", lambda e: self.configure(bg=blend(self._bg, INK, 0.12)))
        self.bind("<Leave>", lambda e: self.configure(bg=self._bg))

    def set_variant(self, variant):
        bg, fg = self.VARIANTS[variant]
        self._bg = bg
        self.configure(bg=bg, fg=fg)


class Card(tk.Frame):
    def __init__(self, master, title=None, meta=None, fonts=None):
        super().__init__(master, bg=SURFACE_RAISED, highlightthickness=1,
                         highlightbackground=LINE, padx=SPACE_4, pady=SPACE_4)
        if title:
            tk.Label(self, text=title, bg=SURFACE_RAISED, fg=INK, font=fonts["headline"],
                     anchor="w").pack(fill="x")
        if meta:
            tk.Label(self, text=meta, bg=SURFACE_RAISED, fg=INK_MUTED, font=fonts["caption"],
                     anchor="w", justify="left").pack(fill="x", pady=(0, SPACE_2))


class LoadSlider(tk.Frame):
    def __init__(self, master, label, var, frm, to, unit, fonts, hint=None):
        super().__init__(master, bg=SURFACE_RAISED)
        self.var, self.unit = var, unit
        top = tk.Frame(self, bg=SURFACE_RAISED)
        top.pack(fill="x")
        tk.Label(top, text=label, bg=SURFACE_RAISED, fg=INK, font=fonts["control"]).pack(side="left")
        self.value = tk.Label(top, bg=SURFACE_RAISED, fg=INK, font=fonts["mono_small"])
        self.value.pack(side="right")
        tk.Scale(self, variable=var, from_=frm, to=to, orient="horizontal", showvalue=False,
                 bg=CHARGE, troughcolor=CHARGE_TINT, activebackground=blend(CHARGE, INK, 0.2),
                 highlightthickness=0, bd=0, sliderrelief="flat", width=10, sliderlength=20,
                 ).pack(fill="x", pady=(SPACE_1, 0))
        var.trace_add("write", lambda *_: self.refresh())
        if hint:
            tk.Label(self, text=hint, bg=SURFACE_RAISED, fg=INK_MUTED, font=fonts["caption"],
                     anchor="w").pack(fill="x")
        self.refresh()

    def refresh(self):
        v = int(self.var.get())
        thin = "" if self.unit == "%" else " "
        self.value.configure(text="%d%s%s" % (v, thin, self.unit))


# ---------------------------------------------------------------------------
# The app
# ---------------------------------------------------------------------------
class BatterySimApp:
    PHONE_W, PHONE_H = 400, 760

    def __init__(self, root):
        self.root = root
        root.title("Battery Sim")
        root.configure(bg=SURFACE)
        root.minsize(1160, 800)

        sans = pick_font(root, ["SF Pro Text", "Segoe UI", "Helvetica Neue", "Inter",
                                "Roboto", "DejaVu Sans", "Helvetica"], "TkDefaultFont")
        mono = pick_font(root, ["SF Mono", "Menlo", "Consolas", "JetBrains Mono",
                                "DejaVu Sans Mono", "Courier New", "Courier"], "TkFixedFont")
        self.sans, self.mono = sans, mono
        self.fonts = {
            "display": (sans, 26, "bold"),
            "headline": (sans, 15, "bold"),
            "control": (sans, 12, "bold"),
            "body": (sans, 12),
            "caption": (sans, 10),
            "label": (sans, 9, "bold"),
            "readout": (mono, 40, "bold"),
            "mono_small": (mono, 12, "bold"),
            "button": (sans, 12, "bold"),
        }

        self.battery = Battery()
        self.running = False

        self.brightness = tk.IntVar(value=70)
        self.apps = tk.IntVar(value=5)
        self.temperature = tk.IntVar(value=25)
        self.health = tk.IntVar(value=100)
        self.speed = tk.IntVar(value=30)  # simulated minutes per real second
        self.low_power = tk.BooleanVar(value=False)
        self.charging = tk.BooleanVar(value=False)
        
        self._build()
        root.bind("<space>", lambda e: self.toggle_run())
        self.render()
        self.root.after(TICK_MS, self.tick)

    # ---- layout -----------------------------------------------------------
    def _build(self):
        f = self.fonts
        outer = tk.Frame(self.root, bg=SURFACE, padx=SPACE_6, pady=SPACE_6)
        outer.pack(fill="both", expand=True)

        self.phone = tk.Canvas(outer, width=self.PHONE_W, height=self.PHONE_H, bg=SURFACE,
                               highlightthickness=0)
        self.phone.grid(row=0, column=0, sticky="n")

        right = tk.Frame(outer, bg=SURFACE)
        right.grid(row=0, column=1, sticky="nsew", padx=(SPACE_6, 0))
        outer.columnconfigure(1, weight=1)

        # Header
        tk.Label(right, text="Battery Sim", bg=SURFACE, fg=INK, font=f["display"],
                 anchor="w").pack(fill="x")
        tk.Label(right, text="Watch an iPhone battery charge and drain under different loads.",
                 bg=SURFACE, fg=INK_MUTED, font=f["body"], anchor="w").pack(fill="x", pady=(0, SPACE_4))

        # Status card
        status = Card(right, fonts=f)
        status.pack(fill="x")
        left = tk.Frame(status, bg=SURFACE_RAISED)
        left.pack(side="left")
        self.readout = tk.Label(left, bg=SURFACE_RAISED, fg=INK, font=f["readout"])
        self.readout.pack(anchor="w")
        self.badge = tk.Label(left, font=f["label"], padx=SPACE_2, pady=SPACE_1)
        self.badge.pack(anchor="w", pady=(SPACE_1, 0))
        info = tk.Frame(status, bg=SURFACE_RAISED)
        info.pack(side="left", padx=(SPACE_6, 0), fill="y")
        self.time_left = tk.Label(info, bg=SURFACE_RAISED, fg=INK, font=f["headline"], anchor="w")
        self.time_left.pack(anchor="w", pady=(SPACE_2, 0))
        self.rate_label = tk.Label(info, bg=SURFACE_RAISED, fg=INK_MUTED, font=f["caption"], anchor="w")
        self.rate_label.pack(anchor="w")
        self.clock_label = tk.Label(info, bg=SURFACE_RAISED, fg=INK_MUTED, font=f["caption"], anchor="w")
        self.clock_label.pack(anchor="w")
        self.note_label = tk.Label(info, bg=SURFACE_RAISED, fg=INK, font=f["caption"], anchor="w")
        self.note_label.pack(anchor="w")

        buttons = tk.Frame(status, bg=SURFACE_RAISED)
        buttons.pack(side="right", anchor="n")
        self.run_button = FlatButton(buttons, "Start", self.toggle_run, "primary", f["button"])
        self.run_button.pack(fill="x")
        FlatButton(buttons, "Reset", self.reset, "secondary", f["button"]).pack(fill="x", pady=(SPACE_2, 0))

        # Controls + chart
        lower = tk.Frame(right, bg=SURFACE)
        lower.pack(fill="both", expand=True, pady=(SPACE_6, 0))

        controls = Card(lower, "Loads", "What the phone is doing", fonts=f)
        controls.grid(row=0, column=0, sticky="nsew")
        sliders = [
            ("Screen brightness", self.brightness, 0, 100, "%", None),
            ("Background apps", self.apps, 0, 20, "apps", None),
            ("Temperature", self.temperature, -10, 45, "°C", "Cold and heat both cost charge."),
            ("Battery health", self.health, 60, 100, "%", None),
            ("Simulation speed", self.speed, 1, 120, "min/s", None),
        ]
        for label, var, a, b, unit, hint in sliders:
            LoadSlider(controls, label, var, a, b, unit, f, hint).pack(fill="x", pady=(0, SPACE_4))
        for text, var in (("Low Power Mode", self.low_power), ("Plugged in", self.charging)):
            tk.Checkbutton(controls, text=text, variable=var, bg=SURFACE_RAISED, fg=INK,
                           activebackground=SURFACE_RAISED, selectcolor=SURFACE_RAISED,
                           highlightthickness=0, bd=0, font=f["control"], anchor="w",
                           command=self.on_toggle).pack(fill="x")

        chart_card = Card(lower, "Charge over time", "Simulated hours since start", fonts=f)
        chart_card.grid(row=0, column=1, sticky="nsew", padx=(SPACE_6, 0))
        lower.columnconfigure(1, weight=1)
        lower.rowconfigure(0, weight=1)
        self.chart = tk.Canvas(chart_card, width=380, height=300, bg=SURFACE_RAISED,
                               highlightthickness=0)
        self.chart.pack(fill="both", expand=True)
        self.chart.bind("<Configure>", lambda e: self.draw_chart())

    # ---- simulation loop --------------------------------------------------
    def toggle_run(self):
        if not self.running and self.battery.level <= 0 and not self.charging.get():
            return
        self.running = not self.running
        self.render()

    def on_toggle(self):
        self.battery.low_power = self.low_power.get()
        self.render()

    def reset(self):
        self.running = False
        self.battery.reset()
        self.low_power.set(False)
        self.render()

    def current_drain(self):
        return self.battery.drain_rate(self.brightness.get(), self.apps.get(),
                                       self.temperature.get(), self.health.get())

    def tick(self):
        if self.running:
            hours = self.speed.get() / 60.0 * TICK_MS / 1000.0
            self.battery.step(hours, self.current_drain(), self.charging.get(),
                              self.temperature.get())
            self.low_power.set(self.battery.low_power)
            if self.battery.is_dead and not self.charging.get():
                self.running = False
        self.render()
        self.root.after(TICK_MS, self.tick)

    # ---- rendering --------------------------------------------------------
    def render(self):
        b = self.battery
        level = b.level
        state = state_for(level)
        charging = self.charging.get()
        drain = self.current_drain()

        self.readout.configure(text="%d%%" % round(level))
        if charging and not b.charging_paused_hot and level < 100:
            badge = ("CHARGING", CHARGE, WHITE)
        elif level <= 0:
            badge = ("EMPTY", CHARGE_CRITICAL, WHITE)
        else:
            badge = {"healthy": ("HEALTHY", CHARGE_TINT, INK),
                     "low": ("LOW POWER", CHARGE_LOW, INK),
                     "critical": ("CRITICAL", CHARGE_CRITICAL, WHITE)}[state]
        self.badge.configure(text=badge[0], bg=badge[1], fg=badge[2])

        temperature = self.temperature.get()
        rate = b.net_rate(drain, charging, temperature)
        hours = b.hours_left(drain, charging, temperature)
        if charging:
            if level >= 100:
                left = "Fully charged"
            elif hours is None:
                left = "Not charging"
            else:
                left = "Full in " + format_duration(hours)
            self.rate_label.configure(text="Charging at %.1f %%/h" % max(rate, 0))
        else:
            left = "Phone off" if b.is_dead else format_duration(hours) + " left"
            self.rate_label.configure(text="Draining at %.1f %%/h" % drain)
        self.time_left.configure(text=left)
        self.clock_label.configure(text="Simulated time: " + format_duration(b.sim_hours))
        if b.charging_paused_hot:
            note = "Charging paused: phone is too hot"
        elif self.low_power.get():
            note = "Low Power Mode is on"
        elif not self.running:
            note = "Paused. Press Start or the space bar."
        else:
            note = ""
        self.note_label.configure(text=note)
        self.run_button.configure(text="Pause" if self.running else "Start")

        self.draw_phone()
        self.draw_chart()

    def screen_colors(self):
        """The lock-screen wallpaper dims with brightness; text flips to stay readable."""
        wallpaper = CHARGE_TINT
        t = 0.25 + 0.75 * self.brightness.get() / 100.0
        bg = blend("#000000", wallpaper, t)
        fg = INK if luminance(bg) > 0.3 else WHITE
        return bg, fg

    def draw_phone(self):
        c = self.phone
        c.delete("all")
        W, H = self.PHONE_W, self.PHONE_H
        x1, y1, x2, y2 = 30, 10, W - 30, H - 10
        level = self.battery.level
        charging = self.charging.get()

        # Side buttons (drawn first so the body overlaps them)
        rounded_rect(c, x1 - 5, 140, x1 + 6, 180, 3, fill=DEVICE_EDGE, outline="")   # action button
        rounded_rect(c, x1 - 5, 210, x1 + 6, 275, 3, fill=DEVICE_EDGE, outline="")   # volume up
        rounded_rect(c, x1 - 5, 290, x1 + 6, 355, 3, fill=DEVICE_EDGE, outline="")   # volume down
        rounded_rect(c, x2 - 6, 230, x2 + 5, 330, 3, fill=DEVICE_EDGE, outline="")   # side button

        # Body, rim and screen
        rounded_rect(c, x1, y1, x2, y2, 58, fill=DEVICE_EDGE, outline="")
        rounded_rect(c, x1 + 4, y1 + 4, x2 - 4, y2 - 4, 54, fill=DEVICE, outline="")
        sx1, sy1, sx2, sy2 = x1 + 16, y1 + 16, x2 - 16, y2 - 16
        dead = level <= 0 and not charging
        if dead:
            bg, fg = "#000000", WHITE
        else:
            bg, fg = self.screen_colors()
        rounded_rect(c, sx1, sy1, sx2, sy2, 44, fill=bg, outline="")
        cx = (sx1 + sx2) / 2

        # Dynamic Island
        rounded_rect(c, cx - 55, sy1 + 14, cx + 55, sy1 + 46, 16, fill="#000000", outline="")

        if dead:
            self._draw_empty_screen(cx, (sy1 + sy2) / 2)
            return

        # Status bar: clock on the left, battery on the right
        minutes = int(8 * 60 + self.battery.sim_hours * 60) % (24 * 60)
        clock = "%d:%02d" % (minutes // 60 if minutes // 60 <= 12 else minutes // 60 - 12, minutes % 60)
        if clock.startswith("0:"):
            clock = "12" + clock[1:]
        c.create_text(sx1 + 44, sy1 + 30, text=clock, fill=fg, font=(self.sans, 13, "bold"))
        self._draw_status_battery(sx2 - 66, sy1 + 23, fg, level, charging)

        # Lock-screen clock and date line
        c.create_text(cx, sy1 + 135, text=clock, fill=fg, font=(self.sans, 64, "bold"))
        c.create_text(cx, sy1 + 74, text="Simulated day", fill=fg, font=(self.sans, 12, "bold"))

        # Battery widget: a ring with the percentage in the middle
        ring_y, r = sy1 + 330, 82
        ring = self._state_color(level, charging, fg)
        c.create_oval(cx - r - 26, ring_y - r - 26, cx + r + 26, ring_y + r + 26,
                      fill=blend(bg, fg, 0.08), outline="")
        c.create_arc(cx - r, ring_y - r, cx + r, ring_y + r, start=90, extent=359.9,
                     style="arc", width=14, outline=blend(bg, fg, 0.18))
        if level > 0:
            c.create_arc(cx - r, ring_y - r, cx + r, ring_y + r, start=90,
                         extent=-max(1.0, 359.9 * level / 100.0), style="arc", width=14, outline=ring)
        c.create_text(cx, ring_y - 8, text="%d%%" % round(level), fill=fg, font=(self.mono, 34, "bold"))
        sub = "Charging" if charging and level < 100 else ("Low Power" if self.low_power.get() else "iPhone")
        c.create_text(cx, ring_y + 28, text=sub, fill=fg, font=(self.sans, 12, "bold"))

        # Time-left line under the widget
        c.create_text(cx, ring_y + r + 56, text=self.time_left.cget("text"), fill=fg,
                      font=(self.sans, 13, "bold"))

        # Lock-screen shortcuts and home indicator
        for dx in (-110, 110):
            c.create_oval(cx + dx - 24, sy2 - 112, cx + dx + 24, sy2 - 64,
                          fill=blend(bg, fg, 0.15), outline="")
        if charging:
            self._draw_bolt(cx + 110, sy2 - 88, 9, fg)
        c.create_oval(cx - 118, sy2 - 96, cx - 102, sy2 - 80, outline=fg, width=2)  # torch lens
        rounded_rect(c, cx - 70, sy2 - 22, cx + 70, sy2 - 16, 3, fill=fg, outline="")

        # Very low brightness: an extra dim layer so the whole screen reads darker
        if self.brightness.get() < 15:
            c.create_rectangle(sx1, sy1, sx2, sy2, fill="#000000", stipple="gray25", outline="")

    def _state_color(self, level, charging, fg):
        if charging:
            return CHARGE if luminance(fg) < 0.5 else "#34c26e"
        if self.low_power.get():
            return CHARGE_LOW
        if level <= LOW_POWER_LEVEL:
            return CHARGE_CRITICAL
        return CHARGE if luminance(fg) < 0.5 else "#34c26e"

    def _draw_status_battery(self, x, y, fg, level, charging):
        c = self.phone
        c.create_text(x - 8, y + 7, text="%d" % round(level), fill=fg, anchor="e",
                      font=(self.sans, 11, "bold"))
        w, h = 28, 14
        rounded_rect(c, x, y, x + w, y + h, 4, fill="", outline=fg, width=1.5)
        c.create_rectangle(x + w + 1, y + 4, x + w + 3, y + h - 4, fill=fg, outline="")
        fill_w = max(2, (w - 4) * level / 100.0)
        color = self._state_color(level, charging, fg)
        if not charging and not self.low_power.get() and level > LOW_POWER_LEVEL:
            color = fg
        rounded_rect(c, x + 2, y + 2, x + 2 + fill_w, y + h - 2, 2, fill=color, outline="")
        if charging:
            self._draw_bolt(x + w / 2, y + h / 2, 5, fg if color != fg else blend(fg, "#000000", 0.6))

    def _draw_bolt(self, cx, cy, s, color):
        pts = [cx + 0.2 * s, cy - 1.3 * s, cx - 0.8 * s, cy + 0.15 * s, cx - 0.05 * s, cy + 0.15 * s,
               cx - 0.25 * s, cy + 1.3 * s, cx + 0.8 * s, cy - 0.15 * s, cx + 0.05 * s, cy - 0.15 * s]
        self.phone.create_polygon(pts, fill=color, outline="")

    def _draw_empty_screen(self, cx, cy):
        c = self.phone
        w, h = 120, 52
        rounded_rect(c, cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2, 12, fill="", outline="#8a9099", width=3)
        c.create_rectangle(cx + w / 2 + 3, cy - 10, cx + w / 2 + 9, cy + 10, fill="#8a9099", outline="")
        c.create_rectangle(cx - w / 2 + 8, cy - h / 2 + 8, cx - w / 2 + 16, cy + h / 2 - 8,
                           fill=CHARGE_CRITICAL, outline="")
        c.create_text(cx, cy + 70, text="Plug in to charge", fill="#8a9099", font=(self.sans, 12, "bold"))

    def draw_chart(self):
        c = self.chart
        c.delete("all")
        W = max(c.winfo_width(), 200)
        H = max(c.winfo_height(), 160)
        L, R, T, B = 44, 12, 12, 26
        hist = self.battery.history + [(self.battery.sim_hours, self.battery.level)]
        max_t = max(1.0, hist[-1][0])

        def x(t):
            return L + t / max_t * (W - L - R)

        def y(v):
            return T + (1 - v / 100.0) * (H - T - B)

        for v in (0, 50, 100):
            c.create_line(L, y(v), W - R, y(v), fill=LINE)
            c.create_text(L - 8, y(v), text="%d%%" % v, anchor="e", fill=INK_MUTED, font=self.fonts["caption"])
        # Thin out the points so long runs stay fast to draw.
        step = max(1, len(hist) // 400)
        pts = hist[::step]
        if pts[-1] != hist[-1]:
            pts.append(hist[-1])
        area = [x(0), y(0)]
        line = []
        for t, v in pts:
            area += [x(t), y(v)]
            line += [x(t), y(v)]
        area += [x(pts[-1][0]), y(0)]
        c.create_polygon(area, fill=CHARGE_TINT, outline="")
        c.create_line(L, y(LOW_POWER_LEVEL), W - R, y(LOW_POWER_LEVEL), fill=INK_MUTED, dash=(4, 4))
        c.create_text(W - R, y(LOW_POWER_LEVEL) - 8, text="Low Power 20%", anchor="e",
                      fill=INK_MUTED, font=self.fonts["caption"])
        if len(line) >= 4:
            c.create_line(line, fill=CHARGE, width=2.5, joinstyle="round", capstyle="round")
        lx, ly = x(hist[-1][0]), y(hist[-1][1])
        c.create_oval(lx - 5, ly - 5, lx + 5, ly + 5, fill=CHARGE, outline=SURFACE_RAISED, width=2)
        for i, t in enumerate((0, max_t / 2, max_t)):
            anchor = ("w", "center", "e")[i]
            label = ("%.1f h" % t).replace(".0 h", " h")
            c.create_text(x(t), H - 10, text=label, anchor=anchor, fill=INK_MUTED, font=self.fonts["caption"])


def main():
    root = tk.Tk()
    BatterySimApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
