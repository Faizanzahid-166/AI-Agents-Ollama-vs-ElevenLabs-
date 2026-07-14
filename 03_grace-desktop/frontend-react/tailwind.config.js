/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: {
          base: '#080810',
          surface: '#0e0e1a',
          elevated: '#13131f',
          overlay: '#1a1a2e',
        },
        accent: {
          violet: '#7c3aed',
          purple: '#9333ea',
          indigo: '#4f46e5',
          cyan: '#06b6d4',
          glow: '#a78bfa',
        },
        text: {
          primary: '#f0eeff',
          secondary: '#8b8aaa',
          muted: '#4a4966',
        },
        border: {
          subtle: '#1e1e30',
          default: '#2a2a40',
          bright: '#3d3d58',
        },
      },
      fontFamily: {
        sans: ['"DM Sans"', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'monospace'],
        display: ['"Space Grotesk"', 'sans-serif'],
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'orb-float': 'orbFloat 4s ease-in-out infinite',
        'fade-up': 'fadeUp 0.3s ease-out',
        'typing': 'typing 1.2s steps(3) infinite',
      },
      keyframes: {
        orbFloat: {
          '0%, 100%': { transform: 'translateY(0px) scale(1)' },
          '50%': { transform: 'translateY(-8px) scale(1.02)' },
        },
        fadeUp: {
          '0%': { opacity: '0', transform: 'translateY(12px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        typing: {
          '0%': { content: '"."' },
          '33%': { content: '".."' },
          '66%': { content: '"..."' },
        },
      },
      boxShadow: {
        'glow-violet': '0 0 30px rgba(124, 58, 237, 0.3)',
        'glow-cyan': '0 0 20px rgba(6, 182, 212, 0.25)',
        'card': '0 1px 3px rgba(0,0,0,0.4), 0 0 0 1px rgba(255,255,255,0.04)',
      },
    },
  },
  plugins: [],
}
