import { ReactNode } from "react";

export function AdminPageLayout({ eyebrow, title, description, actions, children }: {
  eyebrow: string;
  title: string;
  description: string;
  actions?: ReactNode;
  children: ReactNode;
}) {
  return <main className="admin-page admin-page-layout"><header className="admin-page-layout__header"><div className="admin-page-layout__copy"><p className="admin-eyebrow">{eyebrow}</p><h1>{title}</h1><p>{description}</p></div>{actions && <div className="admin-page-layout__actions">{actions}</div>}</header><div className="admin-page-layout__body">{children}</div></main>;
}

export function AdminSection({ title, description, toolbar, children, className = "" }: {
  title: string;
  description?: string;
  toolbar?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return <section className={`admin-section admin-panel ${className}`.trim()}><div className="admin-section__header"><div><h2>{title}</h2>{description && <p>{description}</p>}</div>{toolbar && <div className="admin-section__toolbar">{toolbar}</div>}</div><div className="admin-section__content">{children}</div></section>;
}

export function AdminToolbar({ children }: { children: ReactNode }) {
  return <div className="admin-toolbar">{children}</div>;
}
