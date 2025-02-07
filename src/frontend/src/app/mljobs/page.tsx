import React from 'react'
import { MLJobsTable } from '@/components/mljobs/mljobs-table'
import { MLJobsHeader } from '@/components/mljobs/mljobs-header'

export default function MLJobsPage() {
  return (
    <div className="flex-1 space-y-4 p-8 pt-6">
      <MLJobsHeader />
      <MLJobsTable />
    </div>
  )
} 