import type { Metadata } from 'next';
import { Figtree, Manrope } from 'next/font/google';

import './globals.css';
import { Toaster } from 'sonner';

const manrope = Manrope({
  subsets: ['latin'],
  display: 'swap',
  variable: '--font-manrope',
});

const figtree = Figtree({
  subsets: ['latin'],
  display: 'swap',
  variable: '--font-figtree',
});

export const metadata: Metadata = {
  title: 'HiddenAlerts',
  description: 'Intelligence alerts and reporting',
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${manrope.variable} ${figtree.variable} h-full antialiased`}
      suppressHydrationWarning
    >
      <body className={`${manrope.className} flex min-h-full flex-col`}>
        {children}
        <Toaster />
      </body>
    </html>
  );
}
