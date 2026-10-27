"use client";

import { PropsWithChildren, useEffect, useState } from "react";

import { currentSession, getStudentAccess, StudentAccess } from "../../src/api-client";

export function StudentAccessGate({ children }: PropsWithChildren) {
  const [access, setAccess] = useState<StudentAccess | null>(null);
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    const session = currentSession();
    if (!session || session.role !== "student") {
      setChecked(true);
      return;
    }
    void getStudentAccess(session.accessToken)
      .then(setAccess)
      .catch(() => setAccess({ enabled: false, displayName: "星芽 AI 创作岛", maintenanceMessage: "暂时无法确认创作大厅状态，请稍后重试。", showcaseColumns: 4, showcaseRows: 2, showcaseSort: "featured", showcaseKind: "all", videoDurationSeconds: 5 }))
      .finally(() => setChecked(true));
  }, []);

  if (checked && access && !access.enabled) {
    return <main className="student-maintenance"><div className="student-maintenance__card"><span>🛠️</span><p>CREATIVE HALL</p><h1>{access.displayName}正在休息</h1><strong>{access.maintenanceMessage || "创作大厅正在维护，请稍后再来。"}</strong><a href="/login">返回登录页</a></div></main>;
  }

  return <>{children}</>;
}
