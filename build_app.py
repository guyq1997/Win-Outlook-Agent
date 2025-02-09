import PyInstaller.__main__
import os
import shutil

def build_app():
    # 确保 dist 目录是空的
    if os.path.exists("dist"):
        shutil.rmtree("dist")
    if os.path.exists("build"):
        shutil.rmtree("build")

    # PyInstaller 参数
    args = [
        'voice_email_workflow_ui.py',  # 主程序文件
        '--name=VoiceEmailAssistant',  # 应用程序名称
        '--noconsole',  # 不显示控制台窗口
        '--onedir',  # 创建单文件夹
        # '--icon=app_icon.ico',  # 应用图标（如果有的话）
        '--add-data=.env;.',  # 添加环境配置文件
        '--hidden-import=PyQt6',
        '--hidden-import=qasync',
        '--hidden-import=keyboard',
        '--hidden-import=sounddevice',
        '--hidden-import=numpy',
        '--hidden-import=openai',
        '--hidden-import=anthropic',
        '--hidden-import=torch',
        '--hidden-import=torchaudio',
        '--hidden-import=librosa',
        '--hidden-import=websockets',
    ]

    # 运行 PyInstaller
    PyInstaller.__main__.run(args)

    print("应用程序打包完成！")
    print("可执行文件位于 dist/VoiceEmailAssistant 目录中")

if __name__ == "__main__":
    build_app() 