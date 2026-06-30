import { useMutation } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client/client.singleton";

const queryKeys = {
  mutation: {
    diskRevealInFinder: ['utils', 'mutation', 'diskRevealInFinder']
  }
};

export function useMutationUtilsDiskRevealInFinder() {
  return useMutation({
    mutationKey: queryKeys.mutation.diskRevealInFinder,
    mutationFn: (
      payload: Parameters<typeof apiClient.utils_disk_revealInFinder>[0]
    ) => apiClient.utils_disk_revealInFinder(payload),
  });
}