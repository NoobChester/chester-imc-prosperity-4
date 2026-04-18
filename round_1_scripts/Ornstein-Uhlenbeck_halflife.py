from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def calculate_fv_book_volumetric(row: pd.Series) -> float:
	"""Calculate volumetric fair value from top 3 bid/ask levels."""
	bid_prices = []
	bid_vols = []
	ask_prices = []
	ask_vols = []

	for i in range(1, 4):
		bid_p = row.get(f"bid_price_{i}")
		bid_v = row.get(f"bid_volume_{i}")
		if pd.notna(bid_p) and pd.notna(bid_v):
			bid_prices.append(float(bid_p))
			bid_vols.append(float(bid_v))

	for i in range(1, 4):
		ask_p = row.get(f"ask_price_{i}")
		ask_v = row.get(f"ask_volume_{i}")
		if pd.notna(ask_p) and pd.notna(ask_v):
			ask_prices.append(float(ask_p))
			ask_vols.append(float(ask_v))

	if not bid_prices or not ask_prices:
		return float("nan")

	bid_numerator = sum(p * v for p, v in zip(bid_prices, bid_vols))
	ask_numerator = sum(p * v for p, v in zip(ask_prices, ask_vols))
	total_volume = sum(bid_vols) + sum(ask_vols)

	if total_volume <= 0:
		return float("nan")

	return (bid_numerator + ask_numerator) / total_volume


def load_osmium_volumetric_series(input_dir: str = "ROUND1") -> pd.Series:
	"""Load osmium rows and return volumetric fair value time series."""
	files = sorted(Path(input_dir).glob("prices_round_1_day_*.csv"))
	if not files:
		raise FileNotFoundError(f"No ROUND1 price files found in {input_dir}")

	frames = []
	for file in files:
		df = pd.read_csv(file, sep=";")
		osmium_df = df[df["product"] == "ASH_COATED_OSMIUM"].copy()
		frames.append(osmium_df)

	osmium = pd.concat(frames, ignore_index=True)
	osmium["day"] = pd.to_numeric(osmium["day"], errors="coerce")
	osmium["timestamp"] = pd.to_numeric(osmium["timestamp"], errors="coerce")
	osmium = osmium.dropna(subset=["day", "timestamp"]).sort_values(["day", "timestamp"]).reset_index(drop=True)

	osmium["mid_price"] = osmium.apply(calculate_fv_book_volumetric, axis=1)
	osmium = osmium.dropna(subset=["mid_price"]).reset_index(drop=True)
	osmium = osmium[osmium["mid_price"] > 0].reset_index(drop=True)

	if len(osmium) < 3:
		raise ValueError("Not enough valid volumetric fair value points to fit OU model")

	return osmium["mid_price"]


def main() -> None:
	mid_price = load_osmium_volumetric_series("ROUND1")

	smoothed_series = mid_price.rolling(window=100).mean().dropna()
	if len(smoothed_series) < 3:
		raise ValueError("Not enough smoothed points to fit OU model")

	# 1. Tick-to-tick price changes (Y)
	delta_p = smoothed_series.diff().dropna()

	# 2. Previous tick's distance from long-run mean 10_000 (X)
	spread_from_mean = (smoothed_series.shift(1) - 10_000).dropna()

	# Align X and Y by index
	common_index = delta_p.index.intersection(spread_from_mean.index)
	y = delta_p.loc[common_index]
	x = spread_from_mean.loc[common_index]
	if len(x) < 2:
		raise ValueError("Not enough aligned points for regression")

	# 3. Linear regression: delta_p = slope * spread_from_mean + intercept
	x_mean = x.mean()
	y_mean = y.mean()
	x_var = ((x - x_mean) ** 2).sum()
	if x_var == 0:
		raise ValueError("Regression failed: zero variance in spread_from_mean")
	slope = ((x - x_mean) * (y - y_mean)).sum() / x_var
	intercept = y_mean - slope * x_mean

	print(f"Data points used: {len(smoothed_series)}")
	print(f"Regression slope: {slope:.8f}")
	print(f"Regression intercept: {intercept:.8f}")

	# 4. Half-life (valid only for mean-reverting slope < 0)
	if slope >= 0:
		print("Series is not mean-reverting under this fit (slope >= 0), half-life undefined.")
		return

	half_life = -np.log(2) / slope
	wave_duration = 2 * half_life

	print(f"Mean Reversion Speed (Lambda): {-slope:.6f}")
	print(f"Half-Life: {half_life:.2f} ticks")
	print(f"Estimated Wave Duration: {wave_duration:.2f} ticks")

	# 5. Visualization
	fig, axes = plt.subplots(2, 1, figsize=(12, 9))

	# Top: smoothed volumetric fair value over time.
	ax_ts = axes[0]
	ax_ts.plot(mid_price.index, mid_price.values, color="lightcoral", linewidth=0.8, alpha=0.5, label="Volumetric (Raw)")
	ax_ts.plot(smoothed_series.index, smoothed_series.values, color="steelblue", linewidth=1.4, label="Smoothed (Rolling 100)")
	ax_ts.axhline(10_000, color="black", linestyle="--", linewidth=1.0, alpha=0.7)
	ax_ts.set_title("Volumetric Fair Value: Raw vs Smoothed (Window=100)")
	ax_ts.set_xlabel("Tick Index")
	ax_ts.set_ylabel("Price")
	ax_ts.grid(True, alpha=0.3)
	ax_ts.legend(loc="best")

	# Bottom: OU regression scatter with fitted line.
	ax_reg = axes[1]
	ax_reg.scatter(x.values, y.values, s=8, alpha=0.25, color="indianred", label="Observed")
	x_line = np.linspace(x.min(), x.max(), 200)
	y_line = slope * x_line + intercept
	ax_reg.plot(x_line, y_line, color="darkblue", linewidth=2.0, label="Linear Fit")
	ax_reg.axhline(0.0, color="black", linestyle=":", linewidth=1.0, alpha=0.7)
	ax_reg.set_title("OU Fit: Delta Price vs Spread From 10000")
	ax_reg.set_xlabel("Spread From Mean (P[t-1] - 10000)")
	ax_reg.set_ylabel("Delta Price (P[t] - P[t-1])")
	ax_reg.grid(True, alpha=0.3)
	ax_reg.legend(loc="best")

	fig.suptitle(
		f"Ornstein-Uhlenbeck Diagnostics | slope={slope:.6f}, half_life={half_life:.2f}",
		fontsize=12,
	)
	plt.tight_layout()
	plt.savefig("ou_halflife_visualization.png", dpi=300, bbox_inches="tight")
	print("Plot saved as 'ou_halflife_visualization.png'")
	plt.show()


if __name__ == "__main__":
	main()