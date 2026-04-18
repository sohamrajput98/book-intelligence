"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export function Navbar() {
  const pathname = usePathname();
  const items = [{ href: "/", label: "Dashboard" }, { href: "/qa", label: "Q&A" }];

  return (
    <header className="sticky top-0 z-50 border-b border-[#8ec8ff33] bg-[#071425cc] backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        <Link
          href="/"
          className="rounded-full border border-[#8ec8ff42] bg-[#8ec8ff0f] px-4 py-2 text-sm font-semibold tracking-[0.12em] text-[#dff2ff] transition hover:border-[#b8e7ff88] hover:bg-[#8ec8ff22]"
        >
          BOOK INTELLIGENCE
        </Link>

        <nav className="flex items-center gap-3">
          {items.map((item) => {
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={[
                  "rounded-full border px-4 py-2 text-sm font-medium transition",
                  isActive
                    ? "border-[#bfe7ff99] bg-[#8ec8ff33] text-[#e8f6ff] shadow-[0_0_18px_rgba(142,200,255,0.22)]"
                    : "border-[#8ec8ff3d] bg-[#8ec8ff12] text-[#aac6dd] hover:border-[#b8e7ff88] hover:bg-[#8ec8ff24] hover:text-[#dff2ff]"
                ].join(" ")}
              >
                {item.label}
              </Link>
            );
          })}

          <span className="inline-flex items-center gap-2 rounded-full border border-[#8ec8ff45] bg-[#8ec8ff12] px-3 py-1.5 text-xs text-[#b6d4ea]">
            <span className="h-2 w-2 animate-pulse rounded-full bg-[#7ad5ff]" />
            API online
          </span>
        </nav>
      </div>
    </header>
  );
}
