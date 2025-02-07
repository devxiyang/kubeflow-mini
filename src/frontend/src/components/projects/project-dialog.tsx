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
import { Project, ProjectCreate } from '@/types'
import * as api from '@/lib/api'
import { useState } from 'react'

const projectFormSchema = z.object({
  name: z.string().min(1, "Name is required"),
  description: z.string().optional(),
  gpu_limit: z.number().min(0, "GPU limit must be >= 0"),
  cpu_limit: z.number().min(0, "CPU limit must be >= 0"),
  memory_limit: z.string().min(1, "Memory limit is required"),
  max_jobs: z.number().min(1, "Max jobs must be >= 1"),
})

type ProjectFormValues = z.infer<typeof projectFormSchema>

interface ProjectDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  project?: Project
  onSuccess?: () => void
}

export function ProjectDialog({ open, onOpenChange, project, onSuccess }: ProjectDialogProps) {
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const form = useForm<ProjectFormValues>({
    resolver: zodResolver(projectFormSchema),
    defaultValues: project || {
      name: "",
      description: "",
      gpu_limit: 0,
      cpu_limit: 1,
      memory_limit: "1Gi",
      max_jobs: 10,
    },
  })

  async function onSubmit(data: ProjectFormValues) {
    try {
      setLoading(true)
      setError(null)

      if (project) {
        await api.updateProject(project.id, data)
      } else {
        await api.createProject(data)
      }

      onSuccess?.()
      onOpenChange(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save project')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>{project ? 'Edit Project' : 'Create Project'}</DialogTitle>
          <DialogDescription>
            {project ? 'Edit your project details.' : 'Create a new machine learning project.'}
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
                    <Input placeholder="Project name" {...field} />
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
                    <Input placeholder="Project description" {...field} />
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
            <FormField
              control={form.control}
              name="max_jobs"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Max Jobs</FormLabel>
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
                {loading ? 'Saving...' : (project ? 'Update' : 'Create')}
              </Button>
            </div>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
} 