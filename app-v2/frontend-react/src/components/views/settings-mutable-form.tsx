import { useForm } from "@tanstack/react-form";

import { schemaSettings, type Settings } from "#/lib/api-client/types";

import { toast } from "@/components/ui/sonner";
import { cn } from "@/lib/utils";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Field, FieldDescription, FieldError, FieldGroup, FieldLabel, FieldLegend, FieldSet } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { tanstackFormUtils } from "@/utils/tanstack-form";
import { useMutationUtilsDiskRevealInFinder } from "#/data/use-utils";
import { HardDriveIcon } from "lucide-react";

type SettingsMutableFormProps = {
  initialValues: Settings['mutable'];
  onSubmit: (value: Settings['mutable']) => Promise<(
    | { status: 'success', message?: string; }
    | { status: 'error', message: string; }
  )>;
};


export function SettingsMutableForm(
  props: SettingsMutableFormProps
) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>
          Settings Mutable
        </CardTitle>
        <CardDescription>
          Those settings are mutable, you can change them!
        </CardDescription>
      </CardHeader>
      <CardContent>
        <TheForm {...props} />
      </CardContent>
    </Card>
  );
}

export function TheForm({
  initialValues,
  onSubmit,
}: SettingsMutableFormProps) {

  // local state - form

  const formApi = useForm({
    validators: {
      onSubmit: schemaSettings.shape.mutable,
    },
    defaultValues: initialValues,
    onSubmitInvalid: (errors) => {
      const fieldsErrors = errors.formApi.getAllErrors();
      toast.error("Invalid form data, please fix and try again.");
      toast.error(JSON.stringify(fieldsErrors.form.errors, null, 2));
    },
    onSubmit: async ({ value }) => {
      // call server
      const serverResult = await onSubmit(value);
      if (serverResult.status === 'success') {
        toast.success("Form submitted successfully");
        toast.success(serverResult.message);
        return;
      }
      toast.error(serverResult.message);
    },
  });

  // server utils

  const mutationUtilDiskRevealInFinder = useMutationUtilsDiskRevealInFinder();

  // render

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        formApi.handleSubmit();
      }}
    >
      {/* {fieldsErrors. > 0 && (
        <AlertMessage
          variant="error"
          title="Error"
          subtitle="Invalid form data, please fix and try again."
          messages={validationErrors}
        />
      )} */}
      <FieldGroup>

        <formApi.Field name="setting_disk_download_path">
          {(fieldApi) => {
            const isInvalid = tanstackFormUtils.isFieldInvalid(fieldApi);
            return (
              <Field data-invalid={isInvalid}>
                <FieldLabel htmlFor={fieldApi.name}>
                  Download Folder
                </FieldLabel>
                <div className="flex-1 flex gap-2">
                  <Input
                    id={fieldApi.name}
                    name={fieldApi.name}
                    value={fieldApi.state.value}
                    onBlur={fieldApi.handleBlur}
                    onChange={(e) => fieldApi.handleChange(e.target.value)}
                    autoComplete="off"
                    aria-invalid={isInvalid}
                  />
                  <Button
                    onClick={() => mutationUtilDiskRevealInFinder.mutate({
                      path: fieldApi.state.value
                    })}
                    isLoading={mutationUtilDiskRevealInFinder.isPending}
                    disabled={mutationUtilDiskRevealInFinder.isPending}
                    variant="secondary"
                  >
                    <HardDriveIcon />
                    Reveal
                  </Button>
                </div>
                {isInvalid && (
                  <FieldError errors={fieldApi.state.meta.errors} />
                )}
                <FieldDescription>
                  This folder is the base folder where tracks will be downloaded.
                  <br />Each playlit will have its own sub-folder.
                </FieldDescription>
              </Field>
            );
          }}
        </formApi.Field>

        <formApi.Field name="setting_disk_filename_pattern">
          {(fieldApi) => {
            const isInvalid = tanstackFormUtils.isFieldInvalid(fieldApi);
            return (
              <Field data-invalid={isInvalid}>
                <FieldLabel htmlFor={fieldApi.name}>
                  File Name Pattern
                </FieldLabel>
                <Input
                  id={fieldApi.name}
                  name={fieldApi.name}
                  value={fieldApi.state.value}
                  onBlur={fieldApi.handleBlur}
                  onChange={(e) => fieldApi.handleChange(e.target.value)}
                  autoComplete="off"
                  aria-invalid={isInvalid}
                />
                {isInvalid && (
                  <FieldError errors={fieldApi.state.meta.errors} />
                )}
                <FieldDescription>
                  This pattern will be converted to filename, and used for each downloaded track.
                  <br />You can construct it using the following variables:
                  <ul>
                    <li><code>{'{index}'}</code></li>
                    <li><code>{'{artist}'}</code></li>
                    <li><code>{'{title}'}</code></li>
                  </ul>
                </FieldDescription>
              </Field>
            );
          }}
        </formApi.Field>

        <Field orientation="horizontal">
          <Button type="button" variant="outline" onClick={() => formApi.reset()}>
            Reset
          </Button>
          <Button type="submit">
            Submit
          </Button>
        </Field>

      </FieldGroup>
    </form>
  );
}

// ui

function AlertMessage({
  variant,
  title,
  subtitle,
  messages,
}: {
  variant: "success" | "error",
  title: string,
  subtitle?: string,
  messages?: string[],
}) {
  return (
    <div
      className={cn(
        "p-4 rounded",
        variant === "success" && "bg-green-500/10 text-green-500",
        variant === "error" && "bg-red-500/10 text-red-500",
      )}
    >
      <p className="font-bold">
        {title}
      </p>
      {subtitle && (
        <p className="text-muted-foreground">
          {subtitle}
        </p>
      )}
      {messages && messages.map((message) => (
        <p key={message}>
          {message}
        </p>
      ))}
    </div>
  );
}