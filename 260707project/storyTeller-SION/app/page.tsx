"use client";

import { FormEvent, useState } from "react";
import { buildStoryPrompt } from "../lib/storyPrompt";

const initialForm = {
  name: "지우",
  gender: "선택 안함",
  age: "5세",
  personality: "상상력이 풍부하고 공주님 이야기를 좋아함",
  lesson: "양치질은 내 몸을 반짝반짝 지키는 용기 있는 행동",
  problemSituation: "양치질을 싫어해서 매일 밤 도망 다님",
  category: "생활습관",
  mood: "따뜻하고 반짝이는",
  place: "구름 왕국",
  era: "현대",
  style: "구연동화식",
  appearance: "동그란 얼굴, 큰 눈, 짧은 검은 머리",
  outfit: "분홍 원피스와 별무늬 양말",
  signatureItem: "작은 토끼 인형",
  behaviorTrait: "신나면 폴짝폴짝 뛰고, 궁금하면 왜요?라고 자주 물음",
  favoriteTheme: "분홍색, 반짝이는 것, 공주님 분위기"
};

type StoryForm = typeof initialForm;

const fields: Array<{
  name: keyof StoryForm;
  label: string;
  type?: "input" | "textarea" | "select";
  options?: string[];
}> = [
  { name: "name", label: "이름" },
  { name: "gender", label: "성별", type: "select", options: ["선택 안함", "남자", "여자"] },
  { name: "age", label: "나이", type: "select", options: ["3세", "4세", "5세"] },
  { name: "personality", label: "성향", type: "textarea" },
  { name: "appearance", label: "생김새", type: "textarea" },
  { name: "outfit", label: "옷차림" },
  { name: "signatureItem", label: "대표 소품" },
  { name: "behaviorTrait", label: "행동 특징", type: "textarea" },
  { name: "favoriteTheme", label: "좋아하는 색/테마", type: "textarea" },
  { name: "problemSituation", label: "문제 상황", type: "textarea" },
  { name: "lesson", label: "교훈", type: "textarea" },
  { name: "category", label: "카테고리" },
  { name: "mood", label: "분위기" },
  { name: "place", label: "배경 장소" },
  { name: "era", label: "시대" },
  { name: "style", label: "문체" }
];

export default function Home() {
  const [form, setForm] = useState<StoryForm>(initialForm);
  const [promptPreview, setPromptPreview] = useState("");
  const [error, setError] = useState("");

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");

    const hasEmptyField = Object.values(form).some((value) => !value.trim());
    if (hasEmptyField) {
      setError("모든 입력값을 채워 주세요.");
      return;
    }

    setPromptPreview(buildStoryPrompt(form));
  }

  function updateField(name: keyof StoryForm, value: string) {
    setForm((prev) => ({ ...prev, [name]: value }));
  }

  return (
    <main className="shell">
      <section className="intro">
        <div>
          <p className="eyebrow">Children&apos;s Story Generator</p>
          <h1>AI 맞춤형 행동 교정 동화</h1>
          <p>
            아이의 성향, 문제 상황, 캐릭터 특징을 바탕으로 따뜻한 유아용 동화를
            생성합니다.
          </p>
        </div>
      </section>

      <section className="workspace">
        <form className="story-form" onSubmit={handleSubmit}>
          <div className="section-title">
            <h2>동화 요구사항</h2>
            <span>프롬프트 설계용 MVP</span>
          </div>

          <div className="field-grid">
            {fields.map((field) => (
              <label
                className={field.type === "textarea" ? "field wide" : "field"}
                key={field.name}
              >
                <span>{field.label}</span>
                {field.type === "select" ? (
                  <select
                    value={form[field.name]}
                    onChange={(event) => updateField(field.name, event.target.value)}
                  >
                    {field.options?.map((option) => (
                      <option key={option}>{option}</option>
                    ))}
                  </select>
                ) : field.type === "textarea" ? (
                  <textarea
                    value={form[field.name]}
                    onChange={(event) => updateField(field.name, event.target.value)}
                    rows={3}
                  />
                ) : (
                  <input
                    value={form[field.name]}
                    onChange={(event) => updateField(field.name, event.target.value)}
                  />
                )}
              </label>
            ))}
          </div>

          <button type="submit">
            프롬프트 만들기
          </button>

          {error ? <p className="error">{error}</p> : null}
        </form>

        <aside className="result-panel">
          <div className="section-title">
            <h2>프롬프트 미리보기</h2>
            <span>API 연결 전 단계</span>
          </div>
          {promptPreview ? (
            <article className="story-output">{promptPreview}</article>
          ) : (
            <p className="empty">
              입력값을 확인한 뒤 프롬프트를 만들면 여기에 결과가 표시됩니다.
            </p>
          )}
        </aside>
      </section>
    </main>
  );
}
