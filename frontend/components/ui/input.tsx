import * as React from "react";
import { cn } from "@/lib/utils";

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(({ className, ...props }, ref) => {
  return <input ref={ref} className={cn("flex h-10 w-full rounded-md border border-border bg-card px-3 py-2 text-sm outline-none ring-offset-background focus-visible:ring-2 focus-visible:ring-accent", className)} {...props} />;
});
Input.displayName = "Input";
