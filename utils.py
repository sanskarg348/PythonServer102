from constants import *
from collections import Counter
import numpy as np
from scipy import stats
from nlpUtils import *
import re


def normalize_description(desc):
    if not desc or not isinstance(desc, str):
        return None

    desc = desc.lower().strip()
    desc = re.sub(r"[^a-z0-9\s]", "", desc)
    desc = re.sub(r"\s+", " ", desc)

    return desc


def normalize_to_hours(quantity, unit):
    if unit not in UNIT_CONVERSION_TO_HOURS:
        raise ValueError(f"Unsupported unit: {unit}")

    return float(quantity) * UNIT_CONVERSION_TO_HOURS[unit]


def suggest_quantity_and_unit(hours_value, preferred_unit=None):
    """
    Decide the most human-readable (quantity, unit) pair
    for a given normalized quantity in hours.
    """

    candidates = []

    for unit, factor in UNIT_CONVERSION_TO_HOURS.items():
        qty = hours_value / factor
        rules = UNIT_PREFERENCE_RULES.get(unit)

        if rules and rules["min"] <= qty <= rules["max"]:
            candidates.append((unit, round(qty, 2)))

    # Prefer staying in the same unit if possible
    if preferred_unit:
        for unit, qty in candidates:
            if unit == preferred_unit:
                return qty, unit

    # Otherwise prefer H → MIN → D
    for unit in ["H", "MIN", "D"]:
        for u, q in candidates:
            if u == unit:
                return q, u

    # Fallback (hours)
    return round(hours_value, 2), "H"


def trimmed_mean(values, proportion=0.1):
    values = np.array(values)
    if len(values) == 0:
        return None
    return stats.trim_mean(values, proportion)


def most_common(values):
    if not values:
        return None
    return Counter(values).most_common(1)[0][0]
