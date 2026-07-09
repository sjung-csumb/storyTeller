export type StoryInput = {
  name: string;
  gender: string;
  age: string;
  personality: string;
  lesson: string;
  problemSituation: string;
  category: string;
  mood: string;
  place: string;
  era: string;
  style: string;
  appearance: string;
  outfit: string;
  signatureItem: string;
  behaviorTrait: string;
  favoriteTheme: string;
};

export function buildStoryPrompt(input: StoryInput) {
  return `
[제목]
[장르] 동화에 맞춰, 다음 변수들을 활용해 이야기를 생성해 주세요.

- **주인공**
  - 이름: ${input.name}
  - 성별: ${input.gender}
  - 나이: ${input.age}
  - 성향: ${input.personality}
  - 교훈: ${input.lesson}

- **주인공 외형 및 캐릭터 특징**
  - 생김새: ${input.appearance}
  - 옷차림: ${input.outfit}
  - 대표 소품: ${input.signatureItem}
  - 행동 특징: ${input.behaviorTrait}
  - 좋아하는 색/테마: ${input.favoriteTheme}

- **문제 상황**
  - ${input.problemSituation}

- **카테고리**
  - ${input.category}

- **분위기**
  - ${input.mood}

- **배경**
  - 장소: ${input.place}
  - 시대: ${input.era}

- **스토리 흐름**
  1. 도입 – 주인공이 ${input.mood}한 ${input.place}에서 ${input.problemSituation}을 마주한다.
  2. 갈등 – ${input.name}은 ${input.personality} 때문에 어려움을 겪지만, ${input.lesson}을 떠올리며 ...
  3. 전개 – 주요 사건, 조력자, 시험 등을 통해 스스로 생각할 기회를 얻는다.
  4. 클라이맥스 – 도전, 비밀, 전환점을 통해 올바른 행동을 직접 선택한다.
  5. 결말 – ${input.name}이 ${input.lesson}을 실천해 문제를 해결하고, ${input.mood}한 ${input.place}이 새롭게 빛난다.
  - 도입부에서 주인공의 생김새, 옷차림, 대표 소품, 행동 특징을 자연스럽게 보여주세요.

- **스타일**
  - 문체: ${input.style}
  - 언어: 한국어

- **캐릭터 묘사 유의사항**
  - 외모를 평가하지 말고 관찰 가능한 특징만 따뜻하게 묘사해 주세요.
  - 비교, 놀림, 수치심이 들어간 표현은 피해주세요.
  - 주인공의 특징은 이야기 안에서 일관되게 유지해 주세요.

- **안전 요구사항**
  - 아이를 겁주거나 벌주는 방식으로 해결하지 마세요.
  - 협박, 수치심, 죄책감, 과도한 공포 표현을 피해주세요.
  - 긍정적 강화와 스스로 선택하는 장면을 중심으로 써주세요.
  - 3~5세 아이가 이해할 수 있는 쉬운 한국어를 사용해주세요.
  - 의성어와 의태어를 자연스럽게 넣어주세요.

- **출력 형식**
  - 제목
  - 동화 본문
  - 부모님을 위한 한 줄 가이드
`.trim();
}
