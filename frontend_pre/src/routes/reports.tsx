import { createFileRoute } from "@tanstack/react-router"

export const Route = createFileRoute("/reports")({
  component: ReportsPage,
})

function ReportsPage() {
  return (
    <div>
      <h1>历史报告管理</h1>
      <p>这里放历史报告列表。</p>
    </div>
  )
}