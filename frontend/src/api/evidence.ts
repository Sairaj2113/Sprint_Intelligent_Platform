import { apiClient } from "./client";
import type {
  EmployeeContributionEvidence,
  ProjectKpiResponse,
  ProjectWorkflowEvidenceResponse,
  SprintKpiResponse,
  SprintWorkflowEvidenceResponse,
} from "../types/api";

export async function getProjectKpis(projectKey: string): Promise<ProjectKpiResponse> {
  return (await apiClient.get(`/projects/${projectKey}/kpis`)).data;
}

export async function getSprintKpis(projectKey: string, sprintId: string): Promise<SprintKpiResponse> {
  return (await apiClient.get(`/projects/${projectKey}/sprints/${sprintId}/kpis`)).data;
}

export async function getEmployeeContribution(projectKey: string, employeeId: string): Promise<EmployeeContributionEvidence> {
  return (await apiClient.get(`/projects/${projectKey}/employees/${employeeId}/contribution`)).data;
}

export async function getSprintEmployeeContribution(projectKey: string, sprintId: string, employeeId: string): Promise<EmployeeContributionEvidence> {
  return (await apiClient.get(`/projects/${projectKey}/sprints/${sprintId}/employees/${employeeId}/contribution`)).data;
}

export async function getProjectWorkflow(projectKey: string): Promise<ProjectWorkflowEvidenceResponse> {
  return (await apiClient.get(`/projects/${projectKey}/workflow`)).data;
}

export async function getSprintWorkflow(projectKey: string, sprintId: string): Promise<SprintWorkflowEvidenceResponse> {
  return (await apiClient.get(`/projects/${projectKey}/sprints/${sprintId}/workflow`)).data;
}
