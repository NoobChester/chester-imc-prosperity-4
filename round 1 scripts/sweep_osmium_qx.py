import re
import subprocess
from pathlib import Path

TARGET = Path("chester new.py")
RUNNER = ["python", "run_total_profit.py"]
PATTERN_QX = re.compile(r"(OSMIUM_EKF_Q_X\s*=\s*)([0-9]+(?:\.[0-9]+)?)")
PATTERN_PROFIT = re.compile(r"^Total profit:\s*([\d,\-]+)", re.MULTILINE)

text = TARGET.read_text(encoding="utf-8")
match = PATTERN_QX.search(text)
if not match:
    raise RuntimeError("Could not find OSMIUM_EKF_Q_X in chester new.py")

current_qx = float(match.group(2))
# Sweep around the current value in 0.1 increments/decrements.
start = max(0.0, round(current_qx - 1.0, 1))
end = round(current_qx + 1.0, 1)
values = [round(start + 0.1 * i, 1) for i in range(int(round((end - start) / 0.1)) + 1)]

results: list[tuple[int, float]] = []

try:
    for qx in values:
        patched = PATTERN_QX.sub(rf"\g<1>{qx}", text, count=1)
        TARGET.write_text(patched, encoding="utf-8")

        proc = subprocess.run(RUNNER, capture_output=True, text=True)
        combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
        m = PATTERN_PROFIT.search(combined)
        profit = int(m.group(1).replace(",", "")) if m else -10**12
        results.append((profit, qx))
        print(f"profit={profit} qx={qx}")
finally:
    TARGET.write_text(text, encoding="utf-8")

results.sort(reverse=True)
best_profit, best_qx = results[0]
print(f"BEST profit={best_profit} qx={best_qx}")
