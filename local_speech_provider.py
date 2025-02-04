import whisper
import numpy as np
from typing import AsyncGenerator, Optional
import asyncio
from loguru import logger
import librosa
from concurrent.futures import ThreadPoolExecutor

class WhisperSpeechProvider:
    def __init__(self, model_size: str = "large", language: str = None, 
                 transcript_callback=None):
        """
        :param model_size: Model size (tiny, base, small, medium, large)
        :param language: Language code for transcription (auto-detection if None)
        :param transcript_callback: Callback for UI updates
        """


        self.model_size = model_size
        self.language = language
        self.model: Optional[whisper.Whisper] = None
        self.executor = ThreadPoolExecutor(max_workers=2)
        self.sample_rate = 16000  # Whisper标准输入采样率
        self._recording = False
        self.transcript_callback = transcript_callback
        
    async def initialize(self):
        """异步加载模型"""
        logger.info(f"Loading Whisper {self.model_size} model...")
        loop = asyncio.get_running_loop()
        self.model = await loop.run_in_executor(
            self.executor,
            lambda: whisper.load_model(self.model_size)
        )
        logger.success(f"Loaded Whisper {self.model_size} model")

    async def transcribe_audio(self, audio_data: np.ndarray, source_sample_rate: int) -> str:
        """
        转录音频数据
        :param audio_data: 原始音频numpy数组
        :param source_sample_rate: 原始采样率
        :return: 识别文本
        """
        try:
            # 预处理音频
            processed_audio = self._preprocess_audio(audio_data, source_sample_rate)
            
            # 在线程池中运行识别
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                self.executor,
                lambda: self.model.transcribe(
                    processed_audio,
                    language=self.language,  # None enables auto-detection
                    fp16=False,
                    task="transcribe"  # Explicitly set transcription task
                )
            )
            text = result["text"].strip()
            
            # 调用回调函数更新UI
            if self.transcript_callback:
                self.transcript_callback(text)
                
            return text
        except Exception as e:
            logger.error(f"Transcription failed: {str(e)}")
            raise

    def _preprocess_audio(self, audio_data: np.ndarray, source_sr: int) -> np.ndarray:
        """音频预处理"""
        # 检查音频数据
        if audio_data.size == 0:
            raise ValueError("Empty audio data")
        
        # 打印音频信息用于调试
        logger.debug(f"Audio shape: {audio_data.shape}, dtype: {audio_data.dtype}")
        
        # 转换为单声道
        if len(audio_data.shape) > 1:
            audio_data = np.mean(audio_data, axis=1)  # 改为axis=1
        
        # 检查音频是否有声音（避免静音）
        if np.max(np.abs(audio_data)) < 0.01:
            raise ValueError("Audio is too quiet")
        
        # 重采样到16000Hz
        if source_sr != self.sample_rate:
            audio_data = librosa.resample(
                audio_data.astype(np.float32),
                orig_sr=source_sr,
                target_sr=self.sample_rate
            )
        
        # 归一化，但保留一定的动态范围
        normalized = audio_data.astype(np.float32)
        if np.max(np.abs(normalized)) > 0:
            normalized = normalized / np.max(np.abs(normalized))
        
        return normalized

    async def realtime_transcribe(self, audio_queue: asyncio.Queue) -> AsyncGenerator[str, None]:
        """实时转录（需要配合音频流使用）"""
        self._recording = True
        while self._recording:
            audio_chunk = await audio_queue.get()
            text = await self.transcribe_audio(audio_chunk)
            if text:
                yield text

    async def cleanup(self):
        """清理资源"""
        if self.model:
            del self.model
            self.model = None
        self.executor.shutdown(wait=False)
        logger.info("Whisper resources cleaned up") 