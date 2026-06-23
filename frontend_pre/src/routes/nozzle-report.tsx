import { createFileRoute, Link } from "@tanstack/react-router"
import { useRef, useState } from "react"
import type { CSSProperties, ReactNode } from "react"

export const Route = createFileRoute("/nozzle-report")({
  component: NozzleReportPage,
})

type ReportResult = {
  message?: string
  report_json?: any
  image_observations?: any[]
  merged_image_observation?: any
  html_path?: string
  pdf_path?: string
  pdf_download_url?: string
  rag_context_preview?: string
}

function toBackendUrl(path?: string) {
  if (!path) return ""
  return path.startsWith("http") ? path : `http://127.0.0.1:8000${path}`
}

function NozzleReportPage() {
  const fileInputRef = useRef<HTMLInputElement | null>(null)

  const [customer, setCustomer] = useState("")
  const [project, setProject] = useState("")
  const [typeOfTest, setTypeOfTest] = useState("")
  const [conditions, setConditions] = useState("")
  const [fuel, setFuel] = useState("")
  const [runtime, setRuntime] = useState("")
  const [injectorNo, setInjectorNo] = useState("")
  const [nozzleType, setNozzleType] = useState("")
  const [seatGeometry, setSeatGeometry] = useState("")
  const [complaint, setComplaint] = useState("")
  const [problemDescription, setProblemDescription] = useState("")
  const [reportNo, setReportNo] = useState("")
  const [bmNo, setBmNo] = useState("")
  const [customerNo, setCustomerNo] = useState("")

  const [images, setImages] = useState<File[]>([])
  const [previewUrls, setPreviewUrls] = useState<string[]>([])
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<ReportResult | null>(null)
  const [error, setError] = useState("")

  const handleImagesChange = (files: FileList | null) => {
    if (!files) return

    const fileArray = Array.from(files)

    if (fileArray.length > 10) {
      alert("一次最多上传 10 张图片")
      return
    }

    if (fileArray.length === 0) {
      setImages([])
      setPreviewUrls([])
      return
    }

    previewUrls.forEach((url) => URL.revokeObjectURL(url))

    setImages(fileArray)
    setPreviewUrls(fileArray.map((file) => URL.createObjectURL(file)))
    setError("")
  }

  const handleGenerate = async () => {
    if (images.length === 0) {
      alert("请至少上传一张图片")
      return
    }

    const formData = new FormData()

    images.forEach((file) => {
      formData.append("images", file)
    })

    const appendField = (key: string, value: string) => {
      formData.append(key, value ?? "")
    }

    appendField("customer", customer)
    appendField("project", project)
    appendField("type_of_test", typeOfTest)
    appendField("conditions", conditions)
    appendField("fuel", fuel)
    appendField("runtime", runtime)
    appendField("injector_no", injectorNo)
    appendField("nozzle_type", nozzleType)
    appendField("seat_geometry", seatGeometry)
    appendField("complaint", complaint)
    appendField("problem_description", problemDescription)
    appendField("report_no", reportNo)
    appendField("bm_no", bmNo)
    appendField("customer_no", customerNo)

    console.log("===== FormData 检查开始 =====")
    for (const [key, value] of formData.entries()) {
      console.log(key, value)
    }
    console.log("===== FormData 检查结束 =====")

    setLoading(true)
    setResult(null)
    setError("")

    try {
      const res = await fetch(
        "http://127.0.0.1:8000/api/v1/nozzle-report/generate-from-images",
        {
          method: "POST",
          body: formData,
        },
      )

      const text = await res.text()
      console.log("后端原始返回：", text)

      if (!res.ok) {
        throw new Error(text || `请求失败，状态码：${res.status}`)
      }

      let data: ReportResult

      try {
        data = JSON.parse(text)
      } catch {
        throw new Error("后端返回的不是合法 JSON：" + text)
      }

      console.log("接口 JSON 返回：", data)

      setResult(data)

      if (data.html_path) {
        const htmlUrl = toBackendUrl(data.html_path)
        window.open(htmlUrl, "_blank")
      }

      // 不自动打开 PDF，避免浏览器拦截多个弹窗。
      // PDF 下载入口会显示在生成结果区域。
    } catch (err: any) {
      const message = err?.message || "未知错误"
      console.error("生成失败：", err)
      setError(message)
      alert("生成失败：" + message)
    } finally {
      setLoading(false)
    }
  }

  const report = result?.report_json

  return (
    <div style={pageStyle}>
      <div style={shellStyle}>
        <header style={headerStyle}>
          <div>
            <Link to="/" style={backLinkStyle}>
              ← 返回首页
            </Link>
            <h1 style={titleStyle}>Nozzle Investigation</h1>
            <p style={subtitleStyle}>油嘴检测报告生成系统</p>
          </div>

          <div style={statusCardStyle}>
            <div style={statusLabelStyle}>当前状态</div>
            <div style={statusValueStyle}>
              {loading ? "AI 分析中" : result ? "已生成" : "待上传"}
            </div>
          </div>
        </header>

        <section style={panelStyle}>
          <div style={sectionHeaderStyle}>
            <div>
              <h2 style={sectionTitleStyle}>基础信息</h2>
              <p style={sectionDescStyle}>
                填写客户、项目、试验条件和问题描述，用于生成结构化检测报告。
              </p>
            </div>
            <span style={tagStyle}>Step 1</span>
          </div>

          <div style={gridStyle}>
            <Field label="Customer 客户" value={customer} onChange={setCustomer} />
            <Field label="Project 项目" value={project} onChange={setProject} />
            <Field label="Type of test 试验类型" value={typeOfTest} onChange={setTypeOfTest} />
            <Field label="Conditions 工况" value={conditions} onChange={setConditions} />
            <Field label="Fuel 燃油" value={fuel} onChange={setFuel} />
            <Field label="Runtime 运行时间" value={runtime} onChange={setRuntime} />
            <Field label="Injector No. 喷油器号" value={injectorNo} onChange={setInjectorNo} />
            <Field label="Nozzle type 油嘴类型" value={nozzleType} onChange={setNozzleType} />
            <Field label="Seat geometry 座面" value={seatGeometry} onChange={setSeatGeometry} />
            <Field label="Complaint 抱怨" value={complaint} onChange={setComplaint} />
            <Field label="Report No." value={reportNo} onChange={setReportNo} />
            <Field label="BM-No." value={bmNo} onChange={setBmNo} />
            <Field label="Customer-No." value={customerNo} onChange={setCustomerNo} />
          </div>

          <div style={{ marginTop: 22 }}>
            <label style={labelStyle}>Problem description 问题描述</label>
            <textarea
              value={problemDescription}
              onChange={(e) => setProblemDescription(e.target.value)}
              placeholder="例如：疑似座面磨损、导向段磨损、镀层剥落、积炭等"
              style={textareaStyle}
            />
          </div>
        </section>

        <section style={panelStyle}>
          <div style={sectionHeaderStyle}>
            <div>
              <h2 style={sectionTitleStyle}>图片上传</h2>
              <p style={sectionDescStyle}>
                支持多张油嘴图片，建议上传不同角度、不同区域的清晰图像。
              </p>
            </div>
            <span style={tagStyle}>Step 2</span>
          </div>

          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            multiple
            onChange={(e) => handleImagesChange(e.target.files)}
            style={{ display: "none" }}
          />

          <div
            style={uploadBoxStyle}
            onClick={() => fileInputRef.current?.click()}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                fileInputRef.current?.click()
              }
            }}
          >
            <div style={uploadIconStyle}>＋</div>
            <div>
              <div style={uploadTitleStyle}>点击选择图片</div>
              <div style={uploadDescStyle}>最多 10 张，支持 JPG / PNG / JPEG</div>
            </div>
          </div>

          {previewUrls.length > 0 && (
            <div style={{ marginTop: 22 }}>
              <div style={previewHeaderStyle}>
                <h3 style={{ margin: 0 }}>图片预览</h3>
                <span style={imageCountStyle}>{images.length} 张图片</span>
              </div>

              <div style={previewGridStyle}>
                {previewUrls.map((url, index) => (
                  <div key={url} style={previewCardStyle}>
                    <img
                      src={url}
                      alt={`preview-${index + 1}`}
                      style={previewImageStyle}
                    />
                    <div style={previewCaptionStyle}>
                      <span>Image {index + 1}</span>
                      <span>{images[index]?.name || ""}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div style={actionBarStyle}>
            <button
              type="button"
              onClick={handleGenerate}
              disabled={loading}
              style={{
                ...primaryButtonStyle,
                opacity: loading ? 0.7 : 1,
                cursor: loading ? "not-allowed" : "pointer",
              }}
            >
              {loading ? "生成中，请稍候..." : "生成测试报告"}
            </button>

            <span style={hintStyle}>
              生成前请确认图片清晰、问题描述完整。
            </span>
          </div>

          {error && <pre style={errorStyle}>{error}</pre>}
        </section>

        {result && (
          <section style={panelStyle}>
            <div style={sectionHeaderStyle}>
              <div>
                <h2 style={sectionTitleStyle}>生成结果</h2>
                <p style={sectionDescStyle}>
                  以下内容由图像分析、历史知识库和报告模板综合生成。
                </p>
              </div>
              <span style={successTagStyle}>Completed</span>
            </div>

            <div style={downloadBoxStyle}>
              <div>
                <strong>报告文件</strong>
                <p style={{ margin: "6px 0 0", color: "#64748b", fontSize: 13 }}>
                  HTML 用于在线查看，PDF 用于下载归档。
                </p>
              </div>

              <div style={downloadActionsStyle}>
                {result.html_path && (
                  <a
                    href={toBackendUrl(result.html_path)}
                    target="_blank"
                    rel="noreferrer"
                    style={secondaryDownloadButtonStyle}
                  >
                    打开 HTML 报告
                  </a>
                )}

                {(result.pdf_path || result.pdf_download_url) && (
                  <a
                    href={toBackendUrl(result.pdf_path || result.pdf_download_url)}
                    target="_blank"
                    rel="noreferrer"
                    style={downloadButtonStyle}
                  >
                    下载 PDF 报告
                  </a>
                )}

                {!result.pdf_path && !result.pdf_download_url && (
                  <span style={pdfMissingStyle}>
                    后端暂未返回 PDF 地址，请检查 pdf_path 或 pdf_download_url 是否返回。
                  </span>
                )}
              </div>
            </div>

            <ResultBlock title="图片综合分析">
              <pre style={preStyle}>
                {JSON.stringify(result.merged_image_observation ?? "-", null, 2)}
              </pre>
            </ResultBlock>

            {report && (
              <div style={reportCardStyle}>
                <h2 style={reportTitleStyle}>
                  {report.report_meta?.report_title || "Nozzle investigation 油嘴检测报告"}
                </h2>

                <Section title="Basic Information 基本信息">
                  <InfoTable data={report.test_basic_info} />
                </Section>

                <Section title="1. Job-/Problem explanation 任务/问题描述">
                  <p>
                    <b>EN:</b> {report.job_problem_explanation?.description_en || "-"}
                  </p>
                  <p>
                    <b>CN:</b> {report.job_problem_explanation?.description_cn || "-"}
                  </p>
                </Section>

                <Section title="2. Responsible departments 责任部门">
                  <List title="EN" items={report.responsible_departments?.departments_en} />
                  <List title="CN" items={report.responsible_departments?.departments_cn} />
                </Section>

                <Section title="3. Investigation results 检测结果">
                  <h4>Image Analysis 图片分析</h4>
                  <InfoTable data={report.image_analysis} />

                  <h4>Results 结果</h4>
                  <InfoTable data={report.investigation_results} />

                  <h4>Measured values 测量结果</h4>
                  <InfoTable data={report.measured_values} />
                </Section>

                <Section title="3.2 Conclusion 结论">
                  <InfoTable data={report.conclusion} />
                </Section>

                <Section title="3.3 Parts 零件">
                  <InfoTable data={report.parts} />
                </Section>

                <Section title="4-8 Measures 措施">
                  <InfoTable data={report.measures} />
                </Section>

                <Section title="Signatures 签字">
                  <InfoTable data={report.signatures} />
                </Section>

                <details style={{ marginTop: 24 }}>
                  <summary style={summaryStyle}>查看完整 JSON</summary>
                  <pre style={preStyle}>{JSON.stringify(report, null, 2)}</pre>
                </details>
              </div>
            )}

            {result.rag_context_preview && (
              <details style={{ marginTop: 20 }}>
                <summary style={summaryStyle}>知识库检索片段预览</summary>
                <pre style={preStyle}>{result.rag_context_preview}</pre>
              </details>
            )}
          </section>
        )}
      </div>
    </div>
  )
}

function Field({
  label,
  value,
  onChange,
}: {
  label: string
  value: string
  onChange: (v: string) => void
}) {
  return (
    <div>
      <label style={labelStyle}>{label}</label>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        style={inputStyle}
      />
    </div>
  )
}

function Section({
  title,
  children,
}: {
  title: string
  children: ReactNode
}) {
  return (
    <div style={{ marginTop: 26 }}>
      <h3 style={sectionSubTitleStyle}>{title}</h3>
      {children}
    </div>
  )
}

function ResultBlock({
  title,
  children,
}: {
  title: string
  children: ReactNode
}) {
  return (
    <div style={resultBlockStyle}>
      <h3 style={resultBlockTitleStyle}>{title}</h3>
      {children}
    </div>
  )
}

function List({ title, items }: { title: string; items?: any[] }) {
  return (
    <div style={{ marginTop: 10 }}>
      <b>{title}</b>
      {Array.isArray(items) && items.length > 0 ? (
        <ul>
          {items.map((item, index) => (
            <li key={`${title}-${index}`}>{String(item)}</li>
          ))}
        </ul>
      ) : (
        <p>-</p>
      )}
    </div>
  )
}

function InfoTable({ data }: { data: any }) {
  if (!data) return <p>-</p>

  return (
    <div style={tableWrapStyle}>
      <table style={tableStyle}>
        <tbody>
          {Object.entries(data).map(([key, value]) => (
            <tr key={key}>
              <th style={thStyle}>{key}</th>
              <td style={tdStyle}>
                {typeof value === "object" && value !== null ? (
                  <pre style={inlinePreStyle}>{JSON.stringify(value, null, 2)}</pre>
                ) : (
                  String(value ?? "")
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

const pageStyle: CSSProperties = {
  minHeight: "100vh",
  background: "linear-gradient(135deg, #eef3f8 0%, #f7f9fb 45%, #ffffff 100%)",
  padding: "36px 20px 56px",
  boxSizing: "border-box",
  fontFamily: 'Inter, Arial, "Microsoft YaHei", "PingFang SC", sans-serif',
  color: "#172033",
}

const shellStyle: CSSProperties = {
  maxWidth: 1180,
  margin: "0 auto",
}

const headerStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  gap: 24,
  alignItems: "flex-end",
  marginBottom: 24,
}

const backLinkStyle: CSSProperties = {
  display: "inline-block",
  marginBottom: 12,
  color: "#2563eb",
  textDecoration: "none",
  fontSize: 14,
  fontWeight: 600,
}

const titleStyle: CSSProperties = {
  margin: 0,
  fontSize: 38,
  lineHeight: 1.1,
  letterSpacing: "-0.03em",
  fontWeight: 800,
}

const subtitleStyle: CSSProperties = {
  margin: "10px 0 0",
  fontSize: 18,
  color: "#64748b",
}

const statusCardStyle: CSSProperties = {
  minWidth: 150,
  padding: "16px 18px",
  background: "#ffffff",
  borderRadius: 16,
  boxShadow: "0 10px 30px rgba(15, 23, 42, 0.08)",
  border: "1px solid rgba(226, 232, 240, 0.9)",
}

const statusLabelStyle: CSSProperties = {
  fontSize: 12,
  color: "#64748b",
  marginBottom: 6,
}

const statusValueStyle: CSSProperties = {
  fontSize: 18,
  fontWeight: 800,
  color: "#0f766e",
}

const panelStyle: CSSProperties = {
  background: "rgba(255, 255, 255, 0.92)",
  border: "1px solid rgba(226, 232, 240, 0.95)",
  borderRadius: 20,
  padding: 28,
  marginBottom: 22,
  boxShadow: "0 14px 40px rgba(15, 23, 42, 0.07)",
}

const sectionHeaderStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "flex-start",
  gap: 16,
  marginBottom: 22,
}

const sectionTitleStyle: CSSProperties = {
  margin: 0,
  fontSize: 22,
  fontWeight: 800,
}

const sectionDescStyle: CSSProperties = {
  margin: "8px 0 0",
  color: "#64748b",
  fontSize: 14,
  lineHeight: 1.6,
}

const tagStyle: CSSProperties = {
  background: "#eff6ff",
  color: "#2563eb",
  border: "1px solid #bfdbfe",
  borderRadius: 999,
  padding: "6px 12px",
  fontSize: 12,
  fontWeight: 800,
  whiteSpace: "nowrap",
}

const successTagStyle: CSSProperties = {
  ...tagStyle,
  background: "#ecfdf5",
  color: "#047857",
  border: "1px solid #a7f3d0",
}

const gridStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
  gap: 16,
}

const labelStyle: CSSProperties = {
  display: "block",
  fontWeight: 700,
  marginBottom: 8,
  fontSize: 13,
  color: "#334155",
}

const inputStyle: CSSProperties = {
  width: "100%",
  height: 42,
  padding: "0 12px",
  boxSizing: "border-box",
  border: "1px solid #cbd5e1",
  borderRadius: 10,
  outline: "none",
  background: "#ffffff",
  fontSize: 14,
}

const textareaStyle: CSSProperties = {
  width: "100%",
  minHeight: 112,
  padding: 14,
  boxSizing: "border-box",
  border: "1px solid #cbd5e1",
  borderRadius: 12,
  outline: "none",
  resize: "vertical",
  fontSize: 14,
  lineHeight: 1.6,
}

const uploadBoxStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 16,
  border: "2px dashed #93c5fd",
  borderRadius: 16,
  padding: 24,
  background: "#f8fbff",
  cursor: "pointer",
  transition: "all 0.2s ease",
}

const uploadIconStyle: CSSProperties = {
  width: 48,
  height: 48,
  borderRadius: 14,
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  background: "#2563eb",
  color: "#ffffff",
  fontSize: 30,
  lineHeight: 1,
  fontWeight: 300,
}

const uploadTitleStyle: CSSProperties = {
  fontSize: 16,
  fontWeight: 800,
  marginBottom: 4,
}

const uploadDescStyle: CSSProperties = {
  color: "#64748b",
  fontSize: 13,
}

const previewHeaderStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  marginBottom: 12,
}

const imageCountStyle: CSSProperties = {
  color: "#475569",
  fontSize: 13,
  background: "#f1f5f9",
  padding: "5px 10px",
  borderRadius: 999,
}

const previewGridStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fill, minmax(170px, 1fr))",
  gap: 16,
}

const previewCardStyle: CSSProperties = {
  border: "1px solid #e2e8f0",
  borderRadius: 14,
  overflow: "hidden",
  background: "#ffffff",
  boxShadow: "0 6px 18px rgba(15, 23, 42, 0.06)",
}

const previewImageStyle: CSSProperties = {
  width: "100%",
  height: 130,
  objectFit: "cover",
  display: "block",
}

const previewCaptionStyle: CSSProperties = {
  padding: "10px 12px",
  display: "flex",
  flexDirection: "column",
  gap: 4,
  fontSize: 12,
  color: "#64748b",
}

const actionBarStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 16,
  marginTop: 26,
  flexWrap: "wrap",
}

const primaryButtonStyle: CSSProperties = {
  border: "none",
  borderRadius: 12,
  background: "linear-gradient(135deg, #2563eb, #0f766e)",
  color: "#ffffff",
  padding: "12px 26px",
  fontSize: 15,
  fontWeight: 800,
  boxShadow: "0 12px 24px rgba(37, 99, 235, 0.24)",
}

const hintStyle: CSSProperties = {
  color: "#64748b",
  fontSize: 13,
}

const errorStyle: CSSProperties = {
  marginTop: 18,
  padding: 14,
  borderRadius: 12,
  background: "#fef2f2",
  color: "#991b1b",
  border: "1px solid #fecaca",
  whiteSpace: "pre-wrap",
  fontSize: 13,
}

const resultBlockStyle: CSSProperties = {
  border: "1px solid #e2e8f0",
  borderRadius: 16,
  padding: 20,
  background: "#f8fafc",
  marginBottom: 20,
}

const resultBlockTitleStyle: CSSProperties = {
  marginTop: 0,
  fontSize: 18,
  fontWeight: 800,
}

const reportCardStyle: CSSProperties = {
  border: "1px solid #e2e8f0",
  borderRadius: 18,
  padding: 24,
  background: "#ffffff",
}

const reportTitleStyle: CSSProperties = {
  marginTop: 0,
  paddingBottom: 16,
  borderBottom: "1px solid #e2e8f0",
}

const sectionSubTitleStyle: CSSProperties = {
  borderLeft: "4px solid #2563eb",
  paddingLeft: 12,
  marginBottom: 14,
  fontSize: 18,
}

const tableWrapStyle: CSSProperties = {
  overflowX: "auto",
  borderRadius: 12,
  border: "1px solid #e2e8f0",
}

const tableStyle: CSSProperties = {
  width: "100%",
  borderCollapse: "collapse",
  background: "#ffffff",
}

const thStyle: CSSProperties = {
  padding: "12px 14px",
  textAlign: "left",
  width: "260px",
  background: "#f8fafc",
  borderBottom: "1px solid #e2e8f0",
  color: "#334155",
  fontSize: 13,
  verticalAlign: "top",
}

const tdStyle: CSSProperties = {
  padding: "12px 14px",
  borderBottom: "1px solid #e2e8f0",
  color: "#172033",
  fontSize: 13,
  verticalAlign: "top",
}

const preStyle: CSSProperties = {
  background: "#0f172a",
  color: "#e5e7eb",
  padding: 16,
  overflowX: "auto",
  whiteSpace: "pre-wrap",
  borderRadius: 12,
  fontSize: 13,
  lineHeight: 1.6,
}

const inlinePreStyle: CSSProperties = {
  whiteSpace: "pre-wrap",
  margin: 0,
  fontSize: 13,
  lineHeight: 1.5,
}

const summaryStyle: CSSProperties = {
  cursor: "pointer",
  fontWeight: 800,
  color: "#2563eb",
}

const downloadBoxStyle: CSSProperties = {
  marginBottom: 22,
  padding: 18,
  borderRadius: 16,
  background: "#f8fafc",
  border: "1px solid #e2e8f0",
  display: "flex",
  justifyContent: "space-between",
  gap: 18,
  alignItems: "center",
  flexWrap: "wrap",
}

const downloadActionsStyle: CSSProperties = {
  display: "flex",
  gap: 12,
  flexWrap: "wrap",
  alignItems: "center",
}

const downloadButtonStyle: CSSProperties = {
  display: "inline-block",
  padding: "12px 18px",
  background: "#2563eb",
  color: "#ffffff",
  borderRadius: 10,
  textDecoration: "none",
  fontWeight: 800,
  boxShadow: "0 8px 18px rgba(37, 99, 235, 0.22)",
}

const secondaryDownloadButtonStyle: CSSProperties = {
  ...downloadButtonStyle,
  background: "#0f766e",
  boxShadow: "0 8px 18px rgba(15, 118, 110, 0.22)",
}

const pdfMissingStyle: CSSProperties = {
  color: "#991b1b",
  background: "#fef2f2",
  border: "1px solid #fecaca",
  borderRadius: 10,
  padding: "10px 12px",
  fontSize: 13,
  fontWeight: 700,
}