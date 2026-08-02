interface ErrorStateProps {
  message: string;
  onRetry?: () => void;
  size?: "sm" | "md" | "lg";
  requestId?: string | null;
}

export function ErrorState({ message, onRetry, size = "md", requestId }: ErrorStateProps) {
  const iconSizes = {
    sm: "h-8 w-8",
    md: "h-12 w-12",
    lg: "h-16 w-16",
  };

  const textSizes = {
    sm: "text-xs",
    md: "text-sm",
    lg: "text-base",
  };

  return (
    <div className="flex flex-col items-center justify-center py-8 text-slate-400">
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        className={iconSizes[size]}
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
        />
      </svg>
      <p className={`mt-3 ${textSizes[size]} text-slate-500`}>{message}</p>
      {requestId ? (
        <p className="mt-1 font-mono text-[11px] text-slate-400">问题编号：{requestId}</p>
      ) : null}
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="mt-4 rounded-full border border-slate-200 bg-white px-4 py-2 text-sm text-slate-600 transition hover:border-moss hover:text-moss"
        >
          重试
        </button>
      )}
    </div>
  );
}
