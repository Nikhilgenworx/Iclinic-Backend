from abc import ABC, abstractmethod


class BaseTool(ABC):
    name: str

    description: str

    args_schema = None

    @abstractmethod
    async def execute(
        self,
        **kwargs,
    ):
        pass
