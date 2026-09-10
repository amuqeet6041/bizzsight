import "./globals.css";

export const metadata = {
  title: "SME Insights Generator",
  description: "Upload order data, get instant business metrics",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full flex flex-col bg-gray-50">{children}</body>
    </html>
  );
}
