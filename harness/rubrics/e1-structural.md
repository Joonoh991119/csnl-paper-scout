# E1: Structural Compliance — 단계별 출력 스펙

## Scan Output (`paper-scout-candidates-{DATE}.md`)

### 필수 섹션
- [ ] Summary 블록 (후보 수, semantic gate 통과 수, embedding gate 통과 수, 최종 수)
- [ ] Per-candidate 블록 (최소 1개)

### Per-candidate 필수 필드
| Field | Type | Validation |
|-------|------|------------|
| title | string | non-empty |
| authors | string | "First et al." 또는 전체 리스트 |
| journal | string | target_journals에 포함 또는 bioRxiv |
| DOI | string | `10.xxxx/...` 패턴 |
| abstract | string | ≥50 words |
| semantic_distance | float | 0.0–1.0 범위 |
| embedding_cosine | float | ≥0.45 (threshold) |
| source | string | scan 경로 (PI search / anchor expansion / bioRxiv) |

### Fail Conditions
- embedding_cosine < 0.45 인 후보가 포함됨
- DOI 형식 불일치
- abstract 누락

---

## Score Output (`paper-scout-scores-{DATE}.md`)

### 필수 섹션
- [ ] Selection summary (선정 기준, threshold)
- [ ] Per-paper scoring table

### Per-paper × Per-member 필수 필드
| Field | Type | Validation |
|-------|------|------------|
| D1_direct_advance | int 0-10 | |
| D2_hypothesis_tension | int 0-10 | |
| D3_method_import | int 0-10 | |
| D4_competitive_signal | int 0-10 | |
| D5_reframing_power | int 0-10 | |
| composite | int | = max(D1..D5) |
| reasoning | string | per-dimension 1문장 이상 |
| quote | string | D score ≥7 인 차원에 abstract 직접 인용 필수 |

### Fail Conditions
- composite ≠ max(D1..D5)
- D ≥7 인데 quote 없음
- 멤버가 context-bundle.json에 없음

---

## Team Output (`paper-scout-draft-{DATE}.md`)

### 필수 섹션
- [ ] Generation summary (papers, iterations, convergence status)
- [ ] Per-post 블록
- [ ] Team Verdict Log

### Per-post 필수 필드
| Field | Validation |
|-------|------------|
| :fire: hook | ≤120 chars, Korean, 2줄 이내 |
| *title* | 논문 제목 (bold) |
| _author line_ | "First et al. — Journal (Year)" |
| :link: DOI URL | valid URL |
| :dart: target lines | ≥1, `<@SLACK_ID>` 형식 |
| :label: dimension tag | D{n} + score + anchor |

### Team Verdict Log 필수
| Field | Validation |
|-------|------------|
| round_number | 1-3 |
| drafter_version | v1, v2, v3 |
| hook_evaluator | PASS / REWRITE(reason) |
| visual_agent | PASS / REPLACE / ADD_EQUATION / ADD_VISUAL |
| accuracy_evaluator | PASS / FIX(claim, correction) |
| member_advocate | per-member KEEP / STRENGTHEN / REMOVE_TAG |
| final_editor | POLISHED(text) |

---

## Review Output (`paper-scout-review-{DATE}.md`)

### 필수 섹션
- [ ] Summary table (Paper | Group A | Group B | Group C | Final)
- [ ] Per-paper detailed review

### Per-group verdict
| Field | Validation |
|-------|------------|
| verdict | APPROVE / MODIFY(edit) / ESCALATE |
| reasoning | ≥2 sentences |
| tagging_check | add/remove recommendations |

---

## Post Output (`paper-scout-log-{DATE}.md`)

### 필수 필드
| Field | Validation |
|-------|------------|
| channel | paper-reading-study (C06KJ95MGGZ) |
| posted_count | int ≥1 |
| timestamp | ISO 8601 |
| user_confirmed | true |
| per_post_status | success / failed |
