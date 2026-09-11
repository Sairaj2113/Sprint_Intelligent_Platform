import { useQuery } from "@tanstack/react-query";

import {
  getIssue,
  getIssueComments,
  getIssueDeployments,
  getIssueHistory,
  getIssueTests,
} from "../api/issues";

export function useIssue(issueKey: string | null, enabled = true) {
  return useQuery({
    queryKey: ["issues", issueKey],
    queryFn: () => getIssue(issueKey!),
    enabled: Boolean(issueKey) && enabled,
  });
}

export function useIssueHistory(issueKey: string | null, enabled = true) {
  return useQuery({
    queryKey: ["issues", issueKey, "history"],
    queryFn: () => getIssueHistory(issueKey!),
    enabled: Boolean(issueKey) && enabled,
  });
}

export function useIssueComments(issueKey: string | null, enabled = true) {
  return useQuery({
    queryKey: ["issues", issueKey, "comments"],
    queryFn: () => getIssueComments(issueKey!),
    enabled: Boolean(issueKey) && enabled,
  });
}

export function useIssueTests(issueKey: string | null, enabled = true) {
  return useQuery({
    queryKey: ["issues", issueKey, "tests"],
    queryFn: () => getIssueTests(issueKey!),
    enabled: Boolean(issueKey) && enabled,
  });
}

export function useIssueDeployments(issueKey: string | null, enabled = true) {
  return useQuery({
    queryKey: ["issues", issueKey, "deployments"],
    queryFn: () => getIssueDeployments(issueKey!),
    enabled: Boolean(issueKey) && enabled,
  });
}
