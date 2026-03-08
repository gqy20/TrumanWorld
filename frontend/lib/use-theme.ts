"use client";

import { useEffect, useState } from "react";

export type Theme = "light" | "dark" | "system";

const THEME_KEY = "theme";

export function useTheme() {
  const [theme, setThemeState] = useState<Theme>("system");
  const [resolvedTheme, setResolvedTheme] = useState<"light" | "dark">("light");
  const [mounted, setMounted] = useState(false);

  // 初始化：从 localStorage 读取，默认亮色
  useEffect(() => {
    const stored = localStorage.getItem(THEME_KEY) as Theme | null;
    if (stored && ["light", "dark", "system"].includes(stored)) {
      setThemeState(stored);
    } else {
      // 未曾选择过主题，默认亮色
      setThemeState("light");
    }
    setMounted(true);
  }, []);

  // 监听系统主题变化
  useEffect(() => {
    if (!mounted) return;

    const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");

    const updateResolvedTheme = () => {
      if (theme === "system") {
        setResolvedTheme(mediaQuery.matches ? "dark" : "light");
      } else {
        setResolvedTheme(theme);
      }
    };

    updateResolvedTheme();
    mediaQuery.addEventListener("change", updateResolvedTheme);

    return () => mediaQuery.removeEventListener("change", updateResolvedTheme);
  }, [theme, mounted]);

  // 应用主题 class
  useEffect(() => {
    if (!mounted) return;

    const root = document.documentElement;
    root.classList.remove("light", "dark");
    root.classList.add(resolvedTheme);
  }, [resolvedTheme, mounted]);

  const setTheme = (newTheme: Theme) => {
    setThemeState(newTheme);
    localStorage.setItem(THEME_KEY, newTheme);
  };

  return {
    theme,
    resolvedTheme,
    setTheme,
    mounted,
  };
}
