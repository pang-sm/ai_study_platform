import { useState } from "react";

const API_BASE = "/api";

export default function AdminLogin({ setPage, setUser, setTip, initialTip = "" }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [adminCode, setAdminCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(initialTip || "");

  const handleSubmit = async () => {
    setError("");
    if (!username.trim() || !password.trim() || !adminCode.trim()) {
      setError("请填写管理员账号、密码和安全码。");
      return;
    }
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/admin/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: username.trim(), password, admin_code: adminCode.trim() }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setError(data.detail || "管理员认证失败，请检查账号、密码或安全码。");
        setPassword(""); setAdminCode("");
        return;
      }
      const loginUser = data.profile || data.user || { username };
      // Save to localStorage
      try {
        localStorage.setItem("ai_study_platform_user", JSON.stringify(loginUser));
      } catch {}
      setUser(loginUser);
      setPage("adminUsageCenter");
    } catch {
      setError("无法连接后端服务。");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      minHeight: "100vh", background: "linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #0f172a 100%)",
      display: "flex", alignItems: "center", justifyContent: "center",
      fontFamily: "system-ui, -apple-system, sans-serif", padding: 24,
    }}>
      <div style={{
        background: "#fff", borderRadius: 20, width: "min(100%, 440px)",
        boxShadow: "0 24px 80px rgba(0,0,0,0.35)", overflow: "hidden",
      }}>
        {/* Header */}
        <div style={{
          background: "linear-gradient(135deg, #1e293b, #334155)",
          padding: "32px 30px 28px", color: "#fff",
        }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", letterSpacing: 1.5, marginBottom: 8 }}>
            管理后台
          </div>
          <h1 style={{ margin: "0 0 8px", fontSize: "1.45rem", fontWeight: 800, letterSpacing: "-0.02em" }}>
            管理员登录
          </h1>
          <p style={{ margin: 0, fontSize: "0.84rem", color: "#94a3b8", lineHeight: 1.55 }}>
            仅限系统管理员访问，用于用户、课程、资料、额度与系统数据管理。
          </p>
        </div>

        {/* Features */}
        <div style={{
          display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10,
          padding: "20px 30px", background: "#f8fafc", borderBottom: "1px solid #e2e8f0",
        }}>
          {[
            { icon: "👥", label: "用户管理" },
            { icon: "📚", label: "课程与资料管理" },
            { icon: "📊", label: "系统数据看板" },
            { icon: "🔐", label: "权限与额度管理" },
          ].map((item) => (
            <div key={item.label} style={{
              display: "flex", alignItems: "center", gap: 8,
              fontSize: "0.8rem", fontWeight: 600, color: "#475569",
            }}>
              <span>{item.icon}</span> {item.label}
            </div>
          ))}
        </div>

        {/* Form */}
        <div style={{ padding: "24px 30px 28px" }}>
          <div style={{ marginBottom: 14 }}>
            <label style={{ display: "block", marginBottom: 5, fontSize: "0.8rem", fontWeight: 700, color: "#334155" }}>管理员账号</label>
            <input
              value={username} onChange={(e) => setUsername(e.target.value)}
              placeholder="输入管理员账号" autoComplete="username"
              style={{
                width: "100%", height: 44, padding: "0 14px", borderRadius: 10,
                border: "1px solid #dce2ec", fontSize: "0.9rem", outline: "none",
                boxSizing: "border-box", fontFamily: "inherit",
              }}
            />
          </div>
          <div style={{ marginBottom: 14 }}>
            <label style={{ display: "block", marginBottom: 5, fontSize: "0.8rem", fontWeight: 700, color: "#334155" }}>管理员密码</label>
            <input
              type="password" value={password} onChange={(e) => setPassword(e.target.value)}
              placeholder="输入管理员密码" autoComplete="current-password"
              style={{
                width: "100%", height: 44, padding: "0 14px", borderRadius: 10,
                border: "1px solid #dce2ec", fontSize: "0.9rem", outline: "none",
                boxSizing: "border-box", fontFamily: "inherit",
              }}
            />
          </div>
          <div style={{ marginBottom: 8 }}>
            <label style={{ display: "block", marginBottom: 5, fontSize: "0.8rem", fontWeight: 700, color: "#334155" }}>管理员安全码</label>
            <input
              type="password" value={adminCode} onChange={(e) => setAdminCode(e.target.value)}
              placeholder="输入管理员安全码"
              style={{
                width: "100%", height: 44, padding: "0 14px", borderRadius: 10,
                border: "1px solid #dce2ec", fontSize: "0.9rem", outline: "none",
                boxSizing: "border-box", fontFamily: "inherit", letterSpacing: 2,
              }}
            />
          </div>

          {error && (
            <div style={{
              marginTop: 6, padding: "10px 14px", borderRadius: 10,
              background: "#fef2f2", border: "1px solid #fecaca",
              color: "#b91c1c", fontSize: "0.82rem", lineHeight: 1.45,
            }}>
              {error}
            </div>
          )}

          <button
            onClick={handleSubmit} disabled={loading}
            style={{
              width: "100%", height: 46, marginTop: 14, borderRadius: 11,
              border: "none", background: loading ? "#64748b" : "#0f172a",
              color: "#fff", fontSize: "0.92rem", fontWeight: 700, cursor: loading ? "not-allowed" : "pointer",
              fontFamily: "inherit", transition: "background 0.15s",
            }}
            onMouseEnter={(e) => { if (!loading) e.currentTarget.style.background = "#1e293b"; }}
            onMouseLeave={(e) => { if (!loading) e.currentTarget.style.background = "#0f172a"; }}
          >
            {loading ? "验证中..." : "进入管理后台"}
          </button>

          <button
            onClick={() => { setPage("login"); }}
            style={{
              width: "100%", height: 40, marginTop: 10, borderRadius: 10,
              border: "none", background: "transparent", color: "#64748b",
              fontSize: "0.82rem", fontWeight: 600, cursor: "pointer",
              fontFamily: "inherit",
            }}
          >
            ← 返回学习端登录
          </button>
        </div>
      </div>
    </div>
  );
}
