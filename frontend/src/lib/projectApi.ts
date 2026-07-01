import axios from "axios"
import { getAccessToken } from "./authToken"

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000"

const projectApi = axios.create({
  baseURL: API_BASE_URL,
})

projectApi.interceptors.request.use((config) => {
  const token = getAccessToken()

  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }

  return config
})

export type Project = {
  id: string
  title: string
  description?: string | null
  is_active: boolean
  owner_id: string
  created_at: string
  updated_at: string
}

export type ProjectsResponse = {
  data: Project[]
  count: number
}

export type ProjectCreate = {
  title: string
  description?: string | null
  is_active?: boolean
}

export type ProjectUpdate = {
  title?: string
  description?: string | null
  is_active?: boolean
}

export async function getProjects(): Promise<Project[]> {
  const res = await projectApi.get<ProjectsResponse>("/api/v1/projects/")
  return res.data.data
}

export async function createProject(data: ProjectCreate): Promise<Project> {
  const res = await projectApi.post<Project>("/api/v1/projects/", data)
  return res.data
}

export async function updateProject(
  id: string,
  data: ProjectUpdate,
): Promise<Project> {
  const res = await projectApi.patch<Project>(`/api/v1/projects/${id}`, data)
  return res.data
}

export async function deleteProject(id: string): Promise<void> {
  await projectApi.delete(`/api/v1/projects/${id}`)
}
