#!/usr/bin/env python3
"""Model and maximize the Manual Trading challenge objective.

Challenge objective:
PnL = (research(x) * scale(y) * speed(z)) - Budget_Used
We determine the suitable ratio between Research and Scale in this script.
Speed is not considered at this time.
Note that x,y,z represent the percentage of the budget to allocate

Where:
- research(x) = 200000 * log(1 + x) / log(101)
- scale(y) = 7 * y
- 0.1 <= speed(z) <= 0.9 (linearly based on player rank)
- x >= 0, y >= 0, z >= 0
- budget = 50_000
- budget_used = budget * (x + y + z) / 100
- 0 <= budget_used <= budget
"""

from __future__ import annotations

import argparse
import numpy as np
from dataclasses import dataclass

TOTAL_BUDGET = 50_000
RESEARCH_MAX = 200_000
SCALE_MAX = 7
SPEED_MIN = 0.1
SPEED_MAX = 0.9
SPEED_DEFAULT = 0.1
TOTAL_MAX = 100

@dataclass
class result:
    research_percentage: int
    scale_percentage: int
    pnl: int

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Given speed and speed multiplier, compute the best research and scale allocation to maximize PnL.")
    parser.add_argument(
        "speed",
        nargs="?",
        type=int,
        help="Speed allocation percentage (0..100).",
    )
    parser.add_argument(
        "speed_multiplier",
        nargs="?",
        type=float,
        help="Speed multiplier (0.1..0.9).",
    )
    return parser.parse_args()

"""Challenge formula: 200000 * log(1 + x) / log(101)."""
def research_outcome(research: int) -> float:
    return RESEARCH_MAX * np.log(1 + research) / np.log(1 + TOTAL_MAX)

"""Linear growth from 0 to 7."""
def scale_outcome(scale: int) -> float:
    return SCALE_MAX * (scale / TOTAL_MAX)

"""Used budget in XIRECs from percentage allocations."""
def budget_used(research: int, scale: int, speed: int) -> int:
    return TOTAL_BUDGET * (research + scale + speed) / TOTAL_MAX

"""Compute challenge PnL."""
def pnl(research: int, scale: int, speed: int, speed_multiplier: float) -> int:
    return int(
        research_outcome(research) * scale_outcome(scale) * speed_multiplier
        - budget_used(research, scale, speed)
    )

def main() -> None:
    args = parse_args()
    if args.speed is None or args.speed_multiplier is None:
        raise ValueError("missing params")

    speed = args.speed
    if not (0 <= speed <= TOTAL_MAX):
        raise ValueError("speed must be in [0, 100]")

    speed_multiplier = args.speed_multiplier
    if not (SPEED_MIN <= speed_multiplier <= SPEED_MAX):
        raise ValueError("speed_multiplier must be in [0.1, 0.9]")


    step = 1
    research_scale_sum_max = TOTAL_MAX - speed
    best_pnl = result(0, 0, -TOTAL_BUDGET)
    for research in range(0, research_scale_sum_max + 1, step):
        for scale in range(0, research_scale_sum_max + 1, step):
            if (research + scale) > research_scale_sum_max:
                continue
            current_pnl = pnl(research, scale, speed, speed_multiplier)
            if current_pnl > best_pnl.pnl:
                best_pnl = result(research, scale, current_pnl)
    print(
        f"Best R alloc = {best_pnl.research_percentage}%, best Sc alloc = {best_pnl.scale_percentage}%, "
        f"PnL = {best_pnl.pnl}"
    )

if __name__ == "__main__":
    main()
