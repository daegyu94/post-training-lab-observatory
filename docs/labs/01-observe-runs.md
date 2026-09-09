# Observe and Compare Post-Training Runs

## Objective and Status

Status: `runnable` (synthetic replay). SFT와 agentic RL의 workload metric을 구분하고, resource 관측에서 확인한 가설을 작은 결과 기록으로 남깁니다. 실제 학습이나 GPU 성능 측정은 수행하지 않습니다.

## Prerequisites and Start

Python 3, Git과 최신 브라우저가 필요합니다. GPU, model weight와 dataset 다운로드는 필요하지 않습니다. 저장소를 clone한 뒤 로컬 HTTP 서버를 실행합니다.

```bash
git clone https://github.com/daegyu94/post-training-lab-observatory.git
cd post-training-lab-observatory
python -m http.server 8000 --bind 127.0.0.1
```

브라우저에서 `http://127.0.0.1:8000/`을 엽니다. 파일을 직접 여는 `file://` 방식은 JSON fetch를 지원하지 않을 수 있으므로 HTTP 서버를 사용합니다.

## Exercise

1. 첫 화면의 Run history에서 저장된 이력을 살펴본 뒤, **Demo playground**를 엽니다. Run selector에서 `Atlas · baseline` (`pt-1041`)을 선택합니다. Overview의 throughput과 주요 phase, Data paths의 전송 경로, Storage의 checkpoint 지표를 기록합니다.
2. `Atlas · communication study` (`pt-1042`)로 전환하고 같은 지표를 비교합니다. 어떤 phase와 resource가 병목 가설을 뒷받침하는지, 실제 측정이라면 추가로 어떤 counter나 trace가 필요한지 적습니다. 합성 시나리오 간 차이를 실제 성능 개선이나 인과관계로 해석하지 않습니다.
3. `Orion · agentic RL` (`rl-2051`)의 Workload를 확인합니다. SFT 화면과 다른 rollout·agent 지표를 찾아 기록합니다. 이 화면은 RL training command를 실행하지 않습니다.
4. API explorer에서 선택한 run의 `summary.json`과 `data-movement.json`을 요청합니다. HTTP 응답과 화면 값의 연결을 확인합니다.
5. `Export JSON`으로 snapshot을 저장합니다. `Live demo`를 켰다면 합성 stream 재생임을 기록하고, 원본 fixture와 replay 중 화면을 구분합니다.

## Expected Evidence

run ID, 비교한 metric·단위·값, 병목 가설, 추가 검증에 필요한 실제 측정과 `synthetic` 표시를 포함한 짧은 Markdown note를 남깁니다. API 요청이 성공하고 run을 바꿀 때 화면이 갱신되어야 합니다. Export 파일은 로컬 결과로 보관합니다.

JSON 요청이 실패하면 저장소 루트에서 서버를 실행했는지, URL의 port와 `api/runs.json` 경로가 맞는지 확인합니다. 이 실습의 완료는 데이터 탐색과 evidence 작성이며 실제 모델 품질·성능 검증이 아닙니다.

## Cleanup and Next Steps

