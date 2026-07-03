/* Small UI utilities: DOM helpers, formatters, icons, toasts, modals. */
const UI = (() => {
  const el = (id) => document.getElementById(id);

  function h(html) {
    const t = document.createElement("template");
    t.innerHTML = html.trim();
    return t.content.firstElementChild;
  }
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  // ---- formatting ----
  // Active currency, driven by the logged-in user's base_currency. Defaults to
  // INR (₹) since the app is India/MCX-oriented.
  const CURRENCY_SYMBOLS = { INR: "₹", USD: "$", EUR: "€", GBP: "£", JPY: "¥", AUD: "A$", CAD: "C$" };
  const CURRENCY_LOCALE = { INR: "en-IN", USD: "en-US" };
  let currencyCode = "INR";
  let currencySymbol = "₹";
  function setCurrency(code) {
    currencyCode = (code && CURRENCY_SYMBOLS[code]) ? code : "INR";
    currencySymbol = CURRENCY_SYMBOLS[currencyCode];
  }
  function money(v, dp = 2) {
    if (v == null || v === "" || isNaN(v)) return "—";
    const n = Number(v);
    const sign = n < 0 ? "-" : "";
    const locale = CURRENCY_LOCALE[currencyCode] || undefined;
    return sign + currencySymbol + Math.abs(n).toLocaleString(locale, { minimumFractionDigits: dp, maximumFractionDigits: dp });
  }
  function signed(v) {
    if (v == null || isNaN(v)) return "—";
    const n = Number(v);
    return (n > 0 ? "+" : "") + money(n);
  }
  function pct(v, dp = 1) {
    if (v == null || isNaN(v)) return "—";
    return Number(v).toFixed(dp) + "%";
  }
  function num(v, dp = 2) {
    if (v == null || isNaN(v)) return "—";
    return Number(v).toFixed(dp);
  }
  function cls(v) { return Number(v) > 0 ? "pos" : Number(v) < 0 ? "neg" : ""; }
  function date(s) { return s ? String(s).slice(0, 10) : "—"; }
  function datetime(s) { return s ? String(s).slice(0, 16).replace("T", " ") : "—"; }
  function initials(name) {
    return (name || "?").split(" ").map((w) => w[0]).slice(0, 2).join("").toUpperCase();
  }

  // ---- icons (inline svg, 24x24 stroke) ----
  const ICONS = {
    dashboard: '<path d="M3 13h8V3H3v10zm0 8h8v-6H3v6zm10 0h8V11h-8v10zm0-18v6h8V3h-8z"/>',
    trades: '<path d="M3 3v18h18M7 15l4-4 3 3 5-6" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
    calendar: '<rect x="3" y="4" width="18" height="17" rx="2" fill="none" stroke="currentColor" stroke-width="2"/><path d="M3 9h18M8 2v4M16 2v4" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>',
    analytics: '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>',
    coach: '<path d="M12 2a7 7 0 0 0-4 12.7V17a2 2 0 0 0 2 2h4a2 2 0 0 0 2-2v-2.3A7 7 0 0 0 12 2zM9 22h6" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
    goals: '<circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="2"/><circle cx="12" cy="12" r="5" fill="none" stroke="currentColor" stroke-width="2"/><circle cx="12" cy="12" r="1.5"/>',
    plus: '<path d="M12 5v14M5 12h14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>',
    upload: '<path d="M12 16V4m0 0L7 9m5-5 5 5M4 20h16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
    edit: '<path d="M12 20h9M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4 12.5-12.5z" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
    trash: '<path d="M3 6h18M8 6V4h8v2m-9 0v14a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1V6" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
    logout: '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
    check: '<path d="M20 6 9 17l-5-5" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>',
    alert: '<path d="M12 9v4m0 4h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
    menu: '<path d="M3 6h18M3 12h18M3 18h18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>',
    dollar: '<text x="12" y="18" font-size="18" text-anchor="middle" font-weight="700" font-family="system-ui, sans-serif" fill="currentColor">₹</text>',
    trophy: '<path d="M8 21h8m-4-4v4M6 4h12v4a6 6 0 0 1-12 0V4zM6 6H3v2a3 3 0 0 0 3 3M18 6h3v2a3 3 0 0 1-3 3" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
  };
  function icon(name) {
    const body = ICONS[name] || "";
    const fillRule = body.includes("stroke=") ? "" : 'fill="currentColor"';
    return `<svg viewBox="0 0 24 24" ${fillRule} xmlns="http://www.w3.org/2000/svg">${body}</svg>`;
  }

  // ---- toast ----
  function toast(msg, type = "ok") {
    let wrap = document.querySelector(".toast-wrap");
    if (!wrap) { wrap = h('<div class="toast-wrap"></div>'); document.body.appendChild(wrap); }
    const t = h(`<div class="toast ${type === "err" ? "err" : ""}">${esc(msg)}</div>`);
    wrap.appendChild(t);
    setTimeout(() => { t.style.opacity = "0"; t.style.transition = "opacity .3s"; setTimeout(() => t.remove(), 300); }, 3200);
  }

  // ---- modal ----
  function modal(title, bodyHtml, footHtml = "", opts = {}) {
    close();
    const overlay = h(`
      <div class="modal-overlay">
        <div class="modal ${opts.wide ? "wide" : ""}">
          <div class="modal-head"><h3>${esc(title)}</h3><button class="x-btn" data-close>&times;</button></div>
          <div class="modal-body">${bodyHtml}</div>
          ${footHtml ? `<div class="modal-foot">${footHtml}</div>` : ""}
        </div>
      </div>`);
    overlay.addEventListener("mousedown", (e) => { if (e.target === overlay) close(); });
    overlay.querySelectorAll("[data-close]").forEach((b) => b.addEventListener("click", close));
    document.body.appendChild(overlay);
    return overlay;
  }
  function close() {
    const m = document.querySelector(".modal-overlay");
    if (m) m.remove();
  }
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") close(); });

  function confirm(msg, onYes) {
    modal("Please confirm",
      `<p style="color:var(--text-dim)">${esc(msg)}</p>`,
      `<button class="btn btn-ghost" data-close>Cancel</button><button class="btn btn-primary" id="cf-yes">Confirm</button>`);
    el("cf-yes").addEventListener("click", () => { close(); onYes(); });
  }

  return { el, h, esc, money, signed, pct, num, cls, date, datetime, initials, icon, toast, modal, close, confirm, setCurrency, curSym: () => currencySymbol };
})();
