import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "#/lib/api-client/client.singleton";

const queryKeys = {
  query: {
    settings: ['settings']
  },
  mutation: {
    updateSettings: ['settings', 'mutation', 'updateSettings']
  }
};

export const useSettings = () => {
  return useQuery({
    queryKey: queryKeys.query.settings,
    queryFn: () => apiClient.settings_get(),
  });
};

export function useMutationUpdateSettings() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationKey: queryKeys.mutation.updateSettings,
    mutationFn: (
      payload: Parameters<typeof apiClient.settings_update>[0]
    ) => apiClient.settings_update(payload),
    onSettled: () => {
      queryClient.invalidateQueries();
    }
  });
}