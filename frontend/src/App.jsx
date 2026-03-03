import { useState, useEffect, useCallback } from "react";
import {
  AreaChart, Area, PieChart, Pie, Cell,
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, LineChart, Line, Legend,
} from "recharts";

// ─────────────────────────────────────────────────────────────────
// CONFIG
// ─────────────────────────────────────────────────────────────────
const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000/api";

async function api(path) {
  try {
    const r = await fetch(`${BASE_URL}${path}`);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return await r.json();
  } catch (e) {
    console.warn(`[API] ${path} failed:`, e.message);
    return null;
  }
}

// ─────────────────────────────────────────────────────────────────
// CONSTANTS
// ─────────────────────────────────────────────────────────────────
const BROKER_COLORS = {
  "Zerodha":             "#00C7B1",
  "Sharekhan":           "#F7A84F",
  "Interactive Brokers": "#4F8EF7",
  "eToro":               "#7ED6A5",
  "Aionion Capital":     "#E882DC",
};
const PALETTE = ["#00C7B1","#4F8EF7","#F7A84F","#7ED6A5","#E882DC","#FF6B6B","#A78BFA","#38BDF8"];

const FX = { USD: 83.5, EUR: 90.2, INR: 1 };
const toINR = (v, cur = "INR") => v * (FX[cur] || 1);

const fmtINR = (n, decimals = 0) => {
  const abs = Math.abs(n);
  if (abs >= 1e7) return `₹${(abs / 1e7).toFixed(2)}Cr`;
  if (abs >= 1e5) return `₹${(abs / 1e5).toFixed(2)}L`;
  return `₹${abs.toLocaleString("en-IN", { maximumFractionDigits: decimals })}`;
};
const fmtPct = (n) => `${n >= 0 ? "+" : ""}${Number(n).toFixed(2)}%`;
const clr = (n) => (n >= 0 ? "#00C7B1" : "#FF6B6B");
const sign = (n) => (n >= 0 ? "▲" : "▼");

// ─────────────────────────────────────────────────────────────────
// SMALL COMPONENTS
// ─────────────────────────────────────────────────────────────────
function Spinner() {
  return (
    <div style={{ display: "flex", justifyContent: "center", alignItems: "center", height: 200, flexDirection: "column", gap: 16 }}>
      <div style={{ width: 36, height: 36, border: "3px solid #ffffff15", borderTop: "3px solid #00C7B1", borderRadius: "50%", animation: "spin 0.8s linear infinite" }} />
      <div style={{ color: "#4A4E64", fontSize: 13 }}>Loading live data…</div>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

function EmptyState({ msg = "No data — check that the backend is running on port 8000" }) {
  return (
    <div style={{ textAlign: "center", padding: "60px 20px", color: "#4A4E64" }}>
      <div style={{ fontSize: 36, marginBottom: 12 }}>⚡</div>
      <div style={{ fontSize: 14 }}>{msg}</div>
      <div style={{ fontSize: 12, marginTop: 8, color: "#333650" }}>
        Run: <code style={{ background: "#0D0F1A", padding: "2px 8px", borderRadius: 4 }}>cd backend && source venv/bin/activate && python3 -m uvicorn main:app --reload</code>
      </div>
    </div>
  );
}

function StatCard({ label, value, sub, positive }) {
  const pos = positive === undefined ? true : positive;
  return (
    <div style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 16, padding: "20px 24px", flex: 1, minWidth: 160 }}>
      <div style={{ fontSize: 11, color: "#5A5F78", letterSpacing: 1, textTransform: "uppercase", marginBottom: 8 }}>{label}</div>
      <div style={{ fontSize: 22, fontWeight: 700, color: "#E8EAF0", fontFamily: "'DM Mono',monospace" }}>{value}</div>
      {sub !== undefined && (
        <div style={{ marginTop: 6, fontSize: 13, color: pos ? "#00C7B1" : "#FF6B6B", fontWeight: 600 }}>
          {sign(pos ? 1 : -1)} {sub}
        </div>
      )}
    </div>
  );
}

function Tag({ text, color = "#8A8FA8" }) {
  return (
    <span style={{ fontSize: 10, padding: "2px 8px", borderRadius: 20, background: `${color}18`, color, border: `1px solid ${color}35`, fontWeight: 600 }}>
      {text}
    </span>
  );
}

const CustomTip = ({ active, payload, label, currency = "₹" }) => {
  if (!active || !payload?.length) return null;
  return (
    <div style={{ background: "#1A1D2E", border: "1px solid rgba(255,255,255,0.12)", borderRadius: 10, padding: "10px 14px" }}>
      <div style={{ color: "#8A8FA8", fontSize: 12, marginBottom: 4 }}>{label}</div>
      {payload.map((p, i) => (
        <div key={i} style={{ color: p.color || "#00C7B1", fontWeight: 700, fontFamily: "'DM Mono',monospace", fontSize: 13 }}>
          {p.name}: {currency}{Number(p.value).toLocaleString("en-IN", { maximumFractionDigits: 2 })}
        </div>
      ))}
    </div>
  );
};

