import { apiClient } from "./client";
import type {
  Comment,
  Deployment,
  Issue,
  IssueHistory,
  IssueStatusTransition,
  IssueStatusUpdatePayload,
  TestResult,
} from "../types/api";

export async function getProjectIssues(projectKey: string): Promise<Issue[]> {
  const response = await apiClient.get<Issue[]>(`/projects/${projectKey}/issues`);
  if (!Array.isArray(response.data)) {
    throw new Error("Unexpected project issues response from the API.");
  }
  return response.data;
}

export async function getIssue(issueKey: string): Promise<Issue> {
  const response = await apiClient.get<Issue>(`/issues/${issueKey}`);
  return response.data;
}

export async function getIssueHistory(issueKey: string): Promise<IssueHistory[]> {
  const response = await apiClient.get<IssueHistory[]>(`/issues/${issueKey}/history`);
  return response.data;
}

export async function getIssueComments(issueKey: string): Promise<Comment[]> {
  const response = await apiClient.get<Comment[]>(`/issues/${issueKey}/comments`);
  return response.data;
}

export async function getIssueTests(issueKey: string): Promise<TestResult[]> {
  const response = await apiClient.get<TestResult[]>(`/issues/${issueKey}/tests`);
  return response.data;
}

export async function getIssueDeployments(issueKey: string): Promise<Deployment[]> {
  const response = await apiClient.get<Deployment[]>(
    `/issues/${issueKey}/deployments`,
  );
  return response.data;
}

export async function updateIssueStatus(
  issueKey: string,
  payload: IssueStatusUpdatePayload,
): Promise<IssueStatusTransition> {
  const response = await apiClient.patch<IssueStatusTransition>(
    `/issues/${issueKey}/status`,
    payload,
  );
  return response.data;
}
