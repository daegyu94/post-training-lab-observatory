# SFT Lab Observatory

대규모 LLM post-training의 멀티노드·멀티 GPU resource profiling을 설명하기 위한 공개 정적 대시보드 데모입니다.

- 모든 수치, 이벤트, 클러스터 구성은 **합성 시나리오**이며 실제 benchmark나 사내 데이터가 아닙니다.
- GitHub Pages 정적 사이트이므로 GPU, Prometheus, Grafana, run database 또는 인증 시스템에 연결하지 않습니다.
- 화면은 실험 비교, node/GPU map, rank 진단, 운영 서비스 확장 경계를 보여주는 PoC입니다.

실습과 exporter, Prometheus/Grafana, Megatron/verl profiling 구성은 [SFT Lab의 profiling 브랜치](https://github.com/daegyu94/sft-lab/tree/profiling)에서 제공합니다.

## 운영 서비스로 확장

실제 서비스에서는 브라우저가 Prometheus나 credential에 직접 접근하지 않도록, 인증된 server API와 run registry를 대시보드 앞에 둡니다. 이 데모는 그 UI 계약을 검증하기 위한 공개 화면입니다.


## Mock API

화면의 `Mock API explorer`는 아래 정적 JSON endpoint를 브라우저의 `fetch`로 직접 호출합니다.

- `GET /api/runs.json`: run registry
- `GET /api/runs/<run_id>/summary.json`: training, CPU, memory, GPU, network, storage, checkpoint summary
- `GET /api/runs/<run_id>/interconnect.json`: node↔node RoCE/RDMA와 GPU↔GPU NVLink/PCIe matrix
- `GET /api/runs/<run_id>/storage.json`: device throughput, IOPS, latency, queue depth, checkpoint path (현재 `pt-1042`, `pt-1041`, `pt-1038` 비교 run 제공)

현재 endpoint는 GitHub Pages에서 제공하는 합성 JSON입니다. 실제 서비스로 전환할 때는 같은 응답 계약을 인증된 Next.js/Go API가 제공하고, API 서버가 Prometheus·DCGM·Node Exporter·Ray·run registry를 조회하도록 바꾸면 됩니다.

## Covered Signals

`profiling` 브랜치의 metric vocabulary를 기준으로 다음 화면을 포함합니다.

- training throughput, step/collective time, GPU utilization·memory
- host CPU·memory pressure, network/RDMA throughput
- node↔node와 GPU↔GPU interconnect utilization·throughput·latency
- storage read/write, IOPS, latency, queue depth
- checkpoint size, save/load duration, checkpoint throughput
