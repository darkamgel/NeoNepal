import { useState } from "react";
import { api } from "../api/client";

// Extracted from GlacierDetailPanel.jsx so the same "click to analyze, show
// loading, show result" behavior can be reused by the tracked-glaciers view
// without re-duplicating the state logic.
export function useAnalyzeGlacier(glacierId) {
  const [risk, setRisk] = useState(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [error, setError] = useState(null);

  async function analyze() {
    setIsAnalyzing(true);
    setError(null);
    try {
      const result = await api.analyzeGlacier(glacierId);
      setRisk(result);
      return result;
    } catch (e) {
      setError(e.message);
      return null;
    } finally {
      setIsAnalyzing(false);
    }
  }

  return { risk, isAnalyzing, error, analyze };
}
