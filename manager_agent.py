"""
LLM Agent for email recipient analysis and resolution using OpenAI's API.
"""

from typing import List, Optional
import openai
from loguru import logger
from pydantic import BaseModel, EmailStr, Field
from email_service.outlook_service import OutlookService
import json
import asyncio
from prompt import PROMPTS
from openai import OpenAI
import os
from email_service.outlook_agent import run_outlook_agent
from display_window.display_window import display_content



class ManagerAgent:
    def __init__(self):
        """Initialize the agent with OpenAI API key."""
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.outlook_service = OutlookService()



    async def run(self, user_input: str) -> str:
        """Run the agent with user input and return response."""
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "display_content",
                    "description": "Display content to the user",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "content": {"type": "string", "description": "Content to display"},
                        },
                        "required": ["content"]
                    }

                }
            },
            {
                "type": "function",
                "function": {
                    "name": "run_outlook_agent",
                    "description": "Invoke the outlook agent to create a draft email for user.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "user_input": {"type": "string", "description": "User input"},
                        },
                        "required": ["user_input"]
                    }
                }
            }
        ]



        messages = [
            {"role": "system", "content": PROMPTS['allocate_task']},
            {"role": "user", "content": user_input}
        ]


        try:
            client = OpenAI()
            response =  client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                tools=tools,
                tool_choice="required" # call one or more tools
            )

            message = response.choices[0].message

            if message.tool_calls:
                for tool_call in message.tool_calls:
                    try:
                        name = tool_call.function.name
                        args = tool_call.function.arguments
                        logger.info(f"Calling tool {name} with arguments: {args}")
                        tool_result = await self.call_function(name, args)
                        logger.info(f"Tool {name} returned: {tool_result}")

                    except Exception as e:
                        logger.error(f"Error in tool call {name}: {str(e)}")
                        raise

            return None

        except Exception as e:
            logger.error(f"Error in agent execution: {str(e)}")

            raise RuntimeError(f"Agent execution failed: {str(e)}")

    async def call_function(self, name, args):
        """Call a function by name with the given arguments.
        
        Args:
            name (str): Name of the function to call
            args (Union[str, dict]): Arguments for the function, either as JSON string or dict
        
        Returns:
            str: Result of the function call
        """
        # Parse JSON string if args is a string
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                return f"Error: Invalid JSON arguments - {args}"
        
        try:
            # Map function names to their implementations
            function_map = {
                "display_content": display_content,
                "run_outlook_agent": run_outlook_agent
            }
            


            if name not in function_map:
                return f"Error: Unknown function {name}"
                
            func = function_map[name]
            
            # Call async functions with await, regular functions directly
            if asyncio.iscoroutinefunction(func):
                result = await func(**args)
            else:
                result = func(**args)
                
            return result
            
        except TypeError as e:
            return f"Error: Invalid arguments for {name} - {str(e)}"
        except Exception as e:
            return f"Error: Function {name} failed - {str(e)}" 

