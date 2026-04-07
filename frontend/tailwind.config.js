/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        background: '#0C0C0E',
        surface1: '#16161A',
        surface2: '#1C1C22',
        brand: '#F97316',
        insider: '#EF4444',
        suspicious: '#F59E0B',
        clean: '#22C55E',
        yes: '#3B82F6',
        no: '#A855F7',
        muted: '#6B7280',
        border: '#2A2A32',
      },
      fontFamily: {
        headline: ['"Space Grotesk"', 'sans-serif'],
        body: ['Inter', 'sans-serif'],
        data: ['"IBM Plex Sans"', 'sans-serif'],
        mono: ['"IBM Plex Mono"', 'monospace'],
      },
      borderRadius: {
        DEFAULT: '4px',
        sm: '2px',
        md: '6px',
        lg: '8px',
        xl: '12px',
        full: '9999px',
      },
    },
  },
  plugins: [],
}
