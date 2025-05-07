import subprocess
import yaml
from datetime import datetime

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

def generate_html_table(cluster_name, cluster_yaml):
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

    html_content = f"<h2>Cluster: {cluster_name}</h2>"
    html_content += f"<table border='1'><tr><th>Kubernetes Version</th><td>{kubernetes_version}</td></tr>"
    html_content += f"<tr><th>Control Plane Endpoint</th><td>{control_plane_endpoint}</td></tr>"
    html_content += f"<tr><th>CNI Provider</th><td>{cni_provider}</td></tr>"
    html_content += f"<tr><th>Storage Container</th><td>{storage_container}</td></tr>"
    html_content += f"<tr><th>Global Image Registry</th><td>{global_image_registry}</td></tr>"

    html_content += "<tr><th>Service LoadBalancer Address Range</th><td>"
    for range in service_lb_range:
        html_content += f"Start: {range.get('start')}, End: {range.get('end')}<br>"
    html_content += "</td></tr>"

    html_content += "<tr><th>Image Registries</th><td>"
    for url in image_registry_urls:
        html_content += f"- {url}<br>"
    html_content += "</td></tr>"

    html_content += "<tr><th>Controlplane Configuration</th><td>"
    for key, val in cp_info.items():
        if isinstance(val, list):
            val = ", ".join(val)
        html_content += f"<b>{key}</b>: {val}<br>"
    html_content += "</td></tr>"

    html_content += "<tr><th>Worker Configuration</th><td>"
    for worker in worker_configs:
        html_content += f"<b>Worker Name:</b> {worker['workerName']}<br>"
        for key, val in worker.items():
            if key == 'workerName':
                continue
            if isinstance(val, list):
                val = ", ".join(val)
            html_content += f"<b>{key}</b>: {val}<br>"
    html_content += "</td></tr>"

    # Controlplane and Worker nodes
    html_content += "<tr><th>Controlplane Nodes</th><td>"
    cp_nodes = get_node_names_by_pool(cluster_name, cp_pool_name)
    for node in cp_nodes:
        html_content += f"- {node}<br>"
    html_content += "</td></tr>"

    html_content += "<tr><th>Worker Nodes</th><td>"
    for worker in worker_configs:
        worker_nodes = get_node_names_by_pool(cluster_name, worker["workerName"])
        html_content += f"<b>Worker Pool:</b> {worker['workerName']}<br>"
        for node in worker_nodes:
            html_content += f"- {node}<br>"
    html_content += "</td></tr></table><br>"

    return html_content

def save_html_output(html_content, filename="cluster_details.html"):
    with open(filename, "w") as file:
        file.write(f"<html><head><title>Cluster Details</title></head><body>{html_content}</body></html>")

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
    # Fetching configuration for Kommander cluster
    version, airgapped, kommander_cluster_name = get_kommander_config()
    print(f"\nKommander Cluster Name: {kommander_cluster_name}")
    print(f"NKP Version: {version}")
    print(f"Airgapped: {airgapped}\n")

    # Fetching the NKP license tier
    dkp_level = get_nkp_dkp_level()
    print(f"NKP Licence Tier: {dkp_level}")

    # Get the list of clusters
    clusters = get_clusters()

    html_output = ""

    # Start the HTML output with the title and basic information
    html_output += "<html><head><title>NKP Basic Inventory</title></head><body>"
    html_output += "<h1>NKP Basic Inventory</h1>"
    
    # Add Kommander cluster details at the top
    html_output += "<h2>Kommander Cluster Details</h2>"
    html_output += "<table border='1'>"
    html_output += f"<tr><th>Kommander Cluster Name</th><td>{kommander_cluster_name}</td></tr>"
    html_output += f"<tr><th>NKP Version</th><td>{version}</td></tr>"
    html_output += f"<tr><th>Airgapped</th><td>{airgapped}</td></tr>"
    html_output += "</table><br>"

    # Now, fetch and add the details for the Kommander cluster (first cluster)
    kommander_cluster = next((cluster for cluster in clusters if cluster['clustername'] == kommander_cluster_name), None)
    if kommander_cluster:
        namespace = kommander_cluster["namespace"]
        cluster_name = kommander_cluster["clustername"]
        print(f"\nFetching details for Kommander cluster '{cluster_name}' in namespace '{namespace}'...")
        cluster_yaml = get_cluster_yaml(namespace, cluster_name)
        html_output += generate_html_table(cluster_name, cluster_yaml)

    # Process the remaining clusters (excluding Kommander)
    for cluster in clusters:
        if cluster['clustername'] != kommander_cluster_name:
            namespace = cluster["namespace"]
            cluster_name = cluster["clustername"]
            print(f"\nFetching details for cluster '{cluster_name}' in namespace '{namespace}'...")
            cluster_yaml = get_cluster_yaml(namespace, cluster_name)
            html_output += generate_html_table(cluster_name, cluster_yaml)

    # End the HTML output
    html_output += "</body></html>"

    # Save the HTML output
    save_html_output(html_output)
