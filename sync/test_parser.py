#!/usr/bin/env python3
"""Quick parser test with real Slack messages."""

import json
import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
from sync_reading_db import parse_slack_message

# Real messages from #study-paper-reading
test_messages = [
    {
        "user": "U07728304R5",
        "user_name": "Boyun Lee",
        "text": """Stein H, Barbosa J, Bhatt DV (2024). "Unifying network model links recency and central tendency biases in working memory." eLife, 13:e86725.
범위: abstract, intro
정리: contraction bias (과거 trial들의 mean으로 현재 trial의 response가 attract되는 것)과 serial dependence가 사실은 서로 관련이 되어 있고, posterior parietal cortex가 working memory에 input을 주는 형식으로 작동해서 그렇다는 논문이다.
생각: inactivation 실험을 통해서 contraction bias와 serial dependence 효과가 감소했다는 것을 관측했다던데, 사실 두 bias가 긴밀한 관계가 있다는 것은 부정하기 어려운 것 같다.""",
        "ts": "1743353638.000000",
        "date": "2026-03-30 22:53:58 KST",
    },
    {
        "user": "U07728304R5",
        "user_name": "Boyun Lee",
        "text": """Yang, J., Zhang, H., & Lim, S. (2024). Sensory-memory interactions via modular structure explain errors in visual working memory. eLife, 13, RP95160.
범위: methods
내용: 저자들은 cardinal orientations가 frequent한데 비해 attraction이 아니라 repulsion이 생기는 모순에 대해 excitatory connection과 inhibitory connection이 나눠져있지만 둘 다 cardinal orientation 근처에서 강하게 tuning되어 있다는 식으로 설명한다.
생각: inhibitory neurons의 연결이 cardinal orientation tuning된 뉴런들에 더 많이 있는 것으로 생각할 수도 있으려나...?""",
        "ts": "1743088423.000000",
        "date": "2026-03-27 22:23:43 KST",
    },
    {
        "user": "U080KFS0TFZ",
        "user_name": "Saemi Jung",
        "text": """Neri, P., & Heeger, D. J. (2002). Spatiotemporal mechanisms for detecting and identifying image features in human vision. Nature Neuroscience, 5(8), 812–816.
범위: results 일부
내용: 피험자들의 행동 데이터를 분류할 때 4가지 response class를 사용해서 분류를 한 뒤 각 response class에 해당하는 noise images들을 모아 spatiotemporal인 mean과 variance를 각각 계산했다.
생각: 이후 피험자가 Yes라고 응답한 class의 값들은 더하고, No라고 응답한 class의 값들은 빼는 방식으로 최종 kernel을 산출했는데, kernel computation 파트 관련해서는 나중에 디테일하게 봐야할 것 같다.""",
        "ts": "1743087895.000000",
        "date": "2026-03-27 19:44:55 KST",
    },
]

print("=" * 60)
print("Paper Scout Parser Test")
print("=" * 60)

for i, msg in enumerate(test_messages):
    print(f"\n--- Message {i+1}: {msg['user_name']} ---")
    result = parse_slack_message(msg)
    if result:
        print(f"  Paper: {result['paper']['authors']} ({result['paper']['year']})")
        print(f"  Title: {result['paper']['title']}")
        print(f"  Journal: {result['paper']['journal']}")
        print(f"  DOI: {result['paper'].get('doi', 'N/A')}")
        print(f"  Topics: {result['metadata']['topics']}")
        print(f"  Authors parsed: {result['metadata']['authors_parsed']}")
        print(f"  Sections: {list(result['reading'].keys())}")
        has_summary = bool(result['reading']['summary'])
        has_thoughts = bool(result['reading']['thoughts'])
        print(f"  Has summary: {has_summary}, Has thoughts: {has_thoughts}")
    else:
        print("  PARSE FAILED")

print("\n" + "=" * 60)
print("All tests complete.")
