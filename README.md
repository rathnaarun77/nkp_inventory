# NKP Basic Inventory

## Overview
This is a python script which can be run to collect the basic details of the NKP cluster, for completing the as-built guide.


## Usage

### Steps:
1. Set the current context with the KUBECONFIG of the management cluster
    ```sh
    export KUBECONFFIG=<nkp-mgmt.conf>
    ```

2. Run the python script 
    ```sh
    python nkp-as-built.py
    ```

3. After successful completion of the script, the output will be available in te same directory - cluster_details.html


Disclaimer:

The views and opinions expressed in this repository are my own and do not necessarily reflect those of any company or organization. The information provided is based on personal experience and research. It is presented as-is without any warranties. For official guidance, please refer to the official documentation or support channels.

## License
MIT
