import { createFileRoute, Link } from "@tanstack/react-router"
import { useEffect, useState } from "react"

export const Route = createFileRoute("/pd-ecr-modules")({
  component: PdEcrModulesPage,
})

type ActiveModule = "basic" | "change" | "analysis" | "final"

function PdEcrModulesPage() {
  const [reportData, setReportData] = useState<any>(null)
  const [submittedData, setSubmittedData] = useState<any>(null)
  const [activeModule, setActiveModule] = useState<ActiveModule>("basic")
  const [error, setError] = useState("")

  useEffect(() => {
    const reportRaw = sessionStorage.getItem("pd_ecr_report_data")
    const submittedRaw = sessionStorage.getItem("pd_ecr_submitted_data")

    if (!reportRaw || !submittedRaw) {
      setError("没有找到报告数据。请先返回表单页面生成报告。")
      return
    }

    try {
      const report = JSON.parse(reportRaw)
      const submitted = JSON.parse(submittedRaw)

      setReportData(report)
      setSubmittedData(submitted)
    } catch (err) {
      console.error(err)
      setError("报告数据解析失败，请重新生成报告。")
    }
  }, [])

  if (error) {
    return (
      <div style={styles.page}>
        <div style={styles.card}>
          <h1 style={styles.title}>PD-ECR 模块化报告</h1>
          <p style={styles.error}>{error}</p>

          <Link to="/pd-ecr-form" style={styles.backLink}>
            返回表单页面
          </Link>
        </div>
      </div>
    )
  }

  if (!reportData || !submittedData) {
    return (
      <div style={styles.page}>
        <div style={styles.card}>
          <h1 style={styles.title}>PD-ECR 模块化报告</h1>
          <p>正在加载报告数据...</p>
        </div>
      </div>
    )
  }

  const llm = reportData.llm_result || {}

  return (
    <div style={styles.page}>
      <div style={styles.header}>
        <div>
          <div style={styles.bosch}>BOSCH</div>
          <h1 style={styles.mainTitle}>PD-ECR 模块化报告</h1>
          <div style={styles.subTitle}>Development Changes in PD-Phase</div>
        </div>

        <div>
          <Link to="/pd-ecr-form" style={styles.secondaryButton}>
            返回表单
          </Link>

          {reportData.url && (
            <a
              href={`http://127.0.0.1:8000${reportData.url}`}
              target="_blank"
              rel="noreferrer"
              style={styles.primaryButton}
            >
              打开完整报告
            </a>
          )}
        </div>
      </div>

      <div style={styles.moduleArea}>
        <div style={styles.moduleTabs}>
          <button
            type="button"
            onClick={() => setActiveModule("basic")}
            style={{
              ...styles.moduleTab,
              ...(activeModule === "basic" ? styles.activeTab : {}),
            }}
          >
            1. 基础信息
          </button>

          <button
            type="button"
            onClick={() => setActiveModule("change")}
            style={{
              ...styles.moduleTab,
              ...(activeModule === "change" ? styles.activeTab : {}),
            }}
          >
            2. 变更说明
          </button>

          <button
            type="button"
            onClick={() => setActiveModule("analysis")}
            style={{
              ...styles.moduleTab,
              ...(activeModule === "analysis" ? styles.activeTab : {}),
            }}
          >
            3. 工程分析
          </button>

          <button
            type="button"
            onClick={() => setActiveModule("final")}
            style={{
              ...styles.moduleTab,
              ...(activeModule === "final" ? styles.activeTab : {}),
            }}
          >
            4. 最终报告
          </button>
        </div>

        <div style={styles.moduleContent}>
          {activeModule === "basic" && (
            <div>
              <h2 style={styles.moduleTitle}>基础信息</h2>

              <table style={styles.moduleTable}>
                <tbody>
                  <ModuleRow label="DC No." value={submittedData.dc_no} />
                  <ModuleRow label="Date" value={submittedData.date} />
                  <ModuleRow
                    label="Customer / Project"
                    value={submittedData.customer_project}
                  />
                  <ModuleRow label="MCR No." value={submittedData.mcr_no} />
                  <ModuleRow
                    label="Product No."
                    value={submittedData.product_no}
                  />
                  <ModuleRow
                    label="Component No."
                    value={submittedData.component_no}
                  />
                  <ModuleRow
                    label="Initiator"
                    value={submittedData.initiator}
                  />
                </tbody>
              </table>
            </div>
          )}

          {activeModule === "change" && (
            <div>
              <h2 style={styles.moduleTitle}>变更说明</h2>

              <table style={styles.moduleTable}>
                <tbody>
                  <ModuleRow
                    label="Reason of Change"
                    value={submittedData.reason}
                  />
                  <ModuleRow
                    label="Current Design"
                    value={submittedData.current_design}
                  />
                  <ModuleRow
                    label="Change Proposal"
                    value={submittedData.change_proposal}
                  />
                  <ModuleRow label="Remarks" value={submittedData.remarks} />
                </tbody>
              </table>
            </div>
          )}

          {activeModule === "analysis" && (
            <div>
              <h2 style={styles.moduleTitle}>工程分析与验证</h2>

              <SectionBlock
                title="Engineering Analysis"
                value={llm.engineering_analysis}
              />

              <SectionBlock title="Impact Analysis" value={llm.impact_analysis} />

              <SectionBlock
                title="Impact Description"
                value={llm.impact_description}
              />

              <SectionBlock title="Risk Analysis" value={llm.risk_analysis} />

              <SectionBlock
                title="Verification Plan"
                value={llm.verification_plan}
              />

              <SectionBlock
                title="Implementation Plan"
                value={llm.implementation_plan}
              />

              <h3>Impact Template</h3>
              <pre style={styles.modulePre}>
                {reportData.impact || "暂无 Impact 内容"}
              </pre>

              <h3>Implementation Template</h3>
              <pre style={styles.modulePre}>
                {reportData.implementation || "暂无 Implementation 内容"}
              </pre>

              <h3>关键检查项</h3>
              <table style={styles.moduleTable}>
                <tbody>
                  <ModuleRow
                    label="Function / Performance"
                    value={llm.function_performance_value}
                  />
                  <ModuleRow
                    label="Interface / Appearance"
                    value={llm.interface_appearance_value}
                  />
                  <ModuleRow
                    label="Reliability / Robustness"
                    value={llm.reliability_robustness_value}
                  />
                  <ModuleRow
                    label="Other Components"
                    value={llm.other_components_value}
                  />
                  <ModuleRow
                    label="Manufacturing / Assembly / Testing"
                    value={llm.manufacturing_assembly_testing_value}
                  />
                  <ModuleRow
                    label="Supplier Part"
                    value={llm.supplier_part_value}
                  />
                  <ModuleRow
                    label="System / HW / SW / Calibration / Mechanical"
                    value={llm.system_hw_sw_calibration_mechanical_value}
                  />
                </tbody>
              </table>

              <h3>Quality Assurance Items</h3>
              <table style={styles.moduleTable}>
                <tbody>
                  <ModuleRow label="Trial Run" value={llm.trial_run_value} />
                  <ModuleRow label="CMK" value={llm.capability_cmk_value} />
                  <ModuleRow label="MSA" value={llm.capability_msa_value} />
                  <ModuleRow label="MAE Release" value={llm.mae_release_value} />
                  <ModuleRow
                    label="Cleanness Test"
                    value={llm.cleanness_test_value}
                  />
                  <ModuleRow label="QZ Test" value={llm.qz_test_value} />
                  <ModuleRow label="PDL 200h" value={llm.pdl_200h_value} />
                  <ModuleRow label="BOM Check" value={llm.bom_check_value} />
                  <ModuleRow
                    label="Test Report"
                    value={llm.test_report_value}
                  />
                  <ModuleRow label="PAV Release" value={llm.pav_release_value} />
                </tbody>
              </table>
            </div>
          )}

          {activeModule === "final" && (
            <div>
              <h2 style={styles.moduleTitle}>最终报告与审批</h2>

              <h3>审批签字人</h3>
              <table style={styles.moduleTable}>
                <tbody>
                  <ModuleRow
                    label="Development"
                    value={llm.approval_development_person}
                  />
                  <ModuleRow
                    label="Purchasing"
                    value={llm.approval_purchasing_person}
                  />
                  <ModuleRow label="MFE" value={llm.approval_mfe_person} />
                  <ModuleRow label="COS" value={llm.approval_cos_person} />
                  <ModuleRow
                    label="Quality"
                    value={llm.approval_quality_person}
                  />
                  <ModuleRow label="CPjM" value={llm.approval_cpjm_person} />
                  <ModuleRow label="MOEx" value={llm.approval_moex_person} />
                  <ModuleRow label="LOG" value={llm.approval_log_person} />
                  <ModuleRow label="Other" value={llm.approval_other_person} />
                </tbody>
              </table>

              <h3>Revision History</h3>
              <pre style={styles.modulePre}>
                {reportData.revision_history || "暂无 Revision History 内容"}
              </pre>

              <h3>Example of Affected Actions</h3>
              <pre style={styles.modulePre}>
                {reportData.example_of_affected_actions ||
                  "暂无 Affected Actions 内容"}
              </pre>

              {reportData.url && (
                <a
                  href={`http://127.0.0.1:8000${reportData.url}`}
                  target="_blank"
                  rel="noreferrer"
                  style={styles.reportLink}
                >
                  打开完整 HTML 报告
                </a>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function ModuleRow({ label, value }: { label: string; value: any }) {
  return (
    <tr>
      <td style={styles.moduleLabel}>{label}</td>
      <td style={styles.moduleValue}>{value || "未填写"}</td>
    </tr>
  )
}

function SectionBlock({ title, value }: { title: string; value: any }) {
  return (
    <div style={styles.sectionBlock}>
      <h3>{title}</h3>
      <pre style={styles.modulePre}>{value || "暂无内容"}</pre>
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

  header: {
    width: "82%",
    margin: "0 auto 24px auto",
    background: "#fff",
    border: "1px solid #ddd",
    padding: "20px 24px",
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
  },

  bosch: {
    color: "#d40000",
    fontWeight: "bold",
    fontSize: 26,
  },

  mainTitle: {
    margin: "6px 0",
    fontSize: 24,
  },

  subTitle: {
    color: "#666",
  },

  card: {
    width: "80%",
    margin: "40px auto",
    background: "#fff",
    border: "1px solid #ddd",
    padding: 24,
  },

  title: {
    color: "#d40000",
  },

  error: {
    color: "#d40000",
    fontWeight: "bold",
  },

  backLink: {
    display: "inline-block",
    marginTop: 20,
    color: "#d40000",
    textDecoration: "none",
    fontWeight: "bold",
  },

  primaryButton: {
    display: "inline-block",
    marginLeft: 12,
    padding: "10px 18px",
    background: "#d40000",
    color: "#fff",
    textDecoration: "none",
    borderRadius: 4,
  },

  secondaryButton: {
    display: "inline-block",
    padding: "10px 18px",
    background: "#f3f3f3",
    color: "#333",
    textDecoration: "none",
    borderRadius: 4,
    border: "1px solid #ccc",
  },

  moduleArea: {
    width: "82%",
    margin: "30px auto",
    background: "#fff",
    border: "1px solid #ccc",
  },

  moduleTabs: {
    display: "flex",
    borderBottom: "1px solid #ccc",
    background: "#f3f3f3",
  },

  moduleTab: {
    flex: 1,
    padding: "14px",
    border: "none",
    borderRight: "1px solid #ccc",
    background: "#f3f3f3",
    fontWeight: "bold",
    cursor: "pointer",
  },

  activeTab: {
    background: "#d40000",
    color: "#fff",
  },

  moduleContent: {
    padding: "24px",
    minHeight: "420px",
  },

  moduleTitle: {
    marginTop: 0,
    color: "#d40000",
  },

  moduleTable: {
    width: "100%",
    margin: "12px 0 24px 0",
    borderCollapse: "collapse",
  },

  moduleLabel: {
    width: "280px",
    background: "#eef2f7",
    fontWeight: "bold",
    border: "1px solid #ccc",
    padding: "9px",
    verticalAlign: "top",
  },

  moduleValue: {
    border: "1px solid #ccc",
    padding: "9px",
    whiteSpace: "pre-wrap",
    wordBreak: "break-word",
  },

  modulePre: {
    whiteSpace: "pre-wrap",
    wordBreak: "break-word",
    background: "#f7f7f7",
    border: "1px solid #ddd",
    padding: "12px",
    fontFamily: 'Consolas, "Microsoft YaHei", monospace',
    minHeight: 40,
  },

  sectionBlock: {
    marginBottom: 18,
  },

  reportLink: {
    display: "inline-block",
    marginTop: "16px",
    padding: "10px 20px",
    background: "#d40000",
    color: "#fff",
    textDecoration: "none",
    borderRadius: "4px",
  },
}