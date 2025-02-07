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
import { MoreHorizontal, Pencil, Trash, Play, Square } from "lucide-react"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { NotebookDialog } from './notebook-dialog'
import { Notebook } from '@/types'
import * as api from '@/lib/api'

export function NotebooksTable() {
  const [notebooks, setNotebooks] = useState<Notebook[]>([])
  const [editingNotebook, setEditingNotebook] = useState<Notebook | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadNotebooks()
  }, [])

  async function loadNotebooks() {
    try {
      setLoading(true)
      setError(null)
      const data = await api.getNotebooks()
      setNotebooks(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load notebooks')
    } finally {
      setLoading(false)
    }
  }

  async function handleDelete(notebook: Notebook) {
    if (!confirm('Are you sure you want to delete this notebook?')) {
      return
    }

    try {
      await api.deleteNotebook(notebook.id)
      await loadNotebooks()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete notebook')
    }
  }

  async function handleStart(notebook: Notebook) {
    try {
      await api.startNotebook(notebook.id)
      await loadNotebooks()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start notebook')
    }
  }

  async function handleStop(notebook: Notebook) {
    try {
      await api.stopNotebook(notebook.id)
      await loadNotebooks()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to stop notebook')
    }
  }

  async function handleRenewLease(notebook: Notebook) {
    try {
      await api.renewNotebookLease(notebook.id)
      await loadNotebooks()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to renew notebook lease')
    }
  }

  function getStatusColor(status: string): string {
    switch (status.toLowerCase()) {
      case 'running':
        return 'bg-green-100 text-green-700'
      case 'stopped':
        return 'bg-gray-100 text-gray-700'
      default:
        return 'bg-yellow-100 text-yellow-700'
    }
  }

  function getLeaseStatusColor(status: string): string {
    switch (status.toLowerCase()) {
      case 'active':
        return 'bg-green-100 text-green-700'
      case 'expired':
        return 'bg-red-100 text-red-700'
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
              <TableHead>Image</TableHead>
              <TableHead>Project</TableHead>
              <TableHead>Resource Limits</TableHead>
              <TableHead>Lease Status</TableHead>
              <TableHead className="w-[50px]"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {notebooks.map((notebook) => (
              <TableRow key={notebook.id}>
                <TableCell className="font-medium">{notebook.name}</TableCell>
                <TableCell>{notebook.description}</TableCell>
                <TableCell>
                  <div className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${getStatusColor(notebook.status)}`}>
                    {notebook.status}
                  </div>
                </TableCell>
                <TableCell>{notebook.image}</TableCell>
                <TableCell>{notebook.project_id}</TableCell>
                <TableCell>
                  <div className="space-y-1 text-sm">
                    <div>GPU: {notebook.gpu_limit}</div>
                    <div>CPU: {notebook.cpu_limit}</div>
                    <div>Memory: {notebook.memory_limit}</div>
                  </div>
                </TableCell>
                <TableCell>
                  <div className="space-y-1">
                    <div className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${getLeaseStatusColor(notebook.lease_status)}`}>
                      {notebook.lease_status}
                    </div>
                    {notebook.lease_start && (
                      <div className="text-xs text-gray-500">
                        Started: {new Date(notebook.lease_start).toLocaleString()}
                      </div>
                    )}
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
                      {notebook.status === 'stopped' ? (
                        <DropdownMenuItem onClick={() => handleStart(notebook)}>
                          <Play className="mr-2 h-4 w-4" />
                          Start
                        </DropdownMenuItem>
                      ) : (
                        <DropdownMenuItem onClick={() => handleStop(notebook)}>
                          <Square className="mr-2 h-4 w-4" />
                          Stop
                        </DropdownMenuItem>
                      )}
                      {notebook.lease_status === 'active' && (
                        <DropdownMenuItem onClick={() => handleRenewLease(notebook)}>
                          Renew Lease
                        </DropdownMenuItem>
                      )}
                      <DropdownMenuItem onClick={() => setEditingNotebook(notebook)}>
                        <Pencil className="mr-2 h-4 w-4" />
                        Edit
                      </DropdownMenuItem>
                      <DropdownMenuSeparator />
                      <DropdownMenuItem 
                        className="text-red-600"
                        onClick={() => handleDelete(notebook)}
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
      <NotebookDialog 
        open={!!editingNotebook}
        onOpenChange={(open) => !open && setEditingNotebook(null)}
        notebook={editingNotebook || undefined}
        onSuccess={loadNotebooks}
      />
    </>
  )
} 