import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#EEF4FF',
          100: '#DCE7FD',
          200: '#B9CDFB',
          300: '#8AADF7',
          400: '#5A87F0',
          500: '#2F63E5',
          600: '#1A4BD1',
          700: '#123BB4',
          800: '#0E2E8F',
          900: '#0B2472',
          950: '#071640',
        },
      },
      fontFamily: {
        sans: ['Inter', '-apple-system', 'Segoe UI', 'Roboto', 'Helvetica Neue', 'Arial', 'sans-serif'],
      },
      boxShadow: {
        card: '0 1px 2px 0 rgb(11 36 114 / 0.06), 0 4px 16px -4px rgb(11 36 114 / 0.08)',
        modal: '0 24px 64px -12px rgb(7 22 64 / 0.35)',
      },
    },
  },
  plugins: [],
} satisfies Config
