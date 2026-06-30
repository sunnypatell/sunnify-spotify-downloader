import type { ReactNode } from 'react';

import { RootSidebar } from './sidebar';

import { SidebarProvider } from '@/components/ui/sidebar';
import { DebugPanel } from '#/components/views/root/content/debug-panel';
import { RootWrapper, RootContent } from '@/components/ui/root';

interface RootLayoutProps {
  children: ReactNode;
}

export function RootLayout({ children }: RootLayoutProps) {
  return (
    <SidebarProvider>
      <RootWrapper>
        <RootSidebar />
        <RootContent>
          {children}
          <DebugPanel />
        </RootContent>
      </RootWrapper>
    </SidebarProvider>
  );
}


