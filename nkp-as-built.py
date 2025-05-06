import subprocess
import yaml

def get_clusters():
    try:
        result = subprocess.run(
            ["kubectl", "get", "clusters", "-A"],
            capture_output=True,
            text=True,
            check=True
        )
        lines = result.stdout.strip().split("\n")
        clusters = []

        for line in lines[1:]:  # Skip the header line
            parts = line.split()
            if len(parts) >= 2:
                namespace = parts[0]
                clustername = parts[1]
                clusters.append({
                    "namespace": namespace,
                    "clustername": clustername
                })

        return clusters

    except subprocess.CalledProcessError as e:
        print(f"Error executing kubectl: {e}")
        return []

def get_cluster_yaml(namespace: str, cluster_name: str) -> dict:
    try:
        cmd = ["kubectl", "get", "cluster", cluster_name, "-n", namespace, "-o", "yaml"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return yaml.safe_load(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"Failed to get YAML for cluster {cluster_name} in namespace {namespace}: {e}")
        return {}

def print_cluster_details(cluster_name, cluster_yaml):
    topology = cluster_yaml.get('spec', {}).get('topology', {})
    control_plane = topology.get('controlPlane', {})
    worker_pools = topology.get('workers', {}).get('machineDeployments', [])

    # Kubernetes version
    kubernetes_version = topology.get('version', 'N/A')

    # Control Plane Endpoint
    control_plane_endpoint = cluster_yaml.get('spec', {}).get('controlPlaneEndpoint', {}).get('host', 'N/A')

    # Variables
    cluster_config = topology.get('variables', [])
    cni_provider = None
    service_lb_range = []
    worker_subnet = None
    image_registries = []

    control_plane_details = {}

    for var in cluster_config:
        name = var.get('name')
        value = var.get('value', {})

        if name == 'clusterConfig':
            cni_provider = value.get('addons', {}).get('cni', {}).get('provider', 'N/A')
            service_lb_range = value.get('addons', {}).get('serviceLoadBalancer', {}).get('configuration', {}).get('addressRanges', [])
            control_plane_details = value.get('controlPlane', {}).get('nutanix', {}).get('machineDetails', {})
            worker_subnet = value.get('worker')
        elif name == 'imageRegistries':
            credentials = value.get('credentials', [])
            image_registries.extend(credentials)

    # Extract required control plane fields
    cp_info = {
        "clusterName": control_plane_details.get('cluster', {}).get('name'),
        "imageName": control_plane_details.get('image', {}).get('name'),
        "memorySize": control_plane_details.get('memorySize'),
        "project": control_plane_details.get('project', {}).get('name'),
        "subnets": [s.get('name') for s in control_plane_details.get('subnets', [])],
        "systemDiskSize": control_plane_details.get('systemDiskSize'),
        "vcpuSockets": control_plane_details.get('vcpuSockets'),
        "vcpusPerSocket": control_plane_details.get('vcpusPerSocket'),
    }

    # Extract worker node pool configurations
    worker_configs = []
    for worker in worker_pools:
        worker_name = worker.get('name', 'N/A')
        overrides = worker.get('variables', {}).get('overrides', [])
        worker_details = {}

        for override in overrides:
            if override.get('name') == 'workerConfig':
                md = override.get('value', {}).get('nutanix', {}).get('machineDetails', {})
                worker_details = {
                    "workerName": worker_name,
                    "clusterName": md.get('cluster', {}).get('name'),
                    "imageName": md.get('image', {}).get('name'),
                    "memorySize": md.get('memorySize'),
                    "subnets": [s.get('name') for s in md.get('subnets', [])],
                    "systemDiskSize": md.get('systemDiskSize'),
                    "vcpuSockets": md.get('vcpuSockets'),
                    "vcpusPerSocket": md.get('vcpusPerSocket'),
                }
                break

        if worker_details:
            worker_configs.append(worker_details)

    # Print section
    print(f"Cluster: {cluster_name}")
    print(f"Kubernetes Version: {kubernetes_version}")
    print(f"Control Plane Endpoint: {control_plane_endpoint}")
    print(f"CNI Provider: {cni_provider}")

    print("Service LoadBalancer Address Range:")
    for range in service_lb_range:
        print(f"  Start: {range.get('start')}, End: {range.get('end')}")

    print(f"Worker Subnet: {worker_subnet}")

    print("Image Registries:")
    for cred in image_registries:
        print(f"  - Username: {cred.get('username')}, Server: {cred.get('server')}")

    print("Controlplane Configuration:")
    for key, val in cp_info.items():
        if isinstance(val, list):
            val = ", ".join(val)
        print(f"  {key}: {val}")

    print("Worker Configuration:")
    for worker in worker_configs:
        print(f"  Worker Name: {worker['workerName']}")
        for key, val in worker.items():
            if key == 'workerName':
                continue
            if isinstance(val, list):
                val = ", ".join(val)
            print(f"    {key}: {val}")



def get_machine_details():
    try:
        # Run the kubectl command to get machine details
        result = subprocess.run(
            ["kubectl", "get", "machines", "-A"],
            capture_output=True,
            text=True,
            check=True
        )
        lines = result.stdout.strip().split("\n")
        
        # Skip the header line
        machines = []
        for line in lines[1:]:
            parts = line.split()
            if len(parts) >= 4:
                namespace = parts[0]
                name = parts[1]
                cluster = parts[2]
                machines.append({
                    "namespace": namespace,
                    "name": name,
                    "cluster": cluster
                })
        
        return machines

    except subprocess.CalledProcessError as e:
        print(f"Error executing kubectl: {e}")
        return []


if __name__ == "__main__":
    clusters = get_clusters()
    for cluster in clusters:
        namespace = cluster["namespace"]
        cluster_name = cluster["clustername"]
        print(f"\nFetching YAML for cluster '{cluster_name}' in namespace '{namespace}'...")
        cluster_yaml = get_cluster_yaml(namespace, cluster_name)
        # Pass both cluster_name and cluster_yaml
        print_cluster_details(cluster_name, cluster_yaml)

