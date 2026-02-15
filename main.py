import asyncio

from src.core.agent import AgentEngine
from src.utils import SHARED_CONSOLE


async def main():
    engine = AgentEngine(
        system_prompt="你是一个全能助手。如果遇到不懂的问题，请使用搜索工具。请展示你的思考过程。"
    )

    SHARED_CONSOLE.print(
        "[bold blue]Agent 启动完成！输入 'exit' 退出，输入 'save' 导出记录。[/bold blue]"
    )

    while True:
        try:
            user_input = SHARED_CONSOLE.input("[bold yellow]User > [/bold yellow]")

            if user_input.lower() in ["exit", "quit"]:
                break

            if user_input.lower() == "save":
                engine.export_history()
                continue

            if user_input.lower() == "reset":
                engine.reset()
                continue

            if not user_input.strip():
                continue

            await engine.chat(user_input)

            SHARED_CONSOLE.print()

        except KeyboardInterrupt:
            print("\nUser interrupted.")
            break
        except Exception as e:
            SHARED_CONSOLE.print_exception()


if __name__ == "__main__":
    asyncio.run(main())
