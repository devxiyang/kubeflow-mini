import type { Metadata } from "next";
import { Header } from '@/components/header'
import "./globals.css";

export const metadata: Metadata = {
  title: "Kubeflow Mini",
  description: "A lightweight machine learning job management tool",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="min-h-screen bg-background font-sans antialiased">
        <div className="relative flex min-h-screen flex-col">
          <Header />
          <main className="flex-1">{children}</main>
        </div>
      </body>
    </html>
  );
}
