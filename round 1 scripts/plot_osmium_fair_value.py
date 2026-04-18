import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

class ExtendedKalmanFilterOU:
    def __init__(self, r_variance: float = 5.349606**2) -> None:
        # State Vector: [Price_Deviation, Reversion_Factor]
        self.x: float = 0.0        # Start exactly at the 10k anchor
        self.phi: float = 0.997229     # Start assuming very slow mean reversion (1.0 = no reversion)

        # Covariance Matrix (P)
        self.p00: float = 1.0
        self.p01: float = 0.0
        self.p10: float = 0.0
        self.p11: float = 0.01

        # Process Noise Matrix (Q)
        self.q_x: float =  0.4927061830400836     # How fast the true price wanders
        self.q_phi: float = 1e-8    # How fast the mean-reversion speed changes

        # Measurement Noise (R)
        self.r: float = r_variance

    def update(self, measurement: float) -> tuple[float, float]:
        # Convert raw mid-price to deviation from the mean
        z = measurement - 10000.0

        # --- 1. PREDICT STEP ---
        # Predict next state using non-linear functions
        x_pred = self.phi * self.x
        phi_pred = self.phi

        # Evaluate the Jacobian matrix F at the current state
        F00 = self.phi
        F01 = self.x
        F10 = 0.0
        F11 = 1.0

        # Predict Covariance: P_pred = F * P * F^T + Q
        # (Expanded by hand for maximum compute speed)
        FP00 = F00 * self.p00 + F01 * self.p10
        FP01 = F00 * self.p01 + F01 * self.p11
        FP10 = self.p10
        FP11 = self.p11

        P_pred00 = FP00 * F00 + FP01 * F01 + self.q_x
        P_pred01 = FP00 * F10 + FP01 * F11
        P_pred10 = FP10 * F00 + FP11 * F01
        P_pred11 = FP10 * F10 + FP11 * F11 + self.q_phi

        # --- 2. UPDATE STEP ---
        # The Innovation (y)
        y = z - x_pred

        # The Innovation Covariance (S) = H * P_pred * H^T + R
        # Because H = [1, 0], this collapses gracefully to a scalar!
        S = P_pred00 + self.r

        # The Kalman Gain (K) = P_pred * H^T * S^-1
        K0 = P_pred00 / S
        K1 = P_pred10 / S

        # Update State Vector: X = X_pred + K * y
        self.x = x_pred + K0 * y
        self.phi = phi_pred + K1 * y

        # Update Covariance Matrix: P = (I - K * H) * P_pred
        self.p00 = (1 - K0) * P_pred00
        self.p01 = (1 - K0) * P_pred01
        self.p10 = -K1 * P_pred00 + P_pred10
        self.p11 = -K1 * P_pred01 + P_pred11

        # Return the actual Fair Value and the current Reversion Speed
        return self.x + 10000.0, self.phi

def calculate_fv_book_volumetric(row: pd.Series) -> float:
    """Calculate volumetric fair value from top 3 bid/ask levels (unfiltered).

    FV_book = (sum of bid_price_i * bid_volume_i + sum of ask_price_i * ask_volume_i) /
              (sum of bid_volumes + sum of ask_volumes)
    for i in [1, 2, 3]
    """
    bid_prices: list[float] = []
    bid_vols: list[float] = []
    ask_prices: list[float] = []
    ask_vols: list[float] = []

    # Extract bid levels
    for i in range(1, 4):
        price_col = f'bid_price_{i}'
        vol_col = f'bid_volume_{i}'
        if price_col in row and vol_col in row:
            bid_price = row[price_col]
            bid_volume = row[vol_col]
            if pd.notna(bid_price) and pd.notna(bid_volume):
                bid_prices.append(float(bid_price))
                bid_vols.append(float(bid_volume))

    # Extract ask levels
    for i in range(1, 4):
        price_col = f'ask_price_{i}'
        vol_col = f'ask_volume_{i}'
        if price_col in row and vol_col in row:
            ask_price = row[price_col]
            ask_volume = row[vol_col]
            if pd.notna(ask_price) and pd.notna(ask_volume):
                ask_prices.append(float(ask_price))
                ask_vols.append(float(ask_volume))

    if not bid_prices or not ask_prices:
        return np.nan

    bid_numerator = sum(p * v for p, v in zip(bid_prices, bid_vols))
    bid_volume = sum(bid_vols)
    ask_numerator = sum(p * v for p, v in zip(ask_prices, ask_vols))
    ask_volume = sum(ask_vols)

    total_volume = bid_volume + ask_volume
    if total_volume <= 0:
        return np.nan

    fv_book = (bid_numerator + ask_numerator) / total_volume
    return fv_book


def estimate_theoretical_process_noise(mid_price: pd.Series) -> float:
    """Estimate theoretical process noise from 1st and 2nd differences of a price series."""
    prices = np.asarray(pd.Series(mid_price).dropna().astype(float).to_numpy(), dtype=float)
    if len(prices) < 3:
        return float("nan")

    velocity = np.diff(prices)
    velocity_shocks = np.diff(velocity)
    if len(velocity_shocks) == 0:
        return float("nan")

    theoretical_q = np.mean(velocity_shocks**2)
    return float(theoretical_q)



