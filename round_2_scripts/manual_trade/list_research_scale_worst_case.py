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
TOTAL_MAX = 100

@dataclass
class result:
    research_percentage: int
    scale_percentage: int
    min_speed_pnl: int

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
def pnl(research: int, scale: int, speed: int) -> int:
    return int(research_outcome(research) * scale_outcome(scale) * SPEED_MIN - budget_used(research, scale, speed))

def main() -> None:
    step = 1
    for research_scale_sum_max in range(32, 101, step):
        best_min_speed_pnl = result(0, 0, -TOTAL_BUDGET)
        for research in range(0, research_scale_sum_max + 1, step):
            for scale in range(0, research_scale_sum_max + 1, step):
                if (research + scale) > research_scale_sum_max:
                    continue
                speed = TOTAL_MAX - research_scale_sum_max
                current_min_speed_pnl = pnl(research, scale, speed)
                if current_min_speed_pnl > best_min_speed_pnl.min_speed_pnl:
                    best_min_speed_pnl = result(research, scale, current_min_speed_pnl)
        print(f"Given R and Sc alloc = {research_scale_sum_max}%, best alloc = {best_min_speed_pnl.research_percentage}% R {best_min_speed_pnl.scale_percentage}% Sc, PnL at min Sp = {best_min_speed_pnl.min_speed_pnl}")

if __name__ == "__main__":
    main()
