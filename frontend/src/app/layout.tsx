import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: "Medicine Dealer ERP",
  description: "Multi-branch medicine distribution ERP",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <script
          dangerouslySetInnerHTML={{
            __html: `if ("serviceWorker" in navigator) { navigator.serviceWorker.register("/sw.js").catch(function () {}); }`,
          }}
        />
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
