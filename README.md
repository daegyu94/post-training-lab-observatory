# SFT Lab Observatory

대규모 LLM post-training의 멀티노드·멀티 GPU 병목을 탐색하는 공개 dashboard PoC입니다.

- [Live dashboard](https://daegyu94.github.io/sft-lab-observatory/)
- [Profiling labs and metric vocabulary](https://github.com/daegyu94/sft-lab/tree/profiling)
- [Metric contract](https://github.com/daegyu94/sft-lab/blob/profiling/docs/metric-schema.md)

모든 수치와 이벤트는 합성 데이터입니다. 실제 benchmark 결과나 사내 시스템 연결을 포함하지 않습니다.

## Dashboard

| View | 확인할 수 있는 내용 |
| --- | --- |
| Overview | throughput, step phase, CPU, memory, GPU, NIC와 주요 진단 |
| Cluster | node/GPU allocation, GPU health, RDMA·NVLink matrix |
| Data paths | storage→host→GPU→remote GPU의 전송량·대역폭·기준 대비 활용률, phase timing과 peak memory |
| Storage | device throughput, IOPS, latency, queue depth, cache와 checkpoint |
| Workload | SFT efficiency 또는 verl/Ray 기반 agentic RL metric |
| API explorer | 정적 JSON endpoint의 실제 HTTP 요청과 응답 |

Run selector에서 Megatron SFT, FSDP, agentic RL 시나리오를 전환할 수 있습니다. `Live demo`는 선택한 run의 합성 throughput stream을 재생하고, `Export JSON`은 현재 화면의 전체 profiling snapshot을 내려받습니다.

## Mock API

GitHub Pages가 아래 JSON endpoint를 제공하며 dashboard는 브라우저의 `fetch`로 이를 직접 호출합니다.

| Endpoint | Contract |
| --- | --- |
| `GET /api/runs.json` | run registry |
| `GET /api/runs/<run_id>/summary.json` | training, workload와 aggregate resource metric |
| `GET /api/runs/<run_id>/resources.json` | per-node CPU/memory/NIC와 per-GPU health |
| `GET /api/runs/<run_id>/interconnect.json` | node↔node 및 GPU↔GPU topology matrix |
| `GET /api/runs/<run_id>/data-movement.json` | phase-aware storage·host·GPU 전송 경로와 peak memory |
| `GET /api/runs/<run_id>/storage.json` | device I/O, cache와 checkpoint metric |

현재 run은 `rl-2051`, `pt-1042`, `pt-1041`, `pt-1038`입니다.

## Metric Sources

Dashboard vocabulary는 `sft-lab`의 [`profiling/config/metrics.json`](https://github.com/daegyu94/sft-lab/blob/profiling/config/metrics.json)과 [`metrics.schema.json`](https://github.com/daegyu94/sft-lab/blob/profiling/config/metrics.schema.json)을 기준으로 합니다.

- training: framework adapter, timer, selected trace
- rollout/agent: verl, inference engine, OpenTelemetry
- orchestration: Ray metrics
- GPU: DCGM Exporter
- host/network/storage: Node Exporter와 fio
- container: cAdvisor
- data movement: phase marker, framework timer, NCCL/RDMA counter와 selected trace
- checkpoint: framework adapter와 timer

실 서비스에서는 이 응답 계약을 유지한 채 JSON fixture를 인증된 API로 교체합니다. 브라우저가 Prometheus credential을 갖지 않도록 API 서버가 query allowlist, timeout, RBAC와 audit log를 적용하는 구조가 적합합니다.
