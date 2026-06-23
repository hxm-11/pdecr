import axios from "axios"

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000"

function getAccessToken() {
  return (
    localStorage.getItem("access_token") ||
    localStorage.getItem("accessToken") ||
    localStorage.getItem("token")
  )
}

const stageApi = axios.create({
  baseURL: API_BASE_URL,
})

stageApi.interceptors.request.use((config) => {
  const token = getAccessToken()

  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }

  return config
})

export type ProjectStage = {
  id: string
  project_id: string
  name: string
  description?: string | null
  order_index: number
  status: string
  progress: number
  start_date?: string | null
  due_date?: string | null
  created_at: string
  updated_at: string
}

export type ProjectStagesResponse = {
  data: ProjectStage[]
  count: number
}

export type ProjectStageCreate = {
  project_id: string
  name: string
  description?: string | null
  order_index?: number
  status?: string
  progress?: number
  start_date?: string | null
  due_date?: string | null
}

export type ProjectStageUpdate = {
  name?: string
  description?: string | null
  order_index?: number
  status?: string
  progress?: number
  start_date?: string | null
  due_date?: string | null
}

export async function getProjectStages(
  projectId: string,
): Promise<ProjectStage[]> {
  const res = await stageApi.get<ProjectStagesResponse>(
    `/api/v1/project-stages/project/${projectId}`,
  )
  return res.data.data
}

export async function createProjectStage(
  data: ProjectStageCreate,
): Promise<ProjectStage> {
  const res = await stageApi.post<ProjectStage>("/api/v1/project-stages/", data)
  return res.data
}

export async function updateProjectStage(
  id: string,
  data: ProjectStageUpdate,
): Promise<ProjectStage> {
  const res = await stageApi.patch<ProjectStage>(
    `/api/v1/project-stages/${id}`,
    data,
  )
  return res.data
}

export async function deleteProjectStage(id: string): Promise<void> {
  await stageApi.delete(`/api/v1/project-stages/${id}`)
}
