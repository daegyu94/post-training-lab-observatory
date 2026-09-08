# Run History

Observatory의 첫 화면은 저장된 실행 이력입니다.
목록에서 run을 열면 종료 후에도 설정, 기록된 시계열·이벤트, 마지막 리소스 snapshot을 조회할 수 있습니다.
두 기록을 선택하면 설정과 주요 수치를 나란히 비교합니다.
`Profiling details`는 archive 안의 전체 profiling report가 있을 때 기존 상세 화면으로 연결하며, 원본 fixture를 다시 읽거나 Live demo를 실행하지 않습니다.

## Storage and Database

GitHub Pages의 history viewer에는 DB가 필요하지 않습니다.
`api/history/index.json`이 실행 목록을, `api/history/<archive_id>.json`이 각 기록을 보관합니다.
아래 명령으로 파일을 생성하고 Git에 커밋·게시하면 다른 브라우저에서도 같은 기록을 조회할 수 있습니다.
브라우저의 Export는 다운로드이며 서버에 이력을 저장하는 동작은 아닙니다.

현재 collector는 수집용 SQLite를 이미 사용합니다.
여러 학습 작업의 자동 등록·종료 처리, 인증된 검색 API, 대규모 시계열과 보존 정책을 운영하려면 별도 수집 서버와 DB가 필요합니다.
이번 구현은 완료된 report를 보관하고 읽는 단계이며, 학습 framework의 lifecycle adapter나 중앙 운영 서버를 추가하지 않습니다.

## Archive a Profiling Report

기존 대시보드의 `Export JSON` 또는 같은 구조의 framework report를 입력으로 사용합니다.
`synthetic`은 반드시 boolean으로 명시하고, `run.run_id`와 각 snapshot의 `run_id`를 일치시킵니다.
실제 시작·종료 시각은 timezone을 포함한 ISO 8601로 입력합니다.
CLI의 `--status`, `--started-at`, `--ended-at`은 report의 run metadata보다 우선합니다.

```sh
python -m telemetry.history \
  --input artifacts/training-report.json \
  --archive-id train-001-completed \
  --status completed \
  --started-at 2026-09-08T06:00:00Z \
  --ended-at 2026-09-08T07:00:00Z
```

실패한 실행은 `--status failed --failure-reason "Worker exited during checkpoint"`처럼 원인을 함께 기록합니다.
실행 중 snapshot은 `--status running`과 시작 시각만 지정합니다.
동일한 실행의 후속 snapshot은 새로운 `--archive-id`로 보관하며, 기존 파일을 덮어쓰지 않습니다.
이력 목록의 Running은 저장 당시 상태이며 실시간 상태가 아닙니다.

`history`를 포함하면 실제 저장된 시계열과 이벤트도 표시합니다.
샘플·이벤트 시각은 실행 구간 안에 있어야 합니다.
시계열이 없으면 UI는 미수집으로 표시하며, 임의의 과거 값을 생성하지 않습니다.
Live demo의 export는 최근 최대 3,600개의 재생 샘플을 브라우저에서 유지한 범위만 포함하고 합성으로 표시합니다.

```json
{
  "history": {
    "samples": [
      {
        "timestamp": "2026-09-08T06:10:00Z",
        "metrics": {
          "training_tokens_per_second": 84000,
          "training_step_time_seconds_p95": 12.8,
          "gpu_utilization_percent": 84.8,
          "training_loss": 1.84
        }
      }
    ],
    "events": [
      {
        "timestamp": "2026-09-08T06:10:00Z",
        "level": "warning",
        "title": "Collective delay",
        "message": "Rank 16–23 exceeded the expected collective duration."
      }
    ]
  }
}
```

`summary.configuration`에 모델, 학습 설정, parallelism 등의 수집된 설정을 넣습니다.
`summary`, `resources`, `interconnect`, `storage`, `data_movement`는 기존 [profiling report 구조](adding-scenarios.md)를 사용합니다.
필수 summary 외에 없는 정보는 archive에 새로 생성하지 않습니다.

## Archive Measured Host Observations

SQLite에서 선택한 run을 export하면서 이력에도 추가할 수 있습니다.

```sh
python -m telemetry.export \
  --database artifacts/spark.sqlite3 \
  --run-id spark-host-20260908 \
  --archive-dir api/history
```

이미 내려받은 snapshot도 보관할 수 있습니다.

```sh
python -m telemetry.history \
  --input api/telemetry.json \
  --archive-id spark-host-20260908-capture-2
```

Host 기록은 `Captured`로 표시하고 학습 완료·성공으로 해석하지 않습니다.
노드 전체 CPU·메모리·NIC 값이며 학습 프로세스, GPU, rank 또는 학습 설정을 수집한 기록이 아닙니다.
기존 `telemetry.html`은 collector 연결 확인용 화면으로 유지하며, 보관된 기록은 Run history에서 조회합니다.
Collector의 SQLite는 최근 10,000개 샘플을 유지하므로 장기 보관할 run은 수집 직후 export해야 합니다.

## Integrity and Publishing

Archive ID는 영문·숫자·`_`·`-`로 이루어진 최대 96자입니다.
이미 존재하는 ID는 거절하고 이전 기록을 보존합니다.
Linux 파일 잠금으로 동시 CLI 쓰기를 직렬화하고, archive 파일을 쓴 뒤 index를 원자적으로 교체합니다.
프로세스가 파일 저장 중 강제 종료되면 index에 없는 archive 파일이 남을 수 있으므로 해당 파일을 확인한 후 다른 ID로 재시도합니다.

생성된 `api/history/`의 새 archive와 index 변경을 검토·커밋하고 push하면 Pages가 게시합니다.
공개 사이트에 게시할 수 있는 설정과 metric만 포함하고, 큰 trace나 model artifact는 report에 넣지 않습니다.
현재 제공되는 학습 기록은 Synthetic example이며, Spark host 기록만 기존 실측 snapshot에서 가져왔습니다.
