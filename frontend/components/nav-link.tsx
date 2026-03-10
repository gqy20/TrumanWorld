import Link from "next/link";
import { ReactNode } from "react";

type NavLinkProps = {
  href: string;
  eyebrow: string;
  title: string;
  children: ReactNode;
};

export function NavLink({ href, eyebrow, title, children }: NavLinkProps) {
  return (
    <Link
      href={href}
      className="group rounded-3xl border border-slate-200 bg-white p-6 shadow-xs transition hover:-translate-y-0.5 hover:border-moss/40 hover:shadow-md"
    >
      <div className="text-xs uppercase tracking-[0.25em] text-moss">{eyebrow}</div>
      <h2 className="mt-3 text-2xl font-semibold text-ink">{title}</h2>
      <p className="mt-2 text-sm text-slate-600">{children}</p>
    </Link>
  );
}
