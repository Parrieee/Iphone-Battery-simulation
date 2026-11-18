"""The battery calculator behind Battery Sim.

Pure Python with no GUI code, so it can be tested or reused on its own.
All rates are in percent of charge per hour; time is in hours.
"""

LOW_POWER_LEVEL = 20       # Low Power Mode switches on at or below this level
LOW_POWER_OFF_LEVEL = 80   # ...and off again at this level while charging
CRITICAL_LEVEL = 10


def state_for(level):
    """Name the battery's state for a charge level: "healthy", "low" or "critical"."""
    if level <= CRITICAL_LEVEL:
        return "critical"
    if level <= LOW_POWER_LEVEL:
        return "low"
    return "healthy"


def format_duration(hours):
    """3.34 -> "3 h 20 min"; under an hour -> "45 min"; None or infinity -> "—"."""
    if hours is None or hours == float("inf"):
        return "—"
    minutes = int(round(hours * 60))
    h, m = divmod(minutes, 60)
    if h == 0:
        return "%d min" % m
    return "%d h %02d min" % (h, m)


class Battery:
    """A simple battery model."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.level = 100.0
        self.sim_hours = 0.0
        self.history = [(0.0, 100.0)]
        self.charging_paused_hot = False
        self.low_power = False
        self._low_power_offered = False

    # ---- rates ------------------------------------------------------------
    def drain_rate(self, brightness, apps, temperature, health, low_power=None):
        """How fast the phone uses charge, from what it is doing.

        brightness 0–100 (%), apps = background apps, temperature in °C,
        health 1–100 (% of original capacity). low_power defaults to the
        battery's own Low Power Mode setting.
        """
        if self.level <= 0:
            return 0.0
        if low_power is None:
            low_power = self.low_power
        rate = 1.0                      # standby: radios, clock, sensors
        rate += 2.0                     # screen on
        rate += 4.0 * brightness / 100  # backlight
        rate += 0.35 * apps             # background apps refreshing
        if temperature < 10:            # cold cells deliver less charge
            rate += (10 - temperature) * 0.25
        elif temperature > 35:          # heat wastes energy and ages the cell
            rate += (temperature - 35) * 0.3
        if low_power:
            rate *= 0.7
        return rate * 100.0 / health    # a worn battery holds less, so drains faster

    def charge_rate(self, temperature):
        """Fast up to 80%, slower to 95%, then a trickle. Paused above 40 °C."""
        self.charging_paused_hot = temperature > 40
        if self.charging_paused_hot:
            return 0.0
        if self.level < 80:
            return 60.0
        if self.level < 95:
            return 20.0
        return 8.0

    def net_rate(self, drain, charging, temperature):
        """Change in charge per hour: positive while charging, negative while draining.
        While plugged in, the charger covers half of the phone's own use."""
        if charging:
            return self.charge_rate(temperature) - drain * 0.5
        self.charging_paused_hot = False
        return -drain

    def hours_left(self, drain, charging, temperature):
        """Hours until full (charging) or empty (draining); None if it never gets there."""
        rate = self.net_rate(drain, charging, temperature)
        if charging:
            return (100 - self.level) / rate if rate > 0 else None
        return self.level / -rate if rate < 0 else None

    # ---- the clock ----------------------------------------------------------
    def step(self, hours, drain, charging, temperature):
        """Advance the simulation by `hours`; returns the net rate that was applied."""
        net = self.net_rate(drain, charging, temperature)
        self.level = max(0.0, min(100.0, self.level + net * hours))
        self.sim_hours += hours
        self._update_low_power(charging)
        if self.sim_hours - self.history[-1][0] >= 1 / 60.0 - 1e-9:   # one point per simulated minute
            self.history.append((self.sim_hours, self.level))
            if len(self.history) > 3000:
                self.history = self.history[::2]
        return net

    def _update_low_power(self, charging):
        """Like iOS: switch Low Power Mode on once at 20%, off again at 80% while charging."""
        if self.level <= LOW_POWER_LEVEL and not self._low_power_offered:
            self.low_power = True
            self._low_power_offered = True
        if self.level >= LOW_POWER_OFF_LEVEL and charging and self.low_power:
            self.low_power = False
        if self.level > LOW_POWER_LEVEL + 5:
            self._low_power_offered = False

    @property
    def is_dead(self):
        return self.level <= 0
