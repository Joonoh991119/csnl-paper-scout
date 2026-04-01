# Fetch Rescue SKILL — PDF 수집 실패 복구

## 목적
NAS 보충 파이프라인에서 Cloudflare/bot detection으로 실패한 논문 PDF를 복구한다.

## 전제 조건
- NAS 마운트: `/Volumes/CSNL_new/Memory/Papers/_new_supplement/`
- Chrome Extension (Claude in Chrome) 연결 (browser relay용)
- `rescue_unified.py` 위치: `supplement/` 디렉토리

## 전략 우선순위 (Strategy Cascade)

| # | Strategy | 대상 | 작동 원리 | 성공률 |
|---|----------|------|-----------|--------|
| S1 | PMC HTTPS mirror | PMC deposit 있는 OA 논문 | NCBI OA API → HTTPS tar.gz → PDF 추출 | ~70% (deposit 있으면) |
| S2 | Cell.com browser relay | Cell Press (celrep, cub, neuron, isci) | Chrome에서 PDF 로드 → JS fetch → POST localhost:18765 | ~95% |
| S3 | PMC FTP | S1 실패 시 fallback | curl FTP tar.gz | ~60% |
| S4 | eLife CDN | eLife 논문 | `cdn.elifesciences.org/articles/{id}/eLife-{id}-v{n}.pdf` | ~30% (Cloudflare) |
| S5 | Frontiers direct | Frontiers 논문 | DOI resolve → append /pdf | ~30% (Cloudflare) |
| S6 | Unpaywall OA | 비출판사 OA 링크 있는 논문 | api.unpaywall.org → direct PDF URL | ~20% |
| S7 | ScienceDirect browser relay | 순수 Elsevier (neuroimage, cognition 등) | Chrome으로 article page → View PDF → relay | 0% (IP 차단 시) |

## 실행 방법

### 자동 모드 (S1, S3-S6)
```bash
# 전체 실패 목록 스캔
python3 rescue_unified.py

# 특정 출판사만
python3 rescue_unified.py --publisher elife

# 단일 DOI
python3 rescue_unified.py --doi 10.7554/eLife.88652

# 현황 확인
python3 rescue_unified.py --status

# Dry run
python3 rescue_unified.py --dry-run
```

### 브라우저 릴레이 모드 (S2, S7)

**Step 1**: 릴레이 서버 시작
```bash
python3 rescue_unified.py --serve-only
# → http://127.0.0.1:18765 에서 대기
```

**Step 2**: Claude가 Chrome Extension에서 실행
```
1. Chrome Extension으로 PDF URL 탐색
2. PDF 로드 확인 (Chrome PDF viewer에 표시)
3. JavaScript 실행:

(async () => {
    const resp = await fetch(window.location.href);
    const blob = await resp.blob();
    const arrayBuf = await blob.arrayBuffer();
    const postResp = await fetch('http://127.0.0.1:18765', {
        method: 'POST',
        headers: { 'X-Filename': '{doi_safe_name}.pdf', 'Content-Type': 'application/pdf' },
        body: arrayBuf
    });
    return 'OK: ' + await postResp.text();
})()
```

**Step 3**: 릴레이 저장된 PDF를 NAS로 이동
```bash
python3 move_rescued.py  # 또는 수동으로 /tmp/elsevier_rescue/ → NAS
```

### Cell Press 전용 워크플로우
1. Cell.com PDF URL 패턴: `https://www.cell.com/{journal}/pdf/{PII}.pdf`
2. 저널별 URL:
   - Cell Reports: `cell-reports`
   - Current Biology: `current-biology`
   - Neuron: `neuron`
   - iScience: `iscience`
3. Chrome Extension으로 URL 탐색 → PDF viewer 확인 → relay JS 실행

### Elsevier ScienceDirect 제약
- **IP 147.47.66.137 (SNU)** 에서 /pdfft endpoint 전면 차단
- Article page는 로드되지만 PDF download만 선택적 차단
- 시도한 모든 방법 실패: JS fetch, JS navigation, simulated click, Elsevier API, cookie+requests
- **해결 방법**: VPN/다른 IP, 또는 rate limit 완전 해제 후 (수일 소요)

## Failure Registry
`candidates/failure_registry.json` — DOI별 시도 이력 + 현재 상태

상태값:
- `success`: 성공
- `failed`: 자동 전략 실패 (재시도 가능)
- `needs_browser_cell`: Cell Press browser relay 필요
- `needs_browser_elsevier`: ScienceDirect browser relay 필요 (IP 차단 해제 후)
- `exhausted`: 모든 자동 전략 소진 (수동 필요)

## 임베딩 후처리
PDF 저장 후 반드시 embedder 실행:
```bash
python3 embedder.py
```
또는 scheduled task가 1시간마다 자동 실행됨.

## Known Issues
1. PMC12117960 tar.gz (FTP): 파일 깨짐 → HTTPS mirror로 해결
2. eLife CDN: Cloudflare 차단 빈도 높음 → PMC FTP가 더 안정적
3. SNU WAM proxy: 브라우저 수준 인증, cookie/JS fetch로 전달 불가
4. Chrome Extension에서 blob download가 disk에 안 저장됨 → localhost relay가 유일한 방법
