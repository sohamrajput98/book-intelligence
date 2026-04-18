"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Loader2, Search } from "lucide-react";
import { toast } from "sonner";

import { api } from "@/lib/api";
import type { Book } from "@/lib/types";
import { BookCard } from "@/components/book-card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const PAGE_SIZE = 20;

export default function DashboardPage() {
  const [page, setPage] = useState<number>(1);
  const [search, setSearch] = useState<string>("");

  const booksQuery = useQuery({
    queryKey: ["books", page],
    queryFn: () => api.getBooks(page)
  });

  const scrapeMutation = useMutation({
    mutationFn: () => api.scrapeBooks(5),
    onSuccess: (data) => {
      const created = data.stats.books_created;
      const skipped = data.stats.books_skipped_cached;
      const failed = data.stats.books_failed;

      if (created > 0) {
        toast.success(`Scraping completed: added ${created} new books.`);
      } else if (skipped > 0 && failed === 0) {
        toast.info(`Scraping completed: no new books. ${skipped} already existed (cached).`);
      } else {
        toast.warning(`Scraping completed with partial issues. Failed: ${failed}.`);
      }

      booksQuery.refetch();
    },
    onError: (err: Error) => toast.error(err.message)
  });

  const filteredBooks = useMemo(() => {
    const items = booksQuery.data?.results ?? [];
    if (!search.trim()) {
      return items;
    }
    const needle = search.trim().toLowerCase();
    return items.filter((book: Book) => book.title.toLowerCase().includes(needle) || book.author.toLowerCase().includes(needle));
  }, [booksQuery.data?.results, search]);

  const totalPages = Math.max(1, Math.ceil((booksQuery.data?.count ?? 0) / PAGE_SIZE));

  return (
    <div className="space-y-8">
      <section className="glass relative overflow-hidden rounded-2xl p-6 sm:p-10">
        <div className="absolute -right-20 -top-20 h-56 w-56 rounded-full bg-primary/20 blur-3xl" />
        <div className="absolute -left-20 -bottom-16 h-52 w-52 rounded-full bg-accent/20 blur-3xl" />
        <p className="text-sm uppercase tracking-[0.18em] text-accent">Document Intelligence Platform</p>
        <h1 className="mt-2 text-3xl font-semibold sm:text-5xl">Books, AI Insights, and Retrieval Q&A in one workspace</h1>
        <p className="mt-3 max-w-2xl text-muted">Scrape datasets, auto-generate insights, index chunks, and query with grounded sources.</p>
        <div className="mt-6 flex flex-wrap gap-3">
          <Button onClick={() => scrapeMutation.mutate()} disabled={scrapeMutation.isPending}>
            {scrapeMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
            Scrape Books
          </Button>
          <Link href="/qa" className="inline-flex h-10 items-center justify-center rounded-md border border-border px-4 py-2 text-sm font-medium text-foreground transition hover:bg-card">Open Q&A</Link>
        </div>
      </section>

      <section className="space-y-4">
        <div className="relative max-w-xl">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
          <Input className="pl-10" placeholder="Search by title or author" value={search} onChange={(event) => setSearch(event.target.value)} />
        </div>

        {booksQuery.isLoading ? <p className="text-muted">Loading books...</p> : null}
        {booksQuery.isError ? <p className="text-danger">{(booksQuery.error as Error).message}</p> : null}

        {!booksQuery.isLoading && !booksQuery.isError ? (
          <>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {filteredBooks.map((book: Book) => (
                <BookCard key={book.id} book={book} />
              ))}
            </div>
            <div className="flex items-center justify-between rounded-xl border border-border bg-card/60 p-3">
              <p className="text-sm text-muted">Page {page} of {totalPages}</p>
              <div className="flex gap-2">
                <Button variant="outline" disabled={page <= 1} onClick={() => setPage((prev) => prev - 1)}>Previous</Button>
                <Button variant="outline" disabled={page >= totalPages} onClick={() => setPage((prev) => prev + 1)}>Next</Button>
              </div>
            </div>
          </>
        ) : null}
      </section>
    </div>
  );
}


