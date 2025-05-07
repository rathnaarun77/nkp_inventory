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

def get_node_names_by_pool(cluster_name: str, pool_name: str) -> list:
    try:
        result = subprocess.run(
            ["kubectl", "get", "machines", "-A", "--no-headers"],
            capture_output=True,
            text=True,
            check=True
        )
        lines = result.stdout.strip().split("\n")
        matching_nodes = []

        for line in lines:
            parts = line.split()
            if len(parts) >= 4:
                line_cluster = parts[2]
                node_name = parts[3]
                if line_cluster == cluster_name and pool_name in node_name:
                    matching_nodes.append(node_name)

        return matching_nodes

    except subprocess.CalledProcessError as e:
        print(f"Error fetching machines: {e}")
        return []

def get_kommander_config(namespace='default'):
    import yaml
    import subprocess

    try:
        result = subprocess.run(
            ["kubectl", "get", "configmap", "kommander-bootstrap-configuration", "-n", namespace, "-o", "yaml"],
            capture_output=True,
            text=True,
            check=True
        )
        configmap = yaml.safe_load(result.stdout)

        # Parse version and airgapped info
        kommander_yaml_str = configmap['data'].get('kommander-install.yaml', '')
        kommander_data = yaml.safe_load(kommander_yaml_str)
        version = kommander_data.get('version', 'N/A')
        airgapped = kommander_data.get('airgapped', {}).get('enabled', 'N/A')

        # Extract cluster name from label
        cluster_name = configmap.get('metadata', {}).get('labels', {}).get('konvoy.d2iq.io/cluster-name', 'N/A')

        return version, airgapped, cluster_name

    except subprocess.CalledProcessError as e:
        print(f"Error retrieving Kommander config: {e}")
        return 'N/A', 'N/A', 'N/A'



def print_cluster_details(cluster_name, cluster_yaml):
    topology = cluster_yaml.get('spec', {}).get('topology', {})
    control_plane = topology.get('controlPlane', {})
    worker_pools = topology.get('workers', {}).get('machineDeployments', [])

    kubernetes_version = topology.get('version', 'N/A')
    control_plane_endpoint = cluster_yaml.get('spec', {}).get('controlPlaneEndpoint', {}).get('host', 'N/A')

    # Fetch controlPlaneRef for controlplane node identification
    control_plane_ref = cluster_yaml.get('spec', {}).get('controlPlaneRef', {})
    cp_pool_name = control_plane_ref.get('name', '')

    cluster_config = topology.get('variables', [])
    cni_provider = None
    service_lb_range = []
    control_plane_details = {}
    image_registry_urls = []
    storage_container = "N/A"
    global_image_registry = "N/A"

    for var in cluster_config:
        if var.get('name') == 'clusterConfig':
            value = var.get('value', {})

            cni_provider = value.get('addons', {}).get('cni', {}).get('provider', 'N/A')
            service_lb_range = value.get('addons', {}).get('serviceLoadBalancer', {}).get('configuration', {}).get('addressRanges', [])
            control_plane_details = value.get('controlPlane', {}).get('nutanix', {}).get('machineDetails', {})
            storage_container = value.get('addons', {}).get('csi', {}).get('providers', {}).get('nutanix', {}).get(
                'storageClassConfigs', {}).get('volume', {}).get('parameters', {}).get('storageContainer', 'N/A')
            global_image_registry = value.get('globalImageRegistryMirror', {}).get('url', 'N/A')

            image_registries = value.get('imageRegistries', [])
            for reg in image_registries:
                url = reg.get('url')
                if url:
                    image_registry_urls.append(url)

    cp_info = {
        "clusterName": control_plane_details.get('cluster', {}).get('name'),
        "imageName": control_plane_details.get('image', {}).get('name'),
        "memorySize": control_plane_details.get('memorySize'),
        "project": control_plane_details.get('project', {}).get('name') if control_plane_details.get('project') else None,
        "subnets": [s.get('name') for s in control_plane_details.get('subnets', [])],
        "systemDiskSize": control_plane_details.get('systemDiskSize'),
        "vcpuSockets": control_plane_details.get('vcpuSockets'),
        "vcpusPerSocket": control_plane_details.get('vcpusPerSocket'),
        "controlPlaneRef": control_plane_ref  # include for node name lookup
    }

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

    # Print cluster metadata
    print(f"\nCluster: {cluster_name}")
    print(f"Kubernetes Version: {kubernetes_version}")
    print(f"Control Plane Endpoint: {control_plane_endpoint}")
    print(f"CNI Provider: {cni_provider}")
    print(f"Storage Container: {storage_container}")
    print(f"Global Image Registry: {global_image_registry}")

    print("Service LoadBalancer Address Range:")
    for range in service_lb_range:
        print(f"  Start: {range.get('start')}, End: {range.get('end')}")

    print("Image Registries:")
    for url in image_registry_urls:
        print(f"  - {url}")

    print("Controlplane Configuration:")
    for key, val in cp_info.items():
        if key == 'controlPlaneRef':
            continue  # skip printing controlPlaneRef itself
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

    # Fetch and print matching machine node names
    print("Controlplane Nodes:")
    cp_nodes = get_node_names_by_pool(cluster_name, cp_pool_name)
    for node in cp_nodes:
        print(f"  - {node}")

    print("Worker Nodes:")
    for worker in worker_configs:
        worker_nodes = get_node_names_by_pool(cluster_name, worker["workerName"])
        print(f"  Worker Pool: {worker['workerName']}")
        for node in worker_nodes:
            print(f"    - {node}")

