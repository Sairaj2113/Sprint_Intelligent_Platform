export type ApiHealth = {
  status: string;
};

export type ProjectMethodology = "SCRUM" | "KANBAN" | "HYBRID";
export type ProjectStatus =
  | "PLANNING"
  | "ACTIVE"
  | "ON_HOLD"
  | "COMPLETED"
  | "ARCHIVED";
export type SprintStatus = "PLANNED" | "ACTIVE" | "COMPLETED";

export type EmployeeSummary = {
  id: string;
  employee_code: string;
  name: string;
  role: string | null;
};

export type EmployeeNameSummary = {
  id: string;
  employee_code: string;
  name: string;
};

export type Employee = EmployeeSummary & {
  email: string;
  department: string | null;
  is_active: boolean;
};

export type Project = {
  id: string;
  project_key: string;
  name: string;
  description: string | null;
  methodology: ProjectMethodology | null;
  status: ProjectStatus;
  project_lead_id: string | null;
  project_lead: EmployeeSummary | null;
};

export type ProjectMember = {
  id: string;
  project_id: string;
  employee_id: string;
  employee: Employee;
};

export type Sprint = {
  id: string;
  project_id: string;
  name: string;
  goal: string | null;
  status: SprintStatus;
  start_date: string | null;
  end_date: string | null;
  started_at: string | null;
  completed_at: string | null;
};

export type SprintSummary = {
  id: string;
  name: string;
  status: SprintStatus;
};

export type IssueType = "EPIC" | "STORY" | "TASK" | "BUG" | "SUBTASK";
export type IssuePriority = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
export type IssueStatus =
  | "BACKLOG"
  | "SELECTED_FOR_SPRINT"
  | "TODO"
  | "IN_PROGRESS"
  | "CODE_REVIEW"
  | "TESTING"
  | "READY_FOR_RELEASE"
  | "DONE";

export type ParentIssueSummary = {
  id: string;
  issue_key: string;
  title: string;
};

export type Issue = {
  id: string;
  issue_key: string;
  project_id: string;
  sprint_id: string | null;
  assignee_id: string | null;
  reporter_id: string | null;
  parent_issue_id: string | null;
  issue_type: IssueType;
  title: string;
  description: string | null;
  priority: IssuePriority;
  story_points: number | null;
  status: IssueStatus;
  acceptance_criteria: string | null;
  technical_notes: string | null;
  start_date: string | null;
  due_date: string | null;
  assignee: EmployeeSummary | null;
  reporter: EmployeeNameSummary | null;
  parent_issue: ParentIssueSummary | null;
  sprint: SprintSummary | null;
};

export type IssueHistory = {
  id: string;
  issue_id: string;
  old_status: IssueStatus | null;
  new_status: IssueStatus;
  changed_by: string | null;
  changed_at: string;
  notes: string | null;
  changed_by_employee: EmployeeNameSummary | null;
};

export type Comment = {
  id: string;
  issue_id: string;
  employee_id: string;
  content: string;
  created_at: string;
  employee: EmployeeNameSummary | null;
};

export type TestingStatus = "NOT_STARTED" | "IN_PROGRESS" | "PASSED" | "FAILED";

export type TestResult = {
  id: string;
  issue_id: string;
  testing_status: TestingStatus;
  test_cases_total: number | null;
  test_cases_passed: number | null;
  bugs_found: number | null;
  reopened_count: number | null;
  testing_notes: string | null;
  tested_by: string | null;
  tested_at: string | null;
  tested_by_employee: EmployeeNameSummary | null;
};

export type DeploymentStatus =
  | "NOT_DEPLOYED"
  | "STAGING"
  | "PRODUCTION"
  | "FAILED";

export type Deployment = {
  id: string;
  issue_id: string;
  deployment_status: DeploymentStatus;
  environment: string | null;
  deployment_date: string | null;
  production_notes: string | null;
  production_incidents: string | null;
};

export type IssueStatusUpdatePayload = {
  new_status: IssueStatus;
  changed_by: string;
  notes?: string | null;
};

export type IssueStatusTransition = {
  issue_key: string;
  old_status: IssueStatus;
  new_status: IssueStatus;
  changed_by: string;
  changed_at: string;
  notes: string | null;
};
