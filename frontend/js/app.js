/* Trade Journal Pro — SPA controller.
   Handles auth, onboarding, routing, and every view. */
(() => {
  const { el, h, esc, money, signed, pct, num, cls, date, datetime, initials, icon, toast, modal, close, confirm } = UI;
  const app = document.getElementById("app");
  let user = null;

  const NAV = [
    { id: "dashboard", label: "Dashboard", icon: "dashboard" },
    { id: "trades", label: "Trade Log", icon: "trades" },
    { id: "calendar", label: "Calendar", icon: "calendar" },
    { id: "analytics", label: "Analytics", icon: "analytics" },
    { id: "coach", label: "AI Coach", icon: "coach" },
    { id: "goals", label: "Goals & Habits", icon: "goals" },
  ];

  const INSTRUMENTS = ["equity", "option", "future", "commodity", "crypto", "forex"];

  // MCX (India) commodity contracts → P&L multiplier (contract's underlying
  // quantity expressed in the price-quotation unit). Symbol list is the full
  // set of live MCX futures; multipliers are from MCX contract specs and can be
  // overridden per trade. Source of symbols: Zerodha Kite public instruments dump.
  const MCX_MULT = {
    GOLD: 100, GOLDM: 10, GOLDGUINEA: 1, GOLDPETAL: 1, GOLDTEN: 1,
    SILVER: 30, SILVERM: 5, SILVERMIC: 1, SILVER100: 1,
    CRUDEOIL: 100, CRUDEOILM: 10, NATURALGAS: 1250, NATGASMINI: 250,
    COPPER: 2500, ZINC: 5000, ZINCMINI: 1000, LEAD: 5000, LEADMINI: 1000,
    ALUMINIUM: 5000, ALUMINI: 1000, NICKEL: 1500, MENTHAOIL: 360, CARDAMOM: 100,
    COTTON: 25, KAPAS: 200, COTTONOIL: 200, STEELREBAR: 10, ELECDMBL: 1,
    MCXBULLDEX: 50, MCXMETLDEX: 50,
  };
  const SESSIONS = ["Pre-market", "Open", "Midday", "Power Hour", "After-hours"];
  const CONDITIONS = ["Trending", "Ranging", "Volatile"];
  const TIMEFRAMES = ["1m", "5m", "15m", "1h", "4h", "Daily", "Weekly"];
  const EMOTIONS = ["calm", "confident", "fomo", "fear", "greed", "revenge", "hesitant"];

  // ======================================================================
  // Bootstrap
  // ======================================================================
  async function init() {
    if (API.isAuthed()) {
      try {
        const { user: u } = await API.me();
        user = u;
        if (!user.onboarded) return renderOnboarding();
        return renderShell();
      } catch (e) {
        API.logout();
      }
    }
    renderAuth();
  }

  // ======================================================================
  // Auth
  // ======================================================================
  function renderAuth(mode = "login") {
    app.innerHTML = `
      <div class="auth-wrap">
        <div class="auth-hero">
          <div class="brand">
            <img src="/assets/favicon.svg" class="brand-logo" alt=""/>
            <span class="brand-name">Trade Journal<span> Pro</span></span>
          </div>
          <h1>Your trades hold the<br/><span>edge.</span> We surface it.</h1>
          <p class="lede">An AI-first trading journal that turns your history into a personal coach —
            tracking performance, catching behavioral leaks, and telling you exactly what to fix next.</p>
          <div class="hero-points">
            ${heroPoint("Log a trade in under 10 seconds")}
            ${heroPoint("Dashboard: P&L, win rate, expectancy, R, drawdown")}
            ${heroPoint("AI Coach flags revenge trading, overtrading & FOMO")}
            ${heroPoint("Explainable insights — grounded in your own data")}
          </div>
        </div>
        <div class="auth-panel"><div class="auth-card" id="auth-card"></div></div>
      </div>`;
    renderAuthCard(mode);
  }
  function heroPoint(t) {
    return `<div class="hero-point"><span class="dot">${icon("check")}</span><span>${esc(t)}</span></div>`;
  }

  function renderAuthCard(mode) {
    const card = el("auth-card");
    if (mode === "login") {
      card.innerHTML = `
        <h2>Welcome back</h2>
        <p class="sub">Log in to your trading desk.</p>
        <div class="field"><label>Email</label><input id="a-email" type="email" placeholder="you@email.com" autocomplete="email"/></div>
        <div class="field"><label>Password</label><input id="a-pass" type="password" placeholder="••••••••" autocomplete="current-password"/></div>
        <div class="form-error" id="a-err"></div>
        <button class="btn btn-primary" id="a-submit" style="width:100%;justify-content:center">Log in</button>
        <div class="form-switch">No account yet? <a id="to-register">Create one</a></div>
        <div class="form-switch"><a id="to-demo" style="color:var(--text-dim)">Explore the demo account →</a></div>`;
      el("a-submit").addEventListener("click", doLogin);
      el("a-pass").addEventListener("keydown", (e) => e.key === "Enter" && doLogin());
      el("to-register").addEventListener("click", () => renderAuthCard("register"));
      el("to-demo").addEventListener("click", () => { el("a-email").value = "demo@tradejournal.pro"; el("a-pass").value = "demo1234"; doLogin(); });
    } else {
      card.innerHTML = `
        <h2>Create your account</h2>
        <p class="sub">Start journaling in seconds.</p>
        <div class="field"><label>Name</label><input id="r-name" placeholder="Alex Trader"/></div>
        <div class="field"><label>Email</label><input id="r-email" type="email" placeholder="you@email.com"/></div>
        <div class="field"><label>Password</label><input id="r-pass" type="password" placeholder="6+ characters"/></div>
        <div class="form-error" id="a-err"></div>
        <button class="btn btn-primary" id="r-submit" style="width:100%;justify-content:center">Create account</button>
        <div class="form-switch">Already have an account? <a id="to-login">Log in</a></div>`;
      el("r-submit").addEventListener("click", doRegister);
      el("r-pass").addEventListener("keydown", (e) => e.key === "Enter" && doRegister());
      el("to-login").addEventListener("click", () => renderAuthCard("login"));
    }
  }

  async function doLogin() {
    const email = el("a-email").value.trim(), password = el("a-pass").value;
    const err = el("a-err");
    if (!email || !password) { err.textContent = "Enter your email and password."; return; }
    try {
      const { token, user: u } = await API.login({ email, password });
      API.setToken(token); user = u;
      user.onboarded ? renderShell() : renderOnboarding();
    } catch (e) { err.textContent = e.error || "Login failed."; }
  }
  async function doRegister() {
    const name = el("r-name").value.trim(), email = el("r-email").value.trim(), password = el("r-pass").value;
    const err = el("a-err");
    if (!name || !email || password.length < 6) { err.textContent = "Fill every field; password 6+ chars."; return; }
    try {
      const { token, user: u } = await API.register({ name, email, password });
      API.setToken(token); user = u;
      renderOnboarding();
    } catch (e) { err.textContent = e.error || "Could not create account."; }
  }

  // ======================================================================
  // Onboarding
  // ======================================================================
  function renderOnboarding() {
    const state = { trader_type: "intraday", experience: "beginner", account_size: "", base_currency: "USD" };
    app.innerHTML = `
      <div class="auth-wrap">
        <div class="auth-hero">
          <div class="brand">
            <img src="/assets/favicon.svg" class="brand-logo" alt=""/>
            <span class="brand-name">Trade Journal<span> Pro</span></span>
          </div>
          <h1>Let's tune your<br/><span>coaching.</span></h1>
          <p class="lede">Two quick questions so your metrics, benchmarks, and AI recommendations
            fit the way you actually trade. You can change these anytime.</p>
        </div>
        <div class="auth-panel"><div class="auth-card">
          <h2>Set up your profile</h2>
          <p class="sub">Welcome, ${esc(user.name.split(" ")[0])}. This takes 20 seconds.</p>

          <div class="section-label">What do you trade most?</div>
          <div class="chips" id="ob-type"></div>

          <div class="section-label">Experience level</div>
          <div class="chips" id="ob-exp"></div>

          <div class="field-row" style="margin-top:20px">
            <div class="field"><label>Account size</label><input id="ob-size" type="number" placeholder="25000"/></div>
            <div class="field"><label>Base currency</label>
              <select id="ob-cur">${["USD","EUR","GBP","INR","JPY","AUD","CAD"].map(c=>`<option>${c}</option>`).join("")}</select></div>
          </div>
          <div class="form-error" id="ob-err"></div>
          <button class="btn btn-primary" id="ob-submit" style="width:100%;justify-content:center">Enter my dashboard</button>
        </div></div>
      </div>`;

    const types = [["intraday","Intraday / Day"],["swing","Swing"],["options","Options"],["futures","Futures"],["crypto","Crypto"],["investor","Position / Investing"]];
    const exps = [["beginner","Beginner"],["intermediate","Intermediate"],["advanced","Advanced / Pro"]];
    renderChips("ob-type", types, state.trader_type, (v) => state.trader_type = v);
    renderChips("ob-exp", exps, state.experience, (v) => state.experience = v);

    el("ob-submit").addEventListener("click", async () => {
      state.account_size = el("ob-size").value || 0;
      state.base_currency = el("ob-cur").value;
      try {
        const { user: u } = await API.onboard(state);
        user = u; renderShell();
      } catch (e) { el("ob-err").textContent = e.error || "Something went wrong."; }
    });
  }

  function renderChips(containerId, options, active, onPick) {
    const c = el(containerId);
    c.innerHTML = options.map(([v, label]) =>
      `<button class="chip ${v === active ? "active" : ""}" data-v="${v}">${esc(label)}</button>`).join("");
    c.querySelectorAll(".chip").forEach((btn) => btn.addEventListener("click", () => {
      c.querySelectorAll(".chip").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active"); onPick(btn.dataset.v);
    }));
  }

  // ======================================================================
  // App shell + router
  // ======================================================================
  function renderShell() {
    app.innerHTML = `
      <div class="shell">
        <aside class="sidebar" id="sidebar">
          <div class="brand">
            <img src="/assets/favicon.svg" class="brand-logo" alt=""/>
            <span class="brand-name">Trade Journal<span> Pro</span></span>
          </div>
          <nav class="nav" id="nav">
            ${NAV.map((n) => `
              <a class="nav-item" data-route="${n.id}">${icon(n.icon)}<span>${n.label}</span></a>`).join("")}
          </nav>
          <div class="sidebar-foot">
            <div class="user-row">
              <div class="avatar">${initials(user.name)}</div>
              <div class="meta"><b>${esc(user.name)}</b><small>${esc(user.trader_type || "trader")} · ${esc(user.experience||"")}</small></div>
            </div>
            <a class="nav-item" id="logout" style="margin-top:6px">${icon("logout")}<span>Log out</span></a>
          </div>
        </aside>
        <div class="main">
          <header class="topbar">
            <div style="display:flex;align-items:center;gap:12px">
              <button class="btn btn-ghost btn-sm menu-toggle" id="menu-toggle" style="padding:6px">${icon("menu")}</button>
              <div><h1 id="page-title">Dashboard</h1><div class="page-sub" id="page-sub"></div></div>
            </div>
            <div class="topbar-actions">
              <button class="btn btn-sm" id="btn-import">${icon("upload")} Import CSV</button>
              <button class="btn btn-primary btn-sm" id="btn-add">${icon("plus")} Log Trade</button>
            </div>
          </header>
          <main class="content" id="content"><div class="spinner"></div></main>
        </div>
      </div>`;

    el("nav").querySelectorAll(".nav-item").forEach((a) =>
      a.addEventListener("click", () => { location.hash = "#/" + a.dataset.route; }));
    el("logout").addEventListener("click", () => { API.logout(); location.hash = ""; user = null; renderAuth(); });
    el("btn-add").addEventListener("click", () => tradeModal());
    el("btn-import").addEventListener("click", importModal);
    el("menu-toggle").addEventListener("click", () => el("sidebar").classList.toggle("open"));

    window.addEventListener("hashchange", router);
    if (!location.hash) location.hash = "#/dashboard";
    else router();
  }

  const ROUTES = {
    dashboard: { title: "Dashboard", sub: "Your trading performance at a glance", fn: viewDashboard },
    trades: { title: "Trade Log", sub: "Every trade, enriched with P&L and R-multiple", fn: viewTrades },
    calendar: { title: "Calendar", sub: "Daily P&L heatmap", fn: viewCalendar },
    analytics: { title: "Analytics", sub: "Compare performance across strategies and conditions", fn: viewAnalytics },
    coach: { title: "AI Coach", sub: "Explainable, data-driven behavioral insights", fn: viewCoach },
    goals: { title: "Goals & Habits", sub: "Build disciplined, measurable routines", fn: viewGoals },
  };

  function router() {
    const route = (location.hash.replace("#/", "") || "dashboard").split("?")[0];
    const def = ROUTES[route] || ROUTES.dashboard;
    document.querySelectorAll("#nav .nav-item").forEach((a) =>
      a.classList.toggle("active", a.dataset.route === route));
    el("page-title").textContent = def.title;
    el("page-sub").textContent = def.sub;
    el("sidebar").classList.remove("open");
    el("content").innerHTML = '<div class="spinner"></div>';
    def.fn().catch((e) => {
      el("content").innerHTML = `<div class="empty"><div class="big">⚠️</div><h3>Couldn't load this view</h3><p>${esc(e.error||e.message||"")}</p></div>`;
    });
  }

  // ======================================================================
  // Dashboard
  // ======================================================================
  async function viewDashboard() {
    const { metrics: m, equity_curve, recent } = await API.dashboard();
    const c = el("content");
    if (m.total_trades === 0) return emptyState(c, "No trades yet", "Log your first trade or import a CSV to light up your dashboard.");

    const cur = user.base_currency || "USD";
    c.innerHTML = `
      <div class="grid kpi-grid" style="margin-bottom:16px">
        ${kpi("Net P&L", signed(m.net_pnl), cls(m.net_pnl), `${m.closed_trades} closed trades`, "dollar")}
        ${kpi("Win Rate", pct(m.win_rate), m.win_rate>=50?"pos":"", `${m.wins}W / ${m.losses}L`, "trophy")}
        ${kpi("Profit Factor", m.profit_factor==null?"∞":num(m.profit_factor), m.profit_factor>=1.5?"pos":m.profit_factor<1?"neg":"", "gross win ÷ gross loss", "analytics")}
        ${kpi("Expectancy", signed(m.expectancy), cls(m.expectancy), "avg $ per trade", "coach")}
      </div>
      <div class="grid kpi-grid" style="margin-bottom:20px">
        ${kpi("Avg R", m.avg_r==null?"—":num(m.avg_r), m.avg_r>0?"pos":m.avg_r<0?"neg":"", "reward-to-risk", "trades")}
        ${kpi("Max Drawdown", money(m.max_drawdown), "neg", "peak-to-trough", "analytics")}
        ${kpi("Best / Worst", signed(m.best_trade), "pos", `worst ${signed(m.worst_trade)}`, "trades")}
        ${kpi("Open Positions", String(m.open_trades), "", `${m.total_trades} total logged`, "calendar")}
      </div>

      <div class="grid two-col" style="margin-bottom:20px">
        <div class="card">
          <div class="card-head"><h3>Equity Curve</h3><span class="hint">cumulative P&L over ${equity_curve.length} closed trades</span></div>
          <div class="chart-box"><canvas id="eq-chart"></canvas></div>
        </div>
        <div class="card">
          <div class="card-head"><h3>Win / Loss</h3></div>
          <div class="chart-box sm" style="height:180px"><canvas id="wl-chart"></canvas></div>
          <div style="display:flex;justify-content:center;gap:24px;margin-top:14px">
            <div class="center"><div class="mono" style="font-size:20px;font-weight:700" class="pos">${m.wins}</div><small class="faint">Wins</small></div>
            <div class="center"><div class="mono pos" style="font-size:20px;font-weight:700;color:var(--green)">${pct(m.win_rate)}</div><small class="faint">Win rate</small></div>
            <div class="center"><div class="mono" style="font-size:20px;font-weight:700;color:var(--red)">${m.losses}</div><small class="faint">Losses</small></div>
          </div>
        </div>
      </div>

      <div class="card">
        <div class="card-head"><h3>Recent Trades</h3><a class="btn btn-ghost btn-sm" data-goto="trades">View all →</a></div>
        ${tradeTable(recent)}
      </div>`;

    Charts.equityCurve("eq-chart", equity_curve);
    Charts.donut("wl-chart", m.wins, m.losses);
    c.querySelectorAll("[data-goto]").forEach((a)=>a.addEventListener("click",()=>location.hash="#/"+a.dataset.goto));
    bindTradeRowActions(c);
  }

  function kpi(label, value, valClass, foot, ic) {
    return `<div class="kpi">
      <div class="k-icon">${icon(ic)}</div>
      <div class="k-label">${esc(label)}</div>
      <div class="k-value ${valClass}">${value}</div>
      <div class="k-foot">${esc(foot)}</div>
    </div>`;
  }

  // ======================================================================
  // Trades
  // ======================================================================
  let allTrades = [];
  async function viewTrades() {
    const { trades } = await API.trades();
    allTrades = trades;
    const c = el("content");
    if (!trades.length) return emptyState(c, "No trades logged", "Click “Log Trade” or import a broker CSV to get started.");

    const strategies = [...new Set(trades.map((t) => t.strategy).filter(Boolean))];
    c.innerHTML = `
      <div class="filter-bar">
        <select id="f-status"><option value="">All statuses</option><option value="closed">Closed</option><option value="open">Open</option></select>
        <select id="f-strategy"><option value="">All strategies</option>${strategies.map((s)=>`<option>${esc(s)}</option>`).join("")}</select>
        <input id="f-search" placeholder="Search symbol…" style="flex:1;min-width:140px"/>
        <span class="faint" id="f-count"></span>
      </div>
      <div id="trades-table"></div>`;
    const render = () => {
      const status = el("f-status").value, strat = el("f-strategy").value, q = el("f-search").value.trim().toUpperCase();
      let list = allTrades.slice();
      if (status === "open") list = list.filter((t) => t.is_open);
      if (status === "closed") list = list.filter((t) => !t.is_open);
      if (strat) list = list.filter((t) => t.strategy === strat);
      if (q) list = list.filter((t) => (t.symbol || "").includes(q));
      el("f-count").textContent = `${list.length} trade${list.length !== 1 ? "s" : ""}`;
      el("trades-table").innerHTML = tradeTable(list, true);
      bindTradeRowActions(el("trades-table"));
    };
    ["f-status", "f-strategy"].forEach((id) => el(id).addEventListener("change", render));
    el("f-search").addEventListener("input", render);
    render();
  }

  function tradeTable(trades, full = false) {
    if (!trades.length) return `<div class="empty"><p class="faint">No trades match.</p></div>`;
    return `<div class="table-wrap"><table>
      <thead><tr>
        <th>Symbol</th><th>Side</th><th>Qty</th><th>Entry</th><th>Exit</th>
        <th>P&L</th><th>R</th>${full ? "<th>Strategy</th><th>Emotion</th>" : ""}<th>Date</th><th></th>
      </tr></thead>
      <tbody>${trades.map((t) => tradeRow(t, full)).join("")}</tbody>
    </table></div>`;
  }

  function tradeRow(t, full) {
    const side = t.direction === "long"
      ? '<span class="pill pill-blue">LONG</span>' : '<span class="pill pill-amber">SHORT</span>';
    const pnl = t.is_open ? '<span class="pill pill-gray">OPEN</span>'
      : `<span class="${cls(t.pnl)} mono" style="font-weight:700">${signed(t.pnl)}</span>`;
    const r = t.r_multiple == null ? '<span class="faint">—</span>'
      : `<span class="${cls(t.r_multiple)} mono">${num(t.r_multiple, 2)}R</span>`;
    const emo = t.emotion ? `<span class="tag">${esc(t.emotion)}</span>` : "";
    return `<tr data-id="${t.id}">
      <td class="t-sym">${esc(t.symbol)} <small class="faint">${esc(t.instrument||"")}</small></td>
      <td>${side}</td>
      <td class="mono">${num(t.quantity, 0)}${t.multiplier && t.multiplier != 1 ? ` <span class="faint">×${t.multiplier}</span>` : ""}</td>
      <td class="mono">${money(t.entry_price)}</td>
      <td class="mono">${t.exit_price==null?'<span class="faint">—</span>':money(t.exit_price)}</td>
      <td>${pnl}</td>
      <td>${r}</td>
      ${full ? `<td>${t.strategy?`<span class="tag">${esc(t.strategy)}</span>`:'<span class="faint">—</span>'}</td><td>${emo||'<span class="faint">—</span>'}</td>` : ""}
      <td class="faint mono">${date(t.entry_time)}</td>
      <td><div class="row-actions">
        <button class="btn btn-ghost btn-sm" data-edit="${t.id}" title="Edit">${icon("edit")}</button>
        <button class="btn btn-ghost btn-sm" data-del="${t.id}" title="Delete">${icon("trash")}</button>
      </div></td>
    </tr>`;
  }

  function bindTradeRowActions(scope) {
    scope.querySelectorAll("[data-edit]").forEach((b) => b.addEventListener("click", (e) => {
      e.stopPropagation();
      const t = allTrades.find((x) => String(x.id) === b.dataset.edit) || null;
      if (t) tradeModal(t);
    }));
    scope.querySelectorAll("[data-del]").forEach((b) => b.addEventListener("click", (e) => {
      e.stopPropagation();
      confirm("Delete this trade permanently?", async () => {
        await API.deleteTrade(b.dataset.del);
        toast("Trade deleted"); router();
      });
    }));
  }

  // ======================================================================
  // Trade modal (add / edit)
  // ======================================================================
  function tradeModal(t = null) {
    const editing = !!t;
    t = t || {};
    const nowLocal = new Date().toISOString().slice(0, 16);
    const sel = (opts, val) => opts.map((o) => `<option ${o===val?"selected":""}>${esc(o)}</option>`).join("");
    const body = `
      <div class="section-label">Position</div>
      <div class="field-row-3">
        <div class="field"><label>Symbol *</label><input id="tm-symbol" value="${esc(t.symbol||"")}" placeholder="AAPL / GOLD" list="dl-mcx" autocomplete="off"/>
          <datalist id="dl-mcx">${Object.keys(MCX_MULT).map((s)=>`<option>${s}</option>`).join("")}</datalist></div>
        <div class="field"><label>Instrument</label><select id="tm-instrument">${sel(INSTRUMENTS, t.instrument||"equity")}</select></div>
        <div class="field"><label>Direction</label><select id="tm-direction"><option value="long" ${t.direction!=="short"?"selected":""}>Long</option><option value="short" ${t.direction==="short"?"selected":""}>Short</option></select></div>
      </div>
      <div class="field-row-3">
        <div class="field"><label>Quantity *</label><input id="tm-qty" type="number" step="any" value="${t.quantity??""}" placeholder="100"/></div>
        <div class="field"><label>Entry price *</label><input id="tm-entry" type="number" step="any" value="${t.entry_price??""}" placeholder="187.20"/></div>
        <div class="field"><label>Exit price</label><input id="tm-exit" type="number" step="any" value="${t.exit_price??""}" placeholder="blank = open"/></div>
      </div>
      <div class="field-row-3">
        <div class="field"><label>Stop (for R)</label><input id="tm-stop" type="number" step="any" value="${t.stop_price??""}" placeholder="185.90"/></div>
        <div class="field"><label>Fees</label><input id="tm-fees" type="number" step="any" value="${t.fees??""}" placeholder="1.00"/></div>
        <div class="field"><label>Contract multiplier <span class="faint" id="tm-mult-hint" style="font-weight:400"></span></label><input id="tm-mult" type="number" step="any" value="${t.multiplier??1}" placeholder="1"/></div>
      </div>
      <div class="field-row-3">
        <div class="field"><label>Entry time *</label><input id="tm-etime" type="datetime-local" value="${(t.entry_time||nowLocal).slice(0,16)}"/></div>
        <div class="field"><label>Exit time</label><input id="tm-xtime" type="datetime-local" value="${t.exit_time?t.exit_time.slice(0,16):""}"/></div>
        <div class="field"><label>Execution rating</label><div class="rating-stars" id="tm-rating"></div></div>
      </div>

      <div class="section-label">Context</div>
      <div class="field-row-3">
        <div class="field"><label>Strategy</label><input id="tm-strategy" value="${esc(t.strategy||"")}" placeholder="Breakout" list="dl-strat"/>
          <datalist id="dl-strat"><option>Breakout</option><option>Pullback</option><option>VWAP Reversion</option><option>Trend Follow</option><option>Gap & Go</option><option>Mean Reversion</option></datalist></div>
        <div class="field"><label>Setup</label><input id="tm-setup" value="${esc(t.setup||"")}" placeholder="Bull Flag"/></div>
        <div class="field"><label>Timeframe</label><select id="tm-tf"><option value=""></option>${sel(TIMEFRAMES, t.timeframe||"")}</select></div>
      </div>
      <div class="field-row-3">
        <div class="field"><label>Market condition</label><select id="tm-cond"><option value=""></option>${sel(CONDITIONS, t.market_condition||"")}</select></div>
        <div class="field"><label>Session</label><select id="tm-session"><option value=""></option>${sel(SESSIONS, t.session||"")}</select></div>
        <div class="field"><label>Emotion</label><select id="tm-emotion"><option value=""></option>${sel(EMOTIONS, t.emotion||"")}</select></div>
      </div>

      <div class="section-label">Journal</div>
      <div class="field"><label>Pre-trade plan</label><textarea id="tm-pre" placeholder="Why are you taking this trade? Where's your stop and target?">${esc(t.pre_notes||"")}</textarea></div>
      <div class="field"><label>Post-trade review</label><textarea id="tm-post" placeholder="Did you execute the plan? What would you do differently?">${esc(t.post_notes||"")}</textarea></div>
      <div class="form-error" id="tm-err"></div>`;

    const foot = `<button class="btn btn-ghost" data-close>Cancel</button>
      <button class="btn btn-primary" id="tm-save">${editing ? "Save changes" : "Log trade"}</button>`;
    modal(editing ? "Edit trade" : "Log a trade", body, foot, { wide: true });

    // rating stars
    let rating = t.rating || 0;
    const rEl = el("tm-rating");
    const drawStars = () => { rEl.innerHTML = [1,2,3,4,5].map((i)=>`<span class="star ${i<=rating?"on":""}" data-r="${i}">★</span>`).join("");
      rEl.querySelectorAll(".star").forEach((s)=>s.addEventListener("click",()=>{rating=+s.dataset.r;drawStars();})); };
    drawStars();

    // auto-fill contract multiplier from the MCX table for commodity/future
    // symbols (always editable afterwards).
    const applyMult = () => {
      const sym = (el("tm-symbol").value || "").trim().toUpperCase();
      const inst = el("tm-instrument").value;
      const hint = el("tm-mult-hint");
      if ((inst === "commodity" || inst === "future") && MCX_MULT[sym] != null) {
        el("tm-mult").value = MCX_MULT[sym];
        hint.textContent = `· MCX ${sym} = ${MCX_MULT[sym]}`;
      } else {
        hint.textContent = "";
      }
    };
    el("tm-symbol").addEventListener("change", applyMult);
    el("tm-instrument").addEventListener("change", applyMult);
    if (!editing) applyMult();

    el("tm-save").addEventListener("click", async () => {
      const g = (id) => el(id).value;
      const payload = {
        symbol: g("tm-symbol").trim(), instrument: g("tm-instrument"), direction: g("tm-direction"),
        quantity: g("tm-qty"), entry_price: g("tm-entry"), exit_price: g("tm-exit") || null,
        stop_price: g("tm-stop") || null, fees: g("tm-fees") || 0, multiplier: g("tm-mult") || 1,
        entry_time: g("tm-etime"), exit_time: g("tm-xtime") || null,
        strategy: g("tm-strategy"), setup: g("tm-setup"), timeframe: g("tm-tf"),
        market_condition: g("tm-cond"), session: g("tm-session"), emotion: g("tm-emotion"),
        pre_notes: g("tm-pre"), post_notes: g("tm-post"), rating,
      };
      if (!payload.symbol || !payload.quantity || !payload.entry_price || !payload.entry_time) {
        el("tm-err").textContent = "Symbol, quantity, entry price and entry time are required."; return;
      }
      try {
        if (editing) { await API.updateTrade(t.id, payload); toast("Trade updated"); }
        else { await API.createTrade(payload); toast("Trade logged ✓"); }
        close(); router();
      } catch (e) { el("tm-err").textContent = e.error || "Could not save."; }
    });
  }

  // ======================================================================
  // CSV import
  // ======================================================================
  function importModal() {
    const body = `
      <p class="muted" style="margin-bottom:14px">Upload a CSV export from your broker (TD/thinkorswim, Interactive Brokers,
        Robinhood, Webull) or any spreadsheet. We auto-detect columns like symbol, side, quantity, price and dates.</p>
      <div class="field"><label>Choose CSV file</label><input id="im-file" type="file" accept=".csv,text/csv"/></div>
      <div class="field"><label>…or paste CSV</label><textarea id="im-text" style="min-height:120px;font-family:var(--mono);font-size:12px" placeholder="Symbol,Side,Quantity,Entry Price,Exit Price,Open Date&#10;AAPL,Buy,100,187.20,189.85,2026-06-02T09:41"></textarea></div>
      <div class="form-error" id="im-err"></div>
      <div id="im-result"></div>`;
    const foot = `<button class="btn btn-ghost" data-close>Cancel</button><button class="btn btn-primary" id="im-go">${icon("upload")} Import</button>`;
    modal("Import trades from CSV", body, foot);
    el("im-file").addEventListener("change", (e) => {
      const f = e.target.files[0]; if (!f) return;
      const r = new FileReader(); r.onload = () => el("im-text").value = r.result; r.readAsText(f);
    });
    el("im-go").addEventListener("click", async () => {
      const csv = el("im-text").value.trim();
      if (!csv) { el("im-err").textContent = "Choose a file or paste CSV first."; return; }
      try {
        const { inserted, warnings } = await API.importCsv(csv);
        el("im-result").innerHTML = `<div class="insight info" style="margin-top:12px">
          <b>Imported ${inserted} trade${inserted!==1?"s":""}.</b>
          ${warnings && warnings.length ? `<div class="muted" style="margin-top:6px">${warnings.map(esc).join("<br/>")}</div>` : ""}</div>`;
        if (inserted > 0) { toast(`Imported ${inserted} trades ✓`); setTimeout(() => { close(); router(); }, 1200); }
      } catch (e) { el("im-err").textContent = e.error || "Import failed."; }
    });
  }

  // ======================================================================
  // Calendar
  // ======================================================================
  let calMonth = new Date();
  async function viewCalendar() {
    const { daily } = await API.calendar();
    const c = el("content");
    const render = () => {
      const y = calMonth.getFullYear(), mo = calMonth.getMonth();
      const first = new Date(y, mo, 1), startDow = first.getDay();
      const days = new Date(y, mo + 1, 0).getDate();
      const monthName = calMonth.toLocaleString(undefined, { month: "long", year: "numeric" });
      let monthPnl = 0, monthTrades = 0, greenDays = 0, redDays = 0;
      let cells = "";
      for (let i = 0; i < startDow; i++) cells += `<div class="cal-cell empty"></div>`;
      for (let d = 1; d <= days; d++) {
        const key = `${y}-${String(mo+1).padStart(2,"0")}-${String(d).padStart(2,"0")}`;
        const info = daily[key];
        if (info) { monthPnl += info.pnl; monthTrades += info.trades; info.pnl>=0?greenDays++:redDays++; }
        const klass = !info ? "" : info.pnl >= 0 ? "cal-win has" : "cal-loss has";
        cells += `<div class="cal-cell ${klass}">
          <div class="d">${d}</div>
          ${info ? `<div><div class="p ${cls(info.pnl)}">${signed(info.pnl)}</div><div class="n">${info.trades} trade${info.trades!==1?"s":""}</div></div>` : ""}
        </div>`;
      }
      c.innerHTML = `
        <div class="grid three-col" style="margin-bottom:18px">
          ${kpi("Month P&L", signed(monthPnl), cls(monthPnl), monthName, "dollar")}
          ${kpi("Trading days", String(greenDays+redDays), "", `${greenDays} green / ${redDays} red`, "calendar")}
          ${kpi("Trades this month", String(monthTrades), "", "", "trades")}
        </div>
        <div class="card">
          <div class="cal-month">
            <button class="btn btn-ghost btn-sm" id="cal-prev">← Prev</button>
            <h3>${monthName}</h3>
            <button class="btn btn-ghost btn-sm" id="cal-next">Next →</button>
          </div>
          <div class="cal-grid">${["Sun","Mon","Tue","Wed","Thu","Fri","Sat"].map((d)=>`<div class="cal-head">${d}</div>`).join("")}${cells}</div>
        </div>`;
      el("cal-prev").addEventListener("click", () => { calMonth = new Date(y, mo-1, 1); render(); });
      el("cal-next").addEventListener("click", () => { calMonth = new Date(y, mo+1, 1); render(); });
    };
    render();
  }

  // ======================================================================
  // Analytics
  // ======================================================================
  async function viewAnalytics() {
    const a = await API.analytics();
    const c = el("content");
    const hasData = a.by_strategy && a.by_strategy.length;
    if (!hasData) return emptyState(c, "Not enough data", "Log some closed trades to unlock strategy comparison.");

    c.innerHTML = `
      <div class="grid two-col" style="margin-bottom:18px">
        <div class="card">
          <div class="card-head"><h3>Net P&L by Strategy</h3><span class="hint">your most and least profitable playbooks</span></div>
          ${barChartRows(a.by_strategy)}
        </div>
        <div class="card">
          <div class="card-head"><h3>Performance by Day of Week</h3></div>
          <div class="chart-box sm"><canvas id="wd-chart"></canvas></div>
        </div>
      </div>
      <div class="grid two-col" style="margin-bottom:18px">
        ${breakdownCard("By Setup", a.by_setup)}
        ${breakdownCard("By Market Condition", a.by_market_condition)}
      </div>
      <div class="grid two-col">
        ${breakdownCard("By Trading Session", a.by_session)}
        ${breakdownCard("By Instrument", a.by_instrument)}
      </div>`;

    if (a.weekday && a.weekday.length) {
      Charts.barPnl("wd-chart", a.weekday.map((w) => w.group.slice(0,3)), a.weekday.map((w) => w.net_pnl));
    }
  }

  function barChartRows(groups) {
    const max = Math.max(1, ...groups.map((g) => Math.abs(g.net_pnl)));
    return `<div class="bars">${groups.map((g) => {
      const w = Math.abs(g.net_pnl) / max * 50;
      const fill = g.net_pnl >= 0
        ? `<div class="bar-fill pos" style="width:${w}%"></div>`
        : `<div class="bar-fill neg" style="width:${w}%"></div>`;
      return `<div class="bar-row">
        <div title="${esc(g.group)}" style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(g.group)}</div>
        <div class="bar-track">${fill}<div class="bar-mid"></div></div>
        <div class="mono ${cls(g.net_pnl)}" style="text-align:right;font-weight:700">${signed(g.net_pnl)}</div>
      </div>`;
    }).join("")}</div>`;
  }

  function breakdownCard(title, groups) {
    if (!groups || !groups.length) return `<div class="card"><div class="card-head"><h3>${esc(title)}</h3></div><div class="empty"><p class="faint">No data.</p></div></div>`;
    return `<div class="card">
      <div class="card-head"><h3>${esc(title)}</h3></div>
      <div class="table-wrap"><table>
        <thead><tr><th>${esc(title.replace("By ",""))}</th><th>Trades</th><th>Win%</th><th>Net P&L</th></tr></thead>
        <tbody>${groups.map((g)=>`<tr>
          <td>${esc(g.group)}</td>
          <td class="mono">${g.trades}</td>
          <td class="mono ${g.win_rate>=50?"pos":""}">${pct(g.win_rate)}</td>
          <td class="mono ${cls(g.net_pnl)}" style="font-weight:700">${signed(g.net_pnl)}</td>
        </tr>`).join("")}</tbody>
      </table></div>
    </div>`;
  }

  // ======================================================================
  // AI Coach
  // ======================================================================
  let coachPeriod = "all";
  async function viewCoach() {
    const { report, metrics: m } = await API.coach(coachPeriod);
    const c = el("content");
    const gradeClass = { A: "grade-a", "B+": "grade-b", B: "grade-b", "C+": "grade-c", C: "grade-c", D: "grade-d", "—": "grade-c" }[report.grade] || "grade-c";

    c.innerHTML = `
      <div style="display:flex;justify-content:flex-end;margin-bottom:14px">
        <div class="seg" id="coach-period">
          <button data-p="week" class="${coachPeriod==="week"?"active":""}">7 days</button>
          <button data-p="month" class="${coachPeriod==="month"?"active":""}">30 days</button>
          <button data-p="all" class="${coachPeriod==="all"?"active":""}">All time</button>
        </div>
      </div>
      <div class="card" style="margin-bottom:18px">
        <div class="coach-hero">
          <div class="grade-badge ${gradeClass}">${report.grade}</div>
          <div>
            <div class="faint" style="text-transform:uppercase;letter-spacing:.06em;font-size:11px;font-weight:700;margin-bottom:4px">Coaching report · ${esc(report.period)}</div>
            <h2 style="font-size:20px;font-weight:700;margin-bottom:6px">${esc(report.headline)}</h2>
            <p class="muted">Your grade blends expectancy, profit factor, win rate and detected discipline leaks —
              every figure below is computed from your own trades.</p>
          </div>
        </div>
      </div>

      <div class="lists-2" style="margin-bottom:18px">
        <div class="card">
          <div class="card-head"><h3 class="pos">✓ Strengths</h3></div>
          <ul class="slist">${report.strengths.map((s)=>`<li><span class="ic pos">${icon("check")}</span><span>${esc(s)}</span></li>`).join("")}</ul>
        </div>
        <div class="card">
          <div class="card-head"><h3 style="color:var(--amber)">△ Watch-outs</h3></div>
          <ul class="slist">${report.weaknesses.map((s)=>`<li><span class="ic" style="color:var(--amber)">${icon("alert")}</span><span>${esc(s)}</span></li>`).join("")}</ul>
        </div>
      </div>

      <div class="card-head" style="margin:8px 2px 12px"><h3 style="font-size:16px">Behavioral Insights</h3>
        <span class="hint">${report.insights.length} pattern${report.insights.length!==1?"s":""} detected · ranked by impact</span></div>
      ${report.insights.length ? `<div class="grid" style="gap:14px">${report.insights.map(insightCard).join("")}</div>`
        : `<div class="card empty"><div class="big">🎯</div><h3>No behavioral leaks detected</h3><p>Keep journaling — the coach re-scans every trade you add.</p></div>`}

      <div class="card" style="margin-top:18px">
        <div class="card-head"><h3>Top recommendations this ${report.period.includes("7")?"week":report.period.includes("30")?"month":"period"}</h3></div>
        <ol style="padding-left:20px;display:grid;gap:10px">${report.recommendations.map((r)=>`<li style="color:var(--text-dim)">${esc(r)}</li>`).join("")}</ol>
      </div>`;

    el("coach-period").querySelectorAll("button").forEach((b) => b.addEventListener("click", () => {
      coachPeriod = b.dataset.p; router();
    }));
  }

  function insightCard(i) {
    const sevPill = { high: "pill-red", medium: "pill-amber", low: "pill-blue", info: "pill-green" }[i.severity] || "pill-gray";
    const impact = i.impact == null ? "" : `<span class="pill ${i.impact>=0?"pill-green":"pill-red"}">${signed(i.impact)} impact</span>`;
    return `<div class="insight ${i.severity}">
      <div class="i-head">
        <h4>${esc(i.pattern)}</h4>
        <div style="display:flex;gap:8px;align-items:center">${impact}<span class="pill ${sevPill}">${esc(i.severity)}</span></div>
      </div>
      <div class="evidence">${esc(i.evidence)}</div>
      <div class="rec"><b>Coach:</b> ${esc(i.recommendation)}</div>
    </div>`;
  }

  // ======================================================================
  // Goals & Habits
  // ======================================================================
  async function viewGoals() {
    const [{ goals }, { habits }] = await Promise.all([API.goals(), API.habits()]);
    const c = el("content");
    c.innerHTML = `
      <div class="grid two-col">
        <div>
          <div class="card-head" style="margin:0 2px 12px"><h3 style="font-size:16px">Goals</h3>
            <button class="btn btn-primary btn-sm" id="add-goal">${icon("plus")} New goal</button></div>
          <div class="grid" style="gap:12px" id="goals-list">${goals.map(goalCard).join("") || emptyInline("No goals yet — set a target to aim for.")}</div>
        </div>
        <div>
          <div class="card-head" style="margin:0 2px 12px"><h3 style="font-size:16px">Habit Tracker</h3>
            <button class="btn btn-primary btn-sm" id="add-habit">${icon("plus")} New habit</button></div>
          <div class="card"><div id="habits-list">${habits.map(habitRow).join("") || emptyInline("Track daily discipline habits here.")}</div></div>
        </div>
      </div>`;

    el("add-goal").addEventListener("click", goalModal);
    el("add-habit").addEventListener("click", async () => {
      const name = prompt("Name your habit (e.g. “Followed my trading plan”)");
      if (name) { await API.createHabit({ name }); toast("Habit added"); router(); }
    });
    c.querySelectorAll("[data-delgoal]").forEach((b) => b.addEventListener("click", () =>
      confirm("Delete this goal?", async () => { await API.deleteGoal(b.dataset.delgoal); router(); })));
    c.querySelectorAll("[data-delhabit]").forEach((b) => b.addEventListener("click", () =>
      confirm("Delete this habit?", async () => { await API.deleteHabit(b.dataset.delhabit); router(); })));
    c.querySelectorAll(".wd").forEach((w) => w.addEventListener("click", async () => {
      await API.toggleHabit(w.dataset.hid, w.dataset.date); router();
    }));
  }

  function goalCard(g) {
    const pctDone = g.target ? Math.max(0, Math.min(100, (g.current / g.target) * 100)) : 0;
    const unit = g.metric === "pnl" ? money(g.current) : g.metric === "win_rate" ? pct(g.current) : num(g.current);
    const tgt = g.metric === "pnl" ? money(g.target) : g.metric === "win_rate" ? pct(g.target) : num(g.target);
    const done = pctDone >= 100;
    return `<div class="card goal">
      <div style="display:flex;justify-content:space-between;align-items:flex-start">
        <div><b>${esc(g.title)}</b> ${done?'<span class="pill pill-green">reached ✓</span>':""}
          <div class="faint" style="font-size:12px;margin-top:2px">Metric: ${esc(g.metric)}</div></div>
        <button class="btn btn-ghost btn-sm" data-delgoal="${g.id}">${icon("trash")}</button>
      </div>
      <div class="progress"><span style="width:${pctDone}%"></span></div>
      <div style="display:flex;justify-content:space-between;font-size:12.5px" class="muted">
        <span class="mono">${unit}</span><span class="faint">target ${tgt}</span></div>
    </div>`;
  }

  function habitRow(hb) {
    const days = [];
    for (let i = 6; i >= 0; i--) { const d = new Date(); d.setDate(d.getDate() - i); days.push(d); }
    const dots = days.map((d) => {
      const key = d.toISOString().slice(0, 10);
      const on = hb.log && hb.log[key];
      const lbl = d.toLocaleDateString(undefined, { weekday: "narrow" });
      return `<div class="wd ${on?"on":""}" data-hid="${hb.id}" data-date="${key}" title="${key}">${lbl}</div>`;
    }).join("");
    return `<div class="habit-row">
      <div><b style="font-size:14px">${esc(hb.name)}</b>
        <div class="streak-badge">🔥 ${hb.streak||0} day streak</div></div>
      <div style="display:flex;align-items:center;gap:12px">
        <div class="week-dots">${dots}</div>
        <button class="btn btn-ghost btn-sm" data-delhabit="${hb.id}">${icon("trash")}</button>
      </div>
    </div>`;
  }

  function goalModal() {
    const body = `
      <div class="field"><label>Goal title</label><input id="g-title" placeholder="Reach a 55% win rate"/></div>
      <div class="field"><label>Track against metric</label>
        <select id="g-metric">
          <option value="win_rate">Win rate (%)</option>
          <option value="pnl">Net P&L ($)</option>
          <option value="profit_factor">Profit factor</option>
          <option value="expectancy">Expectancy ($)</option>
          <option value="custom">Custom (manual)</option>
        </select></div>
      <div class="field"><label>Target value</label><input id="g-target" type="number" step="any" placeholder="55"/></div>
      <div class="form-error" id="g-err"></div>`;
    modal("New goal", body, `<button class="btn btn-ghost" data-close>Cancel</button><button class="btn btn-primary" id="g-save">Create goal</button>`);
    el("g-save").addEventListener("click", async () => {
      const title = el("g-title").value.trim();
      if (!title) { el("g-err").textContent = "Give your goal a title."; return; }
      await API.createGoal({ title, metric: el("g-metric").value, target: el("g-target").value || 0 });
      close(); toast("Goal created"); router();
    });
  }

  // ======================================================================
  // Helpers
  // ======================================================================
  function emptyState(c, title, msg) {
    c.innerHTML = `<div class="card empty"><div class="big">📈</div><h3>${esc(title)}</h3><p>${esc(msg)}</p>
      <div style="margin-top:18px;display:flex;gap:10px;justify-content:center">
        <button class="btn btn-primary" id="es-add">${icon("plus")} Log a trade</button>
        <button class="btn" id="es-import">${icon("upload")} Import CSV</button></div></div>`;
    el("es-add").addEventListener("click", () => tradeModal());
    el("es-import").addEventListener("click", importModal);
  }
  function emptyInline(msg) { return `<div class="card empty"><p class="faint">${esc(msg)}</p></div>`; }

  init();
})();
