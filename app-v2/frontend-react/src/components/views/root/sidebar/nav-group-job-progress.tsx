import { useGlobalJobProgress } from "#/state/global.job-progress";
import { useGlobalWebSocket } from "#/state/global.ws";
import { useMutationDemoJobDemoStart } from "#/data/use-demo";

import {
  ProgressBoxWrapper,
  ProgressBoxTopBar,
  ProgressBoxBottomBar,
  ProgressBoxContent,
  ProgressBoxContentJob,
  ProgressBoxContentNoJobs,
} from "#/components/ui/progress-box";
import { Button } from "#/components/ui/button";
import { IconIsInvalid, IconIsValid } from "#/components/ui/icons-common";
import { DebugOnly } from "#/components/ui/debug.with-state";

export function AppSidebarNavGroupJobProgress() {
  // global state
  const globalWs = useGlobalWebSocket();
  const jobProgress = useGlobalJobProgress();

  // server mutation
  const mutationDemoJobDemoStart = useMutationDemoJobDemoStart();

  return (
    <ProgressBoxWrapper className="mx-3 h-45 lg:h-70">
      <DebugOnly>
        <ProgressBoxTopBar />
      </DebugOnly>
      <ProgressBoxContent debugData={jobProgress}>
        {jobProgress.jobs.length === 0 ? (
          <ProgressBoxContentNoJobs />
        ) : jobProgress.jobs.map((job, index) => (
          <ProgressBoxContentJob
            key={index}
            title={job.title}
            status={job.executionStatus}
            progress={job.progress}
            stepsTotal={job.stepsTotal}
            stepsCompleted={job.stepsCompleted}
            messages={job.messages}
          />
        ))}
      </ProgressBoxContent>
      <ProgressBoxBottomBar>
        {globalWs.isConnected ? (
          <div className="flex items-center gap-1 text-xs text-green-500">
            <IconIsValid className="size-[1em]" />
            <span>Connected</span>
          </div>
        ) : (
          <div className="flex items-center gap-1 text-xs text-destructive">
            <IconIsInvalid className="size-[1em]" />
            <span>Disconnected</span>
          </div>
        )}
        <DebugOnly>
          <Button
            onClick={() => mutationDemoJobDemoStart.mutate()}
            isLoading={mutationDemoJobDemoStart.isPending}
            disabled={mutationDemoJobDemoStart.isPending}
            variant="link"
            size="xs"
          >
            Job Demo - Start
          </Button>
        </DebugOnly>
      </ProgressBoxBottomBar>
    </ProgressBoxWrapper>
  );
}