# Load all price data
data_frames: list[pd.DataFrame] = []
for day in [-2, -1, 0]:
    csv_path = Path(f'ROUND1/prices_round_1_day_{day}.csv')
    if csv_path.exists():
        df = pd.read_csv(csv_path, sep=';')
        # Filter for osmium only
        osmium_df = df[df['product'] == 'ASH_COATED_OSMIUM'].copy()
        data_frames.append(osmium_df)
        print(f"Loaded day {day}: {len(osmium_df)} records")

if not data_frames:
    print("No data files found!")
    exit(1)

# Combine all data
combined_df = pd.concat(data_frames, ignore_index=True)
print(f"Total records: {len(combined_df)}")

# Calculate volumetric fair values
combined_df['fv_book_volumetric'] = combined_df.apply(calculate_fv_book_volumetric, axis=1)

# Keep only valid volumetric observations before filtering.
valid_df = combined_df.dropna(subset=['fv_book_volumetric']).reset_index(drop=True)

# Transitioned filter: Extended Kalman Filter with OU latent dynamics.
ekf = ExtendedKalmanFilterOU(r_variance=5.349606**2)
ekf_fair_values: list[float] = []
ekf_phi_values: list[float] = []

for measurement in valid_df['fv_book_volumetric']:
    fair_value, phi_value = ekf.update(measurement)
    ekf_fair_values.append(fair_value)
    ekf_phi_values.append(phi_value)

valid_df['fv_book_ekf_ou'] = ekf_fair_values
valid_df['phi_estimate'] = ekf_phi_values

print(f"Valid fair value records: {len(valid_df)}")


# Print summary statistics
print("\nFair Value Statistics")
print("=" * 42)
vol_std = valid_df['fv_book_volumetric'].std()
ekf_std = valid_df['fv_book_ekf_ou'].std()
noise_reduction = ((vol_std - ekf_std) / vol_std) * 100 if vol_std > 0 else 0.0
theoretical_q = estimate_theoretical_process_noise(valid_df['fv_book_volumetric'])

print(f"Volumetric Std: {vol_std:.4f}")
print(f"EKF-OU Std:     {ekf_std:.4f}")
print(f"Noise Reduction:{noise_reduction:.1f}%")
print(f"Theoretical Process Noise: {float(theoretical_q)}")
print(f"Final phi:      {valid_df['phi_estimate'].iloc[-1]:.6f}")
print(f"Mean phi:       {valid_df['phi_estimate'].mean():.6f}")


# Create figure with subplots for price and latent phi.
fig, axes = plt.subplots(3, 1, figsize=(14, 12))  # type: ignore[reportUnknownMemberType]

sequence = range(len(valid_df))

# Top: Time series comparison
ax_ts = axes[0]
ax_ts.plot(sequence, valid_df['fv_book_volumetric'], linewidth=0.7, label='Volumetric', color='lightcoral', alpha=0.6)
ax_ts.plot(sequence, valid_df['fv_book_ekf_ou'], linewidth=1.3, label='EKF-OU Fair Value', color='steelblue')
ax_ts.set_title('Osmium Fair Value: Volumetric vs EKF-OU Filtered', fontsize=12, fontweight='bold')
ax_ts.set_ylabel('Fair Value')
ax_ts.grid(True, alpha=0.3)
ax_ts.legend(loc='best')

# Middle: Distribution comparison
ax_hist = axes[1]
ax_hist.hist(valid_df['fv_book_volumetric'], bins=50, alpha=0.5, color='lightcoral', edgecolor='darkred', label='Volumetric')
ax_hist.hist(valid_df['fv_book_ekf_ou'], bins=50, alpha=0.5, color='steelblue', edgecolor='darkblue', label='EKF-OU')
ax_hist.set_title('Distribution: Volumetric vs EKF-OU Fair Value', fontsize=12, fontweight='bold')
ax_hist.set_ylabel('Frequency')
ax_hist.grid(True, alpha=0.3, axis='y')
ax_hist.legend(loc='best')

# Bottom: Reversion factor trajectory
ax_phi = axes[2]
ax_phi.plot(sequence, valid_df['phi_estimate'], color='darkgreen', linewidth=1.1)
ax_phi.axhline(1.0, color='black', linestyle='--', linewidth=1.0, alpha=0.7)
ax_phi.set_title('Estimated OU Reversion Factor (phi) Over Time', fontsize=12, fontweight='bold')
ax_phi.set_xlabel('Observation Index')
ax_phi.set_ylabel('phi')
ax_phi.grid(True, alpha=0.3)

fig.suptitle('Osmium Extended Kalman Filter (OU State)', fontsize=15, fontweight='bold', y=0.995)  # type: ignore[reportUnknownMemberType]
plt.tight_layout()
fig.savefig('osmium_fair_value_ekf_ou.png', dpi=1000, bbox_inches='tight')  # type: ignore[reportUnknownMemberType]
print("Plot saved as 'osmium_fair_value_ekf_ou.png'")


plt.show(block=True)
