import csv
from pathlib import Path

import matplotlib.pyplot as plt


def main() -> None:
    input_path = Path("analysis_output/order_count_distribution.csv")
    output_path = Path("analysis_output/order_count_distribution_barchart.png")

    rows: list[tuple[int, int, int]] = []
    with input_path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            buy = int(row["bid_volume_sum"])
            sell = int(row["ask_volume_sum"])
            freq = int(row["frequency"])
            rows.append((buy, sell, freq))

    if not rows:
        raise ValueError(f"No rows found in {input_path}")

    rows.sort(key=lambda r: (r[0], r[1]))
    labels = [f"BidVol{buy}|AskVol{sell}" for buy, sell, _ in rows]
    frequencies = [freq for _, _, freq in rows]

    fig, ax = plt.subplots(figsize=(14, 6))
    ax.bar(range(len(labels)), frequencies, color="#2C7FB8")
    ax.set_title("Bid/Ask Volume-Sum Distribution per Timestamp (Bar Chart)")
    ax.set_xlabel("(Bid volume sum | Ask volume sum)")
    ax.set_ylabel("Frequency")
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=60, ha="right")

    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=180)
    plt.close(fig)

    print(f"Wrote: {output_path}")


if __name__ == "__main__":
    main()
