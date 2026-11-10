import type { Config } from "tailwindcss";

export default {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  darkMode: "media",
  theme: {
    extend: {
      colors: {
        lapis: { 50: "#eef2ff", 100: "#dfe6ff", 400: "#6f8dff", 600: "#2447c8", 700: "#1c379c", 900: "#0b1233" },
        gold: { 400: "#e3b04b", 600: "#8a6212" },
        ink: { DEFAULT: "#1d1d1f", soft: "#3a3a3d", muted: "#5f5f64", faint: "#6e6e73" },
        surface: { DEFAULT: "#ffffff", 50: "#fbfbfd", 100: "#f5f5f7", 200: "#e8e8ed", 300: "#d2d2d7" },
        night: { DEFAULT: "#000000", 100: "#161618", 200: "#1c1c1e", 300: "#2c2c2e", 400: "#3a3a3c" },
        danger: { 50: "#fff4f2", 100: "#fde7e4", 600: "#b42318", 700: "#912018" },
        warn: { 50: "#fffaeb", 100: "#fef0c7", 700: "#93370d" },
        ok: { 50: "#ecfdf3", 600: "#067647" },
      },
      fontFamily: {
        sans: ["-apple-system", "BlinkMacSystemFont", "SF Arabic", "Segoe UI", "Noto Sans Arabic", "Tahoma", "sans-serif"],
        display: ["Reem Kufi", "-apple-system", "sans-serif"],
      },
    },
  },
  plugins: [],
} satisfies Config;
