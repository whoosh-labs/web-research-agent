import asyncio
from react_agent.graph import graph

from dotenv import load_dotenv
load_dotenv()


async def run_async_react_agent():
    response = await graph.ainvoke(
        {"messages": [("user", "Who is the founder of LangChain?")]},
        {"configurable": {"system_prompt": "You are a helpful AI assistant."}},
    )

    return response["messages"][-1].content


def run_react_agent():
    response = graph.invoke(
        {"messages": [("user", "Who is the founder of LangChain?")]}
    )
    return response["messages"][-1].content


if __name__ == "__main__":
    response = asyncio.run(run_async_react_agent())
    # response = run_react_agent()
    print(response)

