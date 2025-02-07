"""主入口模块"""
import logging
from .db import init_db
from .operator import (
    create_ml_job,
    delete_ml_job,
    update_ml_job,
    monitor_job_status,
)

def main():
    """主入口函数"""
    # 配置日志级别
    logging.basicConfig(level=logging.INFO)
    
    # 初始化数据库
    init_db()
    
    # kopf会自动发现和注册处理函数
    import kopf
    kopf.run() 