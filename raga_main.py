from common.server import TaskManager
from common.server import A2AServer

from typing import AsyncIterable
from common.types import (
    SendTaskRequest,
    TaskSendParams,
    Message,
    TaskStatus,
    Artifact,
    TextPart,
    Task,
    TaskState,
    SendTaskResponse,
    InvalidParamsError,
)
from common.server.task_manager import InMemoryTaskManager
from common.utils.push_notification_auth import PushNotificationSenderAuth
import common.server.utils as utils
from typing import Union
import os
import click
import asyncio
import logging
import traceback

from common.server import A2AServer
from common.types import AgentCard, AgentCapabilities, AgentSkill, MissingAPIKeyError
from common.utils.push_notification_auth import PushNotificationSenderAuth

from starlette.responses import JSONResponse
from starlette.requests import Request


logger = logging.getLogger(__name__)


class AgentTaskManager(InMemoryTaskManager):

    def __init__(self, agent):
        super().__init__()
        self.agent = agent
        
    async def on_cancel_task(self, request):
        return await super().on_cancel_task(request)
    
    async def on_get_task(self, request):
        return await super().on_get_task(request)
    
    async def on_get_task_push_notification(self, request):
        return await super().on_get_task_push_notification(request)
    
    async def on_resubscribe_to_task(self, request):
        return await super().on_resubscribe_to_task(request)
    
    async def on_send_task_subscribe(self, request):
        return await super().on_send_task_subscribe(request)
    
    async def on_set_task_push_notification(self, request):
        return await super().on_set_task_push_notification(request)
    
    async def on_send_task(self, request: SendTaskRequest) -> SendTaskResponse:
        """Handles the 'send task' request."""

        await self.upsert_task(request.params)
        await self.update_store(
            request.params.id, TaskStatus(state=TaskState.WORKING), None
        )
        
        task_send_params: TaskSendParams = request.params
        query = self._get_user_query(task_send_params)
        try:
            agent_response = await self.call_langgraph_agent(self.agent, query)
        except Exception as e:
            traceback.print_exc()
            logger.error(f"Error invoking agent: {e}")
            raise ValueError(f"Error invoking agent: {e}")
        return await self._process_agent_response(
            request, agent_response
        )
    
    async def call_langgraph_agent(self, graph, user_query):
        response = await graph.ainvoke(
            {"messages": [("user", user_query)]},
            {"configurable": {"system_prompt": "You are a helpful AI assistant."}},
        )
        llm_response = response["messages"][-1].content
        return {
            "content": llm_response
        }
    
    async def _process_agent_response(
        self, request: SendTaskRequest, agent_response: dict
    ) -> SendTaskResponse:
        """Processes the agent's response and updates the task store."""
        task_send_params: TaskSendParams = request.params
        task_id = task_send_params.id
        history_length = task_send_params.historyLength
        task_status = None

        parts = [{"type": "text", "text": agent_response["content"]}]
        task_status = TaskStatus(state=TaskState.COMPLETED)
        artifact = Artifact(parts=parts)
        task = await self.update_store(
            task_id, task_status, None if artifact is None else [artifact]
        )
        task_result = self.append_task_history(task, history_length)
        # await self.send_task_notification(task)
        return SendTaskResponse(id=request.id, result=task_result)
    

    def _get_user_query(self, task_send_params: TaskSendParams) -> str:
        part = task_send_params.message.parts[0]
        if not isinstance(part, TextPart):
            raise ValueError("Only text parts are supported")
        return part.text
    


def load_object_from_path(file_path_with_attr):
    import importlib.util
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


# from agent import CurrencyAgent

graph = load_object_from_path('./react_agent/graph.py:graph')
notification_sender_auth = PushNotificationSenderAuth()
task_manager = AgentTaskManager(graph)

"""
A2A dependency
pip install git+https://github.com/google/A2A.git#subdirectory=samples/python
"""

@click.command()
@click.option("--host", "host", default="localhost")
@click.option("--port", "port", default=10000)
def main(host, port):
    """Starts the Currency Agent server."""
    try:
        import json
        with open("a2a.json") as fd:
            a2a = json.load(fd)

        cap_streaming = a2a["capabilities"]["streaming"]
        cap_push_notifications =  a2a["capabilities"]["push_notifications"]
        capabilities = AgentCapabilities(
            streaming=cap_streaming, 
            pushNotifications=cap_push_notifications,
        )
        agent_skills = []
        for skill in a2a["skills"]:
            agent_skill = AgentSkill(
                id=skill["id"],
                name=skill["name"],
                description=skill["description"],
                tags=skill["tags"],
                examples=skill["examples"],
            )
            agent_skills.append(agent_skill)
        
        agent_card = AgentCard(
            name=a2a["name"],
            description=a2a["description"],
            url=f"http://{host}:{port}/",
            version="1.0.0",
            defaultInputModes=a2a["input_modes"],
            defaultOutputModes=a2a["output_modes"],
            capabilities=capabilities,
            skills=agent_skills,
        )

        notification_sender_auth = PushNotificationSenderAuth()
        notification_sender_auth.generate_jwk()
        server = A2AServer(
            agent_card=agent_card,
            task_manager=task_manager,
            host=host,
            port=port,
        )

        server.app.add_route(
            "/.well-known/jwks.json", 
            notification_sender_auth.handle_jwks_endpoint, 
            methods=["GET"]
        )

        async def health_check():
            return JSONResponse({"status": "ok"})

        server.app.add_route(
            "/api/healthcheck", 
            health_check, 
            methods=["GET"]
        )

        logger.info(f"Starting server on {host}:{port}")
        server.start()
    except Exception as e:
        logger.error(f"An error occurred during server startup: {e}")
        traceback.print_exc()
        exit(1)


if __name__ == "__main__":
    main()