def save_html_output(html_content, filename="cluster_details.html"):
    with open(filename, "w") as file:
        file.write(html_content)
        
def get_nkp_dkp_level():
    try:
        result = subprocess.run(
            ['kubectl', 'get', 'license', '-n', 'kommander', '-o', 'yaml'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            text=True
        )

        license_data = yaml.safe_load(result.stdout)
        items = license_data.get('items', [])

        if not items:
            return None

        return items[0].get('status', {}).get('dkpLevel')

    except subprocess.CalledProcessError as e:
        print("Error fetching license:", e.stderr)
        return None
    except yaml.YAMLError as ye:
        print("Failed to parse YAML:", str(ye))
        return None




if __name__ == "__main__":
    version, airgapped, kommander_cluster_name = get_kommander_config()
    print(f"\nKommander Cluster Name: {kommander_cluster_name}")
    print(f"NKP Version: {version}")
    print(f"Airgapped: {airgapped}\n")
    
    # Fetching the NKP license tier
    dkp_level = get_nkp_dkp_level()
    print(f"NKP Licence Tier: {dkp_level}")

    # Get the list of clusters
    clusters = get_clusters()

    # First, fetch and print the Kommander cluster details
    kommander_cluster = next((cluster for cluster in clusters if cluster['clustername'] == kommander_cluster_name), None)
    if kommander_cluster:
        namespace = kommander_cluster["namespace"]
        cluster_name = kommander_cluster["clustername"]
        print(f"\nFetching YAML for Kommander cluster '{cluster_name}' in namespace '{namespace}'...")
        cluster_yaml = get_cluster_yaml(namespace, cluster_name)
        print_cluster_details(cluster_name, cluster_yaml)

    # Now, process the remaining clusters (excluding Kommander)
    for cluster in clusters:
        if cluster['clustername'] != kommander_cluster_name:
            namespace = cluster["namespace"]
            cluster_name = cluster["clustername"]
            print(f"\nFetching YAML for cluster '{cluster_name}' in namespace '{namespace}'...")
            cluster_yaml = get_cluster_yaml(namespace, cluster_name)
            print_cluster_details(cluster_name, cluster_yaml)