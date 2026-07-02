import csv
import random
import argparse
from .gfi import TARGET_GFI

FUELS = ["VLSFO", "LNG", "Bio-methanol", "Ammonia", "MGO"]


def generate(path: str, ships: int, months: int, seed: int = 42):
    random.seed(seed)
    rows = []
    for i in range(ships):
        imo = f"IMO{9000000 + i}"
        # 約三成船隊是綠色燃料、會超額；其餘傳統燃料多為缺額
        green = random.random() < 0.3
        for m in range(1, months + 1):
            if green:
                fuel = random.choice(["Bio-methanol", "LNG", "Ammonia"])
                attained = random.uniform(0.55, 0.92) * TARGET_GFI  # 低於目標＝超額
            else:
                fuel = random.choice(["VLSFO", "MGO"])
                attained = random.uniform(1.02, 1.25) * TARGET_GFI  # 高於目標＝缺額
            rows.append({
                "ship_id": imo,
                "reporting_period": f"2028-{m:02d}",
                "attained_gfi": round(attained, 2),
                "energy_mj": random.randint(80_000_000, 240_000_000),
                "fuel": fuel,
            })
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"寫入 {len(rows)} 筆（{ships} 船 × {months} 月）→ {path}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/out/fleet.csv")
    ap.add_argument("--ships", type=int, default=30)
    ap.add_argument("--months", type=int, default=12)
    generate(ap.parse_args().out, ap.parse_args().ships, ap.parse_args().months)
