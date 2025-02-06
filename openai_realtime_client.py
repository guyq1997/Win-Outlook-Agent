import os
import json
from loguru import logger
import websockets
from typing import Optional, Dict, Callable, Any
import base64
import asyncio


class OpenAIRealtimeAudioTextClient:
    """
    A client for the OpenAI realtime API.
    """
    def __init__(self,  model: str = "gpt-4o-realtime-preview"):
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.model = model
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.session_id = None
        self.response_finished = False
        self.base_url = "wss://api.openai.com/v1/realtime"
        self.concatenated_text_buffer = ""
        self.receive_task: Optional[asyncio.Task] = None
        self.response_event = asyncio.Event()
        # Server -> Client message handlers

        self.message_handlers = {
            # Session related events
            "session.updated": self._create_generic_logger("session.updated"),
            "session.created": self._create_generic_logger("session.created"),
            "session.error": self._create_error_logger("Session"),

            # Input audio buffer events
            "input_audio_buffer.cleared": self._create_generic_logger("input_audio_buffer.cleared"),
            "input_audio_buffer.commited": self._create_generic_logger("input_audio_buffer.commited"),
            "input_audio_buffer.committed": self._create_generic_logger("input_audio_buffer.committed"),

            # Response events
            "response.created": self._create_generic_logger("response.created"),
            "response.done": self._create_generic_logger("response.done"),
            "response.output_item.added": self._create_generic_logger("response.output_item.added"),
            "response.output_item.done": self._create_generic_logger("response.output_item.done"),
            "response.text.delta": self._handle_text_delta,
            "response.text.done": self._handle_text_done,
            "response.content_part.added": self._create_generic_logger("response.content_part.added"),
            "response.content_part.done": self._create_generic_logger("response.content_part.done"),

            # Conversation events
            "conversation.item.created": self._create_generic_logger("conversation.item.created"),

            # Rate limits events
            "rate_limits.updated": self._create_generic_logger("rate_limits.updated"),

            # General server error
            "error": self._create_error_logger("General")
        }
    def _create_generic_logger(self, event_type: str,):
        """Create a generic logger handler for similar message types
        
        Args:
            event_type: The type of event (e.g., 'text', 'session', etc.)
            data_key: The key to extract data from the message (defaults to event_type)
        """
        async def handler(data: dict):
            content = data.get("text", "") or data.get("content", "") or data.get(event_type, "")
            
            is_final = data.get("final", False)
            logger.debug(f"Received {event_type}: {content} (final: {is_final})")
            if data.get("type") == "response.text.done":
                await self.response_done_handler()
            elif data.get("type") == "response.text.delta":
                self.concatenated_text_buffer += content
            elif data.get("type") == "response.text.done":
                logger.debug(f"Concatenated text buffer: {self.concatenated_text_buffer}")

        return handler


    def _create_error_logger(self, error_type: str):
        """Create an error logger handler
        
        Args:
            error_type: The type of error (e.g., 'session', 'text', etc.)
        """
        def handler(data: dict):
            error = data.get("error", {})
            logger.error(f"{error_type} error: {error.get('message')} (code: {error.get('code')})")
        return handler




    async def _on_message(self, message):
        """Handle incoming messages"""
        try:
            data = json.loads(message)
            event_type = data.get("type")
            
            if event_type in self.message_handlers:
                handler = self.message_handlers[event_type]
                await handler(data)
            else:
                logger.warning(f"Unhandled event type: {event_type}")
        except json.JSONDecodeError:
            logger.error("Failed to decode message")
        except Exception as e:
            logger.error(f"Error handling message: {str(e)}")

    def _on_error(self, ws, error):
        """Handle WebSocket errors"""
        logger.error(f"WebSocket error: {error}")

    def _on_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket connection closing"""
        logger.debug(f"WebSocket connection closed: {close_status_code} - {close_msg}")

    async def _on_open(self):
        """Handle connection opening"""
        await self.ws.send(json.dumps({
            "type": "session.update",
            "session": {
                "modalities": ["text"],
                "input_audio_format": "pcm16",
                "input_audio_transcription": None,
                "turn_detection": None,
            }
        }))

    async def connect(self):
        """Establish asynchronous WebSocket connection"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "OpenAI-Beta": "realtime=v1"
        }
        
        url = f"{self.base_url}?model={self.model}"
        
        try:
            self.ws = await websockets.connect(url, additional_headers=headers)
            # Handle initial session setup
            await self._on_open()
            # Start message receiving task
            self.receive_task = asyncio.create_task(self._receive_messages())
            logger.debug("WebSocket connection established")
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            raise

    async def _receive_messages(self):
        """Async message receiver"""
        try:
            async for message in self.ws:
                await self._on_message(message)
        except websockets.exceptions.ConnectionClosed:
            logger.debug("WebSocket connection closed")
        except Exception as e:
            logger.error(f"Error receiving messages: {e}")

    async def send_audio(self, audio_data: bytes):
        """Async audio sending"""
        try:
            if not self.ws:
                logger.warning("WebSocket not available, attempting to reconnect...")
                await self.connect()
                
            if self.ws:
                await self.ws.send(json.dumps({
                    "type": "input_audio_buffer.append",
                    "audio": base64.b64encode(audio_data).decode('utf-8')
                }))
                logger.debug(f"Sent audio chunk of size: {len(audio_data)}")
            else:
                raise RuntimeError("Failed to establish WebSocket connection")
        except Exception as e:
            logger.error(f"Error sending audio: {e}")
            raise

    async def commit_audio(self):
        try:
            if not self.ws:
                logger.warning("WebSocket not available, attempting to reconnect...")
                await self.connect()
                
            if self.ws:
                await self.ws.send(json.dumps({"type": "input_audio_buffer.commit"}))
                logger.debug("Sent audio commit")
            else:
                raise RuntimeError("Failed to establish WebSocket connection")
        except Exception as e:
            logger.error(f"Error committing audio: {e}")
            raise

    async def clear_audio_buffer(self):
        try:
            if not self.ws:
                logger.warning("WebSocket not available, attempting to reconnect...")
                await self.connect()
                
            if self.ws:
                await self.ws.send(json.dumps({"type": "input_audio_buffer.clear"}))
                logger.debug("Cleared audio buffer")
            else:
                raise RuntimeError("Failed to establish WebSocket connection")
        except Exception as e:
            logger.error(f"Error clearing audio buffer: {e}")
            raise

    async def start_response(self, instructions: str):
        try:
            if not self.ws:
                logger.warning("WebSocket not available, attempting to reconnect...")
                await self.connect()
                
            if self.ws:
                await self.ws.send(json.dumps({
                    "type": "response.create",
                    "response": {
                        "modalities": ["text"],
                        "instructions": instructions
                    }
                }))
                logger.debug(f"Started response with instructions: {instructions}")
            else:
                raise RuntimeError("Failed to establish WebSocket connection")
        except Exception as e:
            logger.error(f"Error starting response: {e}")
            raise

    async def disconnect(self):
        """Async disconnect"""
        if self.ws:
            await self.ws.close()
            if self.receive_task:
                self.receive_task.cancel()

                try:
                    await self.receive_task
                except asyncio.CancelledError:
                    pass
            logger.debug("Disconnected successfully")
        self.ws = None
        self.session_id = None

    async def response_done_handler(self):
        """Mark the response as done"""
        self.response_finished = True
        self.response_event.set()
        logger.debug("Response processing completed")

    async def wait_for_response(self):
        """Wait for the response completion event"""
        try:
            await asyncio.wait_for(self.response_event.wait(), timeout=10.0)
            self.response_event.clear()
            return True
        except asyncio.TimeoutError:
            logger.warning("Response wait timeout")
            return False
        finally:
            if self.response_finished:
                await self.disconnect()

    async def _handle_text_delta(self, data: dict):
        """Handle text delta events"""
        content = data.get("delta", "")
        #self.concatenated_text_buffer += content
        logger.debug(f"Received text delta: {content}")


    async def _handle_text_done(self, data: dict):
        """Handle text done events"""
        content = data.get("text", "")
        self.concatenated_text_buffer += content
        logger.debug(f"Received text done: {content}")
        await self.response_done_handler()