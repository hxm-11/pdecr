import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"

import {
  createProjectStage,
  deleteProjectStage,
  getProjectStages,
  type ProjectStage,
  updateProjectStage,
} from "@/lib/stageApi"

export const Route = createFileRoute("/_layout/projects/$projectId")({
  component: ProjectDetailPage,
})

function getStatusText(status: string) {
  const map: Record<string, string> = {
    not_started: "未开始",
    in_progress: "进行中",
    completed: "已完成",
    blocked: "阻塞",
  }

  return map[status] || status
}

function ProjectDetailPage() {
  const { projectId } = Route.useParams()
  const queryClient = useQueryClient()

  const [showForm, setShowForm] = useState(false)
  const [editingStage, setEditingStage] = useState<ProjectStage | null>(null)

  const [form, setForm] = useState({
    name: "",
    description: "",
    order_index: 0,
    status: "not_started",
    progress: 0,
  })

  const {
    data: stages = [],
    isLoading,
    isError,
  } = useQuery({
    queryKey: ["project-stages", projectId],
    queryFn: () => getProjectStages(projectId),
    refetchInterval: 5000,
  })

  const saveMutation = useMutation({
    mutationFn: async () => {
      if (!form.name.trim()) {
        throw new Error("阶段名称不能为空")
      }

      if (editingStage) {
        return updateProjectStage(editingStage.id, {
          name: form.name,
          description: form.description,
          order_index: Number(form.order_index),
          status: form.status,
          progress: Number(form.progress),
        })
      }

      return createProjectStage({
        project_id: projectId,
        name: form.name,
        description: form.description,
        order_index: Number(form.order_index),
        status: form.status,
        progress: Number(form.progress),
      })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["project-stages", projectId] })
      setShowForm(false)
      setEditingStage(null)
      setForm({
        name: "",
        description: "",
        order_index: 0,
        status: "not_started",
        progress: 0,
      })
      alert("保存成功")
    },
    onError: (error) => {
      alert(error instanceof Error ? error.message : "保存失败")
    },
  })

  const deleteMutation = useMutation({
    mutationFn: deleteProjectStage,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["project-stages", projectId] })
      alert("删除成功")
    },
    onError: () => {
      alert("删除失败")
    },
  })

  const handleCreateDefaultStages = async () => {
    const defaultStages = [
      "工业设计",
      "仿真分析",
      "采购准备",
      "加工制造",
      "测试验证",
      "交付验收",
    ]

    for (let i = 0; i < defaultStages.length; i++) {
      await createProjectStage({
        project_id: projectId,
        name: defaultStages[i],
        order_index: i + 1,
        status: i === 0 ? "in_progress" : "not_started",
        progress: i === 0 ? 10 : 0,
      })
    }

    queryClient.invalidateQueries({ queryKey: ["project-stages", projectId] })
    alert("默认流程已创建")
  }

  const handleEdit = (stage: ProjectStage) => {
    setEditingStage(stage)
    setForm({
      name: stage.name,
      description: stage.description || "",
      order_index: stage.order_index,
      status: stage.status,
      progress: stage.progress,
    })
    setShowForm(true)
  }

  const totalProgress =
    stages.length === 0
      ? 0
      : Math.round(
          stages.reduce((sum, stage) => sum + stage.progress, 0) /
            stages.length,
        )

  return (
    <div className="p-6 space-y-6">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>项目详情</CardTitle>
          <div className="space-x-2">
            <Button variant="outline" onClick={handleCreateDefaultStages}>
              生成默认流程
            </Button>
            <Button
              onClick={() => {
                setEditingStage(null)
                setForm({
                  name: "",
                  description: "",
                  order_index: stages.length + 1,
                  status: "not_started",
                  progress: 0,
                })
                setShowForm(true)
              }}
            >
              新增阶段
            </Button>
          </div>
        </CardHeader>

        <CardContent>
          <div className="space-y-2">
            <div className="text-sm text-muted-foreground">
              项目 ID：{projectId}
            </div>

            <div>
              <div className="flex justify-between text-sm mb-1">
                <span>整体进度</span>
                <span>{totalProgress}%</span>
              </div>
              <div className="h-3 w-full rounded bg-gray-200">
                <div
                  className="h-3 rounded bg-blue-500"
                  style={{ width: `${totalProgress}%` }}
                />
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {showForm && (
        <Card>
          <CardHeader>
            <CardTitle>{editingStage ? "编辑阶段" : "新增阶段"}</CardTitle>
          </CardHeader>

          <CardContent className="space-y-4">
            <Input
              placeholder="阶段名称，例如：工业设计"
              value={form.name}
              onChange={(e) =>
                setForm({
                  ...form,
                  name: e.target.value,
                })
              }
            />

            <textarea
              placeholder="阶段描述"
              value={form.description}
              onChange={(e) =>
                setForm({
                  ...form,
                  description: e.target.value,
                })
              }
              className="w-full min-h-[90px] rounded-md border px-3 py-2 text-sm"
            />

            <Input
              type="number"
              placeholder="排序"
              value={form.order_index}
              onChange={(e) =>
                setForm({
                  ...form,
                  order_index: Number(e.target.value),
                })
              }
            />

            <select
              value={form.status}
              onChange={(e) =>
                setForm({
                  ...form,
                  status: e.target.value,
                })
              }
              className="w-full rounded-md border px-3 py-2 text-sm"
            >
              <option value="not_started">未开始</option>
              <option value="in_progress">进行中</option>
              <option value="completed">已完成</option>
              <option value="blocked">阻塞</option>
            </select>

            <Input
              type="number"
              min={0}
              max={100}
              placeholder="进度 0-100"
              value={form.progress}
              onChange={(e) =>
                setForm({
                  ...form,
                  progress: Number(e.target.value),
                })
              }
            />

            <div className="space-x-2">
              <Button
                onClick={() => saveMutation.mutate()}
                disabled={saveMutation.isPending}
              >
                {saveMutation.isPending ? "保存中..." : "保存"}
              </Button>

              <Button
                variant="outline"
                onClick={() => {
                  setShowForm(false)
                  setEditingStage(null)
                }}
              >
                取消
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>流程阶段</CardTitle>
        </CardHeader>

        <CardContent>
          {isLoading ? (
            <div>正在加载流程阶段...</div>
          ) : isError ? (
            <div className="text-red-500">
              流程阶段加载失败，请检查接口或登录状态。
            </div>
          ) : stages.length === 0 ? (
            <div className="text-muted-foreground">
              暂无流程阶段，可以点击“生成默认流程”。
            </div>
          ) : (
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {stages.map((stage) => (
                <Card key={stage.id}>
                  <CardHeader>
                    <CardTitle className="text-base">
                      {stage.order_index}. {stage.name}
                    </CardTitle>
                  </CardHeader>

                  <CardContent className="space-y-3">
                    <div className="text-sm text-muted-foreground">
                      {stage.description || "暂无描述"}
                    </div>

                    <div className="text-sm">
                      状态：{getStatusText(stage.status)}
                    </div>

                    <div>
                      <div className="flex justify-between text-sm mb-1">
                        <span>进度</span>
                        <span>{stage.progress}%</span>
                      </div>
                      <div className="h-2 w-full rounded bg-gray-200">
                        <div
                          className="h-2 rounded bg-blue-500"
                          style={{ width: `${stage.progress}%` }}
                        />
                      </div>
                    </div>

                    <div className="space-x-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleEdit(stage)}
                      >
                        编辑
                      </Button>

                      <Button
                        variant="destructive"
                        size="sm"
                        onClick={() => {
                          if (window.confirm("确定删除该阶段吗？")) {
                            deleteMutation.mutate(stage.id)
                          }
                        }}
                      >
                        删除
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
