import "./globals.css";
import { Libre_Baskerville, Oswald, Special_Elite } from "next/font/google";

const oswald = Oswald({ subsets: ["latin"], variable: "--font-headline" });
const libre = Libre_Baskerville({ subsets: ["latin"], weight: ["400", "700"], variable: "--font-body" });
const specialElite = Special_Elite({ subsets: ["latin"], weight: "400", variable: "--font-typewriter" });

export const metadata = {
  title: "NYC Crime Pulse",
  description: "A gritty NYC crime analytics bulletin",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body className={`${oswald.variable} ${libre.variable} ${specialElite.variable}`}>{children}</body>
    </html>
  );
}
