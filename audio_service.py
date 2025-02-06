"""
Audio recording service implementation using sounddevice and PyAudio.
"""
from typing import Callable, Optional, Generator
import numpy as np
import sounddevice as sd
from loguru import logger
from queue import Queue, Empty
import wave
from datetime import datetime
import scipy.signal
import asyncio

MAX_QUEUE_SIZE = 50  # 根据硬件性能调整

class AudioProcessor:
    def __init__(self, target_sample_rate=24000):
        self.target_sample_rate = target_sample_rate
        self.source_sample_rate = 48000
        # 预计算重采样比例
        self.resample_ratio = self.target_sample_rate / self.source_sample_rate
        
    def process_audio_chunk(self, audio_data):
        # 转换二进制音频数据为 Int16 数组
        pcm_data = np.frombuffer(audio_data, dtype=np.int16)
        
        # 如果采样率相同，直接返回
        if self.target_sample_rate == self.source_sample_rate:
            return audio_data
            
        # 使用更高效的重采样方法
        resampled_data = scipy.signal.resample_poly(
            pcm_data, 
            self.target_sample_rate, 
            self.source_sample_rate,
            padtype='line'  # 使用线性填充
        )
        
        # 直接转换为int16并返回字节
        return resampled_data.astype(np.int16).tobytes()

class AudioRecordingService:
    """
    Service for handling audio recording with real-time volume level detection.
    """
    def __init__(self, sample_rate: int = 48000, channels: int = 1, target_sample_rate: int = 24000):
        """
        Initialize the audio recording service.
        
        Args:
            sample_rate: The sample rate for recording (default: 48000 Hz)
            channels: Number of audio channels (default: 1 for mono)
            target_sample_rate: Target sample rate for processed audio (default: 24000 Hz)
        """
        self.sample_rate = sample_rate
        self.target_sample_rate = target_sample_rate
        self.channels = channels
        self.recording = False
        self.audio_data = []
        self._volume_callback: Optional[Callable[[float], None]] = None
        self._initialized = False
        self.stream = None
        self.audio_queue = asyncio.Queue(maxsize=100)  # 增加队列大小
        self.loop = asyncio.get_event_loop()
        self.all_chunks_processed = False
        self._chunk_counter = 0
        self.audio_processor = AudioProcessor(target_sample_rate)
        self._processing_lock = asyncio.Lock()  # 添加处理锁

    def initialize(self) -> bool:
        """Initialize audio device and check availability."""
        if self._initialized:
            return True

        try:
            # Check if audio devices are available
            devices = sd.query_devices()
            if not devices:
                logger.error("No audio devices found")
                return False

            # Try to get default input device
            try:
                default_device = sd.query_devices(kind='input')
                logger.info(f"Using default input device: {default_device['name']}")
            except sd.PortAudioError as e:
                logger.error(f"No default input device available: {e}")
                return False

            # Test device by opening a short stream
            try:
                test_stream = sd.InputStream(
                    samplerate=self.sample_rate,
                    channels=self.channels,
                    callback=lambda *args: None
                )
                test_stream.start()
                test_stream.stop()
                test_stream.close()
            except sd.PortAudioError as e:
                logger.error(f"Failed to test audio stream: {e}")
                return False

            self._initialized = True
            logger.info("Audio recording service initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize audio service: {e}")
            return False

    def cleanup(self) -> None:
        """Clean up resources and stop recording if active."""
        try:
            if self.recording:
                self.stop_recording()

            if self.stream:
                try:
                    self.stream.close()
                except Exception as e:
                    logger.warning(f"Error closing stream: {e}")
                finally:
                    self.stream = None

            self._initialized = False
            logger.info("Audio recording service cleaned up successfully")

        except Exception as e:
            logger.error(f"Error during audio service cleanup: {e}")
            raise

    def start_recording(self, volume_callback: Optional[Callable[[float], None]] = None) -> None:
        """Start audio recording."""
        if self.recording:
            logger.warning("Recording already in progress")
            return

        try:
            self.audio_data = []  # 清空之前的录音数据
            self._volume_callback = volume_callback
            
            # 创建音频流时增加dtype参数
            self.stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                callback=self._audio_callback,
                blocksize=2048,
                latency='low',
                device=None,
                dtype=np.int16  # 明确指定数据类型
            )
            self.recording = True
            self.stream.start()
            logger.info("Started audio recording")
        except Exception as e:
            self.recording = False
            logger.error(f"Failed to start recording: {e}")
            raise

    def _process_audio_data(self, audio_data: np.ndarray) -> np.ndarray:
        """优化的音频处理流程"""
        # 直接处理 int16 数据，避免不必要的转换
        if self.sample_rate != self.target_sample_rate:
            resampled = scipy.signal.resample_poly(
                audio_data,
                self.target_sample_rate,
                self.sample_rate
            )
            return resampled.astype(np.int16)
        return audio_data

    def _audio_callback(self, indata: np.ndarray, frames: int, time_info: dict, status: sd.CallbackFlags) -> None:
        """优化的音频回调函数"""
        try:
            if status.input_overflow:
                logger.warning("Input overflow occurred")
                return
                
            # 直接处理音频数据
            processed_audio = self.audio_processor.process_audio_chunk(indata.tobytes())
            self.audio_data.append(processed_audio)

            async def process_and_queue():
                async with self._processing_lock:
                    try:
                        if not self.audio_queue.full():
                            self.audio_queue.put_nowait(processed_audio)
                        else:
                            try:
                                self.audio_queue.get_nowait()
                                self.audio_queue.put_nowait(processed_audio)
                            except asyncio.QueueEmpty:
                                pass
                    except Exception as e:
                        logger.error(f"Error in audio processing: {e}")

            asyncio.run_coroutine_threadsafe(process_and_queue(), self.loop)
                
        except Exception as e:
            logger.error(f"Audio callback error: {str(e)}")

    def stop_recording(self) -> np.ndarray:
        """停止录音并返回完整音频"""
        if not self.recording:
            logger.warning("No recording in progress")
            return np.array([], dtype=np.int16)

        try:
            if self.stream:
                self.stream.stop()
                self.stream.close()
                self.stream = None
            self.recording = False
            
            # 直接从audio_data获取数据
            if not self.audio_data:
                logger.warning("No audio data recorded")
                return np.array([], dtype=np.int16)
            
            # 合并所有音频块
            full_audio = np.concatenate([np.frombuffer(chunk, dtype=np.int16) for chunk in self.audio_data])
            
            # 清空队列
            while not self.audio_queue.empty():
                try:
                    self.audio_queue.get_nowait()
                except asyncio.QueueEmpty:
                    break

            if full_audio.size == 0:
                logger.warning("Processed audio is empty")
                return np.array([], dtype=np.int16)
                
            return full_audio

        except Exception as e:
            logger.error(f"Error stopping recording: {e}")
            self.recording = False
            raise

    async def get_audio_chunk(self) -> Optional[bytes]:
        """异步获取音频数据"""
        try:
            # 添加超时以避免永久阻塞
            return await asyncio.wait_for(self.audio_queue.get(), timeout=0.1)
        except asyncio.TimeoutError:
            return None
        except asyncio.QueueEmpty:
            return None

    @property
    def is_recording(self) -> bool:
        """Check if recording is in progress."""
        return self.recording 

    def _get_all_chunks(self) -> Generator[bytes, None, None]:
        """获取所有音频块"""
        while not self.audio_queue.empty():
            try:
                yield self.audio_queue.get_nowait()
            except asyncio.QueueEmpty:
                break 