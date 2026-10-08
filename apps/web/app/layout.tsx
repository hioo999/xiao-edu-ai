import type { ReactNode } from "react";
import "./globals.css";
import "./creative-island.css";
import { StudentAccessGate } from "./components/student-access-gate";

export const metadata = {
  title: "AI 创造力学习工作台",
  description: "面向小学 AI 课程的多模态创作学习平台",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="zh-CN">
      <body><StudentAccessGate>{children}</StudentAccessGate></body>
    </html>
  );
}
