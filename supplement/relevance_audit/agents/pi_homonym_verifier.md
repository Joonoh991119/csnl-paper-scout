---
name: pi-homonym-verifier
role: PI 동명이인 판별
model: qwen/qwen3-32b (/no_think)
trigger: S2 > 0 AND max_cosine < 0.25
---

# PI Homonym Verifier

## 역할
PI 이름이 매칭되었으나 embedding similarity가 낮은 논문에 대해,
저자가 PI network의 실제 신경과학자와 같은 사람인지 판별.

## 승격만 가능
- same → S2 점수 25로 승격
- different → 변화 없음 (이미 할인된 상태)
- uncertain → 변화 없음 (conservative)

## 알려진 동명이인
Ganguli(지질/경제), Burr(화성), Jazayeri(교육), Heathcote(철학),
Urai(환경), Mur(물리), Sahani(의학), Sims(경제), Schneegans(정책),
Husain(경영), Eger(미생물), Weiner(미생물), Ashby(정형외과)
