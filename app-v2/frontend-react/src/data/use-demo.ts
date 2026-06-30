import { useMutation } from '@tanstack/react-query';
import { apiClient } from '#/lib/api-client/client.singleton';

const queryKeys = {
  mutation: {
    jobDemoStart: ['playlists', 'mutation', 'demo', 'job', 'start'],
  },
};

export function useMutationDemoJobDemoStart() {
  return useMutation({
    mutationKey: queryKeys.mutation.jobDemoStart,
    mutationFn: () => apiClient.demo_jobDemoStart(),
  });
}

