from typing import Optional, Callable
import numpy as np
from loguru import logger
import asyncio
from audio_service import AudioRecordingService
from local_speech_provider import WhisperSpeechProvider
from email_parser import EmailParser
from outlook_service import OutlookService

class VoiceEmailWorkflow:
    def __init__(self, whisper_model: str = "base", transcript_callback=None):
        self.audio_service = AudioRecordingService(
            sample_rate=16000,
            channels=1,
        )
        self.speech_provider = WhisperSpeechProvider(
            model_size=whisper_model,
            transcript_callback=transcript_callback
        )
        self.email_parser = EmailParser()
        self.outlook_service = OutlookService()
        self.is_processing = False
        self.current_audio = None
        self.is_shutting_down = False
        self.transcript_callback = transcript_callback
        logger.debug("VoiceEmailWorkflow initialized")
        
    async def initialize_services(self):
        """初始化所有服务"""
        try:
            # 初始化语音识别服务
            await self.speech_provider.initialize()
            # 初始化音频服务
            self.audio_service.initialize()
            logger.info("All services initialized successfully")
        except Exception as e:
            logger.error(f"Service initialization failed: {str(e)}")
            raise

    async def start_recording(self, volume_callback: Optional[Callable[[float], None]] = None):
        if self.audio_service.sample_rate != 16000:
            raise ValueError("Audio service sample rate must be 16000 for Whisper")
            
        if self.is_processing or self.is_shutting_down:
            logger.warning("Workflow already in progress")
            return
            
        self.is_processing = True
        self.audio_service.start_recording(volume_callback)
        logger.info("Recording started")

    async def stop_and_process(self):
        """Stop recording and process the audio"""
        if self.is_shutting_down:
            logger.debug("Workflow is already shutting down")
            return

        try:
            audio_data = self.audio_service.stop_recording()
            if audio_data is None or len(audio_data) == 0:
                logger.warning("No audio data to process")
                return

            # 1. Get transcript
            transcript = await self.speech_provider.transcribe_audio(
                audio_data=audio_data,
                source_sample_rate=self.audio_service.sample_rate
            )
            
            # 2. Parse email from transcript
            logger.debug(f"Raw transcript: {transcript}")
            email_data = await self.email_parser.parse_email(transcript)
            logger.info(f"Parsed email: {email_data}")
            
            # 3. Create draft and notify UI
            if all([email_data.get('subject'), email_data.get('body'), email_data.get('to')]):
                draft_id = await self.outlook_service.create_draft(email_data)
                logger.success(f"Draft created: {draft_id}")
                
                # Show draft to user through Outlook UI
                await self.outlook_service.display_draft(draft_id)
                
                # Show draft to user through callback
                if self.transcript_callback:
                    self.transcript_callback({
                        'type': 'draft',
                        'data': {
                            'id': draft_id,
                            'to': email_data['to'],
                            'subject': email_data['subject'],
                            'body': email_data['body']
                        }
                    })
            else:
                logger.error("Invalid email data parsed from transcript")
            
            return transcript
            
        except Exception as e:
            logger.error(f"工作流失败: {str(e)}")
            raise
        finally:
            if not self.is_shutting_down:
                self.is_shutting_down = True
                await self.cleanup()
                self.is_processing = False
                self.is_shutting_down = False

    async def _transcribe_audio(self, audio_data: np.ndarray) -> str:
        return await self.speech_provider.transcribe_audio(
            audio_data=audio_data,
            source_sample_rate=self.audio_service.sample_rate
        )

    async def cleanup(self):
        """Cleanup resources"""
        try:
            if self.speech_provider:
                await self.speech_provider.cleanup()
            if self.audio_service:
                self.audio_service.cleanup()
        except Exception as e:
            logger.error(f"Cleanup failed: {str(e)}")

    async def full_cleanup(self):
        await self.cleanup()
        await self.outlook_service.cleanup()
        logger.info("All resources cleaned up")

async def main():
    workflow = VoiceEmailWorkflow(whisper_model="base")
    try:
        await workflow.initialize_services()
        def volume_callback(level: float):
            print(f"当前音量: {level:.2f}")
        await workflow.start_recording(volume_callback)
        await asyncio.sleep(5)
        await workflow.stop_and_process()
    finally:
        await workflow.full_cleanup()

if __name__ == "__main__":
    asyncio.run(main()) 