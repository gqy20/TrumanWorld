import type { Config } from "tailwindcss";

export default {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#172033",
        mist: "#eef3ea",
        moss: "#6f8b6b",
        ember: "#d86f45",
      },
    },
  },
  plugins: [],
} satisfies Config;

