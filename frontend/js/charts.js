/* Chart.js wrappers. Everything degrades gracefully if Chart.js failed to load
   (offline) — the app still works, charts just show a note. */
const Charts = (() => {
  const registry = {};
  const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();

  function available() { return typeof Chart !== "undefined"; }

  function destroy(id) {
    if (registry[id]) { registry[id].destroy(); delete registry[id]; }
  }

  function guard(canvasId) {
    const cv = document.getElementById(canvasId);
    if (!cv) return null;
    if (!available()) {
      const box = cv.parentElement;
      box.innerHTML = '<div class="empty"><p class="faint">Charts need an internet connection (Chart.js CDN).</p></div>';
      return null;
    }
    return cv.getContext("2d");
  }

  function equityCurve(canvasId, points) {
    const ctx = guard(canvasId);
    if (!ctx) return;
    destroy(canvasId);
    const green = css("--accent");
    const labels = points.map((p, i) => p.date || i + 1);
    const data = points.map((p) => p.equity);
    const grad = ctx.createLinearGradient(0, 0, 0, 300);
    grad.addColorStop(0, "rgba(45,212,167,0.28)");
    grad.addColorStop(1, "rgba(45,212,167,0.0)");
    registry[canvasId] = new Chart(ctx, {
      type: "line",
      data: { labels, datasets: [{
        data, borderColor: green, backgroundColor: grad, fill: true,
        borderWidth: 2, tension: 0.25, pointRadius: 0, pointHoverRadius: 5,
        pointHoverBackgroundColor: green,
      }] },
      options: baseOpts({ money: true }),
    });
  }

  function barPnl(canvasId, labels, values) {
    const ctx = guard(canvasId);
    if (!ctx) return;
    destroy(canvasId);
    const green = css("--green"), red = css("--red");
    registry[canvasId] = new Chart(ctx, {
      type: "bar",
      data: { labels, datasets: [{
        data: values,
        backgroundColor: values.map((v) => (v >= 0 ? "rgba(52,211,153,.75)" : "rgba(248,113,113,.75)")),
        borderColor: values.map((v) => (v >= 0 ? green : red)),
        borderWidth: 1, borderRadius: 5,
      }] },
      options: baseOpts({ money: true }),
    });
  }

  function donut(canvasId, wins, losses) {
    const ctx = guard(canvasId);
    if (!ctx) return;
    destroy(canvasId);
    registry[canvasId] = new Chart(ctx, {
      type: "doughnut",
      data: { labels: ["Wins", "Losses"], datasets: [{
        data: [wins, losses], backgroundColor: [css("--green"), css("--red")],
        borderColor: css("--panel"), borderWidth: 3, hoverOffset: 4,
      }] },
      options: {
        cutout: "70%", responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false } },
      },
    });
  }

  function baseOpts({ money }) {
    const grid = "rgba(255,255,255,0.05)";
    const tick = css("--text-faint");
    return {
      responsive: true, maintainAspectRatio: false,
      interaction: { intersect: false, mode: "index" },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: css("--panel-2"), borderColor: css("--border-2"), borderWidth: 1,
          titleColor: css("--text"), bodyColor: css("--text-dim"), padding: 10, displayColors: false,
          callbacks: money ? { label: (c) => "$" + Number(c.raw).toLocaleString(undefined, { maximumFractionDigits: 2 }) } : {},
        },
      },
      scales: {
        x: { grid: { display: false }, ticks: { color: tick, maxRotation: 0, autoSkip: true, maxTicksLimit: 8, font: { size: 11 } } },
        y: { grid: { color: grid }, ticks: { color: tick, font: { size: 11 },
          callback: (v) => (money ? "$" + Number(v).toLocaleString(undefined, { notation: "compact" }) : v) } },
      },
    };
  }

  return { equityCurve, barPnl, donut, destroy, available };
})();
