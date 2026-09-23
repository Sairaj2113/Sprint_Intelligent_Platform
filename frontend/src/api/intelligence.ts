import { apiClient } from "./client";
import type {
  GroundedAnalysisRequest,
  GroundedAnalysisResponse,
} from "../types/api";

export async function analyzeProjectIntelligence(
  projectKey: string,
  request: GroundedAnalysisRequest,
): Promise<GroundedAnalysisResponse> {
  const response = await apiClient.post<GroundedAnalysisResponse>(
    `/projects/${projectKey}/intelligence/analyze`,
    request,
  );
  return response.data;
}
