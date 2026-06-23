import { createFileRoute } from "@tanstack/react-router"

export const Route = createFileRoute("/pdf-upload")({
  component: PdfUploadPage,
})

function PdfUploadPage() {
  return (
    <div>
      <h1>PDF 文档解析</h1>
      <p>这里放你的 PDF 上传解析功能。</p>
    </div>
  )
}