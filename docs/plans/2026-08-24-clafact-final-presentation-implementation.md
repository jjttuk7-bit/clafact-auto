# CLAFACT-AUTO Final Presentation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 기존 발표자료의 디자인을 유지하면서 최신 구현과 통합 진행 원장을 반영한 22장 PPTX를 만든다.

**Architecture:** 원본 PPTX를 Open XML 구조로 분해하고, 기존 슬라이드 세 장을 복제하여 새 페이지를 만든다. 슬라이드 구조를 먼저 22장으로 확정한 뒤 텍스트와 도형 크기를 수정하고, 다시 조립하여 PowerPoint 렌더링과 텍스트 추출로 검증한다.

**Tech Stack:** PowerPoint Open XML, PPTX skill scripts, PowerPoint COM read-only rendering, Python `python-pptx` validation

---

### Task 1: 원본 보존과 작업본 분해

**Files:**
- Read: `C:/Users/USER/Downloads/CLAFACT_AUTO_최종발표_20260818.pptx`
- Create: `artifacts/pptx_build_20260824/unpacked/`

**Steps:**
1. 원본 파일 크기와 수정 시각을 기록한다.
2. PPTX 전용 `unpack.py`로 작업 폴더에 분해한다.
3. 원본 슬라이드가 19장인지 확인한다.

### Task 2: 22장 구조 확정

**Files:**
- Modify: `artifacts/pptx_build_20260824/unpacked/ppt/presentation.xml`
- Create: 복제 슬라이드 3개 및 관련 관계 파일

**Steps:**
1. 기존 5쪽을 복제하여 복합 Claim 재투입 슬라이드를 만든다.
2. 기존 12쪽을 복제하여 기사 시점 값 보호 슬라이드를 만든다.
3. 기존 17쪽을 복제하여 문제 유형별 하네스 슬라이드를 만든다.
4. 새 슬라이드를 각각 기존 7·12·16쪽 다음에 배치한다.
5. 슬라이드 수와 순서를 확인한다.

### Task 3: 최신 내용 반영

**Files:**
- Modify: `artifacts/pptx_build_20260824/unpacked/ppt/slides/slide*.xml`

**Steps:**
1. 기존 4~7쪽의 고정 Claim 수와 처리 역할을 수정한다.
2. 기존 5쪽의 전체 파이프라인에 공식 표 구조·공표 확인·재투입을 반영한다.
3. 새 복합 Claim 슬라이드에 부모·자식·재진입 흐름을 작성한다.
4. KOSIS 표·좌표 설명에 메타데이터와 다중 기간 근거를 반영한다.
5. 새 기사 시점 값 보호 슬라이드에 수정일·공표일·안전 보류를 작성한다.
6. 실행 화면 슬라이드의 단계 목록을 최신화한다.
7. 평가 페이지를 문제 묶음별 개선과 최종 수용 기준으로 바꾼다.
8. 현황 페이지에 1,542·24·1,518·연결 실패 0을 반영한다.
9. 문제 분포 페이지를 680·222·206·199·101·63·47로 바꾼다.
10. 새 하네스 페이지와 최종 실행계획 페이지를 작성한다.
11. 22개 하단 페이지 번호를 정리한다.

### Task 4: 조립과 구조 검증

**Files:**
- Create: `deliverables/CLAFACT_AUTO_최종발표_20260824.pptx`

**Steps:**
1. `clean.py`로 사용하지 않는 파일을 정리한다.
2. `pack.py`로 새 PPTX를 만든다.
3. Open XML 검증기를 실행한다.
4. `python-pptx`로 22장과 핵심 문구를 확인한다.
5. 원본 파일의 크기와 수정 시각이 바뀌지 않았는지 확인한다.

### Task 5: 시각 검증과 수정

**Files:**
- Create: `artifacts/pptx_build_20260824/rendered/slide-*.png`
- Modify: 필요 시 해당 슬라이드 XML

**Steps:**
1. PowerPoint 읽기 전용 렌더링으로 22개 PNG를 만든다.
2. 전체 모음 이미지와 수정 페이지의 원본 크기 이미지를 검토한다.
3. 텍스트 잘림, 도형 겹침, 잘못된 페이지 번호, 막대 길이를 수정한다.
4. 수정한 슬라이드를 다시 조립하고 재렌더링한다.
5. 최종 텍스트와 시각 상태를 한 번 더 확인한다.

### Task 6: 최종 전달

**Files:**
- Deliver: `deliverables/CLAFACT_AUTO_최종발표_20260824.pptx`

**Steps:**
1. 최종 파일 존재 여부와 크기를 확인한다.
2. 슬라이드 수 22장과 핵심 수치를 확인한다.
3. 사용자에게 PPTX 링크와 주요 변경 내용을 전달한다.

