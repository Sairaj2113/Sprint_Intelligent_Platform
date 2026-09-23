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
export type DocumentType =
  | "PRD"
  | "TRD"
  | "ARCHITECTURE"
  | "TESTING"
  | "RELEASE"
  | "DESIGN"
  | "OTHER";

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

export type IssueMetrics = {
  total_issues: number;
  completed_issues: number;
  open_issues: number;
  issue_completion_percentage: number;
};

export type StoryPointMetrics = {
  total_story_points: number;
  completed_story_points: number;
  remaining_story_points: number;
  story_point_completion_percentage: number;
};

export type BugMetrics = {
  total_bugs: number;
  resolved_bugs: number;
  open_bugs: number;
};

export type StatusDistribution = {
  todo: number;
  in_progress: number;
  code_review: number;
  testing: number;
  done: number;
};

export type AggregateDurationMetrics = {
  average_cycle_time_hours: number | null;
  average_development_time_hours: number | null;
  average_review_time_hours: number | null;
  average_testing_time_hours: number | null;
};

export type ProjectKpiResponse = {
  project_id: string;
  project_key: string;
  issue_metrics: IssueMetrics;
  story_point_metrics: StoryPointMetrics;
  bug_metrics: BugMetrics;
  status_distribution: StatusDistribution;
  duration_metrics: AggregateDurationMetrics;
};

export type SprintKpiResponse = {
  sprint_id: string;
  sprint_name: string;
  sprint_status: SprintStatus;
  issue_metrics: IssueMetrics;
  story_point_metrics: StoryPointMetrics;
  bug_metrics: BugMetrics;
  status_distribution: StatusDistribution;
  duration_metrics: AggregateDurationMetrics;
};

export type EmployeeContributionSummary = {
  employee_id: string;
  assigned_issues: number;
  completed_issues: number;
  assigned_story_points: number;
  completed_story_points: number;
  assigned_bugs: number;
  resolved_bugs: number;
  issues_reaching_testing: number;
  issues_deployed: number;
  issues_commented_on: number;
  reopen_count: number;
  average_cycle_time_hours: number | null;
  average_development_time_hours: number | null;
  average_review_time_hours: number | null;
  average_testing_time_hours: number | null;
};

export type EmployeeIssueEvidence = {
  issue_id: string;
  issue_key: string;
  title: string;
  issue_type: IssueType;
  status: IssueStatus;
  story_points: number | null;
  sprint_id: string | null;
  sprint_name: string | null;
  was_completed: boolean;
  reached_testing: boolean;
  was_deployed: boolean;
  reopen_count: number;
  cycle_time_hours: number | null;
  development_time_hours: number | null;
  review_time_hours: number | null;
  testing_time_hours: number | null;
  test_result_count: number;
  deployment_count: number;
  comment_count: number;
};

export type EmployeeContributionEvidence = {
  employee_id: string;
  employee_code: string;
  employee_name: string;
  project_id: string;
  project_key: string;
  project_name: string;
  sprint_id: string | null;
  sprint_name: string | null;
  summary: EmployeeContributionSummary;
  issues: EmployeeIssueEvidence[];
};

export type DeliveryStage =
  | "TODO"
  | "DEVELOPMENT"
  | "REVIEW"
  | "TESTING"
  | "DONE_NOT_DEPLOYED"
  | "DEPLOYED";

export type WorkflowTransitionSummary = {
  old_status: IssueStatus | null;
  new_status: IssueStatus;
  changed_at: string;
};

export type IssueWorkflowEvidence = {
  issue_id: string;
  issue_key: string;
  title: string;
  issue_type: IssueType;
  status: IssueStatus;
  story_points: number | null;
  sprint_id: string | null;
  sprint_name: string | null;
  transition_count: number;
  reopen_count: number;
  reached_in_progress: boolean;
  reached_code_review: boolean;
  reached_testing: boolean;
  reached_done: boolean;
  blocked_time_hours: number | null;
  cycle_time_hours: number | null;
  development_time_hours: number | null;
  review_time_hours: number | null;
  testing_time_hours: number | null;
  test_result_count: number;
  passed_test_count: number;
  failed_test_count: number;
  deployment_count: number;
  was_deployed: boolean;
  delivery_stage: DeliveryStage;
  transitions: WorkflowTransitionSummary[];
};

export type WorkflowEvidenceSummary = {
  total_issues: number;
  issues_in_todo: number;
  issues_in_development: number;
  issues_in_review: number;
  issues_in_testing: number;
  issues_done_not_deployed: number;
  issues_deployed: number;
  reopened_issues: number;
  total_reopen_count: number;
  issues_reaching_testing: number;
  issues_with_test_evidence: number;
  issues_with_failed_test_evidence: number;
  issues_with_deployment_evidence: number;
  average_cycle_time_hours: number | null;
  average_development_time_hours: number | null;
  average_review_time_hours: number | null;
  average_testing_time_hours: number | null;
  average_blocked_time_hours: number | null;
};

export type ProjectWorkflowEvidenceResponse = {
  project_id: string;
  project_key: string;
  project_name: string;
  summary: WorkflowEvidenceSummary;
  issues: IssueWorkflowEvidence[];
};

export type SprintWorkflowEvidenceResponse = ProjectWorkflowEvidenceResponse & {
  sprint_id: string;
  sprint_name: string;
  sprint_status: SprintStatus;
};

export type EvidenceSufficiencyStatus =
  | "SUFFICIENT"
  | "LIMITED"
  | "INSUFFICIENT"
  | "INVALID_CITATIONS";

export type GroundedAnalysisLimits = {
  max_issues?: number;
  max_tests?: number;
  max_deployments?: number;
  max_comments?: number;
  max_documents?: number;
};

export type GroundedAnalysisRequest = {
  question: string;
  top_k?: number;
  limits?: GroundedAnalysisLimits;
};

export type GroundedClaim = {
  statement: string;
  source_ids: string[];
};

export type GroundedAnswer = {
  answer: string;
  claims: GroundedClaim[];
  limitations: string[];
};

export type CitationValidation = {
  valid: boolean;
  cited_source_ids: string[];
  valid_source_ids: string[];
  invalid_source_ids: string[];
};

export type EvidenceSufficiency = {
  status: EvidenceSufficiencyStatus;
  can_proceed: boolean;
  reasons: string[];
  limitations: string[];
};

export type LLMUsage = {
  input_tokens: number | null;
  output_tokens: number | null;
  total_tokens: number | null;
};

export type GenerationMetadata = {
  provider: string | null;
  model: string | null;
  fallback_used: boolean | null;
  usage: LLMUsage | null;
};

export type GroundedAnalysisSourceType =
  | "ISSUE"
  | "TEST"
  | "DEPLOYMENT"
  | "COMMENT"
  | "DOCUMENT";

export type GroundedAnalysisSource = {
  source_id: string;
  source_type: GroundedAnalysisSourceType;
  title: string;
  issue_key: string | null;
  record_id: string | null;
  document_id: string | null;
  chunk_id: string | null;
  chunk_index: number | null;
  document_type: DocumentType | null;
  page_number: number | null;
  section_title: string | null;
};

export type GroundedAnalysisResponse = {
  question: string;
  answer: GroundedAnswer | null;
  citation_validation: CitationValidation | null;
  evidence: EvidenceSufficiency;
  generation: GenerationMetadata;
  sources: GroundedAnalysisSource[];
};
