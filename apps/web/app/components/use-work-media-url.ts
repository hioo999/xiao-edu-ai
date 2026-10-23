"use client";

import { useEffect, useState } from "react";

import { currentSession, fetchWorkMedia, protectedMediaPath } from "../../src/api-client";

export function useWorkMediaUrl(url: string): string {
  const protectedMedia = protectedMediaPath(url) !== null;
  const [source, setSource] = useState(protectedMedia ? "" : url);

  useEffect(() => {
    if (!protectedMedia) { setSource(url); return; }
    const session = currentSession();
    if (!session) { setSource(""); return; }
    let active = true;
    let objectUrl = "";
    setSource("");
    void fetchWorkMedia(url, session.accessToken)
      .then((response) => {
        if (!response.ok) throw new Error("媒体预览暂时不可用");
        return response.blob();
      })
      .then((blob) => {
        if (!active) return;
        objectUrl = URL.createObjectURL(blob);
        setSource(objectUrl);
      })
      .catch(() => { if (active) setSource(""); });
    return () => { active = false; if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [protectedMedia, url]);

  return source;
}
