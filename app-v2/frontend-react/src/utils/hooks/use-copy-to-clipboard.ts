import { toast } from "#/components/ui/sonner";

export function useCopyToClipboard() {
  const copy = async ({
    text,
    showToast = true
  }: {
    text: string,
    showToast?: boolean;
  }) => {
    return navigator.clipboard.writeText(text)
      .then(() => true)
      .catch(() => false)
      .then((copied) => {
        if (showToast) {
          if (copied) toast.success('Copied to clipboard');
          else toast.error('Failed to copy to clipboard');
        }
        return copied;
      });
  };

  return { copy };
}