// ─────────────────────────────────────────────────────────────────
// HOLDINGS TABLE
// ─────────────────────────────────────────────────────────────────
function HoldingsTable({ holdings, owner = "all" }) {
  const [search, setSearch] = useState("");
  const [sort, setSort]     = useState({ key: "current_value", dir: -1 });

  const filtered = holdings
    .filter(h => owner === "all" || h.owner === owner)
    .filter(h => !search || h.symbol.includes(search.toUpperCase()) || h.name?.toLowerCase().includes(search.toLowerCase()))
    .sort((a, b) => {
      const av = a[sort.key] ?? 0, bv = b[sort.key] ?? 0;
      return typeof av === "string" ? sort.dir * av.localeCompare(bv) : sort.dir * (av - bv);
    });

  const TH = ({ k, label, right }) => (
    <th onClick={() => setSort(s => ({ key: k, dir: s.key === k ? -s.dir : -1 }))}
      style={{ padding: "10px 12px", textAlign: right ? "right" : "left", color: sort.key === k ? "#E8EAF0" : "#5A5F78", fontWeight: 600, cursor: "pointer", whiteSpace: "nowrap", userSelect: "none" }}>
      {label} {sort.key === k ? (sort.dir > 0 ? "↑" : "↓") : ""}
    </th>
  );

  if (!filtered.length) return <EmptyState msg={search ? "No matching holdings" : "No holdings loaded"} />;

  return (
    <>
      <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search symbol or name…"
        style={{ width: "100%", marginBottom: 16, padding: "10px 14px", background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 10, color: "#E8EAF0", fontSize: 13, outline: "none" }} />
      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
          <thead>
            <tr style={{ borderBottom: "1px solid rgba(255,255,255,0.1)" }}>
              <TH k="broker"        label="Broker" />
              <TH k="symbol"        label="Symbol" />
              <TH k="name"          label="Name" />
              <TH k="asset_type"    label="Type" />
              <TH k="owner"         label="Owner" />
              <TH k="quantity"      label="Qty"           right />
              <TH k="average_price" label="Avg Price"     right />
              <TH k="current_price" label="LTP"           right />
              <TH k="current_value" label="Value"         right />
              <TH k="pnl"           label="P&L"           right />
              <TH k="pnl_percent"   label="P&L %"         right />
            </tr>
          </thead>
          <tbody>
            {filtered.map((h, i) => {
              const profit = h.pnl >= 0;
              const cur = h.currency || "INR";
              const sym = cur === "INR" ? "₹" : cur === "USD" ? "$" : "€";
              return (
                <tr key={i} style={{ borderBottom: "1px solid rgba(255,255,255,0.04)" }}
                  onMouseEnter={e => e.currentTarget.style.background = "rgba(255,255,255,0.03)"}
                  onMouseLeave={e => e.currentTarget.style.background = "transparent"}>
                  <td style={{ padding: "11px 12px", color: BROKER_COLORS[h.broker] || "#fff", fontWeight: 600, whiteSpace: "nowrap" }}>{h.broker}</td>
                  <td style={{ padding: "11px 12px", color: "#E8EAF0", fontWeight: 700, fontFamily: "'DM Mono',monospace" }}>{h.symbol}</td>
                  <td style={{ padding: "11px 12px", color: "#8A8FA8", maxWidth: 160, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{h.name}</td>
                  <td style={{ padding: "11px 12px" }}><Tag text={h.asset_type} /></td>
                  <td style={{ padding: "11px 12px" }}>
                    <Tag text={h.sub_account ? `📋 ${h.sub_account}` : (h.owner === "radhika" ? "👩 R" : "👤 S")} color={h.owner === "radhika" ? "#E882DC" : "#4F8EF7"} />
                  </td>
                  <td style={{ padding: "11px 12px", textAlign: "right", fontFamily: "'DM Mono',monospace", color: "#C8CAD8" }}>{Number(h.quantity).toLocaleString()}</td>
                  <td style={{ padding: "11px 12px", textAlign: "right", fontFamily: "'DM Mono',monospace", color: "#6B6F84" }}>{sym}{Number(h.average_price).toLocaleString("en-IN", { maximumFractionDigits: 2 })}</td>
                  <td style={{ padding: "11px 12px", textAlign: "right", fontFamily: "'DM Mono',monospace", color: "#E8EAF0" }}>{sym}{Number(h.current_price).toLocaleString("en-IN", { maximumFractionDigits: 2 })}</td>
                  <td style={{ padding: "11px 12px", textAlign: "right", fontFamily: "'DM Mono',monospace", fontWeight: 700 }}>{sym}{Number(h.current_value).toLocaleString("en-IN", { maximumFractionDigits: 0 })}</td>
                  <td style={{ padding: "11px 12px", textAlign: "right", fontFamily: "'DM Mono',monospace", color: clr(h.pnl), fontWeight: 600 }}>
                    {profit ? "+" : "-"}{sym}{Math.abs(h.pnl).toLocaleString("en-IN", { maximumFractionDigits: 0 })}
                  </td>
                  <td style={{ padding: "11px 12px", textAlign: "right" }}>
                    <span style={{ fontSize: 12, padding: "3px 8px", borderRadius: 20, fontWeight: 700, fontFamily: "'DM Mono',monospace",
                      background: profit ? "#00C7B115" : "#FF6B6B15", color: clr(h.pnl), border: `1px solid ${clr(h.pnl)}30` }}>
                      {fmtPct(h.pnl_percent)}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </>
  );
}

// ─────────────────────────────────────────────────────────────────
// COPY TRADERS TABLE
// ─────────────────────────────────────────────────────────────────
function CopyTradersPanel({ data }) {
  if (!data?.length) return <EmptyState msg="No copy traders found — eToro API keys required" />;
  return (
    <div style={{ overflowX: "auto" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
        <thead>
          <tr style={{ borderBottom: "1px solid rgba(255,255,255,0.1)" }}>
            {["Trader","Owner","Positions","Deposited","Net Invested","Portfolio Value","Unrealized P&L","Closed P&L","Total P&L","P&L %","Since"].map(h => (
              <th key={h} style={{ padding: "10px 12px", textAlign: h === "Trader" || h === "Owner" || h === "Since" ? "left" : "right", color: "#5A5F78", fontWeight: 600, whiteSpace: "nowrap" }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((ct, i) => (
            <tr key={i} style={{ borderBottom: "1px solid rgba(255,255,255,0.04)" }}
              onMouseEnter={e => e.currentTarget.style.background = "rgba(255,255,255,0.03)"}
              onMouseLeave={e => e.currentTarget.style.background = "transparent"}>
              <td style={{ padding: "11px 12px", color: "#7ED6A5", fontWeight: 700 }}>{ct.trader}</td>
              <td style={{ padding: "11px 12px" }}><Tag text={ct.owner === "radhika" ? "👩 Radhika" : "👤 Selvam"} color={ct.owner === "radhika" ? "#E882DC" : "#4F8EF7"} /></td>
              <td style={{ padding: "11px 12px", textAlign: "right", color: "#8A8FA8" }}>{ct.positions_count}</td>
              <td style={{ padding: "11px 12px", textAlign: "right", fontFamily: "'DM Mono',monospace" }}>${ct.deposited?.toLocaleString()}</td>
              <td style={{ padding: "11px 12px", textAlign: "right", fontFamily: "'DM Mono',monospace" }}>${ct.net_invested?.toLocaleString()}</td>
              <td style={{ padding: "11px 12px", textAlign: "right", fontFamily: "'DM Mono',monospace", fontWeight: 700 }}>${ct.total_value?.toLocaleString()}</td>
              <td style={{ padding: "11px 12px", textAlign: "right", fontFamily: "'DM Mono',monospace", color: clr(ct.unrealized_pnl) }}>{ct.unrealized_pnl >= 0 ? "+" : ""}${Math.abs(ct.unrealized_pnl).toLocaleString()}</td>
              <td style={{ padding: "11px 12px", textAlign: "right", fontFamily: "'DM Mono',monospace", color: clr(ct.closed_pnl) }}>{ct.closed_pnl >= 0 ? "+" : ""}${Math.abs(ct.closed_pnl).toLocaleString()}</td>
              <td style={{ padding: "11px 12px", textAlign: "right", fontFamily: "'DM Mono',monospace", fontWeight: 700, color: clr(ct.total_pnl) }}>{ct.total_pnl >= 0 ? "+" : ""}${Math.abs(ct.total_pnl).toLocaleString()}</td>
              <td style={{ padding: "11px 12px", textAlign: "right" }}>
                <span style={{ fontSize: 12, padding: "3px 8px", borderRadius: 20, fontWeight: 700, fontFamily: "'DM Mono',monospace",
                  background: ct.pnl_percent >= 0 ? "#00C7B115" : "#FF6B6B15", color: clr(ct.pnl_percent), border: `1px solid ${clr(ct.pnl_percent)}30` }}>
                  {fmtPct(ct.pnl_percent)}
                </span>
              </td>
              <td style={{ padding: "11px 12px", color: "#6B6F84", fontSize: 12 }}>{ct.started}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────
// PERFORMANCE CHARTS
// ─────────────────────────────────────────────────────────────────
function PerformancePanel({ data }) {
  const [view, setView] = useState("monthly");
  if (!data || !Object.keys(data).length) return <EmptyState msg="No performance data — eToro API keys required" />;

  const owners = Object.keys(data);
  const allDates = [...new Set(owners.flatMap(o => (data[o][view] || []).map(d => d.date)))].sort();
  const chartData = allDates.map(date => {
    const row = { date };
    owners.forEach(o => {
      const pt = (data[o][view] || []).find(d => d.date === date);
      if (pt) row[o] = pt.gain;
    });
    return row;
  });

  return (
    <div>
      <div style={{ display: "flex", gap: 8, marginBottom: 20 }}>
        {["monthly", "yearly"].map(v => (
          <button key={v} onClick={() => setView(v)}
            style={{ padding: "6px 16px", borderRadius: 20, border: "1px solid", cursor: "pointer",
              borderColor: view === v ? "#00C7B1" : "rgba(255,255,255,0.1)",
              background: view === v ? "#00C7B115" : "transparent",
              color: view === v ? "#00C7B1" : "#6B6F84", fontSize: 12, fontWeight: 600 }}>
            {v.charAt(0).toUpperCase() + v.slice(1)}
          </button>
        ))}
      </div>
      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
          <XAxis dataKey="date" tick={{ fill: "#6B6F84", fontSize: 11 }} tickLine={false} axisLine={false} />
          <YAxis tick={{ fill: "#6B6F84", fontSize: 11 }} tickLine={false} axisLine={false} tickFormatter={v => `${v}%`} />
          <Tooltip contentStyle={{ background: "#1A1D2E", border: "1px solid rgba(255,255,255,0.12)", borderRadius: 10 }}
            formatter={(v, name) => [`${Number(v).toFixed(2)}%`, name]} />
          <Legend />
          {owners.map((o, i) => (
            <Line key={o} type="monotone" dataKey={o} stroke={PALETTE[i]} strokeWidth={2.5} dot={false} name={`${o} (${data[o].username || o})`} />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────
// MAIN DASHBOARD
// ─────────────────────────────────────────────────────────────────
export default function Dashboard() {
  // ── state ──
  const [summary,      setSummary]      = useState(null);
  const [holdings,     setHoldings]     = useState(null);
  const [brokerAlloc,  setBrokerAlloc]  = useState(null);
  const [assetAlloc,   setAssetAlloc]   = useState(null);
  const [copyTraders,  setCopyTraders]  = useState(null);
  const [performance,  setPerformance]  = useState(null);
  const [activeTab,    setActiveTab]    = useState("overview");
  const [ownerFilter,  setOwnerFilter]  = useState("all");  // all | selvam | radhika
  const [loading,      setLoading]      = useState(false);
  const [lastRefresh,  setLastRefresh]  = useState(null);
  const [apiStatus,    setApiStatus]    = useState("checking"); // ok | error | checking

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const health = await api("/health") ?? await fetch("http://localhost:8000/health").catch(() => null);
      if (!health) { setApiStatus("error"); setLoading(false); return; }
      setApiStatus("ok");

      const [s, h, ba, aa, ct, perf] = await Promise.all([
        api("/portfolio/summary"),
        api("/portfolio/holdings"),
        api("/portfolio/allocation/broker"),
        api("/portfolio/allocation/asset"),
        api("/etoro/copy-traders"),
        api("/etoro/performance"),
      ]);
      if (s)    setSummary(s);
      if (h)    setHoldings(h);
      if (ba)   setBrokerAlloc(ba);
      if (aa)   setAssetAlloc(aa);
      if (ct)   setCopyTraders(ct);
      if (perf) setPerformance(perf);
      setLastRefresh(new Date().toLocaleTimeString("en-IN"));
    } catch(e) {
      console.error("Load error", e);
      setApiStatus("error");
    }
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  // ── derived ──
  const brokers   = summary?.brokers || [];
  const allHoldings = holdings || [];

  const filteredHoldings = ownerFilter === "all"
    ? allHoldings
    : allHoldings.filter(h => h.owner === ownerFilter);

  const selvamVal  = summary?.selvam_value  || 0;
  const radhikaVal = summary?.radhika_value || 0;

  // ── NAV ──
  const NAV_ITEMS = [
    { id: "overview",   icon: "◈", label: "Overview"     },
    { id: "holdings",   icon: "◉", label: "Holdings"     },
    { id: "brokers",    icon: "◫", label: "By Broker"    },
    { id: "copytraders",icon: "⟳", label: "Copy Traders" },
    { id: "performance",icon: "◐", label: "Performance"  },
    { id: "analytics",  icon: "◑", label: "Analytics"    },
  ];

  // ─────────────────────────────────────────────────────────────
  return (
    <div style={{ minHeight: "100vh", background: "#0D0F1A", color: "#E8EAF0", fontFamily: "'Inter','Segoe UI',sans-serif" }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Syne:wght@700;800&family=Inter:wght@400;500;600&display=swap');
        *{box-sizing:border-box;margin:0;padding:0;}
        ::-webkit-scrollbar{width:5px;height:5px;}
        ::-webkit-scrollbar-track{background:#0D0F1A;}
        ::-webkit-scrollbar-thumb{background:#252839;border-radius:3px;}
        input::placeholder{color:#3A3D52;}
      `}</style>

      {/* ── SIDEBAR ── */}
      <div style={{ position:"fixed", left:0, top:0, bottom:0, width:230, background:"#080A13", borderRight:"1px solid rgba(255,255,255,0.07)", display:"flex", flexDirection:"column", padding:"28px 0", zIndex:100 }}>

        {/* Logo */}
        <div style={{ padding:"0 24px 24px", borderBottom:"1px solid rgba(255,255,255,0.07)" }}>
          <div style={{ fontSize:10, letterSpacing:2.5, color:"#4F8EF7", fontWeight:700, textTransform:"uppercase", marginBottom:3 }}>TRaMS</div>
          <div style={{ fontSize:18, fontWeight:800, fontFamily:"'Syne',sans-serif" }}>Portfolio</div>
          <div style={{ fontSize:11, color:"#4A4E64", marginTop:2 }}>Selvam · Radhika</div>
        </div>

        {/* Owner filter */}
        <div style={{ padding:"16px 16px", borderBottom:"1px solid rgba(255,255,255,0.07)" }}>
          <div style={{ fontSize:10, color:"#3A3D52", letterSpacing:1, textTransform:"uppercase", marginBottom:8 }}>View</div>
          <div style={{ display:"flex", gap:6 }}>
            {[["all","👨‍👩‍👧 All"],["selvam","👤 Selvam"],["radhika","👩 Radhika"]].map(([v, label]) => (
              <button key={v} onClick={() => setOwnerFilter(v)}
                style={{ flex:1, padding:"6px 4px", borderRadius:8, border:"1px solid", cursor:"pointer", fontSize:10, fontWeight:600,
                  borderColor: ownerFilter===v ? (v==="radhika"?"#E882DC":"#4F8EF7") : "rgba(255,255,255,0.08)",
                  background:  ownerFilter===v ? (v==="radhika"?"#E882DC15":"#4F8EF715") : "transparent",
                  color:       ownerFilter===v ? (v==="radhika"?"#E882DC":"#4F8EF7") : "#4A4E64" }}>
                {label}
              </button>
            ))}
          </div>
        </div>

        {/* Nav */}
        <nav style={{ padding:"16px 12px", flex:1 }}>
          {NAV_ITEMS.map(item => (
            <button key={item.id} onClick={() => setActiveTab(item.id)}
              style={{ display:"flex", alignItems:"center", gap:10, width:"100%", padding:"9px 14px", borderRadius:10,
                border:"none", cursor:"pointer", marginBottom:2, fontSize:13, fontWeight:600, textAlign:"left", transition:"all 0.15s",
                background: activeTab===item.id ? "rgba(79,142,247,0.12)" : "transparent",
                color:      activeTab===item.id ? "#4F8EF7" : "#5A5F78" }}>
              <span style={{ fontSize:15 }}>{item.icon}</span>{item.label}
            </button>
          ))}
        </nav>

        {/* Broker status */}
        <div style={{ padding:"16px 16px 0", borderTop:"1px solid rgba(255,255,255,0.07)" }}>
          <div style={{ fontSize:10, color:"#3A3D52", letterSpacing:1, textTransform:"uppercase", marginBottom:10 }}>Connections</div>
          {brokers.map(b => (
            <div key={b.broker} style={{ display:"flex", alignItems:"center", gap:8, marginBottom:7, fontSize:11 }}>
              <div style={{ width:6, height:6, borderRadius:"50%", background: b.connected ? "#00C7B1" : "#F7A84F", flexShrink:0 }} />
              <span style={{ color:"#5A5F78", overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap", flex:1 }}>{b.broker}</span>
              {b.connected
                ? <span style={{ color:"#00C7B150", fontSize:9, fontWeight:700 }}>LIVE</span>
                : <span style={{ color:"#F7A84F50", fontSize:9, fontWeight:700 }}>OFF</span>}
            </div>
          ))}
          {apiStatus === "error" && (
            <div style={{ marginTop:8, fontSize:10, color:"#FF6B6B", background:"#FF6B6B10", padding:"6px 8px", borderRadius:6 }}>
              ⚠ Backend offline
            </div>
          )}
          {lastRefresh && (
            <div style={{ marginTop:8, fontSize:10, color:"#3A3D52" }}>Updated {lastRefresh}</div>
          )}
        </div>
      </div>

      {/* ── MAIN ── */}
      <div style={{ marginLeft:230, padding:"32px 32px 60px" }}>

        {/* Header */}
        <div style={{ display:"flex", justifyContent:"space-between", alignItems:"flex-start", marginBottom:32 }}>
          <div>
            <h1 style={{ fontFamily:"'Syne',sans-serif", fontSize:26, fontWeight:800, letterSpacing:-0.5 }}>
              { {overview:"Overview", holdings:"Holdings", brokers:"By Broker", copytraders:"Copy Traders", performance:"Performance", analytics:"Analytics"}[activeTab] }
            </h1>
            <div style={{ color:"#4A4E64", fontSize:12, marginTop:4 }}>
              {new Date().toLocaleDateString("en-IN",{weekday:"long",year:"numeric",month:"long",day:"numeric"})}
              {loading && <span style={{ marginLeft:12, color:"#4F8EF7" }}>● Refreshing…</span>}
            </div>
          </div>
          <button onClick={load}
            style={{ padding:"9px 20px", background:"#4F8EF715", border:"1px solid #4F8EF730", borderRadius:10, color:"#4F8EF7", fontSize:13, fontWeight:600, cursor:"pointer" }}>
            ↻ Refresh
          </button>
        </div>

        {/* ── OVERVIEW ── */}
        {activeTab === "overview" && (
          <>
            {loading && !summary ? <Spinner /> : !summary ? <EmptyState /> : (
              <>
                {/* KPIs */}
                <div style={{ display:"flex", gap:14, marginBottom:20, flexWrap:"wrap" }}>
                  <StatCard label="Total Portfolio" value={fmtINR(summary.total_value)} />
                  <StatCard label="Total Invested"  value={fmtINR(summary.total_invested)} />
                  <StatCard label="Total P&L"        value={fmtINR(summary.total_pnl)}
                    sub={fmtPct(summary.total_pnl_percent)} positive={summary.total_pnl >= 0} />
                  <StatCard label="Holdings" value={summary.total_holdings || allHoldings.length} />
                </div>

                {/* Owner split */}
                {(selvamVal > 0 || radhikaVal > 0) && (
                  <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:14, marginBottom:20 }}>
                    {[["👤 Selvam", selvamVal, "#4F8EF7"],["👩 Radhika", radhikaVal, "#E882DC"]].map(([label, val, color]) => (
                      <div key={label} style={{ background:`${color}08`, border:`1px solid ${color}20`, borderLeft:`3px solid ${color}`, borderRadius:14, padding:"16px 20px" }}>
                        <div style={{ fontSize:12, color:"#5A5F78", marginBottom:6 }}>{label}</div>
                        <div style={{ fontSize:24, fontWeight:800, fontFamily:"'DM Mono',monospace", color }}>{fmtINR(val)}</div>
                        <div style={{ fontSize:11, color:"#4A4E64", marginTop:4 }}>{((val / summary.total_value) * 100).toFixed(1)}% of total</div>
                      </div>
                    ))}
                  </div>
                )}

                {/* Allocations */}
                <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:16, marginBottom:20 }}>
                  {[
                    { title:"Broker Allocation", data: brokerAlloc, key:"broker" },
                    { title:"Asset Allocation",  data: assetAlloc,  key:"type"   },
                  ].map(({ title, data, key }) => !data ? null : (
                    <div key={title} style={{ background:"rgba(255,255,255,0.03)", border:"1px solid rgba(255,255,255,0.07)", borderRadius:16, padding:22 }}>
                      <div style={{ fontSize:13, fontWeight:700, color:"#8A8FA8", marginBottom:16 }}>{title}</div>
                      <div style={{ display:"flex", alignItems:"center", gap:20 }}>
                        <ResponsiveContainer width={140} height={140}>
                          <PieChart>
                            <Pie data={data} cx="50%" cy="50%" innerRadius={38} outerRadius={62} dataKey="value" paddingAngle={3}>
                              {data.map((_, idx) => <Cell key={idx} fill={PALETTE[idx % PALETTE.length]} />)}
                            </Pie>
                          </PieChart>
                        </ResponsiveContainer>
                        <div style={{ flex:1 }}>
                          {data.map((d, i) => (
                            <div key={i} style={{ display:"flex", justifyContent:"space-between", marginBottom:7, fontSize:12, alignItems:"center" }}>
                              <div style={{ display:"flex", alignItems:"center", gap:7 }}>
                                <div style={{ width:7, height:7, borderRadius:2, background:PALETTE[i % PALETTE.length] }} />
                                <span style={{ color:"#8A8FA8" }}>{d[key]}</span>
                              </div>
                              <span style={{ color:"#C8CAD8", fontFamily:"'DM Mono',monospace", fontWeight:600 }}>{d.percent?.toFixed(1)}%</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>

                {/* Broker cards */}
                <div style={{ background:"rgba(255,255,255,0.03)", border:"1px solid rgba(255,255,255,0.07)", borderRadius:16, padding:22 }}>
                  <div style={{ fontSize:13, fontWeight:700, color:"#8A8FA8", marginBottom:16 }}>Broker Summary</div>
                  {!brokers.length ? <EmptyState msg="No broker data yet" /> : (
                    <div style={{ display:"grid", gridTemplateColumns:"repeat(auto-fill, minmax(210px, 1fr))", gap:12 }}>
                      {brokers.map(b => {
                        const color = BROKER_COLORS[b.broker] || "#fff";
                        const profit = b.total_pnl >= 0;
                        const cur = b.currency === "USD" ? "$" : "₹";
                        return (
                          <div key={b.broker} style={{ background:"rgba(255,255,255,0.04)", border:`1px solid ${color}20`, borderLeft:`3px solid ${color}`, borderRadius:12, padding:"16px 18px" }}>
                            <div style={{ display:"flex", justifyContent:"space-between", marginBottom:10 }}>
                              <div style={{ fontWeight:700, color:"#E8EAF0", fontSize:13 }}>{b.broker}</div>
                              <span style={{ fontSize:9, padding:"2px 7px", borderRadius:20,
                                background: b.connected ? "#00C7B120" : "#F7A84F20",
                                color:      b.connected ? "#00C7B1"   : "#F7A84F",
                                border:     `1px solid ${b.connected ? "#00C7B140" : "#F7A84F40"}`, fontWeight:700 }}>
                                {b.connected ? "● LIVE" : "● OFF"}
                              </span>
                            </div>
                            <div style={{ fontSize:20, fontWeight:800, color, fontFamily:"'DM Mono',monospace" }}>
                              {cur}{Number(b.total_value).toLocaleString("en-IN", { maximumFractionDigits: 0 })}
                            </div>
                            <div style={{ display:"flex", justifyContent:"space-between", marginTop:8 }}>
                              <div style={{ fontSize:11, color:"#5A5F78" }}>{b.holdings_count} holdings</div>
                              <div style={{ fontSize:12, fontWeight:600, color: clr(b.total_pnl) }}>
                                {profit ? "+" : "-"}{cur}{Math.abs(b.total_pnl).toLocaleString("en-IN", { maximumFractionDigits:0 })}
                                <span style={{ fontSize:11, marginLeft:4 }}>({fmtPct(b.total_pnl_percent)})</span>
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              </>
            )}
          </>
        )}

        {/* ── HOLDINGS ── */}
        {activeTab === "holdings" && (
          <div style={{ background:"rgba(255,255,255,0.03)", border:"1px solid rgba(255,255,255,0.07)", borderRadius:16, padding:24 }}>
            {loading && !holdings ? <Spinner /> : !holdings?.length ? <EmptyState /> : (
              <HoldingsTable holdings={allHoldings} owner={ownerFilter} />
            )}
          </div>
        )}

        {/* ── BY BROKER ── */}
        {activeTab === "brokers" && (
          <div style={{ display:"grid", gap:20 }}>
            {loading && !brokers.length ? <Spinner /> : brokers.map(b => {
              const bHoldings = allHoldings.filter(h => h.broker === b.broker && (ownerFilter === "all" || h.owner === ownerFilter));
              const color = BROKER_COLORS[b.broker] || "#4F8EF7";
              const cur = b.currency === "USD" ? "$" : "₹";
              return (
                <div key={b.broker} style={{ background:"rgba(255,255,255,0.03)", border:`1px solid ${color}20`, borderLeft:`3px solid ${color}`, borderRadius:16, padding:24 }}>
                  <div style={{ display:"flex", justifyContent:"space-between", alignItems:"flex-start", marginBottom:20 }}>
                    <div>
                      <h2 style={{ fontFamily:"'Syne',sans-serif", fontSize:18, fontWeight:700, color }}>{b.broker}</h2>
                      <div style={{ color:"#5A5F78", fontSize:11, marginTop:3 }}>
                        {b.holdings_count} holdings · {b.connected ? "Live API" : "Offline"} · Owner: {b.owner}
                      </div>
                    </div>
                    <div style={{ textAlign:"right" }}>
                      <div style={{ fontSize:22, fontWeight:800, fontFamily:"'DM Mono',monospace", color }}>{cur}{Number(b.total_value).toLocaleString("en-IN",{maximumFractionDigits:0})}</div>
                      <div style={{ fontSize:13, color: clr(b.total_pnl), fontWeight:600 }}>
                        {b.total_pnl >= 0 ? "+" : ""}{cur}{Math.abs(b.total_pnl).toLocaleString("en-IN",{maximumFractionDigits:0})} ({fmtPct(b.total_pnl_percent)})
                      </div>
                    </div>
                  </div>
                  <div style={{ display:"flex", gap:12, marginBottom:20 }}>
                    {[["Invested", `${cur}${Number(b.total_invested).toLocaleString("en-IN",{maximumFractionDigits:0})}`, "#E8EAF0"],
                      ["Cash",     `${cur}${Number(b.cash_balance).toLocaleString("en-IN",{maximumFractionDigits:0})}`, "#00C7B1"]].map(([lbl, val, vc]) => (
                      <div key={lbl} style={{ background:"rgba(255,255,255,0.04)", borderRadius:10, padding:"12px 16px", flex:1 }}>
                        <div style={{ fontSize:11, color:"#5A5F78", marginBottom:4 }}>{lbl}</div>
                        <div style={{ fontFamily:"'DM Mono',monospace", fontWeight:700, color:vc }}>{val}</div>
                      </div>
                    ))}
                  </div>
                  {bHoldings.length > 0 ? <HoldingsTable holdings={bHoldings} owner="all" /> : <EmptyState msg={`No ${ownerFilter !== "all" ? ownerFilter + "'s" : ""} holdings in ${b.broker}`} />}
                </div>
              );
            })}
          </div>
        )}

        {/* ── COPY TRADERS ── */}
        {activeTab === "copytraders" && (
          <div style={{ background:"rgba(255,255,255,0.03)", border:"1px solid rgba(255,255,255,0.07)", borderRadius:16, padding:24 }}>
            <div style={{ fontSize:13, fontWeight:700, color:"#8A8FA8", marginBottom:20 }}>
              eToro Copy Traders — {copyTraders?.length || 0} active
            </div>
            {loading && !copyTraders ? <Spinner /> : <CopyTradersPanel data={copyTraders} />}
          </div>
        )}

        {/* ── PERFORMANCE ── */}
        {activeTab === "performance" && (
          <div style={{ background:"rgba(255,255,255,0.03)", border:"1px solid rgba(255,255,255,0.07)", borderRadius:16, padding:24 }}>
            <div style={{ fontSize:13, fontWeight:700, color:"#8A8FA8", marginBottom:20 }}>eToro Monthly & Yearly Gain %</div>
            {loading && !performance ? <Spinner /> : <PerformancePanel data={performance} />}
          </div>
        )}

        {/* ── ANALYTICS ── */}
        {activeTab === "analytics" && (
          <div style={{ display:"grid", gap:20 }}>
            {loading && !brokers.length ? <Spinner /> : (
              <>
                {/* P&L bars */}
                <div style={{ background:"rgba(255,255,255,0.03)", border:"1px solid rgba(255,255,255,0.07)", borderRadius:16, padding:24 }}>
                  <div style={{ fontSize:13, fontWeight:700, color:"#8A8FA8", marginBottom:20 }}>P&L by Broker (INR)</div>
                  {!brokers.length ? <EmptyState /> : (
                    <div style={{ display:"flex", flexDirection:"column", gap:14 }}>
                      {[...brokers].sort((a,b) => b.total_pnl - a.total_pnl).map(b => {
                        const maxPnl = Math.max(...brokers.map(x => Math.abs(toINR(x.total_pnl, x.currency))));
                        const pnlINR = toINR(b.total_pnl, b.currency);
                        const w = maxPnl ? (Math.abs(pnlINR) / maxPnl * 100).toFixed(1) : 0;
                        const color = BROKER_COLORS[b.broker] || "#4F8EF7";
                        return (
                          <div key={b.broker}>
                            <div style={{ display:"flex", justifyContent:"space-between", marginBottom:5, fontSize:12 }}>
                              <span style={{ color:"#B0B4C4" }}>{b.broker}</span>
                              <span style={{ fontFamily:"'DM Mono',monospace", fontWeight:700, color: clr(pnlINR) }}>
                                {pnlINR >= 0 ? "+" : ""}{fmtINR(pnlINR)} ({fmtPct(b.total_pnl_percent)})
                              </span>
                            </div>
                            <div style={{ height:8, background:"rgba(255,255,255,0.06)", borderRadius:4, overflow:"hidden" }}>
                              <div style={{ height:"100%", width:`${w}%`, background: clr(pnlINR), borderRadius:4, transition:"width 1s ease" }} />
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>

                {/* Top winners / losers */}
                {allHoldings.length > 0 && (
                  <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:16 }}>
                    {[
                      { title:"🏆 Top Winners", items:[...filteredHoldings].sort((a,b)=>b.pnl_percent-a.pnl_percent).slice(0,6) },
                      { title:"📉 Top Losers",  items:[...filteredHoldings].sort((a,b)=>a.pnl_percent-b.pnl_percent).slice(0,6) },
                    ].map(({ title, items }) => (
                      <div key={title} style={{ background:"rgba(255,255,255,0.03)", border:"1px solid rgba(255,255,255,0.07)", borderRadius:16, padding:22 }}>
                        <div style={{ fontSize:13, fontWeight:700, color:"#8A8FA8", marginBottom:16 }}>{title}</div>
                        {items.map((h, i) => (
                          <div key={i} style={{ display:"flex", justifyContent:"space-between", marginBottom:11, alignItems:"center" }}>
                            <div>
                              <div style={{ fontWeight:700, color:"#E8EAF0", fontSize:13, fontFamily:"'DM Mono',monospace" }}>{h.symbol}</div>
                              <div style={{ fontSize:11, color:"#5A5F78" }}>{h.broker}</div>
                            </div>
                            <span style={{ fontSize:12, padding:"3px 10px", borderRadius:20, fontWeight:700, fontFamily:"'DM Mono',monospace",
                              background: h.pnl_percent >= 0 ? "#00C7B115" : "#FF6B6B15",
                              color: clr(h.pnl_percent), border:`1px solid ${clr(h.pnl_percent)}30` }}>
                              {fmtPct(h.pnl_percent)}
                            </span>
                          </div>
                        ))}
                      </div>
                    ))}
                  </div>
                )}
              </>
            )}
          </div>
        )}

      </div>
    </div>
  );
}
