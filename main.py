import asyncio


import importlib.util
import os

from dotenv import load_dotenv
load_dotenv()


def load_object_from_path(file_path_with_attr):
    # Split path and attribute
    file_path, attr = file_path_with_attr.split(":")
    file_path = os.path.abspath(file_path)

    # Derive a module name (arbitrary but must be unique if used multiple times)
    module_name = os.path.splitext(os.path.basename(file_path))[0]

    # Load the module
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # Get the attribute (object)
    return getattr(module, attr)


async def run_react_agent():
    graph = load_object_from_path('./src/react_agent/graph.py:graph')
    response = await graph.ainvoke(
        {"messages": [("user", "Who is the founder of LangChain?")]},
        {"configurable": {"system_prompt": "You are a helpful AI assistant."}},
    )

    return response["messages"][-1].content


if __name__ == "__main__":
    response = asyncio.run(run_react_agent())
    print(response)

