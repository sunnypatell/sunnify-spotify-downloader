import { TanStackDevtools } from '@tanstack/react-devtools';
import { TanStackRouterDevtoolsPanel } from '@tanstack/react-router-devtools';
import { QueryClientProvider, QueryClient } from '@tanstack/react-query';
import { ReactQueryDevtoolsPanel } from '@tanstack/react-query-devtools';

import { useWsEntryPoint } from '#/data/use-ws-entry-point';

import { TooltipProvider } from '@/components/ui/tooltip';
import { Toaster } from '@/components/ui/sonner';

export const tanstackQueryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
    }
  }
});

export function RootProviders({ children }: { children: React.ReactNode; }) {
  return (
    <>
      <QueryClientProvider client={tanstackQueryClient}>
        <WebSocketBackendEventListener />
        <TanStackDevtools
          config={{
            position: 'bottom-right',
          }}
          plugins={[
            {
              name: 'Tanstack Router',
              render: <TanStackRouterDevtoolsPanel />,
            },
            {
              name: 'TanStack Query',
              render: <ReactQueryDevtoolsPanel />,
            },
          ]}
        />
        <TooltipProvider>
          {children}
        </TooltipProvider>
        <Toaster
          expand
          visibleToasts={15}
          richColors
          duration={9000}
        />
      </QueryClientProvider>
    </>
  );
}

function WebSocketBackendEventListener() {
  useWsEntryPoint();
  return null;
}