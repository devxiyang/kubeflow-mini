"""配置管理模块

该模块负责加载和管理kubeflow-mini的配置信息，包括：
1. 加载配置文件
2. 提供配置访问接口
3. 配置验证
"""

import os
import yaml
import logging
from typing import Dict, Any

class Config:
    """配置管理类"""
    
    def __init__(self):
        self._config = {}
        self._logger = logging.getLogger(__name__)
    
    def load(self, config_path: str = None) -> None:
        """加载配置文件
        
        Args:
            config_path: 配置文件路径，如果为None则使用默认路径
            
        Raises:
            FileNotFoundError: 配置文件不存在
            yaml.YAMLError: 配置文件格式错误
        """
        # 默认配置文件路径
        if config_path is None:
            config_path = os.environ.get(
                'KUBEFLOW_MINI_CONFIG',
                os.path.join(os.path.dirname(__file__), '../../config/config.yaml')
            )
        
        try:
            with open(config_path, 'r') as f:
                self._config = yaml.safe_load(f)
            self._logger.info(f"Loaded configuration from {config_path}")
        except FileNotFoundError:
            self._logger.warning(f"Config file not found: {config_path}, using default configuration")
            self._load_default_config()
        except yaml.YAMLError as e:
            self._logger.error(f"Failed to parse config file: {e}")
            raise
    
    def _load_default_config(self) -> None:
        """加载默认配置"""
        self._config = {
            'retry': {
                'default': {
                    'max_retries': 3,
                    'delay': 1
                },
                'operations': {
                    'create': {'max_retries': 3, 'delay': 2},
                    'delete': {'max_retries': 5, 'delay': 1},
                    'update': {'max_retries': 3, 'delay': 2},
                    'get': {'max_retries': 3, 'delay': 1}
                }
            },
            'logging': {
                'level': 'INFO',
                'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            },
            'api': {
                'group': 'kubeflow-mini.io',
                'version': 'v1',
                'plural': 'mljobs'
            },
            'status': {
                'phases': ['Created', 'Running', 'Failed', 'Succeeded', 'Deleted'],
                'conditions': {
                    'default_status': 'True',
                    'time_format': '%Y-%m-%dT%H:%M:%SZ'
                }
            }
        }
    
    def get_retry_config(self, operation: str = None) -> Dict[str, Any]:
        """获取重试配置
        
        Args:
            operation: 操作类型，如果为None则返回默认配置
            
        Returns:
            重试配置字典
        """
        retry_config = self._config.get('retry', {})
        if operation:
            return retry_config.get('operations', {}).get(
                operation,
                retry_config.get('default', {})
            )
        return retry_config.get('default', {})
    
    def get_logging_config(self) -> Dict[str, Any]:
        """获取日志配置"""
        return self._config.get('logging', {})
    
    def get_api_config(self) -> Dict[str, Any]:
        """获取API配置"""
        return self._config.get('api', {})
    
    def get_status_config(self) -> Dict[str, Any]:
        """获取状态配置"""
        return self._config.get('status', {})

# 全局配置实例
config = Config() 