import grpc
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

# Load generated gRPC modules
import api_pb2
import api_pb2_grpc


def get_pod_resources_map():
    try:
        kubelet_address = "/var/lib/kubelet/pod-resources/kubelet.sock"
        channel_address = f"unix://{kubelet_address}"
        channel = grpc.insecure_channel(channel_address)

        # Create gRPC client
        stub = api_pb2_grpc.PodResourcesListerStub(channel)

        # Call 'List' method to obtain pod resources
        response = stub.List(api_pb2.ListPodResourcesRequest())

        # Handle response
        if not response.pod_resources:
            return {}

        device_to_pod = {}
        for pod_resource in response.pod_resources:
            for container in pod_resource.containers:
                if not container.devices:
                    continue
                for device in container.devices:
                    if device.resource_name == 'amd.com/gpu' and len(device.device_ids):
                        device_id = device.device_ids[0]
                        device_to_pod[device_id] = {
                            'namespace': pod_resource.namespace,
                            'pod': pod_resource.name,
                            'container': container.name,
                        }
        return device_to_pod

    except grpc.RpcError as e:
        print(f"\ngRPC connection error: {e.code().name} - {e.details()}")
        print("Please check the following:")
        print(f"  1. Is the Kubelet running?")
        print(f"  2. Is the Kubelet's Pod resource gRPC service enabled?")
        print(f"  3. Is the Kubelet address '{kubelet_address}' correct?")
        print(f"  4. If using UDS, is the file '{kubelet_address}' present and readable?")
        print(f"  5. If using TCP, is the port correct, and does the firewall allow connections?")
        print(f"  6. If using TCP, Kubelet might require a TLS certificate, but this code uses insecure_channel.")
        return {}
    except FileNotFoundError:
        print(f"\nError: Unix Domain Socket file '{kubelet_address}' does not exist.")
        return {}
    except Exception as e:
        print(f"\nAn unknown error occurred: {e}")
        return {}


if __name__ == "__main__":
    print(get_pod_resources_map())

