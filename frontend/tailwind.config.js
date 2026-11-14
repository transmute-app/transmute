/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      keyframes: {
        shimmer: {
          '0%': { backgroundPosition: '200% 0' },
          '100%': { backgroundPosition: '-200% 0' },
        },
      },
      animation: {
        shimmer: 'shimmer 1.4s linear infinite',
      },
      // All colors reference CSS custom properties defined per [data-theme] in
      // index.css. The `<alpha-value>` placeholder lets Tailwind's opacity
      // modifiers work (e.g. bg-primary/20 → rgb(var(--color-primary) / 0.2)).
      colors: {
        primary: {
          DEFAULT: 'rgb(var(--color-primary) / <alpha-value>)',
          light:   'rgb(var(--color-primary-light) / <alpha-value>)',
          dark:    'rgb(var(--color-primary-dark) / <alpha-value>)',
        },
        accent:  'rgb(var(--color-accent) / <alpha-value>)',
        success: {
          DEFAULT: 'rgb(var(--color-success) / <alpha-value>)',
          light:   'rgb(var(--color-success-light) / <alpha-value>)',
          dark:    'rgb(var(--color-success-dark) / <alpha-value>)',
        },
        surface: {
          dark:  'rgb(var(--color-surface-dark) / <alpha-value>)',
          light: 'rgb(var(--color-surface-light) / <alpha-value>)',
        },
        text: {
          DEFAULT: 'rgb(var(--color-text) / <alpha-value>)',
          muted:   'rgb(var(--color-text-muted) / <alpha-value>)',
        },
      },
    },
  },
  plugins: [],
}
