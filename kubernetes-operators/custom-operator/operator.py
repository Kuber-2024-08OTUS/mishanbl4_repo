from kubernetes import client, config, watch
from kubernetes.client.rest import ApiException
import os
import time

config.load_incluster_config()

api_core = client.CoreV1Api()
api_apps = client.AppsV1Api()
api_crd = client.CustomObjectsApi()

GROUP = "otus.homework"
VERSION = "v1"
PLURAL = "mysqls"
NAMESPACE = "default"

def create_resources(mysql):
    metadata = mysql['metadata']
    spec = mysql['spec']
    name = metadata['name']

    labels = {"app": f"mysql-{name}"}

    # PVC
    pvc = client.V1PersistentVolumeClaim(
        metadata=client.V1ObjectMeta(name=name),
        spec=client.V1PersistentVolumeClaimSpec(
            access_modes=["ReadWriteOnce"],
            resources=client.V1ResourceRequirements(
                requests={"storage": spec["storage_size"]}
            )
        )
    )

    # Deployment
    container = client.V1Container(
        name="mysql",
        image=spec["image"],
        env=[
            client.V1EnvVar(name="MYSQL_ROOT_PASSWORD", value=spec["password"]),
            client.V1EnvVar(name="MYSQL_DATABASE", value=spec["database"]),
        ],
        ports=[client.V1ContainerPort(container_port=3306)],
        volume_mounts=[client.V1VolumeMount(name="mysql-data", mount_path="/var/lib/mysql")]
    )

    deployment = client.V1Deployment(
        metadata=client.V1ObjectMeta(name=name),
        spec=client.V1DeploymentSpec(
            replicas=1,
            selector=client.V1LabelSelector(match_labels=labels),
            template=client.V1PodTemplateSpec(
                metadata=client.V1ObjectMeta(labels=labels),
                spec=client.V1PodSpec(
                    containers=[container],
                    volumes=[client.V1Volume(
                        name="mysql-data",
                        persistent_volume_claim=client.V1PersistentVolumeClaimVolumeSource(claim_name=name)
                    )]
                )
            )
        )
    )

    # Service
    service = client.V1Service(
        metadata=client.V1ObjectMeta(name=name),
        spec=client.V1ServiceSpec(
            selector=labels,
            ports=[client.V1ServicePort(port=3306)]
        )
    )

    try:
        api_core.create_namespaced_persistent_volume_claim(namespace=NAMESPACE, body=pvc)
        api_apps.create_namespaced_deployment(namespace=NAMESPACE, body=deployment)
        api_core.create_namespaced_service(namespace=NAMESPACE, body=service)
    except ApiException as e:
        print(f"Error creating resources for {name}: {e}")

def delete_resources(name):
    try:
        api_core.delete_namespaced_service(namespace=NAMESPACE, name=name, body=client.V1DeleteOptions())
        api_apps.delete_namespaced_deployment(namespace=NAMESPACE, name=name, body=client.V1DeleteOptions())
        api_core.delete_namespaced_persistent_volume_claim(namespace=NAMESPACE, name=name, body=client.V1DeleteOptions())
    except ApiException as e:
        print(f"Error deleting resources for {name}: {e}")

def watch_mysql():
    w = watch.Watch()
    print("Watching MySQL objects...")
    for event in w.stream(api_crd.list_cluster_custom_object, group=GROUP, version=VERSION, plural=PLURAL):
        obj = event['object']
        event_type = event['type']
        name = obj['metadata']['name']
        print(f"Event: {event_type} on {name}")

        if event_type == 'ADDED':
            create_resources(obj)
        elif event_type == 'DELETED':
            delete_resources(name)

if __name__ == "__main__":
    while True:
        try:
            watch_mysql()
        except Exception as e:
            print(f"Exception: {e}")
            time.sleep(5)