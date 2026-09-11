import {
  DndContext,
  PointerSensor,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import { CircleUserRound, Layers3, Search, X } from "lucide-react";
import { useMemo, useRef, useState } from "react";
import { useParams } from "react-router-dom";

import { ErrorState, LoadingState } from "../components/async-state";
import { IssueDetailsDrawer } from "../components/issue-details-drawer";
import { useProjectIssues } from "../hooks/use-issues";
import { useUpdateIssueStatus } from "../hooks/use-update-issue-status";
import { DEMO_CURRENT_USER_ID } from "../lib/constants";
import type { Issue, IssueStatus, IssueType } from "../types/api";

type BoardStatus = Extract<
  IssueStatus,
  "TODO" | "IN_PROGRESS" | "CODE_REVIEW" | "TESTING" | "DONE"
>;

const boardColumns: { status: BoardStatus; label: string }[] = [
  { status: "TODO", label: "To Do" },
  { status: "IN_PROGRESS", label: "In Progress" },
  { status: "CODE_REVIEW", label: "Code Review" },
  { status: "TESTING", label: "Testing" },
  { status: "DONE", label: "Done" },
];

const statusLabels: Record<BoardStatus, string> = {
  TODO: "To Do",
  IN_PROGRESS: "In Progress",
  CODE_REVIEW: "Code Review",
  TESTING: "Testing",
  DONE: "Done",
};

const issueTypeStyles: Record<IssueType, string> = {
  EPIC: "border-violet-200 bg-violet-50 text-violet-700",
  STORY: "border-sky-200 bg-sky-50 text-sky-700",
  TASK: "border-slate-200 bg-slate-50 text-slate-700",
  BUG: "border-rose-200 bg-rose-50 text-rose-700",
  SUBTASK: "border-amber-200 bg-amber-50 text-amber-700",
};

const priorityStyles: Record<Issue["priority"], string> = {
  LOW: "text-slate-500",
  MEDIUM: "text-sky-700",
  HIGH: "text-amber-700",
  CRITICAL: "text-rose-700",
};

function initials(name: string): string {
  return name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();
}

function DraggableIssueCard({
  issue,
  isUpdating,
  onSelect,
}: {
  issue: Issue;
  isUpdating: boolean;
  onSelect: (issueKey: string) => void;
}) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: issue.id,
    data: { issueKey: issue.issue_key, status: issue.status },
    disabled: isUpdating,
  });

  const assigneeName = issue.assignee?.name;
  const style = transform
    ? { transform: `translate3d(${transform.x}px, ${transform.y}px, 0)` }
    : undefined;

  return (
    <button
      ref={setNodeRef}
      type="button"
      style={style}
      disabled={isUpdating}
      onClick={() => onSelect(issue.issue_key)}
      className={`w-full cursor-grab rounded-lg border border-slate-200 bg-white p-3 text-left shadow-sm transition hover:border-sky-300 hover:shadow-md active:cursor-grabbing disabled:cursor-wait disabled:opacity-60 ${
        isDragging ? "z-10 opacity-45 shadow-lg" : ""
      }`}
      {...attributes}
      {...listeners}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="font-mono text-xs text-slate-500">{issue.issue_key}</span>
        <span
          className={`rounded border px-1.5 py-0.5 text-[11px] font-medium uppercase tracking-wide ${issueTypeStyles[issue.issue_type]}`}
        >
          {issue.issue_type.toLowerCase()}
        </span>
      </div>

      <h3 className="mt-2 line-clamp-2 text-sm font-semibold leading-5 text-slate-900">
        {issue.title}
      </h3>

      <div className="mt-3 flex items-center justify-between gap-2 text-xs">
        <span className={`font-medium ${priorityStyles[issue.priority]}`}>
          {issue.priority.toLowerCase()} priority
        </span>
        {issue.story_points !== null && issue.story_points !== undefined ? (
          <span className="rounded bg-slate-100 px-1.5 py-0.5 font-medium text-slate-600">
            {issue.story_points} pt
          </span>
        ) : null}
      </div>

      <div className="mt-3 flex min-w-0 items-center justify-between gap-2 border-t border-slate-100 pt-3">
        <span className="truncate text-xs text-slate-500">
          {issue.parent_issue ? `${issue.parent_issue.issue_key} / ` : ""}
          {issue.sprint?.name ?? "No sprint"}
        </span>
        {assigneeName ? (
          <span
            title={assigneeName}
            className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-sky-100 text-[10px] font-semibold text-sky-700"
          >
            {initials(assigneeName)}
          </span>
        ) : (
          <CircleUserRound className="h-5 w-5 shrink-0 text-slate-300" aria-label="Unassigned" />
        )}
      </div>
    </button>
  );
}

