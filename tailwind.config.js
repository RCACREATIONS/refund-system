/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#18222f",
        paper: "#f7f8fa",
        navy: "#16324f",
        mint: "#d8f3e7",
        coral: "#ffebe2",
        sun: "#fff4cf",
      },
      boxShadow: {
        soft: "0 12px 32px rgba(19, 42, 66, 0.08)",
      },
    },
  },
  plugins: [],
};
