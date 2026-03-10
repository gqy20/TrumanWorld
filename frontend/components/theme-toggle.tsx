"use client";

import { motion } from "framer-motion";
import { useTheme, type Theme } from "@/lib/use-theme";

const OPTIONS: Array<{ value: Theme; icon: string; label: string }> = [
  { value: "light", icon: "☀️", label: "亮色" },
  { value: "dark", icon: "🌙", label: "深色" },
  { value: "system", icon: "💻", label: "系统" },
];

interface ThemeToggleProps {
  className?: string;
}

export function ThemeToggle({ className = "" }: ThemeToggleProps) {
  const { theme, setTheme, mounted } = useTheme();

  if (!mounted) {
    return (
      <div className={`flex items-center gap-1 rounded-full bg-(--sidebar-hover) p-1 ${className}`}>
        {OPTIONS.map((option) => (
          <button
            key={option.value}
            className="flex h-6 w-6 items-center justify-center rounded-full text-xs"
            disabled
          >
            {option.icon}
          </button>
        ))}
      </div>
    );
  }

  return (
    <div
      className={`flex items-center gap-0.5 rounded-full bg-(--sidebar-hover) p-1 ${className}`}
      role="radiogroup"
      aria-label="主题切换"
    >
      {OPTIONS.map((option) => (
        <button
          key={option.value}
          onClick={() => setTheme(option.value)}
          style={{ color: theme === option.value ? "var(--sidebar-text)" : "var(--sidebar-muted)" }}
          className="relative flex h-6 w-6 items-center justify-center rounded-full transition-colors hover:text-(--sidebar-text)"
          role="radio"
          aria-checked={theme === option.value}
          aria-label={option.label}
          title={option.label}
        >
          {theme === option.value && (
            <motion.div
              layoutId="theme-indicator"
              className="absolute inset-0 rounded-full bg-(--sidebar-active)"
              transition={{ type: "spring", stiffness: 400, damping: 30 }}
            />
          )}
          <span className="relative z-10 text-[11px]">{option.icon}</span>
        </button>
      ))}
    </div>
  );
}
