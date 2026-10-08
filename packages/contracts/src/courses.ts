export type LessonBlockKind = "text" | "image" | "video" | "code" | "attachment" | "interaction" | "step" | "challenge";

export interface LessonBlock {
  id: string;
  kind: LessonBlockKind;
  order: number;
  content: unknown;
}
