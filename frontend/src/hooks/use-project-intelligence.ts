import { useMutation } from "@tanstack/react-query";

import { analyzeProjectIntelligence } from "../api/intelligence";
import type { GroundedAnalysisRequest } from "../types/api";

export function useAnalyzeProjectIntelligence(projectKey: string) {
  return useMutation({
    mutationFn: (request: GroundedAnalysisRequest) =>
      analyzeProjectIntelligence(projectKey, request),
    retry: false,
  });
}
