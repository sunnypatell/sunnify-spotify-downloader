import { useEffect, useState } from "react";

export function useIntervalValue<TValue>({
  intervalMs,
  producer,
}: {
  intervalMs: number,
  producer: () => TValue,
}) {
  const [value, setValue] = useState<TValue>(producer);
  useEffect(
    () => {
      const setter = () => setValue(producer());
      const interval = setInterval(setter, intervalMs);
      return () => clearInterval(interval);
    },
    [intervalMs, producer]
  );
  return value;
}