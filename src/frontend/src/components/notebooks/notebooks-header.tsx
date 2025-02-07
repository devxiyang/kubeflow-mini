'use client'

import React, { useState } from 'react'
import { Button } from "@/components/ui/button"
import { NotebookDialog } from './notebook-dialog'

export function NotebooksHeader() {
  const [dialogOpen, setDialogOpen] = useState(false)

  return (
    <div className="flex items-center justify-between space-x-2">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Notebooks</h2>
        <p className="text-muted-foreground">
          Manage your Jupyter notebooks
        </p>
      </div>
      <div className="flex items-center space-x-2">
        <Button onClick={() => setDialogOpen(true)}>
          Create Notebook
        </Button>
      </div>
      <NotebookDialog 
        open={dialogOpen} 
        onOpenChange={setDialogOpen}
        onSuccess={() => window.location.reload()}
      />
    </div>
  )
} 