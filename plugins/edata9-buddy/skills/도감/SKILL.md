---
name: 도감
description: 클로드 박사 과정 도감 40칸을 보여 주고, 해 본 칸을 체크합니다
argument-hint: "[비우면 보기 · '체크 되감기' 처럼 칸 이름으로 체크]"
disable-model-invocation: true
---

# 도감 — 클로드 박사 과정

받은 인자: $ARGUMENTS

도감 기록은 «박사 키우기» 세이브(`edata9-work/edata9-doctor/character.json`)에 함께 있다. 계산과 기록은 `${CLAUDE_PLUGIN_ROOT}/게임/doctor.py` 가 한다. 나온 글 전체를 네 답에 고치지 말고 그대로 옮겨 적는다(도구 결과는 학생 화면에서 접혀 있다).

1. 인자가 비었으면 `python "${CLAUDE_PLUGIN_ROOT}/게임/doctor.py" 도감` — 다섯 등급 표와 체크한 칸.
2. 인자가 `체크 <칸 이름>` 이면, 먼저 `${CLAUDE_PLUGIN_ROOT}/도감.md` 에서 가장 가까운 칸을 찾아 **«이 칸을 체크할까요?»** 라고 한 번 묻는다. 예라고 하면 `python "${CLAUDE_PLUGIN_ROOT}/게임/doctor.py" 도감 <칸 이름>`.
3. 캐릭터가 아직 없다는 글이 나오면 `/키우기 시작` 을 안내하고 멈춘다.
4. 칭찬이나 순위는 붙이지 않는다.
