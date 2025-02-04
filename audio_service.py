"""
Audio recording service implementation using sounddevice and PyAudio.
"""
from typing import Callable, Optional
import numpy as np
import sounddevice as sd
from loguru import logger

class AudioRecordingService:
    """
    Service for handling audio recording with real-time volume level detection.
    """
    def __init__(self, sample_rate: int = 44100, channels: int = 1):
        """
        Initialize the audio recording service.
        
        Args:
            sample_rate: The sample rate for recording (default: 44100 Hz)
            channels: Number of audio channels (default: 1 for mono)
        """
        self.sample_rate = sample_rate
        self.channels = channels
        self.recording = False
        self.audio_data = []
        self._volume_callback: Optional[Callable[[float], None]] = None
        self._initialized = False
        self.stream = None

    def initialize(self) -> None:
        """Initialize audio device and check availability."""
        if self._initialized:
            return

        try:
            # Check if audio device is available
            devices = sd.query_devices()
            if not devices:
                raise RuntimeError("No audio devices found")

            # Try to get default input device
            try:
                default_device = sd.query_devices(kind='input')
                logger.info(f"Using default input device: {default_device['name']}")
            except sd.PortAudioError as e:
                raise RuntimeError(f"No default input device available: {e}")

            # Test device by opening a short stream
            test_stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                callback=lambda *args: None
            )
            test_stream.start()
            test_stream.stop()
            test_stream.close()

            self._initialized = True
            logger.info("Audio recording service initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize audio service: {e}")
            raise RuntimeError(f"Audio initialization failed: {e}")

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
            
            # 创建音频流
            self.stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                callback=self._audio_callback
            )
            self.recording = True
            self.stream.start()
            logger.info("Started audio recording")
        except Exception as e:
            self.recording = False
            logger.error(f"Failed to start recording: {e}")
            raise

    def stop_recording(self) -> np.ndarray:
        """Stop recording and return the recorded audio data."""
        if not self.recording:
            logger.warning("No recording in progress")
            return np.array([])

        try:
            if self.stream:
                self.stream.stop()
                self.stream.close()
                self.stream = None
            self.recording = False
            
            # 检查是否有录音数据
            if not self.audio_data:
                logger.warning("No audio data collected")
                return np.array([])
            
            # 合并所有音频数据
            audio_data = np.concatenate(self.audio_data)
            
            # 检查音频数据质量
            if np.any(np.isnan(audio_data)) or np.any(np.isinf(audio_data)):
                logger.error("Invalid audio data in recording")
                return np.array([])
            
            logger.info(f"Stopped recording, audio length: {len(audio_data)}")
            self.audio_data = []  # 清空缓存
            return audio_data
        
        except Exception as e:
            logger.error(f"Error stopping recording: {e}")
            self.recording = False
            raise

    def _audio_callback(self, indata: np.ndarray, frames: int, 
                       time_info: dict, status: sd.CallbackFlags) -> None:
        """Audio callback function."""
        if status:
            logger.warning(f"Audio callback status: {status}")
        
        # 检查音频数据质量
        if np.any(np.isnan(indata)) or np.any(np.isinf(indata)):
            logger.warning("Invalid audio data detected")
            return
        
        # 检查是否有声音
        volume = np.max(np.abs(indata))
        if volume < 0.01:  # 音量太小
            logger.debug(f"Low volume detected: {volume}")
        
        # 存储音频数据
        self.audio_data.append(indata.copy())
        
        # 计算音量级别并回调
        if self._volume_callback:
            volume_norm = np.linalg.norm(indata) / np.sqrt(len(indata))
            self._volume_callback(volume_norm)

    @property
    def is_recording(self) -> bool:
        """Check if recording is in progress."""
        return self.recording 