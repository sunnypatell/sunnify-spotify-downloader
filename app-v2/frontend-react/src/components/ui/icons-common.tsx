import { cn } from "#/lib/utils";
import { CheckCircle2Icon, XCircleIcon } from "lucide-react";

const iconClasses = {
  success: "text-green-500/90 fill-green-500/15",
  error: "text-destructive/90 fill-destructive/15",
};

export function IconIsValid(props: React.ComponentProps<typeof CheckCircle2Icon>) {
  return (
    <CheckCircle2Icon
      {...props}
      className={cn(iconClasses.success, props.className)}
    />
  );
}
export function IconIsInvalid(props: React.ComponentProps<typeof XCircleIcon>) {
  return (
    <XCircleIcon
      {...props}
      className={cn(iconClasses.error, props.className)}
    />
  );
}