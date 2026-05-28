import { Component } from "react";

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, errorInfo) {
    this.setState({ errorInfo });
    console.error("[ErrorBoundary] React render error:", error, errorInfo);
  }

  render() {
    if (this.state.error) {
      return (
        <div style={{
          padding: "40px 24px",
          maxWidth: 640,
          margin: "60px auto",
          fontFamily: "system-ui, -apple-system, sans-serif",
          background: "#fef2f2",
          border: "1px solid #fecaca",
          borderRadius: 12,
        }}>
          <h2 style={{ color: "#991b1b", margin: "0 0 8px" }}>页面加载异常</h2>
          <p style={{ color: "#7f1d1d", margin: "0 0 16px", lineHeight: 1.6 }}>
            页面渲染时发生了错误，请尝试刷新页面。如果问题持续存在，请联系管理员。
          </p>
          <details style={{ cursor: "pointer" }}>
            <summary style={{ color: "#991b1b", fontWeight: 600 }}>错误详情</summary>
            <pre style={{
              marginTop: 12,
              padding: 12,
              background: "#fff",
              border: "1px solid #fecaca",
              borderRadius: 8,
              fontSize: 13,
              overflow: "auto",
              whiteSpace: "pre-wrap",
              wordBreak: "break-word",
              color: "#7f1d1d",
            }}>
              {String(this.state.error?.message || this.state.error || "未知错误")}
              {"\n\n"}
              {this.state.errorInfo?.componentStack || ""}
            </pre>
          </details>
        </div>
      );
    }

    return this.props.children;
  }
}
