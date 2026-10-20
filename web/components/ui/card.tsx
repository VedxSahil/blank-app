import * as React from "react";
import { cn } from "@/lib/utils";

export function Card({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn("relative rounded-xl border border-border bg-card p-5 shadow-sm", className)} {...props} />
  );
}
