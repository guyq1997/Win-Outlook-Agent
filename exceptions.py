"""
Custom exceptions for speech recognition services.
"""

class SpeechRecognitionError(Exception):
    """Base exception for speech recognition errors."""
    pass

class ProviderInitializationError(SpeechRecognitionError):
    """Exception raised when a speech recognition provider fails to initialize."""
    pass

class RecognitionTimeoutError(SpeechRecognitionError):
    """Exception raised when speech recognition times out."""
    pass

class AudioDeviceError(SpeechRecognitionError):
    """Exception raised when there are issues with audio devices."""
    pass

class UnsupportedLanguageError(SpeechRecognitionError):
    """Exception raised when attempting to use an unsupported language."""
    pass

class RecognitionInProgressError(SpeechRecognitionError):
    """Exception raised when attempting to start recognition while it's already running."""
    pass

class ProviderNotReadyError(SpeechRecognitionError):
    """Exception raised when trying to use a provider that's not initialized."""
    pass 