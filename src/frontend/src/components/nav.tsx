import React from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { cn } from '../lib/utils'

const navigation = [
  { name: 'Dashboard', href: '/' },
  { name: 'Projects', href: '/projects' },
  { name: 'ML Jobs', href: '/mljobs' },
  { name: 'Notebooks', href: '/notebooks' },
]

export function MainNav() {
  const pathname = usePathname()

  return (
    <nav className="flex space-x-4">
      {navigation.map((item) => (
        <Link
          key={item.href}
          href={item.href}
          className={cn(
            'text-sm font-medium transition-colors hover:text-primary',
            pathname === item.href
              ? 'text-black dark:text-white'
              : 'text-muted-foreground'
          )}
        >
          {item.name}
        </Link>
      ))}
    </nav>
  )
} 