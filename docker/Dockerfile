FROM rocm/dev-ubuntu-24.04:6.4.1

ENV SHELL=/bin/bash \
    TERM=xterm \
    TZ=UTC \
    DEBIAN_FRONTEND=noninteractive \
    LC_ALL=C.UTF-8 \
    LANG=C.UTF-8

RUN sed -i 's/archive.ubuntu.com/tw.archive.ubuntu.com/g' /etc/apt/sources.list.d/ubuntu.sources && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
    curl \
    rdc \
    netcat-traditional \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

COPY gen_device_map.py /opt/rocm/libexec/rocm_smi/
COPY grpc_client.py rdc_prometheus.py /opt/rocm/libexec/rdc/python_binding/

RUN curl -L -o /opt/rocm/libexec/rdc/python_binding/api.proto \
    "https://raw.githubusercontent.com/kubernetes/kubelet/refs/heads/master/pkg/apis/podresources/v1/api.proto" && \
    mkdir -p /opt/rocm/libexec/rdc/python_binding/github.com/gogo/protobuf/gogoproto/ && \
    curl -L -o /opt/rocm/libexec/rdc/python_binding/github.com/gogo/protobuf/gogoproto/gogo.proto \
    "https://raw.githubusercontent.com/gogo/protobuf/refs/heads/master/gogoproto/gogo.proto"

RUN pip install --break-system-packages \
    prometheus-client \
    grpcio \
    grpcio-tools \
    && cd /opt/rocm/libexec/rdc/python_binding \
    && python3 -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. api.proto github.com/gogo/protobuf/gogoproto/gogo.proto
