'use client'

import React from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import * as z from 'zod'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Button } from "@/components/ui/button"
import { MLJob, MLJobCreate } from '@/types'
import * as api from '@/lib/api'
import { useState } from 'react'

const mlJobFormSchema = z.object({
  name: z.string().min(1, "Name is required"),
  description: z.string().optional(),
  priority: z.number().min(0, "Priority must be >= 0").max(100, "Priority must be <= 100"),
  training: z.string().min(1, "Training configuration is required"),
  project_id: z.number().min(1, "Project is required"),
})

type MLJobFormValues = z.infer<typeof mlJobFormSchema>

interface MLJobDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  job?: MLJob
  onSuccess?: () => void
}

export function MLJobDialog({ open, onOpenChange, job, onSuccess }: MLJobDialogProps) {
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const form = useForm<MLJobFormValues>({
    resolver: zodResolver(mlJobFormSchema),
    defaultValues: job || {
      name: "",
      description: "",
      priority: 50,
      training: "",
      project_id: 0,
    },
  })

  async function onSubmit(data: MLJobFormValues) {
    try {
      setLoading(true)
      setError(null)

      if (job) {
        await api.updateMLJob(job.id, data)
      } else {
        await api.createMLJob(data)
      }

      onSuccess?.()
      onOpenChange(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save ML job')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[600px]">
        <DialogHeader>
          <DialogTitle>{job ? 'Edit ML Job' : 'Create ML Job'}</DialogTitle>
          <DialogDescription>
            {job ? 'Edit your ML job details.' : 'Create a new machine learning training job.'}
          </DialogDescription>
        </DialogHeader>
        {error && (
          <div className="text-red-500 text-sm">{error}</div>
        )}
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <FormField
              control={form.control}
              name="name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Name</FormLabel>
                  <FormControl>
                    <Input placeholder="Job name" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="description"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Description</FormLabel>
                  <FormControl>
                    <Input placeholder="Job description" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="priority"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Priority (0-100)</FormLabel>
                  <FormControl>
                    <Input 
                      type="number" 
                      min={0}
                      max={100}
                      {...field}
                      onChange={e => field.onChange(Number(e.target.value))}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="training"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Training Configuration (YAML)</FormLabel>
                  <FormControl>
                    <Textarea 
                      placeholder="Enter training configuration in YAML format"
                      className="font-mono"
                      rows={10}
                      {...field}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="project_id"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Project ID</FormLabel>
                  <FormControl>
                    <Input 
                      type="number" 
                      {...field}
                      onChange={e => field.onChange(Number(e.target.value))}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <div className="flex justify-end space-x-2">
              <Button 
                type="button" 
                variant="outline" 
                onClick={() => onOpenChange(false)}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={loading}>
                {loading ? 'Saving...' : (job ? 'Update' : 'Create')}
              </Button>
            </div>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
} 