# render an AuditResult: ascii tables to stdout, and clean matplotlib plots.
# plots: (1) per-group skew bars vs budget, (2) impedance-vs-length scatter
# with the critical-length line and the target band.

import os
from .audit import OK, WARN, FAIL

TAG = {OK: "ok  ", WARN: "WARN", FAIL: "FAIL"}


def text(res):
    out = []
    p = out.append
    p("=" * 66)
    p("SI audit: %s" % res.board)
    p("critical length @ this edge rate: %.1f mm (impedance matters above this)" % res.crit_len_mm)
    p("=" * 66)
    p("\nclass targets (derived from stackup):")
    for name, (w, z) in res.class_targets.items():
        wtxt = ("%.3f mm" % w) if w else "n/a"
        ztxt = ("Z0 %.0f ohm" % z) if z else "impedance not applicable"
        p("  %-13s width %-9s %s" % (name, wtxt, ztxt))

    for g in res.groups:
        p("\n----- %s  (%.0f MHz, period %.0f ps, skew budget %.0f ps, target %.0f ohm) -----"
          % (g.name, g.clock_mhz, g.period_ps, g.budget_ps, g.z_target))
        p("  %-26s %8s %6s %9s %5s  %s" % ("net", "len_mm", "Z0", "skew_ps", "vias", "status"))
        for n, ln, z0, skew, vias, s in g.rows:
            p("  %-26s %8.1f %6.0f %9.0f %5d  %s" % (n[:26], ln, z0, skew, vias, TAG[s]))

    longbad = [r for r in res.nets if r.electrically_long and r.sev]
    p("\n----- electrically-long nets off target (%d) -----" % len(longbad))
    p("  %-26s %-11s %8s %6s %6s %5s  %s" % ("net", "class", "len_mm", "w_mm", "Z0", "vias", "flag"))
    for r in (longbad or []):
        p("  %-26s %-11s %8.1f %6.3f %6.0f %5d  %s | %s" % (
            r.name[:26], r.cls, r.length_mm, r.width_mm, r.z0, r.vias,
            TAG[r.sev], "; ".join(r.reasons)))
    if not longbad:
        p("  (none)")

    nfail = sum(1 for r in res.nets if r.sev == FAIL)
    nwarn = sum(1 for r in res.nets if r.sev == WARN)
    p("\noverall: %d FAIL, %d WARN, %d nets audited" % (nfail, nwarn, len(res.nets)))
    return "\n".join(out)


def plots(res, outdir):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    os.makedirs(outdir, exist_ok=True)
    col = {OK: "#2ca02c", WARN: "#e8a33d", FAIL: "#d62728"}
    written = []

    # 1. skew bars per group
    if res.groups:
        fig, axs = plt.subplots(1, len(res.groups), figsize=(6 * len(res.groups), 7), squeeze=False)
        for ax, g in zip(axs[0], res.groups):
            rows = g.rows
            skews = [r[3] for r in rows]
            cols = [col[r[5]] for r in rows]
            ax.barh(range(len(rows)), skews, color=cols)
            ax.set_yticks(range(len(rows)))
            ax.set_yticklabels([r[0].split("/")[-1] for r in rows], fontsize=7)
            ax.axvline(g.budget_ps, ls="--", c="#d62728", lw=1)
            ax.axvline(-g.budget_ps, ls="--", c="#d62728", lw=1)
            ax.axvline(0, c="#888", lw=0.8)
            ax.set_title("%s skew (budget +/-%.0f ps)" % (g.name, g.budget_ps), fontsize=10)
            ax.set_xlabel("skew vs reference, ps")
            ax.invert_yaxis()
        fig.suptitle("%s  intra-bus skew" % res.board)
        fig.tight_layout()
        f = os.path.join(outdir, "%s_skew.png" % res.board)
        fig.savefig(f, dpi=120)
        plt.close(fig)
        written.append(f)

    # 2. impedance vs length scatter
    fig, ax = plt.subplots(figsize=(10, 7))
    imp_nets = [r for r in res.nets if r.z0 > 0]
    for r in imp_nets:
        ax.scatter(r.length_mm, r.z0, c=col[r.sev], s=28, zorder=3)
    ax.axvline(res.crit_len_mm, ls="--", c="#888", label="critical length %.0f mm" % res.crit_len_mm)
    tgt = 50.0
    ax.axhspan(tgt * 0.9, tgt * 1.1, color="#2ca02c", alpha=0.12, label="50 ohm +/-10%")
    ax.axhline(tgt, color="#2ca02c", lw=0.8)
    ax.set_xlabel("routed length (mm)")
    ax.set_ylabel("Z0 from routed width (ohm)")
    ax.set_title("%s  impedance vs length  (right of dashed line = impedance matters)" % res.board)
    ax.legend(loc="best", fontsize=8)
    ax.grid(alpha=0.2)
    fig.tight_layout()
    f = os.path.join(outdir, "%s_impedance.png" % res.board)
    fig.savefig(f, dpi=120)
    plt.close(fig)
    written.append(f)
    return written
