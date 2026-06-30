import { createFileRoute } from '@tanstack/react-router';

import { useMutationUpdateSettings, useSettings } from '@/data/use-settings';

import { SettingsReadonlyForm } from '#/components/views/settings-readonly-form';
import { SettingsMutableForm } from '#/components/views/settings-mutable-form';

import { RootContentMain, RootContentTopBar } from '@/components/ui/root';
import { Skeleton } from '@/components/ui/skeleton';

export const Route = createFileRoute('/settings')({
  component: RouteComponent,
});

function RouteComponent() {

  const querySettings = useSettings();
  const mutationUpdateSettings = useMutationUpdateSettings();

  if (querySettings.isLoading) {
    return (
      <>
        <RootContentTopBar>
          <Skeleton className="w-50 h-8" />
        </RootContentTopBar>
        <RootContentMain>
          {null}
        </RootContentMain>
      </>
    );
  }

  if (querySettings.isError || !querySettings.data) {
    return (
      <>
        <RootContentTopBar>
          Settings
        </RootContentTopBar>
        <RootContentMain>
          <p>
            There was an error loading settings
          </p>
        </RootContentMain>
      </>
    );
  }


  return (
    <>
      <RootContentTopBar>
        Settings
      </RootContentTopBar>
      <RootContentMain>
        <div className="w-full grid grid-cols-2 gap-4">
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
      </RootContentMain>
    </>
  );
}
