"""
LLM Agent for email recipient analysis and resolution using OpenAI's API.
"""

from typing import List, Optional, Union
import openai
from loguru import logger
from pydantic import BaseModel, EmailStr, Field
from email_service.outlook_service import OutlookService
import json
import asyncio
from prompt import PROMPTS
from openai import OpenAI
import os

async def run_outlook_agent(user_input: str) -> str:
    """Run the outlook agent to create a draft email for user."""
    outlook_service = OutlookService()
    tools = [
        {
            "type": "function",
            "function": {
                "name": "create_draft",
                "description": "Create and display a draft email in Outlook",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "to": {"type": "string", "description": "Recipient email addresses, separated by commas"},
                        "subject": {"type": "string", "description": "Email subject"},
                        "body": {"type": "string", "description": "Email body content"},
                        "priority": {"type": "string", "enum": ["normal", "high"], "description": "Email priority"},
                        "attachments": {"type": "array", "items": {"type": "string"}, "description": "List of attachment paths"}
                    },
                    "required": ["subject", "body"]
                }
            }
        }
    ]

    messages = [
        {"role": "system", "content": PROMPTS['email_draft']},
        {"role": "user", "content": "Below is the user input:\n\n " + user_input}
    ]

    try:
        client = OpenAI()
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            tools=tools,
            tool_choice="required"
        )

        message = response.choices[0].message
        messages.append(message)
        logger.info(f"Message: {message}")
        
        count = 0
        while count < 3 and message.tool_calls:
            for tool_call in message.tool_calls:
                try:

                    name = tool_call.function.name
                    args = tool_call.function.arguments

                    logger.info(f"Calling tool {name} with arguments: {args}")
                    tool_result = await call_function(name, args, outlook_service)
                    logger.info(f"Tool {name} returned: {tool_result}")
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": str(tool_result)
                    })

                except Exception as e:
                    logger.error(f"Error in tool call {name}: {str(e)}")
                    raise
                
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                tools=tools,
                tool_choice="auto"
            )

            message = response.choices[0].message
            logger.info(f"Message: {message}")
            messages.append(message)
            count += 1

        return None

    except Exception as e:

        logger.error(f"Error in agent execution: {str(e)}")
        raise RuntimeError(f"Agent execution failed: {str(e)}")

async def call_function(name: str, args: Union[str, dict], outlook_service: OutlookService):
    """Call a function by name with the given arguments."""
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except json.JSONDecodeError:
            return f"Error: Invalid JSON arguments - {args}"
    
    try:
        function_map = {
            "create_draft": outlook_service.create_draft
        }
        
        if name not in function_map:
            return f"Error: Unknown function {name}"
            
        func = function_map[name]
        
        if asyncio.iscoroutinefunction(func):
            result = await func(**args)
        else:
            result = func(**args)
            
        return result
        
    except TypeError as e:
        return f"Error: Invalid arguments for {name} - {str(e)}"
    except Exception as e:
        return f"Error: Function {name} failed - {str(e)}"

async def cleanup(outlook_service: OutlookService):
    """Cleanup Outlook service resources."""
    await outlook_service.cleanup() 