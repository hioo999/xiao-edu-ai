"use client";

import { useEffect, useState } from "react";

import { currentSession, destinationForRole, myCreditBalance } from "../../src/api-client";

export function StudentAccountEntrance() {
  const [href, setHref] = useState("/login");
  const [label, setLabel] = useState("登录");
  const [credits, setCredits] = useState<number | null>(null);

  useEffect(() => {
    const session = currentSession();
    if (!session) return;
    setHref(destinationForRole(session.role));
    setLabel(session.role === "student" ? "我的创作岛" : "进入工作台");
    if (session.role === "student") void myCreditBalance(session.accessToken).then((wallet) => setCredits(wallet.configured ? wallet.balance : null)).catch(() => setCredits(null));
  }, []);

  return <a className="kids-login" href={href}><span aria-hidden="true">{label === "登录" ? "🔐" : "😊"}</span>{label}{credits !== null && <small>{credits} 积分</small>}</a>;
}
