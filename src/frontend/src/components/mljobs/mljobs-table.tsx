'use client'

import React, { useState, useEffect } from 'react'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Button } from "@/components/ui/button"
import { MoreHorizontal, Pencil, Trash } from "lucide-react"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { MLJobDialog } from './mljob-dialog'
import { MLJob } from '@/types'
import * as api from '@/lib/api'

export function MLJobsTable() {
  const [jobs, setJobs] = useState<MLJob[]>([])
  const [editingJob, setEditingJob] = useState<MLJob | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadJobs()
  }, [])

  async function loadJobs() {
    try {
      setLoading(true)
      setError(null)
      const data = await api.getMLJobs()
      setJobs(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load ML jobs')
    } finally {
      setLoading(false)
    }
  }

  async function handleDelete(job: MLJob) {
    if (!confirm('Are you sure you want to delete this ML job?')) {
      return
    }

    try {
      await api.deleteMLJob(job.id)
      await loadJobs()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete ML job')
    }
  }

  function getStatusColor(status: string): string {
    switch (status.toLowerCase()) {
      case 'running':
        return 'bg-green-100 text-green-700'
      case 'failed':
        return 'bg-red-100 text-red-700'
      case 'succeeded':
        return 'bg-blue-100 text-blue-700'
      case 'pending':
        return 'bg-yellow-100 text-yellow-700'
      default:
        return 'bg-gray-100 text-gray-700'
    }
  }

  if (loading) {
    return <div>Loading...</div>
  }

  if (error) {
    return <div className="text-red-500">{error}</div>
  }

  return (
    <>
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Description</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Priority</TableHead>
              <TableHead>Project</TableHead>
              <TableHead>Created</TableHead>
              <TableHead>Resource Usage</TableHead>
              <TableHead className="w-[50px]"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {jobs.map((job) => (
              <TableRow key={job.id}>
                <TableCell className="font-medium">{job.name}</TableCell>
                <TableCell>{job.description}</TableCell>
                <TableCell>
                  <div className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${getStatusColor(job.status)}`}>
                    {job.status}
                  </div>
                </TableCell>
                <TableCell>{job.priority}</TableCell>
                <TableCell>{job.project_id}</TableCell>
                <TableCell>{new Date(job.created_at).toLocaleDateString()}</TableCell>
                <TableCell>
                  <div className="space-y-1 text-sm">
                    {job.gpu_usage !== undefined && <div>GPU: {job.gpu_usage}</div>}
                    {job.cpu_usage !== undefined && <div>CPU: {job.cpu_usage}</div>}
                    {job.memory_usage && <div>Memory: {job.memory_usage}</div>}
                  </div>
                </TableCell>
                <TableCell>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" className="h-8 w-8 p-0">
                        <MoreHorizontal className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuLabel>Actions</DropdownMenuLabel>
                      <DropdownMenuItem onClick={() => setEditingJob(job)}>
                        <Pencil className="mr-2 h-4 w-4" />
                        Edit
                      </DropdownMenuItem>
                      <DropdownMenuSeparator />
                      <DropdownMenuItem 
                        className="text-red-600"
                        onClick={() => handleDelete(job)}
                      >
                        <Trash className="mr-2 h-4 w-4" />
                        Delete
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      <MLJobDialog 
        open={!!editingJob}
        onOpenChange={(open) => !open && setEditingJob(null)}
        job={editingJob || undefined}
        onSuccess={loadJobs}
      />
    </>
  )
} 