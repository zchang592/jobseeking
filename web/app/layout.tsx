import "./globals.css";
import type { Metadata } from "next";
export const metadata: Metadata = {
  title: { default: "音乐教职雷达", template: "%s · 音乐教职雷达" },
  description: "个人音乐教育招聘情报工作台",
  robots: { index: false, follow: false },
};
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
