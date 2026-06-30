import { cn } from "#/lib/utils";
import { useState } from "react";

export function useTabsFromTuple<TKey extends string>(
  keys: TKey[],
  initialKey: TKey
) {
  const [activeKey, setActiveKey] = useState<TKey>(initialKey);

  return {
    keys,
    activeKey,
    setActiveKey,
  };
}

export function Tabs<TKey extends string>({
  keys,
  activeKey,
  setActiveKey,
  className,
}: (
    & ReturnType<typeof useTabsFromTuple<TKey>>
    & {
      className?: React.ComponentProps<"div">["className"];
    }
  )) {
  return (
    <div
      className={cn(
        "w-max p-1.5 flex items-center border rounded-xl bg-background",
        className
      )}
    >
      {keys.map((key) => (
        <TabTrigger
          key={key}
          tabKey={key}
          isActive={key === activeKey}
          setActiveKey={setActiveKey}
        />
      ))}
    </div>
  );
}

function TabTrigger<TKey extends string>({
  isActive,
  tabKey,
  setActiveKey,
}: {
  isActive: boolean;
  tabKey: TKey;
  setActiveKey: (key: TKey) => void;
}) {
  return (
    <button
      type="button"
      onClick={() => setActiveKey(tabKey)}
      className={cn(
        "px-3 py-1 text-xs/none rounded-xl border font-medium",
        "transition-colors duration-200",
        !isActive
          ? "bg-transparent border-transparent text-muted-foreground"
          : "bg-muted border-muted-foreground/10"
      )}
    >
      {tabKey}
    </button>
  );
}