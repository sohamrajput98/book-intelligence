import axios, { AxiosError } from "axios";

import type { Book, ChatHistoryItem, PaginatedBooks, QAResponse, RecommendationBook } from "@/lib/types";

interface ApiEnvelope<T> {
  success: boolean;
  data: T;
  error: string | null;
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000/api";
const DEFAULT_TIMEOUT_MS = Number(process.env.NEXT_PUBLIC_API_TIMEOUT_MS ?? "120000");
const LONG_TIMEOUT_MS = Number(process.env.NEXT_PUBLIC_API_LONG_TIMEOUT_MS ?? "180000");

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: DEFAULT_TIMEOUT_MS
});

function parseError(error: unknown): Error {
  if (axios.isAxiosError(error)) {
    const axiosError = error as AxiosError<ApiEnvelope<unknown>>;
    const msg = axiosError.response?.data?.error;
    return new Error(msg || axiosError.message || "Request failed");
  }
  return new Error("Unknown request error");
}

async function unwrap<T>(promise: Promise<{ data: ApiEnvelope<T> }>): Promise<T> {
  try {
    const response = await promise;
    if (!response.data.success) {
      throw new Error(response.data.error || "Request unsuccessful");
    }
    return response.data.data;
  } catch (error) {
    throw parseError(error);
  }
}

export const api = {
  getBooks: (page: number): Promise<PaginatedBooks> => unwrap(apiClient.get(`/books/?page=${page}`)),
  getBook: (id: number): Promise<Book> => unwrap(apiClient.get(`/books/${id}/`)),
  getRecommendations: (id: number): Promise<RecommendationBook[]> => unwrap(apiClient.get(`/books/${id}/recommendations/`)),
  scrapeBooks: (pages: number): Promise<{ stats: { books_created: number } }> => unwrap(apiClient.post("/books/scrape/", { pages }, { timeout: LONG_TIMEOUT_MS })),
  generateInsights: (id: number): Promise<{ status: string }> => unwrap(apiClient.post(`/books/${id}/generate-insights/`, {}, { timeout: LONG_TIMEOUT_MS })),
  indexBook: (id: number): Promise<{ chunks_indexed: number }> => unwrap(apiClient.post(`/books/${id}/index/`, {}, { timeout: LONG_TIMEOUT_MS })),
  askQuestion: (question: string): Promise<QAResponse> => unwrap(apiClient.post("/qa/ask/", { question }, { timeout: LONG_TIMEOUT_MS })),
  getHistory: (): Promise<ChatHistoryItem[]> => unwrap(apiClient.get("/qa/history/")),
  clearHistory: (): Promise<{ deleted_count: number }> => unwrap(apiClient.delete("/qa/history/"))
};
