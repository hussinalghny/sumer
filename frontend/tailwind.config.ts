import type { Config } from "tailwindcss";

// اللون المميز: لازورد أور (Lapis of Ur) — أزرق عراقي تاريخي
export default {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        lapis: { 50: "#eef2ff", 100: "#dfe6ff", 200: "#c0ccff", 400: "#6f8dff", 500: "#3a5fe6", 600: "#2447c8", 700: "#1c379c", 800: "#18307f", 900: "#142659" },
        gold: { 400: "#e3b04b", 500: "#c99a2e", 600: "#a87d1e" },
        ink: { DEFAULT: "#1d1d1f", soft: "#424245", muted: "#6e6e73", faint: "#86868b" },
        surface: { DEFAULT: "#ffffff", 50: "#fbfbfd", 100: "#f5f5f7", 200: "#e8e8ed", 300: "#d2d2d7" },
        night: { DEFAULT: "#000000", 50: "#0b0b0d", 100: "#161618", 200: "#1c1c1e", 300: "#2c2c2e", 400: "#3a3a3c" },
      },
      fontFamily: {
        sans: ["-apple-system", "BlinkMacSystemFont", "SF Arabic", "SF Pro Text", "Segoe UI", "Noto Sans Arabic", "Tahoma", "sans-serif"],
      },
      boxShadow: {
        soft: "0 1px 2px rgba(0,0,0,.04), 0 8px 28px rgba(0,0,0,.06)",
        ring: "0 0 0 5px rgba(36,71,200,.12)",
      },
      borderRadius: { "4xl": "2rem" },
    },
  },
  plugins: [],
} satisfies Config;
