import React, { useState } from "react";

// 定义报告结构类型
interface ReportJson {
  test_basic_info?: any;
  job_problem_explanation?: any;
  responsible_departments?: any;
  image_analysis?: any;
  investigation_results?: any;
  measured_values?: any;
  conclusion?: any;
  parts?: any;
  measures?: any;
  signatures?: any;
}

function NozzleReportRoute() {
  const [log, setLog] = useState("");
  const [reportData, setReportData] = useState<ReportJson | null>(null);

  async function handleTestClick() {
    setLog("按钮已点击，准备请求后端接口……");
    try {
      // 示例：仅发送空表单，实际应包含图片和表单数据
      const formData = new FormData();
      // 可根据实际需求添加图片和表单字段
      const res = await fetch("/nozzle-report/generate-from-images", {
        method: "POST",
        body: formData,
      });
      const data = await res.json();
      setReportData(data.report_json);
      setLog("报告生成成功！");
    } catch (e) {
      setLog("报告生成失败：" + e);
    }
  }

  return (
    <div style={{ background: "red", color: "white", fontSize: 40, padding: 80 }}>
      Test Nozzle Report Page
      <br />
      <button type="button" onClick={handleTestClick}>点击测试</button>
      <div style={{ marginTop: 20, fontSize: 18 }}>{log}</div>
      {reportData && (
        <div style={{ marginTop: 40, background: "#fff", color: "#333", fontSize: 18, padding: 20 }}>
          <h2>报告分模块展示</h2>
          <div>
            <strong>基本信息：</strong>
            <pre>{JSON.stringify(reportData.test_basic_info, null, 2)}</pre>
          </div>
          <div>
            <strong>问题说明：</strong>
            <pre>{JSON.stringify(reportData.job_problem_explanation, null, 2)}</pre>
          </div>
          <div>
            <strong>责任部门：</strong>
            <pre>{JSON.stringify(reportData.responsible_departments, null, 2)}</pre>
          </div>
          <div>
            <strong>图片分析：</strong>
            <pre>{JSON.stringify(reportData.image_analysis, null, 2)}</pre>
          </div>
          <div>
            <strong>调查结果：</strong>
            <pre>{JSON.stringify(reportData.investigation_results, null, 2)}</pre>
          </div>
          <div>
            <strong>测量值：</strong>
            <pre>{JSON.stringify(reportData.measured_values, null, 2)}</pre>
          </div>
          <div>
            <strong>结论：</strong>
            <pre>{JSON.stringify(reportData.conclusion, null, 2)}</pre>
          </div>
          <div>
            <strong>零件：</strong>
            <pre>{JSON.stringify(reportData.parts, null, 2)}</pre>
          </div>
          <div>
            <strong>措施：</strong>
            <pre>{JSON.stringify(reportData.measures, null, 2)}</pre>
          </div>
          <div>
            <strong>签名：</strong>
            <pre>{JSON.stringify(reportData.signatures, null, 2)}</pre>
          </div>
        </div>
      )}
    </div>
  );
}
