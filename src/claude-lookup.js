// Looks a word up with Claude and returns a dictionary entry in Korean.
// Bundled to www/claude-lookup.js by `npm run build:claude` (esbuild).
import Anthropic from "@anthropic-ai/sdk";

const SCHEMA = {
  type: "object",
  properties: {
    found: { type: "boolean", description: "false if this is not a real English word or phrase" },
    word: { type: "string", description: "the headword, corrected spelling if the input had a typo" },
    pos: { type: "string", description: "part of speech abbreviation such as n., v., adj., adv., phr." },
    ipa: { type: "string", description: "IPA pronunciation, or empty" },
    meanings: { type: "array", items: { type: "string" }, description: "1-4 Korean meanings, most common first" },
    example: { type: "string", description: "one natural English example sentence using the word" },
    example_ko: { type: "string", description: "Korean translation of the example" },
    note: { type: "string", description: "one short Korean usage note, or empty" },
  },
  required: ["found", "word", "pos", "ipa", "meanings", "example", "example_ko", "note"],
  additionalProperties: false,
};

const SYSTEM =
  "You are an English-Korean learner's dictionary for Korean students. " +
  "Given an English word or phrase, return its dictionary entry. Meanings and notes are in Korean. " +
  "Keep meanings short, the way a Korean vocabulary book lists them. " +
  "If the input is not a real English word or phrase, set found to false and leave the other fields empty.";

export async function lookup({ apiKey, model, word }) {
  // The key is the user's own, typed into this app on their device, so calling from the WebView is intended.
  const client = new Anthropic({ apiKey, dangerouslyAllowBrowser: true, maxRetries: 1, timeout: 60_000 });
  const params = {
    model,
    max_tokens: 2000,
    system: SYSTEM,
    messages: [{ role: "user", content: word }],
    output_config: { effort: "low", format: { type: "json_schema", schema: SCHEMA } },
  };
  let response;
  try {
    if (model === "claude-opus-5-5") {
      // If a safety classifier declines, the API retries on a fallback model in the same call.
      response = await client.beta.messages.create({
        ...params,
        betas: ["server-side-fallback-2026-07-01"],
        fallbacks: "default",
      });
    } else {
      response = await client.messages.create(params);
    }
  } catch (error) {
    if (error instanceof Anthropic.AuthenticationError) throw new Error("API 키가 올바르지 않아요. 설정에서 다시 확인해 주세요.");
    if (error instanceof Anthropic.PermissionDeniedError) throw new Error("이 API 키로는 이 모델을 쓸 수 없어요.");
    if (error instanceof Anthropic.RateLimitError) throw new Error("요청이 너무 많아요. 잠시 뒤에 다시 해 주세요.");
    if (error instanceof Anthropic.BadRequestError) throw new Error("요청이 거절됐어요: " + error.message);
    if (error instanceof Anthropic.APIConnectionError) throw new Error("인터넷에 연결할 수 없어요.");
    if (error instanceof Anthropic.APIError) throw new Error("Claude 오류 (" + error.status + "). 잠시 뒤에 다시 해 주세요.");
    throw error;
  }
  if (response.stop_reason === "refusal") throw new Error("Claude가 이 단어에는 답하지 않았어요.");
  if (response.stop_reason === "max_tokens") throw new Error("답이 잘렸어요. 다시 시도해 주세요.");
  const text = response.content.filter((b) => b.type === "text").map((b) => b.text).join("");
  const entry = JSON.parse(text);
  entry.model = response.model;
  return entry;
}
