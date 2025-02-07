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
import { Button } from "@/components/ui/button"
import { Notebook, NotebookCreate } from '@/types'
import * as api from '@/lib/api'
import { useState } from 'react'

const notebookFormSchema = z.object({
  name: z.string().min(1, "Name is required"),
  description: z.string().optional(),
  image: z.string().min(1, "Image is required"),
  gpu_limit: z.number().min(0, "GPU limit must be >= 0"),
  cpu_limit: z.number().min(0, "CPU limit must be >= 0"),
  memory_limit: z.string().min(1, "Memory limit is required"),
  lease_duration: z.number().min(1, "Lease duration must be >= 1"),
  max_lease_renewals: z.number().min(0, "Max lease renewals must be >= 0"),
  project_id: z.number().min(1, "Project is required"),
})

type NotebookFormValues = z.infer<typeof notebookFormSchema>

interface NotebookDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  notebook?: Notebook
  onSuccess?: () => void
}

export function NotebookDialog({ open, onOpenChange, notebook, onSuccess }: NotebookDialogProps) {
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const form = useForm<NotebookFormValues>({
    resolver: zodResolver(notebookFormSchema),
    defaultValues: notebook || {
      name: "",
      description: "",
      image: "jupyter/minimal-notebook:latest",
      gpu_limit: 0,
      cpu_limit: 1,
      memory_limit: "1Gi",
      lease_duration: 24,
      max_lease_renewals: 3,
      project_id: 0,
    },
  })

  async function onSubmit(data: NotebookFormValues) {
    try {
      setLoading(true)
      setError(null)

      if (notebook) {
        await api.updateNotebook(notebook.id, data)
      } else {
        await api.createNotebook(data)
      }

      onSuccess?.()
      onOpenChange(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save notebook')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>{notebook ? 'Edit Notebook' : 'Create Notebook'}</DialogTitle>
          <DialogDescription>
            {notebook ? 'Edit your notebook details.' : 'Create a new Jupyter notebook instance.'}
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
                    <Input placeholder="Notebook name" {...field} />
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
                    <Input placeholder="Notebook description" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="image"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Docker Image</FormLabel>
                  <FormControl>
                    <Input placeholder="e.g. jupyter/minimal-notebook:latest" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <div className="grid grid-cols-2 gap-4">
              <FormField
                control={form.control}
                name="gpu_limit"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>GPU Limit</FormLabel>
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
              <FormField
                control={form.control}
                name="cpu_limit"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>CPU Limit</FormLabel>
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
            </div>
            <FormField
              control={form.control}
              name="memory_limit"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Memory Limit</FormLabel>
                  <FormControl>
                    <Input placeholder="e.g. 1Gi, 512Mi" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <div className="grid grid-cols-2 gap-4">
              <FormField
                control={form.control}
                name="lease_duration"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Lease Duration (hours)</FormLabel>
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
              <FormField
                control={form.control}
                name="max_lease_renewals"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Max Lease Renewals</FormLabel>
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
            </div>
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
                {loading ? 'Saving...' : (notebook ? 'Update' : 'Create')}
              </Button>
            </div>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
} 