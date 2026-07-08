
// main layout

/**
 * 
 * @example
 * ```tsx
 * <RootWrapper>
 *   <SidebarProvider> // shadcn
 *     <Sidebar> // shadcn
 *       // sidebar code here
 *     </Sidebar>
 *     <SidebarInset /> // shadcn
 *     <SidebarRail /> // shadcn
 *   </SidebarProvider>
 *   <RootBottomBar>
 *     // bottom bar code here
 *   </RootBottomBar>
 * </RootWrapper>
 * ```
 */
export function RootWrapper({ children }: { children: React.ReactNode; }) {
  return (
    <div
      data-comp="RootWrapper"
      className="h-screen w-screen flex flex-col"
    >
      {children}
    </div>
  );
}

export function RootBottomBar({ children }: { children: React.ReactNode; }) {
  return (
    <div
      data-comp="RootBottomBar"
      className="min-h-9 px-4 py-2 bg-muted/50 border-t flex flex-col"
    >
      {children}
    </div>
  );
}


// inside RootSidebarWithContentWrapper layout

export function RootSidebarContentTopBar({ children }: { children: React.ReactNode; }) {
  return (
    <div
      data-comp="RootSidebarContentTopBar"
      className="min-h-16 px-4 flex gap-4 justify-between items-center border-b font-semibold"
    >
      {children}
    </div>
  );
}

export function RootSidebarContentMain({ children }: { children: React.ReactNode; }) {
  return (
    <div
      data-comp="RootSidebarContentMain"
      className="min-h-0 flex-1 px-4 py-4 flex flex-col gap-6"
    >
      {children}
    </div>
  );
}