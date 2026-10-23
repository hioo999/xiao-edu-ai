export type AgentTurn = { role: "student" | "assistant"; text: string };

export function buildStudentAgentPrompt(instructions: string, history: AgentTurn[], task: string): string {
  const recent = history.slice(-8).map((turn) => `${turn.role === "student" ? "学生" : "智能体"}：${turn.text.slice(0, 1200)}`).join("\n");
  return ["【智能体设定】", instructions.trim(), "【之前的对话】", recent || "暂无", "【学生的新指令】", task.trim(), "请依据智能体设定回答学生的新指令，延续必要的对话上下文。"].join("\n\n");
}
