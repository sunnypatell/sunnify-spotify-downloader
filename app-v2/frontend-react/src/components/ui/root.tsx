export function RootWrapper({ children }: { children: React.ReactNode; }) {
  return (
    <div
      className="flex h-screen w-screen"
      data-comp="RootWrapper"
    >
      {/* Sidebar Goes here */}
      {children}
    </div>
  );
}

export function RootContent({ children }: { children: React.ReactNode; }) {
  return (
    <div
      className="min-w-0 flex-1 h-full flex flex-col bg-background"
      data-comp="RootContent"
    >
      {children}
    </div>
  );
}

export function RootContentTopBar({ children }: { children: React.ReactNode; }) {
  return (
    <div
      className="min-h-16 px-4 flex gap-4 justify-between items-center border-b"
      data-comp="RootContentTopBar"
    >
      {children}
    </div>
  );
}

export function RootContentMain({ children }: { children: React.ReactNode; }) {
  return (
    <div
      className="min-h-0 flex-1 px-4 py-4 flex flex-col gap-6"
      data-comp="RootContentMain"
    >
      {children}
    </div>
  );
}