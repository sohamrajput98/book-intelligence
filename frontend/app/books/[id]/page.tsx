"use client";

import Image from "next/image";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";

import { api } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function BookDetailPage() {
  const params = useParams<{ id: string }>();
  const bookId = Number(params.id);

  const bookQuery = useQuery({ queryKey: ["book", bookId], queryFn: () => api.getBook(bookId), enabled: Number.isFinite(bookId) });
  const recsQuery = useQuery({ queryKey: ["book-recs", bookId], queryFn: () => api.getRecommendations(bookId), enabled: Number.isFinite(bookId) });

  const insightsMutation = useMutation({
    mutationFn: () => api.generateInsights(bookId),
    onSuccess: () => {
      toast.success("Insights generated.");
      bookQuery.refetch();
      recsQuery.refetch();
    },
    onError: (err: Error) => toast.error(err.message)
  });

  const indexMutation = useMutation({
    mutationFn: () => api.indexBook(bookId),
    onSuccess: (data) => toast.success(`Indexed ${data.chunks_indexed} chunks.`),
    onError: (err: Error) => toast.error(err.message)
  });

  if (bookQuery.isLoading) {
    return <p className="text-muted">Loading book details...</p>;
  }

  if (bookQuery.isError || !bookQuery.data) {
    return <p className="text-danger">{(bookQuery.error as Error)?.message ?? "Book not found."}</p>;
  }

  const book = bookQuery.data;

  return (
    <div className="space-y-6">
      <Card>
        <CardContent className="grid gap-6 p-6 md:grid-cols-[220px_1fr]">
          <div className="relative h-80 w-full overflow-hidden rounded-xl border border-border">
            <Image src={book.cover_image_url || "/placeholder.jpg"} alt={book.title} fill className="object-cover" unoptimized />
          </div>
          <div className="space-y-4">
            <h1 className="text-3xl font-semibold">{book.title}</h1>
            <p className="text-muted">by {book.author || "Author unavailable"}</p>
            <div className="flex flex-wrap gap-2">
              <Badge>{book.genre || "Unclassified"}</Badge>
              <Badge variant="outline">Rating: {book.rating ?? "N/A"}</Badge>
              <Badge variant="outline">Reviews: {book.reviews_count}</Badge>
              <Badge variant="outline">Chunks: {book.chunks_count}</Badge>
            </div>
            <p className="leading-relaxed text-foreground/90">{book.description || "No description available."}</p>
            <div className="flex flex-wrap gap-3">
              <Button onClick={() => insightsMutation.mutate()} disabled={insightsMutation.isPending}>
                {insightsMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                Generate Insights
              </Button>
              <Button variant="outline" onClick={() => indexMutation.mutate()} disabled={indexMutation.isPending}>
                {indexMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                Index Book
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>AI Insights</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <p><span className="text-muted">Summary:</span> {book.ai_insight?.summary ?? "Not generated yet."}</p>
          <p><span className="text-muted">Genre:</span> {book.ai_insight?.genre_classification ?? "N/A"}</p>
          <p><span className="text-muted">Sentiment:</span> {book.ai_insight?.sentiment ?? "N/A"} ({book.ai_insight?.sentiment_score ?? "N/A"})</p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Recommended Books</CardTitle>
        </CardHeader>
        <CardContent>
          {recsQuery.isError ? (
            <p className="text-danger">{(recsQuery.error as Error).message}</p>
          ) : null}
          <div className="flex gap-3 overflow-x-auto pb-2">
            {(recsQuery.data ?? []).map((item) => (
              <Link key={item.id} href={`/books/${item.id}`} className="glass min-w-56 rounded-lg p-3">
                <p className="font-medium">{item.title}</p>
                <p className="text-sm text-muted">{item.author}</p>
              </Link>
            ))}
            {recsQuery.isLoading ? <p className="text-muted">Loading recommendations...</p> : null}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

