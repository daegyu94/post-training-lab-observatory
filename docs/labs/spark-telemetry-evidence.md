# Spark Host Telemetry Verification

2026-09-08에 두 Spark 노드에서 각각 2초 간격으로 10개 sample을 수집했습니다.
Run ID는 `spark-host-20260908`이며 결과는 [`api/telemetry.json`](../../api/telemetry.json)에 있습니다.
이 검증은 기존 노드 활동을 관측했으며 training 또는 GPU benchmark를 새로 실행하지 않았습니다.

| Node | Samples | CPU range | Last system used | Last available | Last swap used |
| --- | --- | --- | --- | --- | --- |
| spark1 | 10 | 4.998–6.500% | 65.400 GiB | 54.294 GiB | 8.650 GiB |
| spark2 | 10 | 0.150–0.518% | 4.102 GiB | 115.590 GiB | 0.162 GiB |

마지막 수신 시각은 `2026-09-08T07:06:39Z`입니다.
두 노드 모두 `NVIDIA GB10`으로 확인되었고 `nvidia-smi`의 `memory.total`, `memory.used`는 `[N/A]`였습니다.
사전 점검의 spark1 available 약 4.7 GiB와 이후 snapshot 값은 서로 다른 시점의 관측입니다.
변화를 특정 프로세스나 GPU allocation에 귀속하는 분석은 수행하지 않았습니다.

Agent → SSH reverse tunnel → controller API → SQLite → 선택 run export 경로를 실제 검증했습니다.
Unit/integration test는 counter 단위 변환, 인증 실패, NaN 거부, 조회, export와 DB 재연결 후 보존을 확인했습니다.
JavaScript syntax 검사와 headless Chrome에서 두 노드 행 및 두 CPU history 렌더링 확인도 통과했습니다.
GitHub Pages에서의 공개 결과는 변경사항이 main에 반영되고 배포가 완료된 뒤 확인해야 합니다.
