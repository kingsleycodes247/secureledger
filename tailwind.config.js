/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    // Scan every template in the project for Tailwind classes
    './templates/**/*.html',
    './templates/accounts/**/*.html',
    './templates/dashboard/**/*.html',
    './templates/investments/**/*.html',
    './templates/adminpanel/**/*.html',
    './templates/frontend/**/*.html',
    './templates/emails/**/*.html',
    './**/templates/**/*.html',
  ],
  theme: {
    extend: {
      colors: {
        primary: '#00C896',
        'primary-dark': '#00A57D',
        dark: '#080E14',
        'dark-2': '#0D1620',
        'dark-3': '#111D2B',
        'dark-card': '#0F1A25',
      },
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
        display: ['Space Grotesk', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
    },
  },
  plugins: [],
}
