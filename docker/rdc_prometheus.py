import argparse
import json
import os
from RdcReader import RdcReader
from RdcUtil import RdcUtil
from rdc_bootstrap import *
from prometheus_client import start_http_server, Gauge, REGISTRY, PROCESS_COLLECTOR, PLATFORM_COLLECTOR

default_field_ids = [
        rdc_field_t.RDC_FI_GPU_MEMORY_USAGE,
        rdc_field_t.RDC_FI_GPU_MEMORY_TOTAL,
        rdc_field_t.RDC_FI_POWER_USAGE,
        rdc_field_t.RDC_FI_GPU_CLOCK,
        rdc_field_t.RDC_FI_GPU_UTIL,
        rdc_field_t.RDC_FI_GPU_TEMP,
        rdc_field_t.RDC_FI_PROF_ACTIVE_CYCLES,
        rdc_field_t.RDC_FI_PROF_ACTIVE_WAVES,
        rdc_field_t.RDC_FI_PROF_OCCUPANCY_PERCENT,
]

node_name = os.environ.get('NODE_NAME', '')
prefix = os.environ.get('PREFIX', '')

class PrometheusReader(RdcReader):
    def __init__(self, rdc_ip_port, field_ids, update_freq, max_keep_age, max_keep_samples,
            gpu_indexes, rdc_unauth, enable_plugin_monitoring, enable_kubernetes_integration):
        group_name = "rdc_prometheus_plugin_group"
        field_group_name = "rdc_prometheus_plugin_fieldgroup"
        if rdc_unauth:
            RdcReader.__init__(self, ip_port = rdc_ip_port, field_ids = field_ids, update_freq=update_freq,
                    max_keep_age = max_keep_age, max_keep_samples = max_keep_samples,
                    gpu_indexes = gpu_indexes, field_group_name = field_group_name, gpu_group_name = group_name, root_ca = None)
        else:
             RdcReader.__init__(self, ip_port = rdc_ip_port, field_ids = field_ids, update_freq=update_freq,
                    max_keep_age = max_keep_age, max_keep_samples = max_keep_samples,
                    gpu_indexes = gpu_indexes, field_group_name = field_group_name, gpu_group_name = group_name)

        # Supress internal metrics from prometheus_client
        if enable_plugin_monitoring == False:
            REGISTRY.unregister(PROCESS_COLLECTOR)
            REGISTRY.unregister(PLATFORM_COLLECTOR)

        self.enable_kubernetes_integration = enable_kubernetes_integration

        # Create the gauges
        self.gauges = {}
        for fid in self.field_ids:
            field_name = self.rdc_util.field_id_string(fid).lower()
            labelnames=['gpu_index']
            if self.enable_kubernetes_integration:
                labelnames.extend(['pod', 'namespace', 'container', 'node', 'device_id'])
            self.gauges[fid] = Gauge(f'{prefix}{field_name}', field_name, labelnames)

        if self.enable_kubernetes_integration:
            self.device_map = {}
            with open('/data/devices.json') as f:
                self.device_map = json.load(f)

    def process(self):
        with REGISTRY._lock:
            if self.enable_kubernetes_integration:
                for fid in self.field_ids:
                    self.gauges[fid].clear()
            RdcReader.process(self)

    def handle_field(self, gpu_index, value):
        gpu_label = gpu_index
        if value.field_id.value in self.gauges:
            if self.enable_kubernetes_integration:
                device_id = self.device_map.get(str(gpu_index))
                data = self.find_container(device_id)
                self.gauges[value.field_id.value].labels(gpu_index=gpu_label,
                                                         node=node_name,
                                                         pod=data.get('pod', ''),
                                                         namespace=data.get('namespace', ''),
                                                         container=data.get('container', ''),
                                                         device_id=device_id,
                                                         ).set(value.value.l_int)
            else:
                self.gauges[value.field_id.value].labels(gpu_label).set(value.value.l_int)

    def find_container(self, device_id):
        from grpc_client import get_pod_resources_map
        return get_pod_resources_map().get(device_id, {'pod': '', 'namespace': '', 'container': ''})

def get_field_ids(args):
    field_ids = []

    field_id_str=[]
    if args.rdc_fields:
        field_id_str=args.rdc_fields
    elif args.rdc_fields_file:
        try:
            with open(args.rdc_fields_file) as fi:
                content = fi.readlines()
            field_id_str = [x.strip() for x in content]
        except Exception as e:
             print("Fail to read " + args.rdc_fields_file + ":" + str(e))

    if len(field_id_str)> 0 :
        for f in field_id_str:
            field_id = rdc.get_field_id_from_name(str.encode(f))
            if field_id.value == rdc_field_t.RDC_FI_INVALID:
                print("Invalid field '%s' will be ignored." % (f))
            else:
                field_ids.append(field_id.value)
        return field_ids

    return default_field_ids


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='RDC Prometheus plugin.')
    parser.add_argument('--listen_port', default=5000, type=int, help='The listen port of the plugin (default: 5000)')
    parser.add_argument('--rdc_embedded', default=False, action='store_true', help='Run RDC in embedded mode (default: standalone mode)')
    parser.add_argument('--rdc_ip_port' , default='localhost:50051', help='The rdcd IP and port in standalone mode (default: localhost:50051)')
    parser.add_argument('--rdc_unauth', default=False, action='store_true', help='Set this option if the rdcd is running with unauth in standalone mode (default: false)')
    parser.add_argument('--rdc_update_freq', default=10, help='The fields update frequency in seconds (default: 10)')
    parser.add_argument('--rdc_max_keep_age', default=3600, help='The max keep age of the fields in seconds (default: 3600)')
    parser.add_argument('--rdc_max_keep_samples', default=1000, help='The max samples to keep for each field in the cache (default: 1000)')
    parser.add_argument('--rdc_fields', default=None, nargs='+', help='The list of fields name needs to be watched, for example, " --rdc_fields RDC_FI_GPU_TEMP RDC_FI_POWER_USAGE " (default: predefined fields in the plugin)')
    parser.add_argument('--rdc_fields_file', default=None, help='The list of fields name can also be read from a file with each field name in a separated line (default: None)')
    parser.add_argument('--rdc_gpu_indexes',  default=None, nargs='+', help='The list of GPUs to be watched (default: All GPUs)')
    parser.add_argument('--enable_plugin_monitoring', default=False, action='store_true', help = 'Set this option to collect process metrics of the plugin itself (default: false)')
    parser.add_argument('--enable_kubernetes_integration', default=False, action='store_true', help = 'Set this option if you want per pod gpu monitoring in kubernetes (default: false)')

    args = parser.parse_args()

    field_ids = get_field_ids(args)
    rdc_ip_port = args.rdc_ip_port
    if args.rdc_embedded:
        rdc_ip_port = None
    if args.rdc_gpu_indexes != None:
        for i in range(0, len(args.rdc_gpu_indexes)):
            args.rdc_gpu_indexes[i] = int(args.rdc_gpu_indexes[i])

    reader = PrometheusReader(rdc_ip_port, field_ids, args.rdc_update_freq*1000000,
            args.rdc_max_keep_age, args.rdc_max_keep_samples,
            args.rdc_gpu_indexes, args.rdc_unauth, args.enable_plugin_monitoring, args.enable_kubernetes_integration)
    start_http_server(args.listen_port)
    print("The RDC Prometheus plugin listen at port %d" % (args.listen_port))
    time.sleep(3)
    while True:
        reader.process()
        time.sleep(1)
