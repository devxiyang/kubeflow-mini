"""主入口模块

该模块是kubeflow-mini的入口点，负责：
1. 加载配置文件
2. 初始化日志系统
3. 初始化Kubernetes客户端
4. 启动operator
"""

import os
import sys
import logging
import kopf
from kubernetes import config as k8s_config, client
from .config import config

def init_kubernetes():
    """初始化Kubernetes客户端
    
    尝试以下方式加载配置：
    1. 集群内配置
    2. kubeconfig文件
    3. 默认配置文件路径
    
    Returns:
        bool: 初始化是否成功
    """
    try:
        # 首先尝试集群内配置
        k8s_config.load_incluster_config()
        logging.info("Using in-cluster Kubernetes configuration")
        return True
    except Exception:
        try:
            # 然后尝试kubeconfig
            k8s_config.load_kube_config()
            logging.info("Using kubeconfig for Kubernetes configuration")
            return True
        except Exception as e:
            logging.error(f"Failed to initialize Kubernetes client: {e}")
            return False

def main():
    """主入口函数
    
    1. 加载配置文件
    2. 配置日志系统
    3. 初始化Kubernetes客户端
    4. 启动operator
    """
    try:
        # 加载配置
        config_path = os.environ.get('KUBEFLOW_MINI_CONFIG')
        config.load(config_path)
        
        # 配置日志
        logging_config = config.get_logging_config()
        logging.basicConfig(
            level=logging_config.get('level', 'INFO'),
            format=logging_config.get('format')
        )
        
        # 初始化Kubernetes客户端
        if not init_kubernetes():
            logging.error("Failed to initialize Kubernetes client")
            sys.exit(1)
        
        # 验证API访问权限
        try:
            api = client.ApiClient()
            version = client.VersionApi(api).get_code()
            logging.info(f"Connected to Kubernetes {version.git_version}")
        except Exception as e:
            logging.error(f"Failed to connect to Kubernetes API: {e}")
            sys.exit(1)
        
        # 运行operator
        logging.info("Starting kubeflow-mini operator")
        kopf.run()
        
    except Exception as e:
        logging.error(f"Failed to start kubeflow-mini: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main() 