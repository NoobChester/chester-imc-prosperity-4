import re
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from typing import cast

from prosperity4bt.back_tester import BackTester
from prosperity4bt.models.test_options import TestOptions, TradeMatchingMode


ANSI_ESCAPE_RE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")
TOTAL_PROFIT_RE = re.compile(r"\bTotal\s+profit\s*:\s*.*", re.IGNORECASE)


def main() -> int:
    options = TestOptions(Path("chester new.py").resolve(), ["1"], cast(Path, None))
    options.print_output = False
    options.trade_matching_mode = TradeMatchingMode.worse
    options.show_progress = False
    options.merge_profit_loss = False
    options.show_visualizer = False
    options.merge_timestamps = False

    buffer = StringIO()
    back_tester = BackTester(options)

    with redirect_stdout(buffer), redirect_stderr(buffer):
        back_tester.run()

    combined_output = buffer.getvalue()

    profit_lines: list[str] = []
    for raw_line in combined_output.splitlines():
        clean_line = ANSI_ESCAPE_RE.sub("", raw_line).strip()
        if TOTAL_PROFIT_RE.search(clean_line):
            profit_lines.append(clean_line)

    if profit_lines:
        print(profit_lines[-1])
    else:
        print("Total profit line not found.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
