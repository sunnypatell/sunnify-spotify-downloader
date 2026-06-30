import { cn } from "#/lib/utils";
import { Tooltip, TooltipContent, TooltipTrigger } from "./tooltip";

export function TooltipEasy({
  children,
  tooltipText,
  classNameTrigger,
  classNameContent,
}: {
  children: React.ComponentProps<typeof TooltipTrigger>["render"],
  tooltipText: React.ReactNode,
  classNameTrigger?: React.ComponentProps<"div">["className"];
  classNameContent?: React.ComponentProps<"div">["className"];
}) {
  return (
    <Tooltip>
      <TooltipTrigger
        className={cn("text-left", classNameTrigger)}
        render={children}
      />
      <TooltipContent className={classNameContent}>
        {tooltipText}
      </TooltipContent>
    </Tooltip>
  );
}