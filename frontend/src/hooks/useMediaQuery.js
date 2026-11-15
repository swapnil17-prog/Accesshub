import { useEffect, useState } from 'react';

/** Whether a CSS media query matches (updates live). Falls back to ``fallback`` without matchMedia. */
export function useMediaQuery(query, fallback = true) {
  const read = () => (typeof window !== 'undefined' && window.matchMedia ? window.matchMedia(query).matches : fallback);
  const [matches, setMatches] = useState(read);

  useEffect(() => {
    if (!window.matchMedia) return undefined;
    const mql = window.matchMedia(query);
    const onChange = () => setMatches(mql.matches);
    onChange();
    mql.addEventListener('change', onChange);
    return () => mql.removeEventListener('change', onChange);
  }, [query]);

  return matches;
}
