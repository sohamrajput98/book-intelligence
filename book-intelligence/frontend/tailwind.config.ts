import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        background: "#0b1118",
        foreground: "#e5edf7",
        card: "#121a24",
        border: "#233142",
        muted: "#a2b4c9",
        accent: "#6fd3c0",
        primary: "#f4a261",
        danger: "#ef476f"
      }
    }
  },
  plugins: []
};

export default config;
