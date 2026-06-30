import { cn } from "#/lib/utils";

export function ProgressBar({
  progress,
  className,
}: {
  /** 0-1 range */
  progress: number,
  className?: React.ComponentProps<"div">["className"];
}) {
  return (
    <div className={cn("w-full flex gap-2 items-center", className)}>
      <div className="flex-1 h-2 rounded-2xl bg-muted-foreground/10 border overflow-hidden">
        <div
          className="w-full h-full bg-primary rounded-[inherit] origin-left transition-transform duration-800 ease-in-out"
          style={{ scale: `${progress} 1` }}
        />
      </div>
      <span className="min-w-[5ch] text-right">
        {`${(progress * 100).toFixed(0)}%`}
      </span>
    </div>
  );
}