서버 terminal에서 `Ctrl-C`로 종료합니다. 다운로드한 snapshot은 필요할 때만 보관하고 Git에 추가하지 않습니다. 실제 resource 수집은 [profiling 실습](https://github.com/daegyu94/post-training-lab/tree/profiling), 새 합성 run 추가는 [확장 가이드](../adding-scenarios.md)로 이어집니다.

## Spark Cluster: Publish Real Measurements to Observatory

합성 replay를 마친 뒤 `spark1`, `spark2`의 실제 host telemetry를 같은 Observatory 사이트의 **Run history**에서 확인할 수 있습니다.
두 노드는 독립적으로 수집하며, 이 단계 자체가 multi-node training을 실행하지는 않습니다.
[GitHub Pages는 정적 호스팅](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages)이므로 agent의 HTTP POST를 직접 받을 수 없습니다.
Controller의 수집 API가 push를 받고, 선택한 run의 JSON snapshot을 repository에 게시하면 Pages가 표시합니다.

```text
spark1 /proc --POST via SSH--+
                            +--> controller collector --> SQLite
spark2 /proc --POST via SSH--+                              |
                                                  selected run export
                                                           |
                                            api/telemetry.json + Pages
                                                           |
                                              Spark measured telemetry
```

### 1. Start the Collector on Controller

Observatory 저장소 루트에서 실행합니다.
Python standard library만 필요하고 controller에서 LLM 연산은 실행하지 않습니다.

```bash
mkdir -p artifacts
umask 077
python3 -c 'import secrets; print(secrets.token_hex(24))' > artifacts/token
export OBSERVATORY_TOKEN="$(cat artifacts/token)"
python3 telemetry/server.py --database artifacts/spark.sqlite3
```

API는 기본적으로 `127.0.0.1:8001`에 바인딩됩니다.
Token과 SQLite는 Git에 포함하지 않습니다.
GET과 POST 모두 bearer token이 필요하고, 최대 10,000개 sample을 보존하며 조회는 최근 1,000개를 반환합니다.
장기 보존·다중 사용자 서비스는 기존 Prometheus/Grafana 또는 별도 운영 수집 계층을 사용합니다.

### 2. Push from Both Spark Nodes

별도 controller terminal에서 Observatory 루트로 이동한 뒤 아래 명령을 실행합니다.
SSH reverse tunnel은 각 Spark 노드의 loopback port를 controller collector로 전달하므로 외부에 수집 port를 열 필요가 없습니다.
Token은 SSH 표준 입력으로 전달하며 명령 인자나 repository에 기록하지 않습니다.

```bash
run_id="<training-output-directory-name>"
for node in spark1 spark2; do
  scp telemetry/agent.py "spark@$node:/tmp/observatory-agent.py"
done
pids=()
for node in spark1 spark2; do
  { cat artifacts/token; printf '\n'; } | \
    ssh -o ExitOnForwardFailure=yes -R 18001:127.0.0.1:8001 "spark@$node" \
      "read -r OBSERVATORY_TOKEN; export OBSERVATORY_TOKEN; python3 /tmp/observatory-agent.py --endpoint http://127.0.0.1:18001 --run-id '$run_id' --framework-metrics-dir '<backend-output-root>/$run_id/framework-metrics' --samples 30 --interval 2" \
      > "artifacts/$node.jsonl" &
  pids+=("$!")
done
status=0
for pid in "${pids[@]}"; do
  wait "$pid" || status=1
done
test "$status" -eq 0
```

Agent는 기본 30회 수집 후 종료하며 SSH tunnel도 닫힙니다.
각 `artifacts/spark*.jsonl`에 30개 성공 sample이 있는지 확인합니다.
전송 실패는 agent의 nonzero exit 및 stderr로 나타나며 자동 재시도하지 않습니다.
Port 18001이 이미 사용 중이면 다른 port로 바꾸고 endpoint도 함께 수정합니다.
공유 경로에서 직접 실행하는 경우 controller의 `/home/daegyu/shared/<relative-path>`는 Spark에서 `/home/spark/shared/<relative-path>`로 바꿉니다.

Collector의 `http://127.0.0.1:8001/`을 열고 **Local collector**를 선택한 뒤 token을 입력하고 Refresh합니다.
원격 브라우저에서는 controller로 SSH local forwarding을 연결해 같은 URL을 사용합니다.
Token은 브라우저 저장소에 보존하지 않습니다.

### 3. Export and Publish the Selected Run

```bash
python3 -m telemetry.export --database artifacts/spark.sqlite3 --run-id "$run_id" --archive-dir api/history
python3 -m http.server 8000 --bind 127.0.0.1
```

`http://127.0.0.1:8000/telemetry.html`에서 **Published snapshot**을 확인합니다.
JSON은 선택한 run ID, node 이름, 수집 시각과 허용된 host metric만 포함합니다.
공개할 node 이름은 agent의 `--node`로 지정할 수 있습니다.
IP, token, 환경 변수, model 입력과 training trace는 export하지 않습니다.

변경 내용을 검토한 뒤 `api/telemetry.json`, `api/history/`와 구현 파일을 PR로 올려 main에 반영합니다.
기존 Pages workflow가 배포한 후 [Observatory](https://daegyu94.github.io/post-training-lab-observatory/)의 **Run history**에서 보관된 결과를 확인합니다.
후속 실습에서는 새 run ID로 export하고 `api/history/`의 새 archive와 index를 함께 게시합니다.
기존 기록을 덮어쓰지 않는 저장 방식은 [Run history 가이드](../run-history.md)를 참고하세요.
Snapshot은 마지막 게시 시점의 결과이며 Refresh로 새 측정을 생성하지 않습니다.
공개 사이트에 collector token을 넣거나 private HTTP endpoint를 직접 연결하지 않습니다.

실제 두 노드 전송 검증 결과는 [검증 기록](spark-telemetry-evidence.md)을 참고하세요.

### Interpretation and Evidence

- CPU는 두 `/proc/stat` sample 차이로 계산한 노드 전체 busy 비율이며 idle과 iowait를 제외합니다.
- Memory는 `MemTotal - MemAvailable`을 GiB로 변환합니다.
- NIC는 loopback과 일부 container interface를 제외한 공통 interface counter 차이를 decimal Gbps로 변환합니다.
  Bridge, bond와 physical interface가 겹치는 구성에서는 중복 집계 가능성이 있으므로 NIC별 분석은 Node Exporter를 사용합니다.
- 수집 시각은 controller 수신 시각이고 interval은 agent의 monotonic clock으로 측정합니다.
  30초 이상 지난 sample에는 stale을 표시합니다.
- 다른 프로세스와 SSH/NFS traffic도 포함됩니다.
  이 수치를 training throughput, GPU 사용률, NCCL bandwidth 또는 workload 단독 사용량으로 해석하지 않습니다.

실습 evidence에는 run ID, 두 노드의 sample 수, CPU 범위, 수신 시간 구간, JSON 경로와 Pages 배포 URL을 기록합니다.
실제 LLM 실습과 연결할 때에는 Spark에서 workload를 별도로 실행하면서 같은 run ID와 시간 구간으로 수집합니다.
`post-training-lab` runner로 TRL 또는 Megatron을 같은 `run_id`로 실행하면 agent가 `--framework-metrics-dir`의 rank별 최신 sample을 함께 전송합니다.
화면은 2초마다 collector를 조회하며 loss, tokens/s, step time과 Megatron rank timer를 표시합니다.
Framework metric 파일이 아직 없으면 host metric만 전송합니다.

### Cleanup

수집 서버는 `Ctrl-C`로 종료합니다.
Agent 종료 후 SSH tunnel이 제거되었는지 확인하고, 원격 `/tmp/observatory-agent.py`와 controller의 `artifacts/token`, SQLite는 필요에 따라 삭제합니다.
공개 snapshot을 제거하려면 `api/telemetry.json`을 삭제하고 Pages를 재배포합니다.

### Spark GB10 Unified Memory

DGX Spark는 CPU와 GPU가 128 GB LPDDR5x 물리 메모리를 공유하는 UMA 시스템입니다.
CPU RAM과 별도의 128 GB VRAM이 각각 존재하는 구성이 아닙니다.
두 Spark 노드를 연결해도 하나의 자동 공유 address space가 생기지는 않으며 workload의 분산·sharding 지원이 필요합니다.
사양은 [NVIDIA hardware overview](https://docs.nvidia.com/dgx/dgx-spark/hardware.html)를 참고하세요.

따라서 GPU workload의 allocation이 시스템 메모리 여유에 영향을 줄 수 있습니다.
다만 `free -h`의 사용량 증가만으로 원인을 GPU라고 확정할 수는 없습니다.
OS, 다른 프로세스, 파일 cache와 framework가 유지하는 allocation도 함께 고려합니다.
이 화면은 시스템 `MemTotal - MemAvailable`, `MemAvailable`, `SwapTotal - SwapFree`를 각각 표시하고 GPU allocation을 더하지 않습니다.
`free` 열 하나보다 available, swap 변화와 workload의 allocation 통계를 같은 시간 구간에 비교하세요.
Swap 사용량 자체는 현재 swap I/O가 발생한다는 뜻이 아니므로 `vmstat 1`의 `si/so` 또는 별도 swap I/O counter로 확인합니다.

NVIDIA는 iGPU에서 `nvidia-smi` framebuffer memory의 `Not Supported`가 정상이라고 설명합니다.
이 값을 0으로 바꾸거나 dedicated GPU의 VRAM capacity 패널에 넣지 않습니다.
또한 `cudaMemGetInfo`는 OS가 회수 가능한 메모리를 모두 반영하지 않으므로 시스템 available 값과 다를 수 있습니다.
관련 지침은 [NVIDIA UMA memory reporting](https://docs.nvidia.com/dgx/dgx-spark/known-issues.html#guidance-for-reporting-memory-resources-with-unified-memory-architecture)을 참고하세요.

PyTorch의 allocated/reserved 통계를 추가할 때에는 해당 process의 allocator 범위라는 label을 유지합니다.
이 값은 시스템 전체 사용량을 대체하지 않으며 별도 CPU tensor와 GPU tensor copy가 자동으로 하나의 allocation이 된다고 가정하지 않습니다.
OS와 workload를 위한 headroom을 남기고, swap을 고속 GPU memory capacity로 계산하지 않습니다.
측정을 맞추기 위해 cache drop, swap 해제 또는 다른 workload 종료를 수행하지 않습니다.
