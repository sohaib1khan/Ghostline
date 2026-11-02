import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  hasQuiz,
  optionsForItem,
  pickQuizQuestion,
  quizQuestionId,
  shuffle,
} from "./quizSelect.js";

describe("quizSelect", () => {
  it("shuffles without dropping options", () => {
    const source = ["a", "b", "c", "d"];
    const out = shuffle(source);
    assert.equal(out.length, 4);
    assert.deepEqual([...out].sort(), [...source].sort());
    assert.notEqual(out, source);
  });

  it("builds a stable question id", () => {
    assert.equal(
      quizQuestionId("ex-1", { q: "What?", code: "print(1)" }),
      "ex-1|What?|print(1)",
    );
  });

  it("never repeats the last question when another exists", () => {
    const pool = [
      { exerciseId: "a", item: { q: "One", code: "", answer: "1", wrong: ["2"] } },
      { exerciseId: "a", item: { q: "Two", code: "", answer: "2", wrong: ["1"] } },
    ];
    const lastId = quizQuestionId("a", pool[0].item);
    const seen = { [lastId]: 1, [quizQuestionId("a", pool[1].item)]: 2 };
    for (let i = 0; i < 20; i += 1) {
      const next = pickQuizQuestion(pool, { lastId, seen });
      assert.ok(next);
      assert.notEqual(next.id, lastId);
    }
  });

  it("prefers unseen questions", () => {
    const pool = [
      { exerciseId: "a", item: { q: "Seen", code: "", answer: "1", wrong: ["2"] } },
      { exerciseId: "a", item: { q: "Fresh", code: "", answer: "3", wrong: ["4"] } },
    ];
    const seenId = quizQuestionId("a", pool[0].item);
    const next = pickQuizQuestion(pool, { seen: { [seenId]: 1 } });
    assert.equal(next.item.q, "Fresh");
  });

  it("includes the answer among shuffled options", () => {
    const options = optionsForItem({
      answer: "None",
      wrong: ["[1, 2, 3]", "[3, 1, 2]"],
    });
    assert.ok(options.includes("None"));
    assert.equal(options.length, 3);
  });

  it("falls back to ExplainBack only when quiz is empty", () => {
    assert.equal(hasQuiz({ quiz: [{ q: "x", answer: "1", wrong: ["2"] }] }), true);
    assert.equal(hasQuiz({ quiz: [] }), false);
    assert.equal(hasQuiz({}), false);
  });
});
