import type { ReactNode } from "react";
import "./globals.css";
import "./creative-island.css";
import { StudentAccessGate } from "./components/student-access-gate";
import { platformTitle } from "../src/platform-title";

export const metadata = {
  title: platformTitle,
  description: "面向小学 AI 课程的多模态创作学习平台",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="zh-CN">
      <body><StudentAccessGate>{children}</StudentAccessGate></body>
    </html>
  );
}
