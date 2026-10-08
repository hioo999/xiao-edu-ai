# AgentScope 运行时配置

默认情况下，平台智能体会通过已配置的模型网关执行，不需要安装 AgentScope。需要将某类智能体接入 AgentScope 时，在 API 服务环境中安装可选依赖并设置工厂路径：

```bash
python -m pip install -e 'apps/api[agentscope]'
export AGENTSCOPE_AGENT_FACTORY='your_package.agents:create_agent'
```

`create_agent(agent_id)` 由部署方实现：接收平台智能体 ID，返回一个已经配置好模型、工具和权限的 AgentScope Agent。兼容两种结果：自定义桥接对象的 `run(prompt)` 返回结构化结果，或官方 Agent 的 `reply(prompt)` 返回带 `content` 的消息对象。

```python
{"html": "<main>...</main>", "teachingSteps": ["步骤一", "步骤二"]}
```

模型密钥、MCP 凭据与 AgentScope 工具配置只能保存在部署环境或密钥服务中，不得提交到仓库、课程内容或浏览器端。未设置该环境变量时，平台自动退回到模型网关运行时，保证课程不中断。
# AgentScope Runtime

Set `AGENTSCOPE_AGENT_FACTORY` to `package.module:factory`. The factory receives the managed agent ID. Existing factories may keep a single argument.

To enable approved MCP calls, define the factory with a second positional `tool_executor` argument or a `tool_executor` keyword argument:

```python
def factory(agent_id, tool_executor):
    return create_agent(agent_id, tool_executor=tool_executor)
```

`tool_executor.execute(server_id, capability, arguments)` performs the platform permission check using the current organization’s MCP configuration before calling the deployment-configured MCP server. A server must be enabled in the platform, connected by `MCP_SERVER_CONNECTIONS`, and expose the requested approved capability.
