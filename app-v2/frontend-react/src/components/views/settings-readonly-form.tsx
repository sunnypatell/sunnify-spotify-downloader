import type { Settings } from "#/lib/api-client/types";
import { FieldGroup, Field, FieldLabel, FieldDescription } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { useMutationUtilsDiskRevealInFinder } from "#/data/use-utils";
import { Button } from "../ui/button";
import { HardDriveIcon } from "lucide-react";

type SettingsReadonlyFormProps = {
  settingsReadonly: Settings['readonly'],
};

export function SettingsReadonlyForm(
  props: SettingsReadonlyFormProps
) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>
          Settings Readonly
        </CardTitle>
        <CardDescription>
          Those settings are readonly, you cannot change them!
        </CardDescription>
      </CardHeader>
      <CardContent>
        <TheForm {...props} />
      </CardContent>
    </Card>
  );
}

function TheForm({
  settingsReadonly
}: SettingsReadonlyFormProps) {

  const mutationUtilDiskRevealInFinder = useMutationUtilsDiskRevealInFinder();

  return (
    <FieldGroup>
      <Field>
        <FieldLabel>
          User config file path
        </FieldLabel>
        <div className="flex-1 flex gap-2">
          <Input
            readOnly
            value={settingsReadonly.user_config_file_path}
          />
          <Button
            onClick={() => mutationUtilDiskRevealInFinder.mutate({
              path: settingsReadonly.user_config_file_path
            })}
            isLoading={mutationUtilDiskRevealInFinder.isPending}
            disabled={mutationUtilDiskRevealInFinder.isPending}
            variant="secondary"
          >
            <HardDriveIcon />
            Reveal
          </Button>
        </div>
        <FieldDescription>
          This is the path to the user config file.
          <br />This file is the DataBase of the app.
          <br />IMPORTANT: Backup this file!
        </FieldDescription>
      </Field>
    </FieldGroup>
  );

}