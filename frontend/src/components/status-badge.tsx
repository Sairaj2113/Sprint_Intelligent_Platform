type StatusBadgeProps = {
  status: string;
};

const statusStyles: Record<string, string> = {
  ACTIVE: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  COMPLETED: "bg-sky-50 text-sky-700 ring-sky-200",
  PLANNING: "bg-violet-50 text-violet-700 ring-violet-200",
  ON_HOLD: "bg-amber-50 text-amber-700 ring-amber-200",
  ARCHIVED: "bg-slate-100 text-slate-600 ring-slate-200",
  PLANNED: "bg-slate-100 text-slate-600 ring-slate-200",
  TODO: "bg-slate-100 text-slate-700 ring-slate-200",
  IN_PROGRESS: "bg-amber-50 text-amber-700 ring-amber-200",
  CODE_REVIEW: "bg-violet-50 text-violet-700 ring-violet-200",
  TESTING: "bg-sky-50 text-sky-700 ring-sky-200",
  DONE: "bg-emerald-50 text-emerald-700 ring-emerald-200",
};

export function StatusBadge({ status }: StatusBadgeProps) {
  const label = status.replace(/_/g, " ").toLowerCase();
  return (
    <span
      className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold capitalize ring-1 ring-inset ${statusStyles[status] ?? "bg-slate-100 text-slate-700 ring-slate-200"}`}
    >
      {label}
    </span>
  );
}
