"""
LLM Agent for email recipient analysis and resolution using OpenAI's API.
"""

from typing import List, Optional
from loguru import logger
import json
import asyncio
from openai import OpenAI
import os
from .lx_music_controller import LXMusicController
from search_tool.search_with_retry import search

class MusicAgent:
    def __init__(self):
        """Initialize the agent with OpenAI API key."""
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.music_controller = LXMusicController()

    async def run(self, user_input: str) -> str:
        """Run the agent with user input and return response."""
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "play",
                    "description": "Play music",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "pause",
                    "description": "Pause music",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "next_track",
                    "description": "Play next track",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "previous_track",
                    "description": "Play previous track",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "search_and_play",
                    "description": "Search and play music",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "song_name": {
                                "type": "string",
                                "description": "Name of the song for example: '消愁'"
                            },
                            "singer_name": {
                                "type": "string",
                                "description": "Name of the singer for example: '毛不易'"
                            }
                        },
                        "required": ["song_name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "search_song_info",
                    "description": "Search the internet for information about the song",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "content for searching the song name and singer name"},
                            "max_results": {"type": "integer", "description": "Maximum number of results to return (use 3 as default)"},
                            "max_retries": {"type": "integer", "description": "Maximum number of retry attempts (use 3 as default)"}
                        }
                    },
                    "required": ["query"]
                }
            }   
            
        ]




        messages = [
            {"role": "system", "content": """You are a music agent, you can manipulate the music player. You are also able to search the internet for information about the song.
             While using search_song_info tool, pass the query information as detailed as possible. 
             Always consider the user's input and the context of the conversation, then decide what to do next. 
             You should use search_song_info tool to make sure the song name you are going to play is correct, before you play the song. 
             Notice that you can not ask user questions, you have to decide by yourself. 
             Only use chinese and english while using the search_and_play tool. 
             Only use the singer name parameter in search_and_play tool, if you are very sure about that.
             """,
            },
            {"role": "user", "content": user_input}
        ]


        try:
            client = OpenAI()
            response =  client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                tools=tools,
                tool_choice="required" # call one or more tools
            )


            message = response.choices[0].message
            messages.append(message)

            count = 0
            while count < 3 and message.tool_calls:
                for tool_call in message.tool_calls:
                    try:

                        name = tool_call.function.name
                        args = tool_call.function.arguments

                        logger.info(f"Calling tool {name} with arguments: {args}")
                        tool_result = await self.call_function(name, args)
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
                    model="gpt-4o-mini",
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
                "play": self.music_controller.play,
                "pause": self.music_controller.pause,
                "next_track": self.music_controller.next_track,
                "previous_track": self.music_controller.previous_track,
                "search_and_play": self.music_controller.search_and_play,
                "search_song_info": search
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

