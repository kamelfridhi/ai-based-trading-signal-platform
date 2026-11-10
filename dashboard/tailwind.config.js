/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Segoe UI", "system-ui", "sans-serif"],
        mono: ["Cascadia Code", "Consolas", "monospace"],
      },
      colors: {
        surface: {
          950: "#0a0e17",
          900: "#0f1624",
          800: "#151d2e",
          700: "#1c2738",
        },
        accent: {
          cyan: "#22d3ee",
          violet: "#a78bfa",
        },
      },
      boxShadow: {
        glow: "0 0 40px rgba(34, 211, 238, 0.08)",
      },
    },
  },
  plugins: [],
};
