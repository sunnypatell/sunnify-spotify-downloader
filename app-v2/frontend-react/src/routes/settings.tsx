import { createFileRoute } from '@tanstack/react-router';

import { useMutationUpdateSettings, useSettings } from '@/data/use-settings';

import { SettingsReadonlyForm } from '#/components/views/settings-readonly-form';
import { SettingsMutableForm } from '#/components/views/settings-mutable-form';

import { RootSidebarContentMain, RootSidebarContentTopBar } from '@/components/ui/root';
import { Skeleton } from '@/components/ui/skeleton';
import { Alert } from '#/components/ui/alert';

export const Route = createFileRoute('/settings')({
  component: RouteComponent,
});

function RouteComponent() {

  const querySettings = useSettings();
  const mutationUpdateSettings = useMutationUpdateSettings();

  if (querySettings.isLoading) {
    return (
      <>
        <RootSidebarContentTopBar>
          <Skeleton className="w-50 h-8" />
        </RootSidebarContentTopBar>
        <RootSidebarContentMain>
          {null}
        </RootSidebarContentMain>
      </>
    );
  }

  if (querySettings.isError || !querySettings.data) {
    return (
      <>
        <RootSidebarContentTopBar>
          Settings
        </RootSidebarContentTopBar>
        <RootSidebarContentMain>
          <Alert variant="destructive">
            There was an error loading settings
          </Alert>
        </RootSidebarContentMain>
      </>
    );
  }


  return (
    <>
      <RootSidebarContentTopBar>
        Settings
      </RootSidebarContentTopBar>
      <RootSidebarContentMain>
        <div className="w-full flex flex-col gap-4">
          <SettingsReadonlyForm
            settingsReadonly={querySettings.data.readonly}
          />
          <SettingsMutableForm
            initialValues={querySettings.data.mutable}
            onSubmit={async (formValues) => {
              const result = await mutationUpdateSettings.mutateAsync(formValues);
              if (result) return { status: 'success', message: 'Settings Updated', };
              return { status: 'error', message: 'Error', };
            }}
          />
        </div>
      </RootSidebarContentMain>
    </>
  );
}
