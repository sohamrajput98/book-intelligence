export interface AIInsight {
  id: number;
  summary: string;
  genre_classification: string;
  sentiment: string;
  sentiment_score: number;
  created_at: string;
}

export interface Book {
  id: number;
  title: string;
  author: string;
  rating: string | null;
  reviews_count: number;
  description?: string;
  book_url?: string;
  cover_image_url: string;
  genre: string;
  created_at: string;
  ai_insight?: AIInsight;
  chunks_count?: number;
}

export interface PaginatedBooks {
  count: number;
  next: string | null;
  previous: string | null;
  results: Book[];
}

export interface RecommendationBook {
  id: number;
  title: string;
  author: string;
  rating: string | null;
  cover_image_url: string;
  genre: string;
  ai_insight?: AIInsight;
}

export interface QAResponse {
  answer: string;
  sources: string[];
  chunk_references: Array<{ book_id: number; title: string; chunk_index: number; chroma_id: string; score: number }>;
  chat_id: number;
}

export interface ChatHistoryItem {
  id: number;
  question: string;
  answer: string;
  sources: unknown[];
  created_at: string;
}
