import { useForm } from "@tanstack/react-form";
import z from "zod";
import { PlusIcon } from "lucide-react";

import { useAddPlaylist } from "@/data/use-playlists";

import { toast } from "@/components/ui/sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Field, FieldDescription, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { tanstackFormUtils } from "@/utils/tanstack-form";


export function FormAddPlaylist() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>
          Add New Spotify Playlist
        </CardTitle>
      </CardHeader>
      <CardContent>
        <TheForm />
      </CardContent>
    </Card>
  );
}


const schemaForm = z.object({
  playlistSpotifyUrl: z
    .string()
    .min(1, { error: "Required" })
    .pipe(
      z.url()
    ),
});
type FormValues = z.infer<typeof schemaForm>;

function TheForm() {

  // mutation
  const mutationAddPlaylist = useAddPlaylist();

  // local state form
  const formApi = useForm({
    validators: {
      onSubmit: schemaForm,
    },
    defaultValues: {
      playlistSpotifyUrl: '',
    } satisfies FormValues,
    onSubmitInvalid: (errors) => {
      const fieldsErrors = errors.formApi.getAllErrors();
      toast.error("Invalid form data, please fix and try again.");
      toast.error(JSON.stringify(fieldsErrors.form.errors, null, 2));
    },
    onSubmit: async ({ value }) => {
      // call server
      const serverResult = await mutationAddPlaylist.mutateAsync(value);
      if (serverResult) {
        toast.success("Playlist added!");
        return;
      }
      toast.error("Error adding playlist");
    },
  });

  return (
    <form
      className="flex flex-col gap-4"
      onSubmit={(e) => {
        e.preventDefault();
        formApi.handleSubmit();
      }}
    >

      <FieldGroup>

        <formApi.Field name="playlistSpotifyUrl">
          {(fieldApi) => {
            const isInvalid = tanstackFormUtils.isFieldInvalid(fieldApi);
            return (
              <Field data-invalid={isInvalid}>
                <FieldLabel htmlFor={fieldApi.name}>
                  Playlist Spotify URL
                </FieldLabel>
                <Input
                  id={fieldApi.name}
                  name={fieldApi.name}
                  value={fieldApi.state.value}
                  onBlur={fieldApi.handleBlur}
                  onChange={(e) => fieldApi.handleChange(e.target.value)}
                  autoComplete="off"
                  aria-invalid={isInvalid}
                  placeholder="https://open.spotify.com/playlist/33FahYVoz6g4ukPFJMfJaw?si=18dbd42f14ea489a"
                />
                {isInvalid && (
                  <FieldError errors={fieldApi.state.meta.errors} />
                )}
                <FieldDescription>
                  You should get from Spotify - Playlist - Share - Copy link
                </FieldDescription>
              </Field>
            );
          }}
        </formApi.Field>

        <Field orientation="horizontal">
          <Button
            type="submit"
            className="leading-none"
            disabled={mutationAddPlaylist.isPending}
            isLoading={mutationAddPlaylist.isPending}
          >
            <PlusIcon />
            Add Playlist
          </Button>
        </Field>
      </FieldGroup>

    </form>
  );
}