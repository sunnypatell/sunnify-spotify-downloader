import { useCallback } from "react";
import { Time } from "#/utils/time";
import { useIntervalValue } from "#/utils/hooks/use-interval";

export function TimeDurationMMSS(props: (
  | { type: "ms"; durationInMs: number; }
  | { type: "mm:ss", durationString: string; }
)) {
  const text = props.type === 'mm:ss'
    ? props.durationString
    : new Time(props.durationInMs).asMMSS().full.asString;

  return (
    <span className="min-w-9 text-xs text-muted-foreground break-all text-center">
      {text}
    </span>
  );
}

export function TimePassedAgoMMSS({
  dateTimeIso,
}: {
  dateTimeIso: string,
}) {

  // local state
  const difference = useIntervalValue({
    intervalMs: 1000,
    producer: useCallback(
      () => {
        const now = new Date();
        const date = new Date(dateTimeIso);
        const passedMs = now.getTime() - date.getTime();
        return new Time(passedMs);
      },
      [dateTimeIso]
    ),
  });

  const text = difference.asMMSS().full.asStringNice;

  return (
    <span className="min-w-9 break-all text-center">
      {text} ago
    </span>
  );
}