import React from 'react'
import { ProjectsTable } from '@/components/projects/projects-table'
import { ProjectsHeader } from '@/components/projects/projects-header'

export default function ProjectsPage() {
  return (
    <div className="flex-1 space-y-4 p-8 pt-6">
      <ProjectsHeader />
      <ProjectsTable />
    </div>
  )
} 