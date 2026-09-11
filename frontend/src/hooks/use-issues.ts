import { useQuery } from "@tanstack/react-query";

import { getProjectIssues } from "../api/issues";

export function useProjectIssues(projectKey: string | undefined) {
  return useQuery({
    queryKey: ["projects", projectKey, "issues"],
    queryFn: () => getProjectIssues(projectKey!),
    enabled: Boolean(projectKey),
  });
}
