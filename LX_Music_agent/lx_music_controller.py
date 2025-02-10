import webbrowser
import urllib.parse
import psutil
import time
import os
import subprocess
from loguru import logger

class LXMusicController:
    BASE_URL = "lxmusic://"
    APP_NAME = "lx-music-desktop.exe"  # Windows executable name
    # 添加一个类变量来存储自定义路径
    CUSTOM_PATH = "D:/LXMUSIC/lx-music-desktop/lx-music-desktop.exe"  # 可以在初始化时设置
    



    @staticmethod
    def is_running():
        """Check if LX Music is running"""
        for proc in psutil.process_iter(['name']):
            try:
                if proc.info['name'] == LXMusicController.APP_NAME:
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        return False
    
    @staticmethod
    def ensure_app_running():
        """Ensure LX Music is running, launch if not"""
        if not LXMusicController.is_running():
            logger.info("LX Music is not running. Attempting to launch...")
            
            # 扩展可能的安装路径
            possible_paths = [
                # 检查自定义路径
                LXMusicController.CUSTOM_PATH,
                # 常见的安装位置
                os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Programs', 'lx-music-desktop', LXMusicController.APP_NAME),
                os.path.join(os.environ.get('PROGRAMFILES', ''), 'lx-music-desktop', LXMusicController.APP_NAME),
                os.path.join(os.environ.get('PROGRAMFILES(X86)', ''), 'lx-music-desktop', LXMusicController.APP_NAME),
                # 添加桌面快捷方式位置
                os.path.join(os.path.expanduser('~'), 'Desktop', 'lx-music-desktop.exe'),
                # 添加开始菜单位置
                os.path.join(os.environ.get('APPDATA', ''), 'Microsoft', 'Windows', 'Start Menu', 'Programs', 'lx-music-desktop', LXMusicController.APP_NAME),
            ]
            
            # 过滤掉 None 和空字符串的路径
            possible_paths = [p for p in possible_paths if p]
            
            for path in possible_paths:
                logger.debug(f"Checking path: {path}")
                if os.path.exists(path):
                    try:
                        logger.info(f"Found LX Music at: {path}")
                        subprocess.Popen(path)
                        # 等待应用启动
                        for _ in range(20):  # 增加等待时间到10秒
                            if LXMusicController.is_running():
                                logger.success("LX Music launched successfully")
                                time.sleep(1)  # 额外等待1秒确保完全启动
                                return True
                            time.sleep(0.5)
                    except Exception as e:
                        logger.error(f"Error launching LX Music at {path}: {e}")
                        continue
            
            logger.error("Could not find LX Music installation. Please set CUSTOM_PATH or ensure correct installation.")
            return False
        return True

    def __init__(self, custom_path=None):
        """Initialize with optional custom path to LX Music executable"""
        if custom_path:
            LXMusicController.CUSTOM_PATH = custom_path

    @staticmethod
    def _open_url(url):
        """Helper method to open LX Music URLs"""
        try:
            # 确保应用正在运行
            if not LXMusicController.ensure_app_running():
                logger.error("Failed to ensure LX Music is running")
                return False
            
            # 等待一小段时间确保应用完全启动
            time.sleep(0.5)
            webbrowser.open(url)
            logger.debug(f"Opened URL: {url}")
            return True
        except Exception as e:
            logger.error(f"Error opening LX Music URL: {e}")
            return False

    def play(self):
        """Start playing music"""
        try:
            logger.info("Attempting to start music playback")
            self._open_url(self.BASE_URL + "player/play")
            return "Success: Music playback started"
        except Exception as e:
            logger.error(f"Failed to start playback: {e}")
            return f"Error: Failed to start playback - {str(e)}"

    def pause(self):
        """Pause music playback"""
        try:
            logger.info("Attempting to pause music playback")
            self._open_url(self.BASE_URL + "player/pause")
            return "Success: Music playback paused"
        except Exception as e:
            logger.error(f"Failed to pause playback: {e}")
            return f"Error: Failed to pause playback - {str(e)}"


    def next_track(self):
        """Play next track"""
        try:
            self._open_url(self.BASE_URL + "player/skipNext")
            return "Success: Next track played"
        except Exception as e:
            return f"Error: Failed to play next track - {str(e)}"
    

    def previous_track(self):
        """Play previous track"""
        try:
            self._open_url(self.BASE_URL + "player/skipPrevious")
            return "Success: Previous track played"
        except Exception as e:
            return f"Error: Failed to play previous track - {str(e)}"



    def search_and_play(self, song_name, singer_name = None):
        """Search and play music directly"""
        try:
            logger.info(f"Searching for song: {song_name}" + (f" by {singer_name}" if singer_name else ""))
            if singer_name:
                name = f"{song_name}-{singer_name}"
            else:
                name = song_name

            url = f"{self.BASE_URL}music/searchPlay/{urllib.parse.quote(name)}"
            self._open_url(url)
            return "Success: Search and play initiated"
        except Exception as e:
            logger.error(f"Failed to search and play: {e}")
            return f"Error: Failed to search and play - {str(e)}"

# Example usage
if __name__ == "__main__":
    controller = LXMusicController()
    
    # 检查应用是否运行
    if not LXMusicController.is_running():
        print("LX Music is not running. Attempting to launch...")
        if not LXMusicController.ensure_app_running():
            print("Failed to launch LX Music. Please make sure it's installed correctly.")
            exit(1)
        print("LX Music launched successfully!")
    
    # Example: Toggle play/pause
    controller.toggle_play()
    
    # Example: Search for a song
    # controller.search_music("突然的自我")
    
    # Example: Play next track
    # controller.next_track() 