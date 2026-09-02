/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        page: '#F4F5F7',
        ink: {
          DEFAULT: '#14161A',
          muted: '#5A6270',
          subtle: '#8C93A0',
        },
        surface: {
          DEFAULT: '#FFFFFF',
          raised: '#FAFAFB',
          inset: '#F0F1F4',
        },
        border: {
          DEFAULT: '#E2E4E9',
          strong: '#D1D5DC',
          subtle: '#ECEEF1',
        },
        accent: {
          DEFAULT: '#2F3BB3',
          hover: '#252F94',
          subtle: '#EEF0FA',
          border: '#C5CBEF',
        },
        recovered: {
          DEFAULT: '#1D7A5F',
          subtle: '#E8F5F1',
          border: '#B6E2D5',
        },
        suppressed: {
          DEFAULT: '#A66A0B',
          subtle: '#FEF6E7',
          border: '#F7DCB0',
        },
        dnc: {
          DEFAULT: '#5A6270',
          subtle: '#EEF0F3',
          border: '#D1D5DC',
        },
        danger: {
          DEFAULT: '#A82222',
          subtle: '#FDF0F0',
          border: '#F5C4C4',
        },
      },
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'Roboto Mono', 'Menlo', 'monospace'],
      },
      fontSize: {
        'xxs': ['11px', { lineHeight: '14px', letterSpacing: '0.01em' }],
        'xs': ['12px', { lineHeight: '16px' }],
        'sm': ['13px', { lineHeight: '18px' }],
        'base': ['14px', { lineHeight: '20px' }],
        'md': ['15px', { lineHeight: '22px' }],
        'lg': ['16px', { lineHeight: '24px' }],
        'xl': ['20px', { lineHeight: '28px' }],
        '2xl': ['24px', { lineHeight: '32px' }],
        '3xl': ['32px', { lineHeight: '38px' }],
      },
    },
  },
  plugins: [],
}
