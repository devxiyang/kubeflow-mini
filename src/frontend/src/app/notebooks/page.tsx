import React from 'react'
import { NotebooksTable } from '@/components/notebooks/notebooks-table'
import { NotebooksHeader } from '@/components/notebooks/notebooks-header'

export default function NotebooksPage() {
  return (
    <div className="flex-1 space-y-4 p-8 pt-6">
      <NotebooksHeader />
      <NotebooksTable />
    </div>
  )
} 