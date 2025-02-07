'use client'

import React, { useState } from 'react'
import { Button } from "@/components/ui/button"
import { ProjectDialog } from './project-dialog'

export function ProjectsHeader() {
  const [dialogOpen, setDialogOpen] = useState(false)

  return (
    <div className="flex items-center justify-between space-x-2">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Projects</h2>
        <p className="text-muted-foreground">
          Manage your machine learning projects
        </p>
      </div>
      <div className="flex items-center space-x-2">
        <Button onClick={() => setDialogOpen(true)}>
          Create Project
        </Button>
      </div>
      <ProjectDialog 
        open={dialogOpen} 
        onOpenChange={setDialogOpen}
        onSuccess={() => window.location.reload()}
      />
    </div>
  )
} 