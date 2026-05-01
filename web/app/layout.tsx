import "./globals.css";

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
      <body>{children}</body>
    </html>
  );
}
