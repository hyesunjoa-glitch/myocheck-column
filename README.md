# 묘책 칼럼 (column.myocheck.kr)

실제로 올라온 고민에서 출발해 사주로 풀어보는 묘책의 칼럼 사이트예요.
묘책 본 사이트(myocheck.kr)와는 따로 움직여요. 본 사이트는 건드리지 않아요.

## 글이 올라가는 길

1. `content/columns/` 에 글 파일이 들어가요. (틀: `_template.md`)
2. 저장소(main)에 올라가면 자동으로 사이트를 만들어요.
3. 이때 **안전검사를 통과한 글만** 사이트에 올라가요.
4. 새 글 주소는 검색엔진(빙·네이버 등)에 바로 알려요. (IndexNow — 정식 오픈 뒤부터)

## 안전검사 — 하나라도 걸리면 발행되지 않아요

- 상태(status)가 `승인`이 아님 → 사람이 검수하기 전엔 안 올라가요
- 검수자(reviewer)가 비어 있음
- 실제 고민(concerns)이 없거나 출처가 없음 → 지어낸 사연은 못 올려요
- 연결 상품이 없거나 상품 링크가 비어 있음
- `[[사주해석]]` 자리가 남아 있음 → 해석 기준 문서가 오기 전엔 해석 글을 못 올려요
- `[○○ 대기]` 같은 빈자리가 남아 있음
- 검색용 제목이 30자를 넘음 → 제목이 길면 `seo_title:`에 30자 이내 제목을 따로 적어요 (화면 큰 제목은 그대로)

발행을 막지는 않고 **⚠️ 확인해 보세요**만 띄우는 것: "무조건·반드시·끝났어요·계속 연락" 같은 단정·집착 조장 말. 사연 인용이면 그대로 둬도 돼요.

`python build.py --check` 를 돌리면 글마다 왜 안 올라가는지 알려줘요.

## 판매형 칼럼 틀

- 맨 위: 짧은 답(결론) → 이 고민에서 시작했어요(실제 고민 인용) → 글 순서
- 가운데: `[[상품버튼]]` 자리에 상품 버튼 (없으면 소제목 가운데쯤에 자동으로 들어감)
- 맨 아래: 자주 묻는 질문 → 상품 버튼 → 글·검수 정보
- 버튼마다 추적 태그(UTM)가 붙어요: 어느 글(utm_campaign)의 어느 버튼(utm_medium: cta_mid / cta_toc / cta_sticky / rail)에서 왔는지

## AI 검색·검색엔진용 장치

- `robots.txt` — 정식 오픈 뒤 ChatGPT·Perplexity·Claude·구글·네이버·다음 봇 모두 허용
- `sitemap.xml`, `feed.xml`(RSS), `llms.txt`(AI용 사이트 안내서)
- 글마다 구조화 데이터(Article, FAQPage, BreadcrumbList) + 운영사(Organization, 푸터와 같은 값) + 검수자(WebPage reviewedBy)
- 검색 결과 제목: `seo_title(없으면 title) | myocheck(묘책사주)` — 브랜드 표기는 site.yml `brand_full`
- 글이 0개인 분류 페이지와 404는 검색에서 빼고 sitemap에도 안 넣어요
- 공유 미리보기 이미지(1200×630): `python3 scripts/make_og.py` 로 글마다 `static/og/주소.jpg`를 만들어요. **새 글을 쓰거나 제목을 바꾸면 한 번 돌려 주세요.** 없으면 기본 이미지로 공유돼요
- 검색엔진 소유 확인 태그: site.yml `naver_site_verification` / `google_site_verification` / `bing_site_verification`에 값만 붙여 넣기

## 스위치 (site.yml)

- `allow_indexing: false` → 시안 단계. 모든 봇 차단. **도메인 연결 뒤에 true로**
- `indexnow_enabled: false` → 정식 오픈 때 true로
- `ga4_id` → 구글 애널리틱스 ID를 넣으면 버튼 클릭이 기록돼요

## 상품 링크 (products.yml)

상품 링크가 비어 있어요. 링크가 들어가기 전에는 그 상품에 연결된 글은 발행되지 않아요.

## 노션 칼럼 공장 표
- 위치: 노션 「사주서비스 런칭 3주 스프린트 (D-16)」 아래 「📝 칼럼 공장 — column.myocheck.kr」
- 데이터소스 ID: `9c9745b1-b7b7-4fca-a2fb-381fa90e0410` (나중에 자동 동기화에 씀)
- 흐름: 글감 → 초안 → 검수중 → 승인 → 발행. 「승인」인 글만 사이트에 올라감.
- 글감은 실제 사람 고민(스레드·유튜브 댓글·구글 검색)에서만. 원문은 `research/`(공개 저장소 제외)에 보관.
