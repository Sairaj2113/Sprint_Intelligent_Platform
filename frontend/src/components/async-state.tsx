type AsyncStateProps = {
  title: string;
  description?: string;
};

export function LoadingState({ title }: AsyncStateProps) {
  return (
    <div className="animate-pulse rounded-lg border border-slate-200 bg-white p-5">
      <div className="h-4 w-32 rounded bg-slate-200" />
      <div className="mt-3 h-3 w-3/4 rounded bg-slate-100" />
      <p className="sr-only">{title}</p>
    </div>
  );
}

export function ErrorState({ title, description }: AsyncStateProps) {
  return (
    <div className="rounded-lg border border-rose-200 bg-rose-50 p-5 text-sm">
      <p className="font-semibold text-rose-950">{title}</p>
      <p className="mt-1 leading-6 text-rose-800">
        {description ?? "Check that the backend is available and try again."}
      </p>
    </div>
  );
}
