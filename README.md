# Post-Training Lab Observatory

LLM post-training의 SFT와 agentic RL workload에서 멀티노드·멀티 GPU 병목을 탐색하는 공개 dashboard PoC이자 관측 실습 저장소입니다. 학습 실행과 공통 contract는 [Post-Training Lab](https://github.com/daegyu94/post-training-lab)이 관리합니다.

- [Live dashboard](https://daegyu94.github.io/post-training-lab-observatory/)
- [Profiling labs and metric vocabulary](https://github.com/daegyu94/post-training-lab/tree/profiling)
- [Metric contract](https://github.com/daegyu94/post-training-lab/blob/profiling/docs/metric-schema.md)

기본 시나리오의 수치와 이벤트는 합성 데이터입니다.
Run history는 합성 학습 예제와 별도 수집한 실제 host 관측 기록을 함께 보관하며 데이터 출처를 구분합니다.
수집·게시 절차는 [Spark 실습 가이드](docs/labs/01-observe-runs.md#spark-cluster-publish-real-measurements-to-observatory)를 참고하세요.

## Start a Lab

Python 3와 브라우저만 있으면 [첫 관측 실습](docs/labs/01-observe-runs.md)을 실행할 수 있습니다. GPU나 training framework 설치는 필요하지 않습니다. SFT run 비교, RL metric 탐색과 snapshot export를 합성 데이터로 연습합니다.

새 관측 시나리오는 [확장 가이드](docs/adding-scenarios.md)에 따라 registry와 fixture를 함께 추가합니다. DPO 등 새로운 학습 방식은 대응 metric과 화면을 구현하기 전까지 지원되는 것으로 표시하지 않습니다.

## Run History

첫 화면에서 실행 이력을 검색·필터링하고, run별 설정·타임라인·리소스와 실행 간 비교를 확인합니다.
완료된 기록은 run별 JSON archive로 보관하므로 Pages 조회에는 DB가 필요하지 않습니다.
기존 SQLite collector에서 관측값을 export하거나 profiling report를 archive에 추가하는 절차는 [Run history 가이드](docs/run-history.md)를 참고하세요.

## Dashboard

| View | 확인할 수 있는 내용 |
| --- | --- |
| Overview | throughput, step phase, CPU, memory, GPU, NIC와 주요 진단 |
| Cluster | node/GPU allocation, GPU health, RDMA·NVLink matrix |
| Data paths | storage→host→GPU→remote GPU의 전송량·대역폭·기준 대비 활용률, phase timing과 peak memory |
| Storage | device throughput, IOPS, latency, queue depth, cache와 checkpoint |
| Workload | SFT efficiency 또는 verl/Ray 기반 agentic RL metric |
| API explorer | 정적 JSON endpoint의 실제 HTTP 요청과 응답 |

Run selector에서 Megatron SFT, FSDP, agentic RL 시나리오를 전환할 수 있습니다.
`Live demo`는 1초마다 합성 1분을 재생하며 throughput, step timing, CPU/GPU, memory, network, storage, data path와 workload 지표를 함께 갱신합니다.
설정값과 완료된 작업의 기록·누적 counter는 유지하며, 실측 데이터가 아닙니다.
`Pause demo`는 마지막 샘플을 유지하고, run 전환은 해당 fixture로 초기화합니다.
`WINDOW`는 throughput 차트에 표시할 합성 시간 구간을 선택합니다.
`Export JSON`은 현재 화면의 profiling snapshot과 데모 샘플 시각을 내려받습니다.

`THEME`에서 System, Light, Dark를 선택할 수 있습니다.
기본값은 시스템 설정을 따르며, 선택은 브라우저에 저장되어 대시보드와 실측 telemetry 페이지에 공통으로 적용됩니다.

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
| `GET/POST /api/framework-metrics` | local collector의 TRL·Megatron loss, tokens/s와 rank timer |

현재 run은 `rl-2051`, `pt-1042`, `pt-1041`, `pt-1038`입니다.

## Metric Sources

Dashboard vocabulary는 `post-training-lab`의 [`profiling/config/metrics.json`](https://github.com/daegyu94/post-training-lab/blob/profiling/config/metrics.json)과 [`metrics.schema.json`](https://github.com/daegyu94/post-training-lab/blob/profiling/config/metrics.schema.json)을 기준으로 합니다.

- training: framework adapter, timer, selected trace
- rollout/agent: verl, inference engine, OpenTelemetry
- orchestration: Ray metrics
- GPU: DCGM Exporter
- host/network/storage: Node Exporter와 fio
- container: cAdvisor
- data movement: phase marker, framework timer, NCCL/RDMA counter와 selected trace
- checkpoint: framework adapter와 timer

실 서비스에서는 이 응답 계약을 유지한 채 JSON fixture를 인증된 API로 교체합니다. 브라우저가 Prometheus credential을 갖지 않도록 API 서버가 query allowlist, timeout, RBAC와 audit log를 적용하는 구조가 적합합니다.

## Repository Migration

기존 clone에서는 `git remote set-url origin git@github.com:daegyu94/post-training-lab-observatory.git`로 remote를 갱신하세요. 저장소는 `sft-lab-observatory`에서 이름을 변경했으며, GitHub Pages의 기존 주소는 자동 리디렉션되지 않습니다. 위의 새 Live dashboard 링크를 사용하세요.
