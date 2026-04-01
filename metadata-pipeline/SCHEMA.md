# CSNL MetaData Schema v1.0

## Purpose
NAS Memory 폴더의 모든 연구원/프로젝트/인프라 정보를 AI agent가 즉시 활용 가능한 구조화된 형태로 유지.

## Directory Structure
```
MetaData/
├── SCHEMA.md              ← 이 파일
├── registry.json          ← 마스터 인덱스 (모든 폴더 → 메타 파일 매핑)
├── members/
│   ├── JOP.json           ← 연구원별 통합 메타데이터
│   ├── SK.json
│   ├── ...
│   └── HG.json            ← alumni 포함
├── infrastructure/
│   ├── Grant.json
│   ├── CWLL.json
│   └── ...
├── reviews/
│   └── review_YYYY-MM-DD.json  ← pooled review 결과
└── _pipeline/
    ├── SKILL.md            ← agent pipeline 실행 가이드
    ├── scan_agent.md       ← 개별 스캔 에이전트 프롬프트
    ├── pooling_agent.md    ← 풀링 에이전트 프롬프트
    └── review_agent.md     ← 리뷰 에이전트 프롬프트
```

## Member JSON Schema
```json
{
  "initials": "JOP",
  "name_ko": "박준오",
  "name_en": "Joonoh Park",
  "role": "PhD student / Operator",
  "group": "A",
  "slack_id": "U06JGAX5HD5",
  "nas_root": "/Volumes/CSNL_new/Memory/JOP",
  "last_scanned": "2026-04-01",
  "projects": {
    "RingRepSca": {
      "status": "active|paused|completed|archived",
      "hypothesis": "...",
      "keywords": [],
      "period": {"start": "YYYY-MM", "end": "ongoing"},
      "publication_doi": null,
      "grant_link": "BRL P1 상대화",
      "code": {
        "languages": ["MATLAB"],
        "key_scripts": ["main.m", "simulation.m"],
        "total_files": 23,
        "subfolders": ["BDM_Magnitude"]
      },
      "data": {
        "type": "behavioral|fMRI|EEG|simulation",
        "subjects": 51,
        "paradigm": "ring size estimation",
        "has_raw": true,
        "has_neuroimaging": false,
        "nii_manifest": null
      },
      "results": {
        "figures": 15,
        "key_outputs": ["BrainDay poster"],
        "manuscript_status": "in_prep|submitted|revision|published"
      },
      "context": {
        "meeting_files": 5,
        "reference_papers": 3,
        "latest_meeting": "2026-02-13"
      },
      "has_template_json": true,
      "has_kb_json": true,
      "gaps": ["missing nii_manifest for tDCS subset"]
    }
  },
  "cross_references": ["MSY — serial dependence shared framework"],
  "notes": "Operator — manages pipeline infrastructure"
}
```

## Infrastructure JSON Schema
```json
{
  "folder_name": "Grant",
  "type": "administrative|shared_resource|alumni_archive|lab_seminar",
  "nas_path": "/Volumes/CSNL_new/Memory/Grant",
  "description": "연구비 제안서 및 보고서 아카이브",
  "contents": [
    {"name": "Grant_2024_BRL.pdf", "type": "proposal", "year": 2024}
  ],
  "last_scanned": "2026-04-01"
}
```

## Scan Rules
1. template.json / project.json / kb_*.json이 있으면 먼저 읽고 활용
2. Code/에서 파일 확장자 통계 (.m, .py, .R, .ipynb)
3. Data/에서 subject 폴더 수, .mat/.csv 존재 여부, .nii/.IMA 존재 여부
4. Results/에서 figure 파일 수, manuscript draft 존재 여부
5. Context/에서 meeting pptx 날짜 패턴, reference PDF 수
6. 빈 폴더 또는 Claude_context_individual만 있으면 status: "empty"
