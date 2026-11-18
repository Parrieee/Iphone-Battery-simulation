# week8_practice.py
# First version of my Mobile Phone Charging Simulator (planned in Week 8).
#
# It asks for three inputs, prints a True/False check for each one,
# and prints one estimated charge time.
#
# There is no if or while yet, so:
#   - an input outside its range prints False, but the time is still calculated
#   - an input that is not a number (e.g. "two") prints False, then the
#     calculation crashes with a ValueError
# Next version: use if and while to ask again instead.

print("Mobile Phone Charging Simulator")
print("-------------------------------")

# 1. Ask for the inputs (input() always gives back text)
capacity_text = input("Battery capacity (mAh, 500 to 10000): ")
level_text = input("Starting battery level (%, 0 to 100): ")
current_text = input("Charging current (A, above 0 and up to 5): ")

# 2. Check each input: is it a number, and is it in the valid range?
# replace(".", "", 1) lets one decimal point through, so "2.0" counts as a number.
# "and" stops at the first False, so float() is never run on text like "two" here.
capacity_ok = capacity_text.replace(".", "", 1).isdigit() and 500 <= float(capacity_text) <= 10000
level_ok = level_text.replace(".", "", 1).isdigit() and 0 <= float(level_text) <= 100
current_ok = current_text.replace(".", "", 1).isdigit() and 0 < float(current_text) <= 5

print()
print(f"Capacity valid: {capacity_ok}")
print(f"Level valid:    {level_ok}")
print(f"Current valid:  {current_ok}")

# 3. Calculate the charge time
# charge needed (Ah) = capacity / 1000 x (100 - level) / 100
# time (hours)       = charge needed / current
capacity = float(capacity_text)
level = float(level_text)
current = float(current_text)

charge_needed = capacity / 1000 * (100 - level) / 100
time_hours = charge_needed / current
time_minutes = time_hours * 60

print()
print(f"Charge needed: {charge_needed:.2f} Ah")
print(f"Estimated charge time: {time_minutes:.1f} min ({time_hours:.2f} h)")
