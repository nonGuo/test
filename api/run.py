# -*- coding: utf-8 -*-
"""
API 服务启动脚本
"""
import os
import sys
from dotenv import load_dotenv

# 加载环境变量
env_file = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(env_file):
    load_dotenv(env_file)
    print(f"[INFO] 已加载环境变量：{env_file}")
else:
    print(f"[WARNING] 环境变量文件不存在：{env_file}")
    print("[INFO] 请复制 .env.example 为 .env 并配置相关参数")

# 添加项目根目录到 Python 路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from api.app import create_app, Config

if __name__ == '__main__':
    app = create_app()
    
    print(f"""
╔══════════════════════════════════════════════════════════╗
║   数仓测试用例生成工具 - API 服务                          ║
╠══════════════════════════════════════════════════════════╣
║   版本：{Config.VERSION}
║   地址：http://{Config.HOST}:{Config.PORT}
║   健康检查：http://{Config.HOST}:{Config.PORT}/api/v1/health
║   配置信息：http://{Config.HOST}:{Config.PORT}/api/v1/config
╚══════════════════════════════════════════════════════════╝

按 Ctrl+C 停止服务
    """)
    
    app.run(
        host=Config.HOST,
        port=Config.PORT,
        debug=Config.DEBUG
    )
