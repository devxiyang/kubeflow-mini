// Project types
export interface Project {
  id: number
  name: string
  description?: string
  status: 'active' | 'archived' | 'deleted'
  owner: string
  created_at: string
  updated_at: string
  gpu_limit: number
  cpu_limit: number
  memory_limit: string
  max_jobs: number
}

export interface ProjectCreate {
  name: string
  description?: string
  gpu_limit: number
  cpu_limit: number
  memory_limit: string
  max_jobs: number
}

export interface ProjectUpdate extends Partial<ProjectCreate> {}

// MLJob types
export interface MLJob {
  id: number
  job_id: string
  name: string
  namespace: string
  description?: string
  priority: number
  labels?: Record<string, string>
  training: string
  status: string
  message?: string
  training_status?: string
  sync_errors: number
  gpu_usage?: number
  cpu_usage?: number
  memory_usage?: string
  created_at: string
  updated_at: string
  started_at?: string
  completed_at?: string
  project_id: number
  user_id: number
}

export interface MLJobCreate {
  name: string
  description?: string
  priority?: number
  labels?: Record<string, string>
  training: string
  project_id: number
}

export interface MLJobUpdate extends Partial<MLJobCreate> {}

// Notebook types
export interface Notebook {
  id: number
  name: string
  description?: string
  image: string
  cpu_limit: number
  memory_limit: string
  gpu_limit: number
  status: string
  message?: string
  service_name?: string
  endpoint?: string
  created_at: string
  updated_at: string
  started_at?: string
  stopped_at?: string
  lease_status: string
  lease_start?: string
  lease_duration: number
  lease_renewal_count: number
  max_lease_renewals: number
  project_id: number
  user_id: number
}

export interface NotebookCreate {
  name: string
  description?: string
  image: string
  gpu_limit: number
  cpu_limit: number
  memory_limit: string
  lease_duration?: number
  max_lease_renewals?: number
  project_id: number
}

export interface NotebookUpdate extends Partial<NotebookCreate> {}

// User types
export interface User {
  id: number
  username: string
  email: string
  full_name: string
  is_active: boolean
  role: string
  created_at: string
  updated_at: string
}

export interface UserCreate {
  username: string
  email: string
  full_name: string
  password: string
}

export interface UserUpdate extends Partial<Omit<UserCreate, 'password'>> {
  password?: string
}

// Auth types
export interface Token {
  access_token: string
  token_type: string
} 