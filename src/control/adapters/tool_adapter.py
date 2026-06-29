from control.tools.base_tool import BaseTool
from langchain_core.tools import StructuredTool


class ToolAdapter:
    @staticmethod
    def adapt(
        tool: BaseTool,
    ) -> StructuredTool:
        async def _execute(
            **kwargs,
        ):
            return await tool.execute(**kwargs)

        return StructuredTool.from_function(
            coroutine=_execute,
            name=tool.name,
            description=tool.description,
            args_schema=tool.args_schema,
        )
