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

1. Run selector에서 `Atlas · baseline` (`pt-1041`)을 선택합니다. Overview의 throughput과 주요 phase, Data paths의 전송 경로, Storage의 checkpoint 지표를 기록합니다.
2. `Atlas · communication study` (`pt-1042`)로 전환하고 같은 지표를 비교합니다. 어떤 phase와 resource가 병목 가설을 뒷받침하는지, 실제 측정이라면 추가로 어떤 counter나 trace가 필요한지 적습니다. 합성 시나리오 간 차이를 실제 성능 개선이나 인과관계로 해석하지 않습니다.
3. `Orion · agentic RL` (`rl-2051`)의 Workload를 확인합니다. SFT 화면과 다른 rollout·agent 지표를 찾아 기록합니다. 이 화면은 RL training command를 실행하지 않습니다.
4. API explorer에서 선택한 run의 `summary.json`과 `data-movement.json`을 요청합니다. HTTP 응답과 화면 값의 연결을 확인합니다.
5. `Export JSON`으로 snapshot을 저장합니다. `Live demo`를 켰다면 합성 stream 재생임을 기록하고, 원본 fixture와 replay 중 화면을 구분합니다.

## Expected Evidence

run ID, 비교한 metric·단위·값, 병목 가설, 추가 검증에 필요한 실제 측정과 `synthetic` 표시를 포함한 짧은 Markdown note를 남깁니다. API 요청이 성공하고 run을 바꿀 때 화면이 갱신되어야 합니다. Export 파일은 로컬 결과로 보관합니다.

JSON 요청이 실패하면 저장소 루트에서 서버를 실행했는지, URL의 port와 `api/runs.json` 경로가 맞는지 확인합니다. 이 실습의 완료는 데이터 탐색과 evidence 작성이며 실제 모델 품질·성능 검증이 아닙니다.

## Cleanup and Next Steps

서버 terminal에서 `Ctrl-C`로 종료합니다. 다운로드한 snapshot은 필요할 때만 보관하고 Git에 추가하지 않습니다. 실제 resource 수집은 [profiling 실습](https://github.com/daegyu94/post-training-lab/tree/profiling), 새 합성 run 추가는 [확장 가이드](../adding-scenarios.md)로 이어집니다.
