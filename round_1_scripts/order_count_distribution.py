import argparse
import csv
import glob
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Calculate distribution of summed bid/ask volumes per timestamp from prices CSV data."
    )
    parser.add_argument(
        "--input-glob",
        default="ROUND1/prices_round_1_day_*.csv",
        help="Glob for input price files (default: ROUND1/prices_round_1_day_*.csv)",
    )
    parser.add_argument(
        "--group-by",
        choices=["timestamp", "row"],
        default="timestamp",
        help="Group counts by full timestamp (summing products) or keep per-row counts.",
    )
    parser.add_argument(
        "--out-dir",
        default="analysis_output",
        help="Directory to write output CSV files.",
    )
    return parser.parse_args()


def detect_delimiter(header_line: str) -> str:
    if header_line.count(";") >= header_line.count(","):
        return ";"
    return ","


def is_present(value: str | None) -> bool:
    return value is not None and str(value).strip() != ""


def to_float(value: str | None) -> float:
    if not is_present(value):
        return 0.0
    try:
        return float(str(value))
    except ValueError:
        return 0.0


def ordered_level_columns(fieldnames: Iterable[str], prefix: str) -> list[str]:
    cols = [name for name in fieldnames if name.startswith(prefix)]

    def key_fn(name: str) -> int:
        tail = name.split("_")[-1]
        return int(tail) if tail.isdigit() else 10**9

    return sorted(cols, key=key_fn)


def level_indices(fieldnames: Iterable[str], side: str) -> list[int]:
    indices: set[int] = set()
    for name in fieldnames:
        for prefix in (f"{side}_price_", f"{side}_volume_"):
            if name.startswith(prefix):
                tail = name.split("_")[-1]
                if tail.isdigit():
                    indices.add(int(tail))
    return sorted(indices)


