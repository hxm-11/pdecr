import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, Link } from "@tanstack/react-router"
import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Textarea } from "@/components/ui/textarea"

import {
  createProject,
  deleteProject,
  getProjects,
  type Project,
  updateProject,
} from "@/lib/projectApi"

export const Route = createFileRoute("/_layout/projects")({
  component: ProjectsPage,
})

function ProjectsPage() {
  const queryClient = useQueryClient()

  const [open, setOpen] = useState(false)
  const [isEdit, setIsEdit] = useState(false)

  const [form, setForm] = useState<Partial<Project>>({
    title: "",
    description: "",
    is_active: true,
  })

  const {
    data: projectList = [],
    isLoading,
    isError,
  } = useQuery({
    queryKey: ["projects"],
    queryFn: getProjects,
    refetchInterval: 5000,
  })

  const saveMutation = useMutation({
    mutationFn: async () => {
      if (!form.title || form.title.trim() === "") {
        throw new Error("项目名称不能为空")
      }

      if (isEdit && form.id) {
        return updateProject(form.id, {
          title: form.title,
          description: form.description,
          is_active: form.is_active,
        })
      }

      return createProject({
        title: form.title,
        description: form.description,
        is_active: form.is_active ?? true,
      })
    },
    onSuccess: () => {
      setOpen(false)
      queryClient.invalidateQueries({ queryKey: ["projects"] })
      alert(isEdit ? "修改成功" : "新增成功")
    },
    onError: (error) => {
      alert(
        error instanceof Error
          ? `保存失败：${error.message}`
          : "保存失败，请检查后端接口或登录状态",
      )
    },
  })

  const deleteMutation = useMutation({
    mutationFn: deleteProject,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] })
      alert("删除成功")
    },
    onError: () => {
      alert("删除失败，请检查权限或后端接口")
    },
  })

  const handleCreate = () => {
    setIsEdit(false)
    setForm({
      title: "",
      description: "",
      is_active: true,
    })
    setOpen(true)
  }

  const handleEdit = (item: Project) => {
    setIsEdit(true)
    setForm({
      id: item.id,
      title: item.title,
      description: item.description ?? "",
      is_active: item.is_active,
    })
    setOpen(true)
  }

  const handleDelete = (id: string) => {
    if (window.confirm("确定要删除该项目吗？")) {
      deleteMutation.mutate(id)
    }
  }

  return (
    <div className="p-6 space-y-4">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>项目管理</CardTitle>
          <Button onClick={handleCreate}>新增项目</Button>
        </CardHeader>

        <CardContent>
          {isLoading ? (
            <div className="py-8 text-center text-muted-foreground">
              正在加载项目列表...
            </div>
          ) : isError ? (
            <div className="py-8 text-center text-red-500">
              项目列表加载失败，请检查后端接口或登录状态。
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>项目名称</TableHead>
                  <TableHead>描述</TableHead>
                  <TableHead>状态</TableHead>
                  <TableHead>创建时间</TableHead>
                  <TableHead className="text-right">操作</TableHead>
                </TableRow>
              </TableHeader>

              <TableBody>
                {projectList.length === 0 ? (
                  <TableRow>
                    <TableCell
                      colSpan={5}
                      className="text-center text-muted-foreground"
                    >
                      暂无项目
                    </TableCell>
                  </TableRow>
                ) : (
                  projectList.map((item) => (
                    <TableRow key={item.id}>
                      <TableCell className="font-medium">
                        {item.title}
                      </TableCell>

                      <TableCell className="max-w-[300px] truncate">
                        {item.description || "-"}
                      </TableCell>

                      <TableCell>
                        {item.is_active ? (
                          <span className="text-green-600">启用</span>
                        ) : (
                          <span className="text-gray-500">禁用</span>
                        )}
                      </TableCell>

                      <TableCell>
                        {item.created_at
                          ? new Date(item.created_at).toLocaleString()
                          : "-"}
                      </TableCell>

                      <TableCell className="text-right space-x-2">
                        <Link
                          to="/projects/$projectId"
                          params={{ projectId: item.id }}
                        >
                          <Button variant="outline" size="sm">
                            详情
                          </Button>
                        </Link>

                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleEdit(item)}
                        >
                          编辑
                        </Button>

                        <Button
                          variant="destructive"
                          size="sm"
                          onClick={() => handleDelete(item.id)}
                          disabled={deleteMutation.isPending}
                        >
                          删除
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{isEdit ? "编辑项目" : "新增项目"}</DialogTitle>
          </DialogHeader>

          <div className="space-y-4">
            <Input
              placeholder="项目名称"
              value={form.title ?? ""}
              onChange={(e) =>
                setForm({
                  ...form,
                  title: e.target.value,
                })
              }
            />

            <Textarea
              placeholder="项目描述"
              value={form.description ?? ""}
              onChange={(e) =>
                setForm({
                  ...form,
                  description: e.target.value,
                })
              }
            />

            <div className="flex items-center gap-2 text-sm">
              <input
                id="is_active"
                type="checkbox"
                checked={form.is_active ?? true}
                onChange={(e) =>
                  setForm({
                    ...form,
                    is_active: e.target.checked,
                  })
                }
              />
              <label htmlFor="is_active">启用项目</label>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>
              取消
            </Button>

            <Button
              onClick={() => saveMutation.mutate()}
              disabled={saveMutation.isPending}
            >
              {saveMutation.isPending ? "保存中..." : "保存"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
