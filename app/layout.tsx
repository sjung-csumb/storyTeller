import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Children's Story Generator",
  description: "AI 맞춤형 행동 교정 동화 생성 서비스"
};

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