def main() -> None:
    args = parse_args()
    paths = sorted(glob.glob(args.input_glob))
    if not paths:
        raise SystemExit(f"No files matched: {args.input_glob}")

    row_records: list[dict[str, str | int | float]] = []
    per_product_level_hits: dict[str, dict[str, object]] = defaultdict(
        lambda: {"rows": 0, "bid": Counter(), "ask": Counter()}
    )
    max_bid_level = 0
    max_ask_level = 0

    for file_path in paths:
        with open(file_path, "r", newline="", encoding="utf-8") as f:
            first_line = f.readline()
            f.seek(0)
            delimiter = detect_delimiter(first_line)
            reader = csv.DictReader(f, delimiter=delimiter)
            if not reader.fieldnames:
                continue

            bid_levels = level_indices(reader.fieldnames, "bid")
            ask_levels = level_indices(reader.fieldnames, "ask")
            if bid_levels:
                max_bid_level = max(max_bid_level, max(bid_levels))
            if ask_levels:
                max_ask_level = max(max_ask_level, max(ask_levels))

            for row in reader:
                product = str(row.get("product", ""))
                bid_present_levels = [lvl for lvl in bid_levels if abs(to_float(row.get(f"bid_volume_{lvl}"))) > 0.0]
                ask_present_levels = [lvl for lvl in ask_levels if abs(to_float(row.get(f"ask_volume_{lvl}"))) > 0.0]

                product_state = per_product_level_hits[product]
                product_state["rows"] = int(product_state["rows"]) + 1
                bid_counter = product_state["bid"]
                ask_counter = product_state["ask"]
                assert isinstance(bid_counter, Counter)
                assert isinstance(ask_counter, Counter)
                for lvl in bid_present_levels:
                    bid_counter[lvl] += 1
                for lvl in ask_present_levels:
                    ask_counter[lvl] += 1

                bid_volume_sum = sum(to_float(row.get(f"bid_volume_{lvl}")) for lvl in bid_levels)
                # Ask-side depth can be represented as positive or negative across datasets.
                ask_volume_sum = sum(abs(to_float(row.get(f"ask_volume_{lvl}"))) for lvl in ask_levels)

                row_records.append(
                    {
                        "file": str(Path(file_path).name),
                        "day": row.get("day", ""),
                        "timestamp": int(row.get("timestamp", "0")),
                        "product": product,
                        "bid_volume_sum": int(round(bid_volume_sum)),
                        "ask_volume_sum": int(round(ask_volume_sum)),
                    }
                )

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.group_by == "timestamp":
        grouped: dict[tuple[str, str, int], dict[str, int]] = defaultdict(
            lambda: {"bid_volume_sum": 0, "ask_volume_sum": 0}
        )
        for rec in row_records:
            key = (str(rec["file"]), str(rec["day"]), int(rec["timestamp"]))
            grouped[key]["bid_volume_sum"] += int(rec["bid_volume_sum"])
            grouped[key]["ask_volume_sum"] += int(rec["ask_volume_sum"])

        per_timestamp_rows = [
            {
                "file": file_name,
                "day": day,
                "timestamp": timestamp,
                "bid_volume_sum": vals["bid_volume_sum"],
                "ask_volume_sum": vals["ask_volume_sum"],
            }
            for (file_name, day, timestamp), vals in grouped.items()
        ]
        per_timestamp_rows.sort(key=lambda r: (r["file"], int(r["day"]), int(r["timestamp"])))
    else:
        per_timestamp_rows = list(row_records)

    dist_counter = Counter((int(r["bid_volume_sum"]), int(r["ask_volume_sum"])) for r in per_timestamp_rows)

    distribution_rows = [
        {
            "bid_volume_sum": buy,
            "ask_volume_sum": sell,
            "frequency": freq,
        }
        for (buy, sell), freq in sorted(dist_counter.items())
    ]

    per_product_dist_counter = Counter(
        (str(r["product"]), int(r["bid_volume_sum"]), int(r["ask_volume_sum"])) for r in row_records
    )
    per_product_distribution_rows = [
        {
            "product": product,
            "bid_volume_sum": bid,
            "ask_volume_sum": ask,
            "frequency": freq,
        }
        for (product, bid, ask), freq in sorted(per_product_dist_counter.items())
    ]

    level_fill_rows: list[dict[str, object]] = []
    for product, state in sorted(per_product_level_hits.items()):
        rows_count = int(state["rows"])
        if rows_count <= 0:
            continue
        bid_counter = state["bid"]
        ask_counter = state["ask"]
        assert isinstance(bid_counter, Counter)
        assert isinstance(ask_counter, Counter)

        row: dict[str, object] = {"product": product, "rows": rows_count}
        for lvl in range(1, max_bid_level + 1):
            row[f"bid_l{lvl}_fill_rate"] = bid_counter[lvl] / rows_count
        for lvl in range(1, max_ask_level + 1):
            row[f"ask_l{lvl}_fill_rate"] = ask_counter[lvl] / rows_count
        level_fill_rows.append(row)

    per_timestamp_path = out_dir / "order_counts_per_timestamp.csv"
    dist_path = out_dir / "order_count_distribution.csv"
    per_product_dist_path = out_dir / "order_count_distribution_by_product.csv"
    level_fill_path = out_dir / "order_level_fill_rate_by_product.csv"

    with open(per_timestamp_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["file", "day", "timestamp", "bid_volume_sum", "ask_volume_sum"],
        )
        writer.writeheader()
        for row in per_timestamp_rows:
            writer.writerow(row)

    with open(dist_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["bid_volume_sum", "ask_volume_sum", "frequency"],
        )
        writer.writeheader()
        for row in distribution_rows:
            writer.writerow(row)

    with open(per_product_dist_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["product", "bid_volume_sum", "ask_volume_sum", "frequency"],
        )
        writer.writeheader()
        for row in per_product_distribution_rows:
            writer.writerow(row)

    if level_fill_rows:
        level_fields = ["product", "rows"]
        level_fields.extend([f"bid_l{lvl}_fill_rate" for lvl in range(1, max_bid_level + 1)])
        level_fields.extend([f"ask_l{lvl}_fill_rate" for lvl in range(1, max_ask_level + 1)])
        with open(level_fill_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=level_fields)
            writer.writeheader()
            for row in level_fill_rows:
                writer.writerow(row)

    print(f"Wrote: {per_timestamp_path}")
    print(f"Wrote: {dist_path}")
    print(f"Wrote: {per_product_dist_path}")
    print(f"Wrote: {level_fill_path}")
    print(f"Timestamps analyzed: {len(per_timestamp_rows)}")


if __name__ == "__main__":
    main()
