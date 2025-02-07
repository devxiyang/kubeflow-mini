"""Owner资源处理器

该模块负责处理Owner资源的基本CRUD操作。
"""

import kopf
import logging
from kubernetes.client.rest import ApiException
from datetime import datetime
from .handlers import retry_on_error, ResourceNotFoundError
from ..config import config

API_CONFIG = config.get_api_config()

@kopf.on.create('owners')
def create_owner(spec, name, logger, **kwargs):
    """处理Owner创建"""
    try:
        current_time = datetime.utcnow().isoformat() + "Z"
        return {
            'status': {
                'lastUpdateTime': current_time
            }
        }
    except Exception as e:
        logger.error(f"Failed to create owner: {e}")
        raise kopf.PermanentError(str(e))

@kopf.on.update('owners')
def update_owner(spec, name, logger, **kwargs):
    """处理Owner更新"""
    try:
        current_time = datetime.utcnow().isoformat() + "Z"
        return {
            'status': {
                'lastUpdateTime': current_time
            }
        }
    except Exception as e:
        logger.error(f"Failed to update owner: {e}")
        raise kopf.PermanentError(str(e))

@retry_on_error(operation='get')
def get_owner(owner_name):
    """获取Owner信息"""
    api = kopf.CustomObjectsApi()
    try:
        return api.get_cluster_custom_object(
            group=API_CONFIG['group'],
            version=API_CONFIG['version'],
            plural='owners',
            name=owner_name
        )
    except ApiException as e:
        if e.status == 404:
            raise ResourceNotFoundError(f"Owner {owner_name} does not exist")
        raise 