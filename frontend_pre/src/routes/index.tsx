import { createFileRoute, Link } from "@tanstack/react-router"

export const Route = createFileRoute("/")({
  component: HomePage,
})

function HomePage() {
  return (
    <div style={styles.body}>
      <div style={styles.container}>
        <h1 style={styles.h1}>Engineering Report System</h1>
        <p style={styles.subtitle}>请选择需要使用的功能：</p>

        <div style={styles.cardList}>
          <Link to="/pd-ecr-form" style={styles.card}>
            <h2 style={styles.cardTitle}>PD-ECR 报告生成</h2>
            <p style={styles.cardDesc}>
              填写工程变更信息，生成 PD-ECR 工程变更报告。
            </p>
          </Link>

          <Link to="/nozzle-report" style={styles.card}>
            <h2 style={styles.cardTitle}>
              Nozzle Investigation 油嘴检测报告
            </h2>
            <p style={styles.cardDesc}>
              上传多张油嘴图片，结合历史知识库生成检测报告。
            </p>
          </Link>

          <Link to="/pdf-upload" style={styles.card}>
            <h2 style={styles.cardTitle}>PDF 文档解析</h2>
            <p style={styles.cardDesc}>
              上传PDF工程报告，自动转换为可编辑的Markdown格式。
            </p>
          </Link>

          <Link to="/reports" style={styles.card}>
            <h2 style={styles.cardTitle}>历史报告管理</h2>
            <p style={styles.cardDesc}>
              查看、下载和管理所有已生成的工程报告。
            </p>
          </Link>
        </div>
      </div>
    </div>
  )
}

const styles = {
  body: {
    fontFamily: 'Arial, "Microsoft YaHei", sans-serif',
    padding: "60px 20px",
    background: "#f7f7f7",
    color: "#222",
    minHeight: "100vh",
    margin: 0,
  },
  container: {
    maxWidth: "800px",
    margin: "0 auto",
    background: "white",
    padding: "40px",
    borderRadius: "12px",
    boxShadow: "0 2px 12px rgba(0, 0, 0, 0.08)",
  },
  h1: {
    marginBottom: "12px",
    fontSize: "28px",
    fontWeight: 600,
  },
  subtitle: {
    color: "#555",
    fontSize: "16px",
    marginBottom: "30px",
  },
  cardList: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))",
    gap: "20px",
  },
  card: {
    border: "1px solid #ddd",
    borderRadius: "10px",
    padding: "24px",
    background: "#fff",
    textDecoration: "none",
    color: "#222",
    transition: "all 0.2s ease",
    cursor: "pointer",
  },
  cardTitle: {
    marginTop: 0,
    fontSize: "20px",
    fontWeight: 600,
    marginBottom: "8px",
  },
  cardDesc: {
    marginBottom: 0,
    fontSize: "14px",
    color: "#666",
    lineHeight: 1.5,
  },
} as const