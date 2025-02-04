import sys
import os
from pathlib import Path

# 确保运行路径正确
script_dir = Path(__file__).parent
os.chdir(script_dir)

# 添加当前目录到Python路径
sys.path.append(str(script_dir))

# 启动应用
from voice_email_workflow_ui import main
main() 