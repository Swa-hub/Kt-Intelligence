/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Luxury editorial palette — light-first.
        ink:       "#111110",   // obsidian — primary text, buttons
        graphite:  "#292927",   // secondary text, borders in dark mode
        paper:     "#FAF9F6",   // page background
        ivory:     "#F5F2EC",   // elevated surface (sidebar, cards)
        bone:      "#EDE9DF",   // deeper warm surface
        stone:     "#A7A39B",   // muted body text, meta
        mist:      "#D4CFC2",   // dividers, hairline borders
        forest:    "#34483D",   // deep forest accent (status / emphasis)
        forestSoft:"#E3E8E4",   // forest tint for backgrounds
        champagne: "#B39A70",   // champagne accent (hover / highlight)
        champagneSoft:"#F2EBDC",
        rust:      "#8A4B2A",   // warm severity (muted red replacement)
        rustSoft:  "#F3E6DD",
        ochre:     "#A77A2D",   // muted amber for medium severity
        ochreSoft: "#F2E8CF",
      },
      fontFamily: {
        serif: ['"Instrument Serif"', 'Cormorant', '"Times New Roman"', 'serif'],
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'monospace'],
      },
      letterSpacing: {
        tightest: '-0.03em',
        eyebrow: '0.14em',
      },
    },
  },
  plugins: [],
};
