import { useMutation, useQueryClient } from "@tanstack/react-query";

import { updateIssueStatus } from "../api/issues";
import type { IssueStatusUpdatePayload } from "../types/api";

type UpdateIssueStatusVariables = {
  issueKey: string;
  payload: IssueStatusUpdatePayload;
};

export function useUpdateIssueStatus(projectKey: string | undefined) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ issueKey, payload }: UpdateIssueStatusVariables) =>
      updateIssueStatus(issueKey, payload),
    onSuccess: async (_, { issueKey }) => {
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: ["projects", projectKey, "issues"],
        }),
        queryClient.invalidateQueries({ queryKey: ["issues", issueKey] }),
        queryClient.invalidateQueries({
          queryKey: ["issues", issueKey, "history"],
        }),
      ]);
    },
  });
}
