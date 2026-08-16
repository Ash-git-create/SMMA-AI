"""Render the discrete-time SIR update rules as a typeset equation image."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path

OUT = Path(r"D:/Master Thesis/SMMA_AI_Systems/docs/figures")
OUT.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({"mathtext.fontset": "cm"})

fig, ax = plt.subplots(figsize=(6.2, 2.3))
ax.axis("off")
lines = [
    r"$S_{t+1} = S_t - \beta\, S_t I_t / N$",
    r"$I_{t+1} = I_t + \beta\, S_t I_t / N - \gamma\, I_t$",
    r"$R_{t+1} = R_t + \gamma\, I_t$",
    r"$R_0 = \beta / \gamma$",
]
ys = [0.88, 0.64, 0.40, 0.12]
for text, y in zip(lines, ys):
    ax.text(0.5, y, text, ha="center", va="center", fontsize=16, color="#222222")
fig.tight_layout()
for ext in ("png", "pdf"):
    fig.savefig(OUT / f"fig_sir_equations.{ext}", dpi=200, bbox_inches="tight")
plt.close(fig)
print("wrote fig_sir_equations (png+pdf)")
