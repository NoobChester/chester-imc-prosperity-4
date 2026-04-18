import itertools
import re
import subprocess
from pathlib import Path

TARGET = Path("chester new.py")
RUNNER = ["python", "-u", "run_total_profit.py"]

text = TARGET.read_text(encoding="utf-8")
start_pat = re.compile(r"def _get_osmium_phase_fair_shift\(")
end_pat = re.compile(r"\n\s*def _update_root_fair\(")
profit_pat = re.compile(r"^Total profit:\s*([\d,\-]+)", re.MULTILINE)

s = start_pat.search(text)
if not s:
    raise RuntimeError("Could not find _get_osmium_phase_fair_shift start")
e = end_pat.search(text, s.start())
if not e:
    raise RuntimeError("Could not find _get_osmium_phase_fair_shift end")

orig_block = text[s.start():e.start()]

thresholds = [0.5, 0.6, 0.7]
base_shifts = [0.6, 0.8, 1.0]
strong_shifts = [1.5, 2.0, 2.5]


def build_block(block: str, threshold: float, base_shift: float, strong_shift: float) -> str:
    out = block
    out = re.sub(
        r"turning_down = normalized_component > [0-9.]+ and slope < 0\.0",
        f"turning_down = normalized_component > {threshold} and slope < 0.0",
        out,
        count=1,
    )
    out = re.sub(
        r"turning_up = normalized_component < -[0-9.]+ and slope > 0\.0",
        f"turning_up = normalized_component < -{threshold} and slope > 0.0",
        out,
        count=1,
    )
    out = re.sub(r"return -[0-9.]+", f"return -{strong_shift}", out, count=1)
    out = re.sub(r"return [0-9.]+", f"return {strong_shift}", out, count=1)
    out = re.sub(r"return -[0-9.]+", f"return -{base_shift}", out, count=1)
    out = re.sub(r"return [0-9.]+", f"return {base_shift}", out, count=1)
    return out

results: list[tuple[int, float, float, float]] = []

try:
    for threshold, base_shift, strong_shift in itertools.product(thresholds, base_shifts, strong_shifts):
        new_block = build_block(orig_block, threshold, base_shift, strong_shift)
        TARGET.write_text(text[:s.start()] + new_block + text[e.start():], encoding="utf-8")

        proc = subprocess.run(RUNNER, capture_output=True, text=True)
        combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
        m = profit_pat.search(combined)
        profit = int(m.group(1).replace(",", "")) if m else -10**12
        results.append((profit, threshold, base_shift, strong_shift))
        print(f"profit={profit} threshold={threshold} base={base_shift} strong={strong_shift}")
finally:
    TARGET.write_text(text, encoding="utf-8")

results.sort(reverse=True)
best = results[0]
print(f"BEST profit={best[0]} threshold={best[1]} base={best[2]} strong={best[3]}")
