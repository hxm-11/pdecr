import { createFileRoute, useNavigate } from "@tanstack/react-router"
import { useState } from "react"

export const Route = createFileRoute("/pd-ecr-form")({
  component: PdEcrFormPage,
})

function PdEcrFormPage() {
  const navigate = useNavigate()

  const [result, setResult] = useState("")
  const [showResult, setShowResult] = useState(false)
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()

    const form = e.currentTarget
    const formData = new FormData(form)

    const data = {
      dc_no: formData.get("dc_no") || "",
      date: formData.get("date") || "",
      customer_project: formData.get("customer_project") || "",
      mcr_no: formData.get("mcr_no") || "",
      product_no: formData.get("product_no") || "",
      component_no: formData.get("component_no") || "",
      initiator: formData.get("initiator") || "",
      reason: formData.get("reason") || "",
      current_design: formData.get("current_design") || "",
      change_proposal: formData.get("change_proposal") || "",
      remarks: formData.get("remarks") || "",
    }

    if (!data.dc_no) {
      setShowResult(true)
      setResult("请先填写 DC No.，否则报告文件名会变成 report_unknown.html。")
      return
    }

    setShowResult(true)
    setResult("正在生成报告，请稍等...")
    setLoading(true)

    try {
      const response = await fetch(
        "http://127.0.0.1:8000/api/v1/pd-ecr/generate-report",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(data),
        },
      )

      const text = await response.text()

      let resultData: any
      try {
        resultData = JSON.parse(text)
      } catch {
        resultData = text
      }

      if (!response.ok) {
        setResult(
          `生成失败：\n\n${
            typeof resultData === "object"
              ? JSON.stringify(resultData, null, 2)
              : resultData
          }`,
        )
        return
      }

      if (typeof resultData === "object" && resultData.url) {
        sessionStorage.setItem("pd_ecr_report_data", JSON.stringify(resultData))
        sessionStorage.setItem("pd_ecr_submitted_data", JSON.stringify(data))

        navigate({
          to: "/pd-ecr-modules",
        })

        return
      }

      setResult(
        `生成成功，但是后端没有返回 url：\n\n${
          typeof resultData === "object"
            ? JSON.stringify(resultData, null, 2)
            : resultData
        }`,
      )
    } catch (error) {
      setResult(
        `生成报告失败，请检查后端是否启动，或查看浏览器 F12 Console。\n\n${error}`,
      )
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={styles.page}>
      <div style={styles.container}>
        <div style={styles.boschHeader}>BOSCH</div>

        <div style={styles.mainTitle}>
          Development Changes in PD-Phase
          <br />
          产品开发变更
        </div>

        <div style={styles.grey}>Confidential</div>

        <form onSubmit={handleSubmit}>
          <table style={styles.table}>
            <tbody>
              <tr>
                <td style={styles.td} colSpan={2}>
                  Affected domain / 影响的开发域
                </td>

                <td style={styles.td} colSpan={6}>
                  <label>
                    <input type="checkbox" name="domain_sys" /> sys
                  </label>{" "}
                  <label>
                    <input type="checkbox" name="domain_me" /> ME
                  </label>{" "}
                  <label>
                    <input type="checkbox" name="domain_hw" /> HW
                  </label>
                </td>

                <td style={styles.td}>
                  DC No.
                  <br />
                  开发更改单号
                </td>

                <td style={styles.td}>
                  <input type="text" name="dc_no" style={{ width: 120 }} />
                </td>

                <td style={styles.td}>
                  Date
                  <br />
                  日期
                </td>

                <td style={styles.td}>
                  <input type="date" name="date" />
                </td>
              </tr>

              <tr>
                <td style={{ ...styles.td, ...styles.section }} colSpan={12}>
                  Step 1: Change request & Basic information
                </td>
              </tr>

              <tr>
                <td style={styles.td} colSpan={2}>
                  Customer project Name
                  <br />
                  客户项目名称
                </td>

                <td style={styles.td} colSpan={3}>
                  <input
                    type="text"
                    name="customer_project"
                    style={{ width: 180 }}
                  />
                </td>

                <td style={styles.td}>
                  MCR No.
                  <br />
                  MCR号
                </td>

                <td style={styles.td}>
                  <input type="text" name="mcr_no" style={{ width: 90 }} />
                </td>

                <td style={styles.td}>
                  Product No.
                  <br />
                  产品号
                </td>

                <td style={styles.td}>
                  <input type="text" name="product_no" style={{ width: 90 }} />
                </td>

                <td style={styles.td}>
                  Component No.
                  <br />
                  部件号
                </td>

                <td style={styles.td} colSpan={2}>
                  <input
                    type="text"
                    name="component_no"
                    style={{ width: 100 }}
                  />
                </td>
              </tr>

              <tr>
                <td style={styles.td}>
                  Sample type
                  <br />
                  样品类型
                </td>

                <td style={styles.td} colSpan={4}>
                  <label>
                    <input type="radio" name="sample_type" value="A" /> A
                  </label>{" "}
                  <label>
                    <input type="radio" name="sample_type" value="B" /> B
                  </label>{" "}
                  <label>
                    <input type="radio" name="sample_type" value="C" /> C
                  </label>{" "}
                  <label>
                    <input type="radio" name="sample_type" value="FD" /> FD
                  </label>
                </td>

                <td style={styles.td}>
                  Initiator
                  <br />
                  发起人
                </td>

                <td style={styles.td} colSpan={2}>
                  <input type="text" name="initiator" style={{ width: 120 }} />
                </td>

                <td style={styles.td} colSpan={3}>
                  Reason of changes
                  <br />
                  更改理由
                </td>

                <td style={styles.td} colSpan={2}>
                  <input type="text" name="reason" style={{ width: 150 }} />
                </td>
              </tr>

              <tr>
                <td style={styles.td} colSpan={12}>
                  Customer request / 客户要求{" "}
                  <input type="checkbox" name="customer_request" /> Supplier
                  request / 供应商请求{" "}
                  <input type="checkbox" name="supplier_request" /> Design
                  optimization / 设计优化{" "}
                  <input type="checkbox" name="design_optimization" />{" "}
                  Correction / 更正{" "}
                  <input type="checkbox" name="correction" /> Process / 工艺{" "}
                  <input type="checkbox" name="process" /> Other / 其它{" "}
                  <input type="checkbox" name="other" />
                </td>
              </tr>

              <tr>
                <td style={{ ...styles.td, ...styles.section }} colSpan={12}>
                  Step 2: Change proposal & Change description
                </td>
              </tr>

              <tr>
                <td style={styles.td} colSpan={4}>
                  当前设计 Current design
                  <br />
                  <textarea
                    name="current_design"
                    rows={5}
                    style={{ width: "95%" }}
                  />
                </td>

                <td style={styles.td} colSpan={4}>
                  更改建议 Change proposal
                  <br />
                  <textarea
                    name="change_proposal"
                    rows={5}
                    style={{ width: "95%" }}
                  />
                </td>

                <td style={styles.td} colSpan={4}>
                  备注 Remarks
                  <br />
                  <textarea name="remarks" rows={5} style={{ width: "95%" }} />
                </td>
              </tr>
            </tbody>
          </table>

          <div style={styles.center}>
            <button type="submit" style={styles.button} disabled={loading}>
              {loading ? "生成中..." : "生成报告"}
            </button>
          </div>
        </form>

        {showResult && <pre style={styles.resultBox}>{result}</pre>}
      </div>
    </div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  page: {
    fontFamily: '"Microsoft YaHei", Arial, sans-serif',
    background: "#fafafa",
    minHeight: "100vh",
    padding: "24px 0",
  },

  container: {
    width: "82%",
    margin: "auto",
  },

  boschHeader: {
    color: "#d40000",
    fontWeight: "bold",
    fontSize: 24,
  },

  mainTitle: {
    fontSize: 20,
    fontWeight: "bold",
  },

  grey: {
    color: "#888",
  },

  table: {
    borderCollapse: "collapse",
    width: "80%",
    margin: "30px auto",
    background: "#fff",
  },

  td: {
    border: "1px solid #666",
    padding: 8,
    fontSize: 14,
    verticalAlign: "middle",
  },

  section: {
    background: "#e6eef8",
    fontWeight: "bold",
  },

  center: {
    textAlign: "center",
    margin: 24,
  },

  button: {
    cursor: "pointer",
    fontSize: 18,
    padding: "6px 36px",
  },

  resultBox: {
    width: "80%",
    margin: "20px auto",
    padding: 12,
    background: "#fff",
    border: "1px solid #ccc",
    whiteSpace: "pre-wrap",
  },
}