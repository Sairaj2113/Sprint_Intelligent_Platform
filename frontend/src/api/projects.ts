import { apiClient } from "./client";
import type { Project, ProjectMember, Sprint } from "../types/api";

function requireArray<T>(value: unknown, resource: string): T[] {
  if (!Array.isArray(value)) {
    throw new Error(`Unexpected ${resource} response from the API.`);
  }
  return value as T[];
}

function requireObject<T>(value: unknown, resource: string): T {
  if (!value || Array.isArray(value) || typeof value !== "object") {
    throw new Error(`Unexpected ${resource} response from the API.`);
  }
  return value as T;
}

export async function getProjects(): Promise<Project[]> {
  const response = await apiClient.get<Project[]>("/projects");
  return requireArray<Project>(response.data, "projects");
}

export async function getProject(projectKey: string): Promise<Project> {
  const response = await apiClient.get<Project>(`/projects/${projectKey}`);
  return requireObject<Project>(response.data, "project");
}

export async function getProjectMembers(projectKey: string): Promise<ProjectMember[]> {
  const response = await apiClient.get<ProjectMember[]>(
    `/projects/${projectKey}/members`,
  );
  return requireArray<ProjectMember>(response.data, "project members");
}

export async function getProjectSprints(projectKey: string): Promise<Sprint[]> {
  const response = await apiClient.get<Sprint[]>(
    `/projects/${projectKey}/sprints`,
  );
  return requireArray<Sprint>(response.data, "project sprints");
}
