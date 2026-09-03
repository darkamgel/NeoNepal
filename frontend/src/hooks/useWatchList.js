import { useCallback, useState } from "react";

const STORAGE_KEY = "neonepal_tracked_glaciers";

function readStored() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return []; // private browsing / storage disabled / corrupted value
  }
}

function writeStored(list) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(list));
  } catch {
    // best-effort — a watch list that fails to persist still works for the
    // current page load, it just won't survive a refresh
  }
}

// Which glaciers a viewer has chosen to track is a per-browser preference,
// not server state — there's no user-account system in this app, and the
// real, shared data (risk history) already lives server-side keyed by
// glacier id regardless of who's watching it.
export function useWatchList() {
  const [tracked, setTracked] = useState(readStored);

  const isTracked = useCallback((id) => tracked.some((g) => g.id === id), [tracked]);

  const track = useCallback((glacier) => {
    setTracked((prev) => {
      if (prev.some((g) => g.id === glacier.id)) return prev;
      const next = [...prev, { id: glacier.id, name: glacier.name, lat: glacier.lat, lon: glacier.lon }];
      writeStored(next);
      return next;
    });
  }, []);

  const untrack = useCallback((id) => {
    setTracked((prev) => {
      const next = prev.filter((g) => g.id !== id);
      writeStored(next);
      return next;
    });
  }, []);

  return { tracked, isTracked, track, untrack };
}
