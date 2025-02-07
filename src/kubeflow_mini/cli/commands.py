"""CLI命令"""
import click
from tabulate import tabulate
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
    pass

@cli.command()
@click.option('--namespace', '-n', default='default', help='命名空间')
@click.option('--project', '-p', help='按项目筛选')
@click.option('--owner', '-o', help='按所有者筛选')
@click.option('--tag', '-t', help='按标签筛选')
def list(namespace, project, owner, tag):
    """列出所有MLJob"""
    api = init_kubernetes()
    try:
        jobs = api.list_namespaced_custom_object(
            group="kubeflow-mini.io",
            version="v1",
            namespace=namespace,
            plural="mljobs"
        )
        
        headers = ['任务ID', '名称', '项目', '所有者', '状态', '优先级', '标签', '创建时间']
        rows = []
        
        for job in jobs.get('items', []):
            metadata = job.get('metadata', {})
            spec = job.get('spec', {})
            status = job.get('status', {})
            
            # 根据条件筛选
            if project and spec.get('project') != project:
                continue
            if owner and spec.get('owner') != owner:
                continue
            if tag and tag not in spec.get('tags', []):
                continue
            
            rows.append([
                spec.get('jobId', 'N/A'),
                metadata.get('name'),
                spec.get('project', 'N/A'),
                spec.get('owner', 'N/A'),
                status.get('phase', 'Unknown'),
                spec.get('priority', 50),
                ', '.join(spec.get('tags', [])),
                metadata.get('creationTimestamp', 'Unknown')
            ])
        
        if rows:
            print(tabulate(rows, headers=headers, tablefmt='grid'))
        else:
            print(f"在命名空间 {namespace} 中没有找到任何MLJob")
            
    except ApiException as e:
        print(f"获取MLJob列表失败: {e}")

@cli.command()
@click.argument('identifier')
@click.option('--namespace', '-n', default='default', help='命名空间')
@click.option('--by-id', is_flag=True, help='使用任务ID查询')
@click.option('--show-training/--no-training', default=False, help='是否显示training-operator任务信息')
def get(identifier, namespace, by_id, show_training):
    """获取MLJob详细信息"""
    api = init_kubernetes()
    try:
        if by_id:
            # 通过JobId查询
            jobs = api.list_namespaced_custom_object(
                group="kubeflow-mini.io",
                version="v1",
                namespace=namespace,
                plural="mljobs",
                label_selector=f"mljob.kubeflow-mini.io/job-id={identifier}"
            )
            if not jobs.get('items'):
                print(f"未找到JobId为 {identifier} 的任务")
                return
            mljob = jobs['items'][0]
        else:
            # 通过名称查询
            mljob = api.get_namespaced_custom_object(
                group="kubeflow-mini.io",
                version="v1",
                namespace=namespace,
                plural="mljobs",
                name=identifier
            )
        
        metadata = mljob.get('metadata', {})
        spec = mljob.get('spec', {})
        status = mljob.get('status', {})
        
        # 打印基本信息
        print("\nMLJob信息:")
        print(f"名称: {metadata.get('name')}")
        print(f"命名空间: {metadata.get('namespace')}")
        print(f"任务ID: {spec.get('jobId', 'N/A')}")
        print(f"项目: {spec.get('project', 'N/A')}")
        print(f"所有者: {spec.get('owner', 'N/A')}")
        print(f"描述: {spec.get('description', 'N/A')}")
        print(f"标签: {', '.join(spec.get('tags', []))}")
        print(f"优先级: {spec.get('priority', 50)}")
        print(f"创建时间: {metadata.get('creationTimestamp')}")
        
        # 打印状态信息
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
            training_spec = spec.get('training')
            if training_spec:
                try:
                    group, version = training_spec['apiVersion'].split('/')
                    kind = training_spec['kind'].lower() + 's'
                    training_job = api.get_namespaced_custom_object(
                        group=group,
                        version=version,
                        namespace=namespace,
                        plural=kind,
                        name=metadata.get('name')
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
            print(f"MLJob {identifier} 在命名空间 {namespace} 中不存在")
        else:
            print(f"获取MLJob信息失败: {e}") 