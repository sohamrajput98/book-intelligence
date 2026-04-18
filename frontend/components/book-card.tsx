import Image from "next/image";
import Link from "next/link";

import type { Book } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";

export function BookCard({ book }: { book: Book }) {
  return (
    <Link href={`/books/${book.id}`}>
      <Card className="h-full transition hover:-translate-y-0.5 hover:border-accent">
        <CardContent className="space-y-3 p-4">
          <div className="relative h-56 overflow-hidden rounded-lg border border-border">
            <Image src={book.cover_image_url || "/placeholder.jpg"} alt={book.title} fill className="object-cover" unoptimized />
          </div>
          <div>
            <p className="line-clamp-2 text-sm font-medium">{book.title}</p>
            <p className="text-xs text-muted">{book.author || "Author unavailable"}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Badge variant="outline">{book.genre || "N/A"}</Badge>
            <Badge variant="outline">{book.ai_insight?.sentiment ?? "N/A"}</Badge>
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}

