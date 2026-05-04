/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Dark theme colors
        bg: {
          primary: '#0a0a0a',
          secondary: '#111111',
          tertiary: '#1a1a1a',
        },
        border: {
          primary: '#1f1f1f',
          secondary: '#2a2a2a',
        },
        text: {
          primary: '#ffffff',
          secondary: '#a0a0a0',
          tertiary: '#6b6b6b',
        },
        accent: {
          primary: '#6366f1',
          secondary: '#8b5cf6',
        },
      },
    },
  },
  plugins: [],
}

