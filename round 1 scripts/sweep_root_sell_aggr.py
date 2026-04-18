import itertools
import re
import subprocess
from pathlib import Path

TARGET = Path("chester new.py")
RUNNER = ["python", "run_total_profit.py"]

orig = TARGET.read_text(encoding="utf-8")

inst_caps = [5.5, 6.0, 6.5, 7.0]
roll_caps = [4.5, 5.0, 5.5]
divs = [8, 7]
w_inst = [0.9, 1.0]
w_roll = [0.75, 0.85]

roots_block_re = re.compile(
    r"(def _rolling_sell_quantity_from_fair_deviation_roots\([\s\S]*?\n\s*return min\(qty, sell_remaining\)\n)",
    re.MULTILINE,
)

pattern_inst = re.compile(r"instant_signal = min\([0-9.]+, deviation / scale\)")
pattern_roll = re.compile(r"rolling_signal = min\([0-9.]+, dev_ema / scale\)")
pattern_div = re.compile(r"base_qty = max\(1, total_available // [0-9]+\)")
pattern_qty = re.compile(r"qty = int\(round\(base_qty \* \(1\.0 \+ [0-9.]+ \* instant_signal \+ [0-9.]+ \* rolling_signal\)\)\)")
pattern_profit = re.compile(r"^Total profit:\s*([\d,\-]+)", re.MULTILINE)

results = []


def extract_profit(output: str) -> int:
    m = pattern_profit.search(output)
    if not m:
        return -10**12
    return int(m.group(1).replace(",", ""))

try:
    baseline_proc = subprocess.run(RUNNER, capture_output=True, text=True)
    baseline_combined = (baseline_proc.stdout or "") + "\n" + (baseline_proc.stderr or "")
    baseline_profit = extract_profit(baseline_combined)
    print(f"BASELINE profit={baseline_profit}")

    for ic, rc, d, wi, wr in itertools.product(inst_caps, roll_caps, divs, w_inst, w_roll):
        txt = orig
        block_match = roots_block_re.search(txt)
        if not block_match:
            raise RuntimeError("Could not locate roots sell quantity function block")

        block = block_match.group(1)
        block = pattern_inst.sub(f"instant_signal = min({ic}, deviation / scale)", block, count=1)
        block = pattern_roll.sub(f"rolling_signal = min({rc}, dev_ema / scale)", block, count=1)
        block = pattern_div.sub(f"base_qty = max(1, total_available // {d})", block, count=1)
        block = pattern_qty.sub(
            f"qty = int(round(base_qty * (1.0 + {wi} * instant_signal + {wr} * rolling_signal)))",
            block,
            count=1,
        )

        txt = txt[: block_match.start(1)] + block + txt[block_match.end(1) :]
        TARGET.write_text(txt, encoding="utf-8")

        try:
            proc = subprocess.run(RUNNER, capture_output=True, text=True, timeout=45)
        except subprocess.TimeoutExpired:
            continue
        combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
        profit = extract_profit(combined)
        gain = profit - baseline_profit

        if gain > 100:
            results.append((profit, gain, ic, rc, d, wi, wr))
            print(f"profit={profit} gain={gain} ic={ic} rc={rc} d={d} wi={wi} wr={wr}")

finally:
    TARGET.write_text(orig, encoding="utf-8")

results.sort(reverse=True)
print("TOP_RESULTS_GAIN_GT_100")
if not results:
    print("NO_CANDIDATE_WITH_GAIN_GT_100")
for row in results[:10]:
    print(row)
