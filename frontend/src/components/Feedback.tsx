export function ErrorNotice({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return <div className="alert error" role="alert"><span aria-hidden="true">!</span><p>{message}</p>{onRetry && <button type="button" onClick={onRetry}>Tekrar dene</button>}</div>;
}

export function EmptyState({ title, description, action, onAction }: {
  title: string; description: string; action?: string; onAction?: () => void;
}) {
  return <div className="empty-state"><span aria-hidden="true">◇</span><h2>{title}</h2><p>{description}</p>{action && <button className="primary-button" onClick={onAction}>{action}</button>}</div>;
}
