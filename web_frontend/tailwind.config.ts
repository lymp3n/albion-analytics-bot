import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        apple: {
          black: "#0A0A0E",
          charcoal: "#111115",
          slate: "#1A1A21",
          blue: "#007AFF",
          text: "#F5F5F7",
          muted: "#B7B7C2",
        },
      },
      boxShadow: {
        glass: "0 20px 70px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.16)",
      },
      backdropBlur: {
        xl2: "34px",
      },
      letterSpacing: {
        tightplus: "-0.02em",
      },
      borderRadius: {
        shell: "24px",
      },
    },
  },
  plugins: [],
};

export default config;
