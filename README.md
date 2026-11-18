# Iphone-Battery-simulation

A desktop simulator, built with tkinter, that shows an iPhone battery charging and draining under different loads.

## Run it

Python 3.8 or later with tkinter (included in the python.org installers; on Debian or Ubuntu, `sudo apt install python3-tk`).

```bash
python3 battery_sim.py
```

## What you can do

- Press **Start** (or the space bar) to run the clock. The phone's lock screen shows the time, a battery ring and the time left.
- Drag the **load sliders** (screen brightness, background apps, temperature, battery health) and watch the drain rate change.
- Tick **Plugged in** to charge: fast to 80%, slower to 95%, then a trickle. Above 40 °C charging pauses.
- **Low Power Mode** turns on by itself at 20% and cuts drain by 30%. While charging, it turns off again at 80%.
- At 0% the screen goes black until you plug in.

Colours and type follow the Battery Sim design system.
