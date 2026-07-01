/* Thin API client. Stores the session token in localStorage and attaches it
   to every request. All methods return parsed JSON or throw {error}. */
const API = (() => {
  const TOKEN_KEY = "tjp_token";
  let token = localStorage.getItem(TOKEN_KEY) || null;

  function setToken(t) {
    token = t;
    if (t) localStorage.setItem(TOKEN_KEY, t);
    else localStorage.removeItem(TOKEN_KEY);
  }

  async function request(method, path, body) {
    const headers = { "Content-Type": "application/json" };
    if (token) headers["Authorization"] = "Bearer " + token;
    const res = await fetch("/api" + path, {
      method,
      headers,
      body: body != null ? JSON.stringify(body) : undefined,
    });
    let data = {};
    try { data = await res.json(); } catch (e) { /* empty */ }
    if (!res.ok) {
      throw { status: res.status, error: data.error || "Request failed" };
    }
    return data;
  }

  return {
    get token() { return token; },
    setToken,
    isAuthed: () => !!token,
    logout: () => setToken(null),
    // auth
    register: (d) => request("POST", "/auth/register", d),
    login: (d) => request("POST", "/auth/login", d),
    me: () => request("GET", "/me"),
    onboard: (d) => request("POST", "/onboard", d),
    // trades
    trades: (qs = "") => request("GET", "/trades" + qs),
    createTrade: (d) => request("POST", "/trades", d),
    updateTrade: (id, d) => request("PUT", "/trades/" + id, d),
    deleteTrade: (id) => request("DELETE", "/trades/" + id),
    importCsv: (csv) => request("POST", "/trades/import", { csv }),
    // analytics
    dashboard: () => request("GET", "/dashboard"),
    calendar: () => request("GET", "/calendar"),
    analytics: () => request("GET", "/analytics"),
    coach: (period = "all") => request("GET", "/coach?period=" + period),
    // goals & habits
    goals: () => request("GET", "/goals"),
    createGoal: (d) => request("POST", "/goals", d),
    updateGoal: (id, d) => request("PUT", "/goals/" + id, d),
    deleteGoal: (id) => request("DELETE", "/goals/" + id),
    habits: () => request("GET", "/habits"),
    createHabit: (d) => request("POST", "/habits", d),
    toggleHabit: (id, date) => request("POST", "/habits/" + id + "/toggle", { date }),
    deleteHabit: (id) => request("DELETE", "/habits/" + id),
  };
})();
