import React, { createContext, useContext } from "react";

import { cn } from "@/lib/utils";
import { Tabs, useTabsFromTuple } from "@/components/ui/tab";
import { ProgressBar } from "@/components/ui/progress-bar";
import { Badge } from "@/components/ui/badge";

// ctx
type TabKey = "normal" | "debug";
type Ctx = ReturnType<typeof useTabsFromTuple<TabKey>>;
const ctx = createContext<Ctx>({} as Ctx);
const useCtx = () => useContext(ctx);

export function ProgressBoxWrapper({
  className,
  children,
}: {
  className?: React.ComponentProps<"div">["className"];
  children?: React.ReactNode;
}) {
  const ctxValue: Ctx = useTabsFromTuple(['normal', 'debug'], 'normal');
  return (
    <ctx.Provider value={ctxValue}>
      <div className={cn("h-30 flex flex-col border rounded-md bg-muted", className)}>
        <div className="min-h-0 flex-1 flex flex-col">
          {children}
        </div>
      </div>
    </ctx.Provider>
  );
}


export function ProgressBoxTopBar() {
  const tabState = useCtx();

  return (
    <div className="py-1 px-2 border-b">
      <Tabs {...tabState} />
    </div>
  );
}

export function ProgressBoxContent({
  debugData,
  children,
}: {
  debugData: unknown;
  children?: React.ReactNode;
}) {
  const tabState = useCtx();

  return (
    <div className="min-h-0 h-full overflow-hidden flex flex-col">
      {tabState.activeKey === 'debug' ? (
        <pre className="min-h-full p-2 overflow-auto whitespace-pre-wrap text-xs text-muted-foreground">
          {serializeJsonToString(debugData)}
        </pre>
      ) : tabState.activeKey === 'normal' ? (
        <div className="min-h-full p-2 overflow-auto flex flex-col">
          {children}
        </div>
      ) : (
        null
      )}
    </div>
  );
}

export function ProgressBoxContentNoJobs() {
  return (
    <div className="flex-1 flex justify-center items-center text-muted-foreground text-xs">
      No Job in progress
    </div>
  );
}

type JobItemData = {
  title: string;
  /** 0-1 range */
  progress: number;
  stepsTotal: number;
  stepsCompleted: number;
  status: (
    | "WAITING_START"
    | "RUNNING"
    | "COMPLETED"
    | "CANCELED"
    | "ERRORED"
  );
  messages: string[];
};

const statusUi: Record<
  JobItemData["status"],
  {
    className: React.ComponentProps<"div">["className"];
    label: React.ReactNode,
  }> = {
  "WAITING_START": {
    className: "bg-muted-foreground/10",
    label: <Badge variant="outline">WAITING</Badge>,
  },
  "RUNNING": {
    className: "bg-blue-500/10",
    label: <Badge variant="outline" className="bg-blue-500/20 text-blue-400">RUNNING</Badge>,
  },
  "COMPLETED": {
    className: "bg-green-500/10",
    label: <Badge variant="outline" className="bg-green-500/20 text-green-500">COMPLETED</Badge>,
  },
  "CANCELED": {
    className: "bg-amber-500/10",
    label: <Badge variant="outline" className="bg-amber-500/20 text-amber-500">CANCELED</Badge>,
  },
  "ERRORED": {
    className: "bg-red-500/10",
    label: <Badge variant="destructive">ERRORED</Badge>,
  },
};

export function ProgressBoxContentJob({
  title,
  progress,
  stepsTotal,
  stepsCompleted,
  status,
  messages,
}: JobItemData) {
  return (
    <div
      className={cn(
        "px-3 py-3 flex flex-wrap items-center gap-y-3 gap-x-2 rounded-md text-xs",
        statusUi[status].className,
      )}
    >
      <div className="-ml-0.5 w-full">
        {statusUi[status].label}
      </div>
      <div className="w-full truncate font-semibold leading-none">
        {title}
      </div>
      <span className="min-w-[5ch] font-semibold text-muted-foreground tracking-widest text-[0.9em]/none">
        {stepsCompleted}/{stepsTotal}
      </span>
      <ProgressBar
        progress={progress}
        className="flex-10 gap-1 font-semibold text-muted-foreground text-[0.9em]/none"
      />
      {messages.length > 0 && (
        <div className="w-full max-w-full overflow-auto flex flex-col gap-2 text-muted-foreground">
          {messages.map((message, i) => (
            <p key={i} className="w-max">
              {message}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}

export function ProgressBoxBottomBar({
  children,
  className,
}: {
  children?: React.ReactNode;
  className?: React.ComponentProps<"div">["className"];
}) {
  return (
    <div className={cn(
      "empty:hidden"
      + " py-1 px-2"
      + " flex gap-2 justify-between items-center"
      + " text-xs/none text-muted-foreground"
      + " border-t"
      ,
      className
    )}>
      {children}
    </div>
  );
}

// utils

function serializeJsonToString(data: unknown) {
  try {
    return JSON.stringify(data, null, 2);
  } catch (error) {
    console.log('Progress Box - serializeJsonToString - Error');
    console.error(error);
    console.log('Progress Box - serializeJsonToString - Input Data');
    console.log(data);
    return "Invalid JSON";
  }
}