function KanbanColumn({
  status,
  label,
  issues,
  isUpdating,
  onSelectIssue,
}: {
  status: BoardStatus;
  label: string;
  issues: Issue[];
  isUpdating: boolean;
  onSelectIssue: (issueKey: string) => void;
}) {
  const { setNodeRef, isOver } = useDroppable({
    id: status,
    data: { status },
  });

  return (
    <section
      ref={setNodeRef}
      className={`min-h-[32rem] min-w-[17rem] rounded-xl bg-slate-100/80 p-3 transition-shadow ${
        isOver ? "ring-2 ring-sky-400 ring-offset-2" : ""
      }`}
    >
      <div className="mb-3 flex items-center justify-between gap-3 px-1">
        <h2 className="text-sm font-semibold text-slate-800">{label}</h2>
        <span className="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-xs font-medium text-slate-600">
          {issues.length}
        </span>
      </div>

      <div className="space-y-3">
        {issues.length ? (
          issues.map((issue) => (
            <DraggableIssueCard
              key={issue.id}
              issue={issue}
              isUpdating={isUpdating}
              onSelect={onSelectIssue}
            />
          ))
        ) : (
          <p className="rounded-lg border border-dashed border-slate-300 bg-white/60 px-3 py-5 text-center text-sm text-slate-500">
            No issues
          </p>
        )}
      </div>
    </section>
  );
}

