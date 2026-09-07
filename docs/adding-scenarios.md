# Add an Observatory Scenario

Observatory는 정적 JSON을 사용하는 합성 데이터 dashboard입니다. 새 run은 기존 화면의 계약을 따르는 fixture로 추가합니다. 실제 측정 데이터를 연결하는 작업은 별도 adapter와 검증이 필요합니다.

## Files and Contract

| File | Responsibility |
| --- | --- |
| `api/runs.json` | run selector에 표시할 고유 run ID와 workload metadata |
| `api/runs/<run_id>/summary.json` | training·workload와 aggregate resource metric |
| `api/runs/<run_id>/resources.json` | per-node와 per-GPU resource |
| `api/runs/<run_id>/interconnect.json` | topology matrix |
| `api/runs/<run_id>/data-movement.json` | phase별 전송 경로와 peak memory |
| `api/runs/<run_id>/storage.json` | device I/O와 checkpoint |

metric 이름과 단위는 [profiling metric contract](https://github.com/daegyu94/post-training-lab/blob/profiling/docs/metric-schema.md)를 기준으로 합니다. Observatory fixture의 구체적인 구조는 기존 JSON과 `index.html`의 renderer가 결정합니다. profiling schema만 통과했다고 dashboard 호환성이 검증되는 것은 아닙니다.

## Procedure

1. 기존 SFT 또는 agentic RL run 중 같은 workload의 fixture 디렉터리를 복사하고 새로운 고유 run ID를 지정합니다.
2. 다섯 endpoint와 registry의 run ID, framework, workload, node·GPU 수와 topology를 일관되게 갱신합니다. metric 단위를 유지하고 합성 데이터임을 표시합니다.
3. 기존 renderer가 지원하지 않는 workload는 `index.html`의 관련 화면과 API 표시까지 먼저 구현합니다. run label만 바꾸어 DPO나 다른 알고리즘이 지원된다고 표시하지 않습니다.
4. [로컬 실행 실습](labs/01-observe-runs.md#prerequisites-and-start)의 서버를 시작합니다. registry와 다섯 endpoint의 HTTP 응답, run 전환, 각 view, API explorer와 Export JSON을 확인합니다. 새 run뿐 아니라 기존 SFT·RL run도 확인합니다.
5. 시나리오가 보여 주는 질문, 예상 관측과 한계를 `docs/labs/`에 작성하고 README에서 연결합니다. 실제 benchmark 결과로 해석하지 않습니다.

API 경로는 `api/...`처럼 사이트 기준 상대 경로를 유지해야 GitHub Pages의 저장소 subpath에서도 동작합니다. `api/**` 변경은 Pages workflow의 재배포 대상입니다. 큰 trace, model artifact와 credential은 저장소에 넣지 않습니다.
