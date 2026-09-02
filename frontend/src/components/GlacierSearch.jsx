import { useEffect, useRef, useState } from "react";
import { api } from "../api/client";

export default function GlacierSearch({ onSelect }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [isSearching, setIsSearching] = useState(false);
  const debounceRef = useRef(null);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (query.trim().length < 2) {
      setResults([]);
      return;
    }
    setIsSearching(true);
    debounceRef.current = setTimeout(async () => {
      try {
        const hits = await api.searchGlaciers(query.trim());
        setResults(hits);
      } catch {
        setResults([]);
      } finally {
        setIsSearching(false);
      }
    }, 300);
    return () => clearTimeout(debounceRef.current);
  }, [query]);

  function handleSelect(glacier) {
    onSelect(glacier);
    setQuery(glacier.name || "");
    setResults([]);
  }

  return (
    <div className="glacier-search">
      <input
        type="text"
        placeholder="Search any glacier in Nepal (e.g. Ngozumpa)..."
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />
      {isSearching && <p className="muted small">Searching...</p>}
      {results.length > 0 && (
        <ul className="glacier-search-results">
          {results.map((g) => (
            <li key={g.id} onClick={() => handleSelect(g)}>
              {g.name}
            </li>
          ))}
        </ul>
      )}
      {!isSearching && query.trim().length >= 2 && results.length === 0 && (
        <p className="muted small">No named glaciers match "{query}".</p>
      )}
    </div>
  );
}
