from typing import Optional, Callable
import numpy as np
from loguru import logger
import asyncio
from audio_service import AudioRecordingService
from email_service.email_parser import EmailParser
from email_service.outlook_service import OutlookService
from openai_realtime_client import OpenAIRealtimeAudioTextClient
from prompt import PROMPTS
from llm_agent import EmailDraftAgent

class VoiceEmailWorkflow:
    def __init__(self):
        self.transcript = ""	
        self.audio_service = AudioRecordingService()
        self.outlook_service = OutlookService()
        self.is_processing = False
        self.is_shutting_down = False
        self.openai_client = OpenAIRealtimeAudioTextClient()
        self._current_audio_data = None  # 存储当前音频数据
        logger.debug("VoiceEmailWorkflow initialized")

    async def initialize_services(self):
        """初始化所有服务"""
        try:
            # 初始化音频服务
            if not self.audio_service.initialize():
                logger.error("Audio service initialization returned False")
                raise RuntimeError("Audio service initialization failed")

            logger.info("All services initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Service initialization failed: {str(e)}")
            raise

    async def start_recording(self, volume_callback: Optional[Callable[[float], None]] = None):
        if self.is_processing or self.is_shutting_down:
            logger.warning("Workflow already in progress")
            return
            
        self.is_processing = True
        try:

            await self.openai_client.connect()

            self.audio_service.start_recording(volume_callback)

            logger.debug("Audio recording started")
            
            # 保存任务引用以便后续取消
            self._stream_task = asyncio.create_task(self._stream_audio_to_openai())
            logger.info("Recording started")
        except Exception as e:
            self.is_processing = False
            logger.error(f"启动录音失败: {str(e)}")
            raise

    async def _stream_audio_to_openai(self):
        """发送处理后的音频"""
        try:
            while self.audio_service.is_recording:
                # 使用异步方法获取音频块
                chunk = await self.audio_service.get_audio_chunk()
                if chunk:
                    await self.openai_client.send_audio(chunk)
                else:
                    # 如果没有数据，短暂等待避免CPU过载
                    await asyncio.sleep(0.01)
        except asyncio.CancelledError:
            logger.info("Audio streaming cancelled")
        except Exception as e:
            logger.error(f"音频流传输失败: {str(e)}")
            raise

    async def stop_and_process(self):
        """停止时保存完整音频"""
        if not self.is_processing:
            logger.warning("stop_and_process called but not processing")
            return
        
        try:
            logger.info("Stopping recording and starting processing...")
            # 先停止音频流传输任务
            if hasattr(self, '_stream_task'):
                logger.debug("Cancelling audio stream task...")
                self._stream_task.cancel()
                try:
                    await asyncio.wait_for(self._stream_task, timeout=2.0)
                    logger.debug("Audio stream task cancelled successfully")
                except (asyncio.CancelledError, asyncio.TimeoutError):
                    logger.warning("Audio streaming task cancelled or timed out", exc_info=True)
            
            # 使用 await 调用 run_in_executor
            logger.debug("Stopping audio recording...")
            loop = asyncio.get_running_loop()
            full_audio = await loop.run_in_executor(
                None, 
                self.audio_service.stop_recording
            )
            logger.debug(f"Got full audio of length: {len(full_audio)}")
            
            if len(full_audio) == 0:
                logger.error("No audio data recorded")
                raise ValueError("No audio data recorded")
            
            # 保存音频数据以供重试使用
            self._current_audio_data = full_audio.tobytes()
            
            # 新增：清空剩余音频缓存
            logger.debug("Draining remaining audio chunks...")
            chunks_drained = 0
            while True:
                chunk = await self.audio_service.get_audio_chunk()
                if not chunk:
                    break
                chunks_drained += 1
                self._current_audio_data += chunk  # 追加到存储的音频数据
            logger.debug(f"Drained {chunks_drained} remaining chunks")
            
            # 检查 WebSocket 连接状态
            if not self.openai_client.ws:
                logger.error("WebSocket not connected")
                raise RuntimeError("WebSocket connection lost")

            # 添加重试逻辑
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    logger.debug(f"Processing attempt {attempt + 1}/{max_retries}")
                    
                    # 确保每次重试都有新的连接
                    if not self.openai_client.ws:
                        logger.debug("Reconnecting to OpenAI...")
                        await self.openai_client.connect()
                        logger.debug("Reconnected successfully")
                    
                    # 重新发送完整的音频数据
                    if self._current_audio_data:
                        logger.debug(f"Sending audio data of length: {len(self._current_audio_data)}")
                        # 分块发送音频数据，每块32KB
                        chunk_size = 32 * 1024
                        for i in range(0, len(self._current_audio_data), chunk_size):
                            chunk = self._current_audio_data[i:i + chunk_size]
                            await self.openai_client.send_audio(chunk)
                            await asyncio.sleep(0.01)  # 小延迟，避免发送太快
                    
                    logger.debug("WebSocket connected, committing audio...")
                    await self.openai_client.commit_audio()
                    logger.debug("Audio committed successfully")
                    
                    logger.debug("Starting response processing...")
                    await self.openai_client.start_response(PROMPTS['paraphrase-gpt-realtime'])
                    logger.debug("Response processing started successfully")
                    
                    logger.debug("Waiting for response...")
                    await asyncio.wait_for(
                        self.openai_client.wait_for_response(),
                        timeout=10.0  # 10秒超时
                    )
                    logger.debug("Response received successfully")
                    
                    # 检查响应
                    if not self.openai_client.concatenated_text_buffer:
                        if attempt < max_retries - 1:
                            logger.warning(f"No text received, retrying... (attempt {attempt + 1})")
                            await asyncio.sleep(1)  # 等待1秒后重试
                            continue
                        else:
                            raise RuntimeError("No transcription received after all retries")
                    
                    self.transcript = self.openai_client.concatenated_text_buffer
                    logger.success(f"Processing completed, transcript length: {len(self.transcript)}")
                    break  # 成功获取到文本，跳出重试循环
                    
                except asyncio.TimeoutError:
                    if attempt < max_retries - 1:
                        logger.warning(f"Timeout occurred, retrying... (attempt {attempt + 1})")
                        continue
                    else:
                        raise RuntimeError("Response timeout after all retries")
                except Exception as e:
                    logger.error(f"Error during processing: {type(e)}: {str(e)}", exc_info=True)
                    raise
                
        except Exception as e:
            logger.error(f"Workflow failed with error type {type(e)}: {str(e)}", exc_info=True)
            raise
        finally:
            email_draft = EmailDraftAgent()
            await email_draft.run(user_input=self.transcript)
            self.is_processing = False
            logger.debug("Disconnecting from OpenAI...")
            try:


                if hasattr(self, 'openai_client') and self.openai_client.ws:
                    disconnect_task = asyncio.create_task(self.openai_client.disconnect())
                    await asyncio.wait_for(disconnect_task, timeout=5.0)
                    logger.debug("Disconnected from OpenAI")
            except Exception as e:
                logger.error(f"Error during disconnect: {str(e)}", exc_info=True)

    async def cleanup(self):
        """清理资源"""
        try:
            await self.openai_client.disconnect()
            await self.outlook_service.cleanup()
            if self.audio_service:
                self.audio_service.cleanup()
            # Reset internal state
            self.transcript = ""
            self.is_processing = False
            self._current_audio_data = None
            if hasattr(self, '_stream_task'):
                delattr(self, '_stream_task')
        except Exception as e:
            logger.error(f"Cleanup failed: {str(e)}")
