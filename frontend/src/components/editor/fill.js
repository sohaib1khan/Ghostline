export function wordsOf(code) {
  return code
    .trim()
    .split(/\s+/)
    .filter((word) => word.length > 0);
}

export function fillAnswer(code, blanks, values) {
  return wordsOf(code)
    .map((word, index) => {
      const blank = blanks.find((item) => item.index === index + 1);
      return blank ? values[String(blank.index)] || "" : word;
    })
    .join(" ");
}
