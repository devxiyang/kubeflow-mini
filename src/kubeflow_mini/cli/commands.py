"""CLI命令"""
import click
from tabulate import tabulate
from ..db import init_db, list_jobs, get_job
from kubernetes import config, client
from kubernetes.client.rest import ApiException

def init_kubernetes():
    """初始化Kubernetes客户端"""
    try:
        config.load_kube_config()
    except:
        config.load_incluster_config()
    return client.CustomObjectsApi()

@click.group()
def cli():
    """机器学习任务管理工具"""
    init_db()

@cli.command()
@click.option('--namespace', help='筛选指定命名空间的任务')
@click.option('--status', help='筛选指定状态的任务')
def list(namespace=None, status=None):
    """列出所有任务"""
    jobs = list_jobs(namespace, status)
    
    headers = ['名称', '命名空间', '框架', '状态', '创建时间']
    rows = []
    
    for job in jobs:
        rows.append([
            job.name,
            job.namespace,
            job.framework,
            job.status,
            job.created_at.strftime('%Y-%m-%d %H:%M:%S')
        ])
    
    if rows:
        print(tabulate(rows, headers=headers, tablefmt='grid'))
    else:
        print("没有找到任何任务")

@cli.command()
@click.argument('name')
@click.argument('namespace')
def status(name, namespace):
    """查看指定任务的详细状态"""
    job = get_job(name, namespace)
    
    if job:
        print("\n任务详情:")
        print(f"名称: {job.name}")
        print(f"命名空间: {job.namespace}")
        print(f"框架: {job.framework}")
        print(f"版本: {job.framework_version}")
        print(f"分布式训练: {'是' if job.distributed else '否'}")
        print(f"Worker副本数: {job.worker_replicas}")
        
        if job.ps_replicas and job.ps_replicas > 0:
            print(f"Parameter Server副本数: {job.ps_replicas}")
            
        print(f"镜像: {job.image}")
        print(f"状态: {job.status}")
        print(f"创建时间: {job.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        
        if job.completed_at:
            print(f"完成时间: {job.completed_at.strftime('%Y-%m-%d %H:%M:%S')}")
        
        if job.error_message:
            print(f"错误信息: {job.error_message}")
    else:
        print(f"未找到任务: {name} (命名空间: {namespace})")

@cli.command()
@click.option('--namespace', '-n', default='default', help='命名空间')
def list_mljob(namespace):
    """列出所有MLJob"""
    api = init_kubernetes()
    try:
        jobs = api.list_namespaced_custom_object(
            group="kubeflow-mini.io",
            version="v1",
            namespace=namespace,
            plural="mljobs"
        )
        
        headers = ['名称', '状态', '创建时间']
        rows = []
        
        for job in jobs.get('items', []):
            metadata = job.get('metadata', {})
            status = job.get('status', {})
            rows.append([
                metadata.get('name'),
                status.get('phase', 'Unknown'),
                metadata.get('creationTimestamp', 'Unknown')
            ])
        
        if rows:
            print(tabulate(rows, headers=headers, tablefmt='grid'))
        else:
            print(f"在命名空间 {namespace} 中没有找到任何MLJob")
            
    except ApiException as e:
        print(f"获取MLJob列表失败: {e}")

@cli.command()
@click.argument('name')
@click.option('--namespace', '-n', default='default', help='命名空间')
@click.option('--show-training/--no-training', default=False, help='是否显示training-operator任务信息')
def get_mljob(name, namespace, show_training):
    """获取MLJob详细信息"""
    api = init_kubernetes()
    try:
        # 获取MLJob信息
        mljob = api.get_namespaced_custom_object(
            group="kubeflow-mini.io",
            version="v1",
            namespace=namespace,
            plural="mljobs",
            name=name
        )
        
        # 打印基本信息
        print("\nMLJob信息:")
        print(f"名称: {mljob['metadata']['name']}")
        print(f"命名空间: {mljob['metadata']['namespace']}")
        print(f"创建时间: {mljob['metadata']['creationTimestamp']}")
        
        # 打印状态信息
        status = mljob.get('status', {})
        print(f"\n状态: {status.get('phase', 'Unknown')}")
        
        # 打印状态历史
        conditions = status.get('conditions', [])
        if conditions:
            print("\n状态历史:")
            for condition in conditions:
                print(f"- {condition['type']}: {condition['status']}")
                print(f"  时间: {condition['lastTransitionTime']}")
                print(f"  原因: {condition['reason']}")
                print(f"  信息: {condition.get('message', '')}")
        
        # 如果需要，获取并打印training-operator任务信息
        if show_training:
            training_spec = mljob['spec'].get('training')
            if training_spec:
                try:
                    group, version = training_spec['apiVersion'].split('/')
                    kind = training_spec['kind'].lower() + 's'
                    training_job = api.get_namespaced_custom_object(
                        group=group,
                        version=version,
                        namespace=namespace,
                        plural=kind,
                        name=name
                    )
                    print(f"\nTraining Job状态:")
                    print(f"状态: {training_job.get('status', {}).get('phase', 'Unknown')}")
                except ApiException as e:
                    if e.status != 404:
                        print(f"获取Training Job信息失败: {e}")
                    else:
                        print("Training Job不存在")
            
    except ApiException as e:
        if e.status == 404:
            print(f"MLJob {name} 在命名空间 {namespace} 中不存在")
        else:
            print(f"获取MLJob信息失败: {e}") 