export function ProjectBoardPage() {
  const { projectKey } = useParams();
  const [selectedIssueKey, setSelectedIssueKey] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [sprintFilter, setSprintFilter] = useState("all");
  const [assigneeFilter, setAssigneeFilter] = useState("all");
  const [issueTypeFilter, setIssueTypeFilter] = useState<IssueType | "all">("all");
  const [statusFilter, setStatusFilter] = useState<BoardStatus | "all">("all");
  const didDragRef = useRef(false);
  const issuesQuery = useProjectIssues(projectKey);
  const updateStatusMutation = useUpdateIssueStatus(projectKey);
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
  );

  const issues = issuesQuery.data ?? [];
  const sprintOptions = useMemo(() => {
    const options = new Map<string, string>();

    for (const issue of issues) {
      if (issue.sprint_id) {
        options.set(issue.sprint_id, issue.sprint?.name ?? "Unnamed sprint");
      }
    }

    return Array.from(options, ([id, name]) => ({ id, name })).sort((a, b) =>
      a.name.localeCompare(b.name),
    );
  }, [issues]);
  const assigneeOptions = useMemo(() => {
    const options = new Map<string, string>();

    for (const issue of issues) {
      if (issue.assignee_id) {
        options.set(
          issue.assignee_id,
          issue.assignee ? `${issue.assignee.name} (${issue.assignee.employee_code})` : "Unknown assignee",
        );
      }
    }

    return Array.from(options, ([id, name]) => ({ id, name })).sort((a, b) =>
      a.name.localeCompare(b.name),
    );
  }, [issues]);
  const hasIssuesWithoutSprint = issues.some((issue) => issue.sprint_id === null);
  const hasUnassignedIssues = issues.some((issue) => issue.assignee_id === null);
  const filteredIssues = useMemo(() => {
    const searchTerm = search.trim().toLowerCase();

    return issues.filter((issue) => {
      const matchesSearch =
        !searchTerm ||
        issue.issue_key.toLowerCase().includes(searchTerm) ||
        issue.title.toLowerCase().includes(searchTerm);
      const matchesSprint =
        sprintFilter === "all" ||
        (sprintFilter === "none" ? issue.sprint_id === null : issue.sprint_id === sprintFilter);
      const matchesAssignee =
        assigneeFilter === "all" ||
        (assigneeFilter === "none"
          ? issue.assignee_id === null
          : issue.assignee_id === assigneeFilter);
      const matchesIssueType = issueTypeFilter === "all" || issue.issue_type === issueTypeFilter;
      const matchesStatus = statusFilter === "all" || issue.status === statusFilter;

      return matchesSearch && matchesSprint && matchesAssignee && matchesIssueType && matchesStatus;
    });
  }, [assigneeFilter, issueTypeFilter, issues, search, sprintFilter, statusFilter]);
  const issuesByStatus = useMemo(() => {
    const grouped: Record<BoardStatus, Issue[]> = {
      TODO: [],
      IN_PROGRESS: [],
      CODE_REVIEW: [],
      TESTING: [],
      DONE: [],
    };

    for (const issue of filteredIssues) {
      if (issue.status in grouped) {
        grouped[issue.status as BoardStatus].push(issue);
      }
    }

    return grouped;
  }, [filteredIssues]);
  const filtersAreActive =
    Boolean(search) ||
    sprintFilter !== "all" ||
    assigneeFilter !== "all" ||
    issueTypeFilter !== "all" ||
    statusFilter !== "all";

  function clearFilters() {
    setSearch("");
    setSprintFilter("all");
    setAssigneeFilter("all");
    setIssueTypeFilter("all");
    setStatusFilter("all");
  }

  function suppressCardClickBriefly() {
    window.setTimeout(() => {
      didDragRef.current = false;
    }, 150);
  }

  function handleDragStart() {
    didDragRef.current = true;
  }

  function handleDragCancel() {
    suppressCardClickBriefly();
  }

  function handleDragEnd(event: DragEndEvent) {
    const issue = issues.find((candidate) => candidate.id === event.active.id);
    const targetStatus = event.over?.data.current?.status as BoardStatus | undefined;

    if (
      issue &&
      targetStatus &&
      issue.status !== targetStatus &&
      !updateStatusMutation.isPending
    ) {
      updateStatusMutation.mutate({
        issueKey: issue.issue_key,
        payload: {
          new_status: targetStatus,
          changed_by: DEMO_CURRENT_USER_ID,
          notes: "Status changed from Kanban board",
        },
      });
    }

    suppressCardClickBriefly();
  }

  if (issuesQuery.isLoading) {
    return <LoadingState title="Loading project board..." />;
  }

  if (issuesQuery.isError) {
    return (
      <ErrorState
        title="Unable to load the board"
        description="The project issues could not be retrieved. Check that the backend is available and try again."
      />
    );
  }

  return (
    <>
      <div className="w-full px-5 py-7 sm:px-8 lg:px-10">
        <header className="mb-6">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-sky-700">
            {projectKey ?? "Project"} / Board
          </p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-950">Delivery board</h1>
          <p className="mt-2 text-sm text-slate-600">
            Drag an issue to another column to update its saved status.
          </p>
          <div className="mt-4 flex items-center gap-2 text-sm font-medium text-slate-700">
            <Layers3 className="h-4 w-4 text-sky-700" />
            {filteredIssues.length} of {issues.length} {issues.length === 1 ? "issue" : "issues"}
          </div>
        </header>

        {updateStatusMutation.isError ? (
          <div className="mb-5 rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">
            Status update failed. The board still reflects the saved database status. Please try again.
          </div>
        ) : null}

        <div className="mb-5 flex flex-wrap items-center gap-2 rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
          <label className="relative min-w-[13rem] flex-1 sm:max-w-xs">
            <span className="sr-only">Search issues</span>
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <input
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search key or title"
              className="h-9 w-full rounded-md border border-slate-200 bg-white pl-9 pr-3 text-sm text-slate-800 outline-none transition placeholder:text-slate-400 focus:border-sky-400 focus:ring-2 focus:ring-sky-100"
            />
          </label>
          <label>
            <span className="sr-only">Filter by sprint</span>
            <select
              value={sprintFilter}
              onChange={(event) => setSprintFilter(event.target.value)}
              className="h-9 max-w-48 rounded-md border border-slate-200 bg-white px-2 text-sm text-slate-700 outline-none focus:border-sky-400 focus:ring-2 focus:ring-sky-100"
            >
              <option value="all">All sprints</option>
              {sprintOptions.map((sprint) => (
                <option key={sprint.id} value={sprint.id}>
                  {sprint.name}
                </option>
              ))}
              {hasIssuesWithoutSprint ? <option value="none">No sprint</option> : null}
            </select>
          </label>
          <label>
            <span className="sr-only">Filter by assignee</span>
            <select
              value={assigneeFilter}
              onChange={(event) => setAssigneeFilter(event.target.value)}
              className="h-9 max-w-52 rounded-md border border-slate-200 bg-white px-2 text-sm text-slate-700 outline-none focus:border-sky-400 focus:ring-2 focus:ring-sky-100"
            >
              <option value="all">All assignees</option>
              {assigneeOptions.map((assignee) => (
                <option key={assignee.id} value={assignee.id}>
                  {assignee.name}
                </option>
              ))}
              {hasUnassignedIssues ? <option value="none">Unassigned</option> : null}
            </select>
          </label>
          <label>
            <span className="sr-only">Filter by issue type</span>
            <select
              value={issueTypeFilter}
              onChange={(event) => setIssueTypeFilter(event.target.value as IssueType | "all")}
              className="h-9 rounded-md border border-slate-200 bg-white px-2 text-sm text-slate-700 outline-none focus:border-sky-400 focus:ring-2 focus:ring-sky-100"
            >
              <option value="all">All types</option>
              {Object.keys(issueTypeStyles).map((issueType) => (
                <option key={issueType} value={issueType}>
                  {issueType}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span className="sr-only">Filter by status</span>
            <select
              value={statusFilter}
              onChange={(event) => setStatusFilter(event.target.value as BoardStatus | "all")}
              className="h-9 rounded-md border border-slate-200 bg-white px-2 text-sm text-slate-700 outline-none focus:border-sky-400 focus:ring-2 focus:ring-sky-100"
            >
              <option value="all">All statuses</option>
              {boardColumns.map(({ status }) => (
                <option key={status} value={status}>
                  {statusLabels[status]}
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            onClick={clearFilters}
            disabled={!filtersAreActive}
            className="inline-flex h-9 items-center gap-1.5 rounded-md px-2.5 text-sm font-medium text-slate-600 transition hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-40"
          >
            <X className="h-4 w-4" />
            Clear filters
          </button>
        </div>

        {issues.length === 0 ? (
          <div className="rounded-xl border border-dashed border-slate-300 bg-white px-6 py-14 text-center">
            <h2 className="text-base font-semibold text-slate-800">No issues in this project</h2>
            <p className="mt-1 text-sm text-slate-500">Issues will appear here when the project has work to track.</p>
          </div>
        ) : filteredIssues.length === 0 ? (
          <div className="rounded-xl border border-dashed border-slate-300 bg-white px-6 py-14 text-center">
            <h2 className="text-base font-semibold text-slate-800">No issues match the current filters.</h2>
            <p className="mt-1 text-sm text-slate-500">Clear or adjust a filter to see more project issues.</p>
          </div>
        ) : (
          <DndContext
            sensors={sensors}
            onDragStart={handleDragStart}
            onDragCancel={handleDragCancel}
            onDragEnd={handleDragEnd}
          >
            <div className="overflow-x-auto pb-3">
              <div className="grid min-w-[88rem] grid-cols-5 gap-4">
                {boardColumns.map(({ status, label }) => (
                  <KanbanColumn
                    key={status}
                    status={status}
                    label={label}
                    issues={issuesByStatus[status]}
                    isUpdating={updateStatusMutation.isPending}
                    onSelectIssue={(issueKey) => {
                      if (!didDragRef.current) {
                        setSelectedIssueKey(issueKey);
                      }
                    }}
                  />
                ))}
              </div>
            </div>
          </DndContext>
        )}
      </div>

      <IssueDetailsDrawer
        issueKey={selectedIssueKey}
        onClose={() => setSelectedIssueKey(null)}
      />
    </>
  );
}
