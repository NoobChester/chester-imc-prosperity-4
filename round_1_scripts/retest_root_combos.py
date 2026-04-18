import re
import subprocess
from pathlib import Path

TARGET = Path("chester new.py")
RUNNER = ["python", "run_total_profit.py"]

orig = TARGET.read_text(encoding="utf-8")

func_start_pat = re.compile(r"def _rolling_sell_quantity_from_fair_deviation_roots\(")
func_end_pat = re.compile(r"\n\s*def _update_root_buy_weighted_avg\(")
profit_pat = re.compile(r"^Total profit:\s*([\d,\-]+)", re.MULTILINE)

# Candidate sets from your top list
candidates = [
    (5.5, 4.5, 8, 0.9, 0.75),
    (5.5, 4.5, 8, 0.95, 0.75),
    (5.5, 4.5, 8, 1.0, 0.75),
    (5.5, 4.8, 8, 1.0, 0.75),
    (5.5, 5.0, 8, 1.0, 0.75),
    (5.5, 5.3, 8, 1.0, 0.75),
    # current-ish aggressive variants
    (5.5, 5.5, 7, 0.9, 0.75),
    (5.5, 4.5, 8, 1.0, 0.7),
    (5.5, 4.5, 8, 1.0, 0.8),
]


def set_combo(text: str, combo: tuple[float, float, int, float, float]) -> str:
    ic, rc, d, wi, wr = combo
    start_match = func_start_pat.search(text)
    if not start_match:
        raise RuntimeError("Could not find roots function start")

    end_match = func_end_pat.search(text, start_match.start())
    if not end_match:
        raise RuntimeError("Could not find roots function end")

    block = text[start_match.start(): end_match.start()]
    block = re.sub(r"instant_signal = min\([0-9.]+, deviation / scale\)", f"instant_signal = min({ic}, deviation / scale)", block, count=1)
    block = re.sub(r"rolling_signal = min\([0-9.]+, dev_ema / scale\)", f"rolling_signal = min({rc}, dev_ema / scale)", block, count=1)
    block = re.sub(r"base_qty = max\(1, total_available // [0-9]+\)", f"base_qty = max(1, total_available // {d})", block, count=1)
    block = re.sub(
        r"qty = int\(round\(base_qty \* \(1\.0 \+ [0-9.]+ \* instant_signal \+ [0-9.]+ \* rolling_signal\)\)\)",
        f"qty = int(round(base_qty * (1.0 + {wi} * instant_signal + {wr} * rolling_signal)))",
        block,
        count=1,
    )
    return text[:start_match.start()] + block + text[end_match.start():]


results: list[tuple[int, tuple[float, float, int, float, float]]] = []

try:
    for combo in candidates:
        TARGET.write_text(set_combo(orig, combo), encoding="utf-8")
        proc = subprocess.run(RUNNER, capture_output=True, text=True)
        out = (proc.stdout or "") + "\n" + (proc.stderr or "")
        m = profit_pat.search(out)
        profit = int(m.group(1).replace(",", "")) if m else -10**12
        results.append((profit, combo))
        print(f"profit={profit} combo={combo}")
finally:
    TARGET.write_text(orig, encoding="utf-8")

results.sort(reverse=True)
print("BEST", results[0])
