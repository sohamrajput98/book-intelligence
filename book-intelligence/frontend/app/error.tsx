"use client";

import { Button } from "@/components/ui/button";

export default function Error({ error, reset }: { error: Error; reset: () => void }) {
  return (
    <div className="glass rounded-2xl p-6">
      <h2 className="text-xl font-semibold">Something went wrong</h2>
      <p className="mt-2 text-muted">{error.message}</p>
      <Button className="mt-4" onClick={reset}>Try again</Button>
    </div>
  );
}
