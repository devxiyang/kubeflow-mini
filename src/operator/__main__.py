"""Operator入口"""

import os
import logging
import kopf
from kubernetes import config

# 配置日志
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

def main():
    """Operator主函数"""
    try:
        # 加载kubeconfig
        if os.getenv("KUBERNETES_SERVICE_HOST"):
            config.load_incluster_config()
        else:
            config.load_kube_config()
            
        # 启动operator
        kopf.run()
    except Exception as e:
        logger.error(f"Failed to start operator: {str(e)}")
        raise

if __name__ == "__main__":
    main() 