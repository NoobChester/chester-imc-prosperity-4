from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def load_osmium_data(input_dir: str = "ROUND1") -> pd.DataFrame:
    files = sorted(Path(input_dir).glob("prices_round_1_day_*.csv"))
    if not files:
        raise FileNotFoundError(f"No ROUND1 price files found in {input_dir}")

    frames = []
    for file in files:
        df = pd.read_csv(file, sep=";")
        osmium = df[df["product"] == "ASH_COATED_OSMIUM"].copy()
        frames.append(osmium)

    combined = pd.concat(frames, ignore_index=True)
    combined["mid_price"] = pd.to_numeric(combined["mid_price"], errors="coerce")
    combined["timestamp"] = pd.to_numeric(combined["timestamp"], errors="coerce")
    combined["bid_price_1"] = pd.to_numeric(combined["bid_price_1"], errors="coerce")
    combined["ask_price_1"] = pd.to_numeric(combined["ask_price_1"], errors="coerce")
    combined = combined.dropna(subset=["mid_price", "timestamp"]).reset_index(drop=True)

    # Exclude invalid book snapshots that cause artificial -10000 deviations.
    has_any_l1_side = ~(combined["bid_price_1"].isna() & combined["ask_price_1"].isna())
    valid_mid_price = combined["mid_price"] > 0
    combined = combined[has_any_l1_side & valid_mid_price].reset_index(drop=True)
    if combined.empty:
        raise ValueError("No valid osmium mid_price values found")

    return combined[["day", "timestamp", "mid_price", "bid_price_1", "ask_price_1"]]


def main() -> None:
    osmium_df = load_osmium_data("ROUND1")
    deviation = osmium_df["mid_price"] - 10000
    sigma_osmium = float(np.std(deviation))

    # Continuous observation index avoids visual gaps from sparse timestamps (0, 100, 200, ...).
    x = np.arange(len(deviation))
    plt.figure(figsize=(14, 6))
    plt.plot(x, deviation, color="steelblue", linewidth=1.0, label="mid_price - 10000")
    plt.axhline(0.0, color="black", linewidth=1.0, linestyle="-", label="mean reference (0)")
    plt.axhline(sigma_osmium, color="crimson", linewidth=1.2, linestyle="--", label=f"+sigma ({sigma_osmium:.2f})")
    plt.axhline(-sigma_osmium, color="crimson", linewidth=1.2, linestyle="--", label=f"-sigma ({-sigma_osmium:.2f})")
    plt.title("Osmium Deviation From 10000 Over Time")
    plt.xlabel("Observation Index")
    plt.ylabel("mid_price - 10000")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig("osmium_sigma_plot.png", dpi=300, bbox_inches="tight")

    print(f"rows={len(osmium_df)}")
    print(f"sigma_osmium={sigma_osmium:.6f}")
    print("plot_saved=osmium_sigma_plot.png")
    plt.show()


if __name__ == "__main__":
    main()
