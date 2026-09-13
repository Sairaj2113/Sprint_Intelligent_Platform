import { useQuery } from "@tanstack/react-query";

import {
  getEmployeeContribution,
  getProjectKpis,
  getProjectWorkflow,
  getSprintEmployeeContribution,
  getSprintKpis,
  getSprintWorkflow,
} from "../api/evidence";

export function useProjectKpis(projectKey: string | undefined) {
  return useQuery({ queryKey: ["project-kpis", projectKey], queryFn: () => getProjectKpis(projectKey!), enabled: Boolean(projectKey) });
}

export function useSprintKpis(projectKey: string | undefined, sprintId: string | undefined) {
  return useQuery({ queryKey: ["sprint-kpis", projectKey, sprintId], queryFn: () => getSprintKpis(projectKey!, sprintId!), enabled: Boolean(projectKey && sprintId) });
}

export function useEmployeeContribution(projectKey: string | undefined, employeeId: string | undefined) {
  return useQuery({ queryKey: ["employee-contribution", projectKey, employeeId], queryFn: () => getEmployeeContribution(projectKey!, employeeId!), enabled: Boolean(projectKey && employeeId) });
}

export function useSprintEmployeeContribution(projectKey: string | undefined, sprintId: string | undefined, employeeId: string | undefined) {
  return useQuery({ queryKey: ["sprint-employee-contribution", projectKey, sprintId, employeeId], queryFn: () => getSprintEmployeeContribution(projectKey!, sprintId!, employeeId!), enabled: Boolean(projectKey && sprintId && employeeId) });
}

export function useProjectWorkflow(projectKey: string | undefined) {
  return useQuery({ queryKey: ["project-workflow", projectKey], queryFn: () => getProjectWorkflow(projectKey!), enabled: Boolean(projectKey) });
}

export function useSprintWorkflow(projectKey: string | undefined, sprintId: string | undefined) {
  return useQuery({ queryKey: ["sprint-workflow", projectKey, sprintId], queryFn: () => getSprintWorkflow(projectKey!, sprintId!), enabled: Boolean(projectKey && sprintId) });
}
