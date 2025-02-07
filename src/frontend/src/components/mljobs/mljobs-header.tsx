'use client'

import React, { useState } from 'react'
import { Button } from "@/components/ui/button"
import { MLJobDialog } from './mljob-dialog'

export function MLJobsHeader() {
  const [dialogOpen, setDialogOpen] = useState(false)

  return (
    <div className="flex items-center justify-between space-x-2">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">ML Jobs</h2>
        <p className="text-muted-foreground">
          Manage your machine learning training jobs
        </p>
      </div>
      <div className="flex items-center space-x-2">
        <Button onClick={() => setDialogOpen(true)}>
          Create ML Job
        </Button>
      </div>
      <MLJobDialog 
        open={dialogOpen} 
        onOpenChange={setDialogOpen}
        onSuccess={() => window.location.reload()}
      />
    </div>
  )
} 