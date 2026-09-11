import { useQuery } from "@tanstack/react-query";

import {
  getProject,
  getProjectMembers,
  getProjects,
  getProjectSprints,
} from "../api/projects";

export function useProjects() {
  return useQuery({
    queryKey: ["projects"],
    queryFn: getProjects,
  });
}

export function useProject(projectKey: string | undefined) {
  return useQuery({
    queryKey: ["projects", projectKey],
    queryFn: () => getProject(projectKey!),
    enabled: Boolean(projectKey),
  });
}

export function useProjectMembers(projectKey: string | undefined) {
  return useQuery({
    queryKey: ["projects", projectKey, "members"],
    queryFn: () => getProjectMembers(projectKey!),
    enabled: Boolean(projectKey),
  });
}

export function useProjectSprints(projectKey: string | undefined) {
  return useQuery({
    queryKey: ["projects", projectKey, "sprints"],
    queryFn: () => getProjectSprints(projectKey!),
    enabled: Boolean(projectKey),
  });
}
