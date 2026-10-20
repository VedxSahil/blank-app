import type { Metadata } from "next";
import "./globals.css";
import { MotionRoot } from "@/components/motion-root";
import { Nav } from "@/components/nav";

export const metadata: Metadata = {
  title: "PEReport - Fund Document Assistant",
  description: "Cited answers and drafted reports from fund documents, with refusals when unsupported.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="flex min-h-full flex-col">
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-10 focus:rounded focus:bg-card focus:p-2"
        >
          Skip to content
        </a>
        <Nav />
        <MotionRoot>
          <main id="main" className="mx-auto w-full max-w-6xl flex-1 px-4 py-6">
            {children}
          </main>
        </MotionRoot>
      </body>
    </html>
  );
}
